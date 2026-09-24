from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.core.settings import settings
from app.api.hospital import router as hospital_router
from app.api.department import router as department_router
from app.api.ward import router as ward_router


app = FastAPI(
    title=settings.app_name,
    description="Local hospital AI monitoring and video intelligence platform",
    version=settings.app_version,
)


app.include_router(auth_router)
app.include_router(hospital_router)
app.include_router(department_router)
app.include_router(ward_router)


@app.get("/")
def root():
    return {
        "application": settings.app_name,
        "version": settings.app_version,
        "status": "online",
        "environment": settings.environment,
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }