from hra_text.hwpx.header import Header, set_line_spacing_percent, set_margin_pt
from hra_text.hwpx.ns import NS
from hra_text.hwpx.package import HwpxPackage


def _header(path):
    return Header(HwpxPackage.open(path).header)


def test_char_shape(sample_hwpx):
    h = _header(sample_hwpx)
    c = h.char("1")
    assert (c.size_pt, c.bold, c.fonts["HANGUL"]) == (12.0, True, "맑은 고딕")
    assert h.char("6").fonts["LATIN"] == "Calibri"
    assert h.char("4").text_color == "#FF0000"


def test_para_shape_reads_pt_from_default_form(sample_hwpx):
    ps = _header(sample_hwpx).para("3")
    assert ps.align == "LEFT"
    assert ps.margins_pt == {"intent": 5.0, "left": 15.0, "right": 0.0, "prev": 0.0, "next": 4.0}
    assert ps.line_spacing == ("PERCENT", 110)


def test_set_margin_writes_both_forms(sample_hwpx):
    h = _header(sample_hwpx)

    def mutate(el):
        set_margin_pt(el, "intent", 10)
        set_line_spacing_percent(el, 160)

    new_id = h.derive_para("3", mutate)
    el = h.para_element(new_id)
    case = el.find("hp:switch/hp:case/hh:margin/hc:intent", NS).get("value")
    default = el.find("hp:switch/hp:default/hh:margin/hc:intent", NS).get("value")
    assert (case, default) == ("1000", "2000")
    assert h.para(new_id).margins_pt["intent"] == 10.0
    assert h.para("3").margins_pt["intent"] == 5.0, "원래 paraPr 는 그대로여야 한다"


def test_derive_reuses_identical_combination(sample_hwpx):
    h = _header(sample_hwpx)
    a = h.derive_para("3", lambda el: set_margin_pt(el, "intent", 10))
    b = h.derive_para("3", lambda el: set_margin_pt(el, "intent", 10))
    assert a == b
    noop = h.derive_para("1", lambda el: None)
    assert noop == "1"


def test_fill_color(sample_hwpx):
    h = _header(sample_hwpx)
    assert h.fill_color("1") is None
    assert h.fill_color("2") == "GRAD:#000000,#FFFFFF"
    assert h.fill_color("3") == "#DCDCDC"


def test_font_id_create(sample_hwpx):
    h = _header(sample_hwpx)
    assert h.font_id("HANGUL", "맑은 고딕") == "0"
    assert h.font_id("HANGUL", "바탕") is None
    new = h.font_id("HANGUL", "바탕", create=True)
    assert h.font_face("HANGUL", new) == "바탕"
