# 🍔 Hamburger Crawling (`hamburger-crawling`)

프랜차이즈 햄버거 메뉴 정보(가격, 영양성분, 알레르기·원산지 정보 등)를 크롤링하고 로컬 파일(JSON/CSV) 및 데이터베이스(SQLite / MySQL / PostgreSQL)에 저장·조회하는 Python 프로젝트입니다.

## 📁 프로젝트 구조

```text
hamburger-crawling/
├── .env.example              # 환경변수 예시 파일 (DB URL, 크롤러 옵션)
├── .gitignore
├── README.md
├── requirements.txt          # 패키지 의존성 목록
├── main.py                   # 크롤링 및 DB 조회 CLI 엔트리포인트
├── data/                     # 로컬 JSON, CSV, SQLite DB 저장 폴더
└── src/
    ├── config.py             # 환경변수 및 경로 설정
    ├── models/
    │   └── burger.py         # Pydantic 데이터 모델 & 버거픽 DB 상품 테이블 ORM 매핑
    ├── crawlers/
    │   ├── base.py           # 정적(requests+BS4) & 동적(Playwright) 공통 BaseCrawler
    │   ├── utils.py          # 숫자·이름 정규화, 소스 간 메뉴명 매칭
    │   ├── mcdonalds.py      # 맥도날드 (공식 JSON API)
    │   ├── burgerking.py     # 버거킹 (bizMOB 내부 API)
    │   ├── lotteria.py       # 롯데리아 (롯데잇츠 브랜드 페이지 + 영양성분표)
    │   ├── momstouch.py      # 맘스터치 (정적 HTML + 판독 영양성분 CSV)
    │   └── data/
    │       └── momstouch_nutrition.csv  # 맘스터치 영양성분표 이미지를 사람이 판독·검수한 값
    └── storage/
        ├── file_storage.py   # JSON / CSV 저장 모듈
        └── db_storage.py     # 상품·변형·가격 이력·영양성분 Upsert 및 조회
```

## 🚀 시작하기 (설치 및 환경 세팅)

### 1. 가상환경 생성 및 활성화
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. 패키지 및 Playwright 브라우저 설치
```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. 환경변수 파일 설정 (선택)
기본적으로 `data/hamburgers.db` (SQLite)를 사용하며, MySQL이나 PostgreSQL 연동을 원할 경우 `.env` 파일을 생성해 `DATABASE_URL`을 변경합니다.
```bash
cp .env.example .env
```

## 💻 실행 방법

### 크롤링 실행 및 전체 저장 (JSON + CSV + DB)
```bash
python main.py crawl
# 특정 포맷만 저장: python main.py crawl --export json
# 특정 브랜드만: python main.py crawl --brand burgerking lotteria
# DB 반영 없이 변경 예정 건수만 확인: python main.py crawl --export db --dry-run
```

## 🗄️ DB 저장 방식 (버거픽 DB)

운영 DB(Supabase PostgreSQL)의 상품 테이블에 저장합니다. 테이블은 이미 있다고 보고 생성하지 않으며, 로컬 SQLite일 때만 테이블을 만듭니다.

| 테이블 | 저장 내용 |
| --- | --- |
| `categories` | `BURGER_CATEGORY_SLUG`(기본 `burger`) 카테고리. 없으면 생성 |
| `brands` | `mcdonalds`, `burgerking`, `lotteria`, `momstouch`. 없으면 생성 |
| `products` | (브랜드, 메뉴명) → (브랜드, slug) 순으로 기존 상품을 찾아 갱신, 없으면 추가. 기존 `image_url`은 덮어쓰지 않음 |
| `product_variants` | `SINGLE`(단품, 기본 변형), 세트 가격이 있으면 `SET` |
| `product_prices` | `STORE` 채널. 가격이 바뀐 경우에만 기존 행의 `ended_at`을 채우고 새 행 추가 |
| `nutrition` | 단품 변형 기준 영양성분 |

## 🍔 브랜드별 수집 범위

| 브랜드 | 출처 | 단품가 | 세트가 | 영양성분 |
| --- | --- | --- | --- | --- |
| 맥도날드 | `mcdonalds.co.kr/api/v1` | ✗ (사이트 미제공) | ✗ | 중량·열량·단백질·당류·포화지방·나트륨 |
| 버거킹 | `burgerking.co.kr` 내부 API | ✓ (매장가) | ✓ | 중량·열량·단백질·당류·포화지방·나트륨 |
| 롯데리아 | `lotteeatz.com/brand/ria` + 영양성분표 | ✓ | ✗ (매장별 주문 페이지에만 있음) | 중량·열량·단백질·당류·포화지방·나트륨 |
| 맘스터치 | `momstouch.co.kr` + 판독 CSV | ✗ (사이트 미제공) | ✗ | 중량·열량·단백질·당류·포화지방·나트륨 (이미지 판독) |

탄수화물·지방은 네 브랜드 모두 공개하지 않아 비워 둡니다.

맘스터치는 영양성분을 전 메뉴 공통 이미지 한 장으로만 공개하므로, 이미지를 판독·검수한 `src/crawlers/data/momstouch_nutrition.csv`를 메뉴명으로 매칭합니다. 크롤링 때 사이트의 영양성분 이미지가 `momstouch.py`의 `NUTRITION_IMAGE_PATH`와 다르면 경고 로그가 남으니, 새 표를 판독해 CSV와 `NUTRITION_IMAGE_PATH`·`NUTRITION_ISSUED`를 갱신하세요.

### 저장된 햄버거 정보 조회
```bash
# 전체 조회
python main.py query

# 브랜드 또는 메뉴명 키워드로 필터링 조회
python main.py query --brand 맥도날드
python main.py query --keyword 와퍼
```

## 🧪 테스트

```bash
pip install -r requirements-dev.txt

pytest          # 오프라인 테스트 (사이트 접속 없음, 몇 초)
pytest --live   # 실제 브랜드 사이트까지 접속하는 스모크 테스트 포함
```

| 파일 | 내용 |
| --- | --- |
| `tests/test_crawlers.py` | `tests/fixtures/`에 저장한 실제 사이트 응답으로 브랜드별 파싱 결과 검증 (빅맥·와퍼·한우불고기버거·싸이버거 값 등) |
| `tests/test_utils.py` | 숫자 파싱(`1,098(55)`, `582Kcal`), 메뉴명 정규화·매칭 |
| `tests/test_db_storage.py` | 메모리 SQLite로 신규 저장, 재실행 시 가격 이력 미중복, 가격 변경 이력, `--dry-run` 롤백, 기존 상품 매칭 |
| `tests/test_live.py` | 브랜드별 10건 이상 수집, 영양성분·가격 수집률 80% 이상 (사이트 구조 변경 감지) |

사이트 구조가 바뀌어 `pytest --live`가 실패하면, 크롤러를 고친 뒤 새 응답을 `tests/fixtures/`에 다시 저장하고 기대값을 갱신합니다.
