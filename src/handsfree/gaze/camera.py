"""Webcam + MediaPipe Face Landmarker. The camera is only open inside `with`."""

from __future__ import annotations

import time
from pathlib import Path

from .features import Observation, feature_vector


class FaceTracker:
    def __init__(self, model_path: Path, camera: int | str = 0, width: int = 640, height: int = 480, fps: int = 30):
        self.model_path = model_path
        self.camera = camera
        self.width = width
        self.height = height
        self.fps = fps
        self._cap = None
        self._landmarker = None
        self._last_ts = 0

    def __enter__(self) -> "FaceTracker":
        import cv2
        from mediapipe.tasks import python as mp_tasks
        from mediapipe.tasks.python import vision

        if not self.model_path.exists():
            raise FileNotFoundError(f"face landmarker model missing: {self.model_path} (re-run install.sh)")
        self._cap = cv2.VideoCapture(self.camera, cv2.CAP_V4L2)
        if not self._cap.isOpened():
            raise RuntimeError(f"cannot open camera {self.camera!r}")
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, self.fps)
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
