"""
ocr/preprocessor.py

Предобработка изображения перед распознаванием: устранение шума,
коррекция перспективы (выравнивание документа), повышение контраста
и бинаризация. Использует OpenCV. Каждая операция вынесена
в отдельный статический метод, чтобы шаги можно было переиспользовать
или тестировать по отдельности.

ИЗМЕНЕНИЯ:
- process(): геометрические трансформации (perspective, deskew) теперь
  выполняются ДО контраста/резкости, а не после. Раньше deskew() шёл
  последним и заново интерполировал (cv2.warpAffine, INTER_CUBIC) уже
  заточенное sharpen()-ом изображение, частично гася эффект резкости.
- correct_perspective(): добавлена проверка правдоподобия найденного
  контура (соотношение сторон) — иначе на фото документа на столе/в
  папке-скоросшивателе иногда искажается по контуру фона, а не листа.
- denoise(): уменьшена сила шумоподавления (h=7 -> h=4), чтобы не
  размывать мелкий убористый текст (штрихкоды, колонки сумм).
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Минимальная длинная сторона для хорошего распознавания PaddleOCR.
# Фото с телефонов часто 3000×4000 — там всё ок. А вот сканы
# или уменьшенные копии могут быть мелкими, и OCR теряет символы.
_MIN_LONG_SIDE = 1800

# Допустимый диапазон соотношения сторон для результата correct_perspective().
# Товарные накладные — это, как правило, вертикальный или горизонтальный
# лист A4 (после поворота уже нормализованного в orientation.py), поэтому
# сильно "квадратный" или сильно вытянутый результат обычно означает, что
# найденный контур — это не документ, а что-то на фоне (стол, скоросшиватель,
# тень), и warp нужно отклонить.
_MIN_ASPECT_RATIO = 0.35
_MAX_ASPECT_RATIO = 3.2


class ImagePreprocessor:
    """Набор операций подготовки изображения накладной к распознаванию."""

    @staticmethod
    def load_image(path: str) -> np.ndarray:
        """Загружает изображение с диска. Поддерживает кириллицу в пути."""
        data = np.fromfile(path, dtype=np.uint8)
        image = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Не удалось загрузить изображение: {path}")
        return image

    @staticmethod
    def upscale_if_small(image: np.ndarray, min_long_side: int = _MIN_LONG_SIDE) -> np.ndarray:
        """
        Если изображение мелкое (длинная сторона < min_long_side),
        увеличивает его в пропорциях. PaddleOCR лучше работает
        с разрешением >= 1800px по длинной стороне.
        """
        h, w = image.shape[:2]
        long_side = max(h, w)
        if long_side >= min_long_side:
            return image
        scale = min_long_side / long_side
        new_w, new_h = int(w * scale), int(h * scale)
        upscaled = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        logger.info("Апскейл: %dx%d -> %dx%d (x%.1f)", w, h, new_w, new_h, scale)
        return upscaled

    @staticmethod
    def denoise(image: np.ndarray) -> np.ndarray:
        """Убирает шум, сохраняя резкость краев текста."""
        # h/hColor снижены с 7 до 4: на убористых зонах (штрихкоды, суммы)
        # прежнее значение заметно смазывало тонкие штрихи цифр.
        return cv2.fastNlMeansDenoisingColored(image, None, h=4, hColor=4, templateWindowSize=7, searchWindowSize=21)

    @staticmethod
    def enhance_contrast(image: np.ndarray) -> np.ndarray:
        """Повышает локальный контраст через CLAHE в канале яркости LAB."""
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        l_channel = clahe.apply(l_channel)
        merged = cv2.merge((l_channel, a_channel, b_channel))
        return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)

    @staticmethod
    def adaptive_threshold(image: np.ndarray) -> np.ndarray:
        """
        Адаптивная бинаризация — помогает при неравномерном освещении
        (тень на документе, блик от вспышки). Конвертирует в оттенки серого,
        применяет adaptiveThreshold, затем возвращает 3-канальное изображение.

        Примечание: этот шаг НЕ входит в process() по умолчанию — PaddleOCR
        обычно точнее работает на полутоновом/цветном изображении, чем на
        жёстко бинаризованном. Метод оставлен доступным для ручного вызова
        на документах с сильно неравномерным освещением, где остальных
        шагов недостаточно.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10
        )
        return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

    @staticmethod
    def sharpen(image: np.ndarray) -> np.ndarray:
        """Повышает резкость текста после апскейла или размытия."""
        kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]], dtype=np.float32)
        sharpened = cv2.filter2D(image, -1, kernel)
        return sharpened

    @staticmethod
    def _order_points(pts: np.ndarray) -> np.ndarray:
        """Упорядочивает 4 угловые точки: верх-лево, верх-право, низ-право, низ-лево."""
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        return rect

    @classmethod
    def correct_perspective(cls, image: np.ndarray) -> np.ndarray:
        """
        Пытается найти контур документа и выровнять перспективу.
        Если подходящий контур не найден (или найденный контур даёт
        неправдоподобный результат — см. _MIN_ASPECT_RATIO/_MAX_ASPECT_RATIO),
        возвращает исходное изображение без изменений. Это важно для фото
        документа на столе/в папке-скоросшивателе: там самый крупный
        4-угольный контур на кадре иногда принадлежит не листу, а фону.
        """
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edged = cv2.Canny(blurred, 50, 150)
            edged = cv2.dilate(edged, np.ones((3, 3), np.uint8), iterations=1)

            contours, _ = cv2.findContours(edged, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return image

            contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
            image_area = image.shape[0] * image.shape[1]

            for contour in contours:
                perimeter = cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)

                if len(approx) == 4 and cv2.contourArea(approx) > 0.3 * image_area:
                    pts = approx.reshape(4, 2).astype("float32")
                    rect = cls._order_points(pts)
                    (tl, tr, br, bl) = rect

                    width_a = np.linalg.norm(br - bl)
                    width_b = np.linalg.norm(tr - tl)
                    max_width = max(int(width_a), int(width_b))

                    height_a = np.linalg.norm(tr - br)
                    height_b = np.linalg.norm(tl - bl)
                    max_height = max(int(height_a), int(height_b))

                    if max_width < 100 or max_height < 100:
                        continue

                    aspect_ratio = max_width / max_height
                    if not (_MIN_ASPECT_RATIO <= aspect_ratio <= _MAX_ASPECT_RATIO):
                        # Похоже не на документ (слишком квадратно/вытянуто) —
                        # пробуем следующий по размеру контур вместо этого.
                        logger.debug(
                            "Контур отклонён по соотношению сторон: %.2f (нужно %.2f..%.2f)",
                            aspect_ratio, _MIN_ASPECT_RATIO, _MAX_ASPECT_RATIO,
                        )
                        continue

                    dst = np.array(
                        [[0, 0], [max_width - 1, 0], [max_width - 1, max_height - 1], [0, max_height - 1]],
                        dtype="float32",
                    )
                    matrix = cv2.getPerspectiveTransform(rect, dst)
                    warped = cv2.warpPerspective(image, matrix, (max_width, max_height))
                    return warped

            return image
        except cv2.error as exc:
            logger.warning("Коррекция перспективы не удалась, использую исходное изображение: %s", exc)
            return image

    @staticmethod
    def deskew(image: np.ndarray) -> np.ndarray:
        """Исправляет небольшой наклон текста (в градусах) через анализ момента."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.bitwise_not(gray)
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]

        coords = np.column_stack(np.where(thresh > 0))
        if coords.shape[0] < 10:
            return image

        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        if abs(angle) < 0.5 or abs(angle) > 15:
            # Пропускаем незначительный или подозрительно большой угол
            return image

        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        return rotated

    @classmethod
    def process(cls, image: np.ndarray) -> np.ndarray:
        """
        Полный пайплайн предобработки в правильном порядке.

        Геометрические шаги (perspective, deskew) выполняются ПЕРВЫМИ,
        пока изображение ещё не обработано контрастом/резкостью — иначе
        последующий warp/поворот заново интерполирует уже "заточенные"
        пиксели и частично гасит эффект sharpen().
        """
        result = cls.upscale_if_small(image)
        result = cls.correct_perspective(result)
        result = cls.deskew(result)
        result = cls.denoise(result)
        result = cls.enhance_contrast(result)
        result = cls.sharpen(result)
        return result
