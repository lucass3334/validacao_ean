from fastapi import APIRouter
from fastapi.responses import JSONResponse
import re
import requests
from bs4 import BeautifulSoup

router = APIRouter()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'pt-BR,pt;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
}


def _limpar_titulo_ml(titulo: str) -> str:
    """Remove sufixos como ' - R$ 54,09' ou ' | Frete gratis' do titulo do ML."""
    t = re.sub(r'\s*-\s*R\$\s*[\d.,]+\s*$', '', titulo)
    t = re.sub(r'\s*\|\s*Frete gr.tis\s*$', '', t, flags=re.IGNORECASE)
    return t.strip()


def buscar_produto_mercadolivre(ean: str):
    """
    Busca produto no Mercado Livre.
    Para EANs validos, ML costuma redirecionar direto para a pagina do produto.
    Nesse caso, usa Open Graph (og:image, og:title) que e estavel.
    Se cair numa pagina de busca, procura primeiro card de produto.
    """
    url = f"https://lista.mercadolivre.com.br/{ean}"
    try:
        session = requests.Session()
        response = session.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        session.close()

        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        # Strategy 1: Open Graph (caso ML redirecionou pra pagina de produto)
        og_image = soup.find('meta', property='og:image')
        og_title = soup.find('meta', property='og:title')

        if og_image and og_title:
            img_url = og_image.get('content', '')
            title = og_title.get('content', '')

            # Verifica se e imagem de produto (nao imagem generica do ML)
            if 'mlstatic.com' in img_url and ('D_NQ_NP' in img_url or 'D_Q_NP' in img_url):
                return {
                    'ean': ean,
                    'nome': _limpar_titulo_ml(title),
                    'imagem_url': img_url,
                    'source': 'mercadolivre',
                }

        # Strategy 2: pagina de busca — pegar o primeiro card de produto
        # Cada card tem uma imagem com pattern mlstatic.com/D_NQ_NP_
        cards = soup.select('li.ui-search-layout__item, .ui-search-result, [class*="poly-card"]')
        for card in cards:
            title_el = card.select_one('h2, h3, [class*="title"], a[title]')
            title = None
            if title_el:
                title = title_el.get('title') or title_el.get_text(strip=True)

            for img_tag in card.find_all('img'):
                src = img_tag.get('src', '') or img_tag.get('data-src', '')
                if 'mlstatic.com/D_' in src and '.svg' not in src:
                    alt = img_tag.get('alt', '').strip()
                    if not title and alt and 'Imagen' not in alt:
                        title = alt
                    if title and 'Imagen' not in title and len(title) > 5:
                        return {
                            'ean': ean,
                            'nome': _limpar_titulo_ml(title),
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
    return JSONResponse(status_code=404, content={"Erro": "Produto nao encontrado no Mercado Livre"})
