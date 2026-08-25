from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "ContentOps is running"}

@app.get("/health")
def root():
    return {"status": "ok",
    "service": "contentops-api"}

@app.get("/hello")
def root():
    return {"message": "Hello from ContentOps"}
