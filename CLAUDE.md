# HRA 보고서 자동 서식 교정 프로그램

HRA 20기 보고서(경영서·기업실무·고전) hwp/hwpx 파일을 양식에 맞게 자동 수정하고, 수정 내용을 정해진 문체의 **메모(코멘트)**로 남기는 프로그램.

## 문서-코드 동기화 규칙 (필수)

1. 서식 규칙의 기준은 **[docs/FORMAT_RULES.md](docs/FORMAT_RULES.md)** 하나뿐이다.
2. 규칙 추가·변경 순서: **FORMAT_RULES.md 수정 → 코드 수정 → 테스트 → 같은 커밋으로 묶기**.
3. 각 규칙 구현은 FORMAT_RULES의 규칙 ID(`R01`…)를 `RULE_ID`로 가진다. `tests/test_rules_sync.py`가 문서의 ID 목록과 코드에 등록된 규칙 ID가 1:1인지 검사한다 (불일치 시 테스트 실패).
4. 메모 문구는 FORMAT_RULES의 템플릿과 같아야 한다 (같은 테스트가 검사).
5. 구현 상태(`계획`/`구현`/`검증`)와 변경 이력 표를 코드 변경과 함께 갱신한다.
6. 사용자 답변으로 Q 항목이 해결되면 해당 규칙에 반영하고 Q에서 지운다.

## 브랜치

| 브랜치 | 내용 | 실행 환경 |
|---|---|---|
| `main` | 공통 문서(CLAUDE.md, FORMAT_RULES.md), 안정 버전 병합 | — |
| `hwpx-xml` | **1차 개발.** hwp→hwpx 변환 후 hwpx XML을 직접 수정 | WSL(Linux) + Python + Java |
| `hwp-com` | 2차 개발. 한글 프로그램 COM(pyhwpx)으로 hwp 직접 수정 | Windows + 한글 + Python |

- 두 브랜치는 같은 FORMAT_RULES.md를 따른다. 규칙 변경은 `main`에서 하고 각 브랜치로 병합한다.
- 원격: https://github.com/Rhombusbork/hra_text (**공개 저장소** — 아래 "개인정보" 참고)

## 개인정보

샘플 보고서에는 학생 이름·학과가 들어 있다. **실제 hwp/hwpx는 커밋하지 않는다** (`.gitignore`로 `*.hwp`, `*.hwpx` 제외). 테스트용 파일은 이름을 가명화한 합성 fixture로 만든다(`tests/fixtures/`, gitignore 예외로 명시 허용).

---

## 샘플 분석 요약 (사용자가 직접 한 수정)

### A. 기업실무: `…재제출 (1).hwp` → `…근로시간제 ).hwp`
| 항목 | 수정 전 | 수정 후 | 규칙 |
|---|---|---|---|
| 스타일 | 본문 / MS바탕글 / 제목 1 혼재 | 전부 바탕글 | R01 |
| ■ 기업실무 | 10pt 보통 | 12pt 진하게 | R03 |
| 왼쪽 여백 | 15pt (본문 스타일 문단 전체) | 0 | R05 |
| 1단위(Ⅰ.) 들여쓰기 | 10pt | 0 | R05 |
| 표지 영역 들여쓰기 | 10pt | 0 | R05 |
| 표 안 글자 | 8.5pt | 10pt | R03 |
| 표 안 문단 | 왼쪽 정렬, 위/아래 간격 1pt, 줄간격 110% | 양쪽, 0, 160% | R04 R06 |
| 표지 정보 표 | 오른쪽 정렬, MS바탕글 | 가운데, 바탕글 | R04 R14 |
| 띄어쓰기 | 직종별유연근무제제안, 경영학과4학년 | 직종별 유연근무제 제안, 경영학과 4학년 | R11 |
| 표지 빈 줄 배치 | — | 제목 위치 조정 | R14 |

### B. 경영서: `…가이드).hwpx` → `…가이드)_피드백.hwpx`
| 항목 | 수정 | 규칙 |
|---|---|---|
| 들여쓰기 5pt(`1000`) → 10pt(`2000`) | 자동 수정 대상 | R05 |
| 메모: 사진 글자처럼 취급 | 메모 | R07 |
| 메모: 너무 많이 띄어짐 → 한 줄만 | 메모 | R09 |
| 메모: 출처 8pt | 메모 | R08 |
| 메모: 문단 아래 간격 4pt 제거, 왼쪽/양쪽 정렬 혼재 → 양쪽 통일 | 메모 | R06 R04 |
| 메모: 2단위·3단위 타이틀 붙여쓰기, 바탕글 아님 (Alt T / Alt C 안내) | 메모 | R09 R01 |
| 메모: 10.5pt → 10pt | 메모 | R03 |

피드백본에도 아직 남은 위반(프로그램이 추가로 잡아야 할 것): `MS바탕글`·`제목 1/2` 스타일, 10.5pt 본문 일부, 제목 앞 Calibri 공백, 문단 앞 스페이스 들여쓰기, `treatAsChar="0"` 개체 3개(책 소개 표 2, 그림 1), 6~9장 들여쓰기 0.

### C. 양식 템플릿 (경영서/기업실무/고전)
템플릿 문단에 서식이 글자로 적혀 있음 → FORMAT_RULES R03~R08의 근거. 고전 양식은 "발표자용"과 "함께읽기용" 두 부분으로 되어 있음.

---

## 처리 방식 결정: "역할 분류 → 규칙별 패스"

검토한 방식:
1. **줄(문단) 단위**: 문단마다 모든 서식을 검사하고 수정. 직관적이지만 규칙이 한 함수에 엉켜서 문서와 1:1 대응이 어렵고, 같은 위반 메모를 묶기 어렵다.
2. **속성 단위 패스**: 바탕글 전체 검사 → 글꼴 전체 → 크기 전체 … 규칙과 1:1이라 관리가 쉽다. 하지만 "크기가 몇이어야 하는가"는 문단이 제목인지 본문인지에 따라 달라서, **각 패스가 역할 판별을 매번 따로** 하게 된다.
3. **채택: 1단계 역할 분류 + 2단계 규칙별 패스**
   - 1단계: 문서를 한 번 훑어 모든 문단에 역할(H1/H2/BODY/SOURCE…)을 붙인다. 이것이 핵심이고, `--dump`로 사람이 확인할 수 있게 한다.
   - 2단계: FORMAT_RULES의 규칙마다 패스 하나 (R15 안내문 삭제 → R01 스타일 → R02 글꼴 → …). 각 패스는 역할표를 보고 기대값과 다르면 **즉시 XML을 고치고** `Change(rule_id, key, old, new, 문단)` 기록을 남긴다 (앞 패스의 결과를 뒤 패스가 보도록).
   - 3단계: Change 기록을 문단별로 묶어 메모와 변경 내역 보고서를 만든다.
   - 장점: 규칙 ↔ 코드 ↔ 메모가 1:1, 규칙 하나만 켜고 끄며 테스트 가능, 순서 의존(안내문 삭제 후 빈 줄 정리 등)을 명시적으로 관리.
   - "넣어야 할 것"뿐 아니라 "**들어가면 안 되는 것**"도 같은 방식으로 처리한다: 각 패스는 역할별 기대값과 **다른 값은 무엇이든** 기대값으로 덮어쓴다(예: 아래 간격 4pt → 0, 본문 볼드 → 해제). 규칙에 없는 숨은 서식(기울임, 밑줄, 셀 음영 등)은 R13이 기본값으로 되돌린다.

두 방식을 따로 만들어 비교할 필요는 없다고 판단해 별도 브랜치는 만들지 않는다.

### 패스 순서 (의존성)
```
parse → classify(역할) → R15 안내문 삭제 → R16 쪽 번호 제거 → R10 앞공백 → R11 띄어쓰기(텍스트)
      → R01 스타일 → R02 글꼴 → R03 크기/볼드 → R13 기본값 복원 → R04 정렬 → R05 들여쓰기
      → R06 간격 → R07 개체 → R08 출처 → R09 빈 줄 → R14 표지/목차 → memo → save
```

---

## 아키텍처 (hwpx-xml 브랜치)

```
hra_text/
  cli.py              # hra-fix convert | dump | fix | compare
  convert.py          # hwp → hwpx (hwp2hwpx Java 라이브러리 호출)
  document.py         # Document: 패키지 + header + 문단 목록(+역할), touched(수정 문단), save
  engine.py           # run_rules: rules.base.ORDER 순서로 등록된 규칙 실행
  compare.py          # 우리 결과 vs 사람이 고친 수정본: 글자로 문단 짝짓기 → 서식 비교
  hwpx/
    package.py        # zip 열기/저장 (mimetype 무압축·첫 항목 유지, 나머지 그대로 보존)
    header.py         # charPr/paraPr/style/font 레지스트리: "이 속성 조합의 ID 찾기/없으면 생성"
    section.py        # 문단/런/표/그림 순회, 텍스트 범위 위치(path) 표현
    edit.py           # 글자/문단 모양 바꾸기(derive → IDRef 교체), 레이아웃 캐시 삭제
    memo.py           # (6단계) fieldBegin(MEMO)/fieldEnd 삽입, ID·번호 부여
  model.py            # Change (규칙이 남기는 변경 기록)
  classify.py         # 역할 분류 (FORMAT_RULES §1)
  rules/
    __init__.py       # REGISTRY, register (r??_*.py 자동 로드)
    base.py           # Rule(RULE_ID, NAME, apply(doc) -> list[Change]), ORDER(패스 순서)
    r01_style.py … r16_page_number.py   # R12는 보류(FORMAT_RULES §6)
    spacing_dict.tsv  # R11-b 교정 사전
    memo_templates.py # FORMAT_RULES §2 메모 문구 (동기화 테스트 대상)
  dump.py             # 문단별 역할·서식 표
  report.py           # 변경 내역 텍스트 보고서
tests/
  conftest.py         # 합성 hwpx fixture (개인정보 없음) 생성
  test_package.py     # 열고 저장만 해도 내용 동일
  test_header.py / test_classify.py / test_convert.py
  test_rules.py       # 규칙 동작 + 로컬 샘플 회귀(우리 결과 vs 사용자 수정본, 알려진 수정 누락 목록 외 차이 0)
  test_rules_sync.py  # FORMAT_RULES ↔ 코드 동기화 검사
```

### 핵심 구현 포인트
- **charPr/paraPr는 공유 객체**: 한 문단의 크기를 바꾸려고 charPr를 직접 고치면 같은 ID를 쓰는 다른 곳도 바뀐다. 항상 "원래 속성 + 변경"으로 새 조합을 만들고 → 같은 조합이 이미 있으면 재사용, 없으면 header에 추가 → 런의 IDRef만 교체.
- **linesegarray**: 레이아웃 캐시. 서식을 바꾸면 값이 맞지 않게 되므로 수정한 문단의 `hp:linesegarray`를 제거한다 (한글이 열 때 다시 계산). 열리는지 실제 한글로 검증 필요.
- **메모 범위**: 텍스트 범위에 메모를 달려면 런을 분할해 fieldBegin/fieldEnd 컨트롤을 끼워 넣는다. 샘플 구조: `hp:ctrl > hp:fieldBegin[type=MEMO] > hp:parameters + hp:subList > hp:p` … `hp:ctrl > hp:fieldEnd[beginIDRef]`.
- **문단 여백 단위**: `hh:paraPr`의 여백·줄간격은 `hp:switch` 안 `hp:case`(1pt=100)와 `hp:default`(1pt=200) 두 벌이 있다. 둘 다 같은 pt로 맞춰야 한다 (FORMAT_RULES §0 ※).
- **텍스트 추출**: `hp:t` 안의 `hp:tab`/`hp:lineBreak` 뒤 tail 텍스트까지 읽는다.
- **원본 보존**: 입력 파일은 절대 덮어쓰지 않는다. 출력은 `output/{원본명}_피드백.hwpx`.
- **메모 정책**: 고친 것마다 메모 (수정 문단 1개당 메모 1개, 여러 규칙은 한 메모에 묶음). 상세는 FORMAT_RULES §3.
- **양식 안내문**: 템플릿의 붉은 글씨(`#FF0000`)는 지워야 할 안내문(R15). 반대로 H1 칸의 흰 글씨·검은 배경, 표지 표 항목명의 회색 글씨는 템플릿 디자인이라 유지(R13 예외).

### R12 (쪽 나누기) — 보류
사용자 요청으로 보류(FORMAT_RULES §6). WSL에는 한글의 조판 엔진이 없어 쪽 채움 비율을 추정해야 하므로, 재개 시 hwp-com 브랜치에서 한글의 실제 조판 결과를 쓰는 방식부터 검토한다.

---

## 구현 계획 (hwpx-xml)

| 단계 | 작업 | 완료 기준 |
|---|---|---|
| 0 | 환경: venv, `requirements.txt`, hwp2hwpx 빌드(`scripts/build_hwp2hwpx.sh`, Maven 없이 javac) | ✅ 2026-10-29 |
| 1 | hwp→hwpx 변환 검증: 샘플 5종 변환, pyhwp로 읽은 원본과 문단 단위 비교(글자·스타일·크기·볼드·정렬·여백 모두 일치) → 한글에서 열림 확인(사용자) | 자동 비교 ✅ / 사용자 확인 대기 |
| 2 | hwpx 입출력: 열고 그대로 저장 → 한글에서 열림 | ✅ test_package (실제 샘플 포함) |
| 3 | header 레지스트리 + `hra-fix dump` (문단별 역할/스타일/크기/정렬 표) | ✅ |
| 4 | 역할 분류기 (FORMAT_RULES §1) | 자동 테스트 ✅ / 샘플 역할표 사용자 확인 대기 |
| 5 | R01~R08 서식 규칙 + `fix`/`compare` | ✅ 2026-10-29. 기업실무: 짝지은 512문단 중 차이는 전부 수정본 쪽 누락(표 안 왼쪽 정렬·MS바탕글·8.5pt, 출처 10pt 등). 재실행 시 변경 0건 |
| 6 | 메모 삽입 + 묶기 | 경영서 결과에 피드백본과 같은 문체 메모 |
| 7 | R15 안내문 삭제, R16 쪽 번호, R09 빈 줄, R10 공백, R13 기본값 복원, R14 표지/목차 | 템플릿을 넣으면 붉은 글씨가 모두 사라짐 |
| 8 | R11 띄어쓰기(규칙·사전) | 기업실무 띄어쓰기 수정 재현 |
| 9 | 일괄 처리, 보고서, README | 폴더 단위 실행 |

## 개발 명령
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./scripts/build_hwp2hwpx.sh            # vendor/hwp2hwpx-cli.jar 생성 (Java 필요)
.venv/bin/pytest
.venv/bin/hra-fix convert <hwp 파일|폴더> -o output   # hwp → hwpx (원본 유지)
.venv/bin/hra-fix dump <hwp/hwpx 파일|폴더> [-o output]  # 문단별 역할·서식 표
.venv/bin/hra-fix fix <hwp/hwpx 파일|폴더> [-o output] [--rules R01,R03]  # → <이름>_피드백.hwpx + <이름>_변경내역.txt
.venv/bin/hra-fix compare <우리 결과.hwpx> <사람 수정본>      # 서식 차이 요약
```
