from contextlib import asynccontextmanager
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
for directory in [ROOT / 'packages', ROOT / 'packages' / 'rag']:
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.portal.router import router


@asynccontextmanager
async def lifespan(app):
    if settings.portal_demo_mode:
        from app.portal.seed import seed_demo
        seed_demo()
    yield


app = FastAPI(title='Mustahiq AI · Staff API', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[v.strip() for v in settings.staff_portal_origins.split(',') if v.strip()],
                   allow_methods=['GET', 'POST', 'PUT', 'PATCH'], allow_headers=['Authorization', 'Content-Type'])
app.include_router(router)


@app.exception_handler(IntegrityError)
async def integrity_conflict(request, exception):
    return JSONResponse(status_code=409, content={'detail': 'This action conflicts with an existing record. Refresh the workspace and review the latest state.'})

from app.routers import health, beneficiaries, matching, duplicate_flags
app.include_router(health.router)
app.include_router(beneficiaries.router)
app.include_router(matching.router)
app.include_router(duplicate_flags.router)


@app.get('/')
def root():
    return {'message': 'Mustahiq AI staff backend', 'demo_mode': settings.portal_demo_mode}
