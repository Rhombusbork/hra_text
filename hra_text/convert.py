"""hwp → hwpx 변환 (vendor/hwp2hwpx-cli.jar 호출).

원본 파일은 읽기만 하고, 변환 결과는 항상 별도 경로에 쓴다.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_JAR = ROOT / "vendor" / "hwp2hwpx-cli.jar"


class ConvertError(RuntimeError):
    pass


def find_jar() -> Path:
    jar = Path(os.environ.get("HRA_HWP2HWPX_JAR", DEFAULT_JAR))
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
    java = shutil.which("java")
    if java is None:
        raise ConvertError("java 가 설치되어 있지 않습니다.")
    dst.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [java, "-jar", str(find_jar()), str(src), str(dst)],
        capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0 or not dst.is_file():
        raise ConvertError(f"변환 실패: {src.name}\n{proc.stderr.strip()}")
    return dst
