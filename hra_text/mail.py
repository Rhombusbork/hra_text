"""네이버 메일(IMAP)로 들어온 hwp/hwpx 첨부를 내려받아 자동으로 서식 교정.

- 답장은 보내지 않는다 (사람이 확인한 뒤 보낸다).
- 메일을 '읽음'으로 바꾸지 않는다 (BODY.PEEK). 이미 처리한 메일은 상태 파일(UID)로 건너뛴다.
- 처음 실행하면 오늘 들어온 메일부터 처리한다 (예전 메일 전체를 처리하지 않도록).

폴더 (기본: 문서\\HRA메일):
  받은파일\\2026-10-29\\보낸사람_파일이름.hwp   ← 내려받은 원본
  결과\\2026-10-29\\파일이름_피드백.hwpx + _변경내역.txt
  처리기록.csv
"""

from __future__ import annotations

import configparser
import csv
import email
import imaplib
import json
import re
import tempfile
import time
from dataclasses import dataclass
from datetime import date, datetime
from email.policy import default as default_policy
from email.utils import parseaddr
from pathlib import Path

from .paths import config_dir, documents_dir

NAVER_IMAP = ("imap.naver.com", 993)
SUFFIXES = (".hwp", ".hwpx")


@dataclass
class MailConfig:
    user: str
    password: str
    folder: Path
    host: str = NAVER_IMAP[0]
    port: int = NAVER_IMAP[1]
    mailbox: str = "INBOX"
    author: str = "neoju"

    @property
    def inbox_dir(self) -> Path:
        return self.folder / "받은파일"

    @property
    def result_dir(self) -> Path:
        return self.folder / "결과"


def config_path() -> Path:
    return config_dir() / "mail.ini"


def state_path() -> Path:
    return config_dir() / "mail_state.json"


def load_config(path: Path | None = None) -> MailConfig:
    path = path or config_path()
    if not path.is_file():
        raise FileNotFoundError(f"메일 설정이 없습니다: {path}  (hra-mail setup 으로 만드세요)")
    cp = configparser.ConfigParser()
    cp.read(path, encoding="utf-8")
    s = cp["mail"]
    return MailConfig(user=s["아이디"], password=s["앱비밀번호"],
                      folder=Path(s.get("저장폴더", str(documents_dir() / "HRA메일"))),
                      author=s.get("메모작성자", "neoju"))


def save_config(cfg: MailConfig, path: Path | None = None) -> Path:
    path = path or config_path()
    cp = configparser.ConfigParser()
    cp["mail"] = {"아이디": cfg.user, "앱비밀번호": cfg.password, "저장폴더": str(cfg.folder),
                  "메모작성자": cfg.author}
    with open(path, "w", encoding="utf-8") as f:
        cp.write(f)
    return path


# ---------------------------------------------------------------- 상태 (처리한 메일)
def _load_state() -> dict:
    try:
        return json.loads(state_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def _save_state(state: dict) -> None:
    state_path().write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- 메일 → 첨부
def _safe(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", name).strip()
    return name or "첨부"


def attachments(raw: bytes) -> tuple[dict, list[tuple[str, bytes]]]:
    """(메일 정보, [(파일 이름, 내용), ...]) — hwp/hwpx 첨부만."""
    msg = email.message_from_bytes(raw, policy=default_policy)
    info = {"from": parseaddr(str(msg.get("From", "")))[1] or str(msg.get("From", "")),
            "subject": str(msg.get("Subject", "")), "date": str(msg.get("Date", ""))}
    files = []
    for part in msg.walk():
        name = part.get_filename()
        if name and Path(name).suffix.lower() in SUFFIXES:
            files.append((name, part.get_payload(decode=True) or b""))
    return info, files


def _unique(path: Path) -> Path:
    if not path.exists():
        return path
    for i in range(2, 1000):
        cand = path.with_name(f"{path.stem}({i}){path.suffix}")
        if not cand.exists():
            return cand
    raise FileExistsError(path)


# ---------------------------------------------------------------- 처리
def fix_file(src: Path, out_dir: Path, author: str) -> dict:
    """한 파일 서식 교정 (hra-fix fix 와 같은 처리)."""
    from .document import Document
    from .engine import run_rules
    from .memo import add_memos
    from .report import render

    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hra_mail_") as work:
        doc = Document.open(src, work_dir=Path(work))
        changes = run_rules(doc)
        memos = add_memos(doc, changes, author=author)
        dst = doc.save(_unique(out_dir / f"{src.stem}_피드백.hwpx"))
        (out_dir / f"{src.stem}_변경내역.txt").write_text(render(changes, title=src.name, memos=memos) + "\n",
                                                        encoding="utf-8")
    return {"result": str(dst), "changes": len(changes), "memos": memos}


def _log(cfg: MailConfig, row: dict) -> None:
    log = cfg.folder / "처리기록.csv"
    new = not log.exists()
    with open(log, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["시각", "보낸사람", "제목", "파일", "결과", "변경", "메모", "오류"])
        if new:
            w.writeheader()
        w.writerow(row)


def check_once(cfg: MailConfig, *, imap=None, log=print) -> int:
    """새 메일을 확인해 첨부를 고친다. 처리한 파일 수를 돌려준다. imap 은 테스트용으로 바꿔 끼울 수 있다."""
    state = _load_state()
    key = f"{cfg.user}@{cfg.host}/{cfg.mailbox}"
    box = state.get(key, {})
    client = imap or imaplib.IMAP4_SSL(cfg.host, cfg.port)
    processed = 0
    try:
        client.login(cfg.user, cfg.password)
        typ, data = client.select(cfg.mailbox, readonly=True)
        if typ != "OK":
            raise RuntimeError(f"메일함을 열 수 없습니다: {cfg.mailbox}")
        validity = _uidvalidity(client)
        if box.get("uidvalidity") != validity:
            box = {"uidvalidity": validity, "last_uid": 0, "since": date.today().strftime("%d-%b-%Y")}
        if box["last_uid"]:
            typ, data = client.uid("SEARCH", None, f"UID {box['last_uid'] + 1}:*")
        else:
            typ, data = client.uid("SEARCH", None, f"SINCE {box['since']}")
        uids = [int(u) for u in (data[0] or b"").split() if int(u) > box["last_uid"]]
        for uid in sorted(uids):
            typ, msg_data = client.uid("FETCH", str(uid), "(BODY.PEEK[])")
            raw = next((part[1] for part in msg_data if isinstance(part, tuple)), b"")
            info, files = attachments(raw)
            day = datetime.now().strftime("%Y-%m-%d")
            for name, content in files:
                sender = _safe(info["from"].split("@")[0])
                saved = _unique(cfg.inbox_dir / day / f"{sender}_{_safe(name)}")
                saved.parent.mkdir(parents=True, exist_ok=True)
                saved.write_bytes(content)
                row = {"시각": datetime.now().isoformat(timespec="seconds"), "보낸사람": info["from"],
                       "제목": info["subject"], "파일": str(saved), "결과": "", "변경": "", "메모": "", "오류": ""}
                try:
                    res = fix_file(saved, cfg.result_dir / day, cfg.author)
                    row.update({"결과": res["result"], "변경": res["changes"], "메모": res["memos"]})
                    log(f"고침: {saved.name} → {Path(res['result']).name} (변경 {res['changes']}건, 메모 {res['memos']}개)")
                except Exception as e:  # 한 파일이 실패해도 나머지는 계속
                    row["오류"] = str(e)
                    log(f"실패: {saved.name} — {e}")
                _log(cfg, row)
                processed += 1
            box["last_uid"] = uid
            state[key] = box
            _save_state(state)
        state[key] = box
        _save_state(state)
    finally:
        try:
            client.logout()
        except Exception:
            pass
    return processed


def _uidvalidity(client) -> str:
    """메일함을 연 응답에 들어 있는 UIDVALIDITY (메일함이 새로 만들어지면 바뀜)."""
    typ, data = client.response("UIDVALIDITY")
    value = (data or [None])[0]
    return value.decode() if isinstance(value, bytes) else str(value or "0")


def watch(cfg: MailConfig, minutes: float, *, log=print) -> None:
    log(f"{minutes:g}분마다 새 메일을 확인합니다. 멈추려면 창을 닫거나 Ctrl+C.")
    while True:
        try:
            n = check_once(cfg, log=log)
            log(f"[{datetime.now():%H:%M}] 확인 완료 — 새 파일 {n}개")
        except Exception as e:
            log(f"[{datetime.now():%H:%M}] 확인 실패: {e}")
        time.sleep(minutes * 60)


# ---------------------------------------------------------------- 명령행: hra-mail
def main(argv: list[str] | None = None) -> int:
    import argparse
    import getpass

    ap = argparse.ArgumentParser(prog="hra-mail", description="네이버 메일 첨부 hwp/hwpx 자동 서식 교정 (답장 안 함)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup", help="네이버 아이디·앱 비밀번호·저장 폴더 설정")
    sub.add_parser("check", help="지금 한 번 확인")
    w = sub.add_parser("watch", help="몇 분마다 계속 확인")
    w.add_argument("--minutes", type=float, default=5)
    args = ap.parse_args(argv)

    if args.cmd == "setup":
        user = input("네이버 아이디 (@naver.com 앞부분): ").strip()
        pw = getpass.getpass("애플리케이션 비밀번호 (입력해도 화면에 안 보임): ").strip()
        folder = input(f"저장 폴더 [기본 {documents_dir() / 'HRA메일'}]: ").strip() or str(documents_dir() / "HRA메일")
        path = save_config(MailConfig(user=user, password=pw, folder=Path(folder)))
        print(f"저장했습니다: {path}")
        return 0
    cfg = load_config()
    if args.cmd == "check":
        print(f"새 파일 {check_once(cfg)}개 처리. 결과: {cfg.result_dir}")
        return 0
    watch(cfg, args.minutes)
    return 0
