from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests

router = APIRouter()

class EmpresaID(BaseModel):
    empresa_id: int

API_URL_BASE = "https://asahknimbggpzpoebmej.supabase.co"
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFzYWhrbmltYmdncHpwb2VibWVqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MTcxODQxNjMsImV4cCI6MjAzMjc2MDE2M30.rYChkMDDU-hdsMK_MxT6tQLCTNj_D6U__jQKIaXCP2U"

@router.post("/")
async def detalhar_produtos(empresa: EmpresaID):
    headers = {
        "apikey": API_KEY,
        "Content-Type": "application/json"
    }

    # Obter todas as chaves de acesso
    notas_url = f"{API_URL_BASE}/rest/v1/notas_fiscais?empresa_id=eq.{empresa.empresa_id}&select=chave_acesso"
    response = requests.get(notas_url, headers=headers)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Erro ao buscar notas fiscais")

    notas = response.json()
    if not notas:
        return {"message": "Nenhuma nota fiscal encontrada"}

    for nota in notas:
        chave_acesso = nota.get("chave_acesso")
        if not chave_acesso:
            continue

        payload = {
            "chave_acesso": chave_acesso,
            "empresa_id": empresa.empresa_id
        }
        detalhes_url = f"{API_URL_BASE}/functions/v1/detalhes_nota_fiscal_chave_acesso"
        detalhes_response = requests.post(detalhes_url, json=payload, headers=headers)

        if detalhes_response.status_code != 200:
            # Você pode registrar o erro ou lidar conforme necessário
            continue

    return {"message": "Detalhamento de produtos concluído com sucesso"}
