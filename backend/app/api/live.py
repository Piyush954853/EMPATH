
import cv2
import numpy as np

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.permissions import require_permission
from app.core.database import get_db
from app.models.camera import Camera
from app.models.user import User
from app.services.live_webcam_manager import live_webcam_manager
from app.services.resource_access import (
    can_access_camera,
    is_admin,
)


router = APIRouter(
    prefix="/live",
    tags=["Live Webcam Analysis"],
)

MAX_FRAME_BYTES = 2 * 1024 * 1024


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
            detail="Only administrators can control the live webcam session",
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
        audit=False,
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
# START LIVE WEBCAM — ADMIN ONLY
# =========================================================

@router.post("/cameras/{camera_id}/start")
def start_live_webcam(
    camera_id: int,
    current_user: User = Depends(
        require_permission("cameras.manage")
    ),
    db: Session = Depends(get_db),
):
    ensure_admin(db, current_user)

    camera = get_camera_or_404(db, camera_id)
    ensure_camera_active(camera)
    ensure_camera_access(db, current_user, camera)

    try:
        session = live_webcam_manager.start(
            camera_id=camera.id,
            user_id=current_user.id,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not initialize the webcam analysis engine",
        ) from error

    return {
        "message": "Live webcam analysis session started",
        "camera": {
            "id": camera.id,
            "name": camera.name,
            "code": camera.code,
            "room_id": camera.room_id,
        },
        "session": session,
    }


# =========================================================
# SUBMIT WEBCAM FRAME — ADMIN SESSION ONLY
# =========================================================

@router.post("/cameras/{camera_id}/frame")
def analyze_webcam_frame(
    camera_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(
        require_permission("cameras.manage")
    ),
    db: Session = Depends(get_db),
):
    ensure_admin(db, current_user)

    camera = get_camera_or_404(db, camera_id)
    ensure_camera_active(camera)
    ensure_camera_access(db, current_user, camera)

    try:
        contents = file.file.read(MAX_FRAME_BYTES + 1)

        if not contents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The submitted frame is empty",
            )

        if len(contents) > MAX_FRAME_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="The webcam frame exceeds the 2 MB limit",
            )

        encoded = np.frombuffer(contents, dtype=np.uint8)
        frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)

        if frame is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The submitted file is not a valid image frame",
            )

        try:
            result = live_webcam_manager.process_frame(
                camera_id=camera.id,
                user_id=current_user.id,
                frame=frame,
                jpeg_bytes=contents,
                db=db,
            )
        except PermissionError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(error),
            ) from error
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(error),
            ) from error

        return {
            "camera_id": camera.id,
            "analysis": result,
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webcam frame analysis failed",
        ) from error

    finally:
        file.file.close()


# =========================================================
# GET LIVE SESSION STATUS — AUTHORIZED CAMERA USERS
# =========================================================

@router.get("/cameras/{camera_id}/status")
def get_live_webcam_status(
    camera_id: int,
    current_user: User = Depends(
        require_permission("cameras.read")
    ),
    db: Session = Depends(get_db),
):
    camera = get_camera_or_404(db, camera_id)
    ensure_camera_access(db, current_user, camera)

    return {
        "camera": {
            "id": camera.id,
            "name": camera.name,
            "code": camera.code,
            "room_id": camera.room_id,
            "is_active": camera.is_active,
        },
        "session": live_webcam_manager.status(
            camera_id=camera.id,
        ),
    }


# =========================================================
# GET LATEST WEBCAM SNAPSHOT — AUTHORIZED CAMERA USERS
# =========================================================

@router.get("/cameras/{camera_id}/snapshot")
def get_live_webcam_snapshot(
    camera_id: int,
    current_user: User = Depends(
        require_permission("cameras.read")
    ),
    db: Session = Depends(get_db),
):
    camera = get_camera_or_404(db, camera_id)
    ensure_camera_access(db, current_user, camera)
    ensure_camera_active(camera)

    latest = live_webcam_manager.latest_jpeg(
        camera_id=camera.id,
    )

    if latest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active webcam snapshot is available",
        )

    return Response(
        content=latest,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
        },
    )


# =========================================================
# STOP LIVE WEBCAM — ADMIN ONLY
# =========================================================

@router.post("/cameras/{camera_id}/stop")
def stop_live_webcam(
    camera_id: int,
    current_user: User = Depends(
        require_permission("cameras.manage")
    ),
    db: Session = Depends(get_db),
):
    ensure_admin(db, current_user)

    camera = get_camera_or_404(db, camera_id)
    ensure_camera_access(db, current_user, camera)

    try:
        session = live_webcam_manager.stop(
            camera_id=camera.id,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return {
        "message": "Live webcam analysis stopped",
        "session": session,
    }
