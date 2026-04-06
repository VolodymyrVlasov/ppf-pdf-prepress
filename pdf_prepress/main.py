"""
main.py — Точка входу PDF Pre-Press Processor.

Використання:
    python main.py                  # відкриває діалог вибору файлу
    python main.py path/to/file.pdf # одразу відкриває налаштування для файлу
    pdf_prepress.exe "%1"           # так викликається з контекстного меню Windows
"""

import sys
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox
import tkinter as tk

import customtkinter as ctk

from gui import SettingsWindow


def _pick_file() -> str | None:
    """
    Показує діалог вибору PDF-файлу.
    Повертає шлях або None, якщо користувач скасував.
    """
    # Тимчасове приховане кореневе вікно лише для діалогу
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    path = filedialog.askopenfilename(
        parent=root,
        title="Оберіть PDF-файл для обробки",
        filetypes=[("PDF файли", "*.pdf"), ("Усі файли", "*.*")],
    )
    root.destroy()
    return path or None


def main() -> None:
    """Головна функція — визначає pdf_path та відкриває SettingsWindow."""

    pdf_path: str | None = None

    # --- Аргумент командного рядка ---
    if len(sys.argv) >= 2:
        arg = sys.argv[1]
        if Path(arg).exists():
            pdf_path = arg
        else:
            # Файл з аргументу не знайдено — повідомляємо, продовжуємо без нього
            _warn(f"Файл не знайдено:\n{arg}\n\nБуде відкрито діалог вибору файлу.")

    # --- Без аргументу або файл не знайдено — показуємо файловий діалог ---
    if pdf_path is None:
        pdf_path = _pick_file()
        # Якщо користувач скасував діалог — запускаємо без файлу
        # (SettingsWindow покаже попередження при спробі запустити обробку)

    # --- Запускаємо головне вікно ---
    app = SettingsWindow(pdf_path=pdf_path)
    app.mainloop()


def _warn(msg: str) -> None:
    """Показує попередження через тимчасове tk-вікно (до появи основного)."""
    root = tk.Tk()
    root.withdraw()
    messagebox.showwarning("PDF Pre-Press", msg, parent=root)
    root.destroy()


# ---------------------------------------------------------------------------
# Захист від необроблених виключень верхнього рівня
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        # Показуємо повний traceback у messagebox перед виходом
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
            # Якщо навіть tk недоступний — виводимо у stderr
            print(err, file=sys.stderr)
        sys.exit(1)
