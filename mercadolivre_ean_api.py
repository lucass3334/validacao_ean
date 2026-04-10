from fastapi import APIRouter
from fastapi.responses import JSONResponse
import requests
from bs4 import BeautifulSoup

router = APIRouter()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'pt-BR,pt;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
}


def buscar_produto_mercadolivre(ean: str):
    url = f"https://lista.mercadolivre.com.br/{ean}"
    try:
        session = requests.Session()
        response = session.get(url, headers=HEADERS, timeout=15)
        session.close()

        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        # Strategy 1: Find product cards (poly-card or ui-search-layout__item)
        # and extract the first product image + title from within
        cards = soup.select('.ui-search-layout__item, .poly-card, [class*="ui-search-result"]')
        for card in cards:
            # Get title from h2/h3 inside the card
            title_el = card.select_one('h2, h3, [class*="title"]')
            title = title_el.get_text(strip=True) if title_el else None

            # Get product image (D_NQ_NP = product, not D_NQ_8 = banner)
            img = None
            for img_tag in card.find_all('img'):
                src = img_tag.get('src', '') or img_tag.get('data-src', '')
                if 'mlstatic.com/D_' in src and '.svg' not in src:
                    img = src
                    if not title:
                        title = img_tag.get('alt', '').strip()
                    break

            if img and title:
                # Clean "Imagen - 1/2" suffix from alt text
                if 'Imagen' in title:
                    title = title.split('Imagen')[0].strip()
                return {
                    'ean': ean,
                    'nome': title,
                    'imagem_url': img,
                    'source': 'mercadolivre',
                }

        # Strategy 2: fallback - find first img with D_NQ_NP pattern AND a nearby h2
        for img_tag in soup.find_all('img'):
            src = img_tag.get('src', '') or img_tag.get('data-src', '')
            if 'mlstatic.com/D_NQ_NP' in src and '.svg' not in src:
                alt = img_tag.get('alt', '').strip()
                if alt and 'Imagen' not in alt and len(alt) > 10:
                    return {
                        'ean': ean,
                        'nome': alt,
                        'imagem_url': src,
                        'source': 'mercadolivre',
                    }

        return None
    except Exception:
        return None


@router.get("/produto/{ean}")
async def buscar_produto(ean: str):
    resultado = buscar_produto_mercadolivre(ean)
    if resultado:
        return {
            'EAN': ean,
            'Nome do Produto': resultado['nome'],
            'Link da Imagem': resultado['imagem_url'],
            'Fonte': 'Mercado Livre',
        }
    else:
        return JSONResponse(status_code=404, content={"Erro": "Produto nao encontrado no Mercado Livre"})
