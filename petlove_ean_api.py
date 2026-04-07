from fastapi import APIRouter
from fastapi.responses import JSONResponse
import requests
from bs4 import BeautifulSoup

router = APIRouter()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'pt-BR,pt;q=0.9',
}


def buscar_produto_petlove(ean: str):
    url = f"https://www.petlove.com.br/busca?q={ean}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        # Petlove product cards contain img with alt text matching the product name
        imagem_url = None
        nome = None

        for img in soup.find_all('img', alt=True):
            src = img.get('src', '') or img.get('data-src', '')
            alt = img.get('alt', '')
            if src and 'petlove.com.br/images/products' in src and alt:
                imagem_url = src
                nome = alt.strip()
                break

        if not imagem_url:
            return None

        return {
            'ean': ean,
            'nome': nome,
            'imagem_url': imagem_url,
            'source': 'petlove',
        }
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
