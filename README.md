# PDF Pre-Press

Інструмент підготовки PDF до друку з деформацією, конвертацією кольору та ICC профілями.  
A PDF pre-press tool with warp correction, color-space conversion, and ICC profile embedding.

![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)
![pywebview](https://img.shields.io/badge/UI-pywebview-green)
![Ghostscript](https://img.shields.io/badge/Raster-Ghostscript-orange)
![Windows 10/11](https://img.shields.io/badge/OS-Windows%2010%2F11-lightgrey)

---

## 🇺🇦 Українська

### Зміст
- [Опис](#опис)
- [Інструкція з використання](#інструкція-з-використання)
- [Технології та залежності](#технології-та-залежності)
- [Структура проекту](#структура-проекту)
- [Встановлення з GitHub](#встановлення-з-github)
- [Ліцензія](#ліцензія)

---

## Опис

**PDF Pre-Press** — це десктопна програма для Windows, яка готує PDF файли до поліграфічного друку.

✅ Растрування PDF файлів з налаштуванням DPI (72–1200)  
✅ Конвертація колірного простору: CMYK, Grayscale, RGB  
✅ Призначення ICC профілів (embed без конвертації кольорів — числові значення пікселів не змінюються)  
✅ Геометрична деформація сторінок (4-точкове перспективне викривлення) для компенсації прогину корінця при брошурованому друці  
✅ Режим 1-сторонній друк — всі сторінки обробляються з налаштуваннями FRONT  
✅ Режим 2-сторонній друк — непарні сторінки як FRONT, парні як BACK  
✅ Обробка кількох файлів без перезапуску програми  
✅ Автоматичне додавання лічильника при збігу імен вихідних файлів  
✅ Вибір методу інтерполяції деформації (Lanczos, Cubic, Linear, Nearest)  
✅ Вибір стиснення проміжних TIFF файлів (LZW, Deflate, без стиснення)  
✅ Автовідкриття обробленого файлу після завершення  
✅ Адаптивний нативний інтерфейс (pywebview + HTML/CSS/JS)  
✅ Зберігання всіх налаштувань між сесіями

---

## Інструкція з використання

1. **Додавання файлів** — натисніть кнопку **⊕ Додати** і виберіть один або кілька PDF файлів. Усі файли залишаються у списку до закриття програми.

2. **Вибір режиму друку** — оберіть **1-ст друк** або **2-ст друк** у верхній панелі. У режимі 1-ст налаштування деформації BACK блокуються.

3. **Налаштування деформації** — введіть зміщення кутів у міліметрах окремо для **FRONT** (непарні) і **BACK** (парні сторінки). Позитивне значення — назовні, негативне — всередину. Превью оновлюється в реальному часі при кожному введенні.

4. **Вкладка "Растрування"** — оберіть DPI (або введіть вручну), метод інтерполяції деформації та формат стиснення проміжних TIFF файлів.

5. **Вкладка "Суфікси"** — задайте суфікси вихідних файлів для кожного колірного простору (`_CMYK`, `_GRAY`, `_RGB`). Вихідний файл зберігається поруч з оригіналом.

6. **Вкладка "ICC профілі"** — покладіть `.icc`/`.icm` файли у відповідні підпапки (`icc_profiles/cmyk/`, `/rgb/`, `/gray/`), після чого натисніть **⟳** для оновлення списку. Увімкніть або вимкніть призначення профілю галочкою.

7. **Вибір режиму обробки** — оберіть режим зі спадного меню у панелі запуску: `cmyk`, `grayscale`, `rgb` або відповідний з деформацією (`_warp`).

8. **Запуск** — натисніть **▶ Запустити**. Прогрес відображається у рядку стану. Для зупинки натисніть **⏹ Зупинити**.

9. **Після завершення** — програма автоматично відкриє оброблений файл (якщо увімкнено опцію). Шлях до файлу відображається у рядку стану внизу.

---

## Технології та залежності

### Python залежності

| Назва | Версія | Призначення |
|---|---|---|
| pywebview | 4.x | GUI на основі WebView2 — HTML/CSS/JS у нативному вікні Windows |
| PyMuPDF (fitz) | 1.x | Запасна растеризація PDF сторінок (коли GS недоступний) |
| opencv-python | 4.x | Перспективна деформація (`warpPerspective`) |
| Pillow | 10.x | Обробка зображень, збереження TIFF, конвертація форматів |
| img2pdf | 0.x | Збірка PDF з TIFF без перекомпресії |
| pikepdf | 8.x | Призначення ICC профілів у PDF (OutputIntents) |

### Зовнішні інструменти

| Назва | Версія | Призначення |
|---|---|---|
| Ghostscript | 10.x | Растеризація PDF зі збереженням CMYK значень; основний растеризатор |
| Inno Setup | 6.x | Створення Windows інсталятора (тільки для збірки) |
| PyInstaller | 6.x | Пакування у `.exe` (тільки для збірки) |

### Frontend

| Назва | Версія | Призначення |
|---|---|---|
| HTML5 / CSS3 / Vanilla JS | — | Інтерфейс програми |
| Montserrat | — | Шрифт інтерфейсу (локальний, `ui/fonts/`) |

---

## Структура проекту

```
pdf_prepress/
├── main.py              — точка входу, запуск HTTP сервера і pywebview
├── app.py               — API міст між Python і JS (pywebview js_api)
├── processor.py         — логіка обробки PDF (растеризація, warp, ICC)
├── settings.py          — збереження/завантаження налаштувань (settings.json)
├── theme.py             — Python-копія дизайн-токенів
├── requirements.txt     — pip залежності
├── icc_profiles/
│   ├── cmyk/            — CMYK профілі (.icc, .icm)
│   ├── rgb/             — RGB профілі
│   ├── gray/            — Grayscale профілі
│   └── README.txt       — інструкція по профілях
└── ui/
    ├── index.html       — головна сторінка інтерфейсу
    ├── assets/          — іконки програми
    ├── fonts/           — локальний шрифт Montserrat
    └── css/
    │   ├── theme.css        — CSS змінні (дизайн-токени)
    │   ├── base.css         — reset, типографіка
    │   ├── layout.css       — сітка, колонки
    │   ├── components.css   — картки, кнопки, інпути, вкладки
    │   └── warp-preview.css — стилі превью деформації
    └── js/
        ├── api.js       — виклики Python API через pywebview
        ├── ui.js        — DOM взаємодія, превью деформації (SVG)
        └── main.js      — ініціалізація, обробники подій

build/
├── build.spec           — конфігурація PyInstaller (onedir, windowed)
├── installer.iss        — скрипт Inno Setup
├── build_all.bat        — майстер-скрипт збірки
├── check_tools.bat      — перевірка залежностей збірки
└── ghostscript/         — папка для файлів Ghostscript (заповнити перед збіркою)
    └── README.txt
```

---

## Встановлення з GitHub

### Необхідне програмне забезпечення

- [ ] **Python 3.11+** (64-bit) — [python.org/downloads](https://www.python.org/downloads/)
- [ ] **Ghostscript 10.x** (64-bit) — [ghostscript.com/releases](https://ghostscript.com/releases/)
- [ ] **Git** — [git-scm.com](https://git-scm.com/)

### Клонування та запуск (режим розробки)

```bash
git clone https://github.com/YOUR_USERNAME/pdf_prepress.git
cd pdf_prepress
pip install -r pdf_prepress/requirements.txt
python pdf_prepress/main.py
```

Для запуску з конкретним файлом:

```bash
python pdf_prepress/main.py "C:\path\to\file.pdf"
```

### ICC профілі (необов'язково)

Покладіть `.icc`/`.icm` файли у відповідні підпапки:

```
pdf_prepress/icc_profiles/cmyk/   ← CMYK профілі
pdf_prepress/icc_profiles/rgb/    ← RGB профілі
pdf_prepress/icc_profiles/gray/   ← Grayscale профілі
```

Безкоштовні профілі:

| Профіль | Джерело | Призначення |
|---|---|---|
| `ISOcoated_v2_eci.icc` | [eci.org](http://www.eci.org/en/downloads) | CMYK офсетний друк |
| `sRGB Color Space Profile.icm` | `C:\Windows\System32\spool\drivers\color\` | RGB (вбудований у Windows) |

### Збірка Windows інсталятора

1. Встановіть **Inno Setup 6** — [jrsoftware.org/isdl.php](https://jrsoftware.org/isdl.php)

2. Скопіюйте вміст папки Ghostscript у `build/ghostscript/`:

   ```
   C:\Program Files\gs\gs10.x.x\  →  build/ghostscript/
   ```

   Детальна інструкція: `build/ghostscript/README.txt`

3. Переконайтеся, що `icon.ico` знаходиться у корені проекту

4. Виконайте збірку:

   ```bat
   cd build
   check_tools.bat
   build_all.bat
   ```

5. Готовий інсталятор буде збережено у:

   ```
   dist_installer\setup_pdf_prepress.exe
   ```

### Інтеграція з контекстним меню Windows

Під час встановлення увімкніть опцію **"Додати 'PDF Pre-Press' у контекстне меню PDF файлів"**. Після цього будь-який `.pdf` файл можна відкрити у програмі через правий клік миші → **PDF Pre-Press**.

---

## Ліцензія

Код програми розповсюджується під ліцензією **MIT**.

> **Важливо:** Ghostscript розповсюджується під ліцензією **GNU AGPL v3**.
> Якщо ви поширюєте цей продукт з бандлом Ghostscript — переконайтеся, що умови AGPL дотримані,
> або придбайте комерційну ліцензію Ghostscript у [Artifex Software](https://www.ghostscript.com/licensing/).

---
---

## 🇬🇧 English

### Contents
- [Description](#description)
- [How to use](#how-to-use)
- [Technologies & dependencies](#technologies--dependencies)
- [Project structure](#project-structure)
- [Installation from GitHub](#installation-from-github)
- [License](#license)

---

## Description

**PDF Pre-Press** is a Windows desktop application for preparing PDF files for professional printing.

✅ PDF rasterization with configurable DPI (72–1200)  
✅ Color space conversion: CMYK, Grayscale, RGB  
✅ ICC profile embedding (assign without color conversion — pixel values are preserved unchanged)  
✅ Geometric page warping (4-point perspective transformation) to compensate for spine curvature in booklet printing  
✅ Single-sided mode — all pages processed with FRONT settings  
✅ Double-sided mode — odd pages as FRONT, even pages as BACK  
✅ Process multiple files without restarting the application  
✅ Automatic filename counter when output file already exists  
✅ Configurable warp interpolation method (Lanczos, Cubic, Linear, Nearest)  
✅ Configurable intermediate TIFF compression (LZW, Deflate, none)  
✅ Auto-open processed file on completion  
✅ Responsive native UI (pywebview + HTML/CSS/JS)  
✅ All settings persisted between sessions

---

## How to use

1. **Add files** — click **⊕ Add** and select one or more PDF files. All files remain in the list until the application is closed.

2. **Select print mode** — choose **Single-sided** or **Double-sided** in the top bar. In single-sided mode the BACK warp controls are disabled.

3. **Configure warp** — enter corner offsets in millimetres separately for **FRONT** (odd pages) and **BACK** (even pages). Positive values move corners outward, negative inward. The preview updates in real time with every keystroke.

4. **Rasterization tab** — set DPI (or type a custom value), warp interpolation method, and intermediate TIFF compression format.

5. **Suffixes tab** — set output filename suffixes for each color space (`_CMYK`, `_GRAY`, `_RGB`). Output files are saved alongside the original.

6. **ICC profiles tab** — place `.icc`/`.icm` files in the appropriate subfolders (`icc_profiles/cmyk/`, `/rgb/`, `/gray/`), then click **⟳** to refresh the list. Enable or disable profile assignment with the checkbox.

7. **Select processing mode** — choose a mode from the dropdown in the launch panel: `cmyk`, `grayscale`, `rgb`, or the corresponding warp variant (`_warp`).

8. **Run** — click **▶ Start**. Progress is shown in the status bar. Click **⏹ Stop** to cancel.

9. **After completion** — the application will automatically open the processed file (if the option is enabled). The output path is shown in the bottom status bar.

---

## Technologies & dependencies

### Python dependencies

| Name | Version | Purpose |
|---|---|---|
| pywebview | 4.x | GUI using WebView2 — HTML/CSS/JS in a native Windows window |
| PyMuPDF (fitz) | 1.x | Fallback PDF rasterizer (when Ghostscript is unavailable) |
| opencv-python | 4.x | Perspective warp transformation (`warpPerspective`) |
| Pillow | 10.x | Image processing, TIFF saving, format conversion |
| img2pdf | 0.x | Assembles PDF from TIFF files without recompression |
| pikepdf | 8.x | Embeds ICC profiles into PDF (OutputIntents) |

### External tools

| Name | Version | Purpose |
|---|---|---|
| Ghostscript | 10.x | PDF rasterization preserving CMYK values; primary rasterizer |
| Inno Setup | 6.x | Creates the Windows installer (build only) |
| PyInstaller | 6.x | Packages the app into a `.exe` (build only) |

### Frontend

| Name | Version | Purpose |
|---|---|---|
| HTML5 / CSS3 / Vanilla JS | — | Application UI |
| Montserrat | — | UI font (local, `ui/fonts/`) |

---

## Project structure

```
pdf_prepress/
├── main.py              — entry point: starts the HTTP server and pywebview window
├── app.py               — API bridge between Python and JS (pywebview js_api)
├── processor.py         — PDF processing logic (rasterization, warp, ICC)
├── settings.py          — load/save settings (settings.json)
├── theme.py             — Python copy of design tokens
├── requirements.txt     — pip dependencies
├── icc_profiles/
│   ├── cmyk/            — CMYK profiles (.icc, .icm)
│   ├── rgb/             — RGB profiles
│   ├── gray/            — Grayscale profiles
│   └── README.txt       — profile placement instructions
└── ui/
    ├── index.html       — main UI page
    ├── assets/          — application icons
    ├── fonts/           — local Montserrat font
    └── css/
    │   ├── theme.css        — CSS variables (design tokens)
    │   ├── base.css         — reset, typography
    │   ├── layout.css       — grid, columns
    │   ├── components.css   — cards, buttons, inputs, tabs
    │   └── warp-preview.css — warp preview styles
    └── js/
        ├── api.js       — Python API calls via pywebview
        ├── ui.js        — DOM interactions, SVG warp preview
        └── main.js      — app init, event handlers

build/
├── build.spec           — PyInstaller configuration (onedir, windowed)
├── installer.iss        — Inno Setup script
├── build_all.bat        — master build script
├── check_tools.bat      — build prerequisite checker
└── ghostscript/         — place Ghostscript files here before building
    └── README.txt
```

---

## Installation from GitHub

### Prerequisites

- [ ] **Python 3.11+** (64-bit) — [python.org/downloads](https://www.python.org/downloads/)
- [ ] **Ghostscript 10.x** (64-bit) — [ghostscript.com/releases](https://ghostscript.com/releases/)
- [ ] **Git** — [git-scm.com](https://git-scm.com/)

### Clone and run (development mode)

```bash
git clone https://github.com/YOUR_USERNAME/pdf_prepress.git
cd pdf_prepress
pip install -r pdf_prepress/requirements.txt
python pdf_prepress/main.py
```

To open a specific file directly:

```bash
python pdf_prepress/main.py "C:\path\to\file.pdf"
```

### ICC profiles (optional)

Place `.icc`/`.icm` files in the appropriate subfolders:

```
pdf_prepress/icc_profiles/cmyk/   ← CMYK profiles
pdf_prepress/icc_profiles/rgb/    ← RGB profiles
pdf_prepress/icc_profiles/gray/   ← Grayscale profiles
```

Free profiles:

| Profile | Source | Purpose |
|---|---|---|
| `ISOcoated_v2_eci.icc` | [eci.org](http://www.eci.org/en/downloads) | CMYK offset printing |
| `sRGB Color Space Profile.icm` | `C:\Windows\System32\spool\drivers\color\` | RGB (built into Windows) |

### Build Windows installer

1. Install **Inno Setup 6** — [jrsoftware.org/isdl.php](https://jrsoftware.org/isdl.php)

2. Copy the Ghostscript installation folder contents into `build/ghostscript/`:

   ```
   C:\Program Files\gs\gs10.x.x\  →  build/ghostscript/
   ```

   Full instructions: `build/ghostscript/README.txt`

3. Ensure `icon.ico` is present in the project root

4. Run the build:

   ```bat
   cd build
   check_tools.bat
   build_all.bat
   ```

5. The ready installer will be saved to:

   ```
   dist_installer\setup_pdf_prepress.exe
   ```

### Windows right-click context menu

During installation, check the option **"Add 'PDF Pre-Press' to the context menu for PDF files"**. After that, any `.pdf` file can be opened in the application via right-click → **PDF Pre-Press**.

---

## License

The application source code is released under the **MIT License**.

> **Note:** Ghostscript is distributed under the **GNU AGPL v3** license.
> If you distribute this product bundled with Ghostscript, ensure compliance with the AGPL terms,
> or obtain a commercial Ghostscript license from [Artifex Software](https://www.ghostscript.com/licensing/).
