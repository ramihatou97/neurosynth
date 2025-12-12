"""
Object Detector (YOLOv8)
========================
Provides object detection for medical images (MRI, CT, Instruments).
Wraps Ultralytics YOLOv8.
"""

import logging
from dataclasses import dataclass
from typing import List

try:
    # YOLO specific imports lazy loaded to avoid heaviness if unused
    from ultralytics import YOLO
except ImportError:
    YOLO = None

logger = logging.getLogger(__name__)


@dataclass
class DetectedObject:
    label: str
    confidence: float
    box: list[float]  # [x1, y1, x2, y2]


class ObjectDetector:
    """
    Wrapper for YOLOv8 to detect objects in medical images.
    """

    def __init__(self, model_path: str = None):
        self.enabled = False

        # Check config flag first
        try:
            from neurosynth.config import get_settings

            settings = get_settings()
            if not settings.enable_object_detection:
                logger.debug("Object detection disabled via config.")
                return
            model_path = model_path or settings.yolo_model
        except ImportError:
            model_path = model_path or "yolov8m.pt"

        if not YOLO:
            logger.warning(
                "YOLO dependencies (ultralytics) missing. Object detection disabled."
            )
            return

        try:
            # "yolov8m.pt" downloads automatically if not found.
            # In production, this should point to a fine-tuned medical model.
            self.model = YOLO(model_path)
            self.enabled = True
            logger.info(f"ObjectDetector initialized with {model_path}")
        except Exception as e:
            logger.error(f"Failed to init YOLO: {e}")
            self.enabled = False

    def detect(self, image_path: str) -> list[DetectedObject]:
        """
        Detect objects in an image.

        Args:
            image_path: Path to image file

        Returns:
            List of DetectedObject
        """
        if not self.enabled:
            return []

        try:
            results = self.model(image_path, verbose=False)
            detected = []

            for r in results:
                boxes = r.boxes
                for box in boxes:
                    # Ultralytics boxes object
                    coords = box.xyxy[0].tolist()
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    label = self.model.names[cls_id]

                    detected.append(
                        DetectedObject(label=label, confidence=conf, box=coords)
                    )

            return detected

        except Exception as e:
            logger.error(f"Detection failed for {image_path}: {e}")
            return []
