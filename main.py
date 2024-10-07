from fastapi import FastAPI
from validacao_ean import router as validacao_router
from cobasi_api import router as cobasi_router
from cobasi_ean_api import router as cobasi_ean_router
from petz_ean_api import router as petz_ean_router
from Detalhamento_de_produtos_flowb2b import router as detalhamento_router
from vinculo_produto_por_fornecedor_flowb2b import router as vinculo_router
from calculo_pedido_auto_otimizado import router as calculo_router
from empresa_sync_apis import router as empresa_sync_router  # Novo import

app = FastAPI()

app.include_router(validacao_router, prefix="/validacao_ean")
app.include_router(cobasi_router, prefix="/cobasi_api")
app.include_router(cobasi_ean_router, prefix="/cobasi_ean")
app.include_router(petz_ean_router, prefix="/petz_ean")
app.include_router(detalhamento_router, prefix="/detalhamento_de_produtos")
app.include_router(vinculo_router, prefix="/vinculo_produto_por_fornecedor")
app.include_router(calculo_router, prefix="/calculo_pedido_auto_otimizado")
app.include_router(empresa_sync_router, prefix="/empresa_sync")  # Novo router
