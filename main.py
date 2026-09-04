"""
main.py

Точка входа в приложение. Инициализирует логирование, создает
необходимые директории, запускает Qt-приложение и главное окно.
"""

from __future__ import annotations

import logging
import os
import sys

os.environ.setdefault("FLAGS_use_mkldnn", "0")  # fix oneDNN crash on Windows

from PySide6.QtWidgets import QApplication, QMessageBox

from config.config import EXPORTS_DIR, LOGS_DIR, TEMP_DIR
from utils.logger import setup_logging


def _ensure_runtime_directories() -> None:
    """Создает рабочие папки приложения при первом запуске."""
    for directory in (LOGS_DIR, EXPORTS_DIR, TEMP_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def main() -> int:
    _ensure_runtime_directories()
    setup_logging(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info("Запуск приложения")

    app = QApplication(sys.argv)
    app.setApplicationName("Invoice Recognizer")

    try:
        from ui.main_window import MainWindow

        window = MainWindow()
        window.show()
    except Exception:  # noqa: BLE001 - фатальная ошибка запуска должна быть залогирована
        logger.exception("Критическая ошибка при запуске приложения")
        QMessageBox.critical(None, "Ошибка запуска", "Приложение не удалось запустить. Подробности в logs/app.log")
        return 1

    exit_code = app.exec()
    logger.info("Приложение завершено, код выхода: %s", exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
