"""
models/product.py

Модель одной строки товарной накладной. Используется на всех этапах:
от результата OCR до записи в Excel.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Product:
    """Одна позиция (строка) товарной накладной."""

    name: str = ""
    article: str = ""
    barcode: str = ""
    quantity: str = ""
    price: str = ""
    total: str = ""
    unit: str = ""

    # Служебное поле: средняя уверенность OCR по строке (0..1), не экспортируется
    confidence: float = field(default=0.0, repr=False, compare=False)

    def is_empty(self) -> bool:
        """Строка считается пустой, если не заполнено ни одно значимое поле."""
        return not any([self.name, self.article, self.barcode, self.quantity, self.price, self.total])

    def to_row(self) -> list[str]:
        """Возвращает значения в порядке колонок таблицы/Excel."""
        return [self.name, self.article, self.barcode, self.quantity, self.price, self.total, self.unit]

    def to_dict(self) -> dict[str, str]:
        """Сериализация в словарь для JSON-экспорта."""
        return {
            "name": self.name,
            "article": self.article,
            "barcode": self.barcode,
            "quantity": self.quantity,
            "price": self.price,
            "total": self.total,
            "unit": self.unit,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "Product":
        """Десериализация из словаря (JSON-черновик)."""
        return cls(
            name=data.get("name", ""),
            article=data.get("article", ""),
            barcode=data.get("barcode", ""),
            quantity=data.get("quantity", ""),
            price=data.get("price", ""),
            total=data.get("total", ""),
            unit=data.get("unit", ""),
        )

    @classmethod
    def from_row(cls, row: list[str]) -> "Product":
        values = list(row) + [""] * (7 - len(row))
        return cls(
            name=values[0],
            article=values[1],
            barcode=values[2],
            quantity=values[3],
            price=values[4],
            total=values[5],
            unit=values[6],
        )
