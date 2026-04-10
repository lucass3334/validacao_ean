from fastapi import APIRouter
from fastapi.responses import JSONResponse
from bs4 import BeautifulSoup
from selenium_helper import fetch_page_html

router = APIRouter()


def buscar_produto_por_nome(nome):
    url = f"https://www.petz.com.br/busca?q={nome}"
    return fetch_page_html(url, wait_selector='li.card-product, img[alt]', wait_timeout=10)


def extrair_informacoes_produto(html):
    soup = BeautifulSoup(html, 'html.parser')
    produto = soup.find('li', class_='card-product')
    if produto:
        link_tag = produto.find('a', class_='card-link-product') or produto.find('a', href=True)
        if not link_tag:
            return None, None, None, None
        link_produto = link_tag.get('href', '')
        nome_tag = produto.find('p', class_='ptz-card-label-left') or produto.find('h2') or produto.find('h3')
        nome_produto = nome_tag.text.strip() if nome_tag else ''
        url_completo = f"https://www.petz.com.br{link_produto}" if not link_produto.startswith('http') else link_produto

        preco_original_tag = produto.find('p', class_='ptz-card-price ptz-card-price-showcase') or produto.find('span', class_='card-price')
        preco_original = None
        if preco_original_tag:
            preco_original = preco_original_tag.text.split()[-1].replace('R$', '').strip()

        preco_desconto_tag = produto.find('p', class_='ptz-card-subscription-price')
        preco_desconto = None
        if preco_desconto_tag:
            preco_desconto = preco_desconto_tag.text.strip().replace('R$', '').strip()

        return nome_produto, url_completo, preco_original, preco_desconto

    # Fallback: try any product-like link with image
    for a_tag in soup.find_all('a', href=True):
        href = a_tag.get('href', '')
        if '/p?' in href or '/p/' in href:
            img = a_tag.find('img', alt=True)
            if img:
                nome = img.get('alt', '').strip()
                url = f"https://www.petz.com.br{href}" if not href.startswith('http') else href
                return nome, url, None, None

    return None, None, None, None


def obter_detalhes_do_produto(url):
    html = fetch_page_html(url, wait_selector='img.image-swiper, img[alt]', wait_timeout=10)
    if not html:
        return None, None, None, None

    soup = BeautifulSoup(html, 'html.parser')

    # Image
    imagem = None
    img_tag = soup.find('img', class_='image-swiper')
    if img_tag:
        imagem = img_tag.get('src')
    else:
        for img in soup.find_all('img', alt=True):
            src = img.get('src', '')
            if 'petz.com.br' in src and '.svg' not in src and 'icon' not in src.lower():
                imagem = src
                break

    # Ficha tecnica
    ficha_tecnica = {}
    for li in soup.find_all('li', class_='specifications'):
        chave_el = li.find('span', class_='spec-key')
        valor_el = li.find('span', class_='spec-value')
        if chave_el and valor_el:
            ficha_tecnica[chave_el.text.strip()] = valor_el.text.strip()

    # Descricao
    descricao = ""
    desc_div = soup.find('section', id='description')
    if desc_div:
        descricao = desc_div.get_text(separator="\n", strip=True)

    # EAN
    ean = None
    for li in soup.find_all('li'):
        chave_el = li.find('span', class_='spec-key')
        valor_el = li.find('span', class_='spec-value')
        if chave_el and chave_el.text.strip() == "Código de barras":
            ean = valor_el.text.strip() if valor_el else None
            break

    return imagem, ficha_tecnica, descricao, ean


def converter_preco(preco_str):
    preco_str = preco_str.replace('R$', '').replace('.', '').replace(',', '.').replace('A partir de ', '').strip()
    try:
        return float(preco_str)
    except ValueError:
        return None


@router.get("/produto/{nome}")
async def buscar_produto(nome: str, ean: str = None):
    html_resultado = buscar_produto_por_nome(nome)
    if html_resultado:
        nome_produto, url_produto, preco_original, preco_desconto = extrair_informacoes_produto(html_resultado)
        if nome_produto and url_produto:
            imagem, ficha_tecnica, descricao_detalhada, ean_encontrado = obter_detalhes_do_produto(url_produto)

            ean_correto = ean == ean_encontrado if ean and ean_encontrado else None

            preco_original = converter_preco(preco_original) if preco_original else None
            preco_desconto = converter_preco(preco_desconto) if preco_desconto else None

            return {
                'EAN': ean if ean else ean_encontrado,
                'EAN_CORRETO': ean_correto,
                'Nome do Produto': nome_produto,
                'Preço': preco_original,
                'Preço de Desconto': preco_desconto,
                'Link da Imagem': imagem,
                'Ficha Técnica': ficha_tecnica,
                'Descrição Detalhada': descricao_detalhada,
                'EAN Encontrado': ean_encontrado,
            }
        else:
            return JSONResponse(status_code=404, content={"Erro": "Produto não encontrado"})
    else:
        return JSONResponse(status_code=500, content={"Erro": "Falha ao acessar a página de resultados"})
