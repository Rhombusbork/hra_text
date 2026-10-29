"""hwp → hwpx 변환 (vendor/hwp2hwpx-cli.jar 호출).

원본 파일은 읽기만 하고, 변환 결과는 항상 별도 경로에 쓴다.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .paths import java_path, jar_path

DEFAULT_JAR = jar_path()


class ConvertError(RuntimeError):
    pass


def find_jar() -> Path:
    jar = jar_path()
    if not jar.is_file():
        raise ConvertError(f"{jar} 가 없습니다. scripts/build_hwp2hwpx.sh 를 먼저 실행하세요.")
    return jar


def hwp_to_hwpx(src: Path, dst: Path, *, timeout: int = 120) -> Path:
    """src(.hwp)를 dst(.hwpx)로 변환한다. src와 dst가 같으면 거부한다."""
    src, dst = Path(src).resolve(), Path(dst).resolve()
    if src.suffix.lower() != ".hwp":
        raise ConvertError(f"hwp 파일이 아닙니다: {src.name}")
    if src == dst:
        raise ConvertError("원본을 덮어쓸 수 없습니다.")
    java = java_path()
    if java is None:
        raise ConvertError("java 가 설치되어 있지 않습니다.")
    dst.parent.mkdir(parents=True, exist_ok=True)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0  # 배포판에서 검은 창이 뜨지 않게
    proc = subprocess.run(
        [java, "-jar", str(find_jar()), str(src), str(dst)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
        creationflags=flags,
    )
    if proc.returncode != 0 or not dst.is_file():
        raise ConvertError(f"변환 실패: {src.name}\n{proc.stderr.strip()}")
    return dst
