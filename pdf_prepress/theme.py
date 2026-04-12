"""
theme.py — Єдине місце для всіх візуальних параметрів інтерфейсу.

Чистий файл з даними: без імпортів з інших файлів проєкту.
"""

# ──────────────────────────────────────────
# FONTS
# ──────────────────────────────────────────
FONT = "Segoe UI"   # головний шрифт (замінити на "Segoe UI" якщо не встановлений)

# ──────────────────────────────────────────
# THEME DICTIONARY
# ──────────────────────────────────────────
THEME = {

    # --- Шрифти ---
    "font_title":        (FONT, 24, "bold"),   # заголовки карток
    "font_normal":       (FONT, 14),           # основний текст, підписи полів
    "font_small":        (FONT, 12),           # дрібні підписи, примітки
    "font_button":       (FONT, 14, "bold"),   # текст кнопок

    # --- Кольори фону ---
    "color_window_bg":   "#F0F0F0",   # фон головного вікна
    "color_card_bg":     "#FFFFFF",   # фон картки
    "color_card_border": "#DCDCDC",   # обводка картки
    "color_tab_active":  "#FFFFFF",   # фон активної вкладки (збігається з карткою)
    "color_tab_inactive":"#EFEFEF",   # фон неактивної вкладки

    # --- Кольори тексту ---
    "color_text_primary":  "#1A1A1A", # основний текст
    "color_text_secondary":"#888888", # другорядний текст, підказки
    "color_text_tab_active":  "#1A1A1A",  # текст активної вкладки
    "color_text_tab_inactive":"#888888",  # текст неактивної вкладки

    # --- Акцентний колір (фокус, чекбокси, радіокнопки) ---
    "color_accent":        "#555555", # основний акцент
    "color_accent_hover":  "#444444", # акцент при наведенні
    "color_accent_light":  "#E8E8E8", # світлий акцент (hover на чекбоксі)

    # --- Кнопка Запустити ---
    "btn_launch_bg":       "#2E7D32", # фон кнопки запуску (зелений)
    "btn_launch_hover":    "#388E3C", # фон при наведенні
    "btn_launch_text":     "#FFFFFF", # колір тексту
    "btn_launch_height":   44,        # висота кнопки (px)
    "btn_launch_radius":   8,         # заокруглення кутів (px)
    "btn_launch_padx":     0,         # горизонтальний відступ всередині
    "btn_launch_pady":     0,         # вертикальний відступ всередині

    # --- Кнопка Зупинити ---
    "btn_stop_bg":         "#C62828", # фон кнопки зупинки (червоний)
    "btn_stop_hover":      "#D32F2F", # фон при наведенні
    "btn_stop_text":       "#FFFFFF", # колір тексту

    # --- Звичайні кнопки (⟳, ⊕, папка тощо) ---
    "btn_normal_bg":       "#FFFFFF", # фон
    "btn_normal_hover":    "#F0F0F0", # фон при наведенні
    "btn_normal_border":   "#CCCCCC", # обводка
    "btn_normal_text":     "#1A1A1A", # колір тексту
    "btn_normal_height":   32,        # висота (px)
    "btn_normal_radius":   6,         # заокруглення (px)
    "btn_normal_padx":     10,        # горизонтальний відступ
    "btn_normal_pady":     0,         # вертикальний відступ

    # --- Спадні меню (CTkComboBox / CTkOptionMenu) ---
    "dropdown_bg":         "#F5F5F5", # фон поля
    "dropdown_border":     "#CCCCCC", # колір обводки
    "dropdown_border_focus":"#555555",# колір обводки при фокусі/наведенні
    "dropdown_border_width": 1,       # товщина обводки (px)
    "dropdown_text":       "#1A1A1A", # колір тексту
    "dropdown_arrow":      "#555555", # колір стрілки вниз
    "dropdown_list_bg":    "#F5F5F5", # фон списку варіантів
    "dropdown_list_hover": "#E8E8E8", # фон рядка при наведенні
    "dropdown_list_text":  "#1A1A1A", # текст у списку
    "dropdown_height":     34,        # висота поля (px)
    "dropdown_radius":     6,         # заокруглення (px)

    # --- Поля вводу (CTkEntry) ---
    "entry_bg":            "#FFFFFF", # фон поля
    "entry_border":        "#CCCCCC", # колір обводки
    "entry_border_focus":  "#555555", # колір обводки при фокусі
    "entry_border_width":  1,         # товщина обводки (px)
    "entry_text":          "#1A1A1A", # колір тексту
    "entry_height":        34,        # висота поля (px)
    "entry_radius":        6,         # заокруглення (px)
    "entry_padx":          8,         # горизонтальний відступ тексту

    # --- Картки (CTkFrame) ---
    "card_radius":         10,        # заокруглення кутів картки
    "card_border_width":   1,         # товщина обводки картки
    "card_padding":        16,        # внутрішній відступ картки (px)

    # --- Вкладки (таби) ---
    "tab_bar_height":      38,        # висота рядка з ярликами вкладок (px)
    "tab_content_height":  220,       # фіксована висота зони контенту вкладки (px)
    "tab_radius":          0,         # заокруглення ярлика вкладки
    "tab_active_line":     2,         # товщина підкреслення активної вкладки (px)

    # --- Відступи сітки ---
    "grid_padx":           8,         # горизонтальний відступ між картками
    "grid_pady":           8,         # вертикальний відступ між картками

    # --- Адаптивний макет ---
    "layout_breakpoint":   900,       # ширина вікна (px), нижче якої — вузький макет
}
