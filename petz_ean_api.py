from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import requests
from bs4 import BeautifulSoup

router = APIRouter()

def buscar_produto_por_nome(nome):
    url = f"https://www.petz.com.br/busca?q={nome}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.text
    else:
        return None

def extrair_informacoes_produto(html):
    soup = BeautifulSoup(html, 'html.parser')
    produto = soup.find('li', class_='card-product')
    if produto:
        link_produto = produto.find('a', class_='card-link-product')['href']
        nome_produto = produto.find('p', class_='ptz-card-label-left').text.strip()
        url_completo = f"https://www.petz.com.br{link_produto}"
        
        preco_original = produto.find('span', class_='ptz-card-price-showcase-older')
        preco_original = preco_original.text.strip() if preco_original else None

        preco_desconto = produto.find('p', class_='ptz-card-price-showcase')
        preco_desconto = preco_desconto.text.strip() if preco_desconto else None

        return nome_produto, url_completo, preco_original, preco_desconto
    else:
        return None, None, None, None

def obter_detalhes_do_produto(url):
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Captura a imagem do produto
        imagem = soup.find('img', class_='image-swiper')['src'] if soup.find('img', class_='image-swiper') else None
        
        # Captura a ficha técnica
        ficha_tecnica = {}
        especificacoes = soup.find_all('li', class_='specifications')
        for especificacao in especificacoes:
            chave = especificacao.find('span', class_='spec-key').text.strip()
            valor = especificacao.find('span', class_='spec-value').text.strip()
            ficha_tecnica[chave] = valor
        
        # Captura a descrição detalhada do produto
        descricao_detalhada = ""
        descricao_div = soup.find('section', id='description')
        if descricao_div:
            descricao_detalhada = descricao_div.get_text(separator="\n", strip=True)

        # Captura o EAN
        ean = ficha_tecnica.get("Código de barras", None)
        
        return imagem, ficha_tecnica, descricao_detalhada, ean
    else:
        return None, None, None, None

@router.get("/produto/{nome}/{ean}")
async def buscar_produto(nome: str, ean: str = None):
    html_resultado = buscar_produto_por_nome(nome)
    if html_resultado:
        nome_produto, url_produto, preco_original, preco_desconto = extrair_informacoes_produto(html_resultado)
        if nome_produto and url_produto:
            imagem, ficha_tecnica, descricao_detalhada, ean_encontrado = obter_detalhes_do_produto(url_produto)
            ean_correto = ean == ean_encontrado
            if imagem and ficha_tecnica:
                return {
                    'EAN': ean,
                    'EAN_CORRETO': ean_correto,
                    'Nome do Produto': nome_produto,
                    'Preço': preco_original,
                    'Preço de Desconto': preco_desconto,
                    'Link da Imagem': imagem,
                    'Ficha Técnica': ficha_tecnica,
                    'Descrição Detalhada': descricao_detalhada,
                    'EAN Encontrado': ean_encontrado
                }
            else:
                return JSONResponse(status_code=404, content={"Erro": "Detalhes do produto não encontrados"})
        else:
            return JSONResponse(status_code=404, content={"Erro": "Produto não encontrado"})
    else:
        return JSONResponse(status_code=500, content={"Erro": "Falha ao acessar a página de resultados"})
