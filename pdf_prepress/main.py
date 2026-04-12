"""
main.py — Точка входу PDF Pre-Press Processor (pywebview UI).

Використання:
    python main.py                  # відкриває вікно з порожнім списком файлів
    python main.py path/to/file.pdf # одразу завантажує файл у список
    pdf_prepress.exe "%1"           # так викликається з контекстного меню Windows

Сервер:
    Статичні файли (HTML/CSS/JS) роздаються через вбудований HTTP-сервер
    на випадковому порту 127.0.0.1. Це гарантує, що відносні шляхи,
    CSS-імпорти та JS-модулі працюють так само, як у браузері.
"""

import http.server
import socketserver
import sys
import threading
import traceback
from pathlib import Path

import webview

from app import Api


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

UI_DIR = Path(__file__).parent / "ui"

# ---------------------------------------------------------------------------
# Silent HTTP server (serves ui/ directory)
# ---------------------------------------------------------------------------

_port: int = 0
_server_ready = threading.Event()


class _SilentHandler(http.server.SimpleHTTPRequestHandler):
    """Serves files from UI_DIR; suppresses HTTP access log."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(UI_DIR), **kwargs)

    def log_message(self, *_):
        pass  # suppress HTTP log spam in console


def _start_server() -> None:
    global _port
    with socketserver.TCPServer(("127.0.0.1", 0), _SilentHandler) as httpd:
        _port = httpd.server_address[1]
        _server_ready.set()
        httpd.serve_forever()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    # ── Resolve optional initial PDF from CLI arg ──────────────────────────
    initial_file: str | None = None
    if len(sys.argv) >= 2:
        p = Path(sys.argv[1])
        if p.exists() and p.suffix.lower() == ".pdf":
            initial_file = str(p.resolve())

    # ── Start HTTP server in background thread ─────────────────────────────
    t = threading.Thread(target=_start_server, daemon=True)
    t.start()
    _server_ready.wait()  # block until server is actually listening

    # ── Create pywebview window ────────────────────────────────────────────
    api = Api(initial_file=initial_file)

    window = webview.create_window(
        "PDF Pre-Press",
        url=f"http://127.0.0.1:{_port}/index.html",
        js_api=api,
        width=1200,
        height=800,
        min_size=(900, 600),
    )

    api.set_window(window)

    webview.start(debug=False)


# ---------------------------------------------------------------------------
# Top-level exception guard
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        err = traceback.format_exc()
        print(err, file=sys.stderr)
        sys.exit(1)
