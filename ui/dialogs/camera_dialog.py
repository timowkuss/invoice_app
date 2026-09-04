"""
ui/dialogs/camera_dialog.py

Простое диалоговое окно для съемки накладной с веб-камеры.
Показывает живое видео и позволяет сделать снимок, который
сохраняется во временную папку и возвращается вызывающему коду.
"""

from __future__ import annotations

import logging
from datetime import datetime

import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout

from config.config import TEMP_DIR

logger = logging.getLogger(__name__)


class CameraDialog(QDialog):
    """Диалог захвата фото накладной с камеры устройства."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("📷 Сделать фото накладной")
        self.resize(720, 560)

        self.captured_path: str | None = None

        self._video_label = QLabel("Подключение к камере...")
        self._video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._video_label.setStyleSheet("background-color: #111; color: white;")

        capture_btn = QPushButton("📸 Снимок")
        capture_btn.clicked.connect(self._capture_frame)

        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(capture_btn)
        button_row.addWidget(cancel_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self._video_label, stretch=1)
        layout.addLayout(button_row)

        self._capture: cv2.VideoCapture | None = None
        self._last_frame: np.ndarray | None = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_frame)

        self._init_camera()

    def _init_camera(self) -> None:
        self._capture = cv2.VideoCapture(0)
        if not self._capture.isOpened():
            QMessageBox.warning(self, "Камера недоступна", "Не удалось подключиться к веб-камере.")
            self._video_label.setText("Камера недоступна")
            return
        self._timer.start(30)

    def _update_frame(self) -> None:
        if self._capture is None:
            return
        ok, frame = self._capture.read()
        if not ok:
            return
        self._last_frame = frame
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb_frame.shape
        qimage = QImage(rgb_frame.data, width, height, channels * width, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimage.copy()).scaled(
            self._video_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self._video_label.setPixmap(pixmap)

    def _capture_frame(self) -> None:
        if self._last_frame is None:
            QMessageBox.warning(self, "Нет кадра", "Кадр с камеры еще не получен.")
            return

        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        filename = datetime.now().strftime("photo_%Y%m%d_%H%M%S.jpg")
        output_path = TEMP_DIR / filename

        success, buffer = cv2.imencode(".jpg", self._last_frame)
        if not success:
            QMessageBox.critical(self, "Ошибка", "Не удалось сохранить снимок.")
            return

        buffer.tofile(str(output_path))
        self.captured_path = str(output_path)
        logger.info("Снимок сохранен: %s", output_path)
        self.accept()

    def closeEvent(self, event) -> None:  # noqa: N802 - имя метода задано Qt
        self._release_camera()
        super().closeEvent(event)

    def reject(self) -> None:
        self._release_camera()
        super().reject()

    def _release_camera(self) -> None:
        self._timer.stop()
        if self._capture is not None:
            self._capture.release()
            self._capture = None
