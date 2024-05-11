from fastapi import APIRouter, HTTPException, status
from fastapi.params import Body
import httpx

router = APIRouter()

@router.post("/token")
async def get_token(code: str = Body(..., embed=True)):
    url = "https://www.bling.com.br/Api/v3/oauth/token"
    headers = {
        "Authorization": "Basic NmY2ZDdjMmY3ZDUzNzA3ODhmNmE4MDVkMjJhOWY0ZjdhNmNiYTUyZTpiNDg1NTdkZjAyNjI4ODFiOTc5ZjM3NmU5YjAyM2FjODZiZGM3ZDdmNzBmNGFhODkzZGI5NGE3MGIzZGY=",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    body = {
        "grant_type": "authorization_code",
        "code": code
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, data=body)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Failed to get tokens")
        return response.json()
