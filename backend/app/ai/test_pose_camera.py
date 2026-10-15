from __future__ import annotations

import cv2

from app.ai.pose_engine import PoseEngine


def main() -> None:
    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        raise RuntimeError("Unable to open the webcam.")

    print("Camera opened.")
    print("Press SPACE to capture a frame.")
    print("Press ESC to exit.")

    with PoseEngine() as engine:
        while True:
            success, frame = camera.read()

            if not success:
                print("Unable to read webcam frame.")
                break

            display = frame.copy()

            cv2.putText(
                display,
                "EMPATH POSE TEST - SPACE = CAPTURE, ESC = EXIT",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            cv2.imshow("EMPATH Pose Test", display)

            key = cv2.waitKey(1) & 0xFF

            if key == 27:
                break

            if key == 32:
                result = engine.detect(frame)

                print()
                print("========== POSE RESULT ==========")
                print("Pose detected:", result["pose_detected"])
                print("Pose count:", result["pose_count"])

                if result["pose_detected"]:
                    first_pose = result["poses"][0]
                    landmarks = first_pose["landmarks"]

                    print("Landmark count:", len(landmarks))

                    for landmark in landmarks[:5]:
                        print(
                            f"#{landmark['index']}: "
                            f"x={landmark['x']:.3f}, "
                            f"y={landmark['y']:.3f}, "
                            f"z={landmark['z']:.3f}"
                        )

                print("=================================")
                print()

    camera.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()