"""
database/create_1c_db.py

Создаёт SQLite базу данных магазина (аналог справочника 1С)
с реальными товарами казахстанского продуктового магазина.

Запуск: python database/create_1c_db.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "store_1c.db"


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            parent_id INTEGER REFERENCES categories(id)
        );

        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            bin TEXT,
            phone TEXT,
            address TEXT
        );

        CREATE TABLE IF NOT EXISTS units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            short_name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article TEXT UNIQUE,
            barcode TEXT,
            name TEXT NOT NULL,
            category_id INTEGER REFERENCES categories(id),
            unit_id INTEGER REFERENCES units(id),
            supplier_id INTEGER REFERENCES suppliers(id),
            price REAL NOT NULL DEFAULT 0,
            price_discount REAL DEFAULT 0,
            quantity_stock REAL DEFAULT 0,
            min_stock REAL DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_products_article ON products(article);
        CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode);
        CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
        CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
    """)


def seed_units(conn: sqlite3.Connection) -> dict[str, int]:
    units = [
        ("Штука", "шт"),
        ("Бутылка", "бут"),
        ("Упаковка", "уп"),
        ("Килограмм", "кг"),
        ("Литр", "л"),
        ("Банка", "бан"),
        ("Коробка", "короб"),
        ("Пачка", "пач"),
        ("Рулон", "рул"),
        ("Пластик", "пэ"),
    ]
    cursor = conn.executemany(
        "INSERT OR IGNORE INTO units (name, short_name) VALUES (?, ?)", units
    )
    result = {}
    for name, short in units:
        row = conn.execute("SELECT id FROM units WHERE short_name = ?", (short,)).fetchone()
        result[short] = row[0]
    return result


def seed_categories(conn: sqlite3.Connection) -> dict[str, int]:
    categories = [
        ("Чай", None),
        ("Вода", None),
        ("Молочные продукты", None),
        ("Макароны", None),
        ("Напитки", None),
        ("Соки", None),
        ("Крупы", None),
        ("Масло и соусы", None),
        ("Кондитерские изделия", None),
        ("Хлеб и выпечка", None),
        ("Колбасы и мясные", None),
        ("Консервация", None),
        ("Бакалея", None),
        ("Чай чёрный", 1),
        ("Чай зелёный", 1),
        ("Чай фруктовый", 1),
        ("Вода минеральная", 2),
        ("Вода питьевая", 2),
        ("Молоко", 3),
        ("Кефир", 3),
        ("Сметана", 3),
        ("Йогурт", 3),
        ("Сыр", 3),
        ("Макароны", 4),
        ("Вермишель", 4),
        ("Лапша", 4),
        ("Газированные", 5),
        ("Энергетики", 5),
        ("Компоты", 5),
        ("Соки", 6),
        ("Морсы", 6),
    ]
    cursor = conn.executemany(
        "INSERT OR IGNORE INTO categories (name, parent_id) VALUES (?, ?)", categories
    )
    result = {}
    for name, _ in categories:
        row = conn.execute("SELECT id FROM categories WHERE name = ?", (name,)).fetchone()
        result[name] = row[0]
    return result


def seed_suppliers(conn: sqlite3.Connection) -> dict[str, int]:
    suppliers = [
        ("ТОО «Альфа 2017»", "151140012279", "+7(712)55-55-55", "г. Атырау, ул. Абая, 1"),
        ("ИП «Серикалиев Н.К.»", "150140008812", "+7(712)33-33-33", "г. Атырау, ж/м Привокзальный, 3А"),
        ("ТОО «МахиТрейд»", "170740015632", "+7(727)222-11-00", "г. Алматы, ул. Сатпаева, 22"),
        ("ТОО «АSampler»", "160540009874", "+7(712)44-44-44", "г. Атырау, мкр. Азаттык, 10"),
        ("ТОО «Garden Drinks»", "180140023456", "+7(727)333-22-11", "г. Алматы, пр. Достык, 15"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO suppliers (name, bin, phone, address) VALUES (?, ?, ?, ?)",
        suppliers,
    )
    result = {}
    for name, *_ in suppliers:
        row = conn.execute("SELECT id FROM suppliers WHERE name = ?", (name,)).fetchone()
        result[name] = row[0]
    return result


def seed_products(conn: sqlite3.Connection, units: dict, cats: dict, sups: dict) -> None:
    """Средний ассортимент продуктового магазина Казахстана (~70 позиций)."""

    SUP_MAKHITRADE = sups.get("ТОО «МахиТрейд»", 1)
    SUP_ALPHA = sups.get("ТОО «Альфа 2017»", 1)
    SUP_ASAMPLER = sups.get("ТОО «АSampler»", 1)
    SUP_GARDEN = sups.get("ТОО «Garden Drinks»", 1)

    U_SHT = units.get("шт", 1)
    U_BUT = units.get("бут", 2)
    U_UP = units.get("уп", 3)
    U_KG = units.get("кг", 4)
    U_L = units.get("л", 5)

    C_CHERNY = cats.get("Чай чёрный", 1)
    C_ZELENY = cats.get("Чай зелёный", 1)
    C_FRUKT = cats.get("Чай фруктовый", 1)
    C_MINVODA = cats.get("Вода минеральная", 2)
    C_PITVODA = cats.get("Вода питьевая", 2)
    C_MOLOKO = cats.get("Молоко", 3)
    C_KEFIR = cats.get("Кефир", 3)
    C_SMETANA = cats.get("Сметана", 3)
    C_JOGURT = cats.get("Йогурт", 3)
    C_SYR = cats.get("Сыр", 3)
    C_MAKARONY = cats.get("Макароны", 4)
    C_VERM = cats.get("Вермишель", 4)
    C_GAZ = cats.get("Газированные", 5)
    C_ENERGO = cats.get("Энергетики", 5)
    C_KOMPOT = cats.get("Компоты", 5)
    C_SOKI = cats.get("Соки", 6)
    C_MORS = cats.get("Морсы", 6)
    C_KOLBASA = cats.get("Колбасы и мясные", 11)
    C_KRUP = cats.get("Крупы", 7)
    C_MASLO = cats.get("Масло и соусы", 8)
    C_KOND = cats.get("Кондитерские изделия", 9)
    C_HLEB = cats.get("Хлеб и выпечка", 10)
    C_KONS = cats.get("Консервация", 12)
    C_BAL = cats.get("Бакалея", 13)

    products = [
        # ── Чай чёрный (Махі) ──
        ("00000012612", "8690718126120", "Махі Чай черный Клубника 2,0 ПЭТ шт/уп", C_CHERNY, U_UP, SUP_MAKHITRADE, 777.00, 745.92),
        ("00000012664", "8690718126640", "Махі Чай зеленый Лимон 2,0 ПЭТ шт/уп", C_ZELENY, U_UP, SUP_MAKHITRADE, 777.00, 745.92),
        ("00000001801", "8690718018010", "Махі Чай черный Клубника 0,450 ПЭТ 12 шт/уп", C_CHERNY, U_UP, SUP_MAKHITRADE, 330.00, 316.80),
        ("00000001803", "8690718018030", "Махі Чай черный Лесные ягоды 0,450 ПЭТ 12 шт/уп", C_CHERNY, U_UP, SUP_MAKHITRADE, 330.00, 316.80),
        ("00000001802", "8690718018020", "Махі Чай черный Клубника 1,20 ПЭТ 6 шт/уп", C_CHERNY, U_UP, SUP_MAKHITRADE, 510.00, 489.60),
        ("00000001800", "8690718018000", "Махі Чай зеленый Лимон 1,20 ПЭТ 6 шт/уп", C_ZELENY, U_UP, SUP_MAKHITRADE, 510.00, 489.60),
        ("00000001798", "8690718017980", "Махі Чай зеленый Грейпфрут 1,20 ПЭТ 6 шт/уп", C_ZELENY, U_UP, SUP_MAKHITRADE, 510.00, 489.60),
        ("00000005626", "8690718056260", "Махі Чай черный Лайм Мята 1,20 ПЭТ 6 шт/уп", C_CHERNY, U_UP, SUP_MAKHITRADE, 510.00, 489.60),
        ("00000001804", "8690718018040", "Махі Чай черный Лесные ягоды 1,20 ПЭТ 6 шт/уп", C_CHERNY, U_UP, SUP_MAKHITRADE, 510.00, 489.60),
        ("00000001808", "8690718018080", "Махі Чай черный Персик 1,20 ПЭТ 6 шт/уп", C_CHERNY, U_UP, SUP_MAKHITRADE, 510.00, 489.60),
        ("00000001806", "8690718018060", "Махі Чай черный Лимон 1,20 ПЭТ 6 шт/уп", C_CHERNY, U_UP, SUP_MAKHITRADE, 510.00, 489.60),
        ("00000009888", "8690718098880", "Махі Чай черный Малина 1,20 ПЭТ 6 шт/уп", C_CHERNY, U_UP, SUP_MAKHITRADE, 510.00, 489.60),

        # ── Напитки (Garden, Happy, Daily fresh, Sevens) ──
        ("00000012997", "8690718129970", "Garden напиток со вкусом граната 2,0 ПЭТ 6 шт/уп", C_KOMPOT, U_UP, SUP_GARDEN, 777.00, 745.92),
        ("00000001815", "8690718018150", "Первоквас Свежак Квас живого брожения 1,5 ПЭТ 6 шт/уп", C_GAZ, U_UP, SUP_ALPHA, 470.00, 451.20),
        ("00000010315", "8690718103150", "Happy лимонад дюшес 1,5 ПЭТ 6шт/уп", C_GAZ, U_UP, SUP_GARDEN, 420.00, 403.20),
        ("00000010314", "8690718103140", "Happy лимонад тархун 1,5 ПЭТ 6шт/уп", C_GAZ, U_UP, SUP_GARDEN, 420.00, 403.20),
        ("00000005886", "8690718058860", "Daily fresh оригинал с добавлением мякоти алоэ 1,0 ПЭТ 6 шт/уп", C_SOKI, U_UP, SUP_GARDEN, 700.00, 672.00),
        ("00000013295", "8690718132950", "Daily fresh виноград с добавлением мякоти алоэ 1,0 ПЭТ 6 шт/уп", C_SOKI, U_UP, SUP_GARDEN, 700.00, 672.00),
        ("00000013296", "8690718132960", "Daily fresh ананас с добавлением мякоти алоэ 1,0 ПЭТ 6 шт/уп", C_SOKI, U_UP, SUP_GARDEN, 700.00, 672.00),
        ("00000007281", "8690718072810", "Garden напиток со вкусом груши 1,20 ПЭТ 6 шт/уп", C_KOMPOT, U_UP, SUP_GARDEN, 510.00, 489.60),
        ("00000007320", "8690718073200", "Garden напиток со вкусом вишни 1,20 ПЭТ 6 шт/уп", C_KOMPOT, U_UP, SUP_GARDEN, 510.00, 489.60),
        ("00000009918", "8690718099180", "Garden напиток со вкусом граната 1,20 ПЭТ 6 шт/уп", C_KOMPOT, U_UP, SUP_GARDEN, 510.00, 489.60),
        ("00000006981", "8690718069810", "Sevens Вода негазированная 0,5 ПЭТ 12 шт/уп", C_PITVODA, U_UP, SUP_GARDEN, 210.00, 201.60),

        # ── Вода минеральная ──
        ("10000001001", "4640017371616", "Вода минер Ессентуки №4 ПЭТ 1,5л/6", C_MINVODA, U_UP, SUP_ALPHA, 503.00, 503.00),
        ("10000001002", "4640017371678", "Вода минер Ессентуки №17 ПЭТ 1,5л/6", C_MINVODA, U_UP, SUP_ALPHA, 503.00, 503.00),
        ("10000001003", "4640017371000", "Вода минер Боржоми 0,5л/12", C_MINVODA, U_UP, SUP_ALPHA, 620.00, 620.00),
        ("10000001004", "4640017371100", "Вода минер Архыз 0,5л/12", C_MINVODA, U_UP, SUP_ALPHA, 380.00, 380.00),

        # ── Молочные продукты ──
        ("20000002001", "4870240160026", "Молоко Зорькин луг ТБА 3,2% 1л/12", C_MOLOKO, U_UP, SUP_ALPHA, 375.00, 375.00),
        ("20000002002", "4870240160033", "Молоко Зорькин луг ТБА 6% 1л/12", C_MOLOKO, U_UP, SUP_ALPHA, 410.00, 410.00),
        ("20000002003", "4870240160040", "Молоко Зорькин луг ТБА 2,5% 0,93л/12", C_MOLOKO, U_UP, SUP_ALPHA, 310.00, 310.00),
        ("20000002010", "4870240160100", "Кефир Зорькин луг 2,5% 1л/12", C_KEFIR, U_UP, SUP_ALPHA, 350.00, 350.00),
        ("20000002011", "4870240160110", "Кефир Зорькин луг 1% 0,93л/12", C_KEFIR, U_UP, SUP_ALPHA, 320.00, 320.00),
        ("20000002020", "4870240160200", "Сметана Зорькин луг 15% 200г/12", C_SMETANA, U_UP, SUP_ALPHA, 180.00, 180.00),
        ("20000002021", "4870240160210", "Сметана Зорькин луг 20% 300г/12", C_SMETANA, U_UP, SUP_ALPHA, 260.00, 260.00),
        ("20000002030", "4870240160300", "Йогурт Био Малина 2,5% 250г/12", C_JOGURT, U_UP, SUP_ALPHA, 220.00, 220.00),
        ("20000002031", "4870240160310", "Йогурт Био Персик 2,5% 250г/12", C_JOGURT, U_UP, SUP_ALPHA, 220.00, 220.00),
        ("20000002040", "4870240160400", "Сыр К𝐖АЗАР полутвёрдый 45% 200г/6", C_SYR, U_UP, SUP_ALPHA, 520.00, 520.00),

        # ── Макароны (Корона) ──
        ("30000003001", "4870200920974", "Корона 2кг Рожки №2", C_VERM, U_UP, SUP_ALPHA, 730.80, 730.80),
        ("30000003002", "4870200921131", "Корона 2кг Рожки №4", C_VERM, U_UP, SUP_ALPHA, 730.00, 730.00),
        ("30000003003", "4870200921292", "Корона 2кг Рожки №6", C_VERM, U_UP, SUP_ALPHA, 730.00, 730.00),
        ("30000003004", "4870200923845", "Корона 2кг Вермишель №2", C_VERM, U_UP, SUP_ALPHA, 761.00, 761.00),
        ("30000003005", "4870200923920", "Корона 2кг Перья №1", C_VERM, U_UP, SUP_ALPHA, 761.00, 761.00),
        ("30000003006", "4870200921858", "Корона 2кг Пружинка №1", C_VERM, U_UP, SUP_ALPHA, 761.00, 761.00),
        ("30000003007", "4870200923203", "Корона 2кг Спираль №1", C_MAKARONY, U_UP, SUP_ALPHA, 761.00, 761.00),
        ("30000003008", "4870200920950", "Корона 1кг Рожки №2", C_VERM, U_UP, SUP_ALPHA, 371.00, 371.00),
        ("30000003009", "4870200921117", "Корона 1кг Рожки №4", C_VERM, U_UP, SUP_ALPHA, 371.00, 371.00),
        ("30000003010", "4870200921278", "Корона 1кг Рожки №6", C_VERM, U_UP, SUP_ALPHA, 371.00, 371.00),
        ("30000003011", "4870200921353", "Корона 1кг Рожки №7", C_VERM, U_UP, SUP_ALPHA, 761.00, 761.00),
        ("30000003012", "4870200925184", "Корона 2кг Перья №3", C_VERM, U_UP, SUP_ALPHA, 761.00, 761.00),
        ("30000003013", "4870200922725", "Корона 2кг Ракушки №2", C_MAKARONY, U_UP, SUP_ALPHA, 761.00, 761.00),
        ("30000003014", "4870200923760", "Корона 2кг Вермишель №1", C_VERM, U_UP, SUP_ALPHA, 761.00, 761.00),

        # ── Крупы ──
        ("40000004001", "4870200930010", "Рис Астана круглый 1кг/10", C_KRUP, U_UP, SUP_ALPHA, 450.00, 450.00),
        ("40000004002", "4870200930020", "Гречка «Золотая» 1кг/10", C_KRUP, U_UP, SUP_ALPHA, 380.00, 380.00),
        ("40000004003", "4870200930030", "Пшено «Золотое» 1кг/10", C_KRUP, U_UP, SUP_ALPHA, 220.00, 220.00),
        ("40000004004", "4870200930040", "Перловка «Золотая» 1кг/10", C_KRUP, U_UP, SUP_ALPHA, 180.00, 180.00),
        ("40000004005", "4870200930050", "Манка Т-500 1кг/12", C_KRUP, U_UP, SUP_ALPHA, 200.00, 200.00),

        # ── Масло и соусы ──
        ("50000005001", "4870200940010", "Масло подсолнечное «Золотой Восток» 1л/12", C_MASLO, U_UP, SUP_ALPHA, 520.00, 520.00),
        ("50000005002", "4870200940020", "Масло подсолнечное «Золотой Восток» 0,5л/12", C_MASLO, U_UP, SUP_ALPHA, 310.00, 310.00),
        ("50000005003", "4870200940030", "Масло сливочное «Традиция» 82,5% 180г/20", C_MASLO, U_UP, SUP_ALPHA, 480.00, 480.00),

        # ── Кондитерские изделия ──
        ("60000006001", "4870200950010", "Печенье «Мечта» ванильное 200г/24", C_KOND, U_UP, SUP_ALPHA, 190.00, 190.00),
        ("60000006002", "4870200950020", "Печенье «Мечта» с овсянкой 200г/24", C_KOND, U_UP, SUP_ALPHA, 190.00, 190.00),
        ("60000006003", "4870200950030", "Пломбир «Гулчехра» ванильный 100г/36", C_KOND, U_UP, SUP_ALPHA, 250.00, 250.00),
        ("60000006004", "4870200950040", "Шоколад «Гулчехра» молочный 90г/24", C_KOND, U_UP, SUP_ALPHA, 340.00, 340.00),

        # ── Хлеб ──
        ("70000007001", "4870200960010", "Хлеб «Наnan» белый буханка 400г/12", C_HLEB, U_SHT, SUP_ALPHA, 160.00, 160.00),
        ("70000007002", "4870200960020", "Хлеб «Наnan» чёрный буханка 400г/12", C_HLEB, U_SHT, SUP_ALPHA, 170.00, 170.00),
        ("70000007003", "4870200960030", "Лаваш тонкий 250г/20", C_HLEB, U_SHT, SUP_ALPHA, 80.00, 80.00),

        # ── Колбасы ──
        ("80000008001", "4870200970010", "Сосиски «Астана» молочные 350г/12", C_KOLBASA, U_UP, SUP_ALPHA, 520.00, 520.00),
        ("80000008002", "4870200970020", "Сардельки «Астана» из курицы 300г/12", C_KOLBASA, U_UP, SUP_ALPHA, 440.00, 440.00),
        ("80000008003", "4870200970030", "Колбаса варёная «Докторская» 400г/10", C_KOLBASA, U_UP, SUP_ALPHA, 680.00, 680.00),

        # ── Консервация ──
        ("90000009001", "4870200980010", "Горошек зелёный «Алтын» 400г/12", C_KONS, U_UP, SUP_ALPHA, 280.00, 280.00),
        ("90000009002", "4870200980020", "Кукуруза «Алтын» 340г/12", C_KONS, U_UP, SUP_ALPHA, 260.00, 260.00),
        ("90000009003", "4870200980030", "Фасоль красная «Алтын» 400г/12", C_KONS, U_UP, SUP_ALPHA, 270.00, 270.00),

        # ── Бакалея ──
        ("A000000A001", "4870200990010", "Сахар-песок «Астана» 1кг/10", C_BAL, U_UP, SUP_ALPHA, 280.00, 280.00),
        ("A000000A002", "4870200990020", "Соль «Астана» поваренная 1кг/12", C_BAL, U_UP, SUP_ALPHA, 90.00, 90.00),
        ("A000000A003", "4870200990030", "Мука «Астана» высший сорт 2кг/10", C_BAL, U_UP, SUP_ALPHA, 320.00, 320.00),
        ("A000000A004", "4870200990040", "Чай чёрный «КANTON» 100г/24", C_CHERNY, U_UP, SUP_ALPHA, 420.00, 420.00),
        ("A000000A005", "4870200990050", "Кофе растворимый «Nescafe» 95г/12", C_BAL, U_UP, SUP_ALPHA, 1850.00, 1850.00),
        ("A000000A006", "4870200990060", "Мёд натуральный «Тәңірі» 500г/6", C_BAL, U_UP, SUP_ALPHA, 1200.00, 1200.00),
    ]

    conn.executemany(
        """INSERT OR IGNORE INTO products
           (article, barcode, name, category_id, unit_id, supplier_id, price, price_discount)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        products,
    )


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"Удалена старая база: {DB_PATH}")

    conn = sqlite3.connect(str(DB_PATH))
    print(f"Создание базы: {DB_PATH}")

    create_schema(conn)
    units = seed_units(conn)
    cats = seed_categories(conn)
    sups = seed_suppliers(conn)
    seed_products(conn, units, cats, sups)
    conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    print(f"Создано {count} товаров")
    print(f"Категорий: {conn.execute('SELECT COUNT(*) FROM categories').fetchone()[0]}")
    print(f"Поставщиков: {conn.execute('SELECT COUNT(*) FROM suppliers').fetchone()[0]}")

    # Экспорт CSV для 1С
    csv_path = DB_PATH.parent / "products_1c_import.csv"
    export_csv(conn, csv_path)
    print(f"CSV экспорт: {csv_path}")

    conn.close()
    print("Готово!")


def export_csv(conn: sqlite3.Connection, csv_path: Path) -> None:
    """Экспорт справочника товаров в CSV для загрузки в 1С."""
    import csv

    rows = conn.execute("""
        SELECT
            p.article        AS "Артикул",
            p.barcode        AS "Штрихкод",
            p.name           AS "Наименование",
            c.name           AS "Категория",
            u.short_name     AS "Ед.изм",
            s.name           AS "Поставщик",
            p.price          AS "Цена",
            p.price_discount AS "Цена со скидкой"
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        LEFT JOIN units u ON p.unit_id = u.id
        LEFT JOIN suppliers s ON p.supplier_id = s.id
        WHERE p.is_active = 1
        ORDER BY c.name, p.name
    """).fetchall()

    headers = ["Артикул", "Штрихкод", "Наименование", "Категория", "Ед.изм", "Поставщик", "Цена", "Цена со скидкой"]

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(headers)
        writer.writerows(rows)


if __name__ == "__main__":
    main()
