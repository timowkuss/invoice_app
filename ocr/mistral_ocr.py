"""
ocr/mistral_ocr.py

Обёртка над Mistral OCR API. Отправляет PDF/изображения в облако
и получает структурированный текст (Markdown) с распознанным содержимым.

Mistral OCR самостоятельно обрабатывает:
- определение ориентации страницы,
- выравнивание наклонных документов,
- детекцию таблиц,
- распознавание текста, формул, изображений.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class OcrPageResult:
    """Результат OCR для одной страницы документа."""

    page_index: int
    markdown: str


@dataclass
class OcrDocumentResult:
    """Результат OCR для всего документа."""

    pages: list[OcrPageResult]

    @property
    def full_markdown(self) -> str:
        """Объединённый Markdown всех страниц."""
        return "\n\n---\n\n".join(p.markdown for p in self.pages)


class MistralOcrClient:
    """
    Ленивая обёртка над Mistral OCR API.
    Клиент создаётся один раз и переиспользуется.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = None

    def _ensure_client(self) -> None:
        if self._client is not None:
            return
        from mistralai.client import Mistral
        self._client = Mistral(api_key=self._api_key)
        logger.info("Mistral OCR клиент инициализирован")

    def _encode_image(self, image_path: str) -> str:
        """Кодирует локальный файл изображения в base64 data URI."""
        path = Path(image_path)
        suffix = path.suffix.lower().lstrip(".")
        mime_map = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "bmp": "bmp", "tiff": "tiff", "tif": "tiff"}
        mime_suffix = mime_map.get(suffix, "png")
        data = path.read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:image/{mime_suffix};base64,{b64}"

    def _encode_pdf(self, pdf_path: str) -> str:
        """Кодирует локальный PDF в base64 data URI."""
        data = Path(pdf_path).read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:application/pdf;base64,{b64}"

    def recognize_file(self, file_path: str, progress_cb=None) -> OcrDocumentResult:
        """
        Отправляет файл (PDF или изображение) в Mistral OCR и
        возвращает результат с Markdown для каждой страницы.
        """
        self._ensure_client()
        assert self._client is not None

        path = Path(file_path)
        suffix = path.suffix.lower()

        if progress_cb:
            progress_cb(10, "Отправка файла в Mistral OCR...")

        is_pdf = suffix == ".pdf"
        if is_pdf:
            document = {"type": "document_url", "document_url": self._encode_pdf(file_path)}
        else:
            document = {"type": "image_url", "image_url": self._encode_image(file_path)}

        if progress_cb:
            progress_cb(30, "Распознавание документа...")

        logger.info("Отправка файла %s в Mistral OCR", path.name)
        ocr_response = self._client.ocr.process(
            model="mistral-ocr-latest",
            document=document,
        )

        if progress_cb:
            progress_cb(80, "Обработка результатов...")

        pages = []
        for i, page in enumerate(ocr_response.pages):
            pages.append(OcrPageResult(page_index=i, markdown=page.markdown))
            logger.debug("Страница %d: %d символов Markdown", i, len(page.markdown))

        logger.info("Mistral OCR: распознано %d страниц", len(pages))
        return OcrDocumentResult(pages=pages)
