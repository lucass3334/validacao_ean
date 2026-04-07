from fastapi import APIRouter
from fastapi.responses import JSONResponse
import requests
from bs4 import BeautifulSoup

router = APIRouter()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
}


def buscar_produto_amazon(ean: str):
    url = f"https://www.amazon.com.br/s?k={ean}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        # Amazon uses .s-image class for product images in search results
        img = soup.select_one('.s-result-item img.s-image')
        if not img:
            return None

        imagem_url = img.get('src', '')
        if not imagem_url:
            return None

        # Get product name from h2 in the same result item
        result_item = img.find_parent(attrs={'data-component-type': 's-search-result'})
        nome = None
        if result_item:
            h2 = result_item.find('h2')
            if h2:
                nome = h2.get_text(strip=True)

        if not nome:
            nome = img.get('alt', '').strip()

        return {
            'ean': ean,
            'nome': nome,
            'imagem_url': imagem_url,
            'source': 'amazon',
        }
    except Exception:
        return None


@router.get("/produto/{ean}")
async def buscar_produto(ean: str):
    resultado = buscar_produto_amazon(ean)
    if resultado:
        return {
            'EAN': ean,
            'Nome do Produto': resultado['nome'],
            'Link da Imagem': resultado['imagem_url'],
            'Fonte': 'Amazon',
        }
    else:
        return JSONResponse(status_code=404, content={"Erro": "Produto nao encontrado na Amazon"})
