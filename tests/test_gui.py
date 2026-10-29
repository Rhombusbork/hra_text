"""배포판 진입점 중 창 없이 도는 부분 (exe 에 파일 끌어다 놓기)."""

from hra_text import gui


def test_drop_files_on_exe_fixes_into_result_folder(sample_hwpx, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(gui, "config_dir", lambda: tmp_path)
    monkeypatch.setenv("HRA_NO_DIALOG", "1")  # 윈도우에서 알림 창이 떠 테스트가 멈추지 않게
    assert gui.main([str(sample_hwpx)]) == 0
    assert (sample_hwpx.parent / "결과" / "sample_피드백.hwpx").is_file()
    assert (sample_hwpx.parent / "결과" / "sample_변경내역.txt").is_file()
