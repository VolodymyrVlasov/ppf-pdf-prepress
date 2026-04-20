"""
app.py — Python ↔ JavaScript bridge for pywebview.

All public methods are exposed to JS via window.pywebview.api.*
"""

import json
import os
import sys
import threading
from pathlib import Path

from settings import load_settings, save_settings, DEFAULT_SETTINGS
from processor import (
    process_pdf, get_profiles as _get_profiles, ICC_DIR,
    RASTER_ALGORITHMS, get_gs_executable,
)


# ---------------------------------------------------------------------------
# Mapping constants (mirrored from gui.py)
# ---------------------------------------------------------------------------

_MODES: list[tuple[str, str]] = [
    ("CMYK",                   "cmyk"),
    ("CMYK + деформація",      "cmyk_warp"),
    ("Grayscale",              "grayscale"),
    ("Grayscale + деформація", "grayscale_warp"),
    ("RGB",                    "rgb"),
    ("RGB + деформація",       "rgb_warp"),
]
MODE_DISPLAY_TO_KEY = {d: k for d, k in _MODES}
MODE_KEY_TO_DISPLAY = {k: d for d, k in _MODES}
MODE_DISPLAY_NAMES  = [d for d, _ in _MODES]

ICC_SPACES = [
    ("cmyk", "CMYK",      "icc_profile_cmyk"),
    ("rgb",  "RGB",       "icc_profile_rgb"),
    ("gray", "Grayscale", "icc_profile_gray"),
]


# ---------------------------------------------------------------------------
# Api class
# ---------------------------------------------------------------------------

class Api:
    """Exposes all Python functionality to JavaScript."""

    def __init__(self, initial_file: str | None = None) -> None:
        self._initial_file: str | None = initial_file
        self._stop_event: threading.Event | None = None
        self._window = None  # set by main.py after window creation

    def set_window(self, window) -> None:
        """Called from main.py to give the bridge a reference to the webview window."""
        self._window = window

    # -----------------------------------------------------------------------
    # Settings
    # -----------------------------------------------------------------------

    def get_settings(self) -> dict:
        """Returns merged settings dict. Includes initial_file if provided at startup."""
        s = load_settings()
        if self._initial_file:
            s["initial_file"] = self._initial_file
        return s

    def save_settings(self, data: dict) -> bool:
        """Saves settings to settings.json. Returns True on success."""
        try:
            # Persist only known settings keys — don't save transient UI state
            allowed = set(DEFAULT_SETTINGS.keys())
            filtered = {k: v for k, v in data.items() if k in allowed}
            existing = load_settings()
            existing.update(filtered)
            save_settings(existing)
            return True
        except Exception as exc:
            print(f"[app] save_settings error: {exc}")
            return False

    # -----------------------------------------------------------------------
    # ICC profiles
    # -----------------------------------------------------------------------

    def get_profiles(self, color_space: str) -> list[str]:
        """Returns list of .icc/.icm filenames from icc_profiles/{color_space}/."""
        return _get_profiles(color_space)

    # -----------------------------------------------------------------------
    # File dialogs
    # -----------------------------------------------------------------------

    def open_file_dialog(self) -> list[str]:
        """Opens a native file dialog for multiple PDF selection."""
        s = load_settings()
        init_dir = s.get("last_open_folder") or s.get("last_folder", "")
        if not init_dir or not Path(init_dir).exists():
            init_dir = str(Path.home())

        if self._window is None:
            return []

        result = self._window.create_file_dialog(
            dialog_type=10,  # OPEN_DIALOG
            allow_multiple=True,
            file_types=("PDF файли (*.pdf)", "Усі файли (*.*)"),
            directory=init_dir,
        )
        if not result:
            return []

        paths = list(result)
        if paths:
            try:
                s["last_open_folder"] = str(Path(paths[0]).parent)
                save_settings(s)
            except Exception:
                pass
        return paths

    def open_folder(self, path: str) -> None:
        """Opens the given folder in Windows Explorer."""
        try:
            import subprocess
            subprocess.Popen(["explorer", str(Path(path).resolve())])
        except Exception as exc:
            print(f"[app] open_folder error: {exc}")

    def open_file(self, path: str) -> None:
        """Opens the given file with its default application (Windows)."""
        try:
            os.startfile(path)
        except Exception as exc:
            print(f"[app] open_file error: {exc}")

    # -----------------------------------------------------------------------
    # Processing
    # -----------------------------------------------------------------------

    def start_processing(self, params: dict) -> None:
        """
        Starts process_pdf() in a background thread.
        Progress is pushed to JS via window.evaluate_js('onProgress(...)').

        params keys (all required):
            pdf_path, mode, dpi, odd_corners, even_corners,
            output_suffix, use_icc_profile, icc_profile_name,
            icc_cs_key, print_mode, interpolation, compression
        """
        if self._window is None:
            return

        self._stop_event = threading.Event()
        stop_evt = self._stop_event

        def _push(payload: dict) -> None:
            if self._window:
                try:
                    self._window.evaluate_js(
                        f"onProgress({json.dumps(payload, ensure_ascii=False)})"
                    )
                except Exception as exc:
                    print(f"[app] evaluate_js error: {exc}")

        def _log_cb(text: str) -> None:
            if len(text) > 120:
                text = text[:117] + "..."
            _push({"type": "log", "text": text})

        def _progress_cb(current: int, total: int) -> None:
            _push({"type": "progress", "page": current, "total": total})

        def _worker() -> None:
            try:
                pdf_path    = params["pdf_path"]
                mode        = params["mode"]
                dpi         = int(params.get("dpi", 300))
                odd_corners = params.get("odd_corners", DEFAULT_SETTINGS["odd_corners"])
                even_corners= params.get("even_corners", DEFAULT_SETTINGS["even_corners"])
                output_suffix = params.get("output_suffix", "_CMYK")
                print_mode    = params.get("print_mode", "double")
                interpolation = params.get("interpolation", "INTER_LANCZOS4")
                compression   = params.get("compression", "tiff_lzw")
                algorithm     = params.get("raster_algorithm", "pymupdf")

                icc_path = None
                if params.get("use_icc_profile"):
                    cs_key       = params.get("icc_cs_key", "cmyk")
                    profile_name = params.get("icc_profile_name", "")
                    if profile_name:
                        candidate = ICC_DIR / cs_key / profile_name
                        if candidate.exists():
                            icc_path = candidate
                        else:
                            print(f"[app] ICC profile not found: {candidate}")

                out = process_pdf(
                    pdf_path=pdf_path,
                    mode=mode,
                    dpi=dpi,
                    odd_corners=odd_corners,
                    even_corners=even_corners,
                    output_suffix=output_suffix,
                    icc_path=icc_path,
                    print_mode=print_mode,
                    interpolation=interpolation,
                    compression=compression,
                    algorithm=algorithm,
                    log_callback=_log_cb,
                    progress_callback=_progress_cb,
                    stop_event=stop_evt,
                )

                if out is None:
                    _push({"type": "done", "success": False, "cancelled": True})
                else:
                    _push({"type": "done", "success": True, "output_path": out})

            except Exception as exc:
                _push({"type": "done", "success": False, "error": str(exc)})

        threading.Thread(target=_worker, daemon=True).start()

    def stop_processing(self) -> None:
        """Signals the background worker to stop after the current page."""
        if self._stop_event is not None:
            self._stop_event.set()

    # -----------------------------------------------------------------------
    # App metadata
    # -----------------------------------------------------------------------

    def get_modes(self) -> list[dict]:
        """Returns list of {display, key} for processing modes."""
        return [{"display": d, "key": k} for d, k in _MODES]

    def get_icc_spaces(self) -> list[dict]:
        """Returns list of {csKey, label, settingsKey} for ICC color spaces."""
        return [
            {"csKey": cs, "label": label, "settingsKey": sk}
            for cs, label, sk in ICC_SPACES
        ]

    def get_raster_algorithms(self) -> list[dict]:
        """Returns list of raster algorithm descriptors for the UI selector."""
        try:
            get_gs_executable()
            gs_ok = True
        except FileNotFoundError:
            gs_ok = False

        return [
            {
                "value":       key,
                "label":       val["label"],
                "short":       val["short"],
                "description": val["description"],
                "available":   True if not val["requires_gs"] else gs_ok,
            }
            for key, val in RASTER_ALGORITHMS.items()
        ]
