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
    html = cobasi_buscar_html(ean)
    if not html:
        return None
    nome, url_produto = cobasi_extrair(html)
    if not nome or not url_produto:
        return None
    # Get image from product page
    try:
        from bs4 import BeautifulSoup
        resp = http_requests.get(url_produto, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            img = soup.find('img', alt='Imagem do Produto')
            if img and img.get('src'):
                return {'ean': ean, 'nome': nome, 'imagem_url': img['src'], 'source': 'cobasi'}
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
            _rate_limit()
            ean = prod['ean']
            nome = prod['nome']

            # Try EAN cascade
            resultado = None
            if len(ean) == 13 and ean.isdigit():
                for buscar_fn in [_buscar_cobasi, buscar_produto_petlove, buscar_produto_amazon,
                                  buscar_produto_mercadolivre, buscar_produto_magalu]:
                    try:
                        resultado = buscar_fn(ean)
                        if resultado and resultado.get('imagem_url'):
                            break
                        resultado = None
                        _rate_limit()
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
