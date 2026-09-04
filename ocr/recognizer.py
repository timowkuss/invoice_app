"""
ocr/recognizer.py

Обертка над PaddleOCR (v3.x). Модель загружается один раз (лениво, при
первом использовании) и переиспользуется между документами.

Результат распознавания — список TextBox с координатами и текстом,
которые дальше передаются в table_parser для сборки таблицы.
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

# PaddlePaddle 3.x на некоторых CPU (Windows + Intel oneDNN) падает с
# NotImplementedError вconvertPirAttribute2RuntimeAttribute. Отключение
# oneDNN через переменную окружения решает проблему.
os.environ.setdefault("FLAGS_use_mkldnn", "0")


@dataclass
class TextBox:
    """Один распознанный фрагмент текста с его положением на изображении."""

    text: str
    confidence: float
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @property
    def center_y(self) -> float:
        return (self.y_min + self.y_max) / 2

    @property
    def center_x(self) -> float:
        return (self.x_min + self.x_max) / 2

    @property
    def height(self) -> float:
        return self.y_max - self.y_min


def _boxes_from_result(result_dict: dict) -> list[TextBox]:
    """
    Конвертирует результат PaddleOCR 3.x (словарь) в список TextBox.
    Ключи: rec_texts, rec_scores, rec_polys (или dt_polys).
    """
    boxes: list[TextBox] = []
    texts = result_dict.get("rec_texts", [])
    scores = result_dict.get("rec_scores", [])
    polys = result_dict.get("rec_polys") or result_dict.get("dt_polys", [])

    for text, confidence, poly in zip(texts, scores, polys):
        text = text.strip()
        if not text:
            continue
        xs = [point[0] for point in poly]
        ys = [point[1] for point in poly]
        x_min, y_min = float(min(xs)), float(min(ys))
        x_max, y_max = float(max(xs)), float(max(ys))
        boxes.append(
            TextBox(
                text=text,
                confidence=float(confidence),
                x_min=x_min,
                y_min=y_min,
                x_max=x_max,
                y_max=y_max,
            )
        )
    return boxes


class TextRecognizer:
    """
    Ленивая обертка над PaddleOCR 3.x.

    Модель инициализируется один раз при первом вызове recognize()
    (или recognize_probe()), так как загрузка весов занимает время
    и не должна блокировать запуск приложения.
    """

    _lock = threading.Lock()

    def __init__(
        self,
        languages: list[str] | None = None,
        use_gpu: bool = False,
        second_pass_min_confidence: float = 0.35,
        single_pass_box_threshold: int = 60,
        single_pass_min_avg_confidence: float = 0.40,
    ) -> None:
        self._languages = languages or ["ru", "en"]
        self._use_gpu = use_gpu
        self._second_pass_min_confidence = second_pass_min_confidence
        self._single_pass_box_threshold = single_pass_box_threshold
        self._single_pass_min_avg_confidence = single_pass_min_avg_confidence
        self._engine = None  # инициализируется лениво

    def _ensure_engine(self) -> None:
        if self._engine is not None:
            return
        with self._lock:
            if self._engine is not None:
                return
            lang = self._languages[0] if self._languages else "ru"
            logger.info("Инициализация PaddleOCR (язык=%s, gpu=%s)...", lang, self._use_gpu)
            os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
            from paddleocr import PaddleOCR

            self._engine = PaddleOCR(
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                lang=lang,
            )
            logger.info("PaddleOCR готов к работе")

    def _run_predict(self, image: np.ndarray, **kwargs) -> list[TextBox]:
        result = self._engine.predict(image, **kwargs)
        all_boxes: list[TextBox] = []
        for page_result in result:
            all_boxes.extend(_boxes_from_result(page_result))
        return all_boxes

    def recognize_probe(self, image: np.ndarray) -> list[TextBox]:
        """
        Быстрый однопроходный OCR для служебных проверок
        (определение ориентации в orientation.py).
        """
        self._ensure_engine()
        assert self._engine is not None
        return self._run_predict(
            image,
            text_det_thresh=0.5,
            text_rec_score_thresh=0.5,
        )

    def recognize(self, image: np.ndarray, single_pass: bool = False) -> list[TextBox]:
        """
        Распознает текст на изображении (двойной проход):

        1. Основной проход — стандартные параметры для чётких документов.
        2. Дополнительный проход — более чувствительные параметры для
           мелкого/размытого текста.

        single_pass=True принудительно пропускает второй проход.
        """
        self._ensure_engine()
        assert self._engine is not None

        # --- Проход 1: стандартные параметры ---
        boxes = self._run_predict(image, text_det_thresh=0.3, text_rec_score_thresh=0.3)

        # --- Проход 2: чувствительные параметры для мелкого текста ---
        avg_confidence = sum(b.confidence for b in boxes) / len(boxes) if boxes else 0.0
        skip_second_pass = single_pass or (
            len(boxes) >= self._single_pass_box_threshold
            and avg_confidence >= self._single_pass_min_avg_confidence
        )
        if skip_second_pass:
            logger.info(
                "Распознано фрагментов текста: %d (один проход, средняя уверенность %.2f)",
                len(boxes), avg_confidence,
            )
            return boxes

        seen_positions: set[tuple[float, float]] = set()
        for box in boxes:
            seen_positions.add((round(box.center_x, 0), round(box.center_y, 0)))

        try:
            boxes_2 = self._run_predict(
                image,
                text_det_thresh=0.15,
                text_rec_score_thresh=0.2,
            )

            for box in boxes_2:
                pos_key = (round(box.center_x, 0), round(box.center_y, 0))
                if pos_key not in seen_positions:
                    if box.confidence >= self._second_pass_min_confidence:
                        seen_positions.add(pos_key)
                        boxes.append(box)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Дополнительный проход OCR не удался: %s", exc)

        logger.info("Распознано фрагментов текста: %d (два прохода)", len(boxes))
        return boxes
