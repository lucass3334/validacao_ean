from fastapi import APIRouter
from fastapi.responses import JSONResponse
from bs4 import BeautifulSoup
from selenium_helper import fetch_page_html

router = APIRouter()


def buscar_produto_petlove(ean: str):
    """
    Busca produto na Petlove. Requer Selenium (site tem anti-bot em requests diretos).
    Filtra apenas imagens em /images/products/ pra evitar pegar banners, logos, selos e payment methods.
    """
    url = f"https://www.petlove.com.br/busca?q={ean}"
    try:
        html = fetch_page_html(url, wait_selector='img[alt]', wait_timeout=8)
        if not html:
            return None

        soup = BeautifulSoup(html, 'html.parser')

        # Petlove: imagens de produto tem src no formato
        # https://www.petlove.com.br/images/products/{id}/{size}/{ean}.png
        # Filtro estrito pra /images/products/ (com barra) evita /static/uploads/images/payment/methods.png
        for img in soup.find_all('img', alt=True):
            src = img.get('src', '') or img.get('data-src', '')
            alt = img.get('alt', '').strip()
            if not src or not alt:
                continue
            if '/images/products/' not in src:
                continue
            # Whitelist: jpg/jpeg/png/webp apenas
            src_lower = src.lower().split('?')[0]
            if not any(src_lower.endswith(ext) for ext in ('.jpg', '.jpeg', '.png', '.webp')):
                continue
            # Exige alt significativo (nome de produto, nao label generica)
            if len(alt) < 15:
                continue
            return {
                'ean': ean,
                'nome': alt,
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
