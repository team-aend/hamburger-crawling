import pytest

from src.crawlers.utils import (
    build_name_tables,
    clean_name,
    loose_name_key,
    match_by_name,
    name_key,
    parse_number,
    parse_price,
    strip_html,
)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("1098(55)", 1098.0),
        ("23(43%)", 23.0),
        ("582Kcal", 582.0),
        ("1,009", 1009.0),
        ("2.4(16)", 2.4),
        ("223g", 223.0),
        (706, 706.0),
        ("-", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_number(value, expected):
    assert parse_number(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [("9,200원", 9200), ("7400", 7400), ("0원", None), (None, None)],
)
def test_parse_price(value, expected):
    assert parse_price(value) == expected


def test_strip_html_removes_tags_and_breaks():
    assert strip_html("100% 순 쇠고기<br>\r\n빅맥<sub class=reg>®</sub>만의  소스") == "100% 순 쇠고기 빅맥®만의 소스"
    assert strip_html("") is None


def test_clean_name_removes_trademarks():
    assert clean_name("빅맥<sub class=reg>®</sub> 세트") == "빅맥 세트"
    assert clean_name("맥크리스피™  치킨 클래식 ") == "맥크리스피 치킨 클래식"


def test_name_key_ignores_spacing_and_symbols():
    assert name_key("더블 한우불고기버거") == name_key("더블한우불고기버거")
    assert name_key("쿼터파운더® 치즈") == name_key("쿼터파운더®치즈")


def test_loose_name_key_drops_parentheses():
    assert loose_name_key("리아 불고기 더블 (빅불)") == loose_name_key("리아 불고기 더블")
    assert loose_name_key("치킨버거(N)") == loose_name_key("치킨버거")


def test_match_by_name_prefers_exact_then_loose():
    rows = [{"name": "치킨버거(N)", "v": 1}, {"name": "리아 불고기", "v": 2}]
    tables = build_name_tables(rows, lambda r: r["name"])
    assert match_by_name("리아불고기", *tables)["v"] == 2
    assert match_by_name("치킨버거", *tables)["v"] == 1
    assert match_by_name("없는버거", *tables) is None
