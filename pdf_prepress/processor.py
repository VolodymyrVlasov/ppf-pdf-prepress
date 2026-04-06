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
from pathlib import Path

import cv2
import img2pdf
import numpy as np
import pikepdf
from PIL import Image


# Коренева директорія модуля та папка ICC-профілів
_HERE = Path(__file__).parent
ICC_DIR = _HERE / "icc_profiles"   # публічна константа, імпортується gui.py


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
) -> list[Image.Image]:
    """
    Растеризує кожну сторінку PDF у PIL Image через Ghostscript.

    Ghostscript використовує прапор -dColorConversionStrategy=/LeaveColorUnchanged,
    який забороняє будь-яке перетворення колірних значень.
    Числа пікселів у вихідних зображеннях збігаються з оригінальними.

    Якщо Ghostscript не знайдено — використовується PyMuPDF як запасний варіант
    (лише для RGB; CMYK-значення у цьому режимі не гарантовано збережуться).

    :param pdf_path:    Шлях до вхідного PDF-файлу.
    :param dpi:         Роздільна здатність у точках на дюйм.
    :param colorspace:  Цільовий колірний простір: «cmyk», «grayscale», «rgb».
    :return:            Список PIL Image (по одному на сторінку).
    """
    pdf_path = Path(pdf_path)
    colorspace = colorspace.lower()

    gs_exe = _find_ghostscript()

    if gs_exe:
        return _rasterize_via_ghostscript(pdf_path, dpi, colorspace, gs_exe)
    else:
        print(
            "[processor] УВАГА: Ghostscript не знайдено. "
            "Використовується PyMuPDF (RGB). "
            "Числові значення CMYK можуть змінитись. "
            "Встановіть Ghostscript для коректної роботи."
        )
        return _rasterize_via_pymupdf(pdf_path, dpi, colorspace)


def _rasterize_via_ghostscript(
    pdf_path: Path,
    dpi: int,
    colorspace: str,
    gs_exe: str,
) -> list[Image.Image]:
    """
    Растеризація через Ghostscript.
    Кожна сторінка зберігається як окремий TIFF у тимчасовій папці.
    """
    # Вибір пристрою GS залежно від цільового колірного простору
    device_map = {
        "cmyk":      "tiff32nc",   # 4-канальний TIFF, CMYK
        "grayscale": "tiffgray",   # 1-канальний TIFF, Grayscale
        "rgb":       "tiff24nc",   # 3-канальний TIFF, RGB
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
            # Критичний прапор: заборона будь-якої конвертації кольорів
            "-dColorConversionStrategy=/LeaveColorUnchanged",
            # Вимикаємо CIE-нормалізацію (вона може змінювати числа)
            "-dUseCIEColor=false",
            f"-sOutputFile={output_pattern}",
            str(pdf_path),
        ]

        print(f"[processor] Ghostscript: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Ghostscript завершився з помилкою (код {result.returncode}):\n"
                f"{result.stderr.strip()}"
            )

        # Зчитуємо всі TIFF-файли у відсортованому порядку
        tiff_files = sorted(Path(tmpdir).glob("page_*.tif"))
        if not tiff_files:
            raise RuntimeError(
                f"Ghostscript не створив жодного TIFF-файлу. "
                f"Stderr:\n{result.stderr.strip()}"
            )

        images = []
        for tiff_file in tiff_files:
            img = Image.open(tiff_file).copy()   # .copy() звільняє файловий дескриптор
            images.append(img)

    return images


def _rasterize_via_pymupdf(
    pdf_path: Path,
    dpi: int,
    colorspace: str,
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

        # Груба конвертація (без збереження числових значень!)
        if colorspace == "cmyk" and pil_img.mode != "CMYK":
            pil_img = pil_img.convert("CMYK")
        elif colorspace == "grayscale" and pil_img.mode != "L":
            pil_img = pil_img.convert("L")

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
) -> Image.Image:
    """
    Застосовує перспективну деформацію до зображення.

    corners_mm — зміщення кутів у міліметрах від початкового положення:
        {"tl": (dx, dy), "tr": (dx, dy), "bl": (dx, dy), "br": (dx, dy)}
    Позитивний dx → вправо, позитивний dy → вниз.

    Колірні значення пікселів не змінюються — виконується лише геометрична
    трансформація координат.

    :param image:      Вхідне PIL Image.
    :param corners_mm: Словник зміщень для кожного з чотирьох кутів.
    :param dpi:        Роздільна здатність (для перетворення мм → пікселі).
    :return:           PIL Image після деформації (той самий розмір полотна).
    """
    px_per_mm = dpi / 25.4
    w, h = image.size

    # Вихідні кути: TL, TR, BL, BR
    src_pts = np.float32([
        [0,     0    ],   # tl
        [w - 1, 0    ],   # tr
        [0,     h - 1],   # bl
        [w - 1, h - 1],   # br
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
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_REPLICATE,
    )

    # Image.fromarray на 4-канальному масиві повертає "RGBA", а не "CMYK".
    # Використовуємо frombytes, щоб уникнути помилкової колірної інтерпретації.
    result = Image.fromarray(warped)
    if result.mode != original_mode:
        result = Image.frombytes(original_mode, (w, h), warped.tobytes())

    return result


# ---------------------------------------------------------------------------
# 5. Збирання вихідного PDF
# ---------------------------------------------------------------------------

def assemble_pdf(images: list[Image.Image], output_path: str, dpi: int = 300) -> None:
    """
    Зберігає список PIL Images як єдиний PDF-файл через img2pdf.

    Числові значення пікселів передаються без змін.

    :param images:      Список зображень (по одному на сторінку).
    :param output_path: Шлях до вихідного PDF.
    :param dpi:         Роздільна здатність для метаданих PDF.
    """
    output_path = str(output_path)
    img_bytes_list = []

    for img in images:
        buf = io.BytesIO()
        if img.mode not in ("RGB", "L", "CMYK"):
            img = img.convert("RGB")

        # TIFF зберігає числові значення без втрат і підтримує CMYK
        img.save(buf, format="TIFF", dpi=(dpi, dpi))
        img_bytes_list.append(buf.getvalue())

    layout_fun = img2pdf.get_fixed_dpi_layout_fun((dpi, dpi))

    with open(output_path, "wb") as f:
        f.write(img2pdf.convert(img_bytes_list, layout_fun=layout_fun))


# ---------------------------------------------------------------------------
# 6. Призначення ICC-профілю (вбудовування як OutputIntent)
# ---------------------------------------------------------------------------

def assign_icc_profile(
    pdf_path: str,
    icc_path: Path,
    color_space: str,
) -> None:
    """
    Вбудовує ICC-профіль у готовий PDF як OutputIntent (стандарт PDF/X).

    НЕ змінює числові значення пікселів — лише додає метадані,
    що описують, у якому колірному просторі вже записані числа.
    RIP-процесор читає цей тег і коректно інтерпретує дані.

    :param pdf_path:    Шлях до PDF-файлу для модифікації (перезаписується).
    :param icc_path:    Шлях до .icc-файлу профілю.
    :param color_space: «CMYK», «Grayscale» або «RGB».
    """
    icc_path = Path(icc_path)
    # Кількість каналів відповідно до колірного простору
    n_channels = {"CMYK": 4, "Grayscale": 1, "RGB": 3}.get(color_space, 4)

    with pikepdf.open(str(pdf_path), allow_overwriting_input=True) as pdf:
        icc_data = icc_path.read_bytes()

        icc_stream = pikepdf.Stream(pdf, icc_data)
        # /N — кількість компонент кольору (обов'язковий ключ для ICC-потоків)
        icc_stream["/N"] = n_channels

        intent = pikepdf.Dictionary(
            Type=pikepdf.Name("/OutputIntent"),
            # /GTS_PDFA1 — стандартний ідентифікатор для друкарських профілів
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
) -> str:
    """
    Повний цикл обробки PDF:
      растеризація (GS, без зміни чисел) → warp → збірка PDF → призначення ICC.

    :param pdf_path:      Шлях до вхідного PDF.
    :param mode:          «cmyk», «grayscale», «cmyk_warp», «grayscale_warp».
    :param dpi:           Роздільна здатність обробки.
    :param odd_corners:   Зміщення кутів для непарних сторінок (мм).
    :param even_corners:  Зміщення кутів для парних сторінок (мм).
    :param output_suffix: Суфікс, що додається до імені файлу перед «.pdf».
    :param icc_path:      Шлях до .icc-файлу для вбудовування як OutputIntent.
                          None → профіль не вбудовується.
    :return:              Шлях до вихідного PDF-файлу.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"Файл не знайдено: {pdf_path}")

    valid_modes = {"cmyk", "grayscale", "rgb", "cmyk_warp", "grayscale_warp", "rgb_warp"}
    if mode not in valid_modes:
        raise ValueError(f"Невідомий режим «{mode}». Допустимі: {valid_modes}")

    use_warp = mode.endswith("_warp")
    base_mode = mode.removesuffix("_warp")   # "cmyk" | "grayscale" | "rgb"
    colorspace = base_mode                   # передається у rasterize_pdf без змін

    # --- Растеризація (Ghostscript зберігає числові значення кольорів) ---
    print(f"[processor] Растеризація: {pdf_path.name} @ {dpi} DPI  [{colorspace.upper()}]")
    pages = rasterize_pdf(str(pdf_path), dpi=dpi, colorspace=colorspace)
    print(f"[processor] Сторінок растеризовано: {len(pages)}")

    # --- Геометрична деформація (за потреби) ---
    processed = []
    for i, page_img in enumerate(pages):
        page_num = i + 1                    # 1-based
        is_odd   = (page_num % 2 == 1)     # непарна (FRONT) = True

        if use_warp:
            corners = odd_corners if is_odd else even_corners
            page_img = apply_warp(page_img, corners, dpi)
            print(
                f"[processor] Стор. {page_num}: warp "
                f"({'FRONT/непарна' if is_odd else 'BACK/парна'})"
            )

        processed.append(page_img)

    # --- Формування шляху вихідного файлу (поряд із вхідним, без перезапису) ---
    output_name = pdf_path.stem + output_suffix + ".pdf"
    output_path = pdf_path.parent / output_name

    if output_path.exists():
        counter = 2
        while True:
            candidate = pdf_path.parent / f"{pdf_path.stem}{output_suffix}_{counter}.pdf"
            if not candidate.exists():
                output_path = candidate
                print(f"[processor] Файл вже існує. Збережено як: {output_path.name}")
                break
            counter += 1

    # --- Збирання PDF ---
    print(f"[processor] Збирання PDF: {output_path.name}")
    assemble_pdf(processed, str(output_path), dpi=dpi)

    # --- Призначення ICC-профілю як метаданих (без зміни пікселів) ---
    cs_label_map = {"cmyk": "CMYK", "grayscale": "Grayscale", "rgb": "RGB"}
    cs_label = cs_label_map.get(base_mode, "CMYK")

    if icc_path is not None:
        icc_path = Path(icc_path)
        if icc_path.exists():
            print(f"[processor] Призначення ICC-профілю: {icc_path.name}  [{cs_label}]")
            assign_icc_profile(str(output_path), icc_path, cs_label)
            print(f"[processor] {cs_label} профіль призначено (embedded): {icc_path.name}")
            print(f"[processor] Числові значення кольорів збережено без змін")
        else:
            print(f"[processor] УВАГА: ICC-профіль не знайдено: {icc_path} — OutputIntent не додається.")
    else:
        print(f"[processor] {cs_label} — без профілю (OutputIntent не додається)")

    print(f"[processor] Готово! Збережено: {output_path}")
    return str(output_path)
