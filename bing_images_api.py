"""
Bing Images como fallback de ultimo recurso.
Quando Cobasi/Amazon/ML/Magalu/Petlove/Petz nao acham o produto,
busca no Bing usando o nome do produto como query.

Bing Images retorna HTML estatico com os resultados embedded em
<a class="iusc"> com atributo m="{json}" contendo murl (imagem real)
e t (titulo).

Nao precisa de Selenium. Nao tem anti-bot agressivo (ao contrario do Google).
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
import re
import json
import html
import requests

router = APIRouter()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'pt-BR,pt;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
}

_FORMATOS_OK = ('.jpg', '.jpeg', '.png', '.webp')
_ANCHOR_RE = re.compile(r'class="iusc"[^>]*?\sm="([^"]+)"')


def _eh_imagem_valida(url: str) -> bool:
    """Whitelist de extensao + rejeita icones/logos."""
    if not url:
        return False
    u = url.lower().split('?')[0]
    if not any(u.endswith(ext) for ext in _FORMATOS_OK):
        return False
    if 'icon' in u or 'logo' in u or '/sprite' in u:
        return False
    return True


def buscar_candidatos_bing(nome: str, ean: str = '', limite: int = 10):
    """
    Busca candidatos no Bing Images. Retorna LISTA de ate `limite` dicts
    {imagem_url, nome, source} ou lista vazia.
    O orquestrador itera pelos candidatos aplicando validacao IA em cada um.
    """
    query = (nome or ean or '').strip()
    if not query:
        return []

    try:
        url = 'https://www.bing.com/images/search'
        r = requests.get(
            url,
            params={'q': query, 'form': 'HDRSC2'},
            headers=HEADERS,
            timeout=10,
        )
        if r.status_code != 200:
            return []

        anchors = _ANCHOR_RE.findall(r.text)
        if not anchors:
            return []

        candidatos = []
        for raw in anchors:
            if len(candidatos) >= limite:
                break
            try:
                m_str = html.unescape(raw)
                data = json.loads(m_str)
            except Exception:
                continue

            murl = data.get('murl', '')
            titulo = data.get('t') or data.get('desc', '') or ''

            if not _eh_imagem_valida(murl):
                continue
            if not titulo or len(titulo) < 10:
                continue

            candidatos.append({
                'ean': ean,
                'nome': titulo.strip(),
                'imagem_url': murl,
                'source': 'bing',
                'purl': data.get('purl', ''),  # pagina fonte (debug)
            })

        return candidatos
    except Exception:
        return []


def buscar_produto_bing(nome: str, ean: str = ''):
    """Compat: retorna apenas o primeiro candidato (sem validacao)."""
    cands = buscar_candidatos_bing(nome, ean, limite=1)
    return cands[0] if cands else None


@router.get("/buscar")
async def buscar(nome: str = '', ean: str = '', limite: int = 10):
    candidatos = buscar_candidatos_bing(nome, ean, limite=limite)
    if candidatos:
        return {
            'total': len(candidatos),
            'candidatos': candidatos,
            'Fonte': 'Bing Images',
        }
    return JSONResponse(status_code=404, content={"Erro": "Nada encontrado no Bing Images"})
