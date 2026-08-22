from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "ContentOps is running"}

@app.get("/health")
def root():
    return {"status": "ok"}
