from fastapi import FastAPI

from app.routers import health, beneficiaries

app = FastAPI(title="Mustahiq AI - Backend API")

app.include_router(health.router)
app.include_router(beneficiaries.router)

@app.get("/")
def root():
    return {"message": "Mustahiq AI backend is running"}