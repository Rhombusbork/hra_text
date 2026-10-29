"""hwpx(zip) 패키지 열기/저장.

- 손대지 않은 항목은 원래 바이트 그대로 다시 쓴다.
- header.xml, section*.xml 은 처음 접근할 때 파싱하고, 파싱한 항목만 다시 직렬화한다.
- mimetype 은 첫 항목·무압축으로 유지한다 (OCF 규칙).
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from lxml import etree

XML_DECL = b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
_SECTION_RE = re.compile(r"^Contents/section(\d+)\.xml$")


class HwpxError(RuntimeError):
    pass


class HwpxPackage:
    def __init__(self, path: Path):
        self.path = Path(path).resolve()
        self._infos: list[zipfile.ZipInfo] = []
        self._raw: dict[str, bytes] = {}
        self._trees: dict[str, etree._Element] = {}
        with zipfile.ZipFile(self.path) as z:
            for info in z.infolist():
                self._infos.append(info)
                self._raw[info.filename] = z.read(info.filename)
        if self._raw.get("mimetype", b"").strip() != b"application/hwp+zip":
            raise HwpxError(f"hwpx 파일이 아닙니다: {self.path.name}")

    @classmethod
    def open(cls, path: Path | str) -> "HwpxPackage":
        return cls(Path(path))

    # ---- 항목 접근 -------------------------------------------------
    def names(self) -> list[str]:
        return [i.filename for i in self._infos]

    def xml(self, name: str) -> etree._Element:
        """XML 항목의 루트 요소 (수정 가능, 저장 시 반영)."""
        if name not in self._trees:
            if name not in self._raw:
                raise HwpxError(f"항목 없음: {name}")
            parser = etree.XMLParser(remove_blank_text=False, huge_tree=True)
            self._trees[name] = etree.fromstring(self._raw[name], parser)
        return self._trees[name]

    @property
    def header(self) -> etree._Element:
        return self.xml("Contents/header.xml")

    def section_names(self) -> list[str]:
        found = [(int(m.group(1)), n) for n in self.names() if (m := _SECTION_RE.match(n))]
        return [n for _, n in sorted(found)]

    def sections(self) -> list[etree._Element]:
        return [self.xml(n) for n in self.section_names()]

    def raw(self, name: str) -> bytes:
        """항목의 원래 바이트 (그림 등)."""
        return self._raw[name]

    def info(self, name: str) -> zipfile.ZipInfo:
        return next(i for i in self._infos if i.filename == name)

    def add(self, name: str, data: bytes, *, compress_type: int = zipfile.ZIP_DEFLATED) -> None:
        """새 항목 추가 (같은 이름이 있으면 덮어씀)."""
        if name in self._raw:
            self.remove(name)
        info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
        info.compress_type = compress_type
        self._infos.append(info)
        self._raw[name] = data

    def remove(self, name: str) -> None:
        self._infos = [i for i in self._infos if i.filename != name]
        self._raw.pop(name, None)
        self._trees.pop(name, None)

    # ---- 저장 ------------------------------------------------------
    def serialize(self, name: str) -> bytes:
        if name in self._trees:
            body = etree.tostring(self._trees[name], encoding="UTF-8", xml_declaration=False)
            return self._declaration(name) + body
        return self._raw[name]

    def _declaration(self, name: str) -> bytes:
        """원본의 XML 선언을 그대로 유지한다."""
        raw = self._raw[name]
        if raw.startswith(b"<?xml"):
            return raw[: raw.index(b"?>") + 2]
        return XML_DECL

    def save(self, dst: Path | str) -> Path:
        dst = Path(dst).resolve()
        if dst == self.path:
            raise HwpxError("원본을 덮어쓸 수 없습니다. 다른 경로로 저장하세요.")
        dst.parent.mkdir(parents=True, exist_ok=True)
        infos = sorted(self._infos, key=lambda i: i.filename != "mimetype")  # mimetype 맨 앞
        with zipfile.ZipFile(dst, "w") as z:
            for info in infos:
                out = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                out.external_attr = info.external_attr
                out.compress_type = (
                    zipfile.ZIP_STORED if info.filename == "mimetype" else info.compress_type
                )
                z.writestr(out, self.serialize(info.filename))
        return dst
