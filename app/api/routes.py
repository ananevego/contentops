from fastapi import APIRouter
import os

router = APIRouter()

@router.get("/")
def root():
    return {"message": "ContentOps is running"}

@router.get("/health")
def root():
    return {"status": "ok",
    "service": "contentops-api"}

@router.get("/hello")
def root():
    return {"message": "Hello from ContentOps"}

@router.get("/config")
def root():
    return {"app_name": os.getenv("APP_NAME"), "environment": os.getenv("ENVIRONMENT")}
