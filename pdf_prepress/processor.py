"""
processor.py — Ядро обробки зображень для PDF пре-пресу.

КЛЮЧОВА КОНЦЕПЦІЯ:
  ICC-профіль лише призначається (вбудовується як метадані OutputIntent).
  Числові значення пікселів НЕ змінюються.
  Растеризація виконується через Ghostscript із прапором
  -dColorConversionStrategy=/LeaveColorUnchanged, що гарантує збереження
  оригінальних колірних значень (наприклад, CMYK 0,0,0,100 → залишається 0,0,0,100).
"""

import io
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Callable

import cv2
import img2pdf
import numpy as np
import pikepdf
from PIL import Image


# Коренева директорія модуля та папка ICC-профілів
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

def _find_ghostscript() -> str | None:
    """
    Знаходить виконуваний файл Ghostscript у PATH.
    На Windows шукає gswin64c → gswin32c, на Unix — gs.
    Повертає None, якщо GS не встановлено.
    """
    for name in ("gswin64c", "gswin32c", "gs"):
        if shutil.which(name):
            return name
    return None


# ---------------------------------------------------------------------------
# 1. Растеризація PDF через Ghostscript
# ---------------------------------------------------------------------------

def rasterize_pdf(
    pdf_path: str,
    dpi: int = 300,
    colorspace: str = "cmyk",
    log_callback: Callable[[str], None] | None = None,
) -> list[Image.Image]:
    """
    Растеризує кожну сторінку PDF у PIL Image через Ghostscript.

    Ghostscript використовує прапор -dColorConversionStrategy=/LeaveColorUnchanged,
    який забороняє будь-яке перетворення колірних значень.
    Числа пікселів у вихідних зображеннях збігаються з оригінальними.

    Якщо Ghostscript не знайдено — використовується PyMuPDF як запасний варіант
    (лише для RGB; CMYK-значення у цьому режимі не гарантовано збережуться).

    :param pdf_path:     Шлях до вхідного PDF-файлу.
    :param dpi:          Роздільна здатність у точках на дюйм.
    :param colorspace:   Цільовий колірний простір: «cmyk», «grayscale», «rgb».
    :param log_callback: Необов'язкова функція для передачі рядків логу.
    :return:             Список PIL Image (по одному на сторінку).
    """
    pdf_path = Path(pdf_path)
    colorspace = colorspace.lower()

    gs_exe = _find_ghostscript()

    if gs_exe:
        return _rasterize_via_ghostscript(pdf_path, dpi, colorspace, gs_exe, log_callback)
    else:
        _log(
            "[processor] УВАГА: Ghostscript не знайдено. "
            "Використовується PyMuPDF (RGB). "
            "Числові значення CMYK можуть змінитись. "
            "Встановіть Ghostscript для коректної роботи.",
            log_callback,
        )
        return _rasterize_via_pymupdf(pdf_path, dpi, colorspace, log_callback)


def _rasterize_via_ghostscript(
    pdf_path: Path,
    dpi: int,
    colorspace: str,
    gs_exe: str,
    log_callback: Callable[[str], None] | None = None,
) -> list[Image.Image]:
    """
    Растеризація через Ghostscript.
    Кожна сторінка зберігається як окремий TIFF у тимчасовій папці.
    Вивід GS передається рядок за рядком у log_callback.
    """
    device_map = {
        "cmyk":      "tiff32nc",
        "grayscale": "tiffgray",
        "rgb":       "tiff24nc",
    }
    device = device_map.get(colorspace, "tiff32nc")

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
            "-dUseCIEColor=false",
            f"-sOutputFile={output_pattern}",
            str(pdf_path),
        ]

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
    colorspace: str,
    log_callback: Callable[[str], None] | None = None,
) -> list[Image.Image]:
    """
    Запасний варіант растеризації через PyMuPDF (fitz).
    Завжди повертає RGB; для CMYK-режиму виконується проста Pillow-конвертація
    (значення пікселів при цьому змінюються — лише для аварійного запуску).
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

        if colorspace == "cmyk" and pil_img.mode != "CMYK":
            pil_img = pil_img.convert("CMYK")
        elif colorspace == "grayscale" and pil_img.mode != "L":
            pil_img = pil_img.convert("L")

        _log(f"[processor] PyMuPDF: сторінка {page_num + 1}", log_callback)
        images.append(pil_img)

    doc.close()
    return images


# ---------------------------------------------------------------------------
# 2. Конвертація у CMYK (утиліта для прямого виклику / тестів)
# ---------------------------------------------------------------------------

def convert_to_cmyk(image: Image.Image) -> Image.Image:
    """
    Конвертує PIL Image у режим CMYK засобами Pillow.

    УВАГА: ця функція виконує математичне перерахування пікселів
    і НЕ гарантує збереження оригінальних колірних значень.
    У повному циклі обробки (process_pdf) colorspace-конвертація
    виконується Ghostscript без зміни числових значень.

    :param image: Вхідне зображення.
    :return:      Зображення у режимі CMYK.
    """
    if image.mode == "CMYK":
        return image
    if image.mode not in ("RGB",):
        image = image.convert("RGB")
    return image.convert("CMYK")


# ---------------------------------------------------------------------------
# 3. Конвертація у відтінки сірого (утиліта для прямого виклику / тестів)
# ---------------------------------------------------------------------------

def convert_to_grayscale(image: Image.Image) -> Image.Image:
    """
    Конвертує PIL Image у режим відтінків сірого (L).

    :param image: Вхідне зображення.
    :return:      Зображення у режимі «L».
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

    Колірні значення пікселів не змінюються — виконується лише геометрична
    трансформація координат.

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

    original_mode = image.mode
    cv_img = np.array(image)

    warped = cv2.warpPerspective(
        cv_img,
        M,
        (w, h),
        flags=interpolation,
        borderMode=cv2.BORDER_REPLICATE,
    )

    result = Image.fromarray(warped)
    if result.mode != original_mode:
        result = Image.frombytes(original_mode, (w, h), warped.tobytes())

    return result


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

    :param images:      Список зображень (по одному на сторінку).
    :param output_path: Шлях до вихідного PDF.
    :param dpi:         Роздільна здатність для метаданих PDF.
    :param compression: Стиснення проміжних TIFF: «tiff_lzw», «tiff_deflate», «none».
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
    RIP-процесор читає цей тег і коректно інтерпретує дані.

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
    log_callback: Callable[[str], None] | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
    stop_event: threading.Event | None = None,
) -> str | None:
    """
    Повний цикл обробки PDF:
      растеризація (GS, без зміни чисел) → warp → збірка PDF → призначення ICC.

    :param pdf_path:          Шлях до вхідного PDF.
    :param mode:              «cmyk», «grayscale», «cmyk_warp», «grayscale_warp», «rgb», «rgb_warp».
    :param dpi:               Роздільна здатність обробки.
    :param odd_corners:       Зміщення кутів для непарних сторінок (мм).
    :param even_corners:      Зміщення кутів для парних сторінок (мм).
    :param output_suffix:     Суфікс, що додається до імені файлу перед «.pdf».
    :param icc_path:          Шлях до .icc-файлу. None → профіль не вбудовується.
    :param print_mode:        «double» — парні/непарні; «single» — всі через FRONT.
    :param interpolation:     Ім'я константи cv2 для warpPerspective (напр. «INTER_LANCZOS4»).
    :param compression:       Стиснення проміжних TIFF: «tiff_lzw», «tiff_deflate», «none».
    :param log_callback:      Функція, що отримує рядки логу в реальному часі.
    :param progress_callback: Функція progress_callback(current, total) після кожної сторінки.
    :param stop_event:        threading.Event; якщо встановлено — зупиняє обробку після поточної сторінки.
    :return:                  Шлях до вихідного PDF-файлу, або None якщо скасовано.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"Файл не знайдено: {pdf_path}")

    valid_modes = {"cmyk", "grayscale", "rgb", "cmyk_warp", "grayscale_warp", "rgb_warp"}
    if mode not in valid_modes:
        raise ValueError(f"Невідомий режим «{mode}». Допустимі: {valid_modes}")

    use_warp    = mode.endswith("_warp")
    base_mode   = mode.removesuffix("_warp")
    colorspace  = base_mode

    interp_const = _INTERP_MAP.get(interpolation, cv2.INTER_LANCZOS4)

    # --- Растеризація ---
    _log(f"[processor] Растеризація: {pdf_path.name} @ {dpi} DPI  [{colorspace.upper()}]", log_callback)
    pages = rasterize_pdf(str(pdf_path), dpi=dpi, colorspace=colorspace, log_callback=log_callback)
    total = len(pages)
    _log(f"[processor] Сторінок растеризовано: {total}", log_callback)

    if use_warp and print_mode == "single":
        _log("[processor] Режим: 1-сторонній друк — деформація FRONT для всіх сторінок", log_callback)

    # --- Обробка сторінок ---
    processed = []
    cancelled = False

    for i, page_img in enumerate(pages):
        # Перевірка сигналу зупинки
        if stop_event is not None and stop_event.is_set():
            _log(f"[processor] ⛔ Сигнал зупинки отримано після сторінки {i}", log_callback)
            cancelled = True
            break

        page_num = i + 1
        is_odd   = (page_num % 2 == 1)

        _log(f"[processor] Растрування сторінки {page_num} / {total}...", log_callback)

        if use_warp:
            if print_mode == "single":
                corners = odd_corners
                side_label = "FRONT (1-ст друк)"
            else:
                corners    = odd_corners if is_odd else even_corners
                side_label = "FRONT/непарна" if is_odd else "BACK/парна"

            _log(
                f"[processor] Застосування деформації: сторінка {page_num} / {total} ({side_label})",
                log_callback,
            )
            page_img = apply_warp(page_img, corners, dpi, interpolation=interp_const)

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

    _log(f"[processor] Конвертація кольору: {cs_label}", log_callback)
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
