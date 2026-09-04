"""
utils/logger.py

Единая настройка логирования для всего приложения.
Все ошибки и важные события пишутся в logs/app.log,
а также дублируются в консоль во время разработки.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from config.config import LOG_FILE, LOGS_DIR

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    """Инициализирует корневой логгер. Безопасно вызывать несколько раз."""
    global _configured
    if _configured:
        return

    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    _configured = True
    logging.getLogger(__name__).info("Логирование инициализировано")
