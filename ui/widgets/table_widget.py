"""
ui/widgets/table_widget.py

Редактируемая таблица товаров. Позволяет пользователю проверить
результат OCR: изменить ячейки, удалить или добавить строки,
найти товар по названию/артикулу.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config.config import TABLE_COLUMNS
from models.product import Product


class ProductTableWidget(QWidget):
    """Таблица товаров с возможностью редактирования и поиска."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("🔍 Поиск товара по названию или артикулу...")
        self._search_box.textChanged.connect(self._on_search_changed)

        self._table = QTableWidget(0, len(TABLE_COLUMNS))
        self._table.setHorizontalHeaderLabels(list(TABLE_COLUMNS))
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, len(TABLE_COLUMNS)):
            self._table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)

        add_row_btn = QPushButton("➕ Добавить строку")
        add_row_btn.clicked.connect(self.add_empty_row)

        remove_row_btn = QPushButton("🗑 Удалить строку")
        remove_row_btn.clicked.connect(self._remove_selected_rows)

        toolbar = QHBoxLayout()
        toolbar.addWidget(self._search_box, stretch=1)
        toolbar.addWidget(add_row_btn)
        toolbar.addWidget(remove_row_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(toolbar)
        layout.addWidget(self._table)

    # ------------------------------------------------------------------
    # Заполнение / чтение данных
    # ------------------------------------------------------------------
    def load_products(self, products: list[Product]) -> None:
        self._table.setRowCount(0)
        for product in products:
            self._append_row(product)

    def get_products(self) -> list[Product]:
        products: list[Product] = []
        for row in range(self._table.rowCount()):
            values = []
            for col in range(len(TABLE_COLUMNS)):
                item = self._table.item(row, col)
                values.append(item.text() if item else "")
            product = Product.from_row(values)
            if not product.is_empty():
                products.append(product)
        return products

    def clear(self) -> None:
        self._table.setRowCount(0)
        self._search_box.clear()

    def add_empty_row(self) -> None:
        self._append_row(Product())

    def row_count(self) -> int:
        return self._table.rowCount()

    # ------------------------------------------------------------------
    # Внутренние методы
    # ------------------------------------------------------------------
    def _append_row(self, product: Product) -> None:
        row_index = self._table.rowCount()
        self._table.insertRow(row_index)
        for col, value in enumerate(product.to_row()):
            item = QTableWidgetItem(value)
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft if col == 0 else Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row_index, col, item)

    def _remove_selected_rows(self) -> None:
        selected_rows = sorted({index.row() for index in self._table.selectedIndexes()}, reverse=True)
        for row in selected_rows:
            self._table.removeRow(row)

    def _on_search_changed(self, text: str) -> None:
        query = text.strip().lower()
        for row in range(self._table.rowCount()):
            name_item = self._table.item(row, 0)
            article_item = self._table.item(row, 1)
            name_text = name_item.text().lower() if name_item else ""
            article_text = article_item.text().lower() if article_item else ""
            matches = query in name_text or query in article_text
            self._table.setRowHidden(row, bool(query) and not matches)
