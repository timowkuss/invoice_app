"""
ocr/mistral_parser.py

Парсит результат Mistral OCR (Markdown с HTML-таблицами) в список Product.

Mistral OCR с table_format="html" возвращает таблицы в формате HTML,
что позволяет точно определить границы колонок и содержимое ячеек.
"""

from __future__ import annotations

import logging
import re
from html.parser import HTMLParser

from models.product import Product

logger = logging.getLogger(__name__)

# Ключевые слова заголовков колонок (в нижнем регистре)
_HEADER_KEYWORDS: dict[str, tuple[str, ...]] = {
    "name": ("наименование", "название", "товар", "номенклатура", "описание",
             "характеристик"),
    "article": ("артикул", "арт.", "код", "sku", "номер"),
    "barcode": ("штрихкод", "штрих-код", "barcode", "ean"),
    "quantity": ("кол-во", "отпущено", "отгружено", "подлежит отпуску",
                 "количество", "кол-л", "кол.", "qty"),
    "price": ("цена", "price"),
    "discount_price": ("скидк", "со скидкой", "discount"),
    "total": ("сумма", "итого", "стоимость", "total", "amount"),
    "unit": ("ед.изм", "единица измерения", "ед.", "ед ", "unit"),
    "vat": ("ндс", "vat"),
}


def _classify_column(header: str) -> str | None:
    """Определяет тип колонки по заголовку."""
    header_lower = header.lower().strip()
    # Сначала ищем более специфичные совпадения
    for col_type in ("discount_price", "total", "vat", "unit", "quantity",
                     "barcode", "name", "price", "article"):
        keywords = _HEADER_KEYWORDS[col_type]
        for kw in keywords:
            if kw in header_lower:
                return col_type
    return None


_NUMBER_RE = re.compile(r"^-?\d[\d\s]*([.,]\d+)?$")


class _HtmlTableParser(HTMLParser):
    """Простой HTML-парсер для извлечения таблицы."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._current_table: list[list[str]] = []
        self._current_row: list[str] = []
        self._current_cell: list[str] = []
        self._in_table = False
        self._in_row = False
        self._in_cell = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "table":
            self._in_table = True
            self._current_table = []
        elif tag == "tr" and self._in_table:
            self._in_row = True
            self._current_row = []
        elif tag in ("td", "th") and self._in_row:
            self._in_cell = True
            self._current_cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "table":
            self._in_table = False
            if self._current_table:
                self.tables.append(self._current_table)
            self._current_table = []
        elif tag == "tr" and self._in_row:
            self._in_row = False
            if self._current_row:
                self._current_table.append(self._current_row)
            self._current_row = []
        elif tag in ("td", "th") and self._in_cell:
            self._in_cell = False
            self._current_row.append(" ".join(self._current_cell).strip())
            self._current_cell = []

    def handle_data(self, data) -> None:
        if self._in_cell:
            self._current_cell.append(data.strip())


def _is_number(text: str) -> bool:
    normalized = text.replace(" ", "").replace(",", ".")
    return bool(_NUMBER_RE.match(normalized))


def _parse_products_from_table(table: list[list[str]]) -> list[Product]:
    """Парсит одну HTML-таблицу в список Product."""
    if len(table) < 2:
        return []

    # Ищем строку-заголовок (может быть multi-row)
    header_row_idx = -1
    column_map: dict[int, str] = {}

    for row_idx, row in enumerate(table[:30]):
        found_cols = {}
        for col_idx, cell in enumerate(row):
            col_type = _classify_column(cell)
            if col_type and col_idx not in found_cols:
                found_cols[col_idx] = col_type
        # Объединяем с предыдущими строками (multi-row заголовки)
        merged = dict(column_map)
        merged.update(found_cols)
        values = set(merged.values())
        # Проверяем name + (quantity или barcode)
        if "name" in values and ("quantity" in values or "barcode" in values):
            header_row_idx = row_idx
            column_map = merged
            break

    if header_row_idx < 0:
        # Fallback: классифицируем первую строку как заголовок
        for col_idx, cell in enumerate(table[0]):
            col_type = _classify_column(cell)
            if col_type:
                column_map[col_idx] = col_type
        if not column_map:
            return []
        header_row_idx = 0

    products: list[Product] = []
    for row in table[header_row_idx + 1:]:
        if not row or all(not cell.strip() for cell in row):
            continue

        # Пропускаем строку-нумерацию (1 | 2 | 3 | 4 | ...)
        if len(row) >= 3 and all(re.match(r"^\d+$", cell.strip()) for cell in row[:3]):
            continue

        # Пропускаем строку "Итого"
        if any("итого" in cell.lower() for cell in row):
            continue

        product = Product()
        for col_idx, col_type in column_map.items():
            if col_idx >= len(row):
                continue
            value = row[col_idx].strip()
            if not value:
                continue
            # Убираем галочки из значений
            value = value.replace("☑", "").replace("☐", "").strip()
            if col_type == "name":
                product.name = value
            elif col_type == "article":
                product.article = value
            elif col_type == "barcode":
                product.barcode = value
            elif col_type == "quantity":
                product.quantity = value
            elif col_type == "discount_price":
                product.price = value
            elif col_type == "price":
                # Если price ещё не заполнена — записываем, иначе пропускаем
                if not product.price:
                    product.price = value
            elif col_type == "total":
                product.total = value
            elif col_type == "unit":
                product.unit = value
            elif col_type == "vat":
                pass  # НДС не сохраняем в Product

        if product.name and not product.is_empty():
            products.append(product)

    return products


def _parse_products_from_markdown(markdown: str) -> list[Product]:
    """
    Парсит Markdown-таблицу (pipe-separated) в список Product.
    Ищет таблицу с наибольшим числом колонок (товарная таблица).
    """
    lines = markdown.strip().split("\n")
    all_tables: list[list[list[str]]] = []
    current_table: list[list[str]] = []

    for line in lines:
        line = line.strip()
        if not line.startswith("|"):
            if current_table:
                all_tables.append(current_table)
                current_table = []
            continue
        cells = [c.strip() for c in line.split("|")]
        cells = [c for i, c in enumerate(cells) if not (i == 0 or i == len(cells) - 1)]
        if all(re.match(r"^[-:]+$", c) for c in cells if c):
            continue
        current_table.append(cells)

    if current_table:
        all_tables.append(current_table)

    if not all_tables:
        return []

    # Берём таблицу с наибольшим числом колонок (товарная)
    best_table = max(all_tables, key=lambda t: max(len(r) for r in t) if t else 0)
    if len(best_table) < 2:
        return []

    return _parse_products_from_table(best_table)


def parse_ocr_result(markdown: str) -> list[Product]:
    """
    Парсит результат Mistral OCR (Markdown) в список Product.
    Сначала пытается найти HTML-таблицы, затем Markdown-таблицы.
    """
    products: list[Product] = []

    # 1. Ищем HTML-таблицы
    html_parser = _HtmlTableParser()
    html_parser.feed(markdown)
    for table in html_parser.tables:
        products.extend(_parse_products_from_table(table))

    if products:
        logger.info("Извлечено %d товаров из HTML-таблиц", len(products))
        return products

    # 2. Fallback: Markdown pipe-таблицы
    products = _parse_products_from_markdown(markdown)
    if products:
        logger.info("Извлечено %d товаров из Markdown-таблиц", len(products))
        return products

    # 3. Пытаемся найти товары по паттернам в тексте
    logger.warning("Таблицы не найдены, попытка извлечения по паттернам")
    return _extract_products_by_patterns(markdown)


def _extract_products_by_patterns(text: str) -> list[Product]:
    """
    Эвристический парсинг: ищет строки вида
    'Название  Артикул  Кол-во  Цена  Сумма' в тексте.
    """
    products: list[Product] = []
    lines = text.split("\n")

    for line in lines:
        line = line.strip()
        if not line or len(line) < 5:
            continue

        # Пытаемся разделить по 2+ пробелам или табуляции
        parts = re.split(r"\s{2,}|\t", line)
        if len(parts) < 3:
            continue

        numbers = [p for p in parts if _is_number(p)]
        if len(numbers) < 2:
            continue

        text_parts = [p for p in parts if not _is_number(p)]
        if not text_parts:
            continue

        product = Product(
            name=text_parts[0],
            quantity=numbers[0] if len(numbers) > 0 else "",
            price=numbers[1] if len(numbers) > 1 else "",
            total=numbers[2] if len(numbers) > 2 else "",
        )
        if len(text_parts) > 1:
            product.article = text_parts[1]
        if len(text_parts) > 2:
            product.unit = text_parts[2]

        products.append(product)

    return products
