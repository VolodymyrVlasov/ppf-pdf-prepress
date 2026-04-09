"""
gui.py — Вікно налаштувань PDF Pre-Press Processor.

Макет: 3 колонки, responsive grid.
  Рядок 0 — вибір файлів (повна ширина)
  Рядок 1 — FRONT-кути | BACK-кути | Попередній перегляд
  Рядок 2 — Tabbed settings (cols 0-1) | Панель запуску (col 2)
  Рядок 3 — прогрес (спінер + рядок статусу + лічильник)
  Рядок 4 — статус-рядок
"""

import math
import os
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from settings import load_settings, save_settings, DEFAULT_SETTINGS
from processor import process_pdf, get_profiles, ICC_DIR


# ---------------------------------------------------------------------------
# Тема — єдине місце для всіх кольорів та шрифтів
# ---------------------------------------------------------------------------

FONT = "Helvetica"

THEME: dict = {
    # Фони
    "window_bg":         "#B1B1B1",
    "card_bg":           "#FFFFFF",
    "card_border":       "#FFFFFF",
    "card_radius":       4,
    # Акцент (нейтральний сірий — замість синього)
    "accent":            "#555555",
    "accent_hover":      "#444444",
    "accent_light":      "#E8E8E8",
    # Дропдауни (світло-сірий фон)
    "combo_fg":          "#F5F5F5",
    "combo_border":      "#BFBFBF",
    "combo_btn":         "#F5F5F5",
    "combo_btn_hover":   "#E8E8E8",
    "combo_dd_fg":       "#F5F5F5",
    "combo_dd_hover":    "#E8E8E8",
    "combo_dd_text":     "#1A1A1A",
    # Текст
    "title_color":       "#1A1A1A",
    "hint_color":        "#888888",
    # Поля вводу
    "entry_border":      "#BFBFBF",
    "entry_focus":       "#555555",
    # Кнопки запуску
    "run_fg":            "#2E7D32",
    "run_hover":         "#388E3C",
    "stop_fg":           "#C62828",
    "stop_hover":        "#D32F2F",
    # Вкладки (кастомні)
    "tab_active_bg":     "#FFFFFF",
    "tab_active_text":   "#1A1A1A",
    "tab_inactive_bg":   "#EFEFEF",
    "tab_inactive_text": "#616161",
    "tab_hover":         "#E4E4E4",
    # Шрифти: (family, size[, weight])
    "font_title":        (FONT, 20, "bold"),
    "font_normal":       (FONT, 16 ),
    "font_small":        (FONT, 14),
    "font_button":       (FONT, 16, "bold"),
}

WINDOW_TITLE = "PDF Pre-Press — Налаштування"
WINDOW_SIZE  = "1100x700"
PAD          = 12
IPAD         = 10
ENTRY_W      = 70
LABEL_W      = 90

_MODES: list[tuple[str, str]] = [
    ("CMYK",                   "cmyk"),
    ("CMYK + деформація",      "cmyk_warp"),
    ("Grayscale",              "grayscale"),
    ("Grayscale + деформація", "grayscale_warp"),
    ("RGB",                    "rgb"),
    ("RGB + деформація",       "rgb_warp"),
]
_MODE_DISPLAY     = [d for d, _ in _MODES]
_MODE_DISP_TO_KEY = {d: k for d, k in _MODES}

_CORNER_FIELDS = [
    ("tl", 0, "Верх-лів X",  "Верх-лів Y"),
    ("tr", 1, "Верх-прав X", "Верх-прав Y"),
    ("bl", 2, "Низ-лів X",   "Низ-лів Y"),
    ("br", 3, "Низ-прав X",  "Низ-прав Y"),
]

DPI_OPTIONS    = ["150", "300", "600"]
_EMPTY_PROFILE = "— не знайдено —"
_NO_FILES      = "— файли не обрано —"

_ICC_SPACES: list[tuple[str, str, str]] = [
    ("cmyk", "CMYK",      "icc_profile_cmyk"),
    ("rgb",  "RGB",       "icc_profile_rgb"),
    ("gray", "Grayscale", "icc_profile_gray"),
]

_INTERP_OPTIONS: list[tuple[str, str]] = [
    ("Lanczos (найкраща якість)",  "INTER_LANCZOS4"),
    ("Cubic (висока якість)",       "INTER_CUBIC"),
    ("Linear (стандартна)",         "INTER_LINEAR"),
    ("Nearest (без згладжування)", "INTER_NEAREST"),
]
_INTERP_DISPLAY_TO_KEY = {d: k for d, k in _INTERP_OPTIONS}
_INTERP_KEY_TO_DISPLAY = {k: d for d, k in _INTERP_OPTIONS}
_INTERP_DISPLAY_NAMES  = [d for d, _ in _INTERP_OPTIONS]

_COMPRESSION_OPTIONS: list[tuple[str, str]] = [
    ("TIFF LZW (без втрат)",      "tiff_lzw"),
    ("TIFF Deflate (без втрат)",  "tiff_deflate"),
    ("Без стиснення (найшвидше)", "none"),
]
_COMPRESSION_DISPLAY_TO_KEY = {d: k for d, k in _COMPRESSION_OPTIONS}
_COMPRESSION_KEY_TO_DISPLAY = {k: d for d, k in _COMPRESSION_OPTIONS}
_COMPRESSION_DISPLAY_NAMES  = [d for d, _ in _COMPRESSION_OPTIONS]

_TAB_NAMES = ["Растрування", "Суфікси", "ICC профілі"]


# ---------------------------------------------------------------------------
# Допоміжні функції
# ---------------------------------------------------------------------------

def _parse_float(val: str, default: float = 0.0) -> float:
    try:
        return float(val.replace(",", "."))
    except (ValueError, AttributeError):
        return default


def _font(*args) -> ctk.CTkFont:
    return ctk.CTkFont(*args)


def _card(parent, **kwargs) -> ctk.CTkFrame:
    """CTkFrame у стилі білої картки з рамкою."""
    return ctk.CTkFrame(
        parent,
        fg_color=THEME["card_bg"],
        border_width=1,
        border_color=THEME["card_border"],
        corner_radius=THEME["card_radius"],
        **kwargs,
    )


def _title_label(parent, text: str) -> ctk.CTkLabel:
    lbl = ctk.CTkLabel(
        parent, text=text,
        font=_font(*THEME["font_title"]),
        text_color=THEME["title_color"],
        anchor="w",
    )
    lbl.pack(fill="x", padx=IPAD, pady=(IPAD, 4))
    return lbl


def apply_hover(widget, normal_color: str, hover_color: str) -> None:
    """Анімація hover: зміна border_color при наведенні (CTkEntry, CTkComboBox)."""
    widget.bind("<Enter>",
                lambda _: widget.configure(border_color=hover_color), add="+")
    widget.bind("<Leave>",
                lambda _: widget.configure(border_color=normal_color), add="+")


def _make_optionmenu(parent, variable, values, width=None, **kwargs) -> ctk.CTkOptionMenu:
    """CTkOptionMenu зі стандартними стилями теми (CHANGE 3: light-gray bg)."""
    opts: dict = dict(
        fg_color=THEME["combo_fg"],
        text_color=THEME["combo_dd_text"],
        button_color=THEME["combo_btn"],
        button_hover_color=THEME["combo_btn_hover"],
        dropdown_fg_color=THEME["combo_dd_fg"],
        dropdown_hover_color=THEME["combo_dd_hover"],
        dropdown_text_color=THEME["combo_dd_text"],
        font=_font(*THEME["font_normal"]),
        dropdown_font=_font(*THEME["font_normal"]),
    )
    opts.update(kwargs)
    if width is not None:
        opts["width"] = width
    return ctk.CTkOptionMenu(parent, variable=variable, values=values, **opts)


# ---------------------------------------------------------------------------
# Анімований спінер
# ---------------------------------------------------------------------------

class SpinnerCanvas(tk.Canvas):
    SEGMENTS = 8

    def __init__(self, parent, size: int = 28, **kwargs) -> None:
        super().__init__(
            parent,
            width=size, height=size,
            bg=THEME["card_bg"],
            highlightthickness=0,
            **kwargs,
        )
        self._size     = size
        self._angle    = 0
        self._running  = False
        self._after_id = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._animate()

    def stop(self) -> None:
        self._running = False
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self.delete("all")

    def _animate(self) -> None:
        if not self._running:
            return
        self.delete("all")
        cx = cy   = self._size / 2
        r_orbit   = self._size / 2 - 4
        r_dot     = max(2, self._size // 10)
        for i in range(self.SEGMENTS):
            dist       = (self._angle - i) % self.SEGMENTS
            brightness = int(55 + 200 * dist / max(self.SEGMENTS - 1, 1))
            color      = "#{0:02x}{0:02x}{0:02x}".format(brightness)
            angle_rad  = math.pi * 2 * i / self.SEGMENTS - math.pi / 2
            x = cx + r_orbit * math.cos(angle_rad)
            y = cy + r_orbit * math.sin(angle_rad)
            self.create_oval(x - r_dot, y - r_dot, x + r_dot, y + r_dot,
                             fill=color, outline="")
        self._angle    = (self._angle + 1) % self.SEGMENTS
        self._after_id = self.after(80, self._animate)


# ---------------------------------------------------------------------------
# Попередній перегляд деформації (responsive)
# ---------------------------------------------------------------------------

class WarpPreviewCanvas(tk.Canvas):
    PAGE_W     = 100
    PAGE_H     = 141
    COLOR_ODD  = "#4A8FD4"
    COLOR_EVEN = "#E07B20"

    def __init__(
        self,
        parent,
        odd_vars:  dict[str, list[ctk.StringVar]],
        even_vars: dict[str, list[ctk.StringVar]],
        **kwargs,
    ) -> None:
        super().__init__(
            parent,
            bg=THEME["card_bg"],
            highlightthickness=1,
            highlightbackground=THEME["card_border"],
            **kwargs,
        )
        self._odd_vars     = odd_vars
        self._even_vars    = even_vars
        self._single_sided = False

        for var_dict in (odd_vars, even_vars):
            for key, *_ in _CORNER_FIELDS:
                for sv in var_dict[key]:
                    sv.trace_add("write", self._on_var_change)

        self.bind("<Configure>", self._on_resize)

    def set_single_sided(self, single: bool) -> None:
        self._single_sided = single
        self.update_preview()

    def _on_var_change(self, *_) -> None:
        self.update_preview()

    def _on_resize(self, _=None) -> None:
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
        cx: float, cy: float,
        corners_mm: dict[str, tuple[float, float]] | None,
        color: str, orig_color: str,
        scale: float = 1.0,
    ) -> None:
        hw = self.PAGE_W * scale / 2
        hh = self.PAGE_H * scale / 2
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
                    orig[key][0] + corners_mm[key][0] * scale,
                    orig[key][1] + corners_mm[key][1] * scale,
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
        self.delete("all")

        w = max(self.winfo_width(),  120)
        h = max(self.winfo_height(), 80)

        margin  = 16
        gap     = 16
        label_h = 20

        scale_x = (w - margin * 2 - gap) / (2 * self.PAGE_W)
        scale_y = (h - margin * 2 - label_h) / self.PAGE_H
        scale   = max(0.3, min(scale_x, scale_y, 2.0))

        cy = (h - label_h) / 2
        left_cx  = w // 4
        right_cx = 3 * w // 4

        orig_color = "#b0b0b0"
        div_color  = "#c8c8c8"

        mid = w // 2
        self.create_line(mid, 8, mid, h - 8, fill=div_color, dash=(3, 5), width=1)

        odd_corners  = self._read_corners(self._odd_vars)
        even_corners = self._read_corners(self._even_vars)
        back_color   = "#606060" if self._single_sided else self.COLOR_EVEN

        self._draw_page(left_cx, cy, odd_corners, self.COLOR_ODD, orig_color, scale)
        self.create_text(
            left_cx, cy + self.PAGE_H * scale / 2 + 10,
            text="FRONT", fill=self.COLOR_ODD, font=(FONT, 9, "bold"),
        )
        self._draw_page(right_cx, cy, even_corners, back_color, orig_color, scale)
        self.create_text(
            right_cx, cy + self.PAGE_H * scale / 2 + 10,
            text="BACK", fill=back_color, font=(FONT, 9, "bold"),
        )


# ---------------------------------------------------------------------------
# Головне вікно
# ---------------------------------------------------------------------------

class SettingsWindow(ctk.CTk):

    def __init__(self, pdf_path: str | None = None) -> None:
        super().__init__()

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("green")
        self.configure(fg_color=THEME["window_bg"])

        self.title(WINDOW_TITLE)
        self.resizable(True, True)
        self.minsize(900, 600)

        # Відновлення розміру вікна
        s = load_settings()
        geom = s.get("window_geometry", WINDOW_SIZE)
        try:
            self.geometry(geom)
        except Exception:
            self.geometry(WINDOW_SIZE)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # ---- Стан файлів ----
        self._file_paths: list[str] = []
        self._file_combo_var = ctk.StringVar(value=_NO_FILES)
        self._file_combo: ctk.CTkComboBox
        self._last_output_folder: str = s.get("last_output_folder", "")

        # ---- Змінні форми ----
        self._dpi_var         = ctk.StringVar(value="300")
        self._suffix_cmyk_var = ctk.StringVar(value="_CMYK")
        self._suffix_gray_var = ctk.StringVar(value="_GRAY")
        self._suffix_rgb_var  = ctk.StringVar(value="_RGB")
        self._interp_var      = ctk.StringVar(value=_INTERP_DISPLAY_NAMES[0])
        self._compression_var = ctk.StringVar(value=_COMPRESSION_DISPLAY_NAMES[0])
        self._mode_var        = ctk.StringVar(value=_MODE_DISPLAY[0])

        # Кутові зміщення
        self._odd_vars:  dict[str, list[ctk.StringVar]] = self._make_corner_vars()
        self._even_vars: dict[str, list[ctk.StringVar]] = self._make_corner_vars()

        # ICC-профілі
        self._icc_use_var = ctk.BooleanVar(value=True)
        self._icc_vars:  dict[str, ctk.StringVar]     = {cs: ctk.StringVar() for cs, *_ in _ICC_SPACES}
        self._icc_menus: dict[str, ctk.CTkOptionMenu] = {}

        # Режим друку
        self._print_mode_var      = ctk.StringVar(value="double")
        self._back_entry_widgets: list = []

        # Стан обробки
        self._stop_event: threading.Event | None = None
        self._processing = False

        # Авто-відкриття файлу після обробки
        self._auto_open_var = ctk.BooleanVar(value=True)

        # Стан вкладок
        self._tab_btns:       dict[str, ctk.CTkButton] = {}
        self._tab_indicators: dict[str, ctk.CTkFrame]  = {}
        self._tab_frames:     dict[str, ctk.CTkFrame]  = {}
        self._active_tab: str = _TAB_NAMES[0]

        # ---- Побудова UI ----
        self._build_ui()

        # ---- Завантаження налаштувань ----
        self.load_settings()

        # ---- Попереднє завантаження файлу з CLI ----
        if pdf_path and Path(pdf_path).exists():
            self._add_file(pdf_path)

    # -----------------------------------------------------------------------
    # Закриття вікна — збереження геометрії
    # -----------------------------------------------------------------------

    def _on_close(self) -> None:
        try:
            s = load_settings()
            s["window_geometry"] = self.geometry()
            save_settings(s)
        except Exception:
            pass
        self.destroy()

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
        if not self._file_paths:
            return None
        val = self._file_combo_var.get()
        if val == _NO_FILES:
            return None
        try:
            idx = int(val.split(".")[0]) - 1
            return self._file_paths[idx] if 0 <= idx < len(self._file_paths) else None
        except (ValueError, IndexError):
            return None

    def _refresh_file_combo(self, select_idx: int = 0) -> None:
        if not self._file_paths:
            self._file_combo.configure(values=[_NO_FILES])
            self._file_combo_var.set(_NO_FILES)
            return
        display = [f"{i + 1}. {Path(p).name}" for i, p in enumerate(self._file_paths)]
        self._file_combo.configure(values=display)
        idx = max(0, min(select_idx, len(display) - 1))
        self._file_combo_var.set(display[idx])

    def _add_file(self, path: str) -> None:
        if path not in self._file_paths:
            self._file_paths.append(path)
        self._refresh_file_combo(self._file_paths.index(path))

    def _on_add_files(self) -> None:
        s = load_settings()
        init_dir = s.get("last_open_folder") or s.get("last_folder", "")
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

        s["last_open_folder"] = str(Path(paths[0]).parent)
        save_settings(s)
        self._refresh_file_combo(len(self._file_paths) - 1)

    def _on_open_folder(self) -> None:
        folder = None
        if self._last_output_folder and Path(self._last_output_folder).exists():
            folder = self._last_output_folder
        else:
            path = self._current_pdf_path()
            if path:
                folder = str(Path(path).parent)
        if folder:
            subprocess.Popen(["explorer", folder])

    # -----------------------------------------------------------------------
    # Побудова інтерфейсу
    # -----------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=0)

        self._build_file_picker()
        self._build_corners_row()
        self._build_settings_row()
        self._build_progress_panel()
        self._build_status_bar()

    # ---- Статус-рядок (row 4) ----

    def _build_status_bar(self) -> None:
        self._status_lbl = ctk.CTkLabel(
            self, text="", anchor="w",
            font=_font(*THEME["font_small"]),
            fg_color="#E8E8E8",
            corner_radius=0,
            height=22,
        )
        self._status_lbl.grid(row=4, column=0, sticky="ew")

    # ---- Вибір файлів (row 0) ----

    def _build_file_picker(self) -> None:
        frame = _card(self)
        frame.grid(row=0, column=0, sticky="ew", padx=PAD, pady=(PAD, 6))
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            frame, text="Файли:",
            font=_font(*THEME["font_normal"]),
            text_color=THEME["title_color"],
            width=55, anchor="w",
        ).grid(row=0, column=0, padx=(IPAD, 4), pady=10)

        self._file_combo = ctk.CTkComboBox(
            frame,
            variable=self._file_combo_var,
            values=[_NO_FILES],
            fg_color=THEME["combo_fg"],
            border_color=THEME["combo_border"],
            border_width=1,
            button_color=THEME["combo_btn"],
            button_hover_color=THEME["combo_btn_hover"],
            dropdown_fg_color=THEME["combo_dd_fg"],
            dropdown_text_color=THEME["combo_dd_text"],
            font=_font(*THEME["font_normal"]),
            dropdown_font=_font(*THEME["font_normal"]),
        )
        self._file_combo.grid(row=0, column=1, padx=(4, 4), pady=10, sticky="ew")
        apply_hover(self._file_combo, THEME["combo_border"], THEME["entry_focus"])

        ctk.CTkButton(
            frame, text="⊕ Додати", width=90,
            fg_color=THEME["accent"],
            hover_color=THEME["accent_hover"],
            font=_font(*THEME["font_button"]),
            command=self._on_add_files,
        ).grid(row=0, column=2, padx=4, pady=10)

        folder_btn = ctk.CTkButton(
            frame, text="📁", width=38,
            fg_color=THEME["card_bg"],
            text_color=THEME["title_color"],
            border_width=1,
            border_color=THEME["combo_border"],
            hover_color=THEME["combo_btn_hover"],
            font=_font(*THEME["font_normal"]),
            command=self._on_open_folder,
        )
        folder_btn.grid(row=0, column=3, padx=(4, IPAD), pady=10)
        self._bind_tooltip(folder_btn, "Відкрити папку збереженого файлу")

    # ---- Рядок кутів (row 1) ----

    def _build_corners_row(self) -> None:
        row_frame = ctk.CTkFrame(self, fg_color=THEME["window_bg"])
        row_frame.grid(row=1, column=0, sticky="nsew", padx=PAD, pady=(0, 6))
        row_frame.grid_columnconfigure(0, weight=1, uniform="corners")
        row_frame.grid_columnconfigure(1, weight=1, uniform="corners")
        row_frame.grid_columnconfigure(2, weight=1, uniform="corners")
        row_frame.grid_rowconfigure(0, weight=0)
        row_frame.grid_rowconfigure(1, weight=1)

        self._build_print_mode_header(row_frame)

        self._build_corners_panel(
            row_frame, col=0, grid_row=1,
            title="Деформація — Непарні (FRONT)",
            var_dict=self._odd_vars,
        )
        even_entries = self._build_corners_panel(
            row_frame, col=1, grid_row=1,
            title="Деформація — Парні (BACK)",
            var_dict=self._even_vars,
            add_hint=True,
        )
        self._back_entry_widgets = even_entries
        self._build_preview_panel(row_frame, col=2)

    # ---- Рядок налаштувань (row 2) ----

    def _build_settings_row(self) -> None:
        row_frame = ctk.CTkFrame(self, fg_color=THEME["window_bg"])
        row_frame.grid(row=2, column=0, sticky="nsew", padx=PAD, pady=(0, 6))
        row_frame.grid_columnconfigure(0, weight=3)
        row_frame.grid_columnconfigure(1, weight=3)
        row_frame.grid_columnconfigure(2, weight=2)
        row_frame.grid_rowconfigure(0, weight=1)

        self._build_tabbed_settings(row_frame)
        self._build_launch_panel(row_frame, col=2)

    # ---- Панель прогресу (row 3) ----

    def _build_progress_panel(self) -> None:
        self._progress_frame = _card(self)
        self._progress_frame.grid(row=3, column=0, sticky="ew", padx=PAD, pady=(0, 4))
        self._progress_frame.grid_columnconfigure(1, weight=1)

        self._spinner = SpinnerCanvas(self._progress_frame, size=24)
        self._spinner.grid(row=0, column=0, padx=(IPAD, 8), pady=8)

        self._progress_status_lbl = ctk.CTkLabel(
            self._progress_frame,
            text="Очікування...",
            anchor="w",
            font=_font(*THEME["font_normal"]),
            text_color=THEME["hint_color"],
        )
        self._progress_status_lbl.grid(row=0, column=1, sticky="ew", pady=8)

        self._page_counter_lbl = ctk.CTkLabel(
            self._progress_frame,
            text="", anchor="e", width=160,
            font=_font(*THEME["font_normal"]),
            text_color=THEME["hint_color"],
        )
        self._page_counter_lbl.grid(row=0, column=2, padx=(8, IPAD), pady=8)

    # -----------------------------------------------------------------------
    # Заголовок режиму друку
    # -----------------------------------------------------------------------

    def _build_print_mode_header(self, parent) -> None:
        frame = _card(parent)
        frame.grid(row=0, column=0, columnspan=2, sticky="ew",
                   padx=(0, 6), pady=(0, 4))

        ctk.CTkLabel(
            frame, text="Режим друку:",
            font=_font(*THEME["font_title"]),
            text_color=THEME["title_color"],
            anchor="w",
        ).pack(side="left", padx=(IPAD, 12), pady=8)

        ctk.CTkRadioButton(
            frame, text="1-ст друк",
            variable=self._print_mode_var, value="single",
            font=_font(*THEME["font_normal"]),
            hover_color=THEME["accent_light"],
        ).pack(side="left", padx=(0, 20), pady=8)

        ctk.CTkRadioButton(
            frame, text="2-ст друк",
            variable=self._print_mode_var, value="double",
            font=_font(*THEME["font_normal"]),
            hover_color=THEME["accent_light"],
        ).pack(side="left", pady=8)

        self._print_mode_var.trace_add("write", self._on_print_mode_change)

    # -----------------------------------------------------------------------
    # Панель кутів
    # -----------------------------------------------------------------------

    def _build_corners_panel(
        self,
        parent,
        col: int,
        title: str,
        var_dict: dict[str, list[ctk.StringVar]],
        grid_row: int = 0,
        add_hint: bool = False,
    ) -> list:
        frame = _card(parent)
        frame.grid(row=grid_row, column=col, sticky="nsew",
                   padx=(0, 6) if col < 2 else 0, pady=4)

        _title_label(frame, title)

        ctk.CTkLabel(
            frame,
            text="Зміщення кутів у мм  (+ назовні,  − всередину)",
            anchor="w",
            font=_font(*THEME["font_small"]),
            text_color=THEME["hint_color"],
        ).pack(fill="x", padx=IPAD, pady=(0, 6))

        grid = ctk.CTkFrame(frame, fg_color="transparent")
        grid.pack(fill="x", padx=IPAD, pady=(0, IPAD))

        for c_idx, txt in enumerate(("", "X (мм)", "Y (мм)")):
            ctk.CTkLabel(
                grid, text=txt,
                width=LABEL_W if c_idx == 0 else ENTRY_W,
                anchor="center",
                font=_font(*THEME["font_small"]),
                text_color=THEME["title_color"],
            ).grid(row=0, column=c_idx, padx=(0, 4), pady=(0, 2))

        entries = []
        for row_idx, (key, _, lbl_x, _) in enumerate(_CORNER_FIELDS, start=1):
            corner_name = lbl_x.rsplit(" ", 1)[0]
            ctk.CTkLabel(
                grid, text=corner_name, width=LABEL_W, anchor="w",
                font=_font(*THEME["font_normal"]),
                text_color=THEME["title_color"],
            ).grid(row=row_idx, column=0, padx=(0, 4), pady=2)

            ex = ctk.CTkEntry(
                grid, textvariable=var_dict[key][0],
                width=ENTRY_W, justify="center",
                fg_color=THEME["card_bg"],
                border_color=THEME["entry_border"],
                border_width=1,
                font=_font(*THEME["font_normal"]),
            )
            ex.grid(row=row_idx, column=1, padx=(0, 4), pady=2)
            apply_hover(ex, THEME["entry_border"], THEME["entry_focus"])

            ey = ctk.CTkEntry(
                grid, textvariable=var_dict[key][1],
                width=ENTRY_W, justify="center",
                fg_color=THEME["card_bg"],
                border_color=THEME["entry_border"],
                border_width=1,
                font=_font(*THEME["font_normal"]),
            )
            ey.grid(row=row_idx, column=2, pady=2)
            apply_hover(ey, THEME["entry_border"], THEME["entry_focus"])

            entries.extend([ex, ey])

        if add_hint:
            self._back_hint_lbl = ctk.CTkLabel(
                frame,
                text="Всі сторінки обробляються зі значеннями FRONT",
                font=_font(*THEME["font_small"]),
                text_color=THEME["hint_color"],
                anchor="w",
            )

        return entries

    # -----------------------------------------------------------------------
    # Панель попереднього перегляду
    # -----------------------------------------------------------------------

    def _build_preview_panel(self, parent, col: int) -> None:
        frame = _card(parent)
        frame.grid(row=0, column=col, rowspan=2, sticky="nsew", pady=4)

        _title_label(frame, "Попередній перегляд деформації")

        canvas_wrap = ctk.CTkFrame(frame, fg_color=THEME["card_bg"])
        canvas_wrap.pack(fill="both", expand=True, padx=IPAD, pady=(0, 4))

        self._preview = WarpPreviewCanvas(
            canvas_wrap,
            odd_vars=self._odd_vars,
            even_vars=self._even_vars,
        )
        self._preview.pack(fill="both", expand=True)

        legend = ctk.CTkFrame(frame, fg_color=THEME["card_bg"])
        legend.pack(pady=(2, IPAD))

        ctk.CTkLabel(legend, text="- - -  оригінал",
                     font=_font(*THEME["font_small"]),
                     text_color=THEME["hint_color"]).pack(side="left", padx=(0, 14))
        ctk.CTkLabel(legend, text="——  FRONT",
                     font=_font(*THEME["font_small"]),
                     text_color=WarpPreviewCanvas.COLOR_ODD).pack(side="left", padx=(0, 14))
        ctk.CTkLabel(legend, text="——  BACK",
                     font=_font(*THEME["font_small"]),
                     text_color=WarpPreviewCanvas.COLOR_EVEN).pack(side="left")

    # -----------------------------------------------------------------------
    # CHANGE 4 — Кастомна картка з вкладками
    # -----------------------------------------------------------------------

    def _build_tabbed_settings(self, parent) -> None:
        outer = _card(parent)
        outer.grid(row=0, column=0, columnspan=2, sticky="nsew",
                   padx=(0, 6), pady=4)
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(0, weight=0)  # tab bar
        outer.grid_rowconfigure(1, weight=1)  # content

        # ── Tab bar ──────────────────────────────────────────────
        tab_bar = ctk.CTkFrame(outer, fg_color=THEME["card_bg"], corner_radius=0,
                               border_width=0)
        tab_bar.grid(row=0, column=0, sticky="ew")
        for i in range(len(_TAB_NAMES)):
            tab_bar.grid_columnconfigure(i, weight=1)

        for i, name in enumerate(_TAB_NAMES):
            col_frame = ctk.CTkFrame(tab_bar, fg_color=THEME["card_bg"],
                                     corner_radius=0, border_width=0)
            col_frame.grid(row=0, column=i, sticky="nsew")
            col_frame.grid_rowconfigure(0, weight=1)
            col_frame.grid_rowconfigure(1, weight=0)
            col_frame.grid_columnconfigure(0, weight=1)

            btn = ctk.CTkButton(
                col_frame,
                text=name,
                fg_color=THEME["tab_inactive_bg"],
                text_color=THEME["tab_inactive_text"],
                hover_color=THEME["tab_hover"],
                corner_radius=0,
                border_width=0,
                font=_font(*THEME["font_normal"]),
                command=lambda n=name: self._on_tab_click(n),
            )
            btn.grid(row=0, column=0, sticky="ew", ipady=6)
            self._tab_btns[name] = btn

            indicator = ctk.CTkFrame(col_frame, height=2,
                                     fg_color="transparent", corner_radius=0)
            indicator.grid(row=1, column=0, sticky="ew")
            self._tab_indicators[name] = indicator

        # Separator line below tab bar
        ctk.CTkFrame(outer, height=1, fg_color=THEME["card_border"],
                     corner_radius=0).grid(row=0, column=0, sticky="sew",
                                            padx=0, pady=0)

        # ── Content area ─────────────────────────────────────────
        content = ctk.CTkFrame(outer, fg_color=THEME["card_bg"], corner_radius=0,
                               border_width=0)
        content.grid(row=1, column=0, sticky="nsew")
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)

        for name in _TAB_NAMES:
            frame = ctk.CTkFrame(content, fg_color=THEME["card_bg"],
                                 corner_radius=0, border_width=0)
            frame.grid(row=0, column=0, sticky="nsew")
            self._tab_frames[name] = frame

        self._build_tab_rasterization(self._tab_frames["Растрування"])
        self._build_tab_suffixes(self._tab_frames["Суфікси"])
        self._build_tab_icc(self._tab_frames["ICC профілі"])

        self._on_tab_click(_TAB_NAMES[0])

    def _on_tab_click(self, tab_name: str) -> None:
        self._active_tab = tab_name
        for name, btn in self._tab_btns.items():
            is_active = (name == tab_name)
            btn.configure(
                fg_color=THEME["tab_active_bg"] if is_active else THEME["tab_inactive_bg"],
                text_color=THEME["tab_active_text"] if is_active else THEME["tab_inactive_text"],
                font=_font(FONT, 13, "bold") if is_active else _font(FONT, 13),
            )
            self._tab_indicators[name].configure(
                fg_color=THEME["title_color"] if is_active else "transparent"
            )
        for name, frame in self._tab_frames.items():
            if name == tab_name:
                frame.grid()
            else:
                frame.grid_remove()

    # ── Tab: Растрування ─────────────────────────────────────────

    def _build_tab_rasterization(self, tab) -> None:
        row = ctk.CTkFrame(tab, fg_color="transparent")
        row.pack(fill="x", padx=IPAD, pady=(IPAD, 4))
        ctk.CTkLabel(row, text="Роздільна здатність (DPI)", anchor="w",
                     font=_font(*THEME["font_normal"]),
                     text_color=THEME["title_color"]).pack(side="left")
        _make_optionmenu(row, self._dpi_var, DPI_OPTIONS, width=90).pack(side="right")

        row2 = ctk.CTkFrame(tab, fg_color="transparent")
        row2.pack(fill="x", padx=IPAD, pady=(0, 2))
        ctk.CTkLabel(row2, text="Інтерполяція деформації", anchor="w",
                     font=_font(*THEME["font_normal"]),
                     text_color=THEME["title_color"]).pack(side="left")
        _make_optionmenu(row2, self._interp_var, _INTERP_DISPLAY_NAMES,
                         width=210).pack(side="right")

        ctk.CTkLabel(
            tab,
            text="Впливає лише на режими з деформацією. Lanczos рекомендовано для тексту.",
            font=_font(*THEME["font_small"]),
            text_color=THEME["hint_color"],
            anchor="w",
        ).pack(fill="x", padx=IPAD, pady=(0, 6))

        row3 = ctk.CTkFrame(tab, fg_color="transparent")
        row3.pack(fill="x", padx=IPAD, pady=(0, IPAD))
        ctk.CTkLabel(row3, text="Стиснення проміжних файлів", anchor="w",
                     font=_font(*THEME["font_normal"]),
                     text_color=THEME["title_color"]).pack(side="left")
        _make_optionmenu(row3, self._compression_var, _COMPRESSION_DISPLAY_NAMES,
                         width=210).pack(side="right")

    # ── Tab: Суфікси ─────────────────────────────────────────────

    def _build_tab_suffixes(self, tab) -> None:
        suffix_grid = ctk.CTkFrame(tab, fg_color="transparent")
        suffix_grid.pack(fill="x", padx=IPAD, pady=IPAD)

        for row_idx, (label, var) in enumerate([
            ("Суфікс CMYK",      self._suffix_cmyk_var),
            ("Суфікс Grayscale", self._suffix_gray_var),
            ("Суфікс RGB",       self._suffix_rgb_var),
        ]):
            ctk.CTkLabel(suffix_grid, text=label, anchor="w", width=140,
                         font=_font(*THEME["font_normal"]),
                         text_color=THEME["title_color"]).grid(
                row=row_idx, column=0, padx=(0, 8), pady=4, sticky="w")
            entry = ctk.CTkEntry(
                suffix_grid, textvariable=var, width=120,
                fg_color=THEME["card_bg"],
                border_color=THEME["entry_border"],
                border_width=1,
                font=_font(*THEME["font_normal"]),
            )
            entry.grid(row=row_idx, column=1, pady=4, sticky="w")
            apply_hover(entry, THEME["entry_border"], THEME["entry_focus"])

    # ── Tab: ICC профілі ──────────────────────────────────────────

    def _build_tab_icc(self, tab) -> None:
        ctk.CTkCheckBox(
            tab,
            text="Призначати ICC профіль (embed)",
            variable=self._icc_use_var,
            command=self._on_icc_toggle,
            font=_font(*THEME["font_normal"]),
            text_color=THEME["title_color"],
            checkmark_color=THEME["accent"],
            hover_color=THEME["accent_light"],
        ).pack(anchor="w", padx=IPAD, pady=(IPAD, 6))

        icc_grid = ctk.CTkFrame(tab, fg_color="transparent")
        icc_grid.pack(fill="x", padx=IPAD, pady=(0, 4))
        icc_grid.grid_columnconfigure(1, weight=1)

        for row_idx, (cs_key, cs_label, _) in enumerate(_ICC_SPACES):
            ctk.CTkLabel(icc_grid, text=cs_label, width=75, anchor="w",
                         font=_font(*THEME["font_normal"]),
                         text_color=THEME["title_color"]).grid(
                row=row_idx, column=0, padx=(0, 6), pady=3, sticky="w")

            profiles = get_profiles(cs_key)
            values   = profiles if profiles else [_EMPTY_PROFILE]
            initial  = profiles[0] if profiles else _EMPTY_PROFILE
            self._icc_vars[cs_key].set(initial)

            menu = ctk.CTkOptionMenu(
                icc_grid,
                variable=self._icc_vars[cs_key],
                values=values,
                width=200,
                state="normal" if profiles else "disabled",
                fg_color=THEME["combo_fg"],
                text_color=THEME["combo_dd_text"],
                button_color=THEME["combo_btn"],
                button_hover_color=THEME["combo_btn_hover"],
                dropdown_fg_color=THEME["combo_dd_fg"],
                dropdown_hover_color=THEME["combo_dd_hover"],
                dropdown_text_color=THEME["combo_dd_text"],
                font=_font(*THEME["font_normal"]),
                dropdown_font=_font(*THEME["font_normal"]),
            )
            menu.grid(row=row_idx, column=1, padx=(0, 4), pady=3, sticky="ew")
            self._icc_menus[cs_key] = menu

            ctk.CTkButton(
                icc_grid, text="⟳", width=28,
                font=_font(*THEME["font_normal"]),
                command=lambda k=cs_key: self._refresh_icc_dropdown(k),
            ).grid(row=row_idx, column=2, pady=3)

        ctk.CTkLabel(
            tab,
            text="Профіль призначається як тег. Кольори не конвертуються.",
            font=_font(*THEME["font_small"]),
            text_color=THEME["hint_color"],
            anchor="w",
        ).pack(fill="x", padx=IPAD, pady=(4, IPAD))

        self._on_icc_toggle()

    # -----------------------------------------------------------------------
    # CHANGE 5+6 — Панель запуску: grid layout, кнопка знизу, авто-відкриття
    # -----------------------------------------------------------------------

    def _build_launch_panel(self, parent, col: int) -> None:
        frame = _card(parent)
        frame.grid(row=0, column=col, sticky="nsew", pady=4)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=0)  # заголовок
        frame.grid_rowconfigure(1, weight=0)  # дропдаун режиму
        frame.grid_rowconfigure(2, weight=1)  # розтяжний відступ
        frame.grid_rowconfigure(3, weight=0)  # чекбокс авто-відкриття
        frame.grid_rowconfigure(4, weight=0)  # кнопка запуску

        ctk.CTkLabel(
            frame, text="Запуск обробки",
            font=_font(*THEME["font_title"]),
            text_color=THEME["title_color"],
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=IPAD, pady=(IPAD, 4))

        _make_optionmenu(frame, self._mode_var, _MODE_DISPLAY).grid(
            row=1, column=0, sticky="ew", padx=IPAD, pady=(0, 0),
        )

        # Розтяжний відступ (row 2 — weight=1, нічого не містить)

        ctk.CTkCheckBox(
            frame,
            text="Відкрити оброблений документ",
            variable=self._auto_open_var,
            font=_font(*THEME["font_normal"]),
            text_color=THEME["title_color"],
            checkmark_color=THEME["accent"],
            hover_color=THEME["accent_light"],
        ).grid(row=3, column=0, sticky="w", padx=IPAD, pady=(0, 8))

        self._run_btn = ctk.CTkButton(
            frame,
            text="▶  Запустити",
            fg_color=THEME["run_fg"],
            hover_color=THEME["run_hover"],
            text_color="#FFFFFF",
            font=_font(*THEME["font_button"]),
            height=44,
            corner_radius=8,
            command=self._on_run_or_stop,
        )
        self._run_btn.grid(row=4, column=0, sticky="ew", padx=IPAD, pady=(0, IPAD))

    # -----------------------------------------------------------------------
    # Run / Stop
    # -----------------------------------------------------------------------

    def _on_run_or_stop(self) -> None:
        if self._processing:
            self._on_cancel()
        else:
            mode_key = _MODE_DISP_TO_KEY.get(self._mode_var.get(), "cmyk")
            self.on_run(mode_key)

    def _set_run_btn_active(self) -> None:
        self._processing = True
        self._run_btn.configure(
            text="⏹  Зупинити",
            fg_color=THEME["stop_fg"],
            hover_color=THEME["stop_hover"],
            state="normal",
        )

    def _set_run_btn_idle(self) -> None:
        self._processing = False
        self._run_btn.configure(
            text="▶  Запустити",
            fg_color=THEME["run_fg"],
            hover_color=THEME["run_hover"],
            state="normal",
        )

    # -----------------------------------------------------------------------
    # ICC-допоміжники
    # -----------------------------------------------------------------------

    def _on_icc_toggle(self) -> None:
        enabled = self._icc_use_var.get()
        for cs_key, menu in self._icc_menus.items():
            profiles = get_profiles(cs_key)
            menu.configure(state="normal" if (enabled and profiles) else "disabled")

    def _refresh_icc_dropdown(self, cs_key: str) -> None:
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
    # Режим друку
    # -----------------------------------------------------------------------

    def _on_print_mode_change(self, *_) -> None:
        single = self._print_mode_var.get() == "single"
        state = "disabled" if single else "normal"
        for entry in self._back_entry_widgets:
            entry.configure(state=state)
        if single:
            self._back_hint_lbl.pack(fill="x", padx=IPAD, pady=(0, IPAD))
        else:
            self._back_hint_lbl.pack_forget()
        if hasattr(self, "_preview"):
            self._preview.set_single_sided(single)

    # -----------------------------------------------------------------------
    # Налаштування: завантаження / збереження
    # -----------------------------------------------------------------------

    def load_settings(self) -> None:
        s = load_settings()

        dpi_str = str(s.get("dpi", 300))
        self._dpi_var.set(dpi_str if dpi_str in DPI_OPTIONS else "300")

        self._suffix_cmyk_var.set(s.get("output_suffix_cmyk", "_CMYK"))
        self._suffix_gray_var.set(s.get("output_suffix_gray", "_GRAY"))
        self._suffix_rgb_var.set(s.get("output_suffix_rgb",  "_RGB"))

        interp_key = s.get("interpolation", "INTER_LANCZOS4")
        self._interp_var.set(_INTERP_KEY_TO_DISPLAY.get(interp_key, _INTERP_DISPLAY_NAMES[0]))

        comp_key = s.get("compression", "tiff_lzw")
        self._compression_var.set(_COMPRESSION_KEY_TO_DISPLAY.get(comp_key, _COMPRESSION_DISPLAY_NAMES[0]))

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

        self._print_mode_var.set(s.get("print_mode", "double"))
        self._on_print_mode_change()

        self._last_output_folder = s.get("last_output_folder", "")
        self._auto_open_var.set(s.get("auto_open_file", True))

    def get_settings(self) -> dict:
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
            "print_mode":         self._print_mode_var.get(),
            "interpolation":      _INTERP_DISPLAY_TO_KEY.get(
                                      self._interp_var.get(), "INTER_LANCZOS4"),
            "compression":        _COMPRESSION_DISPLAY_TO_KEY.get(
                                      self._compression_var.get(), "tiff_lzw"),
            "auto_open_file":     self._auto_open_var.get(),
            **icc_selections,
        }

    # -----------------------------------------------------------------------
    # Прогрес-панель: керування
    # -----------------------------------------------------------------------

    def _start_progress(self, status_text: str) -> None:
        self._progress_status_lbl.configure(
            text=status_text,
            text_color=THEME["title_color"],
        )
        self._page_counter_lbl.configure(text="Сторінка 0 / ?")
        self._set_run_btn_active()
        self._spinner.start()

    def _stop_progress(self) -> None:
        self._spinner.stop()
        self._set_run_btn_idle()

    def _make_log_callback(self) -> callable:
        def cb(text: str) -> None:
            if len(text) > 80:
                text = text[:77] + "..."
            self.after(0, lambda t=text: self._progress_status_lbl.configure(text=t))
        return cb

    def _make_progress_callback(self) -> callable:
        def cb(current: int, total: int) -> None:
            self.after(
                0,
                lambda c=current, t=total: self._page_counter_lbl.configure(
                    text=f"Сторінка {c} / {t}"
                ),
            )
        return cb

    def _on_cancel(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        self._run_btn.configure(state="disabled", text="Зупиняємо...")

    # -----------------------------------------------------------------------
    # Запуск обробки
    # -----------------------------------------------------------------------

    def on_run(self, mode: str) -> None:
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
        icc_path = None
        if settings.get("use_icc_profile"):
            cs_key, settings_key = icc_cs_map.get(base_mode, ("cmyk", "icc_profile_cmyk"))
            profile_name = settings.get(settings_key, "")
            if profile_name:
                candidate = ICC_DIR / cs_key / profile_name
                if candidate.exists():
                    icc_path = candidate
                else:
                    print(f"[gui] УВАГА: профіль не знайдено: {candidate}")

        status_text = f"Обробка: {Path(pdf_path).name}  [{mode}]"
        self._set_status(f"{status_text}…")
        self._stop_event = threading.Event()
        self._start_progress(status_text)

        log_cb      = self._make_log_callback()
        progress_cb = self._make_progress_callback()
        stop_evt    = self._stop_event

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
                    print_mode=settings["print_mode"],
                    interpolation=settings.get("interpolation", "INTER_LANCZOS4"),
                    compression=settings.get("compression", "tiff_lzw"),
                    log_callback=log_cb,
                    progress_callback=progress_cb,
                    stop_event=stop_evt,
                )
                if out is None:
                    self.after(0, self._on_cancelled)
                else:
                    self.after(0, lambda o=out: self._on_done(o))
            except Exception as exc:
                self.after(0, lambda e=exc: self._on_error(e))

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
        self._status_lbl.configure(text=f"  {text}")

    def _bind_tooltip(self, widget, text: str) -> None:
        tip: tk.Toplevel | None = None

        def show(event):
            nonlocal tip
            tip = tk.Toplevel(self)
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{event.x_root + 12}+{event.y_root + 6}")
            tk.Label(
                tip, text=text,
                background="#FFFFDD", relief="solid", borderwidth=1,
                font=(FONT, 10), padx=4, pady=2,
            ).pack()

        def hide(_):
            nonlocal tip
            if tip:
                tip.destroy()
                tip = None

        widget.bind("<Enter>", show, add="+")
        widget.bind("<Leave>", hide, add="+")

    def _on_done(self, output_path: str) -> None:
        self._stop_progress()

        out_folder = str(Path(output_path).parent)
        self._last_output_folder = out_folder
        try:
            s = load_settings()
            s["last_output_folder"] = out_folder
            save_settings(s)
        except Exception:
            pass

        self._progress_status_lbl.configure(
            text=f"✔ Готово: {Path(output_path).name}",
            text_color=THEME["run_fg"],
        )
        self._set_status(f"Готово: {output_path}")

        # Авто-відкриття обробленого файлу
        if self._auto_open_var.get():
            try:
                os.startfile(output_path)
            except Exception:
                pass

        messagebox.showinfo("Успіх", f"Файл збережено:\n{output_path}", parent=self)

    def _on_cancelled(self) -> None:
        self._stop_progress()
        self._progress_status_lbl.configure(
            text="⛔ Зупинено",
            text_color=THEME["stop_fg"],
        )
        self._page_counter_lbl.configure(text="")
        self._set_status("⛔ Конвертацію зупинено користувачем")

    def _on_error(self, exc: Exception) -> None:
        self._stop_progress()
        self._progress_status_lbl.configure(
            text=f"Помилка: {exc}",
            text_color=THEME["stop_fg"],
        )
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
