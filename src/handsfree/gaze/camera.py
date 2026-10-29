"""Webcam + MediaPipe Face Landmarker. The camera is only open inside `with`."""

from __future__ import annotations

import time
from pathlib import Path

from .features import Observation, feature_vector


def camera_candidates(setting: int | str, devices: list[str] | None = None) -> list[int | str]:
    """What to try opening, in order. "auto" tries every /dev/video* node:
    the camera is not always video0 (Try Omarchy's is video42), and some
    nodes are metadata-only."""
    if setting not in ("auto", "", None):
        return [setting]
    if devices is None:
        devices = [str(p) for p in Path("/dev").glob("video*")]
    return sorted(devices, key=lambda d: int("".join(c for c in d if c.isdigit()) or 0))


def open_capture(setting: int | str, width: int, height: int, fps: int):
    import cv2

    tried = []
    for candidate in camera_candidates(setting):
        cap = cv2.VideoCapture(candidate, cv2.CAP_V4L2)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            cap.set(cv2.CAP_PROP_FPS, fps)
            if cap.read()[0]:
                return cap
        cap.release()
        tried.append(str(candidate))
    raise RuntimeError(f"no working camera (tried {', '.join(tried) or 'nothing'}); set gaze.camera")


class FaceTracker:
    def __init__(self, model_path: Path, camera: int | str = "auto", width: int = 640, height: int = 480, fps: int = 30):
        self.model_path = model_path
        self.camera = camera
        self.width = width
        self.height = height
        self.fps = fps
        self._cap = None
        self._landmarker = None
        self._last_ts = 0

    def __enter__(self) -> "FaceTracker":
        from mediapipe.tasks import python as mp_tasks
        from mediapipe.tasks.python import vision

        if not self.model_path.exists():
            raise FileNotFoundError(f"face landmarker model missing: {self.model_path} (re-run install.sh)")
        self._cap = open_capture(self.camera, self.width, self.height, self.fps)
        options = vision.FaceLandmarkerOptions(
            base_options=mp_tasks.BaseOptions(model_asset_path=str(self.model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
        )
        self._landmarker = vision.FaceLandmarker.create_from_options(options)
        return self

    def __exit__(self, *exc) -> None:
        if self._landmarker is not None:
            self._landmarker.close()
        if self._cap is not None:
            self._cap.release()
        self._cap = self._landmarker = None

    def read(self) -> Observation | None:
        """Next frame's observation, or None when no face is visible."""
        import cv2
        import mediapipe as mp

        ok, frame = self._cap.read()
        if not ok:
            raise RuntimeError("camera stopped delivering frames")
        now = time.monotonic()
        ts = max(int(now * 1000), self._last_ts + 1)  # MediaPipe needs increasing timestamps
        self._last_ts = ts
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self._landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts)
        if not result.face_landmarks:
            return None
        h, w = frame.shape[:2]
        # Pixel coordinates keep the eye geometry undistorted by the aspect ratio.
        lm = [(p.x * w, p.y * h) for p in result.face_landmarks[0]]
        matrix = result.facial_transformation_matrixes[0].tolist()
        shapes = {c.category_name: c.score for c in result.face_blendshapes[0]}
        blink = min(shapes.get("eyeBlinkLeft", 0.0), shapes.get("eyeBlinkRight", 0.0))
        return Observation(now, feature_vector(lm, matrix), blink)
