"""
gui.py — Вікно налаштувань PDF Pre-Press Processor.

Макет: 3 колонки, без прокрутки.
  Рядок 0 — вибір файлів (повна ширина)
  Рядок 1 — FRONT-кути | BACK-кути | Попередній перегляд
  Рядок 2 — DPI+суфікси | ICC-профілі | Кнопки запуску
  Рядок 3 — статус-рядок (повна ширина)
"""

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from settings import load_settings, save_settings, DEFAULT_SETTINGS
from processor import process_pdf, get_profiles, ICC_DIR


# ---------------------------------------------------------------------------
# Константи
# ---------------------------------------------------------------------------

WINDOW_TITLE = "PDF Pre-Press — Налаштування"
WINDOW_SIZE  = "1100x700"
PAD          = 16     # зовнішні відступи
IPAD         = 10     # відступи всередині панелей
ENTRY_W      = 70     # ширина поля вводу кута
LABEL_W      = 90     # ширина підпису кута

# Кнопки запуску: (мітка, mode-ключ, колір) — 3 рядки × 2 стовпці
_BUTTONS = [
    ("CMYK",                   "cmyk",             "#1565C0"),
    ("CMYK + деформація",      "cmyk_warp",        "#6A1B9A"),
    ("Grayscale",              "grayscale",        "#455A64"),
    ("Grayscale + деформація", "grayscale_warp",   "#37474F"),
    ("RGB",                    "rgb",              "#1B6B3A"),
    ("RGB + деформація",       "rgb_warp",         "#2E7D32"),
]

# Кутові поля: (ключ у corners-dict, ряд, мітка X, мітка Y)
_CORNER_FIELDS = [
    ("tl", 0, "Верх-лів X",  "Верх-лів Y"),
    ("tr", 1, "Верх-прав X", "Верх-прав Y"),
    ("bl", 2, "Низ-лів X",   "Низ-лів Y"),
    ("br", 3, "Низ-прав X",  "Низ-прав Y"),
]

DPI_OPTIONS    = ["150", "300", "600"]
_EMPTY_PROFILE = "— не знайдено —"
_NO_FILES      = "— файли не обрано —"

# ICC колірні простори: (ключ папки, мітка в UI, ключ налаштування)
_ICC_SPACES: list[tuple[str, str, str]] = [
    ("cmyk", "CMYK",      "icc_profile_cmyk"),
    ("rgb",  "RGB",       "icc_profile_rgb"),
    ("gray", "Grayscale", "icc_profile_gray"),
]


# ---------------------------------------------------------------------------
# Допоміжні функції
# ---------------------------------------------------------------------------

def _parse_float(val: str, default: float = 0.0) -> float:
    """Безпечне перетворення рядка на float."""
    try:
        return float(val.replace(",", "."))
    except (ValueError, AttributeError):
        return default


def _panel_label(parent, text: str) -> ctk.CTkLabel:
    """Жирний заголовок панелі (компактний відступ)."""
    lbl = ctk.CTkLabel(parent, text=text,
                        font=ctk.CTkFont(size=12, weight="bold"), anchor="w")
    lbl.pack(fill="x", padx=IPAD, pady=(IPAD, 4))
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

    CANVAS_W = 300
    CANVAS_H = 200

    # Розміри прямокутника сторінки (пропорції A4: 1 : √2)
    PAGE_W = 100
    PAGE_H = 141

    # Масштаб: 1 мм = 1 піксель
    MM_TO_PX: float = 1.0

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

    @staticmethod
    def _canvas_bg() -> str:
        return "#2b2b2b" if ctk.get_appearance_mode() == "Dark" else "#ebebeb"

    def _on_var_change(self, *_) -> None:
        self.update_preview()

    def _read_corners(
        self,
        var_dict: dict[str, list[ctk.StringVar]],
    ) -> dict[str, tuple[float, float]] | None:
        result: dict[str, tuple[float, float]] = {}
        for key, *_ in _CORNER_FIELDS:
            try:
                x = float(var_dict[key][0].get().replace(",", "."))
                y = float(var_dict[key][1].get().replace(",", "."))
            except ValueError:
                return None
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
        hw = self.PAGE_W / 2
        hh = self.PAGE_H / 2

        orig = {
            "tl": (cx - hw, cy - hh),
            "tr": (cx + hw, cy - hh),
            "br": (cx + hw, cy + hh),
            "bl": (cx - hw, cy + hh),
        }
        seq = ["tl", "tr", "br", "bl"]

        for i in range(len(seq)):
            x1, y1 = orig[seq[i]]
            x2, y2 = orig[seq[(i + 1) % len(seq)]]
            self.create_line(x1, y1, x2, y2, fill=orig_color, dash=(5, 4), width=1)

        if corners_mm is not None:
            warped = {
                key: (
                    orig[key][0] + corners_mm[key][0] * self.MM_TO_PX,
                    orig[key][1] + corners_mm[key][1] * self.MM_TO_PX,
                )
                for key in seq
            }
            for i in range(len(seq)):
                x1, y1 = warped[seq[i]]
                x2, y2 = warped[seq[(i + 1) % len(seq)]]
                self.create_line(x1, y1, x2, y2, fill=color, width=2)
            r = 3
            for key in seq:
                px, py = warped[key]
                self.create_oval(px - r, py - r, px + r, py + r, fill=color, outline="")

    def update_preview(self) -> None:
        """Повністю перемальовує полотно з поточними значеннями кутів."""
        self.delete("all")

        bg = self._canvas_bg()
        self.configure(bg=bg)

        is_dark    = ctk.get_appearance_mode() == "Dark"
        orig_color = "#606060" if is_dark else "#b0b0b0"
        div_color  = "#505050" if is_dark else "#c8c8c8"

        label_margin = 18
        cy = (self.CANVAS_H - label_margin) // 2

        left_cx  = self.CANVAS_W // 4
        right_cx = 3 * self.CANVAS_W // 4

        mid = self.CANVAS_W // 2
        self.create_line(mid, 8, mid, self.CANVAS_H - 8,
                         fill=div_color, dash=(3, 5), width=1)

        odd_corners  = self._read_corners(self._odd_vars)
        even_corners = self._read_corners(self._even_vars)

        self._draw_page(left_cx,  cy, odd_corners,  self.COLOR_ODD,  orig_color)
        self.create_text(left_cx,  cy + self.PAGE_H // 2 + 10,
                         text="FRONT", fill=self.COLOR_ODD, font=("Arial", 9, "bold"))

        self._draw_page(right_cx, cy, even_corners, self.COLOR_EVEN, orig_color)
        self.create_text(right_cx, cy + self.PAGE_H // 2 + 10,
                         text="BACK",  fill=self.COLOR_EVEN, font=("Arial", 9, "bold"))


# ---------------------------------------------------------------------------
# Головне вікно
# ---------------------------------------------------------------------------

class SettingsWindow(ctk.CTk):
    """
    Головне вікно налаштувань.

    :param pdf_path: Необов'язковий шлях до PDF-файлу (передається з main.py / CLI).
    """

    def __init__(self, pdf_path: str | None = None) -> None:
        super().__init__()

        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        self.title(WINDOW_TITLE)
        self.geometry(WINDOW_SIZE)
        self.resizable(False, False)

        # ---- Список файлів ----
        self._file_paths: list[str] = []
        self._file_combo_var = ctk.StringVar(value=_NO_FILES)
        self._file_combo: ctk.CTkComboBox  # призначається у _build_file_picker

        # ---- Змінні форми ----
        self._dpi_var         = ctk.StringVar(value="300")
        self._suffix_cmyk_var = ctk.StringVar(value="_CMYK")
        self._suffix_gray_var = ctk.StringVar(value="_GRAY")
        self._suffix_rgb_var  = ctk.StringVar(value="_RGB")

        # Кутові зміщення: {"tl": [StringVar_x, StringVar_y], ...}
        self._odd_vars:  dict[str, list[ctk.StringVar]] = self._make_corner_vars()
        self._even_vars: dict[str, list[ctk.StringVar]] = self._make_corner_vars()

        # ICC-профілі
        self._icc_use_var = ctk.BooleanVar(value=True)
        self._icc_vars:  dict[str, ctk.StringVar]     = {cs: ctk.StringVar() for cs, *_ in _ICC_SPACES}
        self._icc_menus: dict[str, ctk.CTkOptionMenu] = {}

        # ---- Побудова UI ----
        self._build_ui()

        # ---- Завантаження налаштувань ----
        self.load_settings()

        # ---- Попереднє завантаження файлу з CLI ----
        if pdf_path and Path(pdf_path).exists():
            self._add_file(pdf_path)

    # -----------------------------------------------------------------------
    # Ініціалізація змінних
    # -----------------------------------------------------------------------

    @staticmethod
    def _make_corner_vars() -> dict[str, list[ctk.StringVar]]:
        return {key: [ctk.StringVar(value="0.0"), ctk.StringVar(value="0.0")]
                for key, *_ in _CORNER_FIELDS}

    # -----------------------------------------------------------------------
    # Управління списком файлів
    # -----------------------------------------------------------------------

    def _current_pdf_path(self) -> str | None:
        """Повертає повний шлях до поточного файлу зі списку, або None."""
        if not self._file_paths:
            return None
        val = self._file_combo_var.get()
        if val == _NO_FILES:
            return None
        try:
            # Формат відображення: "N. filename.pdf"
            idx = int(val.split(".")[0]) - 1
            return self._file_paths[idx] if 0 <= idx < len(self._file_paths) else None
        except (ValueError, IndexError):
            return None

    def _refresh_file_combo(self, select_idx: int = 0) -> None:
        """Оновлює список dropdown і виділяє потрібний елемент."""
        if not self._file_paths:
            self._file_combo.configure(values=[_NO_FILES])
            self._file_combo_var.set(_NO_FILES)
            return
        display = [f"{i + 1}. {Path(p).name}" for i, p in enumerate(self._file_paths)]
        self._file_combo.configure(values=display)
        idx = max(0, min(select_idx, len(display) - 1))
        self._file_combo_var.set(display[idx])

    def _add_file(self, path: str) -> None:
        """Додає файл до списку (якщо ще немає) і виділяє його."""
        if path not in self._file_paths:
            self._file_paths.append(path)
        self._refresh_file_combo(self._file_paths.index(path))

    def _on_add_files(self) -> None:
        """Відкриває діалог вибору PDF-файлів та додає їх до списку."""
        s = load_settings()
        init_dir = s.get("last_folder", "")
        if not init_dir or not Path(init_dir).exists():
            init_dir = str(Path.home())

        paths = filedialog.askopenfilenames(
            parent=self,
            title="Оберіть PDF-файли",
            filetypes=[("PDF файли", "*.pdf"), ("Усі файли", "*.*")],
            initialdir=init_dir,
        )
        if not paths:
            return

        for path in paths:
            if path not in self._file_paths:
                self._file_paths.append(path)

        # Зберігаємо останню папку
        s["last_folder"] = str(Path(paths[-1]).parent)
        save_settings(s)

        self._refresh_file_combo(len(self._file_paths) - 1)

    def _on_remove_file(self) -> None:
        """Видаляє поточний файл зі списку."""
        if not self._file_paths:
            return
        val = self._file_combo_var.get()
        try:
            idx = int(val.split(".")[0]) - 1
        except (ValueError, IndexError):
            return
        if 0 <= idx < len(self._file_paths):
            self._file_paths.pop(idx)
            self._refresh_file_combo(max(0, idx - 1))

    # -----------------------------------------------------------------------
    # Побудова інтерфейсу
    # -----------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Розміщує всі панелі у вікні."""

        # Статус-рядок — пакуємо першим з side="bottom", щоб він завжди знизу
        self._status_lbl = ctk.CTkLabel(
            self, text="", anchor="w",
            font=ctk.CTkFont(size=11),
            fg_color=("gray88", "gray18"),
            corner_radius=0,
        )
        self._status_lbl.pack(fill="x", side="bottom", ipady=5)

        # Рядок 0: вибір файлів
        self._build_file_picker()

        # Рядок 1: FRONT-кути | BACK-кути | Попередній перегляд
        row1 = ctk.CTkFrame(self, fg_color="transparent")
        row1.pack(fill="x", padx=PAD, pady=(0, 6))
        row1.grid_columnconfigure(0, weight=1, uniform="row1")
        row1.grid_columnconfigure(1, weight=1, uniform="row1")
        row1.grid_columnconfigure(2, weight=1, uniform="row1")

        self._build_corners_panel(
            row1, col=0,
            title="Деформація — Непарні (FRONT)",
            var_dict=self._odd_vars,
        )
        self._build_corners_panel(
            row1, col=1,
            title="Деформація — Парні (BACK)",
            var_dict=self._even_vars,
        )
        self._build_preview_panel(row1, col=2)

        # Рядок 2: DPI+суфікси | ICC-профілі | Кнопки
        row2 = ctk.CTkFrame(self, fg_color="transparent")
        row2.pack(fill="x", padx=PAD, pady=(0, 8))
        row2.grid_columnconfigure(0, weight=1, uniform="row2")
        row2.grid_columnconfigure(1, weight=1, uniform="row2")
        row2.grid_columnconfigure(2, weight=1, uniform="row2")

        self._build_dpi_suffix_panel(row2, col=0)
        self._build_icc_panel(row2, col=1)
        self._build_buttons_panel(row2, col=2)

    # ---- Рядок 0: вибір файлів ----

    def _build_file_picker(self) -> None:
        frame = ctk.CTkFrame(self, corner_radius=8)
        frame.pack(fill="x", padx=PAD, pady=(PAD, 8))

        ctk.CTkLabel(frame, text="Файли:", width=55, anchor="w").pack(
            side="left", padx=(IPAD, 4), pady=10)

        # Кнопки праворуч (пакуємо до combobox, щоб він розтягнувся на решту)
        ctk.CTkButton(
            frame, text="✕ Видалити", width=100,
            fg_color="gray40", hover_color="gray30",
            command=self._on_remove_file,
        ).pack(side="right", padx=(4, IPAD), pady=10)

        ctk.CTkButton(
            frame, text="⊕ Додати", width=90,
            command=self._on_add_files,
        ).pack(side="right", padx=4, pady=10)

        # Combobox розтягується на весь вільний простір
        self._file_combo = ctk.CTkComboBox(
            frame,
            variable=self._file_combo_var,
            values=[_NO_FILES],
        )
        self._file_combo.pack(side="left", padx=(4, 4), pady=10, fill="x", expand=True)

    # ---- Рядок 1, колонки 0/1: кутові зміщення ----

    def _build_corners_panel(
        self,
        parent,
        col: int,
        title: str,
        var_dict: dict[str, list[ctk.StringVar]],
    ) -> None:
        frame = ctk.CTkFrame(parent, corner_radius=8)
        frame.grid(row=0, column=col, sticky="nsew",
                   padx=(0, 6) if col < 2 else 0, pady=4)

        _panel_label(frame, title)

        ctk.CTkLabel(
            frame,
            text="Зміщення кутів у мм  (+ назовні,  − всередину)",
            anchor="w", font=ctk.CTkFont(size=10),
            text_color=("gray50", "gray60"),
        ).pack(fill="x", padx=IPAD, pady=(0, 6))

        grid = ctk.CTkFrame(frame, fg_color="transparent")
        grid.pack(fill="x", padx=IPAD, pady=(0, IPAD))

        # Заголовки стовпців
        for c_idx, txt in enumerate(("", "X (мм)", "Y (мм)")):
            ctk.CTkLabel(
                grid, text=txt,
                width=LABEL_W if c_idx == 0 else ENTRY_W,
                anchor="center", font=ctk.CTkFont(size=10, weight="bold"),
            ).grid(row=0, column=c_idx, padx=(0, 4), pady=(0, 2))

        # Рядки кутів
        for row_idx, (key, _, lbl_x, _) in enumerate(_CORNER_FIELDS, start=1):
            corner_name = lbl_x.rsplit(" ", 1)[0]
            ctk.CTkLabel(grid, text=corner_name, width=LABEL_W, anchor="w").grid(
                row=row_idx, column=0, padx=(0, 4), pady=2)
            ctk.CTkEntry(grid, textvariable=var_dict[key][0],
                         width=ENTRY_W, justify="center").grid(
                row=row_idx, column=1, padx=(0, 4), pady=2)
            ctk.CTkEntry(grid, textvariable=var_dict[key][1],
                         width=ENTRY_W, justify="center").grid(
                row=row_idx, column=2, pady=2)

    # ---- Рядок 1, колонка 2: попередній перегляд ----

    def _build_preview_panel(self, parent, col: int) -> None:
        frame = ctk.CTkFrame(parent, corner_radius=8)
        frame.grid(row=0, column=col, sticky="nsew", pady=4)

        _panel_label(frame, "Попередній перегляд деформації")

        canvas_wrap = ctk.CTkFrame(frame, fg_color="transparent")
        canvas_wrap.pack(pady=(0, 4))

        self._preview = WarpPreviewCanvas(
            canvas_wrap,
            odd_vars=self._odd_vars,
            even_vars=self._even_vars,
        )
        self._preview.pack()

        legend = ctk.CTkFrame(frame, fg_color="transparent")
        legend.pack(pady=(2, IPAD))

        ctk.CTkLabel(legend, text="- - -  оригінал",
                     font=ctk.CTkFont(size=10),
                     text_color=("gray50", "gray55")).pack(side="left", padx=(0, 14))
        ctk.CTkLabel(legend, text="——  FRONT",
                     font=ctk.CTkFont(size=10),
                     text_color=WarpPreviewCanvas.COLOR_ODD).pack(side="left", padx=(0, 14))
        ctk.CTkLabel(legend, text="——  BACK",
                     font=ctk.CTkFont(size=10),
                     text_color=WarpPreviewCanvas.COLOR_EVEN).pack(side="left")

    # ---- Рядок 2, колонка 0: DPI + суфікси ----

    def _build_dpi_suffix_panel(self, parent, col: int) -> None:
        frame = ctk.CTkFrame(parent, corner_radius=8)
        frame.grid(row=0, column=col, sticky="nsew", padx=(0, 6), pady=4)

        _panel_label(frame, "Параметри растрування")

        dpi_row = ctk.CTkFrame(frame, fg_color="transparent")
        dpi_row.pack(fill="x", padx=IPAD, pady=(0, 8))
        ctk.CTkLabel(dpi_row, text="Роздільна здатність (DPI)", anchor="w").pack(side="left")
        ctk.CTkOptionMenu(dpi_row, variable=self._dpi_var,
                          values=DPI_OPTIONS, width=80).pack(side="right")

        _panel_label(frame, "Суфікси вихідних файлів")

        suffix_grid = ctk.CTkFrame(frame, fg_color="transparent")
        suffix_grid.pack(fill="x", padx=IPAD, pady=(0, IPAD))

        for row_idx, (label, var) in enumerate([
            ("Суфікс CMYK",      self._suffix_cmyk_var),
            ("Суфікс Grayscale", self._suffix_gray_var),
            ("Суфікс RGB",       self._suffix_rgb_var),
        ]):
            ctk.CTkLabel(suffix_grid, text=label, anchor="w", width=130).grid(
                row=row_idx, column=0, padx=(0, 8), pady=3, sticky="w")
            ctk.CTkEntry(suffix_grid, textvariable=var, width=100).grid(
                row=row_idx, column=1, pady=3, sticky="w")

    # ---- Рядок 2, колонка 1: ICC-профілі ----

    def _build_icc_panel(self, parent, col: int) -> None:
        frame = ctk.CTkFrame(parent, corner_radius=8)
        frame.grid(row=0, column=col, sticky="nsew", padx=(0, 6), pady=4)

        _panel_label(frame, "Кольоровий профіль (ICC)")

        ctk.CTkCheckBox(
            frame,
            text="Призначати ICC профіль (embed)",
            variable=self._icc_use_var,
            command=self._on_icc_toggle,
        ).pack(anchor="w", padx=IPAD, pady=(0, 8))

        icc_grid = ctk.CTkFrame(frame, fg_color="transparent")
        icc_grid.pack(fill="x", padx=IPAD, pady=(0, 4))

        for row_idx, (cs_key, cs_label, _) in enumerate(_ICC_SPACES):
            ctk.CTkLabel(icc_grid, text=cs_label, width=75, anchor="w").grid(
                row=row_idx, column=0, padx=(0, 6), pady=3, sticky="w")

            profiles = get_profiles(cs_key)
            values   = profiles if profiles else [_EMPTY_PROFILE]
            initial  = profiles[0] if profiles else _EMPTY_PROFILE
            self._icc_vars[cs_key].set(initial)

            menu = ctk.CTkOptionMenu(
                icc_grid, variable=self._icc_vars[cs_key],
                values=values, width=200,
                state="normal" if profiles else "disabled",
            )
            menu.grid(row=row_idx, column=1, padx=(0, 4), pady=3)
            self._icc_menus[cs_key] = menu

            ctk.CTkButton(
                icc_grid, text="⟳", width=28,
                command=lambda k=cs_key: self._refresh_icc_dropdown(k),
            ).grid(row=row_idx, column=2, pady=3)

        ctk.CTkLabel(
            frame,
            text="Профіль призначається як тег. Кольори не конвертуються.",
            font=ctk.CTkFont(size=10), text_color=("gray50", "gray55"), anchor="w",
        ).pack(fill="x", padx=IPAD, pady=(4, IPAD))

        self._on_icc_toggle()

    # ---- Рядок 2, колонка 2: кнопки запуску ----

    def _build_buttons_panel(self, parent, col: int) -> None:
        frame = ctk.CTkFrame(parent, corner_radius=8)
        frame.grid(row=0, column=col, sticky="nsew", pady=4)

        _panel_label(frame, "Запуск обробки")

        btn_grid = ctk.CTkFrame(frame, fg_color="transparent")
        btn_grid.pack(fill="both", expand=True, padx=IPAD, pady=(0, IPAD))
        btn_grid.grid_columnconfigure(0, weight=1)
        btn_grid.grid_columnconfigure(1, weight=1)

        # 3 рядки × 2 стовпці: [Base] [Base + деформація]
        for idx, (label, mode, color) in enumerate(_BUTTONS):
            r, c = divmod(idx, 2)
            ctk.CTkButton(
                btn_grid, text=label,
                fg_color=color, hover_color=self._darken(color),
                font=ctk.CTkFont(size=12, weight="bold"),
                height=42, corner_radius=8,
                command=lambda m=mode: self.on_run(m),
            ).grid(
                row=r, column=c,
                padx=(0 if c == 0 else 4, 4 if c == 0 else 0),
                pady=3, sticky="ew",
            )

    # -----------------------------------------------------------------------
    # ICC-допоміжники
    # -----------------------------------------------------------------------

    def _on_icc_toggle(self) -> None:
        """Вмикає/вимикає dropdown залежно від стану checkbox."""
        enabled = self._icc_use_var.get()
        for cs_key, menu in self._icc_menus.items():
            profiles = get_profiles(cs_key)
            menu.configure(state="normal" if (enabled and profiles) else "disabled")

    def _refresh_icc_dropdown(self, cs_key: str) -> None:
        """Пересканує підпапку профілів і оновлює відповідний dropdown."""
        menu = self._icc_menus.get(cs_key)
        if menu is None:
            return
        profiles = get_profiles(cs_key)
        if profiles:
            menu.configure(values=profiles,
                           state="normal" if self._icc_use_var.get() else "disabled")
            current = self._icc_vars[cs_key].get()
            self._icc_vars[cs_key].set(current if current in profiles else profiles[0])
        else:
            menu.configure(values=[_EMPTY_PROFILE], state="disabled")
            self._icc_vars[cs_key].set(_EMPTY_PROFILE)

    # -----------------------------------------------------------------------
    # Налаштування
    # -----------------------------------------------------------------------

    def load_settings(self) -> None:
        """Зчитує settings.json і заповнює всі поля форми."""
        s = load_settings()

        dpi_str = str(s.get("dpi", 300))
        self._dpi_var.set(dpi_str if dpi_str in DPI_OPTIONS else "300")

        self._suffix_cmyk_var.set(s.get("output_suffix_cmyk", "_CMYK"))
        self._suffix_gray_var.set(s.get("output_suffix_gray", "_GRAY"))
        self._suffix_rgb_var.set(s.get("output_suffix_rgb",  "_RGB"))

        self._fill_corner_vars(self._odd_vars,  s.get("odd_corners",  DEFAULT_SETTINGS["odd_corners"]))
        self._fill_corner_vars(self._even_vars, s.get("even_corners", DEFAULT_SETTINGS["even_corners"]))

        self._icc_use_var.set(s.get("use_icc_profile", True))
        for cs_key, _, settings_key in _ICC_SPACES:
            saved_name = s.get(settings_key, "")
            profiles   = get_profiles(cs_key)
            if saved_name and saved_name in profiles:
                self._icc_vars[cs_key].set(saved_name)
            elif profiles:
                self._icc_vars[cs_key].set(profiles[0])
            else:
                self._icc_vars[cs_key].set(_EMPTY_PROFILE)

        if self._icc_menus:
            self._on_icc_toggle()

    def get_settings(self) -> dict:
        """Зчитує всі поля форми і повертає словник налаштувань."""
        icc_selections = {
            settings_key: (
                self._icc_vars[cs_key].get()
                if self._icc_vars[cs_key].get() != _EMPTY_PROFILE else ""
            )
            for cs_key, _, settings_key in _ICC_SPACES
        }
        return {
            "dpi":                int(self._dpi_var.get()),
            "odd_corners":        self._read_corner_vars(self._odd_vars),
            "even_corners":       self._read_corner_vars(self._even_vars),
            "output_suffix_cmyk": self._suffix_cmyk_var.get() or "_CMYK",
            "output_suffix_gray": self._suffix_gray_var.get() or "_GRAY",
            "output_suffix_rgb":  self._suffix_rgb_var.get()  or "_RGB",
            "use_icc_profile":    self._icc_use_var.get(),
            **icc_selections,
        }

    def on_run(self, mode: str) -> None:
        """
        Зберігає налаштування та запускає обробку PDF у фоновому потоці.

        :param mode: «cmyk», «grayscale», «rgb», «cmyk_warp», «grayscale_warp», «rgb_warp».
        """
        pdf_path = self._current_pdf_path()

        if not pdf_path:
            messagebox.showwarning(
                "Файл не обрано",
                "Будь ласка, додайте PDF-файл за допомогою кнопки «⊕ Додати».",
                parent=self,
            )
            return

        if not Path(pdf_path).exists():
            messagebox.showerror(
                "Файл не знайдено",
                f"Не вдалось знайти файл:\n{pdf_path}",
                parent=self,
            )
            return

        settings = self.get_settings()
        try:
            save_settings(settings)
        except Exception as exc:
            messagebox.showerror("Помилка збереження", str(exc), parent=self)
            return

        base_mode = mode.removesuffix("_warp")
        suffix_map = {
            "cmyk":      settings["output_suffix_cmyk"],
            "grayscale": settings["output_suffix_gray"],
            "rgb":       settings["output_suffix_rgb"],
        }
        suffix = suffix_map.get(base_mode, settings["output_suffix_cmyk"])

        icc_cs_map = {
            "cmyk":      ("cmyk", "icc_profile_cmyk"),
            "grayscale": ("gray", "icc_profile_gray"),
            "rgb":       ("rgb",  "icc_profile_rgb"),
        }
        icc_path: Path | None = None
        if settings.get("use_icc_profile"):
            cs_key, settings_key = icc_cs_map.get(base_mode, ("cmyk", "icc_profile_cmyk"))
            profile_name = settings.get(settings_key, "")
            if profile_name:
                candidate = ICC_DIR / cs_key / profile_name
                if candidate.exists():
                    icc_path = candidate
                else:
                    print(f"[gui] УВАГА: профіль не знайдено: {candidate}")

        self._set_status(f"Обробка: {Path(pdf_path).name}  [{mode}]…")

        def _worker() -> None:
            try:
                out = process_pdf(
                    pdf_path=pdf_path,
                    mode=mode,
                    dpi=settings["dpi"],
                    odd_corners=settings["odd_corners"],
                    even_corners=settings["even_corners"],
                    output_suffix=suffix,
                    icc_path=icc_path,
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
        for key, *_ in _CORNER_FIELDS:
            vals = corners_data.get(key, [0.0, 0.0])
            var_dict[key][0].set(str(vals[0]))
            var_dict[key][1].set(str(vals[1]))

    @staticmethod
    def _read_corner_vars(
        var_dict: dict[str, list[ctk.StringVar]],
    ) -> dict[str, list[float]]:
        return {
            key: [_parse_float(var_dict[key][0].get()), _parse_float(var_dict[key][1].get())]
            for key, *_ in _CORNER_FIELDS
        }

    @staticmethod
    def _darken(hex_color: str, factor: float = 0.75) -> str:
        hex_color = hex_color.lstrip("#")
        r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return "#{:02x}{:02x}{:02x}".format(int(r * factor), int(g * factor), int(b * factor))

    def _set_status(self, text: str) -> None:
        """Оновлює текст статус-рядка (завжди викликається з основного потоку)."""
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
