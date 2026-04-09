"""
main.py — Точка входу PDF Pre-Press Processor.

Використання:
    python main.py                  # відкриває вікно з порожнім списком файлів
    python main.py path/to/file.pdf # одразу завантажує файл у список
    pdf_prepress.exe "%1"           # так викликається з контекстного меню Windows
"""

import sys
import traceback
from pathlib import Path
from tkinter import messagebox
import tkinter as tk

import customtkinter as ctk

from gui import SettingsWindow


def main() -> None:
    """Головна функція — визначає pdf_path та відкриває SettingsWindow."""

    pdf_path: str | None = None

    # --- Аргумент командного рядка ---
    if len(sys.argv) >= 2:
        arg = sys.argv[1]
        p = Path(arg)
        if p.exists() and p.suffix.lower() == ".pdf":
            pdf_path = arg
        elif p.exists():
            # Файл існує, але не PDF — просто ігноруємо без діалогу
            pass
        else:
            # Файл з аргументу не знайдено — відкриваємо без файлу
            pass

    # --- Запускаємо головне вікно ---
    # Якщо pdf_path == None, вікно відкривається з порожнім списком файлів.
    # Користувач додає файли через кнопку «⊕ Додати».
    app = SettingsWindow(pdf_path=pdf_path)
    app.mainloop()


# ---------------------------------------------------------------------------
# Захист від необроблених виключень верхнього рівня
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        err = traceback.format_exc()
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Критична помилка — PDF Pre-Press",
                f"Програма завершилась через необроблену помилку:\n\n{err}",
                parent=root,
            )
            root.destroy()
        except Exception:
            print(err, file=sys.stderr)
        sys.exit(1)
