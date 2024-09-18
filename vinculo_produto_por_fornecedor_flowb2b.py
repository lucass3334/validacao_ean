from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, HttpUrl
import requests

router = APIRouter()

class EmpresaVinculo(BaseModel):
    empresa_id: int
    webhook_url: HttpUrl

API_URL_BASE = "https://asahknimbggpzpoebmej.supabase.co"
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFzYWhrbmltYmdncHpwb2VibWVqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MTcxODQxNjMsImV4cCI6MjAzMjc2MDE2M30.rYChkMDDU-hdsMK_MxT6tQLCTNj_D6U__jQKIaXCP2U"

def processar_vinculo(empresa_id: int, webhook_url: str):
    headers = {
        "apikey": API_KEY,
        "Content-Type": "application/json"
    }

    try:
        # Obter todos os IDs de fornecedores
        fornecedores_url = f"{API_URL_BASE}/rest/v1/fornecedores?empresa_id=eq.{empresa_id}&select=id"
        response = requests.get(fornecedores_url, headers=headers)

        if response.status_code != 200:
            raise Exception("Erro ao buscar fornecedores")

        fornecedores = response.json()
        if not fornecedores:
            result = {"message": "Nenhum fornecedor encontrado"}
        else:
            for fornecedor in fornecedores:
                fornecedor_id = fornecedor.get("id")
                if not fornecedor_id:
                    continue

                payload = {
                    "fornecedor_id_param": fornecedor_id,
                    "empresa_id_param": empresa_id
                }
                update_url = f"{API_URL_BASE}/rest/v1/rpc/update_produto_id"
                update_response = requests.post(update_url, json=payload, headers=headers)

                if update_response.status_code != 200:
                    # Registrar o erro conforme necessário
                    continue
            result = {"message": "Vínculo de produtos por fornecedor concluído com sucesso"}

        # Enviar notificação para o webhook_url
        requests.post(webhook_url, json=result)

    except Exception as e:
        error_message = {"error": str(e)}
        # Enviar notificação de erro para o webhook_url
        requests.post(webhook_url, json=error_message)

@router.post("/")
async def vincular_produtos(empresa: EmpresaVinculo, background_tasks: BackgroundTasks):
    background_tasks.add_task(processar_vinculo, empresa_id=empresa.empresa_id, webhook_url=str(empresa.webhook_url))
    return {"message": "Processamento iniciado, você será notificado quando concluído via webhook"}
