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
    "Content-Type": "application/json"
}

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

                # Se o estoque atual for zero e a quantidade vendida for maior que zero, sugerir a quantidade vendida no período
                if estoque_atual == 0 and quantidade_vendida > 0:
                    sugestao_quantidade = max(sugestao_quantidade, quantidade_vendida)

                # Ajustar a quantidade sugerida com base em itens por caixa
                sugestao_quantidade = -(-sugestao_quantidade // itens_por_caixa) * itens_por_caixa  # Ceiling division

                if sugestao_quantidade <= 0:
                    continue  # Ignorar produtos com sugestão zero ou negativa

                # Aplicar multiplicação se o estoque estiver baixo
                multiplicacao = False
                if estoque_atual < 2:
                    sugestao_quantidade = -(- (sugestao_quantidade * 1.2) // 1)  # Ceiling
                    multiplicacao = True

                # Calcular valores
                valor_de_compra = produto.get('valor_de_compra') or 0
                valor_total_produto = sugestao_quantidade * valor_de_compra
                desconto = politica.get('desconto') or 0
                valor_total_produto_com_desconto = valor_total_produto * (1 - desconto)

                # Atualizar totais
                valor_total_pedido += valor_total_produto
                valor_total_pedido_com_desconto += valor_total_produto_com_desconto
                quantidade_produtos += 1

                # Adicionar produto ao array
                produtos_array.append({
                    'produto_id': produto_id,
                    'codigo_do_produto': produto.get('codigo_produto'),
                    'quantidade_vendida': quantidade_vendida,
                    'periodo_venda': periodo_venda,
                    'sugestao_quantidade': sugestao_quantidade,
                    'valor_total_produto': valor_total_produto,
                    'valor_total_produto_com_desconto': valor_total_produto_com_desconto,
                    'estoque_atual': estoque_atual,
                    'data_ultima_venda': data_ultima_venda,
                    'data_ultima_compra': data_ultima_compra,
                    'itens_por_caixa': itens_por_caixa,
                    'multiplicacao_aplicada': multiplicacao
                })
            except Exception as e:
                logger.exception(f"Erro ao processar produto_id {produto_id}")
                continue

        # Verificar se o valor total atende ao mínimo da política
        if valor_total_pedido >= (politica.get('valor_minimo') or 0):
            politica_compra = {
                'politica_id': politica.get('id'),
                'desconto': desconto,
                'bonificacao': politica.get('bonificacao'),
                'valor_minimo': politica.get('valor_minimo'),
                'prazo_estoque': prazo_estoque,
                'melhor_politica': politica.get('id') == melhor_politica_id,
                'quantidade_produtos': quantidade_produtos,
                'valor_total_pedido_sem_desconto': valor_total_pedido,
                'valor_total_pedido_com_desconto': valor_total_pedido_com_desconto,
                'produtos': produtos_array
            }
            resultado.append({'politica_compra': politica_compra})

    return resultado

def find_best_policy(politicas):
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

def fetch_quantidade_vendida(produto_id, data_inicio, data_fim):
    try:
        url = f"{API_URL_BASE}/rest/v1/rpc/get_quantidade_vendida"
        payload = {
            "produto_id": produto_id,
            "data_inicio": data_inicio,
            "data_fim": data_fim
        }
        response = requests.post(url, headers=HEADERS, json=payload)
        if response.status_code != 200:
            logger.error(f"Erro ao buscar quantidade vendida para produto_id {produto_id}: {response.text}")
            return 0
        vendas = response.json()
        quantidade_vendida = vendas.get('quantidade_vendida', 0)
        return quantidade_vendida
    except Exception as e:
        logger.exception(f"Exceção ao buscar quantidade vendida para produto_id {produto_id}")
        return 0
