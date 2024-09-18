from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import requests
from datetime import datetime, timedelta
import os
import logging
from dateutil import parser


router = APIRouter()

class FornecedorID(BaseModel):
    fornecedor_id: int

# Configurações da API do Supabase
API_URL_BASE = "https://asahknimbggpzpoebmej.supabase.co"
API_KEY = os.getenv("SUPABASE_API_KEY")  # Certifique-se de definir essa variável de ambiente

# Headers comuns para as requisições
HEADERS = {
    "apikey": API_KEY,
    "Authorization": f"Bearer {API_KEY}",  # Adicionar o cabeçalho Authorization
    "Content-Type": "application/json"
}

# Configurar o logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@router.post("")
async def calcular_pedido(fornecedor: FornecedorID):
    try:
        fornecedor_id = fornecedor.fornecedor_id
        logger.info(f"Iniciando cálculo para fornecedor_id: {fornecedor_id}")

        # Buscar políticas de compra
        politicas = fetch_policies(fornecedor_id)
        if not politicas:
            logger.info("Nenhuma política de compra encontrada para o fornecedor")
            return {"message": "Nenhuma política de compra encontrada para o fornecedor"}

        # Buscar produtos detalhados
        produtos = fetch_products(fornecedor_id)
        if not produtos:
            logger.info("Nenhum produto encontrado para o fornecedor")
            return {"message": "Nenhum produto encontrado para o fornecedor"}

        # Buscar datas de última venda e última compra para os produtos
        produtos_datas = fetch_produto_datas([p['produto_id'] for p in produtos])

        # Processar cálculos
        resultado = process_calculation(fornecedor_id, politicas, produtos, produtos_datas)

        logger.info("Cálculo concluído com sucesso")
        return resultado

    except HTTPException as e:
        logger.error(f"HTTPException: {e.detail}")
        raise e
    except Exception as e:
        logger.exception("Ocorreu uma exceção não tratada")
        raise HTTPException(status_code=500, detail=str(e))

def fetch_policies(fornecedor_id):
    url = f"{API_URL_BASE}/rest/v1/rpc/flowb2b_fetch_politica_compra"
    payload = {"f_id": fornecedor_id}
    response = requests.post(url, headers=HEADERS, json=payload)

    if response.status_code != 200:
        logger.error(f"Erro ao buscar políticas: {response.text}")
        raise HTTPException(status_code=response.status_code, detail=f"Erro ao buscar políticas: {response.text}")
    return response.json()

def fetch_products(fornecedor_id):
    url = f"{API_URL_BASE}/rest/v1/rpc/flowb2b_get_produtos_detalhados"
    payload = {"f_id": fornecedor_id}
    response = requests.post(url, headers=HEADERS, json=payload)

    if response.status_code != 200:
        logger.error(f"Erro ao buscar produtos: {response.text}")
        raise HTTPException(status_code=response.status_code, detail=f"Erro ao buscar produtos: {response.text}")
    return response.json()

def fetch_produto_datas(produto_ids):
    try:
        # Buscar datas de última venda
        url_vendas = f"{API_URL_BASE}/rest/v1/rpc/get_max_data_saida"
        payload_vendas = {"produto_ids": produto_ids}
        response_vendas = requests.post(url_vendas, headers=HEADERS, json=payload_vendas)
        if response_vendas.status_code != 200:
            logger.error(f"Erro ao buscar datas de última venda: {response_vendas.text}")
            raise HTTPException(status_code=response_vendas.status_code, detail=f"Erro ao buscar datas de última venda: {response_vendas.text}")
        vendas_data = response_vendas.json()
        data_ultima_venda = {item['produto_id']: item['max_data_saida'] for item in vendas_data}

        # Buscar datas de última compra
        url_compras = f"{API_URL_BASE}/rest/v1/rpc/get_max_data_compra"
        payload_compras = {"produto_ids": produto_ids}
        response_compras = requests.post(url_compras, headers=HEADERS, json=payload_compras)
        if response_compras.status_code != 200:
            logger.error(f"Erro ao buscar datas de última compra: {response_compras.text}")
            raise HTTPException(status_code=response_compras.status_code, detail=f"Erro ao buscar datas de última compra: {response_compras.text}")
        compras_data = response_compras.json()
        data_ultima_compra = {item['produto_id']: item['max_data_compra'] for item in compras_data}

        # Combinar dados
        produtos_datas = {}
        for produto_id in produto_ids:
            produtos_datas[produto_id] = {
                "data_ultima_venda": data_ultima_venda.get(produto_id),
                "data_ultima_compra": data_ultima_compra.get(produto_id)
            }

        return produtos_datas
    except Exception as e:
        logger.exception("Erro ao buscar datas dos produtos")
        raise

def process_calculation(fornecedor_id, politicas, produtos, produtos_datas):
    # Encontrar a melhor política
    melhor_politica_id = find_best_policy(politicas)

    resultado = []
    for politica in politicas:
        produtos_array = []
        valor_total_pedido = 0
        valor_total_pedido_com_desconto = 0
        quantidade_produtos = 0

        for produto in produtos:
            try:
                produto_id = produto['produto_id']
                data_info = produtos_datas.get(produto_id, {})
                data_ultima_venda = data_info.get('data_ultima_venda')
                data_ultima_compra = data_info.get('data_ultima_compra')

                # Lógica de cálculo conforme a função original
                # Ignorar produtos sem data de última venda
                if data_ultima_venda is None:
                    continue  # Produto sem giro ignorado

                # Se data_ultima_compra for nula, definir como data_ultima_venda - 365 dias
                if data_ultima_compra is None:
                    data_ultima_compra_dt = parser.isoparse(data_ultima_venda) - timedelta(days=365)
                    data_ultima_compra = data_ultima_compra_dt.isoformat()
                else:
                    data_ultima_compra_dt = parser.isoparse(data_ultima_compra)

                data_venda_dt = parser.isoparse(data_ultima_venda)

                # Calcular periodo_venda
                periodo_venda = (data_venda_dt - data_ultima_compra_dt).days

                if periodo_venda <= 0:
                    periodo_venda = 1  # Evitar divisão por zero

                # Calcular quantidade_vendida no período
                quantidade_vendida = fetch_quantidade_vendida(produto_id, data_ultima_compra_dt.isoformat(), data_venda_dt.isoformat())

                # Calcular média de vendas diárias
                media_venda_dia = quantidade_vendida / periodo_venda

                # Itens por caixa
                itens_por_caixa = produto.get('itens_por_caixa') or 1

                # Calcular sugestão de quantidade
                estoque_atual = produto.get('estoque_atual') or 0
                prazo_estoque = politica.get('prazo_estoque') or 0
                sugestao_quantidade = max((media_venda_dia * prazo_estoque - estoque_atual), 0)

    
