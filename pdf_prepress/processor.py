"""
processor.py — Ядро обробки зображень для PDF пре-пресу.

КЛЮЧОВА КОНЦЕПЦІЯ:
  ICC-профіль лише призначається (вбудовується як метадані OutputIntent).
  Числові значення пікселів НЕ змінюються.
  При використанні Ghostscript растеризація виконується із прапором
  -dColorConversionStrategy=/LeaveColorUnchanged, що гарантує збереження
  оригінальних колірних значень (наприклад, CMYK 0,0,0,100 → залишається 0,0,0,100).
"""

import glob
import io
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Callable

import cv2
import img2pdf
import numpy as np
import pikepdf
from PIL import Image


# Коренева директорія модуля та папка ICC-профілів.
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    _HERE = Path(sys._MEIPASS)
else:
    _HERE = Path(__file__).parent

ICC_DIR = _HERE / "icc_profiles"   # публічна константа, імпортується gui.py

# Відображення імен констант інтерполяції на значення cv2
_INTERP_MAP: dict[str, int] = {
    "INTER_LANCZOS4": cv2.INTER_LANCZOS4,
    "INTER_CUBIC":    cv2.INTER_CUBIC,
    "INTER_LINEAR":   cv2.INTER_LINEAR,
    "INTER_NEAREST":  cv2.INTER_NEAREST,
}

# Відображення ключів стиснення на назви Pillow
_PILLOW_COMPRESSION: dict[str, str | None] = {
    "tiff_lzw":     "tiff_lzw",
    "tiff_deflate": "tiff_adobe_deflate",
    "none":         None,
}

# ---------------------------------------------------------------------------
# Алгоритми растеризації (публічна константа, імпортується app.py)
# ---------------------------------------------------------------------------

RASTER_ALGORITHMS: dict[str, dict] = {
    "pymupdf": {
        "label": "PyMuPDF",
        "short": "Універсальний, без зовнішніх залежностей",
        "description": (
            "Растеризація виконується через вбудований рушій PyMuPDF. "
            "Сторінки завжди конвертуються у RGB як проміжний формат, "
            "незалежно від оригінальної кольорової моделі документа. "
            "При подальшій конвертації у CMYK відбувається зворотне "
            "перерахування RGB→CMYK, що призводить до втрати чистоти "
            "плашкових кольорів: чорний текст (0,0,0,100K) стає "
            "складеним чорним (~86C 87M 87Y 0K). "
            "На дрібному тексті це може проявлятись як кольоровий ореол "
            "при незначному суміщенні кольорових каналів на друці. "
            "Рекомендовано для RGB-документів та попереднього перегляду."
        ),
        "requires_gs": False,
    },
    "ghostscript": {
        "label": "Ghostscript",
        "short": "Точна растеризація зі збереженням кольорової моделі",
        "description": (
            "Растеризація виконується Ghostscript — професійним "
            "PostScript/PDF рушієм. "
            "Кольорова модель растра відповідає обраному режиму обробки: "
            "для CMYK-режиму сторінки растеризуються напряму у CMYK "
            "без проміжного RGB, завдяки чому чорний текст (0,0,0,100K) "
            "зберігається точно як (0,0,0,100K). "
            "Це усуває кольорові ореоли навколо тексту і забезпечує "
            "чистоту плашкових кольорів на відбитку. "
            "Для RGB і Grayscale режимів також використовується прямий "
            "шлях без зміни кольорового простору. "
            "Рекомендовано для поліграфічної підготовки документів з "
            "текстом, лініями та плашковими кольорами."
        ),
        "requires_gs": True,
    },
}


# ---------------------------------------------------------------------------
# Внутрішній логер
# ---------------------------------------------------------------------------

def _log(message: str, log_callback: Callable[[str], None] | None = None) -> None:
    """Виводить повідомлення у stdout та надсилає у log_callback (якщо задано)."""
    print(message)
    if log_callback is not None:
        try:
            log_callback(message)
        except Exception:
            pass


def get_profiles(color_space: str) -> list[str]:
    """
    Повертає список файлів ICC/ICM-профілів із підпапки icc_profiles/{color_space}/.

    :param color_space: «cmyk», «rgb» або «gray».
    :return:            Відсортований список імен файлів (.icc / .icm).
                        Порожній список, якщо папка не існує або в ній немає профілів.
    """
    folder = ICC_DIR / color_space
    if not folder.is_dir():
        return []
    return sorted(
        f.name for f in folder.iterdir()
        if f.suffix.lower() in (".icc", ".icm")
    )


# ---------------------------------------------------------------------------
# Внутрішні допоміжники
# ---------------------------------------------------------------------------

def get_gs_executable() -> str:
    """
    Повертає повний шлях до виконуваного файлу Ghostscript.

    Порядок пошуку:
      1. Бандл PyInstaller: {sys._MEIPASS}/gs/bin/gswin64c.exe
      2. PATH: gswin64c → gswin32c → gs
      3. Стандартні шляхи Windows: C:\\Program Files\\gs\\gs*\\bin\\gswin64c.exe

    :raises FileNotFoundError: якщо GS не знайдено жодним із способів.
    """
    # 1. PyInstaller onedir bundle
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        bundled = os.path.join(sys._MEIPASS, "gs", "bin", "gswin64c.exe")
        if os.path.isfile(bundled):
            return bundled

    # 2. System PATH
    for name in ("gswin64c", "gswin32c", "gs"):
        found = shutil.which(name)
        if found:
            return found

    # 3. Common Windows install locations
    for pattern in (
        r"C:\Program Files\gs\gs*\bin\gswin64c.exe",
        r"C:\Program Files (x86)\gs\gs*\bin\gswin64c.exe",
    ):
        matches = glob.glob(pattern)
        if matches:
            return sorted(matches)[-1]   # use latest version

    raise FileNotFoundError(
        "Ghostscript не знайдено.\n"
        "Встановіть Ghostscript або додайте gswin64c.exe до PATH.\n"
        "Завантажити: https://ghostscript.com/releases/"
    )


def _find_ghostscript() -> str | None:
    """
    Знаходить виконуваний файл Ghostscript.
    Обгортка навколо get_gs_executable(); повертає None замість виключення.
    """
    try:
        return get_gs_executable()
    except FileNotFoundError:
        return None


# ---------------------------------------------------------------------------
# 1. Растеризація PDF
# ---------------------------------------------------------------------------

def rasterize_pdf(
    pdf_path: str,
    dpi: int = 300,
    algorithm: str = "pymupdf",
    color_mode: str = "rgb",
    log_callback: Callable[[str], None] | None = None,
) -> list[Image.Image]:
    """
    Растеризує кожну сторінку PDF у PIL Image.

    :param pdf_path:   Шлях до вхідного PDF-файлу.
    :param dpi:        Роздільна здатність у точках на дюйм.
    :param algorithm:  «pymupdf» або «ghostscript».
    :param color_mode: Цільовий кольоровий режим: «cmyk», «gray», «rgb».
                       Визначається автоматично з режиму обробки — не задається користувачем.
    :param log_callback: Необов'язкова функція для передачі рядків логу.
    :return:           Список PIL Image (по одному на сторінку).
                       PyMuPDF завжди повертає RGB.
                       Ghostscript повертає зображення у запитаному color_mode.
    """
    pdf_path = Path(pdf_path)

    if algorithm == "ghostscript":
        gs_exe = _find_ghostscript()
        if gs_exe:
            return _rasterize_via_ghostscript(pdf_path, dpi, color_mode, gs_exe, log_callback)
        _log(
            "[processor] УВАГА: Ghostscript не знайдено. "
            "Використовується PyMuPDF (RGB). "
            "Числові значення CMYK можуть змінитись. "
            "Встановіть Ghostscript для коректної роботи.",
            log_callback,
        )

    # pymupdf — завжди RGB
    return _rasterize_via_pymupdf(pdf_path, dpi, log_callback)


def _rasterize_via_ghostscript(
    pdf_path: Path,
    dpi: int,
    color_mode: str,
    gs_exe: str,
    log_callback: Callable[[str], None] | None = None,
) -> list[Image.Image]:
    """
    Растеризація через Ghostscript.
    Кожна сторінка зберігається як окремий TIFF у тимчасовій папці.
    Вивід GS передається рядок за рядком у log_callback.
    """
    device_map = {
        "cmyk": "tiff32nc",
        "gray": "tiffgray",
        "rgb":  "tiff24nc",
    }
    device = device_map.get(color_mode, "tiff32nc")

    with tempfile.TemporaryDirectory(prefix="pdfprepress_") as tmpdir:
        output_pattern = str(Path(tmpdir) / "page_%04d.tif")

        cmd = [
            gs_exe,
            "-dBATCH",
            "-dNOPAUSE",
            "-dSAFER",
            f"-sDEVICE={device}",
            f"-r{dpi}",
            "-dColorConversionStrategy=/LeaveColorUnchanged",
        ]
        if color_mode == "cmyk":
            cmd.append("-dUseCIEColor=false")
        cmd += [f"-sOutputFile={output_pattern}", str(pdf_path)]

        _log(f"[processor] Ghostscript: {' '.join(cmd)}", log_callback)

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                _log(f"[gs] {line}", log_callback)
        proc.wait()

        if proc.returncode != 0:
            raise RuntimeError(
                f"Ghostscript завершився з помилкою (код {proc.returncode}). "
                f"Перегляньте лог для деталей."
            )

        tiff_files = sorted(Path(tmpdir).glob("page_*.tif"))
        if not tiff_files:
            raise RuntimeError("Ghostscript не створив жодного TIFF-файлу.")

        images = []
        for tiff_file in tiff_files:
            img = Image.open(tiff_file).copy()
            images.append(img)

    return images


def _rasterize_via_pymupdf(
    pdf_path: Path,
    dpi: int,
    log_callback: Callable[[str], None] | None = None,
) -> list[Image.Image]:
    """
    Растеризація через PyMuPDF (fitz). Завжди повертає RGB.
    Конвертація у цільовий кольоровий простір виконується в process_pdf()
    після застосування деформації.
    """
    import fitz  # PyMuPDF

    scale = dpi / 72.0
    matrix = fitz.Matrix(scale, scale)
    doc = fitz.open(str(pdf_path))
    images = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        img_bytes = pixmap.tobytes("png")
        pil_img = Image.open(io.BytesIO(img_bytes)).copy()
        _log(f"[processor] PyMuPDF: сторінка {page_num + 1}", log_callback)
        images.append(pil_img)

    doc.close()
    return images


# ---------------------------------------------------------------------------
# 2. Конвертація у CMYK
# ---------------------------------------------------------------------------

def convert_to_cmyk(image: Image.Image) -> Image.Image:
    """
    Конвертує PIL Image у режим CMYK засобами Pillow.

    УВАГА: ця функція виконує математичне перерахування пікселів.
    Чорний текст (0,0,0,100K) перетвориться на складений чорний.
    Використовується лише для алгоритму PyMuPDF — для Ghostscript
    конвертація виконується на рівні растеризатора.
    """
    if image.mode == "CMYK":
        return image
    if image.mode not in ("RGB",):
        image = image.convert("RGB")
    return image.convert("CMYK")


# ---------------------------------------------------------------------------
# 3. Конвертація у відтінки сірого
# ---------------------------------------------------------------------------

def convert_to_grayscale(image: Image.Image) -> Image.Image:
    """
    Конвертує PIL Image у режим відтінків сірого (L).
    Використовується лише для алгоритму PyMuPDF.
    """
    if image.mode == "L":
        return image
    return image.convert("L")


# ---------------------------------------------------------------------------
# 4. Перспективна деформація (warp)
# ---------------------------------------------------------------------------

def apply_warp(
    image: Image.Image,
    corners_mm: dict[str, tuple[float, float]],
    dpi: int,
    interpolation: int = cv2.INTER_LANCZOS4,
) -> Image.Image:
    """
    Застосовує перспективну деформацію до зображення.

    corners_mm — зміщення кутів у міліметрах від початкового положення:
        {"tl": (dx, dy), "tr": (dx, dy), "bl": (dx, dy), "br": (dx, dy)}
    Позитивний dx → вправо, позитивний dy → вниз.

    Підтримує будь-який PIL-режим: RGB, CMYK, L тощо.
    Числові значення пікселів не змінюються — виконується лише геометрична трансформація.

    :param image:         Вхідне PIL Image.
    :param corners_mm:    Словник зміщень для кожного з чотирьох кутів.
    :param dpi:           Роздільна здатність (для перетворення мм → пікселі).
    :param interpolation: Метод інтерполяції cv2 (за замовчуванням INTER_LANCZOS4).
    :return:              PIL Image після деформації (той самий розмір полотна).
    """
    px_per_mm = dpi / 25.4
    w, h = image.size

    src_pts = np.float32([
        [0,     0    ],
        [w - 1, 0    ],
        [0,     h - 1],
        [w - 1, h - 1],
    ])

    def offset_px(key: str) -> np.ndarray:
        dx_mm, dy_mm = corners_mm.get(key, (0.0, 0.0))
        return np.float32([dx_mm * px_per_mm, dy_mm * px_per_mm])

    dst_pts = np.float32([
        src_pts[0] + offset_px("tl"),
        src_pts[1] + offset_px("tr"),
        src_pts[2] + offset_px("bl"),
        src_pts[3] + offset_px("br"),
    ])

    M = cv2.getPerspectiveTransform(src_pts, dst_pts)

    arr = np.array(image)
    warped = cv2.warpPerspective(
        arr,
        M,
        (w, h),
        flags=interpolation,
        borderMode=cv2.BORDER_REPLICATE,
    )

    return Image.fromarray(warped, mode=image.mode)


# ---------------------------------------------------------------------------
# 5. Збирання вихідного PDF
# ---------------------------------------------------------------------------

def assemble_pdf(
    images: list[Image.Image],
    output_path: str,
    dpi: int = 300,
    compression: str = "tiff_lzw",
    log_callback: Callable[[str], None] | None = None,
) -> None:
    """
    Зберігає список PIL Images як єдиний PDF-файл через img2pdf.

    Кожне зображення спочатку записується як TIFF у тимчасову папку,
    потім передається у img2pdf — без JPEG-перекомпресії.

    :param images:       Список зображень (по одному на сторінку).
    :param output_path:  Шлях до вихідного PDF.
    :param dpi:          Роздільна здатність для метаданих PDF.
    :param compression:  Стиснення проміжних TIFF: «tiff_lzw», «tiff_deflate», «none».
    :param log_callback: Необов'язкова функція для передачі рядків логу.
    """
    output_path = str(output_path)
    pillow_compression = _PILLOW_COMPRESSION.get(compression, "tiff_lzw")

    _log(
        f"[processor] Проміжний формат: TIFF {compression}, збірка без перекомпресії",
        log_callback,
    )

    layout_fun = img2pdf.get_fixed_dpi_layout_fun((dpi, dpi))

    with tempfile.TemporaryDirectory(prefix="pdfprepress_assemble_") as tmpdir:
        tiff_paths = []
        for idx, img in enumerate(images):
            if img.mode not in ("RGB", "L", "CMYK"):
                img = img.convert("RGB")

            tmp_path = str(Path(tmpdir) / f"page_{idx:04d}.tif")
            save_kwargs: dict = {"format": "TIFF", "dpi": (dpi, dpi)}
            if pillow_compression is not None:
                save_kwargs["compression"] = pillow_compression
            img.save(tmp_path, **save_kwargs)
            tiff_paths.append(tmp_path)

            _log(f"[processor] Збірка PDF: додається сторінка {idx + 1} / {len(images)}", log_callback)

        with open(output_path, "wb") as f:
            f.write(img2pdf.convert(tiff_paths, layout_fun=layout_fun))


# ---------------------------------------------------------------------------
# 6. Призначення ICC-профілю (вбудовування як OutputIntent)
# ---------------------------------------------------------------------------

def assign_icc_profile(
    pdf_path: str,
    icc_path: Path,
    color_space: str,
    log_callback: Callable[[str], None] | None = None,
) -> None:
    """
    Вбудовує ICC-профіль у готовий PDF як OutputIntent (стандарт PDF/X).

    НЕ змінює числові значення пікселів — лише додає метадані,
    що описують, у якому колірному просторі вже записані числа.

    :param pdf_path:    Шлях до PDF-файлу для модифікації (перезаписується).
    :param icc_path:    Шлях до .icc-файлу профілю.
    :param color_space: «CMYK», «Grayscale» або «RGB».
    :param log_callback: Необов'язкова функція для передачі рядків логу.
    """
    icc_path = Path(icc_path)
    n_channels = {"CMYK": 4, "Grayscale": 1, "RGB": 3}.get(color_space, 4)

    _log(f"[processor] Призначення ICC-профілю: {icc_path.name}  [{color_space}]", log_callback)

    with pikepdf.open(str(pdf_path), allow_overwriting_input=True) as pdf:
        icc_data = icc_path.read_bytes()

        icc_stream = pikepdf.Stream(pdf, icc_data)
        icc_stream["/N"] = n_channels

        intent = pikepdf.Dictionary(
            Type=pikepdf.Name("/OutputIntent"),
            S=pikepdf.Name("/GTS_PDFA1"),
            OutputConditionIdentifier=pikepdf.String(icc_path.stem),
            DestOutputProfile=icc_stream,
        )

        if "/OutputIntents" not in pdf.Root:
            pdf.Root["/OutputIntents"] = pikepdf.Array()
        pdf.Root["/OutputIntents"].append(intent)

        pdf.save()


# ---------------------------------------------------------------------------
# 7. Головна функція обробки
# ---------------------------------------------------------------------------

def process_pdf(
    pdf_path: str,
    mode: str,
    dpi: int,
    odd_corners: dict[str, tuple[float, float]],
    even_corners: dict[str, tuple[float, float]],
    output_suffix: str,
    icc_path: Path | None = None,
    print_mode: str = "double",
    interpolation: str = "INTER_LANCZOS4",
    compression: str = "tiff_lzw",
    algorithm: str = "pymupdf",
    log_callback: Callable[[str], None] | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
    stop_event: threading.Event | None = None,
) -> str | None:
    """
    Повний цикл обробки PDF:
      растеризація → warp (опційно) → конвертація кольору (тільки PyMuPDF) →
      збірка PDF → призначення ICC.

    При algorithm="ghostscript" растеризація виконується напряму у цільовому
    кольоровому просторі — крок конвертації пропускається.
    При algorithm="pymupdf" растеризація завжди у RGB, конвертація — після warp.

    :param pdf_path:          Шлях до вхідного PDF.
    :param mode:              «cmyk», «grayscale», «rgb», «cmyk_warp», «grayscale_warp», «rgb_warp».
    :param dpi:               Роздільна здатність обробки.
    :param odd_corners:       Зміщення кутів для непарних сторінок (мм).
    :param even_corners:      Зміщення кутів для парних сторінок (мм).
    :param output_suffix:     Суфікс, що додається до імені файлу перед «.pdf».
    :param icc_path:          Шлях до .icc-файлу. None → профіль не вбудовується.
    :param print_mode:        «double» — парні/непарні; «single» — всі через FRONT.
    :param interpolation:     Ім'я константи cv2 для warpPerspective.
    :param compression:       Стиснення проміжних TIFF: «tiff_lzw», «tiff_deflate», «none».
    :param algorithm:         «pymupdf» або «ghostscript».
    :param log_callback:      Функція, що отримує рядки логу в реальному часі.
    :param progress_callback: Функція progress_callback(current, total) після кожної сторінки.
    :param stop_event:        threading.Event; зупиняє обробку після поточної сторінки.
    :return:                  Шлях до вихідного PDF-файлу, або None якщо скасовано.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"Файл не знайдено: {pdf_path}")

    valid_modes = {"cmyk", "grayscale", "rgb", "cmyk_warp", "grayscale_warp", "rgb_warp"}
    if mode not in valid_modes:
        raise ValueError(f"Невідомий режим «{mode}». Допустимі: {valid_modes}")

    use_warp  = mode.endswith("_warp")
    base_mode = mode.removesuffix("_warp")

    # Кольоровий режим растра визначається автоматично з base_mode
    _color_mode_map = {"cmyk": "cmyk", "grayscale": "gray", "rgb": "rgb"}
    color_mode = _color_mode_map[base_mode]

    interp_const = _INTERP_MAP.get(interpolation, cv2.INTER_LANCZOS4)

    # --- Растеризація ---
    _log(
        f"[processor] Растеризація: {pdf_path.name} @ {dpi} DPI  "
        f"[{color_mode.upper()}]  алгоритм={algorithm}",
        log_callback,
    )
    pages = rasterize_pdf(
        str(pdf_path), dpi=dpi, algorithm=algorithm,
        color_mode=color_mode, log_callback=log_callback,
    )
    total = len(pages)
    _log(f"[processor] Сторінок растеризовано: {total}", log_callback)

    # При Ghostscript сторінки вже у цільовому кольоровому просторі
    gs_direct = (algorithm == "ghostscript" and _find_ghostscript() is not None)
    if gs_direct:
        _log(
            f"[processor] Растеризовано напряму у {color_mode.upper()} — конвертація не потрібна",
            log_callback,
        )

    if use_warp and print_mode == "single":
        _log("[processor] Режим: 1-сторонній друк — деформація FRONT для всіх сторінок", log_callback)

    # --- Обробка сторінок ---
    processed = []
    cancelled = False

    for i, page_img in enumerate(pages):
        if stop_event is not None and stop_event.is_set():
            _log(f"[processor] ⛔ Сигнал зупинки отримано після сторінки {i}", log_callback)
            cancelled = True
            break

        page_num = i + 1
        is_odd   = (page_num % 2 == 1)

        _log(f"[processor] Растрування сторінки {page_num} / {total}...", log_callback)

        # Деформація (підтримує будь-який PIL-режим)
        if use_warp:
            if print_mode == "single":
                corners    = odd_corners
                side_label = "FRONT (1-ст друк)"
            else:
                corners    = odd_corners if is_odd else even_corners
                side_label = "FRONT/непарна" if is_odd else "BACK/парна"

            _log(
                f"[processor] Застосування деформації: сторінка {page_num} / {total} ({side_label})",
                log_callback,
            )
            page_img = apply_warp(page_img, corners, dpi, interpolation=interp_const)

        # Конвертація кольору — лише для PyMuPDF (GS вже повернув правильний режим)
        if not gs_direct:
            if base_mode == "cmyk":
                page_img = convert_to_cmyk(page_img)
            elif base_mode == "grayscale":
                page_img = convert_to_grayscale(page_img)
            # rgb: PyMuPDF вже повертає RGB — нічого не робимо

        processed.append(page_img)

        if progress_callback is not None:
            try:
                progress_callback(page_num, total)
            except Exception:
                pass

    # --- Скасування ---
    if cancelled:
        _log("⛔ Конвертацію зупинено користувачем. Файл не збережено.", log_callback)
        return None

    # --- Формування шляху вихідного файлу ---
    output_name = pdf_path.stem + output_suffix + ".pdf"
    output_path = pdf_path.parent / output_name

    if output_path.exists():
        counter = 2
        while True:
            candidate = pdf_path.parent / f"{pdf_path.stem}{output_suffix}_{counter}.pdf"
            if not candidate.exists():
                output_path = candidate
                _log(f"[processor] Файл вже існує. Збережено як: {output_path.name}", log_callback)
                break
            counter += 1

    # --- Збирання PDF ---
    cs_label_map = {"cmyk": "CMYK", "grayscale": "Grayscale", "rgb": "RGB"}
    cs_label = cs_label_map.get(base_mode, "CMYK")

    _log(f"[processor] Збирання PDF: {output_path.name}", log_callback)
    assemble_pdf(processed, str(output_path), dpi=dpi, compression=compression, log_callback=log_callback)

    # --- Призначення ICC-профілю ---
    if icc_path is not None:
        icc_path = Path(icc_path)
        if icc_path.exists():
            assign_icc_profile(str(output_path), icc_path, cs_label, log_callback=log_callback)
            _log(f"[processor] {cs_label} профіль призначено (embedded): {icc_path.name}", log_callback)
            _log("[processor] Числові значення кольорів збережено без змін", log_callback)
        else:
            _log(f"[processor] УВАГА: ICC-профіль не знайдено: {icc_path} — OutputIntent не додається.", log_callback)
    else:
        _log(f"[processor] {cs_label} — без профілю (OutputIntent не додається)", log_callback)

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    _log(f"[processor] Збережено: {output_path.name} ({file_size_mb:.1f} MB)", log_callback)
    _log(f"[processor] Готово! Збережено: {output_path}", log_callback)
    return str(output_path)
