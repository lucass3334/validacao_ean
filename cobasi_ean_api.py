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
        preco = soup.find('span', class_='card-price').text.strip()
        imagem = soup.find('img', alt='Imagem do Produto')['src']
        return preco, imagem
    else:
        return None, None

@router.get("/produto/{ean}")
async def buscar_produto(ean: str):
    html_resultado = buscar_produto_por_ean(ean)
    if html_resultado:
        nome_produto, url_produto = extrair_informacoes_produto(html_resultado)
        if nome_produto and url_produto:
            preco, imagem = obter_detalhes_do_produto(url_produto)
            if preco and imagem:
                return {
                    'EAN': ean,
                    'Nome do Produto': nome_produto,
                    'Preço': preco,
                    'Link da Imagem': imagem
                }
            else:
                return JSONResponse(status_code=404, content={"Erro": "Detalhes do produto não encontrados"})
        else:
            return JSONResponse(status_code=404, content={"Erro": "Produto não encontrado"})
    else:
        return JSONResponse(status_code=500, content={"Erro": "Falha ao acessar a página de resultados"})
