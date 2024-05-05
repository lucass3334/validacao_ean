from fastapi import APIRouter, HTTPException
router = APIRouter()

def calcular_digito_verificacao(ean: str) -> int:
    """Calcula o dígito de verificação de um EAN-13."""
    soma = 0
    for i, numero in enumerate(ean[:12]):
        if i % 2 == 0:  # índices pares
            soma += int(numero)
        else:  # índices ímpares
            soma += int(numero) * 3
    digito_verificacao = (10 - soma % 10) % 10
    return digito_verificacao

def validar_ean(ean: str) -> bool:
    """Valida um EAN-13 verificando o dígito de verificação."""
    if not ean.isdigit() or len(ean) != 13:
        return False
    digito_calculado = calcular_digito_verificacao(ean)
    return digito_calculado == int(ean[-1])

@router.get("/validar_ean/")
async def validar_ean_api(ean: str):
    if len(ean) != 13 or not ean.isdigit():
        raise HTTPException(status_code=400, detail="O EAN deve ter exatamente 13 dígitos numéricos.")
    ean_valido = validar_ean(ean)
    return {"EAN_VALIDO": ean_valido}


