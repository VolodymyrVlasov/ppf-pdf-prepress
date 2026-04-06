"""
test_processor.py — Юніт- та інтеграційні тести для processor.py.

Запуск:
    pytest tests/ -v
    # або через run_tests.bat у папці pdf_prepress/
"""

import io
from pathlib import Path

import pytest
from PIL import Image

# Імпорти processor — шлях додано у conftest.py
from processor import (
    apply_warp,
    convert_to_cmyk,
    convert_to_grayscale,
    process_pdf,
    rasterize_pdf,
)


# ---------------------------------------------------------------------------
# Допоміжні функції
# ---------------------------------------------------------------------------

def _make_pdf_bytes() -> bytes:
    """
    Створює мінімальний 1-сторінковий PDF (200×200 пт) у пам'яті
    за допомогою reportlab.

    Сторінка залита суцільним червоним кольором.
    """
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.units import pt

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(200 * pt, 200 * pt))
    c.setFillColorRGB(1, 0, 0)          # червоний фон
    c.rect(0, 0, 200 * pt, 200 * pt, fill=1, stroke=0)
    c.save()
    return buf.getvalue()


def _make_pdf_file(tmp_path: Path) -> Path:
    """Записує тестовий PDF у тимчасовий файл і повертає його шлях."""
    pdf_file = tmp_path / "test_input.pdf"
    pdf_file.write_bytes(_make_pdf_bytes())
    return pdf_file


def _red_rgb_image(size: tuple[int, int] = (100, 100)) -> Image.Image:
    """Повертає RGB-зображення заданого розміру, залите червоним кольором."""
    img = Image.new("RGB", size, color=(255, 0, 0))
    return img


_ZERO_CORNERS: dict[str, list[float]] = {
    "tl": [0.0, 0.0],
    "tr": [0.0, 0.0],
    "bl": [0.0, 0.0],
    "br": [0.0, 0.0],
}


# ---------------------------------------------------------------------------
# Тести
# ---------------------------------------------------------------------------

class TestRasterizePdf:
    """Тести функції rasterize_pdf()."""

    def test_returns_list_of_pil_images(self, tmp_path: Path) -> None:
        """rasterize_pdf має повернути список PIL Images."""
        pdf_file = _make_pdf_file(tmp_path)
        result = rasterize_pdf(str(pdf_file), dpi=72)

        assert isinstance(result, list), "Результат має бути списком"
        assert len(result) == 1, "Має бути рівно одна сторінка"

    def test_image_has_nonzero_size(self, tmp_path: Path) -> None:
        """Кожен елемент списку — PIL Image із ненульовими розмірами."""
        pdf_file = _make_pdf_file(tmp_path)
        result = rasterize_pdf(str(pdf_file), dpi=72)

        img = result[0]
        assert isinstance(img, Image.Image), "Елемент має бути PIL Image"
        w, h = img.size
        assert w > 0 and h > 0, f"Розмір зображення має бути > 0, отримано {img.size}"

    def test_dpi_affects_output_size(self, tmp_path: Path) -> None:
        """Вищий DPI → більший розмір пікселів."""
        pdf_file = _make_pdf_file(tmp_path)
        img_low  = rasterize_pdf(str(pdf_file), dpi=72)[0]
        img_high = rasterize_pdf(str(pdf_file), dpi=150)[0]

        assert img_high.size[0] > img_low.size[0], (
            "Ширина при DPI=150 має бути більшою за ширину при DPI=72"
        )


class TestConvertToCmyk:
    """Тести функції convert_to_cmyk()."""

    def test_output_mode_is_cmyk(self) -> None:
        """Результат має бути у режимі CMYK."""
        img = _red_rgb_image()
        result = convert_to_cmyk(img)
        assert result.mode == "CMYK", f"Очікувано CMYK, отримано {result.mode!r}"

    def test_accepts_rgba_input(self) -> None:
        """convert_to_cmyk має коректно обробляти RGBA-зображення."""
        img = Image.new("RGBA", (50, 50), color=(0, 255, 0, 128))
        result = convert_to_cmyk(img)
        assert result.mode == "CMYK"

    def test_output_size_unchanged(self) -> None:
        """Розмір зображення не має змінюватись після конвертації."""
        img = _red_rgb_image((80, 60))
        result = convert_to_cmyk(img)
        assert result.size == (80, 60)


class TestConvertToGrayscale:
    """Тести функції convert_to_grayscale()."""

    def test_output_mode_is_l(self) -> None:
        """Результат має бути у режимі L (відтінки сірого)."""
        img = _red_rgb_image()
        result = convert_to_grayscale(img)
        assert result.mode == "L", f"Очікувано L, отримано {result.mode!r}"

    def test_output_size_unchanged(self) -> None:
        """Розмір зображення не має змінюватись."""
        img = _red_rgb_image((40, 80))
        result = convert_to_grayscale(img)
        assert result.size == (40, 80)


class TestApplyWarp:
    """Тести функції apply_warp()."""

    def test_zero_offsets_returns_same_size(self) -> None:
        """При нульових зміщеннях розмір результату збігається з вхідним."""
        img = _red_rgb_image((100, 100))
        result = apply_warp(img, _ZERO_CORNERS, dpi=300)

        assert isinstance(result, Image.Image)
        assert result.size == img.size

    def test_zero_offsets_no_exception(self) -> None:
        """apply_warp із нульовими зміщеннями не має кидати виключень."""
        img = _red_rgb_image((100, 100))
        apply_warp(img, _ZERO_CORNERS, dpi=300)   # просто не повинно впасти

    def test_nonzero_offsets_returns_pil_image(self) -> None:
        """apply_warp із ненульовими зміщеннями має повернути PIL Image."""
        corners = {
            "tl": ( 2.5,  0.0),
            "tr": (-2.5,  0.0),
            "bl": ( 3.0,  0.0),
            "br": (-3.0,  0.0),
        }
        img = _red_rgb_image((200, 200))
        result = apply_warp(img, corners, dpi=300)

        assert isinstance(result, Image.Image)
        assert result.size == img.size

    def test_warp_preserves_cmyk_mode(self) -> None:
        """apply_warp має зберегти режим CMYK після деформації (не RGBA)."""
        img = Image.new("CMYK", (100, 100), color=(10, 20, 30, 40))
        result = apply_warp(img, _ZERO_CORNERS, dpi=300)
        assert result.mode == "CMYK", (
            f"Режим CMYK має зберегтись, отримано {result.mode!r}"
        )

    def test_warp_preserves_grayscale_mode(self) -> None:
        """apply_warp має зберегти режим L після деформації."""
        img = Image.new("L", (100, 100), color=128)
        result = apply_warp(img, _ZERO_CORNERS, dpi=300)
        assert result.mode == "L", (
            f"Режим L має зберегтись, отримано {result.mode!r}"
        )


class TestFullPipeline:
    """Інтеграційний тест: повний цикл обробки через process_pdf()."""

    def test_cmyk_warp_creates_output_file(self, tmp_path: Path) -> None:
        """
        process_pdf у режимі cmyk_warp має створити вихідний PDF
        поряд із вхідним файлом.
        """
        pdf_file = _make_pdf_file(tmp_path)

        output_path = process_pdf(
            pdf_path=str(pdf_file),
            mode="cmyk_warp",
            dpi=72,                         # низький DPI для швидкості тесту
            odd_corners=_ZERO_CORNERS,
            even_corners=_ZERO_CORNERS,
            output_suffix="_TEST_CMYK",
        )

        out = Path(output_path)
        assert out.exists(), f"Вихідний файл не знайдено: {out}"
        assert out.parent == tmp_path, "Вихідний файл має бути в тій самій папці, що й вхідний"
        assert out.suffix == ".pdf", "Вихідний файл має мати розширення .pdf"
        assert out.stat().st_size > 0, "Вихідний файл не має бути порожнім"

    def test_grayscale_creates_output_file(self, tmp_path: Path) -> None:
        """process_pdf у режимі grayscale має створити вихідний PDF."""
        pdf_file = _make_pdf_file(tmp_path)

        output_path = process_pdf(
            pdf_path=str(pdf_file),
            mode="grayscale",
            dpi=72,
            odd_corners=_ZERO_CORNERS,
            even_corners=_ZERO_CORNERS,
            output_suffix="_TEST_GRAY",
        )

        out = Path(output_path)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_output_suffix_in_filename(self, tmp_path: Path) -> None:
        """Суфікс має бути включений у назву вихідного файлу."""
        pdf_file = _make_pdf_file(tmp_path)
        suffix = "_MY_SUFFIX"

        output_path = process_pdf(
            pdf_path=str(pdf_file),
            mode="cmyk",
            dpi=72,
            odd_corners=_ZERO_CORNERS,
            even_corners=_ZERO_CORNERS,
            output_suffix=suffix,
        )

        assert suffix in Path(output_path).name, (
            f"Суфікс {suffix!r} має бути у назві файлу {Path(output_path).name!r}"
        )

    def test_invalid_mode_raises_value_error(self, tmp_path: Path) -> None:
        """Невідомий режим має призводити до ValueError."""
        pdf_file = _make_pdf_file(tmp_path)

        with pytest.raises(ValueError, match="Невідомий режим"):
            process_pdf(
                pdf_path=str(pdf_file),
                mode="unknown_mode",
                dpi=72,
                odd_corners=_ZERO_CORNERS,
                even_corners=_ZERO_CORNERS,
                output_suffix="_X",
            )

    def test_missing_file_raises_file_not_found(self, tmp_path: Path) -> None:
        """Відсутній вхідний файл має призводити до FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            process_pdf(
                pdf_path=str(tmp_path / "nonexistent.pdf"),
                mode="cmyk",
                dpi=72,
                odd_corners=_ZERO_CORNERS,
                even_corners=_ZERO_CORNERS,
                output_suffix="_X",
            )
