
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.hospital import router as hospital_router
from app.api.department import router as department_router
from app.api.ward import router as ward_router
from app.api.room import router as room_router
from app.api.bed import router as bed_router
from app.api.patient import router as patient_router
from app.api.camera import router as camera_router
from app.api.event import router as event_router
from app.api.alert import router as alert_router
from app.api.video import router as video_router
from app.api.playback import router as playback_router
from app.api.users import router as users_router
from app.api.live import router as live_router

from app.core.settings import settings


app = FastAPI(
    title=settings.app_name,
    description=(
        "Local hospital AI monitoring and video "
        "intelligence platform"
    ),
    version=settings.app_version,
)


# =========================================================
# CORS CONFIGURATION
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# REGISTER API ROUTERS
# =========================================================

app.include_router(auth_router)
app.include_router(hospital_router)
app.include_router(department_router)
app.include_router(ward_router)
app.include_router(room_router)
app.include_router(bed_router)
app.include_router(patient_router)
app.include_router(camera_router)
app.include_router(event_router)
app.include_router(alert_router)
app.include_router(video_router)
app.include_router(playback_router)
app.include_router(users_router)
app.include_router(live_router)


# =========================================================
# ROOT ENDPOINT
# =========================================================

@app.get("/")
def root():
    return {
        "application": settings.app_name,
        "version": settings.app_version,
        "status": "online",
        "environment": settings.environment,
    }


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health():
    return {
        "status": "healthy",
    }
