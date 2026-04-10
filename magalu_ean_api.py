from fastapi import APIRouter
from fastapi.responses import JSONResponse
from bs4 import BeautifulSoup
from selenium_helper import fetch_page_html

router = APIRouter()


def buscar_produto_magalu(ean: str):
    url = f"https://www.magazineluiza.com.br/busca/{ean}"
    try:
        # Magalu is heavy SPA, needs more time to load
        html = fetch_page_html(url, wait_selector='img[alt]', wait_timeout=15)
        if not html:
            return None

        soup = BeautifulSoup(html, 'html.parser')

        # Strategy 1: product cards with /p/ links
        for a_tag in soup.find_all('a', href=True):
            if '/p/' not in a_tag['href']:
                continue
            img = a_tag.find('img', alt=True)
            if img:
                src = img.get('src', '') or img.get('data-src', '')
                alt = img.get('alt', '').strip()
                if src and alt and '.svg' not in src and 'icon' not in src.lower() and len(alt) > 5:
                    return {
                        'ean': ean,
                        'nome': alt,
                        'imagem_url': src,
                        'source': 'magalu',
                    }

        # Strategy 2: any product image with mlcdn or magazineluiza domain
        for img in soup.find_all('img', alt=True):
            src = img.get('src', '') or img.get('data-src', '')
            alt = img.get('alt', '').strip()
            if not src or not alt or len(alt) < 10:
                continue
            if '.svg' in src or 'icon' in src.lower() or 'logo' in src.lower() or 'banner' in src.lower():
                continue
            if ('mlcdn' in src or 'magazineluiza' in src) and src.startswith('http'):
                return {
                    'ean': ean,
                    'nome': alt,
                    'imagem_url': src,
                    'source': 'magalu',
                }

        return None
    except Exception:
        return None


@router.get("/produto/{ean}")
async def buscar_produto(ean: str):
    resultado = buscar_produto_magalu(ean)
    if resultado:
        return {
            'EAN': ean,
            'Nome do Produto': resultado['nome'],
            'Link da Imagem': resultado['imagem_url'],
            'Fonte': 'Magazine Luiza',
        }
    else:
        return JSONResponse(status_code=404, content={"Erro": "Produto nao encontrado no Magazine Luiza"})
