# hra_text

HRA 보고서(hwp/hwpx)를 양식에 맞게 자동 교정하고 피드백 메모를 다는 프로그램(`hra-fix`)과,
확인된 보고서들을 합본으로 묶는 프로그램(`hra-merge`).

- 서식 규칙: [docs/FORMAT_RULES.md](docs/FORMAT_RULES.md)
- 개발 계획/구조: [CLAUDE.md](CLAUDE.md)
- 브랜치: `hwpx-xml`(WSL에서 hwpx XML 수정), `hwp-com`(Windows 한글 COM 자동화)

## 쓰는 법 (WSL)
```bash
.venv/bin/hra-fix fix "제출본.hwp" -o output          # → output/제출본_피드백.hwpx (+ 변경내역.txt)
.venv/bin/hra-merge 고친파일1.hwpx 고친파일2.hwpx --cover 참고합본.hwpx -o output/합본.hwpx --date "2026.11.07.(토)"
```
