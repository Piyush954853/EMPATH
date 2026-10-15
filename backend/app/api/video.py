
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.camera import Camera
from app.models.user import User
from app.ai.video_analyzer import VideoAnalyzer
from app.ai.event_bridge import AIEventBridge
from app.services.resource_access import can_access_camera


router = APIRouter(
    prefix="/video",
    tags=["Video Analysis"],
)


ALLOWED_EXTENSIONS = {
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
    ".webm",
}


@router.post("/analyze")
async def analyze_video(
    file: UploadFile = File(...),
    camera_id: int | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Analyze an uploaded video and optionally associate its
    generated events and alerts with a registered camera.

    Existing uploads without camera_id remain supported.
    Camera-linked uploads require camera access permission.

    AI-generated visual safety indicators require staff review.
    """

    original_name = file.filename or "uploaded_video"
    extension = Path(original_name).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unsupported video format. "
                "Use MP4, AVI, MOV, MKV, or WEBM."
            ),
        )

    # ------------------------------------------------------------
    # 1. Validate the requested camera and its access permissions
    # ------------------------------------------------------------

    camera: Camera | None = None

    if camera_id is not None:
        camera = db.get(Camera, camera_id)

        if camera is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Camera not found",
            )

        if not camera.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot analyze a video for an inactive camera",
            )

        if not can_access_camera(
            db,
            current_user,
            camera.id,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Camera access denied",
            )

    temp_path: Path | None = None

    try:
        # --------------------------------------------------------
        # 2. Save the uploaded video temporarily
        # --------------------------------------------------------

        with tempfile.NamedTemporaryFile(
            suffix=extension,
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)

            while True:
                chunk = await file.read(1024 * 1024)

                if not chunk:
                    break

                temp_file.write(chunk)

        # --------------------------------------------------------
        # 3. Run the existing video analyzer
        # --------------------------------------------------------

        analyzer = VideoAnalyzer(
            sample_every_n_frames=3,
        )

        result = analyzer.analyze(temp_path)

        result["video"]["original_filename"] = original_name

        # --------------------------------------------------------
        # 4. Associate the result with the selected camera
        # --------------------------------------------------------

        result["camera_association"] = {
            "linked": camera is not None,
            "camera_id": camera.id if camera else None,
            "camera_name": camera.name if camera else None,
            "camera_code": camera.code if camera else None,
            "room_id": camera.room_id if camera else None,
            "message": (
                "Video analysis is linked to the selected camera."
                if camera
                else (
                    "No camera was selected. "
                    "Events from this upload will not be associated "
                    "with a specific camera."
                )
            ),
        }

        # --------------------------------------------------------
        # 5. Process frame results through the existing event bridge
        # --------------------------------------------------------

        bridge = AIEventBridge(
            cooldown_seconds=10.0,
        )

        created_alerts = []

        for frame_result in result.get("results", []):
            if not isinstance(frame_result, dict):
                continue

            # Keep compatibility with the current bridge interface.
            behavior = SimpleNamespace(
                possible_fall=bool(
                    frame_result.get("possible_fall", False)
                ),
                posture=frame_result.get(
                    "posture",
                    "UNKNOWN",
                ),
                movement_score=frame_result.get(
                    "movement_score",
                    0.0,
                ),
                body_angle=frame_result.get(
                    "body_angle",
                    0.0,
                ),
                confidence=frame_result.get(
                    "confidence",
                    0.0,
                ),
                reason=frame_result.get(
                    "reason",
                    "Possible visual safety event requires review.",
                ),
            )

            # Process every analyzed frame so edge detection can
            # track transitions into and out of a possible event.
            bridge_result = bridge.process(
                db,
                behavior,
                camera_id=camera.id if camera else None,
                patient_id=None,
                extra_metadata={
                    "analysis_mode": "uploaded_video",
                    "video_filename": original_name,
                    "uploaded_by_user_id": current_user.id,
                    "camera_id": camera.id if camera else None,
                    "camera_code": camera.code if camera else None,
                    "room_id": camera.room_id if camera else None,
                    "frame_number": frame_result.get(
                        "frame_number"
                    ),
                    "timestamp_seconds": frame_result.get(
                        "timestamp_seconds"
                    ),
                },
            )

            if bridge_result:
                event = bridge_result["event"]
                alert = bridge_result["alert"]

                created_alerts.append(
                    {
                        "frame_number": frame_result.get(
                            "frame_number"
                        ),
                        "timestamp_seconds": frame_result.get(
                            "timestamp_seconds"
                        ),
                        "camera_id": camera.id if camera else None,
                        "event_id": getattr(
                            event,
                            "id",
                            None,
                        ),
                        "alert_id": getattr(
                            alert,
                            "id",
                            None,
                        ),
                    }
                )

        # --------------------------------------------------------
        # 6. Return all existing analysis fields plus integration
        #    information. Do not remove existing response fields.
        # --------------------------------------------------------

        result["event_alerts"] = {
            "created_count": len(created_alerts),
            "items": created_alerts,
            "message": (
                "Visual safety indicators are experimental "
                "and require staff verification."
            ),
        }

        return result

    except HTTPException:
        db.rollback()
        raise

    except FileNotFoundError as error:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    except RuntimeError as error:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    except Exception as error:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Video analysis failed: {error}",
        ) from error

    finally:
        await file.close()

        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
