from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import requests
from bs4 import BeautifulSoup

router = APIRouter()

def buscar_produto_por_ean(ean):
    url = f"https://www.cobasi.com.br/pesquisa?terms={ean}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.text
    else:
        return None

def extrair_informacoes_produto(html):
    soup = BeautifulSoup(html, 'html.parser')
    produto = soup.find('div', class_='MuiGrid-root ProductListItem MuiGrid-item MuiGrid-grid-xs-12 MuiGrid-grid-md-4')
    if produto:
        link_produto = produto.find('a')['href']
        nome_produto = produto.find('h3').text
        url_completo = f"https://www.cobasi.com.br{link_produto}"
        return nome_produto, url_completo
    else:
        return None, None

def obter_detalhes_do_produto(url):
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Captura o preço original
        preco_original = soup.find('div', class_='styles__ListPrice-sc-1pw21hb-0')
        preco_original = preco_original.find('span').text.strip() if preco_original else None

        # Captura o preço de desconto, se disponível
        preco_desconto = soup.find('span', class_='card-price')
        preco_desconto = preco_desconto.text.strip() if preco_desconto else None
        
        # Captura a imagem do produto
        imagem = soup.find('img', alt='Imagem do Produto')['src'] if soup.find('img', alt='Imagem do Produto') else None
        
        # Captura a ficha técnica
        ficha_tecnica = {}
        ficha_tecnica_div = soup.find('div', class_='MuiCollapse-wrapperInner')
        if ficha_tecnica_div:
            linhas = ficha_tecnica_div.find_all('div', class_='styles__Line-sc-1ye2cc0-1')
            for linha in linhas:
                chave = linha.find('div', class_='styles__Name-sc-1ye2cc0-2').text
                valor = linha.find('div', class_='styles__Values-sc-1ye2cc0-3').text
                ficha_tecnica[chave] = valor
        
        # Captura a descrição detalhada do produto
        descricao_detalhada = ""
        descricao_div = soup.find('div', class_='styles__DetailsContainerAccordion-sc-1rue5eb-6')
        if descricao_div:
            descricao_detalhada = descricao_div.get_text(separator="\n", strip=True)

        return preco_original, preco_desconto, imagem, ficha_tecnica, descricao_detalhada
    else:
        return None, None, None, None, None

@router.get("/produto/{ean}")
async def buscar_produto(ean: str):
    html_resultado = buscar_produto_por_ean(ean)
    if html_resultado:
        nome_produto, url_produto = extrair_informacoes_produto(html_resultado)
        if nome_produto and url_produto:
            preco_original, preco_desconto, imagem, ficha_tecnica, descricao_detalhada = obter_detalhes_do_produto(url_produto)
            if preco_original and imagem and ficha_tecnica:
                return {
                    'EAN': ean,
                    'Nome do Produto': nome_produto,
                    'Preço': preco_original,
                    'Preço de Desconto': preco_desconto,
                    'Link da Imagem': imagem,
                    'Ficha Técnica': ficha_tecnica,
                    'Descrição Detalhada': descricao_detalhada
                }
            else:
                return JSONResponse(status_code=404, content={"Erro": "Detalhes do produto não encontrados"})
        else:
            return JSONResponse(status_code=404, content={"Erro": "Produto não encontrado"})
    else:
        return JSONResponse(status_code=500, content={"Erro": "Falha ao acessar a página de resultados"})
