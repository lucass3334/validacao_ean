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

        # ML product images use D_NQ_NP pattern (not banners which use D_NQ_8)
        imagem_url = None
        nome = None

        for img in soup.find_all('img'):
            src = img.get('src', '') or img.get('data-src', '')
            if 'mlstatic.com/D_NQ_NP' in src or 'mlstatic.com/D_Q_NP' in src:
                imagem_url = src
                nome = img.get('alt', '').strip()
                if nome and 'Imagen' not in nome:
                    break
                # Clean alt text that contains " Imagen - 1/2" suffix
                if nome:
                    nome = nome.split(' Imagen')[0].strip()
                break

        if not imagem_url:
            return None

        return {
            'ean': ean,
            'nome': nome,
            'imagem_url': imagem_url,
            'source': 'mercadolivre',
        }
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
