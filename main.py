from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from validacao_ean import router as validacao_router
from cobasi_api import router as cobasi_router
from cobasi_ean_api import router as cobasi_ean_router
from petz_ean_api import router as petz_ean_router
from Detalhamento_de_produtos_flowb2b import router as detalhamento_router
from vinculo_produto_por_fornecedor_flowb2b import router as vinculo_router
from calculo_pedido_auto_otimizado import router as calculo_router

app = FastAPI(
    title="FlowB2B API",
    description="API para cálculo de pedidos, validação de EAN e scraping de produtos",
    version="2.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir routers
app.include_router(validacao_router, prefix="/validacao_ean", tags=["Validação EAN"])
app.include_router(cobasi_router, prefix="/cobasi_api", tags=["Cobasi API"])
app.include_router(cobasi_ean_router, prefix="/cobasi_ean", tags=["Cobasi EAN"])
app.include_router(petz_ean_router, prefix="/petz_ean", tags=["Petz EAN"])
app.include_router(detalhamento_router, prefix="/detalhamento_de_produtos", tags=["Detalhamento"])
app.include_router(vinculo_router, prefix="/vinculo_produto_por_fornecedor", tags=["Vínculo Produtos"])
app.include_router(calculo_router, prefix="/calculo_pedido_auto_otimizado", tags=["Cálculo Pedidos"])

@app.get("/")
async def root():
    return {
        "message": "FlowB2B API v2.0.0",
        "endpoints": {
            "validacao_ean": "/validacao_ean/validar_ean/?ean={ean}",
            "cobasi_upload": "/cobasi_api/uploadfile/",
            "cobasi_produto": "/cobasi_ean/produto/{ean}",
            "petz_produto": "/petz_ean/produto/{nome}",
            "detalhamento": "/detalhamento_de_produtos/",
            "vinculo": "/vinculo_produto_por_fornecedor/",
            "calculo_pedido": "/calculo_pedido_auto_otimizado/calcular",
            "monitoramento_calculo": "/calculo_pedido_auto_otimizado/monitoramento/{fornecedor_id}"
        }
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": "2024-06-05T10:00:00Z"}
