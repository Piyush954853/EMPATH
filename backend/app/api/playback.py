
from pathlib import Path
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.permissions import require_permission
from app.core.database import get_db
from app.models.camera import Camera
from app.models.user import User
from app.services.playback_manager import playback_manager
from app.services.resource_access import (
    can_access_camera,
    is_admin,
)


router = APIRouter(
    prefix="/playback",
    tags=["Shared Video Playback"],
)


# backend/storage/playback
BACKEND_DIR = Path(__file__).resolve().parents[2]
PLAYBACK_DIR = BACKEND_DIR / "storage" / "playback"

MAX_UPLOAD_BYTES = 300 * 1024 * 1024
ALLOWED_EXTENSIONS = {".mp4", ".webm"}


# =========================================================
# COMMON HELPERS
# =========================================================

def get_camera_or_404(
    db: Session,
    camera_id: int,
) -> Camera:
    camera = db.get(Camera, camera_id)

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found",
        )

    return camera


def ensure_admin(
    db: Session,
    current_user: User,
) -> None:
    if not is_admin(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can control shared playback",
        )


def ensure_camera_access(
    db: Session,
    current_user: User,
    camera: Camera,
) -> None:
    if not can_access_camera(
        db,
        current_user,
        camera.id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Camera access denied",
        )


def ensure_camera_active(camera: Camera) -> None:
    if not camera.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The selected camera is inactive",
        )


# =========================================================
# START SHARED VIDEO LOOP
# ADMIN ONLY
# =========================================================

@router.post("/cameras/{camera_id}/start")
async def start_shared_playback(
    camera_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(
        require_permission("cameras.manage")
    ),
    db: Session = Depends(get_db),
):
    ensure_admin(db, current_user)

    camera = get_camera_or_404(
        db,
        camera_id,
    )

    ensure_camera_active(camera)

    ensure_camera_access(
        db,
        current_user,
        camera,
    )

    if playback_manager.is_busy(camera.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A playback session is already active for this camera",
        )

    original_filename = Path(
        (file.filename or "playback.mp4").replace("\\", "/")
    ).name

    extension = Path(original_filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only MP4 and WEBM videos are supported",
        )

    saved_path = None
    session_started = False

    try:
        PLAYBACK_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        saved_path = PLAYBACK_DIR / (
            f"{uuid4().hex}{extension}"
        )

        total_bytes = 0

        with saved_path.open("wb") as destination:
            while True:
                chunk = await file.read(1024 * 1024)

                if not chunk:
                    break

                total_bytes += len(chunk)

                if total_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Video exceeds the 300 MB upload limit",
                    )

                destination.write(chunk)

        if total_bytes == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded video is empty",
            )

        try:
            session = playback_manager.start(
                camera_id=camera.id,
                video_path=saved_path,
                original_filename=original_filename,
            )
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(error),
            ) from error

        session_started = True

        return {
            "message": "Shared playback session started",
            "camera": {
                "id": camera.id,
                "name": camera.name,
                "code": camera.code,
                "room_id": camera.room_id,
            },
            "session": session,
            "note": (
                "Backend video analysis runs in the background. "
                "The session status endpoint reports its current state."
            ),
        }

    except HTTPException:
        if saved_path is not None and not session_started:
            saved_path.unlink(missing_ok=True)
        raise

    except OSError as error:
        if saved_path is not None and not session_started:
            saved_path.unlink(missing_ok=True)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save the playback video",
        ) from error

    except Exception as error:
        if saved_path is not None and not session_started:
            saved_path.unlink(missing_ok=True)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not start the playback session",
        ) from error

    finally:
        await file.close()


# =========================================================
# STOP SHARED VIDEO LOOP
# ADMIN ONLY
# =========================================================

@router.post("/cameras/{camera_id}/stop")
def stop_shared_playback(
    camera_id: int,
    current_user: User = Depends(
        require_permission("cameras.manage")
    ),
    db: Session = Depends(get_db),
):
    ensure_admin(db, current_user)

    camera = get_camera_or_404(
        db,
        camera_id,
    )

    ensure_camera_access(
        db,
        current_user,
        camera,
    )

    try:
        session = playback_manager.stop(camera.id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return {
        "message": "Playback stop requested",
        "camera_id": camera.id,
        "session": session,
    }


# =========================================================
# GET SESSION STATUS
# AUTHORIZED USERS ONLY
# =========================================================

@router.get("/cameras/{camera_id}/status")
def get_shared_playback_status(
    camera_id: int,
    current_user: User = Depends(
        require_permission("cameras.read")
    ),
    db: Session = Depends(get_db),
):
    camera = get_camera_or_404(
        db,
        camera_id,
    )

    ensure_camera_access(
        db,
        current_user,
        camera,
    )

    return {
        "camera": {
            "id": camera.id,
            "name": camera.name,
            "code": camera.code,
            "room_id": camera.room_id,
            "is_active": camera.is_active,
        },
        "session": playback_manager.get_status(
            camera.id
        ),
    }


# =========================================================
# GET SHARED VIDEO
# AUTHORIZED USERS ONLY
# =========================================================

@router.get("/cameras/{camera_id}/video")
def get_shared_playback_video(
    camera_id: int,
    current_user: User = Depends(
        require_permission("cameras.read")
    ),
    db: Session = Depends(get_db),
):
    camera = get_camera_or_404(
        db,
        camera_id,
    )

    ensure_camera_access(
        db,
        current_user,
        camera,
    )

    ensure_camera_active(camera)

    video_path = playback_manager.get_video_path(
        camera.id
    )

    if video_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active playback video is available",
        )

    media_type = (
        "video/webm"
        if video_path.suffix.lower() == ".webm"
        else "video/mp4"
    )

    return FileResponse(
        path=video_path,
        media_type=media_type,
        content_disposition_type="inline",
        headers={
            "Cache-Control": "no-store",
        },
    )
