"""Shared dark theme for the observador (cognitive hierarchy + consistency).

Design goals (cognitive-doc-design applied to UI):
  - Lead with the answer (plan strip / semáforo)
  - Progressive disclosure (tabs for detail)
  - Recognition over recall (big numbers, color codes)
  - One visual language across widgets
"""
from __future__ import annotations

# Palette
BG = "#0f1115"
BG_PANEL = "#15171c"
BG_RAISED = "#1a1d24"
BORDER = "#2a2e38"
TEXT = "#e6e6e6"
TEXT_DIM = "#9aa0a6"
TEXT_MUTED = "#6b7280"
ACCENT = "#7fb3ff"
GREEN = "#1f9d55"
GREEN_SOFT = "#1e4d2b"
YELLOW = "#c9a227"
RED = "#c0392b"
RED_SOFT = "#5a2a2a"


def app_stylesheet() -> str:
    return f"""
    QMainWindow, QWidget {{
        background-color: {BG};
        color: {TEXT};
        font-family: "Segoe UI", "Segoe UI Variable", sans-serif;
        font-size: 13px;
    }}
    QTabWidget::pane {{
        border: 1px solid {BORDER};
        border-radius: 6px;
        top: -1px;
        background: {BG_PANEL};
    }}
    QTabBar::tab {{
        background: {BG_RAISED};
        color: {TEXT_DIM};
        padding: 8px 16px;
        margin-right: 2px;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        border: 1px solid {BORDER};
        border-bottom: none;
    }}
    QTabBar::tab:selected {{
        background: {BG_PANEL};
        color: {TEXT};
        font-weight: 600;
        border-bottom: 2px solid {ACCENT};
    }}
    QTabBar::tab:hover {{
        color: {TEXT};
        background: #22262f;
    }}
    QPushButton {{
        background-color: {BG_RAISED};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 7px 14px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: #252a34;
        border-color: #3d4450;
    }}
    QPushButton:pressed {{
        background-color: #12151a;
    }}
    QPushButton:disabled {{
        color: {TEXT_MUTED};
        background-color: #1a1a1a;
        border-color: #2a2a2a;
    }}
    QGroupBox {{
        border: 1px solid {BORDER};
        border-radius: 8px;
        margin-top: 12px;
        padding-top: 10px;
        background: {BG_PANEL};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 6px;
    }}
    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QTextBrowser, QPlainTextEdit {{
        background-color: {BG_PANEL};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 6px;
        selection-background-color: #2a4a6a;
    }}
    QLabel {{
        color: {TEXT};
    }}
    QToolTip {{
        background-color: {BG_RAISED};
        color: {TEXT};
        border: 1px solid {BORDER};
        padding: 4px 8px;
    }}
    """


def btn_primary() -> str:
    return (
        f"QPushButton {{ background-color: {GREEN_SOFT}; color: #e8ffe8; "
        f"font-weight: bold; border: 1px solid {GREEN}; border-radius: 6px; "
        f"padding: 8px 14px; }}"
        f"QPushButton:hover {{ background-color: #2a6b3c; }}"
        f"QPushButton:disabled {{ background-color: #333; color: #888; border-color: #444; }}"
    )


def btn_danger() -> str:
    return (
        f"QPushButton {{ background-color: {RED_SOFT}; color: #fff; "
        f"font-weight: bold; border: 1px solid {RED}; border-radius: 6px; "
        f"padding: 7px 12px; }}"
        f"QPushButton:hover {{ background-color: #7a3535; }}"
    )


def btn_ghost() -> str:
    return (
        f"QPushButton {{ background-color: transparent; color: {TEXT_DIM}; "
        f"border: 1px solid {BORDER}; border-radius: 6px; padding: 7px 12px; }}"
        f"QPushButton:hover {{ color: {TEXT}; background: {BG_RAISED}; }}"
    )
