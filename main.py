from fastapi import FastAPI
from validacao_ean import router as validacao_router
from cobasi_api import router as cobasi_router

app = FastAPI()

app.include_router(validacao_router, prefix="/validacao_ean")
app.include_router(cobasi_router, prefix="/cobasi_api")
