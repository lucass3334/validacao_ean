from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import time
import random
import os
import json
import logging
import requests as http_requests
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

logger = logging.getLogger("scraper_orquestrador")
SITE_TIMEOUT_S = 20  # Hard timeout per site

from cobasi_ean_api import buscar_produto_por_ean as cobasi_buscar_html, extrair_informacoes_produto as cobasi_extrair
from petlove_ean_api import buscar_produto_petlove
from amazon_ean_api import buscar_produto_amazon
from mercadolivre_ean_api import buscar_produto_mercadolivre
from magalu_ean_api import buscar_produto_magalu
from bing_images_api import buscar_candidatos_bing

router = APIRouter()

# ---------------------------------------------------------------------------
# IA validation: compare product name vs scraped title
# ---------------------------------------------------------------------------

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")


def _validar_titulo_ia(nome_original: str, titulo_encontrado: str) -> bool:
    """Usa IA para validar se o titulo encontrado corresponde ao produto original."""
    if not OPENAI_API_KEY or not titulo_encontrado:
        # Fallback: simple keyword matching
        return _validar_titulo_simples(nome_original, titulo_encontrado)

    try:
        resp = http_requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-5.4-mini",
                "max_completion_tokens": 10,
                "reasoning": {"effort": "none"},
                "temperature": 0,
                "messages": [
                    {
                        "role": "system",
                        "content": "Voce valida se dois nomes de produto se referem ao MESMO produto. Responda APENAS 'sim' ou 'nao'. Considere que abreviacoes, ordem diferente de palavras, e marcas equivalentes sao aceitas. Mas produtos completamente diferentes (ex: racao vs tela de celular) devem ser 'nao'."
                    },
                    {
                        "role": "user",
                        "content": f"Produto original: {nome_original}\nProduto encontrado: {titulo_encontrado}\n\nSao o mesmo produto?"
                    }
                ]
            },
            timeout=10,
        )
        if resp.status_code == 200:
            answer = resp.json()["choices"][0]["message"]["content"].strip().lower()
            return answer.startswith("sim")
    except Exception:
        pass

    return _validar_titulo_simples(nome_original, titulo_encontrado)


def _validar_titulo_simples(nome_original: str, titulo_encontrado: str) -> bool:
    """Fallback: validacao por palavras-chave em comum."""
    if not titulo_encontrado:
        return False

    nome_lower = nome_original.lower()
    titulo_lower = titulo_encontrado.lower()

    # Palavras significativas do nome original (>3 chars, sem preposicoes)
    stopwords = {'para', 'com', 'cães', 'caes', 'gato', 'gatos', 'adulto', 'adultos', 'filhote', 'filhotes', 'porte', 'sabor'}
    palavras = [p for p in nome_lower.split() if len(p) > 3 and p not in stopwords]

    if not palavras:
        return False

    matches = sum(1 for p in palavras if p in titulo_lower)
    ratio = matches / len(palavras)

    return ratio >= 0.4

# Rate limiting globals
_request_count = 0
_last_reset = time.time()


def _rate_limit():
    """
    Rate limit curto entre tentativas de sites diferentes no MESMO produto.
    100 requests por minuto maximo (pausa de 60s se atingir o limite).
    Entre requests: 0.3-0.8s (suficiente pra nao ser bloqueado).
    """
    global _request_count, _last_reset
    if _request_count >= 100:
        elapsed = time.time() - _last_reset
        if elapsed < 60:
            time.sleep(60 - elapsed)
        _request_count = 0
        _last_reset = time.time()
    time.sleep(random.uniform(0.3, 0.8))
    _request_count += 1


def _buscar_cobasi(ean: str):
    """Busca na Cobasi e extrai imagem direto da pagina de busca (1 request so)."""
    html = cobasi_buscar_html(ean)
    if not html:
        return None
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        # Extrair imagem direto do resultado de busca (sem navegar pro produto)
        for img in soup.find_all('img', alt=True):
            src = img.get('src', '') or img.get('data-src', '')
            alt = img.get('alt', '')
            if not src or not alt:
                continue
            # Must be from vtexassets (product images), not cms/uploads (icons)
            if 'vtexassets.com' not in src:
                continue
            # Reject SVGs, icons, logos
            if '.svg' in src.lower() or 'icon' in src.lower() or 'logo' in src.lower():
                continue
            # Must be a product image (jpg/png/webp)
            if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                return {'ean': ean, 'nome': alt.strip(), 'imagem_url': src, 'source': 'cobasi'}
    except Exception:
        pass
    return None


def _buscar_petz(nome: str, ean: str):
    """Petz requires Selenium — call via its own endpoint."""
    try:
        from petz_ean_api import buscar_produto_por_nome, extrair_informacoes_produto, obter_detalhes_do_produto
        html = buscar_produto_por_nome(nome)
        if not html:
            return None
        nome_prod, url_prod, _, _ = extrair_informacoes_produto(html)
        if not nome_prod or not url_prod:
            return None
        imagem, _, _, ean_encontrado = obter_detalhes_do_produto(url_prod)
        ean_correto = ean == ean_encontrado if ean and ean_encontrado else False
        if imagem:
            return {
                'ean': ean,
                'nome': nome_prod,
                'imagem_url': imagem,
                'source': 'petz',
                'ean_correto': ean_correto,
            }
    except Exception:
        pass
    return None


class BuscarImagemRequest(BaseModel):
    ean: str
    nome: str


class BuscarImagemResponse(BaseModel):
    success: bool
    ean: str
    image_url: Optional[str] = None
    source: Optional[str] = None
    titulo: Optional[str] = None
    confiavel: bool = False
    error: Optional[str] = None


class ProdutoBatch(BaseModel):
    ean: str
    nome: str


class BatchRequest(BaseModel):
    produtos: list[ProdutoBatch]
    webhook_url: str
    catalogo_id: Optional[int] = None


def _tentar_site(source_name: str, buscar_fn, ean: str, nome: str, por_nome: bool = False) -> Optional[dict]:
    """
    Tenta um motor com timeout hard. Retorna dict {imagem_url, source, titulo, confiavel}
    se achou+IA-aprovou, ou None caso contrario.
    Loga inicio, tempo e resultado de cada tentativa.
    """
    start = time.time()
    logger.info(f"[BUSCA] start {source_name} ean={ean}")
    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit((lambda: buscar_fn(nome, ean)) if por_nome else (lambda: buscar_fn(ean)))
            try:
                resultado = future.result(timeout=SITE_TIMEOUT_S)
            except FuturesTimeout:
                logger.warning(f"[BUSCA] {source_name} TIMEOUT apos {SITE_TIMEOUT_S}s ean={ean}")
                return None

        elapsed = round(time.time() - start, 1)

        if not resultado or not resultado.get('imagem_url'):
            logger.info(f"[BUSCA] {source_name} sem imagem em {elapsed}s ean={ean}")
            return None

        img = resultado['imagem_url']
        img_lower = img.lower().split('?')[0]  # strip query string before extension check

        # Whitelist: aceitar somente jpg/jpeg/png/webp
        formatos_aceitos = ('.jpg', '.jpeg', '.png', '.webp')
        if not any(img_lower.endswith(ext) for ext in formatos_aceitos):
            logger.info(f"[BUSCA] {source_name} formato nao suportado em {elapsed}s ean={ean} url={img[:80]}")
            return None

        # Anti-icone: rejeita explicitamente
        if 'icon' in img_lower or 'logo' in img_lower or '/sprite' in img_lower:
            logger.info(f"[BUSCA] {source_name} icone/logo descartado em {elapsed}s ean={ean}")
            return None

        titulo = resultado.get('nome', '') or ''

        # IA validation: only if both names exist
        if titulo and nome:
            is_match = _validar_titulo_ia(nome, titulo)
            if not is_match:
                logger.info(f"[BUSCA] {source_name} IA reprovou em {elapsed}s ean={ean} titulo='{titulo[:60]}'")
                return None
            logger.info(f"[BUSCA] {source_name} IA APROVOU em {elapsed}s ean={ean}")
        else:
            logger.info(f"[BUSCA] {source_name} sem validacao IA em {elapsed}s ean={ean}")

        return {
            'imagem_url': img,
            'source': resultado.get('source', source_name),
            'titulo': titulo,
            'confiavel': True if not por_nome else resultado.get('ean_correto', False),
        }
    except Exception as e:
        elapsed = round(time.time() - start, 1)
        logger.warning(f"[BUSCA] {source_name} EXCECAO em {elapsed}s ean={ean}: {type(e).__name__}: {str(e)[:100]}")
        return None


def _tentar_bing_com_validacao(nome: str, ean: str) -> Optional[dict]:
    """
    Tier 3 fallback: busca multiplos candidatos no Bing Images e
    valida cada um com IA. Retorna o primeiro que a IA aprovar.
    Usa timeout de 20s na busca inicial.
    """
    start = time.time()
    logger.info(f"[BUSCA] start bing ean={ean} query='{nome[:60]}'")
    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(lambda: buscar_candidatos_bing(nome, ean, limite=10))
            try:
                candidatos = future.result(timeout=SITE_TIMEOUT_S)
            except FuturesTimeout:
                logger.warning(f"[BUSCA] bing TIMEOUT apos {SITE_TIMEOUT_S}s ean={ean}")
                return None

        elapsed = round(time.time() - start, 1)
        if not candidatos:
            logger.info(f"[BUSCA] bing sem resultados em {elapsed}s ean={ean}")
            return None

        logger.info(f"[BUSCA] bing retornou {len(candidatos)} candidatos em {elapsed}s, validando com IA...")

        for i, cand in enumerate(candidatos):
            titulo = cand.get('nome', '')
            if not titulo:
                continue
            is_match = _validar_titulo_ia(nome, titulo)
            if is_match:
                total_elapsed = round(time.time() - start, 1)
                logger.info(
                    f"[BUSCA] bing IA APROVOU candidato #{i+1} em {total_elapsed}s "
                    f"ean={ean} titulo='{titulo[:60]}' purl={cand.get('purl', '')[:60]}"
                )
                return {
                    'imagem_url': cand['imagem_url'],
                    'source': 'bing',
                    'titulo': titulo,
                    'confiavel': False,  # Bing eh fallback, menos confiavel
                }
            else:
                logger.info(f"[BUSCA] bing IA reprovou candidato #{i+1} titulo='{titulo[:60]}'")

        total_elapsed = round(time.time() - start, 1)
        logger.info(f"[BUSCA] bing todos {len(candidatos)} candidatos reprovados pela IA em {total_elapsed}s ean={ean}")
        return None
    except Exception as e:
        elapsed = round(time.time() - start, 1)
        logger.warning(f"[BUSCA] bing EXCECAO em {elapsed}s ean={ean}: {type(e).__name__}: {str(e)[:100]}")
        return None


@router.post("/buscar_imagem", response_model=BuscarImagemResponse)
async def buscar_imagem(req: BuscarImagemRequest):
    ean = req.ean.strip()
    nome = req.nome.strip()

    ean_valido = len(ean) == 13 and ean.isdigit()
    overall_start = time.time()
    logger.info(f"[BUSCA] === inicio ean={ean} nome='{nome[:50]}' ===")

    # Tier 1: rapidos (HTTP, sem Selenium) - sub 3s em caso tipico
    tier1 = []
    if ean_valido:
        tier1 = [
            ("cobasi", _buscar_cobasi, False),
            ("amazon", buscar_produto_amazon, False),
            ("mercadolivre", buscar_produto_mercadolivre, False),
            ("magalu", buscar_produto_magalu, False),
        ]

    # Tier 2: lentos (Selenium) - so se Tier 1 falhou
    tier2 = []
    if ean_valido:
        tier2 = [
            ("petlove", buscar_produto_petlove, False),
        ]
    if nome:
        tier2.append(("petz", _buscar_petz, True))

    # Cascade T1 -> T2, primeiro que valida ganha
    for source_name, buscar_fn, por_nome in tier1 + tier2:
        _rate_limit()
        resultado = _tentar_site(source_name, buscar_fn, ean, nome, por_nome=por_nome)
        if resultado:
            total_elapsed = round(time.time() - overall_start, 1)
            logger.info(f"[BUSCA] === FIM SUCCESS source={source_name} total={total_elapsed}s ean={ean} ===")
            return BuscarImagemResponse(
                success=True,
                ean=ean,
                image_url=resultado['imagem_url'],
                source=resultado['source'],
                titulo=resultado['titulo'],
                confiavel=resultado['confiavel'],
            )

    # Tier 3: Bing Images como ultimo recurso (apenas se nome existe)
    # Busca ate 10 candidatos e valida cada um com IA, retorna primeiro aprovado
    if nome:
        _rate_limit()
        resultado = _tentar_bing_com_validacao(nome, ean)
        if resultado:
            total_elapsed = round(time.time() - overall_start, 1)
            logger.info(f"[BUSCA] === FIM SUCCESS source=bing total={total_elapsed}s ean={ean} ===")
            return BuscarImagemResponse(
                success=True,
                ean=ean,
                image_url=resultado['imagem_url'],
                source=resultado['source'],
                titulo=resultado['titulo'],
                confiavel=resultado['confiavel'],
            )

    total_elapsed = round(time.time() - overall_start, 1)
    logger.info(f"[BUSCA] === FIM NOT_FOUND total={total_elapsed}s ean={ean} ===")
    return BuscarImagemResponse(
        success=False,
        ean=ean,
        error="Imagem nao encontrada em nenhum site",
    )


def _processar_batch(produtos: list[dict], webhook_url: str, catalogo_id: int | None):
    resultados = []
    for prod in produtos:
        try:
            ean = prod['ean']
            nome = prod['nome']

            # Try EAN cascade (rate limit is inside each attempt)
            resultado = None
            if len(ean) == 13 and ean.isdigit():
                for buscar_fn in [_buscar_cobasi, buscar_produto_petlove, buscar_produto_amazon,
                                  buscar_produto_mercadolivre, buscar_produto_magalu]:
                    try:
                        _rate_limit()
                        resultado = buscar_fn(ean)
                        if resultado and resultado.get('imagem_url'):
                            break
                        resultado = None
                    except Exception:
                        continue

            # Fallback Petz
            if not resultado:
                try:
                    resultado = _buscar_petz(nome, ean)
                except Exception:
                    pass

            resultados.append({
                'ean': ean,
                'nome': nome,
                'imagem_url': resultado.get('imagem_url') if resultado else None,
                'source': resultado.get('source') if resultado else None,
                'confiavel': resultado.get('ean_correto', True) if resultado else False,
            })
        except Exception as e:
            resultados.append({
                'ean': prod.get('ean', ''),
                'nome': prod.get('nome', ''),
                'imagem_url': None,
                'source': None,
                'error': str(e),
            })

    # Send results via webhook
    try:
        http_requests.post(webhook_url, json={
            'catalogo_id': catalogo_id,
            'total': len(resultados),
            'com_imagem': sum(1 for r in resultados if r.get('imagem_url')),
            'resultados': resultados,
        }, timeout=30)
    except Exception:
        pass


@router.post("/buscar_imagens_batch")
async def buscar_imagens_batch(req: BatchRequest, background_tasks: BackgroundTasks):
    produtos = [{'ean': p.ean, 'nome': p.nome} for p in req.produtos]
    background_tasks.add_task(_processar_batch, produtos, req.webhook_url, req.catalogo_id)
    return {"message": "Processamento iniciado", "total": len(produtos)}


# ---------------------------------------------------------------------------
# Endpoints individuais para testar cada motor separadamente
# ---------------------------------------------------------------------------

class TestarMotorRequest(BaseModel):
    ean: str
    nome: Optional[str] = ""


class TestarMotorResponse(BaseModel):
    success: bool
    ean: str
    motor: str
    image_url: Optional[str] = None
    titulo: Optional[str] = None
    confiavel: bool = False
    validacao_ia: Optional[str] = None  # 'aprovado', 'reprovado', 'sem_validacao'
    error: Optional[str] = None
    detalhes: Optional[str] = None


def _testar_motor(motor_nome: str, buscar_fn, ean: str, nome: str = "", por_nome: bool = False):
    """Testa um motor individual e retorna resultado detalhado."""
    try:
        if por_nome:
            resultado = buscar_fn(nome, ean)
        else:
            resultado = buscar_fn(ean)

        if resultado is None:
            return TestarMotorResponse(
                success=False, ean=ean, motor=motor_nome,
                error=f"{motor_nome}: nenhum produto encontrado para EAN {ean}",
                detalhes="A busca retornou None. O site pode nao indexar este EAN, ou os seletores CSS estao desatualizados."
            )

        img = resultado.get('imagem_url')
        if not img:
            return TestarMotorResponse(
                success=False, ean=ean, motor=motor_nome,
                titulo=resultado.get('nome'),
                error=f"{motor_nome}: produto encontrado mas sem URL de imagem",
                detalhes=f"Produto: {resultado.get('nome', '?')}. O seletor de imagem nao encontrou tag <img> valida no HTML."
            )

        # Validate image URL
        if '.svg' in img.lower() or 'icon' in img.lower():
            return TestarMotorResponse(
                success=False, ean=ean, motor=motor_nome,
                titulo=resultado.get('nome'),
                image_url=img,
                error=f"{motor_nome}: URL retornada e um icone/SVG, nao imagem de produto",
                detalhes=f"URL: {img}"
            )

        # IA validation: compare product name vs scraped title
        titulo = resultado.get('nome', '')
        validacao = 'sem_validacao'
        is_valid = True

        if titulo and nome:
            is_match = _validar_titulo_ia(nome, titulo)
            validacao = 'aprovado' if is_match else 'reprovado'
            is_valid = is_match

        if not is_valid:
            return TestarMotorResponse(
                success=False, ean=ean, motor=motor_nome,
                image_url=img,
                titulo=titulo,
                confiavel=False,
                validacao_ia='reprovado',
                error=f"{motor_nome}: IA reprovou — titulo nao corresponde ao produto",
                detalhes=f"Original: '{nome}' | Encontrado: '{titulo}'"
            )

        return TestarMotorResponse(
            success=True, ean=ean, motor=motor_nome,
            image_url=img,
            titulo=titulo,
            confiavel=resultado.get('ean_correto', not por_nome),
            validacao_ia=validacao,
        )

    except Exception as e:
        return TestarMotorResponse(
            success=False, ean=ean, motor=motor_nome,
            error=f"{motor_nome}: excecao durante busca: {type(e).__name__}",
            detalhes=str(e)[:200]
        )


@router.post("/testar/cobasi", response_model=TestarMotorResponse)
async def testar_cobasi(req: TestarMotorRequest):
    """Testa busca de imagem na Cobasi por EAN. Passe 'nome' para validacao IA."""
    return _testar_motor("cobasi", _buscar_cobasi, req.ean, req.nome or "")


@router.post("/testar/petlove", response_model=TestarMotorResponse)
async def testar_petlove(req: TestarMotorRequest):
    """Testa busca de imagem na Petlove por EAN. Passe 'nome' para validacao IA."""
    return _testar_motor("petlove", buscar_produto_petlove, req.ean, req.nome or "")


@router.post("/testar/amazon", response_model=TestarMotorResponse)
async def testar_amazon(req: TestarMotorRequest):
    """Testa busca de imagem na Amazon por EAN. Passe 'nome' para validacao IA."""
    return _testar_motor("amazon", buscar_produto_amazon, req.ean, req.nome or "")


@router.post("/testar/mercadolivre", response_model=TestarMotorResponse)
async def testar_ml(req: TestarMotorRequest):
    """Testa busca de imagem no Mercado Livre por EAN. Passe 'nome' para validacao IA."""
    return _testar_motor("mercadolivre", buscar_produto_mercadolivre, req.ean, req.nome or "")


@router.post("/testar/magalu", response_model=TestarMotorResponse)
async def testar_magalu(req: TestarMotorRequest):
    """Testa busca de imagem no Magazine Luiza por EAN. Passe 'nome' para validacao IA."""
    return _testar_motor("magalu", buscar_produto_magalu, req.ean, req.nome or "")


@router.post("/testar/petz", response_model=TestarMotorResponse)
async def testar_petz(req: TestarMotorRequest):
    """Testa busca de imagem na Petz por NOME (com validacao de EAN)."""
    if not req.nome:
        return TestarMotorResponse(
            success=False, ean=req.ean, motor="petz",
            error="petz: campo 'nome' obrigatorio (Petz busca por nome, nao EAN)",
        )
    return _testar_motor("petz", _buscar_petz, req.ean, req.nome, por_nome=True)


@router.post("/testar/todos", response_model=list[TestarMotorResponse])
async def testar_todos(req: TestarMotorRequest):
    """Testa todos os 6 motores e retorna resultado de cada um."""
    resultados = []
    resultados.append(_testar_motor("cobasi", _buscar_cobasi, req.ean))
    resultados.append(_testar_motor("petlove", buscar_produto_petlove, req.ean))
    resultados.append(_testar_motor("amazon", buscar_produto_amazon, req.ean))
    resultados.append(_testar_motor("mercadolivre", buscar_produto_mercadolivre, req.ean))
    resultados.append(_testar_motor("magalu", buscar_produto_magalu, req.ean))
    if req.nome:
        resultados.append(_testar_motor("petz", _buscar_petz, req.ean, req.nome, por_nome=True))
    return resultados
