from fastapi import FastAPI

from app.routers import health, beneficiaries, matching, duplicate_flags

app = FastAPI(title="Mustahiq AI - Backend API")

app.include_router(health.router)
app.include_router(beneficiaries.router)
app.include_router(matching.router)
app.include_router(duplicate_flags.router)

@app.get("/")
def root():
    return {"message": "Mustahiq AI backend is running"}