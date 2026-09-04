"""
ocr/pipeline.py

Связывает все этапы распознавания в единый пайплайн.
Использует Mistral OCR (облачный): файл отправляется в API, результат — Markdown.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

from models.product import Product
from utils.file_utils import is_pdf_file

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, str], None]


@dataclass
class PipelineResult:
    """Результат обработки одного документа (может содержать несколько страниц)."""

    products: list[Product] = field(default_factory=list)
    page_count: int = 1
    preview_images: list[np.ndarray] = field(default_factory=list)


class OcrPipeline:
    """Полный конвейер: файл на диске -> список объектов Product."""

    def __init__(
        self,
        languages: list[str] | None = None,
        use_gpu: bool = False,
        ocr_engine: str = "mistral",
        mistral_api_key: str = "",
    ) -> None:
        self._ocr_engine = ocr_engine
        self._mistral_api_key = mistral_api_key
        self._languages = languages
        self._use_gpu = use_gpu

        # Ленивая инициализация
        self._preprocessor = None
        self._mistral_client = None

    def _ensure_local_components(self) -> None:
        """Инициализирует компоненты для загрузки изображений (лениво)."""
        if self._preprocessor is not None:
            return
        from ocr.preprocessor import ImagePreprocessor
        self._preprocessor = ImagePreprocessor()

    def _ensure_mistral_client(self):
        """Инициализирует Mistral OCR клиент (лениво)."""
        if self._mistral_client is not None:
            return
        from ocr.mistral_ocr import MistralOcrClient
        self._mistral_client = MistralOcrClient(api_key=self._mistral_api_key)

    def process_file(self, file_path: str, progress_cb: ProgressCallback | None = None) -> PipelineResult:
        """Обрабатывает файл (изображение или PDF) и возвращает распознанные товары."""
        return self._process_with_mistral(file_path, progress_cb)

    # ------------------------------------------------------------------
    # Mistral OCR путь
    # ------------------------------------------------------------------
    def _process_with_mistral(self, file_path: str, progress_cb: ProgressCallback | None = None) -> PipelineResult:
        def report(percent: int, message: str) -> None:
            if progress_cb:
                progress_cb(percent, message)

        self._ensure_mistral_client()
        assert self._mistral_client is not None

        report(5, "Загрузка файла...")
        ocr_result = self._mistral_client.recognize_file(file_path, progress_cb=progress_cb)

        report(85, "Парсинг таблиц товаров...")
        from ocr.mistral_parser import parse_ocr_result
        all_products = parse_ocr_result(ocr_result.full_markdown)

        # Загружаем превью для отображения в UI
        preview_images: list[np.ndarray] = []
        try:
            if is_pdf_file(Path(file_path)):
                from ocr.pdf_converter import PdfConverter
                pdf_converter = PdfConverter()
                preview_images = pdf_converter.pdf_to_images(file_path)
            else:
                self._ensure_local_components()
                assert self._preprocessor is not None
                preview_images = [self._preprocessor.load_image(file_path)]
        except Exception as exc:
            logger.warning("Не удалось загрузить превью: %s", exc)

        report(95, "Формирование итоговой таблицы...")
        result = PipelineResult(
            products=all_products,
            page_count=len(ocr_result.pages),
            preview_images=preview_images,
        )
        report(100, "Готово")
        return result


