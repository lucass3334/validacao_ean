from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, HttpUrl
import requests

router = APIRouter()

class EmpresaDetalhamento(BaseModel):
    empresa_id: int
    webhook_url: HttpUrl

API_URL_BASE = "https://asahknimbggpzpoebmej.supabase.co"
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

def processar_detalhamento(empresa_id: int, webhook_url: str):
    headers = {
        "apikey": API_KEY,
        "Content-Type": "application/json"
    }

    try:
        # Obter todas as chaves de acesso
        notas_url = f"{API_URL_BASE}/rest/v1/notas_fiscais?empresa_id=eq.{empresa_id}&select=chave_acesso"
        response = requests.get(notas_url, headers=headers)

        if response.status_code != 200:
            raise Exception("Erro ao buscar notas fiscais")

        notas = response.json()
        if not notas:
            result = {"message": "Nenhuma nota fiscal encontrada"}
        else:
            for nota in notas:
                chave_acesso = nota.get("chave_acesso")
                if not chave_acesso:
                    continue

                payload = {
                    "chave_acesso": chave_acesso,
                    "empresa_id": empresa_id
                }
                detalhes_url = f"{API_URL_BASE}/functions/v1/detalhes_nota_fiscal_chave_acesso"
                detalhes_response = requests.post(detalhes_url, json=payload, headers=headers)

                if detalhes_response.status_code != 200:
                    # Registrar o erro conforme necessário
                    continue
            result = {"message": "Detalhamento de produtos concluído com sucesso"}

        # Enviar notificação para o webhook_url
        requests.post(webhook_url, json=result)

    except Exception as e:
        error_message = {"error": str(e)}
        # Enviar notificação de erro para o webhook_url
        requests.post(webhook_url, json=error_message)

@router.post("/")
async def detalhar_produtos(empresa: EmpresaDetalhamento, background_tasks: BackgroundTasks):
    background_tasks.add_task(processar_detalhamento, empresa_id=empresa.empresa_id, webhook_url=str(empresa.webhook_url))
    return {"message": "Processamento iniciado, você será notificado quando concluído via webhook"}
