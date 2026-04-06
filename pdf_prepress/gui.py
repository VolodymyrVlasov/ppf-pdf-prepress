"""
gui.py — Вікно налаштувань PDF Pre-Press Processor.

Дозволяє налаштувати DPI, кутові зміщення сторінок, суфікси файлів
та запустити обробку у будь-якому з чотирьох режимів.
Містить живий попередній перегляд деформації сторінок.
"""

import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from settings import load_settings, save_settings, DEFAULT_SETTINGS
from processor import process_pdf


# ---------------------------------------------------------------------------
# Константи
# ---------------------------------------------------------------------------

WINDOW_TITLE = "PDF Pre-Press — Налаштування"
WINDOW_SIZE  = "560x640"
PAD          = 16          # базовий відступ
ENTRY_W      = 70          # ширина поля вводу кута
LABEL_W      = 110         # ширина підпису поля кута

# Кнопки запуску: (мітка, mode-ключ, колір)
_BUTTONS = [
    ("CMYK",                   "cmyk",             "#1565C0"),
    ("Grayscale",              "grayscale",        "#4A4A4A"),
    ("CMYK + деформація",      "cmyk_warp",        "#6A1B9A"),
    ("Grayscale + деформація", "grayscale_warp",   "#1B5E20"),
]

# Кутові поля: (ключ у corners-dict, ряд, мітка X, мітка Y)
_CORNER_FIELDS = [
    ("tl", 0, "Верх-лів X",  "Верх-лів Y"),
    ("tr", 1, "Верх-прав X", "Верх-прав Y"),
    ("bl", 2, "Низ-лів X",   "Низ-лів Y"),
    ("br", 3, "Низ-прав X",  "Низ-прав Y"),
]

DPI_OPTIONS = ["150", "300", "600"]


# ---------------------------------------------------------------------------
# Допоміжні функції
# ---------------------------------------------------------------------------

def _parse_float(val: str, default: float = 0.0) -> float:
    """Безпечне перетворення рядка на float."""
    try:
        return float(val.replace(",", "."))
    except (ValueError, AttributeError):
        return default


def _separator(parent, pady=(8, 0)) -> ctk.CTkFrame:
    """Тонка горизонтальна лінія-розділювач."""
    line = ctk.CTkFrame(parent, height=1, fg_color=("gray75", "gray35"))
    line.pack(fill="x", padx=PAD, pady=pady)
    return line


def _section_label(parent, text: str) -> ctk.CTkLabel:
    """Жирний заголовок секції."""
    lbl = ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=13, weight="bold"),
                       anchor="w")
    lbl.pack(fill="x", padx=PAD, pady=(12, 2))
    return lbl


# ---------------------------------------------------------------------------
# Віджет попереднього перегляду деформації
# ---------------------------------------------------------------------------

class WarpPreviewCanvas(tk.Canvas):
    """
    Живий попередній перегляд кутової деформації двох сторінок.

    Ліворуч — непарна сторінка (FRONT), праворуч — парна (BACK).
    Пунктирна сіра лінія — оригінальний прямокутник.
    Суцільна кольорова лінія — деформований чотирикутник.
    """

    # Розміри полотна
    CANVAS_W = 300
    CANVAS_H = 200

    # Розміри прямокутника сторінки (пропорції A4: 1 : √2)
    PAGE_W = 100
    PAGE_H = 141

    # Масштаб: 1 мм = 1 піксель
    # (кожна половина полотна = 150 пікселів ≈ 150 мм сторінки)
    MM_TO_PX: float = 1.0

    # Кольори
    COLOR_ODD  = "#4A8FD4"   # синій — FRONT (непарні)
    COLOR_EVEN = "#E07B20"   # помаранчевий — BACK (парні)

    def __init__(
        self,
        parent,
        odd_vars:  dict[str, list[ctk.StringVar]],
        even_vars: dict[str, list[ctk.StringVar]],
        **kwargs,
    ) -> None:
        bg = self._canvas_bg()
        super().__init__(
            parent,
            width=self.CANVAS_W,
            height=self.CANVAS_H,
            bg=bg,
            highlightthickness=1,
            highlightbackground="#666666",
            **kwargs,
        )

        self._odd_vars  = odd_vars
        self._even_vars = even_vars

        # Підписуємося на зміни усіх 16 StringVar
        for var_dict in (odd_vars, even_vars):
            for key, *_ in _CORNER_FIELDS:
                for sv in var_dict[key]:
                    sv.trace_add("write", self._on_var_change)

        self.update_preview()

    # ---- Внутрішні допоміжники ----

    @staticmethod
    def _canvas_bg() -> str:
        """Колір фону полотна залежно від теми."""
        return "#2b2b2b" if ctk.get_appearance_mode() == "Dark" else "#ebebeb"

    def _on_var_change(self, *_) -> None:
        """Викликається при будь-якій зміні поля — перемальовує полотно."""
        self.update_preview()

    def _read_corners(
        self,
        var_dict: dict[str, list[ctk.StringVar]],
    ) -> dict[str, tuple[float, float]] | None:
        """
        Зчитує числові значення кутів зі StringVar-словника.
        Повертає None, якщо хоча б одне поле містить некоректне значення.
        """
        result: dict[str, tuple[float, float]] = {}
        for key, *_ in _CORNER_FIELDS:
            try:
                x = float(var_dict[key][0].get().replace(",", "."))
                y = float(var_dict[key][1].get().replace(",", "."))
            except ValueError:
                return None   # некоректне введення — пропускаємо перемалювання
            result[key] = (x, y)
        return result

    def _draw_page(
        self,
        cx: float,
        cy: float,
        corners_mm: dict[str, tuple[float, float]] | None,
        color: str,
        orig_color: str,
    ) -> None:
        """
        Малює один прямокутник сторінки з деформацією.

        :param cx, cy:      Центр прямокутника на полотні.
        :param corners_mm:  Зміщення кутів у мм; None → малюємо лише оригінал.
        :param color:       Колір деформованого контуру.
        :param orig_color:  Колір оригінального контуру (пунктир).
        """
        hw = self.PAGE_W / 2
        hh = self.PAGE_H / 2

        # Оригінальні кути (по порядку: TL → TR → BR → BL)
        orig = {
            "tl": (cx - hw, cy - hh),
            "tr": (cx + hw, cy - hh),
            "br": (cx + hw, cy + hh),
            "bl": (cx - hw, cy + hh),
        }
        seq = ["tl", "tr", "br", "bl"]

        # --- Пунктирний оригінальний контур ---
        for i in range(len(seq)):
            x1, y1 = orig[seq[i]]
            x2, y2 = orig[seq[(i + 1) % len(seq)]]
            self.create_line(x1, y1, x2, y2,
                             fill=orig_color, dash=(5, 4), width=1)

        # --- Деформований контур (якщо дані валідні) ---
        if corners_mm is not None:
            warped = {
                key: (
                    orig[key][0] + corners_mm[key][0] * self.MM_TO_PX,
                    orig[key][1] + corners_mm[key][1] * self.MM_TO_PX,
                )
                for key in seq
            }

            # Суцільний контур
            for i in range(len(seq)):
                x1, y1 = warped[seq[i]]
                x2, y2 = warped[seq[(i + 1) % len(seq)]]
                self.create_line(x1, y1, x2, y2, fill=color, width=2)

            # Маленькі кружечки на деформованих кутах
            r = 3
            for key in seq:
                px, py = warped[key]
                self.create_oval(px - r, py - r, px + r, py + r,
                                 fill=color, outline="")

    # ---- Публічний метод оновлення ----

    def update_preview(self) -> None:
        """Повністю перемальовує полотно з поточними значеннями кутів."""
        self.delete("all")

        # Синхронізуємо фон із темою
        bg = self._canvas_bg()
        self.configure(bg=bg)

        is_dark    = ctk.get_appearance_mode() == "Dark"
        orig_color = "#606060" if is_dark else "#b0b0b0"
        div_color  = "#505050" if is_dark else "#c8c8c8"

        # Центри двох сторінок по вертикалі (трохи вище, щоб лишилось місце для підпису)
        label_margin = 18
        cy = (self.CANVAS_H - label_margin) // 2

        left_cx  = self.CANVAS_W // 4       # 75 px
        right_cx = 3 * self.CANVAS_W // 4   # 225 px

        # Вертикальна лінія-розділювач між сторінками
        mid = self.CANVAS_W // 2
        self.create_line(mid, 8, mid, self.CANVAS_H - 8,
                         fill=div_color, dash=(3, 5), width=1)

        # Зчитуємо кути (None якщо поле містить некоректне значення)
        odd_corners  = self._read_corners(self._odd_vars)
        even_corners = self._read_corners(self._even_vars)

        # FRONT (непарна)
        self._draw_page(left_cx,  cy, odd_corners,  self.COLOR_ODD,  orig_color)
        self.create_text(left_cx,  cy + self.PAGE_H // 2 + 10,
                         text="FRONT", fill=self.COLOR_ODD,
                         font=("Arial", 9, "bold"))

        # BACK (парна)
        self._draw_page(right_cx, cy, even_corners, self.COLOR_EVEN, orig_color)
        self.create_text(right_cx, cy + self.PAGE_H // 2 + 10,
                         text="BACK",  fill=self.COLOR_EVEN,
                         font=("Arial", 9, "bold"))


# ---------------------------------------------------------------------------
# Головний клас
# ---------------------------------------------------------------------------

class SettingsWindow(ctk.CTk):
    """
    Головне вікно налаштувань.

    :param pdf_path: Необов'язковий шлях до PDF-файлу для обробки.
                     Якщо не передано — буде показано підказку.
    """

    def __init__(self, pdf_path: str | None = None) -> None:
        super().__init__()

        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        self.title(WINDOW_TITLE)
        self.geometry(WINDOW_SIZE)
        self.resizable(False, False)

        # Шлях до файлу, який оброблятиметься
        self._pdf_path: str | None = pdf_path

        # ---- Змінні форми ----
        self._dpi_var = ctk.StringVar(value="300")
        self._suffix_cmyk_var = ctk.StringVar(value="_CMYK")
        self._suffix_gray_var = ctk.StringVar(value="_GRAY")

        # Кутові зміщення: {"tl": [StringVar_x, StringVar_y], ...}
        self._odd_vars:  dict[str, list[ctk.StringVar]] = self._make_corner_vars()
        self._even_vars: dict[str, list[ctk.StringVar]] = self._make_corner_vars()

        # ---- Побудова UI ----
        self._build_ui()

        # ---- Завантаження збережених налаштувань ----
        self.load_settings()

    # -----------------------------------------------------------------------
    # Ініціалізація змінних
    # -----------------------------------------------------------------------

    @staticmethod
    def _make_corner_vars() -> dict[str, list[ctk.StringVar]]:
        """Створює порожній набір StringVar для чотирьох кутів."""
        return {key: [ctk.StringVar(value="0.0"), ctk.StringVar(value="0.0")]
                for key, *_ in _CORNER_FIELDS}

    # -----------------------------------------------------------------------
    # Побудова інтерфейсу
    # -----------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Розміщує всі секції у вікні."""

        # Прокрутна область — щоб вмістити всі секції без обрізання
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True)

        self._build_raster_section()
        _separator(self._scroll)
        self._build_corners_section(
            title="Деформація — Непарні сторінки (FRONT)",
            var_dict=self._odd_vars,
        )
        _separator(self._scroll)
        self._build_corners_section(
            title="Деформація — Парні сторінки (BACK)",
            var_dict=self._even_vars,
        )
        _separator(self._scroll)
        self._build_preview_section()     # ← попередній перегляд
        _separator(self._scroll)
        self._build_suffix_section()
        _separator(self._scroll, pady=(8, 4))
        self._build_buttons()

        # ---- Статус-рядок (поза scrollable-фреймом, завжди знизу) ----
        self._status_lbl = ctk.CTkLabel(
            self,
            text="Готово",
            anchor="w",
            font=ctk.CTkFont(size=11),
            fg_color=("gray90", "gray20"),
            corner_radius=0,
        )
        self._status_lbl.pack(fill="x", side="bottom", ipady=4, padx=0)

    # ---- Секція 1: DPI ----

    def _build_raster_section(self) -> None:
        _section_label(self._scroll, "Параметри растрування")

        row = ctk.CTkFrame(self._scroll, fg_color="transparent")
        row.pack(fill="x", padx=PAD, pady=(4, 8))

        ctk.CTkLabel(row, text="Роздільна здатність (DPI)", anchor="w").pack(side="left")
        ctk.CTkOptionMenu(
            row,
            variable=self._dpi_var,
            values=DPI_OPTIONS,
            width=90,
        ).pack(side="right")

    # ---- Секція 2 / 3: Кутові зміщення ----

    def _build_corners_section(
        self,
        title: str,
        var_dict: dict[str, list[ctk.StringVar]],
    ) -> None:
        _section_label(self._scroll, title)

        # Підказка
        ctk.CTkLabel(
            self._scroll,
            text="Зміщення кутів у мм  (+ назовні,  − всередину)",
            anchor="w",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60"),
        ).pack(fill="x", padx=PAD, pady=(0, 6))

        grid = ctk.CTkFrame(self._scroll, fg_color="transparent")
        grid.pack(fill="x", padx=PAD, pady=(0, 8))

        # Заголовки стовпців
        for col, txt in enumerate(("", "X (мм)", "Y (мм)"), start=0):
            ctk.CTkLabel(
                grid, text=txt, width=LABEL_W if col == 0 else ENTRY_W,
                anchor="center", font=ctk.CTkFont(size=11, weight="bold"),
            ).grid(row=0, column=col, padx=(0, 6), pady=(0, 4))

        # Рядки для кожного кута
        for row_idx, (key, _, lbl_x, _lbl_y) in enumerate(_CORNER_FIELDS, start=1):
            corner_name = lbl_x.rsplit(" ", 1)[0]   # "Верх-лів", "Низ-прав" тощо
            ctk.CTkLabel(
                grid, text=corner_name, width=LABEL_W, anchor="w",
            ).grid(row=row_idx, column=0, padx=(0, 6), pady=3)

            ctk.CTkEntry(
                grid, textvariable=var_dict[key][0], width=ENTRY_W, justify="center",
            ).grid(row=row_idx, column=1, padx=(0, 6), pady=3)

            ctk.CTkEntry(
                grid, textvariable=var_dict[key][1], width=ENTRY_W, justify="center",
            ).grid(row=row_idx, column=2, padx=0, pady=3)

    # ---- Секція «Попередній перегляд» ----

    def _build_preview_section(self) -> None:
        """Будує секцію з живим попереднім переглядом деформації."""
        _section_label(self._scroll, "Попередній перегляд деформації")

        # Контейнер для центрування полотна
        container = ctk.CTkFrame(self._scroll, fg_color="transparent")
        container.pack(pady=(4, 2))

        # Власне полотно
        self._preview = WarpPreviewCanvas(
            container,
            odd_vars=self._odd_vars,
            even_vars=self._even_vars,
        )
        self._preview.pack()

        # Легенда
        legend = ctk.CTkFrame(container, fg_color="transparent")
        legend.pack(pady=(6, 0))

        ctk.CTkLabel(
            legend,
            text="- - -  оригінал",
            font=ctk.CTkFont(size=10),
            text_color=("gray50", "gray55"),
        ).pack(side="left", padx=(0, 20))

        # «FRONT» зразок
        ctk.CTkLabel(
            legend,
            text="——  FRONT",
            font=ctk.CTkFont(size=10),
            text_color=WarpPreviewCanvas.COLOR_ODD,
        ).pack(side="left", padx=(0, 16))

        # «BACK» зразок
        ctk.CTkLabel(
            legend,
            text="——  BACK",
            font=ctk.CTkFont(size=10),
            text_color=WarpPreviewCanvas.COLOR_EVEN,
        ).pack(side="left")

    # ---- Секція 4: Суфікси ----

    def _build_suffix_section(self) -> None:
        _section_label(self._scroll, "Суфікси вихідних файлів")

        grid = ctk.CTkFrame(self._scroll, fg_color="transparent")
        grid.pack(fill="x", padx=PAD, pady=(4, 8))

        for row_idx, (label, var) in enumerate([
            ("Суфікс CMYK",      self._suffix_cmyk_var),
            ("Суфікс Grayscale", self._suffix_gray_var),
        ]):
            ctk.CTkLabel(grid, text=label, anchor="w", width=150).grid(
                row=row_idx, column=0, padx=(0, 12), pady=4, sticky="w")
            ctk.CTkEntry(grid, textvariable=var, width=130).grid(
                row=row_idx, column=1, pady=4, sticky="w")

    # ---- Секція 5: Кнопки запуску ----

    def _build_buttons(self) -> None:
        _section_label(self._scroll, "Запуск обробки")

        outer = ctk.CTkFrame(self._scroll, fg_color="transparent")
        outer.pack(fill="x", padx=PAD, pady=(6, PAD))

        # 2×2 сітка кнопок
        for idx, (label, mode, color) in enumerate(_BUTTONS):
            row, col = divmod(idx, 2)
            btn = ctk.CTkButton(
                outer,
                text=label,
                fg_color=color,
                hover_color=self._darken(color),
                font=ctk.CTkFont(size=13, weight="bold"),
                height=42,
                corner_radius=8,
                command=lambda m=mode: self.on_run(m),
            )
            btn.grid(row=row, column=col,
                     padx=(0 if col == 0 else 8, 0),
                     pady=(0 if row == 0 else 8, 0),
                     sticky="ew")

        outer.grid_columnconfigure(0, weight=1)
        outer.grid_columnconfigure(1, weight=1)

    # -----------------------------------------------------------------------
    # Публічні методи
    # -----------------------------------------------------------------------

    def load_settings(self) -> None:
        """Зчитує settings.json і заповнює всі поля форми."""
        s = load_settings()

        # DPI
        dpi_str = str(s.get("dpi", 300))
        self._dpi_var.set(dpi_str if dpi_str in DPI_OPTIONS else "300")

        # Суфікси
        self._suffix_cmyk_var.set(s.get("output_suffix_cmyk", "_CMYK"))
        self._suffix_gray_var.set(s.get("output_suffix_gray", "_GRAY"))

        # Кутові зміщення
        self._fill_corner_vars(self._odd_vars,  s.get("odd_corners",  DEFAULT_SETTINGS["odd_corners"]))
        self._fill_corner_vars(self._even_vars, s.get("even_corners", DEFAULT_SETTINGS["even_corners"]))

    def get_settings(self) -> dict:
        """Зчитує всі поля форми і повертає словник налаштувань."""
        return {
            "dpi":                int(self._dpi_var.get()),
            "odd_corners":        self._read_corner_vars(self._odd_vars),
            "even_corners":       self._read_corner_vars(self._even_vars),
            "output_suffix_cmyk": self._suffix_cmyk_var.get() or "_CMYK",
            "output_suffix_gray": self._suffix_gray_var.get() or "_GRAY",
        }

    def on_run(self, mode: str) -> None:
        """
        Зберігає налаштування та запускає обробку PDF у фоновому потоці.

        :param mode: Режим обробки: «cmyk», «grayscale», «cmyk_warp», «grayscale_warp».
        """
        if not self._pdf_path:
            messagebox.showwarning(
                "Файл не обрано",
                "PDF-файл не вказано.\nЗапустіть програму через main.py або передайте шлях до файлу.",
                parent=self,
            )
            return

        if not Path(self._pdf_path).exists():
            messagebox.showerror(
                "Файл не знайдено",
                f"Не вдалось знайти файл:\n{self._pdf_path}",
                parent=self,
            )
            return

        # Зберігаємо налаштування перед запуском
        settings = self.get_settings()
        try:
            save_settings(settings)
        except Exception as exc:
            messagebox.showerror("Помилка збереження", str(exc), parent=self)
            return

        suffix = (settings["output_suffix_cmyk"]
                  if mode.startswith("cmyk")
                  else settings["output_suffix_gray"])

        self._set_status(f"Обробка: {Path(self._pdf_path).name}  [{mode}]…")

        def _worker() -> None:
            try:
                out = process_pdf(
                    pdf_path=self._pdf_path,
                    mode=mode,
                    dpi=settings["dpi"],
                    odd_corners=settings["odd_corners"],
                    even_corners=settings["even_corners"],
                    output_suffix=suffix,
                )
                self.after(0, lambda: self._on_done(out))
            except Exception as exc:
                self.after(0, lambda: self._on_error(exc))

        threading.Thread(target=_worker, daemon=True).start()

    # -----------------------------------------------------------------------
    # Внутрішні допоміжники
    # -----------------------------------------------------------------------

    @staticmethod
    def _fill_corner_vars(
        var_dict: dict[str, list[ctk.StringVar]],
        corners_data: dict,
    ) -> None:
        """Заповнює StringVar-словник значеннями із corners_data."""
        for key, *_ in _CORNER_FIELDS:
            vals = corners_data.get(key, [0.0, 0.0])
            var_dict[key][0].set(str(vals[0]))
            var_dict[key][1].set(str(vals[1]))

    @staticmethod
    def _read_corner_vars(
        var_dict: dict[str, list[ctk.StringVar]],
    ) -> dict[str, list[float]]:
        """Зчитує StringVar-словник і повертає dict із float-парами."""
        return {
            key: [_parse_float(var_dict[key][0].get()), _parse_float(var_dict[key][1].get())]
            for key, *_ in _CORNER_FIELDS
        }

    @staticmethod
    def _darken(hex_color: str, factor: float = 0.75) -> str:
        """Повертає затемнений варіант HEX-кольору для ефекту hover."""
        hex_color = hex_color.lstrip("#")
        r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return "#{:02x}{:02x}{:02x}".format(
            int(r * factor), int(g * factor), int(b * factor))

    def _set_status(self, text: str) -> None:
        """Оновлює текст статус-рядка."""
        self._status_lbl.configure(text=f"  {text}")

    def _on_done(self, output_path: str) -> None:
        self._set_status(f"Готово: {output_path}")
        messagebox.showinfo("Успіх", f"Файл збережено:\n{output_path}", parent=self)

    def _on_error(self, exc: Exception) -> None:
        self._set_status(f"Помилка: {exc}")
        messagebox.showerror("Помилка обробки", str(exc), parent=self)


# ---------------------------------------------------------------------------
# Точка входу для автономного запуску
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    pdf = sys.argv[1] if len(sys.argv) > 1 else None
    app = SettingsWindow(pdf_path=pdf)
    app.mainloop()
