from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(title="ContentOps API")

app.include_router(router)
