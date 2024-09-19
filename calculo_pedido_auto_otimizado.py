from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict
import requests
from datetime import datetime, timedelta
import os
import logging
from dateutil import parser


router = APIRouter()

# Configurações da API do Supabase
API_URL_BASE = "https://asahknimbggpzpoebmej.supabase.co"
API_KEY = os.getenv("SUPABASE_API_KEY")  # Certifique-se de definir essa variável de ambiente

# Headers comuns para as requisições
HEADERS = {
    "apikey": API_KEY,
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Configurar o logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FornecedorID(BaseModel):
    fornecedor_id: int

@router.post("")
async def calcular_pedido(fornecedor: FornecedorID):
    try:
        fornecedor_id = fornecedor.fornecedor_id
        logger.info(f"Iniciando cálculo para fornecedor_id: {fornecedor_id}")

        # Passo 1: Buscar políticas e produtos
        politicas = fetch_policies(fornecedor_id)
        if not politicas:
            logger.warning("Nenhuma política de compra encontrada.")
            return {"message": "Nenhuma política de compra encontrada para o fornecedor"}

        produtos = fetch_products(fornecedor_id)
        if not produtos:
            logger.warning("Nenhum produto encontrado.")
            return {"message": "Nenhum produto encontrado para o fornecedor"}

        # Passo 2: Buscar dados de última venda e compra
        produto_ids = [p['produto_id'] for p in produtos]
        produtos_datas = fetch_produto_datas(produto_ids)

        # Passo 3: Processar o cálculo
        resultado = process_calculation(politicas, produtos, produtos_datas)

        logger.info("Cálculo concluído com sucesso.")
        return resultado

    except HTTPException as e:
        logger.error(f"HTTPException: {e.detail}")
        raise e
    except Exception as e:
        logger.exception("Erro desconhecido.")
        raise HTTPException(status_code=500, detail=str(e))

def fetch_policies(fornecedor_id: int) -> Dict:
    url = f"{API_URL_BASE}/rest/v1/rpc/flowb2b_fetch_politica_compra"
    payload = {"f_id": fornecedor_id}
    response = requests.post(url, headers=HEADERS, json=payload)
    
    if response.status_code != 200:
        logger.error(f"Erro ao buscar políticas: {response.text}")
        raise HTTPException(status_code=response.status_code, detail="Erro ao buscar políticas")

    return response.json()

def fetch_products(fornecedor_id: int) -> Dict:
    url = f"{API_URL_BASE}/rest/v1/rpc/flowb2b_get_produtos_detalhados"
    payload = {"f_id": fornecedor_id}
    response = requests.post(url, headers=HEADERS, json=payload)

    if response.status_code != 200:
        logger.error(f"Erro ao buscar produtos: {response.text}")
        raise HTTPException(status_code=response.status_code, detail="Erro ao buscar produtos")

    return response.json()

def fetch_produto_datas(produto_ids: list) -> Dict:
    try:
        # Fetch last sales dates
        vendas_data = fetch_max_data_saida(produto_ids)
        # Fetch last purchase dates
        compras_data = fetch_max_data_compra(produto_ids)

        # Combine the fetched data
        produtos_datas = {
            produto_id: {
                "data_ultima_venda": vendas_data.get(produto_id),
                "data_ultima_compra": compras_data.get(produto_id)
            }
            for produto_id in produto_ids
        }
        return produtos_datas
    except Exception as e:
        logger.exception("Erro ao buscar datas dos produtos.")
        raise

def fetch_max_data_saida(produto_ids: list) -> Dict:
    url = f"{API_URL_BASE}/rest/v1/rpc/get_max_data_saida"
    payload = {"produto_ids": produto_ids}
    response = requests.post(url, headers=HEADERS, json=payload)

    if response.status_code != 200:
        logger.error(f"Erro ao buscar datas de última venda: {response.text}")
        raise HTTPException(status_code=response.status_code, detail="Erro ao buscar datas de última venda")

    vendas_data = response.json()
    return {item['produto_id']: item['max_data_saida'] for item in vendas_data}

def fetch_max_data_compra(produto_ids: list) -> Dict:
    url = f"{API_URL_BASE}/rest/v1/rpc/get_max_data_compra"
    payload = {"produto_ids": produto_ids}
    response = requests.post(url, headers=HEADERS, json=payload)

    if response.status_code != 200:
        logger.error(f"Erro ao buscar datas de última compra: {response.text}")
        raise HTTPException(status_code=response.status_code, detail="Erro ao buscar datas de última compra")

    compras_data = response.json()
    return {item['produto_id']: item['max_data_compra'] for item in compras_data}

def process_calculation(politicas: Dict, produtos: Dict, produtos_datas: Dict) -> list:
    resultado = []
    melhor_politica_id = find_best_policy(politicas)

    produtos_processados = set()

    for politica in politicas:
        produtos_array = []
        valor_total_pedido = 0
        valor_total_pedido_com_desconto = 0
        quantidade_produtos = 0

        for produto in produtos:
            produto_id = produto['produto_id']
            if produto_id in produtos_processados:
                continue

            produtos_processados.add(produto_id)
            data_info = produtos_datas.get(produto_id, {})
            data_ultima_venda_str = data_info.get('data_ultima_venda')
            data_ultima_compra_str = data_info.get('data_ultima_compra')

            if not data_ultima_venda_str:
                continue  # Ignorar produtos sem última venda

            # Calcular período de venda
            data_ultima_venda = ajustar_data_futura(parser.isoparse(data_ultima_venda_str).date())
            data_ultima_compra = ajustar_data_compra(data_ultima_compra_str, data_ultima_venda)
            periodo_venda = max((data_ultima_venda - data_ultima_compra).days, 1)

            # Buscar a quantidade vendida
            quantidade_vendida = fetch_quantidade_vendida(produto_id, data_ultima_compra.isoformat(), data_ultima_venda.isoformat())

            # Calcular média de vendas diárias
            media_venda_dia = quantidade_vendida / periodo_venda

            # Calcular sugestão de quantidade
            sugestao_quantidade, multiplicacao = calcular_sugestao(produto, politica, media_venda_dia, quantidade_vendida)

            # Se não houver quantidade sugerida, ignorar o produto
            if sugestao_quantidade <= 0:
                continue

            # Calcular valores
            valor_total_produto, valor_total_produto_com_desconto = calcular_valores(produto, politica, sugestao_quantidade)

            # Atualizar totais
            valor_total_pedido += valor_total_produto
            valor_total_pedido_com_desconto += valor_total_produto_com_desconto
            quantidade_produtos += 1

            # Adicionar produto ao array de resultado
            produtos_array.append(montar_detalhes_produto(produto, quantidade_vendida, periodo_venda, sugestao_quantidade, valor_total_produto, valor_total_produto_com_desconto, multiplicacao))

        # Verificar se o valor total atende ao mínimo da política
        if valor_total_pedido >= (politica.get('valor_minimo') or 0):
            politica_compra = montar_politica_compra(politica, valor_total_pedido, valor_total_pedido_com_desconto, quantidade_produtos, melhor_politica_id, produtos_array)
            resultado.append(politica_compra)

    return resultado

def ajustar_data_futura(data: datetime) -> datetime:
    return min(data, datetime.now().date())

def ajustar_data_compra(data_ultima_compra_str: str, data_ultima_venda: datetime) -> datetime:
    if not data_ultima_compra_str:
        return data_ultima_venda - timedelta(days=365)
    data_ultima_compra = parser.isoparse(data_ultima_compra_str).date()
    return min(data_ultima_compra, data_ultima_venda - timedelta(days=1))

def fetch_quantidade_vendida(produto_id: int, data_inicio: str, data_fim: str) -> float:
    url = f"{API_URL_BASE}/rest/v1/rpc/get_quantidade_vendida"
    payload = {
        "p_produto_id": produto_id,
        "data_inicio": data_inicio,
        "data_fim": data_fim
    }
    response = requests.post(url, headers=HEADERS, json=payload)
    
    if response.status_code != 200:
        logger.error(f"Erro ao buscar quantidade vendida: {response.text}")
        raise HTTPException(status_code=response.status_code, detail=f"Erro ao buscar quantidade vendida")

    result = response.json()
    return float(result[0]['quantidade_vendida']) if result else 0

def calcular_sugestao(produto: Dict, politica: Dict, media_venda_dia: float, quantidade_vendida: float) -> tuple:
    itens_por_caixa = produto.get('itens_por_caixa') or 1
    estoque_atual = produto.get('estoque_atual') or 0
    prazo_estoque = politica.get('prazo_estoque') or 0

    sugestao_quantidade = max(media_venda_dia * prazo_estoque - estoque_atual, 0)
    if estoque_atual == 0 and quantidade_vendida > 0:
        sugestao_quantidade = max(sugestao_quantidade, quantidade_vendida)

    sugestao_quantidade = -(-sugestao_quantidade // itens_por_caixa) * itens_por_caixa  # Arredondar para cima
    multiplicacao = False
    if estoque_atual < 2:
        sugestao_quantidade = -(-sugestao_quantidade * 1.2 // 1)
        multiplicacao = True

    return sugestao_quantidade, multiplicacao

def calcular_valores(produto: Dict, politica: Dict, sugestao_quantidade: float) -> tuple:
    valor_de_compra = produto.get('valor_de_compra') or 0
    valor_total_produto = sugestao_quantidade * valor_de_compra
    desconto = politica.get('desconto') or 0
    valor_total_produto_com_desconto = valor_total_produto * (1 - desconto)
    return valor_total_produto, valor_total_produto_com_desconto

def montar_detalhes_produto(produto: Dict, quantidade_vendida: float, periodo_venda: int, sugestao_quantidade: float, valor_total_produto: float, valor_total_produto_com_desconto: float, multiplicacao: bool) -> Dict:
    return {
        'produto_id': produto['produto_id'],
        'codigo_do_produto': produto.get('codigo_produto'),
        'quantidade_vendida': quantidade_vendida,
        'periodo_venda': periodo_venda,
        'sugestao_quantidade': sugestao_quantidade,
        'valor_total_produto': valor_total_produto,
        'valor_total_produto_com_desconto': valor_total_produto_com_desconto,
        'estoque_atual': produto.get('estoque_atual') or 0,
        'data_ultima_venda': produto.get('data_ultima_venda'),
        'data_ultima_compra': produto.get('data_ultima_compra'),
        'itens_por_caixa': produto.get('itens_por_caixa') or 1,
        'multiplicacao_aplicada': multiplicacao
    }

def montar_politica_compra(politica: Dict, valor_total_pedido: float, valor_total_pedido_com_desconto: float, quantidade_produtos: int, melhor_politica_id: int, produtos_array: list) -> Dict:
    return {
        'politica_id': politica.get('id'),
        'desconto': politica.get('desconto'),
        'bonificacao': politica.get('bonificacao'),
        'valor_minimo': politica.get('valor_minimo'),
        'prazo_estoque': politica.get('prazo_estoque'),
        'melhor_politica': politica.get('id') == melhor_politica_id,
        'quantidade_produtos': quantidade_produtos,
        'valor_total_pedido_sem_desconto': valor_total_pedido,
        'valor_total_pedido_com_desconto': valor_total_pedido_com_desconto,
        'produtos': produtos_array
    }

def find_best_policy(politicas: Dict) -> int:
    melhor_desconto = 0
    menor_prazo = float('inf')
    melhor_politica_id = None

    for politica in politicas:
        desconto = politica.get('desconto') or 0
        prazo_estoque = politica.get('prazo_estoque') or float('inf')

        if desconto > melhor_desconto or (desconto == melhor_desconto and prazo_estoque < menor_prazo):
            melhor_desconto = desconto
            menor_prazo = prazo_estoque
            melhor_politica_id = politica.get('id')

    return melhor_politica_id
