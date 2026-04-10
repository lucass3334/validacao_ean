from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import time
import random
import requests as http_requests

from cobasi_ean_api import buscar_produto_por_ean as cobasi_buscar_html, extrair_informacoes_produto as cobasi_extrair
from petlove_ean_api import buscar_produto_petlove
from amazon_ean_api import buscar_produto_amazon
from mercadolivre_ean_api import buscar_produto_mercadolivre
from magalu_ean_api import buscar_produto_magalu

router = APIRouter()

# Rate limiting globals
_request_count = 0
_last_reset = time.time()


def _rate_limit():
    global _request_count, _last_reset
    if _request_count >= 100:
        elapsed = time.time() - _last_reset
        if elapsed < 60:
            time.sleep(60 - elapsed)
        _request_count = 0
        _last_reset = time.time()
    time.sleep(random.uniform(3, 10))
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


@router.post("/buscar_imagem", response_model=BuscarImagemResponse)
async def buscar_imagem(req: BuscarImagemRequest):
    ean = req.ean.strip()
    nome = req.nome.strip()

    # Validate EAN
    ean_valido = len(ean) == 13 and ean.isdigit()

    if ean_valido:
        # Cascade by EAN: Cobasi → Petlove → Amazon → ML → Magalu
        sites_ean = [
            ("cobasi", _buscar_cobasi),
            ("petlove", buscar_produto_petlove),
            ("amazon", buscar_produto_amazon),
            ("mercadolivre", buscar_produto_mercadolivre),
            ("magalu", buscar_produto_magalu),
        ]

        for source_name, buscar_fn in sites_ean:
            try:
                _rate_limit()
                resultado = buscar_fn(ean)
                if resultado and resultado.get('imagem_url'):
                    return BuscarImagemResponse(
                        success=True,
                        ean=ean,
                        image_url=resultado['imagem_url'],
                        source=resultado.get('source', source_name),
                        titulo=resultado.get('nome'),
                        confiavel=True,
                    )
            except Exception:
                continue

    # Fallback: Petz by name (with EAN validation)
    try:
        _rate_limit()
        resultado = _buscar_petz(nome, ean)
        if resultado and resultado.get('imagem_url'):
            return BuscarImagemResponse(
                success=True,
                ean=ean,
                image_url=resultado['imagem_url'],
                source='petz',
                titulo=resultado.get('nome'),
                confiavel=resultado.get('ean_correto', False),
            )
    except Exception:
        pass

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

        return TestarMotorResponse(
            success=True, ean=ean, motor=motor_nome,
            image_url=img,
            titulo=resultado.get('nome'),
            confiavel=resultado.get('ean_correto', not por_nome),
        )

    except Exception as e:
        return TestarMotorResponse(
            success=False, ean=ean, motor=motor_nome,
            error=f"{motor_nome}: excecao durante busca: {type(e).__name__}",
            detalhes=str(e)[:200]
        )


@router.post("/testar/cobasi", response_model=TestarMotorResponse)
async def testar_cobasi(req: TestarMotorRequest):
    """Testa busca de imagem na Cobasi por EAN."""
    return _testar_motor("cobasi", _buscar_cobasi, req.ean)


@router.post("/testar/petlove", response_model=TestarMotorResponse)
async def testar_petlove(req: TestarMotorRequest):
    """Testa busca de imagem na Petlove por EAN."""
    return _testar_motor("petlove", buscar_produto_petlove, req.ean)


@router.post("/testar/amazon", response_model=TestarMotorResponse)
async def testar_amazon(req: TestarMotorRequest):
    """Testa busca de imagem na Amazon por EAN."""
    return _testar_motor("amazon", buscar_produto_amazon, req.ean)


@router.post("/testar/mercadolivre", response_model=TestarMotorResponse)
async def testar_ml(req: TestarMotorRequest):
    """Testa busca de imagem no Mercado Livre por EAN."""
    return _testar_motor("mercadolivre", buscar_produto_mercadolivre, req.ean)


@router.post("/testar/magalu", response_model=TestarMotorResponse)
async def testar_magalu(req: TestarMotorRequest):
    """Testa busca de imagem no Magazine Luiza por EAN."""
    return _testar_motor("magalu", buscar_produto_magalu, req.ean)


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
