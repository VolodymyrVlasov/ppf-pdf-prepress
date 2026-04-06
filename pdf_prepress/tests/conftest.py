"""
conftest.py — Конфігурація pytest для тестів pdf_prepress.

Додає батьківську директорію (pdf_prepress/) до sys.path,
щоб тести могли імпортувати processor, settings тощо без встановлення пакету.
"""

import sys
from pathlib import Path

# pdf_prepress/ — батьківська папка папки tests/
sys.path.insert(0, str(Path(__file__).parent.parent))
