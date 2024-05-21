from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

router = APIRouter()

def buscar_produto_por_nome(nome):
    url = f"https://www.petz.com.br/busca?q={nome}"
    
    options = Options()
    options.add_argument("--headless")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    driver.get(url)
    html = driver.page_source
    driver.quit()
    return html

def extrair_informacoes_produto(html):
    soup = BeautifulSoup(html, 'html.parser')
    produto = soup.find('li', class_='card-product')
    if produto:
        link_produto = produto.find('a', class_='card-link-product')['href']
        nome_produto = produto.find('p', class_='ptz-card-label-left').text.strip()
        url_completo = f"https://www.petz.com.br{link_produto}"
        
        # Capturando preço cheio
        preco_original_tag = produto.find('p', class_='ptz-card-price ptz-card-price-showcase')
        preco_original = None
        if preco_original_tag:
            preco_original = preco_original_tag.text.split()[-1].replace('R$', '').strip()

        # Capturando preço com desconto
        preco_desconto_tag = produto.find('p', class_='ptz-card-subscription-price')
        preco_desconto = None
        if preco_desconto_tag:
            preco_desconto = preco_desconto_tag.text.strip().replace('R$', '').strip()

        return nome_produto, url_completo, preco_original, preco_desconto
    else:
        return None, None, None, None

def obter_detalhes_do_produto(url):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(url)
    
    html = driver.page_source
    driver.quit()
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Captura a imagem do produto
    imagem = soup.find('img', class_='image-swiper')['src'] if soup.find('img', class_='image-swiper') else None
    
    # Captura a ficha técnica
    ficha_tecnica = {}
    especificacoes = soup.find_all('li', class_='specifications')
    for especificacao in especificacoes:
        chave_element = especificacao.find('span', class_='spec-key')
        valor_element = especificacao.find('span', class_='spec-value')
        if chave_element and valor_element:
            chave = chave_element.text.strip()
            valor = valor_element.text.strip()
            ficha_tecnica[chave] = valor
    
    # Captura a descrição detalhada do produto
    descricao_detalhada = ""
    descricao_div = soup.find('section', id='description')
    if descricao_div:
        descricao_detalhada = descricao_div.get_text(separator="\n", strip=True)

    # Captura o EAN (Código de barras)
    ean = None
    especificacoes = soup.find_all('li')
    for especificacao in especificacoes:
        chave_element = especificacao.find('span', class_='spec-key')
        valor_element = especificacao.find('span', class_='spec-value')
        if chave_element and chave_element.text.strip() == "Código de barras":
            ean = valor_element.text.strip()
            break
    
    return imagem, ficha_tecnica, descricao_detalhada, ean

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
            
            # Verificação do EAN, se fornecido
            ean_correto = ean == ean_encontrado if ean else None

            # Convertendo preços para valores numéricos
            preco_original = converter_preco(preco_original) if preco_original else None
            preco_desconto = converter_preco(preco_desconto) if preco_desconto else None

            response = {
                'EAN': ean if ean else ean_encontrado,
                'EAN_CORRETO': ean_correto,
                'Nome do Produto': nome_produto,
                'Preço': preco_original,
                'Preço de Desconto': preco_desconto,
                'Link da Imagem': imagem,
                'Ficha Técnica': ficha_tecnica,
                'Descrição Detalhada': descricao_detalhada,
                'EAN Encontrado': ean_encontrado
            }

            return response
        else:
            return JSONResponse(status_code=404, content={"Erro": "Produto não encontrado"})
    else:
        return JSONResponse(status_code=500, content={"Erro": "Falha ao acessar a página de resultados"})
