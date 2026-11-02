"""PyInstaller 진입점: HRA_Tool.exe

창 프로그램(--windowed)이라 처리 안 된 오류가 나면 PyInstaller 가 오류 창을 띄우고 멈춘다.
그래서 모든 오류를 잡아 기록 파일에 남기고, 사람이 쓸 때만 알림 창을 띄운다.
"""

import os
import sys
import traceback
from pathlib import Path


def _error_log() -> Path:
    if os.environ.get("HRA_ERROR_LOG"):
        return Path(os.environ["HRA_ERROR_LOG"])
    base = Path(os.environ.get("APPDATA", Path.home())) / "HRA보고서도구"
    base.mkdir(parents=True, exist_ok=True)
    return base / "error.log"


def run() -> int:
    try:
        from hra_text.gui import main

        return main() or 0
    except SystemExit as e:
        return int(e.code or 0)
    except BaseException:
        text = traceback.format_exc()
        log = _error_log()
        log.write_text(text, encoding="utf-8")
        if not os.environ.get("HRA_NO_DIALOG"):
            try:
                import tkinter as tk
                from tkinter import messagebox

                tk.Tk().withdraw()
                messagebox.showerror("HRA 보고서 도구 오류", f"오류가 났습니다. 기록: {log}\n\n{text[-1500:]}")
            except Exception:
                pass
        return 1


if __name__ == "__main__":
    sys.exit(run())
