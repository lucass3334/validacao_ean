from fastapi import APIRouter
from fastapi.responses import JSONResponse
from bs4 import BeautifulSoup
from selenium_helper import fetch_page_html

router = APIRouter()


def buscar_produto_petlove(ean: str):
    url = f"https://www.petlove.com.br/busca?q={ean}"
    try:
        html = fetch_page_html(url, wait_selector='img[alt]', wait_timeout=8)
        if not html:
            return None

        soup = BeautifulSoup(html, 'html.parser')

        # Petlove product images are in cards with src containing petlove.com.br/images/products
        for img in soup.find_all('img', alt=True):
            src = img.get('src', '') or img.get('data-src', '')
            alt = img.get('alt', '')
            if not src or not alt:
                continue
            if 'petlove.com.br/images/products' in src or 'petlove.com.br/images' in src:
                if '.svg' not in src and 'icon' not in src.lower() and 'logo' not in src.lower():
                    return {
                        'ean': ean,
                        'nome': alt.strip(),
                        'imagem_url': src,
                        'source': 'petlove',
                    }

        # Fallback: any product-like image with meaningful alt text
        for img in soup.find_all('img', alt=True):
            src = img.get('src', '') or img.get('data-src', '')
            alt = img.get('alt', '')
            if not src or not alt or len(alt) < 10:
                continue
            if '.svg' in src or 'icon' in src.lower() or 'logo' in src.lower() or 'banner' in src.lower():
                continue
            if src.startswith('http') and ('jpg' in src or 'jpeg' in src or 'png' in src or 'webp' in src):
                return {
                    'ean': ean,
                    'nome': alt.strip(),
                    'imagem_url': src,
                    'source': 'petlove',
                }

        return None
    except Exception:
        return None


@router.get("/produto/{ean}")
async def buscar_produto(ean: str):
    resultado = buscar_produto_petlove(ean)
    if resultado:
        return {
            'EAN': ean,
            'Nome do Produto': resultado['nome'],
            'Link da Imagem': resultado['imagem_url'],
            'Fonte': 'Petlove',
        }
    else:
        return JSONResponse(status_code=404, content={"Erro": "Produto nao encontrado na Petlove"})
