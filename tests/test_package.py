import zipfile

import pytest
from lxml import etree

from hra_text.hwpx.package import HwpxError, HwpxPackage

from conftest import local_samples

SAMPLES = local_samples("*.hwpx") + local_samples("output/*.hwpx")


def _entries(path):
    with zipfile.ZipFile(path) as z:
        return [(i.filename, i.compress_type, z.read(i.filename)) for i in z.infolist()]


def test_untouched_roundtrip_is_byte_identical(sample_hwpx, tmp_path):
    out = HwpxPackage.open(sample_hwpx).save(tmp_path / "out.hwpx")
    assert _entries(out) == _entries(sample_hwpx)


def test_parsed_roundtrip_keeps_content(sample_hwpx, tmp_path):
    pkg = HwpxPackage.open(sample_hwpx)
    pkg.header, pkg.sections()  # 파싱만 하고 저장
    out = pkg.save(tmp_path / "out.hwpx")
    before, after = dict((n, d) for n, _, d in _entries(sample_hwpx)), dict((n, d) for n, _, d in _entries(out))
    assert before.keys() == after.keys()
    for name in before:
        if name.endswith(".xml"):
            c14n = lambda b: etree.tostring(etree.fromstring(b), method="c14n")  # noqa: E731
            assert c14n(before[name]) == c14n(after[name]), name
            assert after[name].startswith(b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>')


def test_mimetype_first_and_stored(sample_hwpx, tmp_path):
    out = HwpxPackage.open(sample_hwpx).save(tmp_path / "out.hwpx")
    first = _entries(out)[0]
    assert first[0] == "mimetype" and first[1] == zipfile.ZIP_STORED


def test_refuses_overwrite(sample_hwpx):
    with pytest.raises(HwpxError):
        HwpxPackage.open(sample_hwpx).save(sample_hwpx)


@pytest.mark.skipif(not SAMPLES, reason="로컬 샘플 없음")
@pytest.mark.parametrize("src", SAMPLES, ids=lambda p: p.stem[:20])
def test_real_sample_roundtrip(src, tmp_path):
    pkg = HwpxPackage.open(src)
    pkg.header, pkg.sections()
    out = pkg.save(tmp_path / "out.hwpx")
    for (n1, _, d1), (n2, _, d2) in zip(_entries(src), _entries(out)):
        assert n1 == n2
        if n1.endswith(".xml"):
            assert etree.tostring(etree.fromstring(d1), method="c14n") == etree.tostring(
                etree.fromstring(d2), method="c14n"), n1
        else:
            assert d1 == d2, n1
