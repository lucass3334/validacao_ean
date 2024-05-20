from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import requests
import pandas as pd
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
        preco_desconto = soup.find('span', class_='promo-price').text.strip() if soup.find('span', class_='promo-price') else None
        imagem = soup.find('img', alt='Imagem do Produto')['src']
        ficha_tecnica = obter_ficha_tecnica(soup)
        return preco, preco_desconto, imagem, ficha_tecnica
    else:
        return None, None, None, None

def obter_ficha_tecnica(soup):
    ficha_tecnica = {}
    ficha_section = soup.find('div', {'aria-labelledby': 'panel1d-header'})
    if ficha_section:
        lines = ficha_section.find_all('div', class_='styles__Line-sc-1ye2cc0-1')
        for line in lines:
            name = line.find('div', class_='styles__Name-sc-1ye2cc0-2').text.strip()
            value = line.find('div', class_='styles__Values-sc-1ye2cc0-3').text.strip()
            ficha_tecnica[name] = value
    return ficha_tecnica

@router.post("/uploadfile/")
async def create_upload_file(webhook_url: str, file: UploadFile = File(...)):
    df = pd.read_excel(file.file)
    if 'EAN' not in df.columns:
        raise HTTPException(status_code=400, detail="Excel file must have an 'EAN' column")
    
    results = []
    for ean in df['EAN']:
        html_resultado = buscar_produto_por_ean(ean)
        if html_resultado:
            nome_produto, url_produto = extrair_informacoes_produto(html_resultado)
            if nome_produto and url_produto:
                preco, preco_desconto, imagem, ficha_tecnica = obter_detalhes_do_produto(url_produto)
                if preco and imagem:
                    results.append({
                        'EAN': ean,
                        'Nome do Produto': nome_produto,
                        'Preço': preco,
                        'Preço de Desconto': preco_desconto,
                        'Link da Imagem': imagem,
                        'Ficha Técnica': ficha_tecnica
                    })
                else:
                    results.append({
                        'EAN': ean,
                        'Erro': 'Detalhes do produto não encontrados'
                    })
            else:
                results.append({
                    'EAN': ean,
                    'Erro': 'Produto não encontrado'
                })
        else:
            results.append({
                'EAN': ean,
                'Erro': 'Falha ao acessar a página de resultados'
            })
    
    # Enviar os dados para o webhook como JSON
    response = requests.post(webhook_url, json=results)
    if response.status_code == 200:
        return {"message": "Data sent successfully"}
    else:
        return {
            "message": "Failed to send data",
            "status_code": response.status_code,
            "response_body": response.text
        }
