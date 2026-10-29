"""메일 자동 교정 (실제 네이버 대신 가짜 IMAP)."""

from email.message import EmailMessage

import pytest

from hra_text import mail


class FakeImap:
    def __init__(self, messages: dict[int, bytes], validity=b"7"):
        self.messages, self.validity, self.fetched = messages, validity, []

    def login(self, user, pw):
        assert (user, pw) == ("hra", "app-pw")

    def select(self, box, readonly=False):
        assert readonly, "메일을 읽음으로 바꾸지 않도록 읽기 전용으로 연다"
        return "OK", [b"%d" % len(self.messages)]

    def response(self, code):
        return code, [self.validity]

    def uid(self, cmd, *args):
        if cmd == "SEARCH":
            q = args[-1]
            low = int(q.split()[1].split(":")[0]) if q.startswith("UID") else 0
            return "OK", [b" ".join(b"%d" % u for u in self.messages if u >= low)]
        if cmd == "FETCH":
            assert "PEEK" in args[1]
            self.fetched.append(int(args[0]))
            return "OK", [(b"1 (BODY[] {n}", self.messages[int(args[0])]), b")"]
        raise AssertionError(cmd)

    def logout(self):
        pass


def _mail(sender, name, data, subject="보고서 제출"):
    m = EmailMessage()
    m["From"], m["Subject"] = sender, subject
    m.set_content("첨부합니다")
    m.add_attachment(data, maintype="application", subtype="octet-stream", filename=name)
    return m.as_bytes()


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setattr(mail, "config_dir", lambda: tmp_path / "cfg")
    (tmp_path / "cfg").mkdir()
    return mail.MailConfig(user="hra", password="app-pw", folder=tmp_path / "HRA메일")


def test_attachment_korean_filename():
    info, files = mail.attachments(_mail("홍길동 <hong@naver.com>", "HRA20_홍길동-에세이(책).hwpx", b"X"))
    assert info["from"] == "hong@naver.com"
    assert files == [("HRA20_홍길동-에세이(책).hwpx", b"X")]


def test_ignores_non_hwp_attachments():
    _, files = mail.attachments(_mail("a@naver.com", "사진.jpg", b"J"))
    assert files == []


def test_check_fixes_and_skips_already_done(cfg, sample_hwpx):
    data = sample_hwpx.read_bytes()
    imap = FakeImap({11: _mail("hong@naver.com", "제출.hwpx", data), 12: _mail("kim@naver.com", "사진.jpg", b"J")})
    assert mail.check_once(cfg, imap=imap, log=lambda *_: None) == 1
    results = list(cfg.result_dir.rglob("*_피드백.hwpx"))
    assert len(results) == 1 and results[0].name == "hong_제출_피드백.hwpx"
    assert list(cfg.inbox_dir.rglob("hong_제출.hwpx"))
    assert (cfg.folder / "처리기록.csv").read_text(encoding="utf-8-sig").count("\n") == 2
    # 다시 확인하면 이미 처리한 메일은 건너뛴다
    imap2 = FakeImap({11: _mail("hong@naver.com", "제출.hwpx", data), 12: b""})
    assert mail.check_once(cfg, imap=imap2, log=lambda *_: None) == 0
    assert imap2.fetched == []


def test_broken_file_is_logged_not_fatal(cfg):
    imap = FakeImap({1: _mail("a@naver.com", "깨짐.hwpx", b"not a zip")})
    assert mail.check_once(cfg, imap=imap, log=lambda *_: None) == 1
    log = (cfg.folder / "처리기록.csv").read_text(encoding="utf-8-sig")
    assert "깨짐" in log and log.strip().splitlines()[-1].split(",")[-1] != ""


def test_config_roundtrip(cfg, tmp_path):
    path = mail.save_config(cfg, tmp_path / "m.ini")
    assert mail.load_config(path).password == "app-pw"
