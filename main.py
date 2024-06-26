from fastapi import FastAPI
from validacao_ean import router as validacao_router
from cobasi_api import router as cobasi_router
from cobasi_ean_api import router as cobasi_ean_router
from petz_ean_api import router as petz_ean_router

app = FastAPI()

app.include_router(validacao_router, prefix="/validacao_ean")
app.include_router(cobasi_router, prefix="/cobasi_api")
app.include_router(cobasi_ean_router, prefix="/cobasi_ean")
app.include_router(petz_ean_router, prefix="/petz_ean")
