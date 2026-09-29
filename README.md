# gh-song.github.io

Personal site of **Gookho Song (송국호)**, Ph.D. candidate, Bio and Brain Engineering, KAIST.
**https://gh-song.github.io** · 한국어 **https://gh-song.github.io/ko/**

페이지 구성: 홈(영문·국문) · 연구 소개(`/research/`, `/ko/research/`) · 인쇄용 CV(`/cv/`).
모두 `content/`의 JSON에서 만들어진다. 빌드는 Python 표준 라이브러리만 쓰고, `main`에 push하면 GitHub Actions가 배포한다.

## 빠른 사용법

```bash
python3 build.py --serve      # 빌드 후 http://localhost:8000 미리보기
python3 build.py --pdf        # CV 페이지를 static/files/Gookho_Song_CV.pdf 로 인쇄 (Chrome 필요)
git add -A && git commit -m "update" && git push   # 1–2분 뒤 사이트 반영
```

`_site/`는 빌드 결과물이라 커밋하지 않는다. 문구는 **`content/*.json`만** 고친다.

## 무엇을 어디서 고치나

| 하고 싶은 일 | 파일 | 비고 |
|---|---|---|
| 논문 추가 | `content/publications.json` | `key`는 고유하게. 공동 제1저자면 `"tags": ["first", …]`, 이름 뒤 `†`, 교신 `*`. 프리프린트는 `"type": "preprint"` |
| 논문 썸네일 | `static/img/pub/<key>.webp` | 파일이 있으면 자동 표시, 없으면 저널명 자리표시 |
| 기사 추가 | `content/press.json` → `articles` | `story`는 `stories`의 키. 헤드라인은 원문 그대로 |
| 기사 묶음(성과) 추가 | `content/press.json` → `stories` | `label`(막대그래프 이름), `paper`(논문 key)를 적으면 논문 목록의 "Press (n)"이 자동 연결 |
| 수상 · 특허 | `content/honors.json` | 특허는 `filings`에 국가별 등록/출원을 따로 |
| 학회 발표 | `content/talks.json` | `scope`: international / domestic |
| 소식 | `content/news.json` | 최신 6개만 홈에 표시 |
| 피인용 수 | `content/site.json` → `scholar` | `as_of`, `per_year`도 함께 (그래프에 사용) |
| 학력 · 과제 · 연구비 · 기술 | `content/cv.json` | 타임라인 그래프는 연도에서 자동 |
| 연구 소개 페이지 | `content/research.json` | 공동 제1저자 논문 요약·주요 결과·그림 |
| 마지막 수정일 | `content/site.json` → `updated` | |

모든 문구는 `"문자열"` 또는 `{"en": "...", "ko": "..."}`. `**굵게**`, `*기울임*`, `[링크](https://…)`를 쓸 수 있다.
요약 숫자(논문 수, 제1저자 수, 특허, 발표, 보도 수 등)와 그래프는 JSON에서 **자동 계산**된다.

JSON 정렬이 흐트러지면 `python3 tools/fmt_json.py`. 빌드할 때 없는 논문 키·스토리 키·중복 URL을 검사해 알려준다.

## 이미지

| 파일 | 만드는 법 |
|---|---|
| `static/img/portrait.*`, `pub/*.webp`, 연구 그림 | `python3 tools/prep_images.py` — 원본(논문 PDF, 연구실 홈페이지 썸네일, 사진) 경로는 스크립트 상단에서 지정. 원본은 저장소에 넣지 않는다 |
| `static/img/og.jpg` (링크 미리보기 카드) | `python3 tools/make_og.py` — 숫자가 바뀌면 다시 실행 |
| `static/files/Gookho_Song_CV.pdf` | `python3 build.py --pdf` (전화번호는 넣지 않았다) |

논문 썸네일 8개는 연구실 홈페이지(mooolab.kaist.ac.kr/Publication.html)의 그림을 줄여 쓴 것이다.
연구 소개 페이지의 그림 출처·라이선스는 각 캡션에 있다 (Sci. Adv. CC BY-NC 4.0, Optica OAPA, IEEE TPAMI © IEEE).

## 구조

```
build.py              정적 사이트 생성기 (의존성 없음)
content/              모든 문구와 데이터 (en/ko)
static/css/site.css   화면 스타일
static/css/cv.css     인쇄용 CV (A4)
static/js/site.js     논문 필터 · BibTeX 복사 · 섹션 표시
tools/                이미지 · 미리보기 카드 · JSON 정리 스크립트
.github/workflows/    push → 빌드 → GitHub Pages 배포
```

## 검색 노출 (한 번만)

- **Google Search Console** → URL 접두어 속성 `https://gh-song.github.io/` → `sitemap.xml` 제출
- **네이버 서치어드바이저** → 사이트 등록 → HTML 태그 값을 `content/site.json`의 `verification.naver`에 넣고 push → 소유 확인 → 사이트맵 제출 (구글은 `verification.google`)
- Google Scholar · ORCID · GitHub 프로필의 홈페이지 칸에 이 주소를 넣으면 이름 검색 결과가 서로 연결된다
