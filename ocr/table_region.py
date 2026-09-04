"""
ocr/table_region.py

Определяет прямоугольную область самой таблицы на изображении накладной,
чтобы OCR распознавал только ее, а не шапку документа (лого Halyk, QR-коды,
реквизиты организации) и не подвал (подписи, печать, расшифровки подписей).

Эти зоны и раньше распознавались PaddleOCR наравне с таблицей: QR-код и лого
превращались в мусорный "текст" вроде "@Halyk Kaspl @R", а печать/подписи —
в мусорные строки внизу списка товаров. table_parser отфильтровывает часть
такого мусора эвристиками (поиск заголовка по name+quantity, keywords подвала
в _is_footer_row), но это защита ПОСЛЕ факта — сама область для OCR не
менялась. Обрезка кадра до таблицы устраняет проблему на уровне источника:
PaddleOCR физически не видит QR-код/подписи, плюс дополнительно ускоряет
распознавание (меньше пикселей для сканирования) и повышает точность
(тот же текст занимает большую долю кадра после кропа => выше эффективное
разрешение на символ).

Метод: находим длинные горизонтальные и вертикальные линии через
морфологические операции (эрозия длинным ядром убирает всё, что не
является линией нужной длины, дилатация восстанавливает саму линию —
стандартный прием OpenCV для выделения табличных сеток), объединяем
их в маску сетки и берем наибольший прямоугольник, который она описывает.

Проверено на реальном фото накладной: детектор находит именно область
от строки заголовков колонок до строки "Итого", исключая шапку с QR-кодами
и подвал с подписями/печатью.

Если уверенная табличная сетка не найдена (например, накладная без видимых
линий) — возвращаем None, и вызывающий код должен использовать исходное
изображение целиком: лучше распознать лишнее, чем случайно обрезать часть
настоящей таблицы.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TableRegion:
    """Прямоугольная область таблицы в координатах исходного изображения."""

    x_min: int
    y_min: int
    x_max: int
    y_max: int

    def crop(self, image: np.ndarray) -> np.ndarray:
        return image[self.y_min:self.y_max, self.x_min:self.x_max]


class TableRegionDetector:
    """Находит область таблицы на изображении по сетке линий (OpenCV)."""

    def __init__(
        self,
        min_area_ratio: float = 0.15,
        max_area_ratio: float = 0.97,
        min_width_ratio: float = 0.4,
        min_height_ratio: float = 0.15,
        padding: int = 8,
        top_padding_ratio: float = 0.08,
    ) -> None:
        self._min_area_ratio = min_area_ratio
        self._max_area_ratio = max_area_ratio
        self._min_width_ratio = min_width_ratio
        self._min_height_ratio = min_height_ratio
        self._padding = padding
        # Дополнительный отступ сверху в % от высоты изображения —
        # гарантирует, что строка-заголовок таблицы не будет обрезана,
        # даже если детектор сетки линий нашёл только тело таблицы
        self._top_padding_ratio = top_padding_ratio

    def detect(self, image: np.ndarray) -> TableRegion | None:
        """Возвращает область таблицы или None, если сетка не найдена уверенно."""
        try:
            h, w = image.shape[:2]
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
            thresh = cv2.adaptiveThreshold(
                ~gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 15, -2
            )

            horiz_size = max(w // 30, 20)
            vert_size = max(h // 30, 20)

            horiz_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (horiz_size, 1))
            horiz = cv2.dilate(cv2.erode(thresh, horiz_kernel), horiz_kernel)

            vert_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, vert_size))
            vert = cv2.dilate(cv2.erode(thresh, vert_kernel), vert_kernel)

            grid = cv2.add(horiz, vert)
            grid = cv2.dilate(grid, np.ones((5, 5), np.uint8), iterations=2)

            contours, _ = cv2.findContours(grid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                logger.info("Табличная сетка не найдена, используется вся страница")
                return None

            image_area = h * w
            candidates: list[tuple[float, int, int, int, int]] = []
            for contour in contours:
                x, y, cw, ch = cv2.boundingRect(contour)
                ratio = (cw * ch) / image_area
                if not (self._min_area_ratio <= ratio <= self._max_area_ratio):
                    continue
                if cw < w * self._min_width_ratio or ch < h * self._min_height_ratio:
                    continue
                candidates.append((ratio, x, y, cw, ch))

            if not candidates:
                logger.info("Табличная сетка не прошла проверку по размеру, используется вся страница")
                return None

            candidates.sort(reverse=True)
            _, x, y, cw, ch = candidates[0]

            top_padding = int(h * self._top_padding_ratio)
            x_min = max(x - self._padding, 0)
            y_min = max(y - top_padding, 0)
            x_max = min(x + cw + self._padding, w)
            y_max = min(y + ch + self._padding, h)

            logger.info(
                "Область таблицы найдена: x=%d..%d y=%d..%d (%.0f%% площади страницы)",
                x_min, x_max, y_min, y_max, (cw * ch) / image_area * 100,
            )
            return TableRegion(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max)
        except cv2.error as exc:
            logger.warning("Не удалось определить область таблицы: %s", exc)
            return None
