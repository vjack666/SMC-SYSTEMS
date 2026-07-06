"""Poll ML pipeline status and run post-completion verification + notify."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUS_PATH = ROOT / "results" / "ml_pipeline_status.json"
COMPLETE_MARKER = "ML_PIPELINE_COMPLETE"
POLL_SECONDS = 15


def main() -> int:
    print(f"Watching {STATUS_PATH} for completion...", flush=True)
    while True:
        if STATUS_PATH.exists():
            data = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
            phase = data.get("phase", "")
            message = data.get("message", "")
            print(f"[watch] {phase}: {message}", flush=True)
            if phase == "complete" or COMPLETE_MARKER in message:
                print(COMPLETE_MARKER, flush=True)
                subprocess.run(
                    [sys.executable, str(ROOT / "scripts" / "ml_notify_complete.py")],
                    check=False,
                )
                return 0
            if phase == "failed":
                print(f"ML pipeline failed: {message}", flush=True)
                return 1
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())