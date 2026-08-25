from fastapi import APIRouter

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
