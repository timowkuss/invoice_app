"""
ocr/pdf_converter.py

Конвертация страниц PDF-файла в изображения (numpy массивы),
пригодные для дальнейшей обработки тем же пайплайном, что и фото.
Используется PyMuPDF (fitz) — не требует внешних бинарников,
таких как poppler, что важно для standalone Windows-приложения.
"""

from __future__ import annotations

import logging

import fitz  # PyMuPDF
import numpy as np

logger = logging.getLogger(__name__)


class PdfConverter:
    """Конвертирует страницы PDF в изображения OpenCV (BGR numpy array)."""

    def __init__(self, dpi: int = 300) -> None:
        self._dpi = dpi

    def pdf_to_images(self, pdf_path: str) -> list[np.ndarray]:
        """Возвращает список изображений (по одному на страницу)."""
        images: list[np.ndarray] = []
        try:
            zoom = self._dpi / 72.0
            matrix = fitz.Matrix(zoom, zoom)
            with fitz.open(pdf_path) as document:
                for page_index in range(document.page_count):
                    page = document.load_page(page_index)
                    pixmap = page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB)
                    image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                        pixmap.height, pixmap.width, pixmap.n
                    )
                    # RGB -> BGR для совместимости с OpenCV
                    image_bgr = image[:, :, ::-1].copy()
                    images.append(image_bgr)
            logger.info("PDF %s сконвертирован, страниц: %d", pdf_path, len(images))
        except Exception as exc:  # noqa: BLE001 - конвертация PDF может падать по многим причинам
            logger.error("Ошибка конвертации PDF %s: %s", pdf_path, exc)
            raise
        return images
