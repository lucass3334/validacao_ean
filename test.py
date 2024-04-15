import requests
from bs4 import BeautifulSoup

# Define a URL específica para o produto que você deseja analisar
url = 'https://www.cobasi.com.br/pesquisa?terms=7897348202431'

# Faz a requisição HTTP GET para a URL
response = requests.get(url)

# Verifica se a requisição foi bem-sucedida
if response.status_code == 200:
    # Utiliza BeautifulSoup para analisar o HTML retornado
    soup = BeautifulSoup(response.content, 'html.parser')

    # Aqui, o HTML completo é convertido para uma string formatada de forma mais legível
    html_pretty = soup.prettify()

    # Aqui você pode decidir se deseja imprimir todo o HTML ou salvá-lo em um arquivo para análise
    # Por exemplo, vamos imprimir apenas os primeiros 2000 caracteres para visualização
    print(html_pretty[:200000])

else:
    print("Falha na requisição. Status code:", response.status_code)
