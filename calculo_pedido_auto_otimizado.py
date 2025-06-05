from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import requests
from datetime import datetime, timedelta
import os
import logging
from dateutil import parser
import traceback

router = APIRouter()

# Configurações da API do Supabase
API_URL_BASE = "https://asahknimbggpzpoebmej.supabase.co"
API_KEY = os.getenv("SUPABASE_API_KEY")

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

class CalculationRules:
    """Classe para armazenar e documentar as regras aplicadas durante o cálculo"""
    
    def __init__(self):
        self.rules_applied = []
        self.warnings = []
        self.errors = []
    
    def add_rule(self, rule_type: str, description: str, produto_id: Optional[int] = None, data: Optional[Dict] = None):
        self.rules_applied.append({
            "tipo": rule_type,
            "descricao": description,
            "produto_id": produto_id,
            "dados": data,
            "timestamp": datetime.now().isoformat()
        })
    
    def add_warning(self, warning: str, produto_id: Optional[int] = None):
        self.warnings.append({
            "aviso": warning,
            "produto_id": produto_id,
            "timestamp": datetime.now().isoformat()
        })
    
    def add_error(self, error: str, produto_id: Optional[int] = None):
        self.errors.append({
            "erro": error,
            "produto_id": produto_id,
            "timestamp": datetime.now().isoformat()
        })

@router.post("/calcular")
async def calcular_pedido(fornecedor: FornecedorID):
    """Endpoint original mantido para compatibilidade"""
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

@router.get("/monitoramento/{fornecedor_id}")
async def monitoramento_calculo(fornecedor_id: int):
    """
    Endpoint de monitoramento completo que mostra:
    - Todas as informações coletadas
    - Regras aplicadas durante o cálculo
    - Warnings e erros
    - Resultado final detalhado
    """
    calculation_rules = CalculationRules()
    
    try:
        calculation_rules.add_rule("INICIO", f"Iniciando monitoramento para fornecedor_id: {fornecedor_id}")
        
        # === COLETA DE DADOS BASE ===
        logger.info(f"[MONITORAMENTO] Iniciando para fornecedor_id: {fornecedor_id}")
        
        # 1. Buscar políticas
        calculation_rules.add_rule("FETCH_POLICIES", "Buscando políticas de compra")
        politicas = fetch_policies_with_monitoring(fornecedor_id, calculation_rules)
        
        if not politicas:
            calculation_rules.add_error("Nenhuma política de compra encontrada")
            return build_monitoring_response(calculation_rules, None, None, None, None)
        
        # 2. Buscar produtos
        calculation_rules.add_rule("FETCH_PRODUCTS", "Buscando produtos do fornecedor")
        produtos = fetch_products_with_monitoring(fornecedor_id, calculation_rules)
        
        if not produtos:
            calculation_rules.add_error("Nenhum produto encontrado")
            return build_monitoring_response(calculation_rules, politicas, None, None, None)
        
        # 3. Buscar histórico de vendas/compras
        produto_ids = [p['produto_id'] for p in produtos]
        calculation_rules.add_rule("FETCH_HISTORY", f"Buscando histórico para {len(produto_ids)} produtos")
        produtos_datas = fetch_produto_datas_with_monitoring(produto_ids, calculation_rules)
        
        # === PROCESSAMENTO DETALHADO ===
        calculation_rules.add_rule("START_PROCESSING", "Iniciando processamento detalhado")
        resultado_detalhado = process_calculation_with_monitoring(
            politicas, produtos, produtos_datas, calculation_rules
        )
        
        calculation_rules.add_rule("FINISH", "Cálculo concluído com sucesso")
        
        return build_monitoring_response(
            calculation_rules, 
            politicas, 
            produtos, 
            produtos_datas, 
            resultado_detalhado
        )
        
    except Exception as e:
        calculation_rules.add_error(f"Erro crítico: {str(e)}")
        logger.exception("Erro no monitoramento")
        return build_monitoring_response(calculation_rules, None, None, None, None)

def build_monitoring_response(rules: CalculationRules, politicas, produtos, produtos_datas, resultado):
    """Constrói a resposta completa do monitoramento"""
    return {
        "timestamp": datetime.now().isoformat(),
        "resumo": {
            "total_regras_aplicadas": len(rules.rules_applied),
            "total_warnings": len(rules.warnings),
            "total_errors": len(rules.errors),
            "total_politicas": len(politicas) if politicas else 0,
            "total_produtos": len(produtos) if produtos else 0,
            "sucesso": len(rules.errors) == 0
        },
        "dados_coletados": {
            "politicas": politicas,
            "produtos": produtos,
            "historico_produtos": produtos_datas
        },
        "regras_aplicadas": rules.rules_applied,
        "warnings": rules.warnings,
        "errors": rules.errors,
        "resultado_final": resultado
    }

def fetch_policies_with_monitoring(fornecedor_id: int, rules: CalculationRules) -> List[Dict]:
    try:
        url = f"{API_URL_BASE}/rest/v1/rpc/flowb2b_fetch_politica_compra"
        payload = {"f_id": fornecedor_id}
        response = requests.post(url, headers=HEADERS, json=payload)

        if response.status_code != 200:
            error_msg = f"Erro ao buscar políticas: {response.text}"
            rules.add_error(error_msg)
            raise HTTPException(status_code=response.status_code, detail="Erro ao buscar políticas")

        politicas = response.json()
        rules.add_rule("POLICIES_FOUND", f"Encontradas {len(politicas)} políticas", data={"count": len(politicas)})
        
        for politica in politicas:
            rules.add_rule("POLICY_DETAIL", "Política encontrada", data={
                "id": politica.get('id'),
                "desconto": politica.get('desconto'),
                "valor_minimo": politica.get('valor_minimo'),
                "prazo_estoque": politica.get('prazo_estoque')
            })
        
        return politicas
    except Exception as e:
        rules.add_error(f"Exceção ao buscar políticas: {str(e)}")
        raise

def fetch_products_with_monitoring(fornecedor_id: int, rules: CalculationRules) -> List[Dict]:
    try:
        url = f"{API_URL_BASE}/rest/v1/rpc/flowb2b_get_produtos_detalhados"
        payload = {"f_id": fornecedor_id}
        response = requests.post(url, headers=HEADERS, json=payload)

        if response.status_code != 200:
            error_msg = f"Erro ao buscar produtos: {response.text}"
            rules.add_error(error_msg)
            raise HTTPException(status_code=response.status_code, detail="Erro ao buscar produtos")

        produtos = response.json()
        rules.add_rule("PRODUCTS_FOUND", f"Encontrados {len(produtos)} produtos", data={"count": len(produtos)})
        
        for produto in produtos:
            produto_id = produto.get('produto_id')
            rules.add_rule("PRODUCT_DETAIL", "Produto encontrado", produto_id=produto_id, data={
                "codigo_produto": produto.get('codigo_produto'),
                "estoque_atual": produto.get('estoque_atual'),
                "valor_de_compra": produto.get('valor_de_compra'),
                "itens_por_caixa": produto.get('itens_por_caixa')
            })
        
        return produtos
    except Exception as e:
        rules.add_error(f"Exceção ao buscar produtos: {str(e)}")
        raise

def fetch_produto_datas_with_monitoring(produto_ids: list, rules: CalculationRules) -> Dict:
    try:
        rules.add_rule("FETCH_SALES_HISTORY", "Buscando histórico de vendas")
        vendas_data = fetch_max_data_saida_with_monitoring(produto_ids, rules)
        
        rules.add_rule("FETCH_PURCHASE_HISTORY", "Buscando histórico de compras")
        compras_data = fetch_max_data_compra_with_monitoring(produto_ids, rules)

        produtos_datas = {}
        for produto_id in produto_ids:
            data_venda = vendas_data.get(produto_id)
            data_compra = compras_data.get(produto_id)
            
            produtos_datas[produto_id] = {
                "data_ultima_venda": data_venda,
                "data_ultima_compra": data_compra
            }
            
            # Log das datas encontradas
            rules.add_rule("PRODUCT_DATES", "Datas coletadas", produto_id=produto_id, data={
                "data_ultima_venda": data_venda,
                "data_ultima_compra": data_compra
            })
        
        return produtos_datas
    except Exception as e:
        rules.add_error(f"Erro ao buscar datas dos produtos: {str(e)}")
        raise

def fetch_max_data_saida_with_monitoring(produto_ids: list, rules: CalculationRules) -> Dict:
    try:
        url = f"{API_URL_BASE}/rest/v1/rpc/get_max_data_saida"
        payload = {"produto_ids": produto_ids}
        response = requests.post(url, headers=HEADERS, json=payload)

        if response.status_code != 200:
            error_msg = f"Erro ao buscar datas de última venda: {response.text}"
            rules.add_error(error_msg)
            raise HTTPException(status_code=response.status_code, detail="Erro ao buscar datas de última venda")

        vendas_data = response.json()
        result = {item['produto_id']: item['max_data_saida'] for item in vendas_data}
        
        rules.add_rule("SALES_DATA_COLLECTED", f"Dados de venda coletados para {len(result)} produtos")
        return result
    except Exception as e:
        rules.add_error(f"Exceção ao buscar datas de venda: {str(e)}")
        raise

def fetch_max_data_compra_with_monitoring(produto_ids: list, rules: CalculationRules) -> Dict:
    try:
        url = f"{API_URL_BASE}/rest/v1/rpc/get_max_data_compra"
        payload = {"produto_ids": produto_ids}
        response = requests.post(url, headers=HEADERS, json=payload)

        if response.status_code != 200:
            error_msg = f"Erro ao buscar datas de última compra: {response.text}"
            rules.add_error(error_msg)
            raise HTTPException(status_code=response.status_code, detail="Erro ao buscar datas de última compra")

        compras_data = response.json()
        result = {item['produto_id']: item['max_data_compra'] for item in compras_data}
        
        rules.add_rule("PURCHASE_DATA_COLLECTED", f"Dados de compra coletados para {len(result)} produtos")
        return result
    except Exception as e:
        rules.add_error(f"Exceção ao buscar datas de compra: {str(e)}")
        raise

def process_calculation_with_monitoring(politicas: List[Dict], produtos: List[Dict], 
                                      produtos_datas: Dict, rules: CalculationRules) -> list:
    resultado = []
    melhor_politica_id = find_best_policy_with_monitoring(politicas, rules)
    
    rules.add_rule("BEST_POLICY_SELECTED", f"Melhor política selecionada: {melhor_politica_id}")

    # Cache para id_produto_bling
    id_produto_bling_cache = {}

    for politica in politicas:
        politica_id = politica['id']
        rules.add_rule("PROCESSING_POLICY", f"Processando política {politica_id}", data=politica)
        
        produtos_array = []
        valor_total_pedido = 0
        valor_total_pedido_com_desconto = 0
        quantidade_produtos = 0
        produtos_descartados = 0

        for produto in produtos:
            produto_id = produto['produto_id']
            
            try:
                # Processar produto com monitoramento detalhado
                produto_processado = process_product_with_monitoring(
                    produto, politica, produtos_datas, rules, id_produto_bling_cache
                )
                
                if produto_processado is None:
                    produtos_descartados += 1
                    continue
                
                # Atualizar totais
                valor_total_pedido += produto_processado['valor_total_produto']
                valor_total_pedido_com_desconto += produto_processado['valor_total_produto_com_desconto']
                quantidade_produtos += 1
                
                produtos_array.append(produto_processado)
                
            except Exception as e:
                rules.add_error(f"Erro ao processar produto {produto_id}: {str(e)}", produto_id)
                continue

        # Log do resultado da política
        rules.add_rule("POLICY_RESULT", f"Política {politica_id} processada", data={
            "produtos_incluidos": quantidade_produtos,
            "produtos_descartados": produtos_descartados,
            "valor_total": valor_total_pedido,
            "valor_com_desconto": valor_total_pedido_com_desconto
        })

        # Verificar valor mínimo
        valor_minimo = politica.get('valor_minimo') or 0
        if valor_total_pedido >= valor_minimo:
            politica_compra = montar_politica_compra(
                politica,
                valor_total_pedido,
                valor_total_pedido_com_desconto,
                quantidade_produtos,
                politica['id'] == melhor_politica_id,
                produtos_array
            )
            resultado.append(politica_compra)
            rules.add_rule("POLICY_INCLUDED", f"Política {politica_id} incluída no resultado")
        else:
            rules.add_rule("POLICY_EXCLUDED", f"Política {politica_id} excluída - valor mínimo não atingido", data={
                "valor_total": valor_total_pedido,
                "valor_minimo": valor_minimo
            })

    return resultado

def process_product_with_monitoring(produto: Dict, politica: Dict, produtos_datas: Dict, 
                                   rules: CalculationRules, cache: Dict) -> Optional[Dict]:
    produto_id = produto['produto_id']
    
    try:
        # Obter dados do histórico
        data_info = produtos_datas.get(produto_id, {})
        data_ultima_venda_str = data_info.get('data_ultima_venda')
        data_ultima_compra_str = data_info.get('data_ultima_compra')
        estoque_atual = produto.get('estoque_atual') or 0
        
        rules.add_rule("PRODUCT_DATA_COLLECTED", "Dados iniciais coletados", produto_id, data={
            "estoque_atual": estoque_atual,
            "data_ultima_venda_original": data_ultima_venda_str,
            "data_ultima_compra_original": data_ultima_compra_str
        })

        # REGRA 1: Aplicar regra de estoque com produto disponível
        if estoque_atual > 0:
            data_ultima_venda_str = datetime.now().date().isoformat()
            rules.add_rule("STOCK_AVAILABLE_RULE", "Produto com estoque - data de venda ajustada para hoje", 
                          produto_id, data={"nova_data_venda": data_ultima_venda_str})
        elif not data_ultima_venda_str:
            rules.add_rule("NO_SALES_HISTORY_RULE", "Produto sem histórico de vendas e sem estoque - descartado", produto_id)
            return None

        # REGRA 2: Ajustar datas
        data_ultima_venda = ajustar_data_futura_with_monitoring(
            parser.isoparse(data_ultima_venda_str).date(), rules, produto_id
        )
        data_ultima_compra = ajustar_data_compra_with_monitoring(
            data_ultima_compra_str, data_ultima_venda, rules, produto_id
        )

        # Calcular período de venda
        periodo_venda = max((data_ultima_venda - data_ultima_compra).days, 1)
        rules.add_rule("SALES_PERIOD_CALCULATED", f"Período de venda calculado: {periodo_venda} dias", 
                      produto_id, data={
                          "data_ultima_venda": data_ultima_venda.isoformat(),
                          "data_ultima_compra": data_ultima_compra.isoformat(),
                          "periodo_dias": periodo_venda
                      })

        # Buscar quantidade vendida
        quantidade_vendida = fetch_quantidade_vendida_with_monitoring(
            produto_id, data_ultima_compra.isoformat(), data_ultima_venda.isoformat(), rules
        )

        # Calcular média de vendas diárias
        media_venda_dia = quantidade_vendida / periodo_venda
        rules.add_rule("DAILY_AVERAGE_CALCULATED", f"Média diária calculada: {media_venda_dia:.2f}", 
                      produto_id, data={
                          "quantidade_vendida": quantidade_vendida,
                          "periodo_venda": periodo_venda,
                          "media_venda_dia": media_venda_dia
                      })

        # Calcular sugestão de quantidade
        sugestao_quantidade, multiplicacao = calcular_sugestao_with_monitoring(
            produto, politica, media_venda_dia, quantidade_vendida, rules
        )

        # Verificar se produto deve ser descartado
        if sugestao_quantidade <= 0:
            rules.add_rule("PRODUCT_DISCARDED", "Produto descartado - estoque suficiente", produto_id, data={
                "sugestao_quantidade": sugestao_quantidade,
                "estoque_atual": estoque_atual
            })
            return None

        # Calcular valores
        valor_total_produto, valor_total_produto_com_desconto = calcular_valores_with_monitoring(
            produto, politica, sugestao_quantidade, rules, produto_id
        )

        # Buscar id_produto_bling com cache
        if produto_id in cache:
            id_produto_bling = cache[produto_id]
        else:
            id_produto_bling = fetch_id_produto_bling(produto_id)
            cache[produto_id] = id_produto_bling

        # Montar resultado final do produto
        produto_resultado = montar_detalhes_produto(
            produto,
            quantidade_vendida,
            periodo_venda,
            sugestao_quantidade,
            valor_total_produto,
            valor_total_produto_com_desconto,
            multiplicacao,
            id_produto_bling,
            data_ultima_venda_str,
            data_ultima_compra_str
        )
        
        rules.add_rule("PRODUCT_PROCESSED", "Produto processado com sucesso", produto_id, data={
            "sugestao_quantidade": sugestao_quantidade,
            "valor_total": valor_total_produto,
            "valor_com_desconto": valor_total_produto_com_desconto
        })
        
        return produto_resultado
        
    except Exception as e:
        rules.add_error(f"Erro ao processar produto {produto_id}: {str(e)}", produto_id)
        return None

def calcular_sugestao_with_monitoring(produto: Dict, politica: Dict, media_venda_dia: float, 
                                    quantidade_vendida: float, rules: CalculationRules) -> tuple:
    produto_id = produto.get('produto_id')
    itens_por_caixa = produto.get('itens_por_caixa') or 1
    estoque_atual = produto.get('estoque_atual') or 0
    prazo_estoque = politica.get('prazo_estoque') or 0

    # Fórmula base
    sugestao_inicial = media_venda_dia * prazo_estoque - estoque_atual
    rules.add_rule("INITIAL_SUGGESTION", "Sugestão inicial calculada", produto_id, data={
        "media_venda_dia": media_venda_dia,
        "prazo_estoque": prazo_estoque,
        "estoque_atual": estoque_atual,
        "sugestao_inicial": sugestao_inicial
    })

    if sugestao_inicial <= 0:
        return 0, False

    # Ajustar por embalagem
    if itens_por_caixa > 1:
        resto = sugestao_inicial % itens_por_caixa
        if resto != 0:
            if resto >= itens_por_caixa / 2:
                sugestao_quantidade = sugestao_inicial - resto + itens_por_caixa
                rules.add_rule("PACKAGE_ROUND_UP", "Arredondado para cima por embalagem", produto_id, data={
                    "resto": resto,
                    "itens_por_caixa": itens_por_caixa,
                    "sugestao_final": sugestao_quantidade
                })
            else:
                sugestao_quantidade = sugestao_inicial - resto
                rules.add_rule("PACKAGE_ROUND_DOWN", "Arredondado para baixo por embalagem", produto_id, data={
                    "resto": resto,
                    "itens_por_caixa": itens_por_caixa,
                    "sugestao_final": sugestao_quantidade
                })
        else:
            sugestao_quantidade = sugestao_inicial
    else:
        sugestao_quantidade = round(sugestao_inicial)
        rules.add_rule("SIMPLE_ROUND", "Arredondamento simples", produto_id, data={
            "sugestao_inicial": sugestao_inicial,
            "sugestao_final": sugestao_quantidade
        })

    # Regra de multiplicação por estoque crítico
    multiplicacao = False
    if estoque_atual < 2 and sugestao_quantidade > 0:
        sugestao_quantidade = max(sugestao_quantidade, itens_por_caixa)
        multiplicacao = True
        rules.add_rule("CRITICAL_STOCK_RULE", "Regra de estoque crítico aplicada", produto_id, data={
            "estoque_atual": estoque_atual,
            "quantidade_garantida": sugestao_quantidade
        })

    return sugestao_quantidade, multiplicacao

def calcular_valores_with_monitoring(produto: Dict, politica: Dict, sugestao_quantidade: float, 
                                   rules: CalculationRules, produto_id: int) -> tuple:
    valor_de_compra = produto.get('valor_de_compra') or 0
    valor_total_produto = sugestao_quantidade * valor_de_compra
    desconto = politica.get('desconto') or 0
    valor_total_produto_com_desconto = valor_total_produto * (1 - desconto)
    
    rules.add_rule("VALUES_CALCULATED", "Valores calculados", produto_id, data={
        "valor_unitario": valor_de_compra,
        "quantidade": sugestao_quantidade,
        "valor_total": valor_total_produto,
        "desconto": desconto,
        "valor_com_desconto": valor_total_produto_com_desconto
    })
    
    return valor_total_produto, valor_total_produto_com_desconto

def ajustar_data_futura_with_monitoring(data: datetime, rules: CalculationRules, produto_id: int) -> datetime:
    data_hoje = datetime.now().date()
    if data > data_hoje:
        rules.add_rule("FUTURE_DATE_ADJUSTED", "Data futura ajustada para hoje", produto_id, data={
            "data_original": data.isoformat(),
            "data_ajustada": data_hoje.isoformat()
        })
        return data_hoje
    return data

def ajustar_data_compra_with_monitoring(data_ultima_compra_str: str, data_ultima_venda: datetime, 
                                      rules: CalculationRules, produto_id: int) -> datetime:
    if not data_ultima_compra_str:
        data_ajustada = data_ultima_venda - timedelta(days=365)
        rules.add_rule("NULL_PURCHASE_DATE", "Data de compra nula - assumindo 1 ano antes da venda", 
                      produto_id, data={
                          "data_venda": data_ultima_venda.isoformat(),
                          "data_compra_assumida": data_ajustada.isoformat()
                      })
        return data_ajustada
    
    data_ultima_compra = parser.isoparse(data_ultima_compra_str).date()
    data_minima = data_ultima_venda - timedelta(days=1)
    
    if data_ultima_compra >= data_ultima_venda:
        rules.add_rule("PURCHASE_DATE_ADJUSTED", "Data de compra ajustada para 1 dia antes da venda", 
                      produto_id, data={
                          "data_compra_original": data_ultima_compra.isoformat(),
                          "data_compra_ajustada": data_minima.isoformat(),
                          "data_venda": data_ultima_venda.isoformat()
                      })
        return data_minima
    
    return data_ultima_compra

def fetch_quantidade_vendida_with_monitoring(produto_id: int, data_inicio: str, data_fim: str, 
                                           rules: CalculationRules) -> float:
    try:
        url = f"{API_URL_BASE}/rest/v1/rpc/get_quantidade_vendida"
        payload = {
            "p_produto_id": produto_id,
            "data_inicio": data_inicio,
            "data_fim": data_fim
        }
        response = requests.post(url, headers=HEADERS, json=payload)

        if response.status_code != 200:
            error_msg = f"Erro ao buscar quantidade vendida: {response.text}"
            rules.add_error(error_msg, produto_id)
            raise HTTPException(status_code=response.status_code, detail=f"Erro ao buscar quantidade vendida")

        result = response.json()
        quantidade = float(result[0]['quantidade_vendida']) if result else 0
        
        rules.add_rule("QUANTITY_SOLD_FETCHED", f"Quantidade vendida obtida: {quantidade}", produto_id, data={
            "data_inicio": data_inicio,
            "data_fim": data_fim,
            "quantidade_vendida": quantidade
        })
        
        return quantidade
    except Exception as e:
        rules.add_error(f"Exceção ao buscar quantidade vendida: {str(e)}", produto_id)
        raise

def find_best_policy_with_monitoring(politicas: List[Dict], rules: CalculationRules) -> int:
    melhor_desconto = 0
    menor_prazo = float('inf')
    melhor_politica_id = None

    rules.add_rule("BEST_POLICY_SEARCH", f"Analisando {len(politicas)} políticas para encontrar a melhor")

    for politica in politicas:
        desconto = politica.get('desconto') or 0
        prazo_estoque = politica.get('prazo_estoque') or float('inf')
        politica_id = politica.get('id')

        rules.add_rule("POLICY_EVALUATION", "Avaliando política", data={
            "politica_id": politica_id,
            "desconto": desconto,
            "prazo_estoque": prazo_estoque,
            "eh_melhor_desconto": desconto > melhor_desconto,
            "eh_menor_prazo": prazo_estoque < menor_prazo
        })

        if desconto > melhor_desconto or (desconto == melhor_desconto and prazo_estoque < menor_prazo):
            melhor_desconto = desconto
            menor_prazo = prazo_estoque
            melhor_politica_id = politica_id
            
            rules.add_rule("NEW_BEST_POLICY", f"Nova melhor política encontrada: {politica_id}", data={
                "desconto": desconto,
                "prazo_estoque": prazo_estoque
            })

    rules.add_rule("BEST_POLICY_FINAL", f"Melhor política determinada: {melhor_politica_id}", data={
        "melhor_desconto": melhor_desconto,
        "menor_prazo": menor_prazo
    })

    return melhor_politica_id

# === FUNÇÕES ORIGINAIS MANTIDAS PARA COMPATIBILIDADE ===

def fetch_policies(fornecedor_id: int) -> List[Dict]:
    url = f"{API_URL_BASE}/rest/v1/rpc/flowb2b_fetch_politica_compra"
    payload = {"f_id": fornecedor_id}
    response = requests.post(url, headers=HEADERS, json=payload)

    if response.status_code != 200:
        logger.error(f"Erro ao buscar políticas: {response.text}")
        raise HTTPException(status_code=response.status_code, detail="Erro ao buscar políticas")

    return response.json()

def fetch_products(fornecedor_id: int) -> List[Dict]:
    url = f"{API_URL_BASE}/rest/v1/rpc/flowb2b_get_produtos_detalhados"
    payload = {"f_id": fornecedor_id}
    response = requests.post(url, headers=HEADERS, json=payload)

    if response.status_code != 200:
        logger.error(f"Erro ao buscar produtos: {response.text}")
        raise HTTPException(status_code=response.status_code, detail="Erro ao buscar produtos")

    return response.json()

def fetch_produto_datas(produto_ids: list) -> Dict:
    try:
        vendas_data = fetch_max_data_saida(produto_ids)
        compras_data = fetch_max_data_compra(produto_ids)

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

def fetch_id_produto_bling(produto_id: int) -> int:
    url = f"{API_URL_BASE}/rest/v1/produtos?id=eq.{produto_id}"
    response = requests.get(url, headers=HEADERS)

    if response.status_code != 200:
        logger.error(f"Erro ao buscar id_produto_bling: {response.text}")
        raise HTTPException(status_code=response.status_code, detail="Erro ao buscar id_produto_bling")

    result = response.json()
    return result[0]['id_produto_bling'] if result else None

def process_calculation(politicas: List[Dict], produtos: List[Dict], produtos_datas: Dict) -> list:
    resultado = []
    melhor_politica_id = find_best_policy(politicas)

    id_produto_bling_cache = {}

    for politica in politicas:
        produtos_array = []
        valor_total_pedido = 0
        valor_total_pedido_com_desconto = 0
        quantidade_produtos = 0

        for produto in produtos:
            produto_id = produto['produto_id']

            data_info = produtos_datas.get(produto_id, {})
            data_ultima_venda_str = data_info.get('data_ultima_venda')
            data_ultima_compra_str = data_info.get('data_ultima_compra')

            estoque_atual = produto.get('estoque_atual') or 0

            if estoque_atual > 0:
                data_ultima_venda_str = datetime.now().date().isoformat()
            elif not data_ultima_venda_str:
                continue

            data_ultima_venda = ajustar_data_futura(parser.isoparse(data_ultima_venda_str).date())
            data_ultima_compra = ajustar_data_compra(data_ultima_compra_str, data_ultima_venda)

            periodo_venda = max((data_ultima_venda - data_ultima_compra).days, 1)

            quantidade_vendida = fetch_quantidade_vendida(
                produto_id,
                data_ultima_compra.isoformat(),
                data_ultima_venda.isoformat()
            )

            media_venda_dia = quantidade_vendida / periodo_venda

            sugestao_quantidade, multiplicacao = calcular_sugestao(produto, politica, media_venda_dia, quantidade_vendida)

            if sugestao_quantidade <= 0:
                continue

            valor_total_produto, valor_total_produto_com_desconto = calcular_valores(produto, politica, sugestao_quantidade)

            valor_total_pedido += valor_total_produto
            valor_total_pedido_com_desconto += valor_total_produto_com_desconto
            quantidade_produtos += 1

            if produto_id in id_produto_bling_cache:
                id_produto_bling = id_produto_bling_cache[produto_id]
            else:
                id_produto_bling = fetch_id_produto_bling(produto_id)
                id_produto_bling_cache[produto_id] = id_produto_bling

            produtos_array.append(montar_detalhes_produto(
                produto,
                quantidade_vendida,
                periodo_venda,
                sugestao_quantidade,
                valor_total_produto,
                valor_total_produto_com_desconto,
                multiplicacao,
                id_produto_bling,
                data_ultima_venda_str,
                data_ultima_compra_str
            ))

        if valor_total_pedido >= (politica.get('valor_minimo') or 0):
            politica_compra = montar_politica_compra(
                politica,
                valor_total_pedido,
                valor_total_pedido_com_desconto,
                quantidade_produtos,
                politica['id'] == melhor_politica_id,
                produtos_array
            )
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

    sugestao_quantidade = media_venda_dia * prazo_estoque - estoque_atual

    if sugestao_quantidade <= 0:
        return 0, False

    if itens_por_caixa > 1:
        resto = sugestao_quantidade % itens_por_caixa
        if resto != 0:
            if resto >= itens_por_caixa / 2:
                sugestao_quantidade = sugestao_quantidade - resto + itens_por_caixa
            else:
                sugestao_quantidade = sugestao_quantidade - resto
    else:
        sugestao_quantidade = round(sugestao_quantidade)

    multiplicacao = False
    if estoque_atual < 2 and sugestao_quantidade > 0:
        sugestao_quantidade = max(sugestao_quantidade, itens_por_caixa)
        multiplicacao = True

    return sugestao_quantidade, multiplicacao

def calcular_valores(produto: Dict, politica: Dict, sugestao_quantidade: float) -> tuple:
    valor_de_compra = produto.get('valor_de_compra') or 0
    valor_total_produto = sugestao_quantidade * valor_de_compra
    desconto = politica.get('desconto') or 0
    valor_total_produto_com_desconto = valor_total_produto * (1 - desconto)
    return valor_total_produto, valor_total_produto_com_desconto

def montar_detalhes_produto(produto: Dict, quantidade_vendida: float, periodo_venda: int, 
                          sugestao_quantidade: float, valor_total_produto: float, 
                          valor_total_produto_com_desconto: float, multiplicacao: bool, 
                          id_produto_bling: int, data_ultima_venda_str: str, 
                          data_ultima_compra_str: str) -> Dict:
    return {
        'produto_id': produto['produto_id'],
        'codigo_do_produto': produto.get('codigo_produto'),
        'quantidade_vendida': quantidade_vendida,
        'periodo_venda': periodo_venda,
        'sugestao_quantidade': sugestao_quantidade,
        'valor_total_produto': valor_total_produto,
        'valor_total_produto_com_desconto': valor_total_produto_com_desconto,
        'estoque_atual': produto.get('estoque_atual') or 0,
        'data_ultima_venda': data_ultima_venda_str,
        'data_ultima_compra': data_ultima_compra_str,
        'itens_por_caixa': produto.get('itens_por_caixa') or 1,
        'multiplicacao_aplicada': multiplicacao,
        'id_produto_bling': id_produto_bling
    }

def montar_politica_compra(politica: Dict, valor_total_pedido: float, 
                          valor_total_pedido_com_desconto: float, quantidade_produtos: int, 
                          melhor_politica: bool, produtos_array: list) -> Dict:
    return {
        'politica_id': politica.get('id'),
        'desconto': politica.get('desconto'),
        'bonificacao': politica.get('bonificacao'),
        'valor_minimo': politica.get('valor_minimo'),
        'prazo_estoque': politica.get('prazo_estoque'),
        'melhor_politica': melhor_politica,
        'quantidade_produtos': quantidade_produtos,
        'valor_total_pedido_sem_desconto': valor_total_pedido,
        'valor_total_pedido_com_desconto': valor_total_pedido_com_desconto,
        'produtos': produtos_array
    }

def find_best_policy(politicas: List[Dict]) -> int:
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
