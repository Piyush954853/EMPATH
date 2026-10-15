from __future__ import annotations

import time

import cv2

from app.ai.behavior_analyzer import BehaviorAnalyzer
from app.ai.pose_engine import PoseEngine


def main() -> None:
    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        raise RuntimeError(
            "Unable to open webcam. Make sure another application "
            "is not currently using the camera."
        )

    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    analyzer = BehaviorAnalyzer()

    total_frames = 0
    detected_frames = 0

    start_time = time.perf_counter()

    print("==============================================")
    print("EMPATH LIVE AI TEST")
    print("==============================================")
    print("Camera: OPEN")
    print("Pose engine: READY")
    print("Behavior analyzer: READY")
    print()
    print("Press ESC to exit.")
    print()

    with PoseEngine() as pose_engine:
        while True:
            success, frame = camera.read()

            if not success:
                print("Unable to read webcam frame.")
                break

            total_frames += 1

            pose_result = pose_engine.detect(frame)

            if pose_result["pose_detected"]:
                detected_frames += 1

            # ------------------------------------------------
            # TEMPORAL BEHAVIOR ANALYSIS
            # ------------------------------------------------

            previous_posture = analyzer.previous_posture

            behavior = analyzer.analyze(
                pose_result
            )

            # ------------------------------------------------
            # TEMPORAL TRANSITION DIAGNOSTICS
            # ------------------------------------------------

            if (
                behavior.pose_detected
                and behavior.posture != previous_posture
            ):
                knee_angle = 0.0
                vertical_motion = 0.0

                if analyzer.history:
                    current_features = analyzer.history[-1]

                    knee_angle = current_features["knee_angle"]

                    if len(analyzer.history) >= 2:
                        previous_features = analyzer.history[-2]

                        vertical_motion = (
                            current_features["center_y"]
                            - previous_features["center_y"]
                        )

                print()
                print("---------- POSTURE TRANSITION ----------")
                print(
                    f"{previous_posture} -> {behavior.posture}"
                )
                print(
                    f"Body angle:       {behavior.body_angle:.2f}°"
                )
                print(
                    f"Knee angle:       {knee_angle:.2f}°"
                )
                print(
                    f"Movement score:   {behavior.movement_score:.4f}"
                )
                print(
                    f"Vertical motion:  {vertical_motion:.4f}"
                )
                print(
                    f"Confidence:       {behavior.confidence:.2f}"
                )
                print(
                    f"Reason:           {behavior.reason}"
                )
                print("-----------------------------------------")
                print()

            # ------------------------------------------------
            # DISPLAY
            # ------------------------------------------------

            display = frame.copy()

            status_text = (
                "PERSON DETECTED"
                if behavior.pose_detected
                else "NO PERSON"
            )

            cv2.putText(
                display,
                status_text,
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 255, 0)
                if behavior.pose_detected
                else (0, 0, 255),
                2,
                cv2.LINE_AA,
            )

            cv2.putText(
                display,
                f"Posture: {behavior.posture}",
                (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            cv2.putText(
                display,
                f"Movement: {behavior.movement_score:.3f}",
                (20, 115),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            cv2.putText(
                display,
                f"Body angle: {behavior.body_angle:.1f} deg",
                (20, 150),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            cv2.putText(
                display,
                f"Confidence: {behavior.confidence:.2f}",
                (20, 185),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            if behavior.possible_fall:
                cv2.putText(
                    display,
                    "POSSIBLE FALL - VERIFY",
                    (20, 235),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.95,
                    (0, 0, 255),
                    3,
                    cv2.LINE_AA,
                )

            cv2.putText(
                display,
                "ESC = EXIT",
                (20, display.shape[0] - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (220, 220, 220),
                2,
                cv2.LINE_AA,
            )

            cv2.imshow(
                "EMPATH Live AI",
                display,
            )

            key = cv2.waitKey(1) & 0xFF

            if key == 27:
                break

            # ------------------------------------------------
            # PERIODIC CONSOLE SNAPSHOT
            # ------------------------------------------------

            if total_frames % 30 == 0:
                elapsed = time.perf_counter() - start_time

                fps = (
                    total_frames / elapsed
                    if elapsed > 0
                    else 0.0
                )

                print(
                    f"Frames={total_frames:5d} | "
                    f"FPS={fps:5.1f} | "
                    f"Pose={behavior.pose_detected} | "
                    f"Posture={behavior.posture:12s} | "
                    f"Movement={behavior.movement_score:.3f} | "
                    f"Angle={behavior.body_angle:5.1f}° | "
                    f"PossibleFall={behavior.possible_fall}"
                )

    camera.release()
    cv2.destroyAllWindows()

    # ------------------------------------------------
    # FINAL SUMMARY
    # ------------------------------------------------

    elapsed = time.perf_counter() - start_time

    fps = (
        total_frames / elapsed
        if elapsed > 0
        else 0.0
    )

    detection_rate = (
        detected_frames / total_frames
        if total_frames > 0
        else 0.0
    )

    print()
    print("==============================================")
    print("FINAL TEST SUMMARY")
    print("==============================================")
    print(f"Total frames:        {total_frames}")
    print(f"Average FPS:         {fps:.2f}")
    print(f"Pose frames:         {detected_frames}")
    print(
        f"Pose detection rate: {detection_rate * 100:.1f}%"
    )
    print("Live AI pipeline:    OK")
    print("==============================================")


if __name__ == "__main__":
    main()