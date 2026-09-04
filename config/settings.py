"""
config/settings.py

Менеджер настроек приложения. Хранит настройки в JSON-файле
и предоставляет типизированный доступ к ним. Если файл настроек
отсутствует или поврежден — создается новый со значениями по умолчанию.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from config.config import DEFAULT_SETTINGS, SETTINGS_FILE

logger = logging.getLogger(__name__)


@dataclass
class AppSettings:
    """Типизированное представление настроек приложения."""

    export_folder: str = DEFAULT_SETTINGS["export_folder"]
    language: str = DEFAULT_SETTINGS["language"]
    theme: str = DEFAULT_SETTINGS["theme"]
    auto_open_excel: bool = DEFAULT_SETTINGS["auto_open_excel"]
    ocr_languages: list[str] = field(default_factory=lambda: list(DEFAULT_SETTINGS["ocr_languages"]))
    ocr_gpu: bool = DEFAULT_SETTINGS["ocr_gpu"]
    mistral_api_key: str = DEFAULT_SETTINGS["mistral_api_key"]
    ocr_engine: str = DEFAULT_SETTINGS["ocr_engine"]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        known_fields = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**{**DEFAULT_SETTINGS, **filtered})


class SettingsManager:
    """Загружает, хранит и сохраняет настройки приложения на диск."""

    def __init__(self, settings_path: Path = SETTINGS_FILE) -> None:
        self._path = settings_path
        self._settings = self._load()

    @property
    def settings(self) -> AppSettings:
        return self._settings

    def _load(self) -> AppSettings:
        """Читает JSON-файл настроек, при ошибке возвращает настройки по умолчанию."""
        if not self._path.exists():
            logger.info("Файл настроек не найден, создаю новый со значениями по умолчанию")
            settings = AppSettings()
            self._save_to_disk(settings)
            return settings

        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            return AppSettings.from_dict(raw)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Не удалось прочитать настройки: %s. Использую значения по умолчанию", exc)
            return AppSettings()

    def _save_to_disk(self, settings: AppSettings) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._path, "w", encoding="utf-8") as fh:
                json.dump(settings.to_dict(), fh, ensure_ascii=False, indent=4)
        except OSError as exc:
            logger.error("Не удалось сохранить настройки: %s", exc)

    def update(self, **kwargs: Any) -> None:
        """Обновляет одну или несколько настроек и сохраняет их на диск."""
        for key, value in kwargs.items():
            if hasattr(self._settings, key):
                setattr(self._settings, key, value)
            else:
                logger.warning("Неизвестный ключ настроек: %s", key)
        self._save_to_disk(self._settings)

    def reload(self) -> None:
        self._settings = self._load()
