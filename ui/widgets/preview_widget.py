"""
ui/widgets/preview_widget.py

Виджет предпросмотра загруженного документа (фото/скан).
Поддерживает масштабирование изображения под размер области
и корректно обрабатывает как исходные файлы, так и numpy-массивы
(после предобработки OpenCV).
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget


class PreviewWidget(QWidget):
    """Показывает превью изображения с автоматическим масштабированием."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._original_pixmap: QPixmap | None = None

        self._image_label = QLabel("Документ не загружен")
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._image_label.setStyleSheet(
            "QLabel { background-color: #f4f5f7; border: 1px dashed #c7cad1; color: #8a8f98; font-size: 14px; }"
        )
        self._image_label.setMinimumSize(320, 320)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self._image_label)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll_area)

    def set_image_from_path(self, path: str) -> None:
        """Загружает и отображает изображение по пути на диске."""
        pixmap = QPixmap(str(Path(path)))
        if pixmap.isNull():
            self.clear()
            return
        self._original_pixmap = pixmap
        self._render_scaled()

    def set_image_from_array(self, image: np.ndarray) -> None:
        """Отображает изображение из numpy-массива (формат BGR, как в OpenCV)."""
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb_image.shape
        bytes_per_line = channels * width
        qimage = QImage(rgb_image.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
        self._original_pixmap = QPixmap.fromImage(qimage.copy())
        self._render_scaled()

    def clear(self) -> None:
        self._original_pixmap = None
        self._image_label.setText("Документ не загружен")
        self._image_label.setPixmap(QPixmap())

    def _render_scaled(self) -> None:
        if self._original_pixmap is None:
            return
        target_size = self._image_label.size()
        scaled = self._original_pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._image_label.setPixmap(scaled)

    def resizeEvent(self, event) -> None:  # noqa: N802 - имя метода задано Qt
        super().resizeEvent(event)
        self._render_scaled()
