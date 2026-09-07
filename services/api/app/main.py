import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGES_DIR = REPO_ROOT / "packages"
if str(PACKAGES_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGES_DIR))

from eligibility.persistence import load_scorer

from app.routers import health, beneficiaries, matching, duplicate_flags, programs

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.eligibility_scorer = load_scorer(REPO_ROOT / "artifacts" / "eligibility-scorer")
    yield


app = FastAPI(title="Mustahiq AI - Backend API", lifespan=lifespan)

app.include_router(health.router)
app.include_router(beneficiaries.router)
app.include_router(matching.router)
app.include_router(duplicate_flags.router)
app.include_router(programs.router)

@app.get("/")
def root():
    return {"message": "Mustahiq AI backend is running"}
