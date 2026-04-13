from fastapi import APIRouter
from fastapi.responses import JSONResponse
import re
import requests

router = APIRouter()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'pt-BR,pt;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
}

# Padrao JSON embedded no HTML: "name":"..." ... "image":"https://a-static.mlcdn.com.br/.../.jpg"
_PATTERN_NAME_IMAGE = re.compile(
    r'"name":"([^"]{10,200})"[^}]{0,500}?"image":"(https://a-static\.mlcdn\.com\.br[^"]+\.jpe?g)"'
)


def buscar_produto_magalu(ean: str):
    """
    Busca produto no Magalu via HTML estatico.
    Os produtos sao embedded no HTML como JSON pelo Next.js do magazineluiza.com.br.
    Nao precisa Selenium.
    """
    url = f"https://www.magazineluiza.com.br/busca/{ean}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return None

        # Busca pares nome+imagem no JSON embedded
        matches = _PATTERN_NAME_IMAGE.findall(r.text)
        if not matches:
            return None

        # Primeiro match e o primeiro resultado da busca
        for nome, img in matches:
            if not img or 'icon' in img.lower() or 'logo' in img.lower():
                continue
            # Upgrade resolucao: 186x140 -> 1500x1500 (Magalu aceita qualquer)
            img_hi = img.replace('/186x140/', '/1500x1500/').replace('/280x210/', '/1500x1500/')
            return {
                'ean': ean,
                'nome': nome.strip(),
                'imagem_url': img_hi,
                'source': 'magalu',
            }
        return None
    except Exception:
        return None


@router.get("/produto/{ean}")
async def buscar_produto(ean: str):
    resultado = buscar_produto_magalu(ean)
    if resultado:
        return {
            'EAN': ean,
            'Nome do Produto': resultado['nome'],
            'Link da Imagem': resultado['imagem_url'],
            'Fonte': 'Magazine Luiza',
        }
    return JSONResponse(status_code=404, content={"Erro": "Produto nao encontrado no Magazine Luiza"})
