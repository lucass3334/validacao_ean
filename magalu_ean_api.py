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


def buscar_produto_magalu(ean: str):
    url = f"https://www.magazineluiza.com.br/busca/{ean}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        # Magalu product cards: img inside a[href*="/p/"]
        imagem_url = None
        nome = None

        for a_tag in soup.find_all('a', href=True):
            if '/p/' not in a_tag['href']:
                continue

            img = a_tag.find('img', alt=True)
            if img:
                src = img.get('src', '') or img.get('data-src', '')
                alt = img.get('alt', '').strip()
                if src and alt and 'svg' not in src:
                    imagem_url = src
                    nome = alt
                    break

        if not imagem_url:
            return None

        return {
            'ean': ean,
            'nome': nome,
            'imagem_url': imagem_url,
            'source': 'magalu',
        }
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
