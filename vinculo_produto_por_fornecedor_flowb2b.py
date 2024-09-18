from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests

router = APIRouter()

class EmpresaID(BaseModel):
    empresa_id: int

API_URL_BASE = "https://asahknimbggpzpoebmej.supabase.co"
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFzYWhrbmltYmdncHpwb2VibWVqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MTcxODQxNjMsImV4cCI6MjAzMjc2MDE2M30.rYChkMDDU-hdsMK_MxT6tQLCTNj_D6U__jQKIaXCP2U"

@router.post("/")
async def vincular_produtos(empresa: EmpresaID):
    headers = {
        "apikey": API_KEY,
        "Content-Type": "application/json"
    }

    # Obter todos os IDs de fornecedores
    fornecedores_url = f"{API_URL_BASE}/rest/v1/fornecedores?empresa_id=eq.{empresa.empresa_id}&select=id"
    response = requests.get(fornecedores_url, headers=headers)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Erro ao buscar fornecedores")

    fornecedores = response.json()
    if not fornecedores:
        return {"message": "Nenhum fornecedor encontrado"}

    for fornecedor in fornecedores:
        fornecedor_id = fornecedor.get("id")
        if not fornecedor_id:
            continue

        payload = {
            "fornecedor_id_param": fornecedor_id,
            "empresa_id_param": empresa.empresa_id
        }
        update_url = f"{API_URL_BASE}/rest/v1/rpc/update_produto_id"
        update_response = requests.post(update_url, json=payload, headers=headers)

        if update_response.status_code != 200:
            # Você pode registrar o erro ou lidar conforme necessário
            continue

    return {"message": "Vínculo de produtos por fornecedor concluído com sucesso"}
