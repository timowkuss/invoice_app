"""
ocr/orientation.py

Автоматическое определение и исправление ориентации фото накладной.

Очень частый случай в реальной работе: человек фотографирует документ
телефоном "как удобно" — камера повернута на 90°/180°/270° относительно
текста. OpenCV-выравнивание (deskew) в preprocessor.py исправляет только
небольшой наклон (до ~15°) и не предназначено для поворотов на прямой
угол — такой поворот внешне похож не на "наклон", а на совершенно другую
геометрию страницы.

Идея: у нас уже есть готовый OCR-движок (PaddleOCR). Правильная ориентация —
та, при которой распознанный текст осмысленный, а не "мусор". Поэтому мы
прогоняем уменьшенную копию изображения через OCR во всех 4 поворотах
и выбираем тот, где суммарная уверенность распознавания выше всего:
для перевернутого/повернутого текста PaddleOCR либо не находит фрагменты
вообще, либо распознает их с очень низкой уверенностью.

ИЗМЕНЕНИЯ:
- detect_rotation() теперь использует recognizer.recognize_probe() —
  лёгкий однопроходный OCR — вместо полного recognize() (два прохода).
   Раньше проверка ориентации стоила множественных тяжёлых проходов
   PaddleOCR ДО начала реальной обработки документа.
- Перед пробным OCR к уменьшенной копии применяется быстрое выравнивание
  контраста (эквализация гистограммы). Сырое фото с телефона (тени,
  неравномерный свет) может давать одинаково низкую уверенность OCR
  во всех 4 поворотах — тогда выбор угла становится, по сути, случайным.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

from ocr.recognizer import TextRecognizer

logger = logging.getLogger(__name__)

# Уменьшаем изображение для быстрой 4-кратной проверки ориентации —
# для самой проверки высокое разрешение не нужно, важна только скорость.
_PROBE_MAX_DIMENSION = 900

_ROTATIONS: tuple[tuple[int, int | None], ...] = (
    (0, None),
    (90, cv2.ROTATE_90_CLOCKWISE),
    (180, cv2.ROTATE_180),
    (270, cv2.ROTATE_90_COUNTERCLOCKWISE),
)


class OrientationCorrector:
    """Определяет и исправляет поворот изображения на кратный 90° угол."""

    def __init__(self, recognizer: TextRecognizer) -> None:
        self._recognizer = recognizer

    @staticmethod
    def _resize_for_probe(image: np.ndarray) -> np.ndarray:
        height, width = image.shape[:2]
        longest_side = max(height, width)
        if longest_side <= _PROBE_MAX_DIMENSION:
            return image
        scale = _PROBE_MAX_DIMENSION / longest_side
        return cv2.resize(image, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)

    @staticmethod
    def _enhance_for_probe(image: np.ndarray) -> np.ndarray:
        """
        Быстрое повышение контраста перед пробным OCR. Это не замена
        полному preprocessor.py (он для этого слишком дорогой и здесь
        не нужен — задача только сравнить 4 поворота между собой), а
        лёгкая эквализация гистограммы, чтобы тёмное/неравномерно
        освещённое фото не давало одинаково низкую уверенность OCR
        во всех поворотах сразу.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        equalized = cv2.equalizeHist(gray)
        return cv2.cvtColor(equalized, cv2.COLOR_GRAY2BGR)

    @staticmethod
    def _rotate(image: np.ndarray, rotate_code: int | None) -> np.ndarray:
        if rotate_code is None:
            return image
        return cv2.rotate(image, rotate_code)

    def detect_rotation(self, image: np.ndarray) -> int:
        """
        Пробует все 4 поворота на уменьшенной копии изображения и
        возвращает угол (0/90/180/270), при котором OCR увереннее
        всего распознал текст.
        """
        probe_image = self._enhance_for_probe(self._resize_for_probe(image))

        best_angle = 0
        best_score = -1.0
        scores: dict[int, float] = {}

        for angle, rotate_code in _ROTATIONS:
            rotated = self._rotate(probe_image, rotate_code)
            try:
                boxes = self._recognizer.recognize_probe(rotated)
            except Exception as exc:  # noqa: BLE001 - проверка ориентации не должна ронять весь пайплайн
                logger.warning("Ошибка OCR при проверке ориентации %d°: %s", angle, exc)
                boxes = []

            # Суммарная уверенность распознанных фрагментов — чем осмысленнее
            # текст в данной ориентации, тем выше и увереннее распознавание.
            score = sum(box.confidence for box in boxes)
            scores[angle] = score

            if score > best_score:
                best_score = score
                best_angle = angle

        logger.info("Оценка ориентации по углам: %s -> выбрано %d°", scores, best_angle)
        return best_angle

    def correct(self, image: np.ndarray) -> tuple[np.ndarray, int]:
        """Возвращает изображение, повернутое в правильную ориентацию, и примененный угол."""
        angle = self.detect_rotation(image)
        rotate_code = {0: None, 90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}[
            angle
        ]
        if rotate_code is None:
            return image, 0
        return self._rotate(image, rotate_code), angle
