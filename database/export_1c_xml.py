"""
database/export_1c_xml.py

Генерирует XML-файл для обмена данными с 1С (формат КОММЕРЧЕСКАЯИНФОРМАЦИЯ).
Запуск: python database/export_1c_xml.py
"""

import sqlite3
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString

DB_PATH = Path(__file__).parent / "store_1c.db"
XML_PATH = Path(__file__).parent / "products_1c_import.xml"


def export_xml() -> None:
    conn = sqlite3.connect(str(DB_PATH))

    rows = conn.execute("""
        SELECT
            p.article,
            p.barcode,
            p.name,
            c.name AS category,
            u.short_name AS unit,
            p.price,
            p.price_discount
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        LEFT JOIN units u ON p.unit_id = u.id
        WHERE p.is_active = 1
        ORDER BY c.name, p.name
    """).fetchall()

    # Корневой элемент
    root = Element("КоммерческаяИнформация", {
        "ВерсияСхемы": "2.08",
        "ДатаФормирования": "2026-09-04T12:00:00"
    })

    # Каталог товаров
    catalog = SubElement(root, "Каталог")
    SubElement(catalog, "Ид").text = "products_catalog"
    SubElement(catalog, "Наименование").text = "Справочник товаров"

    items = SubElement(catalog, "Товары")

    for article, barcode, name, category, unit, price, price_disc in rows:
        item = SubElement(items, "Товар")
        SubElement(item, "Ид").text = article or ""
        SubElement(item, "Артикул").text = article or ""
        SubElement(item, "Наименование").text = name
        SubElement(item, "ЕдиницаИзмерения").text = unit or "шт"

        # Штрихкод
        if barcode:
            codes = SubElement(item, "Штрихкоды")
            SubElement(codes, "ШтрихКод").text = barcode

        # Цены
        prices = SubElement(item, "Цены")
        p1 = SubElement(prices, "Цена")
        SubElement(p1, "ТипЦены").text = "Основная"
        SubElement(p1, "Сумма").text = str(price)

        if price_disc and price_disc != price:
            p2 = SubElement(prices, "Цена")
            SubElement(p2, "ТипЦены").text = "Со скидкой"
            SubElement(p2, "Сумма").text = str(price_disc)

        # Категория
        if category:
            SubElement(item, "Группы").text = category

    # Форматированный XML
    xml_str = parseString(tostring(root, encoding="unicode")).toprettyxml(indent="  ")

    XML_PATH.write_text(xml_str, encoding="utf-8")
    print(f"XML экспортирован: {XML_PATH}")
    print(f"Товаров: {len(rows)}")
    conn.close()


if __name__ == "__main__":
    export_xml()
