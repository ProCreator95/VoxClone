from fastapi import APIRouter

from app.api.v1.endpoints import health, jobs, media, uploads

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(uploads.router)
api_router.include_router(media.router)
api_router.include_router(jobs.router)
