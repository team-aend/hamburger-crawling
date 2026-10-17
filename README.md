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
    │   └── burger.py         # Pydantic 데이터 모델 & SQLAlchemy ORM 모델
    ├── crawlers/
    │   ├── base.py           # 정적(requests+BS4) & 동적(Playwright) 공통 BaseCrawler
    │   └── sample_crawler.py # 브랜드별 크롤러 작성 템플릿 예시
    └── storage/
        ├── file_storage.py   # JSON / CSV 저장 모듈
        └── db_storage.py     # SQLAlchemy 기반 DB Upsert 및 조회 모듈
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
# 특정 포맷만 저장할 경우: python main.py crawl --export json
```

### 저장된 햄버거 정보 조회
```bash
# 전체 조회
python main.py query

# 브랜드 또는 메뉴명 키워드로 필터링 조회
python main.py query --brand 맥도날드
python main.py query --keyword 와퍼
```
