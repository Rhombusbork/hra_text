"""배포판 창 화면 (HRA_Tool.exe).

  HRA_Tool.exe                 → 창 (서식 교정 / 합본 / 메일 자동 교정)
  HRA_Tool.exe 파일.hwp …      → exe 위에 파일을 끌어다 놓으면 바로 서식 교정
  HRA_Tool.exe --mail-check    → 창 없이 메일 한 번 확인 (윈도우 작업 스케줄러용)
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import traceback
from datetime import date
from pathlib import Path

from .paths import config_dir

SETTINGS = "settings.json"


def _settings() -> dict:
    try:
        return json.loads((config_dir() / SETTINGS).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def _save_settings(data: dict) -> None:
    (config_dir() / SETTINGS).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def open_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        os.startfile(path)  # noqa: S606 (윈도우 탐색기 열기)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def fix_files(files: list[Path], log) -> Path | None:
    """각 파일을 '원본 폴더/결과'에 고친다. 마지막 결과 폴더를 돌려준다."""
    from .mail import fix_file

    out = None
    for f in files:
        out = f.parent / "결과"
        try:
            res = fix_file(f, out, _settings().get("author", "neoju"))
            log(f"고침: {f.name} → 결과\\{Path(res['result']).name} (변경 {res['changes']}건, 메모 {res['memos']}개)")
        except Exception as e:
            log(f"실패: {f.name} — {e}")
    return out


def run_app() -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    settings = _settings()
    root = tk.Tk()
    root.title("HRA 보고서 도구")
    root.geometry("760x560")
    messages: queue.Queue[str] = queue.Queue()

    def log(msg: str) -> None:
        messages.put(msg)

    def pump() -> None:
        while not messages.empty():
            logbox.insert("end", messages.get() + "\n")
            logbox.see("end")
        root.after(200, pump)

    def in_background(job) -> None:
        def run():
            try:
                job()
            except Exception:
                log("오류:\n" + traceback.format_exc())
        threading.Thread(target=run, daemon=True).start()

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=8, pady=8)

    def file_list(parent, *, ordered: bool):
        frame = ttk.Frame(parent)
        lb = tk.Listbox(frame, selectmode="extended", height=10)
        lb.pack(side="left", fill="both", expand=True)
        bar = ttk.Frame(frame)
        bar.pack(side="left", fill="y", padx=4)
        paths: list[Path] = []

        def refresh():
            lb.delete(0, "end")
            for i, p in enumerate(paths, 1):
                lb.insert("end", f"{i}. {p.name}" if ordered else p.name)

        def add():
            for f in filedialog.askopenfilenames(filetypes=[("한글 문서", "*.hwp *.hwpx")]):
                if Path(f) not in paths:
                    paths.append(Path(f))
            refresh()

        def remove():
            for i in sorted(lb.curselection(), reverse=True):
                paths.pop(i)
            refresh()

        def move(step):
            sel = list(lb.curselection())
            if len(sel) != 1:
                return
            i, j = sel[0], sel[0] + step
            if 0 <= j < len(paths):
                paths[i], paths[j] = paths[j], paths[i]
                refresh()
                lb.selection_set(j)

        ttk.Button(bar, text="파일 추가", command=add).pack(fill="x")
        ttk.Button(bar, text="빼기", command=remove).pack(fill="x", pady=2)
        if ordered:
            ttk.Button(bar, text="▲ 위로", command=lambda: move(-1)).pack(fill="x", pady=(12, 2))
            ttk.Button(bar, text="▼ 아래로", command=lambda: move(1)).pack(fill="x")
        return frame, paths

    # ---- 서식 교정 ----
    t1 = ttk.Frame(nb, padding=8)
    nb.add(t1, text="서식 교정")
    ttk.Label(t1, text="고칠 hwp/hwpx 파일을 추가하고 [고치기]. 결과는 원본 옆 '결과' 폴더에 생깁니다. 원본은 바뀌지 않습니다.").pack(anchor="w")
    f1, fix_paths = file_list(t1, ordered=False)
    f1.pack(fill="both", expand=True, pady=6)
    last_out: dict[str, Path] = {}

    def do_fix():
        files = list(fix_paths)
        if not files:
            messagebox.showinfo("HRA 보고서 도구", "파일을 먼저 추가하세요.")
            return
        def job():
            out = fix_files(files, log)
            if out:
                last_out["fix"] = out
                log("끝. [결과 폴더 열기]로 확인하세요.")
        in_background(job)

    row = ttk.Frame(t1)
    row.pack(anchor="w")
    ttk.Button(row, text="고치기", command=do_fix).pack(side="left")
    ttk.Button(row, text="결과 폴더 열기",
               command=lambda: last_out.get("fix") and open_folder(last_out["fix"])).pack(side="left", padx=6)

    # ---- 합본 ----
    t2 = ttk.Frame(nb, padding=8)
    nb.add(t2, text="합본")
    ttk.Label(t2, text="확인을 마친 파일을 추가하고 ▲▼로 순서를 맞춘 뒤 [합본 만들기]. 메모는 빠집니다.").pack(anchor="w")
    f2, merge_paths = file_list(t2, ordered=True)
    f2.pack(fill="both", expand=True, pady=6)
    form = ttk.Frame(t2)
    form.pack(fill="x")
    cover_var = tk.StringVar(value=settings.get("cover", ""))
    date_var = tk.StringVar()
    ttk.Label(form, text="참고 합본(표지·일정표)").grid(row=0, column=0, sticky="w")
    ttk.Entry(form, textvariable=cover_var, width=60).grid(row=0, column=1, sticky="we")
    ttk.Button(form, text="찾기", command=lambda: cover_var.set(
        filedialog.askopenfilename(filetypes=[("hwpx", "*.hwpx")]) or cover_var.get())).grid(row=0, column=2)
    ttk.Label(form, text="날짜 (예: 2026.11.07.(토))").grid(row=1, column=0, sticky="w")
    ttk.Entry(form, textvariable=date_var, width=24).grid(row=1, column=1, sticky="w")
    form.columnconfigure(1, weight=1)

    def do_merge():
        from .merge.cli import main as merge_main

        files, cover = list(merge_paths), Path(cover_var.get())
        if not files or not cover.is_file():
            messagebox.showinfo("HRA 보고서 도구", "합칠 파일과 참고 합본(hwpx)을 정하세요.")
            return
        settings["cover"] = str(cover)
        _save_settings(settings)
        stamp = date_var.get().strip() or date.today().isoformat()
        out = files[0].parent / "결과" / f"합본_{''.join(c for c in stamp if c.isalnum() or c in '.-')}.hwpx"
        args = [str(f) for f in files] + ["--cover", str(cover), "-o", str(out)]
        if date_var.get().strip():
            args += ["--date", date_var.get().strip()]

        def job():
            merge_main(args)
            last_out["merge"] = out.parent
            log(f"합본 완료: {out}")
        in_background(job)

    row2 = ttk.Frame(t2)
    row2.pack(anchor="w", pady=6)
    ttk.Button(row2, text="합본 만들기", command=do_merge).pack(side="left")
    ttk.Button(row2, text="결과 폴더 열기",
               command=lambda: last_out.get("merge") and open_folder(last_out["merge"])).pack(side="left", padx=6)

    # ---- 메일 자동 교정 ----
    from . import mail

    t3 = ttk.Frame(nb, padding=8)
    nb.add(t3, text="메일 자동 교정")
    ttk.Label(t3, text="네이버 메일에 들어온 hwp/hwpx 첨부를 내려받아 고칩니다. 답장은 보내지 않습니다.").pack(anchor="w")
    try:
        cfg = mail.load_config()
    except (FileNotFoundError, KeyError):
        cfg = mail.MailConfig(user="", password="", folder=mail.documents_dir() / "HRA메일")
    user_var, pw_var, folder_var = tk.StringVar(value=cfg.user), tk.StringVar(value=cfg.password), \
        tk.StringVar(value=str(cfg.folder))
    minutes_var, auto_var = tk.IntVar(value=5), tk.BooleanVar(value=False)
    g = ttk.Frame(t3)
    g.pack(fill="x", pady=6)
    for r, (label, var, show) in enumerate((("네이버 아이디", user_var, ""), ("애플리케이션 비밀번호", pw_var, "*"),
                                            ("저장 폴더", folder_var, ""))):
        ttk.Label(g, text=label).grid(row=r, column=0, sticky="w")
        ttk.Entry(g, textvariable=var, show=show, width=50).grid(row=r, column=1, sticky="we")
    g.columnconfigure(1, weight=1)

    def current_cfg():
        return mail.MailConfig(user=user_var.get().strip(), password=pw_var.get().strip(),
                               folder=Path(folder_var.get().strip()))

    def save_mail():
        mail.save_config(current_cfg())
        log(f"메일 설정 저장: {mail.config_path()}")

    def check_now():
        c = current_cfg()
        in_background(lambda: log(f"메일 확인 — 새 파일 {mail.check_once(c, log=log)}개. 결과: {c.result_dir}"))

    def auto_tick():
        if auto_var.get():
            check_now()
            root.after(max(1, minutes_var.get()) * 60_000, auto_tick)

    b = ttk.Frame(t3)
    b.pack(anchor="w")
    ttk.Button(b, text="설정 저장", command=save_mail).pack(side="left")
    ttk.Button(b, text="지금 확인", command=check_now).pack(side="left", padx=6)
    ttk.Button(b, text="결과 폴더 열기", command=lambda: open_folder(current_cfg().result_dir)).pack(side="left")
    a = ttk.Frame(t3)
    a.pack(anchor="w", pady=6)
    ttk.Checkbutton(a, text="이 창이 켜져 있는 동안 자동 확인, 간격(분):", variable=auto_var,
                    command=auto_tick).pack(side="left")
    ttk.Spinbox(a, from_=1, to=120, textvariable=minutes_var, width=5).pack(side="left")

    # ---- 기록 ----
    logbox = tk.Text(root, height=9)
    logbox.pack(fill="both", padx=8, pady=(0, 8))
    pump()
    root.mainloop()


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--mail-check"]:
        from . import mail

        cfg = mail.load_config()
        lines = []
        mail.check_once(cfg, log=lines.append)
        with open(cfg.folder / "자동확인기록.txt", "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + ("\n" if lines else ""))
        return 0
    files = [Path(a) for a in argv if Path(a).suffix.lower() in (".hwp", ".hwpx")]
    if files:  # exe 위에 끌어다 놓기
        lines: list[str] = []
        fix_files(files, lines.append)
        if os.environ.get("HRA_NO_DIALOG"):  # 자동 점검(빌드)용: 알림 창 없이
            print("\n".join(lines))
            return 0
        try:
            import tkinter as tk
            from tkinter import messagebox

            tk.Tk().withdraw()
            messagebox.showinfo("HRA 보고서 도구", "\n".join(lines) or "고칠 파일이 없습니다.")
        except Exception:
            print("\n".join(lines))
        return 0
    run_app()
    return 0


if __name__ == "__main__":
    sys.exit(main())
