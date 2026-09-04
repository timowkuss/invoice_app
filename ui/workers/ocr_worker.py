"""
ui/workers/ocr_worker.py

Выполняет OCR-пайплайн в отдельном потоке (QThread), чтобы главный
интерфейс не зависал во время распознавания. Взаимодействие с UI
происходит только через Qt-сигналы.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QThread, Signal

from models.product import Product
from ocr.pipeline import OcrPipeline

logger = logging.getLogger(__name__)


class OcrWorker(QThread):
    """Фоновый поток обработки одного файла накладной."""

    progress_changed = Signal(int, str)
    finished_ok = Signal(list)  # list[Product]
    finished_error = Signal(str)

    def __init__(
        self,
        file_path: str,
        languages: list[str],
        use_gpu: bool,
        ocr_engine: str = "mistral",
        mistral_api_key: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._file_path = file_path
        self._languages = languages
        self._use_gpu = use_gpu
        self._ocr_engine = ocr_engine
        self._mistral_api_key = mistral_api_key

    def run(self) -> None:
        try:
            pipeline = OcrPipeline(
                languages=self._languages,
                use_gpu=self._use_gpu,
                ocr_engine=self._ocr_engine,
                mistral_api_key=self._mistral_api_key,
            )
            result = pipeline.process_file(
                self._file_path,
                progress_cb=lambda percent, message: self.progress_changed.emit(percent, message),
            )
            self.finished_ok.emit(result.products)
        except Exception as exc:
            logger.exception("Ошибка в потоке OCR: %s", exc)
            self.finished_error.emit(str(exc))
