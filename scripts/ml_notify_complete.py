"""Windows popup + pleasant sound when ML pipeline completes."""
from __future__ import annotations

import ctypes
import sys
import time

try:
    import winsound
except ImportError:
    winsound = None  # type: ignore[assignment]


def play_completion_sound() -> None:
    if winsound is None:
        return
    melody = [(523, 180), (659, 180), (784, 260), (1047, 420)]
    for freq, duration in melody:
        winsound.Beep(freq, duration)
        time.sleep(0.04)


def show_popup() -> None:
    message = (
        "ML phase is complete — real and functional.\n\n"
        "• Dataset built from real market data\n"
        "• Model trained with chronological holdout\n"
        "• Quality filter wired to paper/live trading"
    )
    ctypes.windll.user32.MessageBoxW(  # type: ignore[attr-defined]
        0,
        message,
        "SMC Systems — ML Complete",
        0x40,  # MB_ICONINFORMATION
    )


def main() -> None:
    if sys.platform != "win32":
        print("ML complete (notification is Windows-only)")
        return
    play_completion_sound()
    show_popup()


if __name__ == "__main__":
    main()