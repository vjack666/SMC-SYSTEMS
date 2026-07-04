"""SMC Trading System Desktop UI."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import MetaTrader5 as mt5
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from desktop import MainWindow


def main() -> None:
    if not mt5.initialize():
        print("ERROR: MetaTrader 5 not installed or not running.", file=sys.stderr)
        input("Press Enter to exit...")
        sys.exit(1)

    QApplication.setStyle("Fusion")

    app = QApplication(sys.argv)
    app.setApplicationName("SMC Trading System")
    app.setOrganizationName("SMC-Systems")

    from PySide6.QtGui import QPalette, QColor
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.WindowText, QColor(220, 220, 220))
    palette.setColor(QPalette.Base, QColor(42, 42, 42))
    palette.setColor(QPalette.AlternateBase, QColor(50, 50, 50))
    palette.setColor(QPalette.ToolTipBase, QColor(30, 30, 30))
    palette.setColor(QPalette.ToolTipText, QColor(220, 220, 220))
    palette.setColor(QPalette.Text, QColor(220, 220, 220))
    palette.setColor(QPalette.Button, QColor(42, 42, 42))
    palette.setColor(QPalette.ButtonText, QColor(220, 220, 220))
    palette.setColor(QPalette.BrightText, QColor(255, 82, 82))
    palette.setColor(QPalette.Link, QColor(100, 181, 246))
    palette.setColor(QPalette.Highlight, QColor(100, 181, 246))
    palette.setColor(QPalette.HighlightedText, QColor(30, 30, 30))
    app.setPalette(palette)

    window = MainWindow()
    window.show()
    exit_code = app.exec()
    mt5.shutdown()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
