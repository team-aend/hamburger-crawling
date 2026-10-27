import re
from html import unescape
from typing import Dict, Iterable, Optional, TypeVar

T = TypeVar("T")

_NUMBER_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def parse_number(value) -> Optional[float]:
    """'1,098(55)', '23(43%)', '582Kcal', '223g' 같은 문자열에서 첫 숫자를 추출 ('-', ''는 None)"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = _NUMBER_RE.search(str(value))
    return float(match.group().replace(",", "")) if match else None


def parse_price(value) -> Optional[int]:
    """'9,200원', '7400' → 정수 원. 0 이하는 None"""
    number = parse_number(value)
    return int(number) if number and number > 0 else None


def strip_html(value: Optional[str]) -> Optional[str]:
    """HTML 태그 제거 + 공백 정리 (<br>은 공백으로)"""
    if not value:
        return None
    text = re.sub(r"<br\s*/?>|</br>", " ", value, flags=re.I)
    text = unescape(re.sub(r"<[^>]+>", "", text))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def clean_name(value: str) -> str:
    """메뉴명 표기 정리 (태그·®·™ 제거, 공백 정리)"""
    text = strip_html(value) or ""
    text = re.sub(r"[®™]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def name_key(value: str) -> str:
    """소스 간 이름 매칭용 키 (공백·기호 제거)"""
    return re.sub(r"[\s®™()\[\]·.,]", "", clean_name(value)).lower()


def loose_name_key(value: str) -> str:
    """괄호 안 내용까지 제거한 느슨한 매칭 키 (예: '리아 불고기 더블 (빅불)' → '리아불고기더블')"""
    return name_key(re.sub(r"\([^)]*\)", "", clean_name(value)))


def match_by_name(name: str, table: Dict[str, T], loose_table: Dict[str, T]) -> Optional[T]:
    """name_key → loose_name_key 순서로 조회"""
    return table.get(name_key(name)) or loose_table.get(loose_name_key(name))


def build_name_tables(rows: Iterable[T], get_name) -> tuple:
    """match_by_name에서 쓸 (정확 키, 느슨한 키) 딕셔너리 생성. 먼저 나온 행이 우선."""
    exact: Dict[str, T] = {}
    loose: Dict[str, T] = {}
    for row in rows:
        name = get_name(row)
        exact.setdefault(name_key(name), row)
        loose.setdefault(loose_name_key(name), row)
    return exact, loose
