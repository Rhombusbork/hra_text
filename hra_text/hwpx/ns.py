"""HWPX(OWPML) XML 네임스페이스."""

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HH = "http://www.hancom.co.kr/hwpml/2011/head"
HC = "http://www.hancom.co.kr/hwpml/2011/core"
HS = "http://www.hancom.co.kr/hwpml/2011/section"
HWPUNITCHAR = "http://www.hancom.co.kr/hwpml/2016/HwpUnitChar"

NS = {"hp": HP, "hh": HH, "hc": HC, "hs": HS}


def hp(tag: str) -> str:
    return f"{{{HP}}}{tag}"


def hh(tag: str) -> str:
    return f"{{{HH}}}{tag}"


def hc(tag: str) -> str:
    return f"{{{HC}}}{tag}"
