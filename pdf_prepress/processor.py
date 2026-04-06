"""
processor.py — Ядро обробки зображень для PDF пре-пресу.

Містить функції для растеризації PDF, конвертації кольорів,
геометричних трансформацій та збирання вихідного PDF.
"""

import io
from pathlib import Path

import fitz  # PyMuPDF
import cv2
import numpy as np
import img2pdf
from PIL import Image, ImageCms


# Шлях до ICC-профілю (поряд з цим файлом)
_HERE = Path(__file__).parent
_ICC_PATH = _HERE / "ISOcoated_v2_eci.icc"


# ---------------------------------------------------------------------------
# 1. Растеризація PDF
# ---------------------------------------------------------------------------

def rasterize_pdf(pdf_path: str, dpi: int = 300) -> list[Image.Image]:
    """
    Растеризує кожну сторінку PDF у PIL Image із заданим DPI.

    :param pdf_path: Шлях до вхідного PDF-файлу.
    :param dpi:      Роздільна здатність у точках на дюйм.
    :return:         Список PIL Image (по одному на сторінку).
    """
    pdf_path = str(pdf_path)
    doc = fitz.open(pdf_path)
    images = []

    # Масштабний коефіцієнт відносно стандартних 72 DPI у PyMuPDF
    scale = dpi / 72.0
    matrix = fitz.Matrix(scale, scale)

    for page_num in range(len(doc)):
        page = doc[page_num]
        # Рендеримо сторінку у піксельний буфер
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        # Конвертуємо у PIL Image через байтовий буфер PNG
        img_bytes = pixmap.tobytes("png")
        pil_img = Image.open(io.BytesIO(img_bytes)).copy()
        images.append(pil_img)

    doc.close()
    return images


# ---------------------------------------------------------------------------
# 2. Конвертація у CMYK
# ---------------------------------------------------------------------------

def convert_to_cmyk(image: Image.Image) -> Image.Image:
    """
    Конвертує PIL Image у режим CMYK.

    Якщо поряд із processor.py знаходиться файл ISOcoated_v2_eci.icc,
    застосовується ICC-перетворення. Інакше — пряма конвертація Pillow.

    :param image: Вхідне зображення (зазвичай RGB або RGBA).
    :return:      Зображення у режимі CMYK.
    """
    # Переводимо у RGB, щоб уникнути проблем з RGBA або палітрою
    if image.mode != "RGB":
        image = image.convert("RGB")

    if _ICC_PATH.exists():
        # --- Конвертація через ICC-профіль ---
        try:
            # sRGB — стандартний вхідний профіль
            srgb_profile = ImageCms.createProfile("sRGB")
            cmyk_profile = ImageCms.getOpenProfile(str(_ICC_PATH))

            transform = ImageCms.buildTransform(
                srgb_profile,
                cmyk_profile,
                inMode="RGB",
                outMode="CMYK",
                renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC,
            )
            return ImageCms.applyTransform(image, transform)
        except Exception as exc:
            # Якщо ICC-перетворення не вдалось — падаємо до простої конвертації
            print(f"[processor] ICC-перетворення не вдалось: {exc}. Використовується пряма конвертація.")

    # --- Пряма конвертація RGB → CMYK засобами Pillow ---
    return image.convert("CMYK")


# ---------------------------------------------------------------------------
# 3. Конвертація у відтінки сірого
# ---------------------------------------------------------------------------

def convert_to_grayscale(image: Image.Image) -> Image.Image:
    """
    Конвертує PIL Image у режим відтінків сірого (L).

    :param image: Вхідне зображення.
    :return:      Зображення у режимі «L».
    """
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

    :param image:      Вхідне PIL Image.
    :param corners_mm: Словник зміщень для кожного з чотирьох кутів.
    :param dpi:        Роздільна здатність (для перетворення мм → пікселі).
    :return:           PIL Image після деформації (той самий розмір полотна).
    """
    # 1 мм = dpi / 25.4 пікселів
    px_per_mm = dpi / 25.4

    w, h = image.size

    # Вихідні кути (перед деформацією): TL, TR, BL, BR
    src_pts = np.float32([
        [0,     0    ],   # tl
        [w - 1, 0    ],   # tr
        [0,     h - 1],   # bl
        [w - 1, h - 1],   # br
    ])

    def offset_px(key: str) -> np.ndarray:
        """Конвертує мм-зміщення у піксельне для заданого кута."""
        dx_mm, dy_mm = corners_mm.get(key, (0.0, 0.0))
        return np.float32([dx_mm * px_per_mm, dy_mm * px_per_mm])

    # Цільові кути (після деформації)
    dst_pts = np.float32([
        src_pts[0] + offset_px("tl"),
        src_pts[1] + offset_px("tr"),
        src_pts[2] + offset_px("bl"),
        src_pts[3] + offset_px("br"),
    ])

    # Матриця перспективного перетворення
    M = cv2.getPerspectiveTransform(src_pts, dst_pts)

    # Конвертуємо PIL → NumPy для OpenCV
    original_mode = image.mode
    cv_img = np.array(image)

    # cv2.warpPerspective очікує BGR для кольорових зображень,
    # але оскільки ми не змінюємо кольори — порядок каналів не важливий
    warped = cv2.warpPerspective(
        cv_img,
        M,
        (w, h),
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_REPLICATE,
    )

    # Повертаємо у PIL Image зі збереженням вихідного режиму.
    # Image.fromarray на 4-канальному масиві повертає "RGBA", а не "CMYK".
    # Використовуємо frombytes щоб уникнути помилкової колірної конвертації.
    result = Image.fromarray(warped)
    if result.mode != original_mode:
        result = Image.frombytes(original_mode, (w, h), warped.tobytes())

    return result


# ---------------------------------------------------------------------------
# 5. Збирання вихідного PDF
# ---------------------------------------------------------------------------

def assemble_pdf(images: list[Image.Image], output_path: str, dpi: int = 300) -> None:
    """
    Зберігає список PIL Images як єдиний PDF-файл.

    :param images:      Список зображень (по одному на сторінку).
    :param output_path: Шлях до вихідного PDF.
    :param dpi:         Роздільна здатність для метаданих PDF.
    """
    output_path = str(output_path)
    img_bytes_list = []

    for img in images:
        buf = io.BytesIO()
        # img2pdf найкраще працює з RGB або L; CMYK теж підтримується
        save_mode = img.mode
        if save_mode not in ("RGB", "L", "CMYK"):
            img = img.convert("RGB")
            save_mode = "RGB"

        # Зберігаємо у TIFF із DPI-метаданими
        img.save(buf, format="TIFF", dpi=(dpi, dpi))
        img_bytes_list.append(buf.getvalue())

    # Формуємо PDF з правильним розміром сторінки (у точках @ 72 dpi)
    layout_fun = img2pdf.get_fixed_dpi_layout_fun((dpi, dpi))

    with open(output_path, "wb") as f:
        f.write(img2pdf.convert(img_bytes_list, layout_fun=layout_fun))


# ---------------------------------------------------------------------------
# 6. Головна функція обробки
# ---------------------------------------------------------------------------

def process_pdf(
    pdf_path: str,
    mode: str,
    dpi: int,
    odd_corners: dict[str, tuple[float, float]],
    even_corners: dict[str, tuple[float, float]],
    output_suffix: str,
) -> str:
    """
    Повний цикл обробки PDF: растеризація → конвертація → (warp) → збірка.

    :param pdf_path:      Шлях до вхідного PDF.
    :param mode:          Режим: «cmyk», «grayscale», «cmyk_warp», «grayscale_warp».
    :param dpi:           Роздільна здатність обробки.
    :param odd_corners:   Зміщення кутів для непарних сторінок (мм).
    :param even_corners:  Зміщення кутів для парних сторінок (мм).
    :param output_suffix: Суфікс, що додається до імені файлу перед «.pdf».
    :return:              Шлях до вихідного PDF-файлу.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"Файл не знайдено: {pdf_path}")

    valid_modes = {"cmyk", "grayscale", "cmyk_warp", "grayscale_warp"}
    if mode not in valid_modes:
        raise ValueError(f"Невідомий режим «{mode}». Допустимі: {valid_modes}")

    # --- Растеризація ---
    print(f"[processor] Растеризація: {pdf_path.name} @ {dpi} DPI")
    pages = rasterize_pdf(str(pdf_path), dpi=dpi)

    use_warp = mode.endswith("_warp")
    use_cmyk = mode.startswith("cmyk")

    processed = []
    for i, page_img in enumerate(pages):
        page_num = i + 1  # номер сторінки (з 1)
        is_odd = (page_num % 2 == 1)

        # --- Конвертація кольору ---
        if use_cmyk:
            page_img = convert_to_cmyk(page_img)
            print(f"[processor] Стор. {page_num}: конвертовано у CMYK")
        else:
            page_img = convert_to_grayscale(page_img)
            print(f"[processor] Стор. {page_num}: конвертовано у відтінки сірого")

        # --- Геометрична деформація (за потреби) ---
        if use_warp:
            corners = odd_corners if is_odd else even_corners
            page_img = apply_warp(page_img, corners, dpi)
            print(f"[processor] Стор. {page_num}: застосовано warp ({'непарна' if is_odd else 'парна'})")

        processed.append(page_img)

    # --- Формування шляху вихідного файлу ---
    output_name = pdf_path.stem + output_suffix + ".pdf"
    output_path = pdf_path.parent / output_name

    # --- Збирання PDF ---
    print(f"[processor] Збирання PDF: {output_path.name}")
    assemble_pdf(processed, str(output_path), dpi=dpi)

    print(f"[processor] Готово! Збережено: {output_path}")
    return str(output_path)
