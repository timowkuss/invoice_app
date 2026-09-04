"""
ocr/table_parser.py

Собирает результат OCR (список TextBox) в таблицу товаров.

Ключевая идея: приложение НЕ полагается на фиксированные координаты
колонок, потому что разные поставщики оформляют накладные по-разному.
Вместо этого используется два независимых механизма:

1. Группировка фрагментов текста в строки — по вертикальному
   перекрытию bounding box'ов (строка = текст на одной горизонтали).
2. Определение колонок — сначала пытаемся найти строку-заголовок
   по ключевым словам ("наименование", "количество", "цена" и т.д.)
   и использовать ее координаты как границы колонок. Если заголовок
   не найден, колонки определяются кластеризацией центров всех
   фрагментов по оси X (гистограммный кластерный анализ), а тип
   каждой колонки определяется по содержимому (числа, штрихкод,
   единицы измерения и т.д.), а не по номеру колонки.

Это позволяет корректно работать с накладными, где порядок и
количество колонок отличается от документа к документу.

ИЗМЕНЕНИЯ:
- _find_header_row(): лимит поиска заголовка поднят с 6 до 25 строк
  (HEADER_SEARCH_LIMIT). На накладных с длинной "шапкой" документа
  (реквизиты сторон, номер/дата документа, ответственный за поставку
  и т.д. — то есть всё, что стоит НАД самой таблицей товаров) реальная
  строка-заголовок таблицы легко оказывается 7-й и позже, и со старым
  лимитом просто не находилась — весь документ уходил в менее точный
  fallback по классификации ячеек.
  Дополнительно теперь обязательно требуется совпадение полей "name"
  И "quantity" (а не любые 3 совпадения) — это единственная пара,
  которая практически всегда есть в реальной шапке товарной таблицы
  и почти никогда не встречается в реквизитах документа выше неё.
- Добавлен _resolve_split_quantity(): некоторые накладные разбивают
  объединённую колонку "Количество" на две подколонки ("подлежит
  отпуску" / "отпущено"). Раньше эти два числа боролись за одну и ту
  же границу поля "quantity" (координаты только одного слова
  "Количество"), из-за чего значение из второй подколонки могло
  утечь в соседнее поле (обычно "price") и испортить цену. Теперь,
  если под заголовком находится такая подстрока, реальные границы
  берутся из подписи "отпущено"/"отгружено" (фактическое количество,
  как и в уже существующей логике для цены со скидкой).
- _row_to_product_by_header(): добавлен порог максимального расстояния
  между фрагментом текста и ближайшей границей поля. Раньше фрагмент
  привязывался к ближайшему полю всегда, даже если находился далеко
  от всех известных колонок (например, обрывок печати/рукописной
  пометки, прошедший через фильтр шума) — теперь такие фрагменты
  просто не попадают ни в одно поле, а не портят случайно ближайшее.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from models.product import Product
from ocr.recognizer import TextBox

logger = logging.getLogger(__name__)


# Ключевые слова заголовков колонок (в нижнем регистре, без знаков препинания).
# ВАЖНО: порядок словаря имеет значение — при поиске заголовка для каждой
# ячейки перебор идет сверху вниз и останавливается на первом совпадении,
# поэтому более специфичные/чаще конфликтующие поля должны идти раньше.
# "index" — служебное поле для колонки "№ по порядку": в модели Product
# такого атрибута нет, поэтому эти данные распознаются, но осознанно
# отбрасываются, а не "утекают" в соседнюю колонку (например, в название).
_HEADER_KEYWORDS: dict[str, tuple[str, ...]] = {
    "index": ("№ по порядку", "№ п/п", "п/п", "по порядку", "№"),
    "name": ("наименование", "название", "товар", "номенклатура", "описание"),
    "barcode": ("штрихкод", "штрих-код", "barcode", "ean"),
    "article": ("артикул", "арт.", "код", "sku"),
    "quantity": ("кол-во", "количество", "кол", "qty"),
    "price": ("цена", "price"),
    # "vat" ловит колонку "Сумма НДС" (без слова "с") ДО общей проверки "total",
    # чтобы она не слилась с колонкой "Сумма с НДС" (реальный итог по строке)
    "vat": ("сумма ндс",),
    "total": ("сумма", "итого", "стоимость", "total", "amount"),
    "unit": ("ед.изм", "единица", "ед", "unit"),
}

# Единицы измерения, часто встречающиеся в накладных — помогают
# распознать соответствующую колонку по содержимому
_UNIT_TOKENS = {
    "шт", "шт.", "кг", "кг.", "г", "л", "мл", "уп", "уп.", "м", "м2", "м3",
    "пач", "пач.", "компл", "компл.", "ящ", "бут", "пар", "рул",
}

_NUMBER_RE = re.compile(r"^-?\d[\d\s]*([.,]\d+)?$")
_BARCODE_RE = re.compile(r"^\d{8,14}$")
_ARTICLE_RE = re.compile(r"^[A-ZА-Я0-9][A-ZА-Я0-9\-/.]{1,14}$", re.IGNORECASE)

# Рукописные пометки (галочки, точки), которые иногда попадают в тот же
# OCR-фрагмент, что и соседняя цифра (например, инспектор ставит "✓"
# прямо перед количеством). Убираем их только по краям строки, рядом
# с цифрой, чтобы не задеть текст названия товара.
_JUNK_SYMBOLS = "✓√✔•·○●"
_LEADING_JUNK_RE = re.compile(rf"^[{_JUNK_SYMBOLS}\s]+(?=\d)")
_TRAILING_JUNK_RE = re.compile(rf"(?<=\d)[{_JUNK_SYMBOLS}\s]+$")

# Типичные ошибки OCR для русского/латинского текста в накладных:
# PaddleOCR часто путает похожие символы, особенно в числах и названиях.
_OCR_CORRECTIONS: dict[str, str] = {
    "O": "0",   # буква O -> ноль (в числовых полях)
    "о": "0",   # кириллическая о -> ноль (в числовых полях)
    "l": "1",   # строчная L -> единица (в числовых полях)
    "I": "1",   # заглавная I -> единица (в числовых полях)
    "С": "C",   # кириллическая С -> латинская C (в артикулах)
    "В": "B",   # кириллическая В -> латинская B (в артикулах)
    "А": "A",   # кириллическая А -> латинская A (в артикулах)
    "Е": "E",   # кириллическая Е -> латинская E (в артикулах)
    "Т": "T",   # кириллическая Т -> латинская T (в артикулах)
    "Н": "H",   # кириллическая Н -> латинская H (в артикулах)
    "К": "K",   # кириллическая К -> латинская K (в артикулах)
    "М": "M",   # кириллическая М -> латинская M (в артикулах)
    "О": "O",   # кириллическая О -> латинская O (в артикулах)
    "Р": "P",   # кириллическая Р -> латинская P (в артикулах)
    "Х": "X",   # кириллическая Х -> латинская X (в артикулах)
}


def _clean_numeric_text(text: str) -> str:
    """Убирает рукописные галочки/точки, приклеившиеся к числовому значению."""
    cleaned = _LEADING_JUNK_RE.sub("", text)
    cleaned = _TRAILING_JUNK_RE.sub("", cleaned)
    return cleaned.strip()


def _fix_ocr_artifacts(text: str, is_numeric: bool = False) -> str:
    """
    Исправляет типичные ошибки OCR:
    - В числовых полях: подменяет похожие буквы на цифры (O->0, l->1, I->1)
    - В артикулах: подменяет кириллицу на латиницу (С->C, В->B, А->A и т.д.)
    """
    if not text:
        return text
    result = text
    if is_numeric:
        # В числах заменяем буквы, похожие на цифры
        for wrong, correct in _OCR_CORRECTIONS.items():
            if wrong.isdigit() or wrong in ("O", "o", "l", "I"):
                result = result.replace(wrong, correct)
    return result


# Поля, для которых применяется очистка от посторонних символов
_NUMERIC_FIELDS = {"quantity", "price", "total", "vat", "list_price"}


def _normalize(text: str) -> str:
    return text.strip().lower().replace("ё", "е")


def _is_number(text: str) -> bool:
    return bool(_NUMBER_RE.match(text.strip()))


def _is_barcode(text: str) -> bool:
    return bool(_BARCODE_RE.match(text.strip()))


def _is_unit(text: str) -> bool:
    return _normalize(text).strip(".") in {u.strip(".") for u in _UNIT_TOKENS}


def _is_article_like(text: str) -> bool:
    stripped = text.strip()
    return bool(_ARTICLE_RE.match(stripped)) and any(ch.isdigit() for ch in stripped)


_JUNK_TOKEN_RE = re.compile(rf"^[{_JUNK_SYMBOLS}\-_.,;:*#]+$")  # рукописные галочки/точки и обрывки пунктуации


def _is_noise(box: "TextBox", min_confidence: float) -> bool:
    """
    Отсекает мусорные фрагменты: очень низкая уверенность OCR или
    "текст", состоящий только из символов (например, случайно
    распознанная рукописная галочка ✓ рядом со строкой таблицы).
    """
    if box.confidence < min_confidence:
        return True
    stripped = box.text.strip()
    if not stripped:
        return True
    if _JUNK_TOKEN_RE.match(stripped):
        return True
    return False


@dataclass
class ParseMeta:
    """Метаданные о качестве разбора, см. TableParser.parse_with_meta()."""

    header_found: bool
    row_count: int


@dataclass
class _Row:
    boxes: list[TextBox]

    @property
    def top(self) -> float:
        return min(b.y_min for b in self.boxes)

    @property
    def bottom(self) -> float:
        return max(b.y_max for b in self.boxes)

    def sorted_boxes(self) -> list[TextBox]:
        return sorted(self.boxes, key=lambda b: b.x_min)


_HAS_LETTER_RE = re.compile(r"[A-Za-zА-Яа-яЁё]")

# Мусорные слова из логотипов/QR-кодов — строки, содержащие только такие
# токены, не являются товарными позициями
_GARBAGE_TOKENS = {
    "halyk", "kaspi", "bank", "qr", "орuаз2", "орuаz2", "орuas2",
    "@halyk", "@kaspi", "nalyk", "kaspl", "bank",
}
# Строка считается мусорной, если доля "плохих" символов
# (не-букв, не-цифр) в названии выше этого порога
_MAX_JUNK_RATIO = 0.50


def _is_garbage_row(product: Product) -> bool:
    """
    Отсекает строки, которые явно не являются товарными позициями:
    мусор из логотипов (@Halyk Kaspi), QR-кодов, случайных обрывков.
    """
    name = product.name.strip().lower()
    if not name:
        return False
    # Проверка по мусорным токенам
    tokens = set(name.split())
    if tokens & _GARBAGE_TOKENS:
        return True
    # Проверка по доле не-буквенных/не-цифровых символов
    if len(name) >= 3:
        junk_count = sum(1 for ch in name if not ch.isalnum() and not ch.isspace())
        if junk_count / len(name) > _MAX_JUNK_RATIO:
            return True
    # Строка из 1-2 символов (кроме артикула/штрихкода) — не товар
    if len(name) <= 2 and not product.article and not product.barcode:
        return True
    return False


def _looks_like_real_product_row(product: Product) -> bool:
    if _is_garbage_row(product):
        return False
    if product.barcode and len(product.barcode.strip()) >= 6:
        return True
    if product.article and len(product.article.strip()) >= 2:
        return True
    name = product.name.strip()
    if len(name) >= 3 and _HAS_LETTER_RE.search(name):
        return True
    return False


# Подписи подколонок под объединённой шапкой "Количество" — см. _resolve_split_quantity.
_ACTUAL_QTY_KEYWORDS = ("отпущено", "отгружено", "выдано", "фактически", "принято")
_PLANNED_QTY_KEYWORDS = ("подлежит", "затребовано", "заказано", "к отпуску", "требуется")

# Признаки того, что строка уже относится к подвалу документа (подписи,
# печать, реквизиты после таблицы), а не к самой таблице товаров.
# Как только такая строка встречена среди data_rows — дальнейшие строки
# не обрабатываются вовсе, а не полагаются только на _looks_like_real_product_row
# (текст из печати/подписи нередко содержит буквы длиной >=3 и проходит
# этот фильтр как "похожий на товар").
_FOOTER_KEYWORDS = (
    "отпуск разрешил", "главный бухгалтер", "бухгалтер", "рассшифровка",
    "расшифровка подписи", "материально ответственн", "запасы получил",
    "по доверенности", "ответственный за перевозку", "ответственный за поставку",
    "должность", "м.п.", "подпись", "транспортно-экспедиционная",
)


def _is_footer_row(row: "_Row") -> bool:
    joined = " ".join(_normalize(box.text) for box in row.boxes)
    return any(keyword in joined for keyword in _FOOTER_KEYWORDS)


class TableParser:
    """Преобразует плоский список TextBox в список объектов Product."""

    # Сколько первых строк страницы просматривать в поисках заголовка
    # таблицы товаров. Раньше было 6 — этого не хватало на бланках с
    # длинной "шапкой" документа (реквизиты сторон, номер/дата и т.п.
    # перед самой таблицей).
    _DEFAULT_HEADER_SEARCH_LIMIT = 25

    def __init__(
        self,
        row_overlap_ratio: float = 0.5,
        min_confidence: float = 0.2,
        header_search_limit: int = _DEFAULT_HEADER_SEARCH_LIMIT,
    ) -> None:
        # Порог вертикального перекрытия для объединения фрагментов в одну строку
        self._row_overlap_ratio = row_overlap_ratio
        # Фрагменты с уверенностью OCR ниже этого порога отбрасываются как шум
        # (понижен с 0.35 до 0.2, чтобы не терять мелкий/размытый текст)
        self._min_confidence = min_confidence
        self._header_search_limit = header_search_limit

    # ------------------------------------------------------------------
    # Группировка в строки
    # ------------------------------------------------------------------
    def _group_into_rows(self, boxes: list[TextBox]) -> list[_Row]:
        if not boxes:
            return []

        sorted_boxes = sorted(boxes, key=lambda b: b.center_y)
        rows: list[_Row] = []

        for box in sorted_boxes:
            placed = False
            for row in rows:
                overlap = min(row.bottom, box.y_max) - max(row.top, box.y_min)
                min_height = min(row.bottom - row.top, box.height) or 1.0
                if overlap > 0 and (overlap / min_height) >= self._row_overlap_ratio:
                    row.boxes.append(box)
                    placed = True
                    break
            if not placed:
                rows.append(_Row(boxes=[box]))

        rows.sort(key=lambda r: r.top)
        return rows

    # ------------------------------------------------------------------
    # Поиск строки-заголовка
    # ------------------------------------------------------------------
    def _find_header_row(self, rows: list[_Row]) -> tuple[int, dict[str, tuple[float, float]]] | None:
        """
        Ищет строку с заголовками колонок среди первых нескольких строк.
        Возвращает индекс строки и границы (x_min, x_max) для каждого
        распознанного типа колонки.

        Ячейки обрабатываются слева направо, и для каждого поля
        сохраняется ПЕРВОЕ (самое левое) совпадение. Это важно для
        документов, где несколько колонок содержат общее ключевое
        слово (например, "Сумма с НДС" и "Сумма НДС" одновременно
        совпадают с ключевым словом "сумма") — без этого правила
        результат зависел бы от случайного порядка бокsов из OCR.
        """
        search_limit = min(len(rows), self._header_search_limit)
        for row_index in range(search_limit):
            row = rows[row_index]
            matches: dict[str, tuple[float, float]] = {}
            for box in row.sorted_boxes():
                normalized = _normalize(box.text)
                for field_name, keywords in _HEADER_KEYWORDS.items():
                    if any(keyword in normalized for keyword in keywords):
                        matches.setdefault(field_name, (box.x_min, box.x_max))
                        break

            self._resolve_discount_price(row, matches)

            # Заголовок считается найденным, только если есть ОБА поля
            # "name" и "quantity" (почти гарантированно есть в реальной
            # шапке товарной таблицы и почти никогда не встречаются вместе
            # в реквизитах документа выше неё) плюс минимум 3 совпадения
            # в целом. "index" не считается содержательной колонкой.
            meaningful_matches = {k: v for k, v in matches.items() if k != "index"}
            if "name" in meaningful_matches and "quantity" in meaningful_matches and len(meaningful_matches) >= 3:
                logger.info("Строка заголовка найдена (индекс %d): %s", row_index, list(matches.keys()))
                return row_index, matches
        return None

    @staticmethod
    def _resolve_discount_price(row: "_Row", matches: dict[str, tuple[float, float]]) -> None:
        """
        Некоторые накладные содержат сразу две колонки цены: базовую
        ("Цена в KZT") и фактическую после скидки ("Цена со скидкой").
        Реальная сумма по строке считается именно от цены со скидкой,
        поэтому она приоритетно занимает поле "price", а базовая цена
        переносится в отдельное неиспользуемое поле "list_price", чтобы
        не смешаться с ней в одной ячейке.
        """
        discount_box = None
        base_price_box = None
        for box in row.sorted_boxes():
            normalized = _normalize(box.text)
            if "скидк" in normalized:
                discount_box = box
            elif "цена" in normalized or "price" in normalized:
                base_price_box = box

        if discount_box is not None:
            if base_price_box is not None:
                matches["list_price"] = (base_price_box.x_min, base_price_box.x_max)
            matches["price"] = (discount_box.x_min, discount_box.x_max)

    @staticmethod
    def _resolve_split_quantity(rows: list[_Row], header_index: int, matches: dict[str, tuple[float, float]]) -> None:
        """
        Некоторые накладные разбивают объединённую шапку "Количество" на
        две подколонки в строке ПОД заголовком: "подлежит отпуску" (план)
        и "отпущено"/"отгружено" (факт). Координаты merged-ячейки
        "Количество" в matches — это координаты одного слова, физически
        не совпадающие ни с одной из подколонок. Из-за этого числа из
        второй подколонки могут "уехать" в соседнее поле (обычно price)
        при сопоставлении по ближайшей границе в _row_to_product_by_header.

        Если такая разбивка обнаружена, границы поля "quantity"
        заменяются на координаты подписи фактического количества —
        по той же логике, что уже применяется в _resolve_discount_price
        для выбора цены со скидкой вместо базовой: для 1С важно
        фактическое количество, а не плановое/заявленное.
        """
        if "quantity" not in matches:
            return
        if header_index + 1 >= len(rows):
            return

        sub_row = rows[header_index + 1]
        actual_box = None
        planned_box = None
        for box in sub_row.sorted_boxes():
            normalized = _normalize(box.text)
            if any(keyword in normalized for keyword in _ACTUAL_QTY_KEYWORDS):
                actual_box = box
            elif any(keyword in normalized for keyword in _PLANNED_QTY_KEYWORDS):
                planned_box = box

        if actual_box is not None and planned_box is not None:
            matches["quantity"] = (actual_box.x_min, actual_box.x_max)
            logger.info(
                "Обнаружена разбивка колонки 'Количество' на план/факт — "
                "для 'quantity' используются координаты подписи фактического количества"
            )

    # ------------------------------------------------------------------
    # Определение колонок без заголовка (кластеризация по X)
    # ------------------------------------------------------------------
    @staticmethod
    def _cluster_columns(rows: list[_Row], n_clusters_hint: int = 7) -> list[tuple[float, float]]:
        """
        Простая кластеризация центров X всех фрагментов на колонки.
        Используется одномерный алгоритм: сортируем центры, режем
        там, где расстояние между соседними точками заметно больше
        среднего (разрыв между колонками).
        """
        centers = sorted(box.center_x for row in rows for box in row.boxes)
        if not centers:
            return []

        gaps = [(centers[i + 1] - centers[i], i) for i in range(len(centers) - 1)]
        if not gaps:
            return [(centers[0] - 1, centers[0] + 1)]

        avg_gap = sum(g for g, _ in gaps) / len(gaps)
        threshold = max(avg_gap * 2.2, 15.0)

        boundaries = [0]
        for gap, idx in gaps:
            if gap > threshold:
                boundaries.append(idx + 1)
        boundaries.append(len(centers))

        clusters: list[tuple[float, float]] = []
        for i in range(len(boundaries) - 1):
            segment = centers[boundaries[i]: boundaries[i + 1]]
            if segment:
                clusters.append((min(segment), max(segment)))
        return clusters

    # ------------------------------------------------------------------
    # Классификация содержимого строки по типу поля (fallback без заголовка)
    # ------------------------------------------------------------------
    @staticmethod
    def _classify_cell(text: str) -> str:
        stripped = text.strip()
        if _is_unit(stripped):
            return "unit"
        if _is_barcode(stripped):
            return "barcode"
        if _is_number(stripped):
            return "number"  # уточняется позже (кол-во/цена/сумма) по позиции
        if _is_article_like(stripped) and len(stripped) <= 16:
            return "article"
        return "name"

    def _row_to_product_by_header(self, row: _Row, header_bounds: dict[str, tuple[float, float]]) -> Product:
        """Сопоставляет фрагменты строки с колонками по ближайшей границе заголовка."""
        product = Product()
        field_values: dict[str, list[str]] = {key: [] for key in header_bounds}

        # Оценка типичной ширины колонки — фрагмент, который дальше от
        # ближайшей известной границы, чем этот порог, ни к какому полю
        # не привязывается (вместо того чтобы искажать случайно ближайшее).
        # Это защищает от мусорных боксов (обрывки печати, штрихи ручки),
        # прошедших через фильтр шума, но физически не попадающих ни
        # в одну из колонок таблицы.
        bound_widths = [x_max - x_min for x_min, x_max in header_bounds.values() if x_max > x_min]
        avg_width = (sum(bound_widths) / len(bound_widths)) if bound_widths else 50.0
        max_distance = max(avg_width * 2.5, 80.0)

        for box in row.sorted_boxes():
            best_field, best_bound = min(
                header_bounds.items(),
                key=lambda item: abs(box.center_x - (item[1][0] + item[1][1]) / 2),
            )
            distance = abs(box.center_x - (best_bound[0] + best_bound[1]) / 2)
            if distance > max_distance:
                continue

            text = box.text
            if best_field in _NUMERIC_FIELDS:
                text = _clean_numeric_text(text)
                text = _fix_ocr_artifacts(text, is_numeric=True)
            if text:
                field_values.setdefault(best_field, []).append(text)

        for field_name, values in field_values.items():
            deduped: list[str] = []
            for value in values:
                if value not in deduped:
                    deduped.append(value)
            joined = " ".join(deduped).strip()
            if hasattr(product, field_name):
                setattr(product, field_name, joined)

        return product

    def _row_to_product_by_classification(self, row: _Row) -> Product:
        """
        Фallback-логика без заголовка: классифицирует каждую ячейку по
        содержимому. Числовые ячейки распределяются по позиции слева
        направо в порядке количество -> цена -> сумма, что соответствует
        подавляющему большинству накладных.
        """
        product = Product()
        name_parts: list[str] = []
        numbers: list[str] = []

        for box in row.sorted_boxes():
            stripped = box.text.strip()
            candidate = _clean_numeric_text(stripped)
            cell_type = self._classify_cell(candidate if _is_number(candidate) else stripped)
            if cell_type == "unit":
                product.unit = stripped
            elif cell_type == "barcode":
                product.barcode = stripped
            elif cell_type == "number":
                candidate = _fix_ocr_artifacts(candidate, is_numeric=True)
                numbers.append(candidate)
            elif cell_type == "article" and not product.article:
                product.article = stripped
            else:
                name_parts.append(stripped)

        product.name = " ".join(name_parts).strip()

        # Распределяем числовые значения: если чисел 3 и более -> кол-во, цена, сумма
        # (сумма обычно самое большое/последнее число в строке)
        if len(numbers) >= 3:
            product.quantity, product.price, product.total = numbers[0], numbers[1], numbers[-1]
        elif len(numbers) == 2:
            product.quantity, product.price = numbers[0], numbers[1]
        elif len(numbers) == 1:
            product.quantity = numbers[0]

        return product

    # ------------------------------------------------------------------
    # Публичный метод
    # ------------------------------------------------------------------
    def parse(self, boxes: list[TextBox]) -> list[Product]:
        """Основной метод: превращает список распознанных фрагментов в товары.

        Обёртка над parse_with_meta() для обратной совместимости —
        отбрасывает метаданные и возвращает только список товаров.
        """
        products, _meta = self.parse_with_meta(boxes)
        return products

    def parse_with_meta(self, boxes: list[TextBox]) -> tuple[list[Product], "ParseMeta"]:
        """
        То же самое, что parse(), но дополнительно возвращает ParseMeta —
        сведения о том, насколько уверенно прошёл разбор (найдена ли шапка
        колонок). Это нужно вызывающему коду (pipeline.py), чтобы отличить
        "нормально распознали по колонкам" от "не нашли шапку и сработал
        слабый резервный метод" — во втором случае имеет смысл попробовать
        перераспознать документ иначе (например, без обрезки кадра),
        а не молча отдавать пользователю мусорный результат.
        """
        clean_boxes = [box for box in boxes if not _is_noise(box, self._min_confidence)]
        rows = self._group_into_rows(clean_boxes)
        if not rows:
            return [], ParseMeta(header_found=False, row_count=0)

        header = self._find_header_row(rows)
        data_rows = rows
        header_bounds: dict[str, tuple[float, float]] | None = None

        if header is not None:
            header_index, header_bounds = header
            self._resolve_split_quantity(rows, header_index, header_bounds)
            data_rows = rows[header_index + 1:]

        products: list[Product] = []
        for row in data_rows:
            if _is_footer_row(row):
                logger.info("Обнаружен подвал документа (подписи/печать) — обработка таблицы остановлена")
                break

            if header_bounds:
                product = self._row_to_product_by_header(row, header_bounds)
            else:
                product = self._row_to_product_by_classification(row)

            if not product.is_empty() and _looks_like_real_product_row(product):
                products.append(product)

        merged = self._merge_multiline_names(products)
        logger.info("Таблица собрана: %d строк товаров", len(merged))
        meta = ParseMeta(header_found=header is not None, row_count=len(merged))
        return merged, meta

    @staticmethod
    def _merge_multiline_names(products: list[Product]) -> list[Product]:
        """
        Если строка содержит только текст названия (без количества, цены,
        суммы, артикула и штрихкода) — это, как правило, перенос названия
        предыдущего товара на новую строку (например, "...осветленный 1л").
        Такой "хвост" присоединяется к названию ПРЕДЫДУЩЕГО уже добавленного
        товара. Если перед ним еще нет ни одного товара, строка сохраняется
        как есть (это может быть единственная позиция в документе).
        """
        merged: list[Product] = []

        for product in products:
            has_data = any([product.quantity, product.price, product.total, product.article, product.barcode])

            if not has_data and product.name and merged:
                merged[-1].name = (merged[-1].name + " " + product.name).strip()
                continue

            merged.append(product)

        return merged
