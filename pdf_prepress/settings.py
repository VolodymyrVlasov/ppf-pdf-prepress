"""
settings.py — Завантаження та збереження налаштувань користувача.

Налаштування зберігаються у файлі settings.json поряд із main.py.
"""

import json
from pathlib import Path


# Шлях до директорії, де лежить main.py (і settings.json)
_BASE_DIR = Path(__file__).parent

_SETTINGS_FILE = _BASE_DIR / "settings.json"

# ---------------------------------------------------------------------------
# Налаштування за замовчуванням
# ---------------------------------------------------------------------------

_ZERO_CORNERS: dict[str, list[float]] = {
    "tl": [0.0, 0.0],
    "tr": [0.0, 0.0],
    "bl": [0.0, 0.0],
    "br": [0.0, 0.0],
}

DEFAULT_SETTINGS: dict = {
    # Роздільна здатність растеризації (DPI)
    "dpi": 300,

    # Зміщення кутів для непарних сторінок (мм)
    "odd_corners": {k: list(v) for k, v in _ZERO_CORNERS.items()},

    # Зміщення кутів для парних сторінок (мм)
    "even_corners": {k: list(v) for k, v in _ZERO_CORNERS.items()},

    # Суфікси вихідних файлів
    "output_suffix_cmyk": "_CMYK",
    "output_suffix_gray": "_GRAY",
    "output_suffix_rgb":  "_RGB",

    # ICC-профілі (лише ім'я файлу в підпапці icc_profiles/{cs}/)
    "use_icc_profile":  True,
    "icc_profile_cmyk": "",
    "icc_profile_rgb":  "",
    "icc_profile_gray": "",

    # Остання папка, відкрита у файловому діалозі
    "last_folder": "",
}


# ---------------------------------------------------------------------------
# Допоміжна функція: глибоке злиття словників
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, override: dict) -> dict:
    """
    Рекурсивно зливає override у base.
    Вкладені словники об'єднуються, а не замінюються цілком.
    """
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# ---------------------------------------------------------------------------
# Публічні функції
# ---------------------------------------------------------------------------

def load_settings() -> dict:
    """
    Зчитує settings.json і повертає словник, об'єднаний із DEFAULT_SETTINGS.

    Якщо файл відсутній або пошкоджений — повертає значення за замовчуванням.

    :return: Словник налаштувань.
    """
    if not _SETTINGS_FILE.exists():
        return dict(DEFAULT_SETTINGS)

    try:
        with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
            user_data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[settings] Не вдалось прочитати {_SETTINGS_FILE.name}: {exc}. Використовуються значення за замовчуванням.")
        return dict(DEFAULT_SETTINGS)

    # Зливаємо: DEFAULT_SETTINGS як база, user_data перезаписує
    merged = _deep_merge(DEFAULT_SETTINGS, user_data)
    return merged


def save_settings(data: dict) -> None:
    """
    Зберігає словник налаштувань у settings.json.

    :param data: Словник з налаштуваннями для збереження.
    """
    try:
        with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as exc:
        print(f"[settings] Не вдалось зберегти {_SETTINGS_FILE.name}: {exc}")
        raise
