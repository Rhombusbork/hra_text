import zipfile
from pathlib import Path

import pytest

from hra_text.convert import ConvertError, DEFAULT_JAR, hwp_to_hwpx

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = sorted(ROOT.glob("*.hwp"))  # 로컬 샘플(커밋 안 됨)

needs_jar = pytest.mark.skipif(not DEFAULT_JAR.is_file(), reason="scripts/build_hwp2hwpx.sh 필요")


def test_refuses_overwrite(tmp_path):
    src = tmp_path / "a.hwp"
    src.write_bytes(b"")
    with pytest.raises(ConvertError):
        hwp_to_hwpx(src, src)


def test_rejects_non_hwp(tmp_path):
    with pytest.raises(ConvertError):
        hwp_to_hwpx(tmp_path / "a.hwpx", tmp_path / "b.hwpx")


@needs_jar
@pytest.mark.skipif(not SAMPLES, reason="로컬 샘플 hwp 없음")
@pytest.mark.parametrize("src", SAMPLES, ids=lambda p: p.stem[:20])
def test_convert_samples(src, tmp_path):
    before = src.read_bytes()
    dst = hwp_to_hwpx(src, tmp_path / (src.stem + ".hwpx"))
    assert src.read_bytes() == before, "원본이 바뀌었습니다"
    with zipfile.ZipFile(dst) as z:
        names = z.namelist()
        assert names[0] == "mimetype"
        assert z.read("mimetype") == b"application/hwp+zip"
        assert "Contents/section0.xml" in names
        assert "Contents/header.xml" in names
