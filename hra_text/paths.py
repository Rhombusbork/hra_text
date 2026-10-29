"""실행 위치에 따른 파일 경로 (개발 폴더 / 배포판 exe 둘 다).

배포판(PyInstaller) 구조:
  HRA_Tool/HRA_Tool.exe
  HRA_Tool/runtime/bin/java.exe      ← jlink 로 만든 작은 Java
  HRA_Tool/_internal/vendor/hwp2hwpx-cli.jar
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)
APP_NAME = "HRA보고서도구"


def resource_dir() -> Path:
    """프로그램과 함께 묶인 파일(jar, 사전)이 있는 곳."""
    if FROZEN:
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def app_dir() -> Path:
    """exe 가 있는 폴더 (배포판) 또는 저장소 폴더 (개발)."""
    return Path(sys.executable).parent if FROZEN else resource_dir()


def jar_path() -> Path:
    return Path(os.environ.get("HRA_HWP2HWPX_JAR", resource_dir() / "vendor" / "hwp2hwpx-cli.jar"))


def java_path() -> str | None:
    if os.environ.get("HRA_JAVA"):
        return os.environ["HRA_JAVA"]
    for name in ("java.exe", "java"):
        bundled = app_dir() / "runtime" / "bin" / name
        if bundled.is_file():
            return str(bundled)
    return shutil.which("java")


def config_dir() -> Path:
    """사용자 설정(메일 계정, 최근 경로)을 두는 곳 — 저장소·배포판 밖."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    d = base / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def documents_dir() -> Path:
    docs = Path.home() / "Documents"
    return docs if docs.is_dir() else Path.home()
