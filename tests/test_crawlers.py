"""저장해 둔 실제 사이트 응답(tests/fixtures)으로 브랜드별 파싱 결과를 검증 (네트워크 접속 없음)"""

import pytest

from src.crawlers import (
    BurgerKingCrawler,
    CryCheeseBurgerCrawler,
    FiveGuysCrawler,
    FrankBurgerCrawler,
    KFCCrawler,
    LotteriaCrawler,
    McDonaldsCrawler,
    MomsTouchCrawler,
    NoBrandBurgerCrawler,
    ShakeShackCrawler,
)
from src.crawlers.fiveguys import burger_recipe
from src.crawlers.momstouch import NUTRITION_CSV as MOMSTOUCH_NUTRITION_CSV
from src.crawlers.shakeshack import parse_won
from src.crawlers.utils import NUTRITION_CSV_FIELDS, load_nutrition_csv, parse_number
from tests.conftest import load_json, load_soup


def by_name(items):
    return {item.name: item for item in items}


# ---------------------------------------------------------------- 맥도날드


@pytest.fixture
def mcdonalds_items(monkeypatch):
    crawler = McDonaldsCrawler()

    def fake_fetch_json(url, params=None):
        if url.endswith("/product/product/list"):
            assert params["subCategory"] == 16  # 0이면 빈 목록이 오므로 '버거전체'를 써야 함
            return load_json("mcdonalds/product_list.json")
        if url.endswith("/product/nutrition"):
            return load_json("mcdonalds/nutrition.json")
        raise AssertionError(f"예상하지 못한 요청: {url}")

    monkeypatch.setattr(crawler, "fetch_json", fake_fetch_json)
    return crawler.crawl()


def test_mcdonalds_collects_all_burgers(mcdonalds_items):
    assert len(mcdonalds_items) == 23
    assert all(item.brand_slug == "mcdonalds" for item in mcdonalds_items)
    assert all(item.price is None and item.set_price is None for item in mcdonalds_items)  # 사이트가 가격 미제공


def test_mcdonalds_big_mac(mcdonalds_items):
    big_mac = by_name(mcdonalds_items)["빅맥"]  # '빅맥® 세트' → '빅맥'
    assert big_mac.name_en == "Big Mac"
    assert big_mac.detail_url == "https://www.mcdonalds.co.kr/kor/menu/detail/178/3/16"
    assert big_mac.image_url is None  # 저작권 문제로 브랜드 공식 이미지는 수집하지 않음
    assert not big_mac.is_limited

    n = big_mac.nutrition
    assert (n.serving_size_g, n.calories_kcal, n.protein_g) == (223, 582, 27)
    assert (n.saturated_fat_g, n.sugar_g, n.sodium_mg) == (11, 8, 902)


def test_mcdonalds_nutrition_matched_for_every_burger(mcdonalds_items):
    missing = [item.name for item in mcdonalds_items if item.nutrition.calories_kcal is None]
    assert missing == []


def test_mcdonalds_limited_menu_by_end_date(mcdonalds_items):
    assert by_name(mcdonalds_items)["맥크리스피 고추장 버터"].is_limited  # 2026.October.21st 종료


# ---------------------------------------------------------------- 버거킹


@pytest.fixture
def burgerking_items(monkeypatch):
    crawler = BurgerKingCrawler()
    details = {"1080013", "7111052"}  # 와퍼 단품·세트만 픽스처가 있음

    def fake_call(trcode, body):
        if trcode in ("BKR0632", "BKR0347"):
            return load_json(f"burgerking/{trcode}.json")["body"]
        if trcode == "BKR0634":
            if body["menuCd"] in details:
                return load_json(f"burgerking/BKR0634_{body['menuCd']}.json")["body"]
            raise RuntimeError("픽스처 없음")  # 크롤러는 상세 실패 메뉴를 건너뜀
        raise AssertionError(f"예상하지 못한 trcode: {trcode}")

    monkeypatch.setattr(crawler, "_call", fake_call)
    return crawler.crawl()


def test_burgerking_whopper(burgerking_items):
    assert [item.name for item in burgerking_items] == ["와퍼"]
    whopper = burgerking_items[0]
    assert whopper.price == 7400
    assert whopper.set_price == 9600
    assert whopper.source_id == "1080013"
    assert whopper.detail_url == "https://www.burgerking.co.kr/menu/detail/1080013"
    assert whopper.image_url is None  # 저작권 문제로 브랜드 공식 이미지는 수집하지 않음
    assert whopper.description

    n = whopper.nutrition
    assert (n.serving_size_g, n.calories_kcal, n.protein_g) == (286, 706, 30)
    assert (n.sugar_g, n.saturated_fat_g, n.sodium_mg) == (10, 12, 1098)


def test_burgerking_classifies_menus(monkeypatch):
    """묶음 상품(X2, +), 라지세트는 제외하고 단품 ↔ 세트를 이름으로 짝지음"""
    crawler = BurgerKingCrawler()
    requested = []

    def fake_call(trcode, body):
        if trcode in ("BKR0632", "BKR0347"):
            return load_json(f"burgerking/{trcode}.json")["body"]
        requested.append(body["menuCd"])
        return {"dineInprc": "1000", "menuKeywordList": []}  # 이름은 목록(BKR0632) 값을 사용

    monkeypatch.setattr(crawler, "_call", fake_call)
    items = crawler.crawl()

    names = [item.name for item in items]
    assert len(names) == len(set(names))
    assert not any("세트" in name or "X2" in name or "+" in name for name in names)
    assert "7712224" not in requested  # 와퍼주니어X2
    assert "7714341" not in requested  # 몬스터 맥시멈 라지세트


# ---------------------------------------------------------------- 롯데리아


@pytest.fixture
def lotteria_items(monkeypatch):
    crawler = LotteriaCrawler()

    def fake_fetch_soup(url, params=None, encoding="utf-8"):
        if url.endswith("/brand/ria"):
            return load_soup("lotteria/brand_ria.html")
        if url.endswith("/ria/items.html"):
            return load_soup("lotteria/nutrition.html")
        if "/products/introductions/" in url:
            return load_soup("lotteria/detail_REP_000073.html")
        raise AssertionError(f"예상하지 못한 요청: {url}")

    monkeypatch.setattr(crawler, "fetch_soup", fake_fetch_soup)
    return crawler.crawl()


def test_lotteria_collects_burger_section_only(lotteria_items):
    names = [item.name for item in lotteria_items]
    assert len(names) == 29
    assert len(set(names)) == 29  # 추천메뉴 섹션 중복 없음
    assert not any(name.endswith("팩") for name in names)


def test_lotteria_hanwoo_bulgogi(lotteria_items):
    burger = by_name(lotteria_items)["한우불고기버거"]
    assert burger.price == 9200
    assert burger.set_price is None
    assert burger.source_id == "REP_000073"
    assert burger.image_url is None  # 저작권 문제로 브랜드 공식 이미지는 수집하지 않음
    assert burger.description.startswith("브리오쉬번에 국내산 한우")

    n = burger.nutrition
    assert (n.serving_size_g, n.calories_kcal, n.protein_g) == (263, 572, 23)
    assert (n.sodium_mg, n.sugar_g, n.saturated_fat_g) == (800, 15, 12)


def test_lotteria_nutrition_matched_for_every_burger(lotteria_items):
    missing = [item.name for item in lotteria_items if item.nutrition.calories_kcal is None]
    assert missing == []


# ---------------------------------------------------------------- 맘스터치


@pytest.fixture
def momstouch_crawl(monkeypatch):
    crawler = MomsTouchCrawler()
    requested_pages = []

    def fake_fetch_soup(url, params=None, encoding="utf-8"):
        if url.endswith("/menu/new.php"):
            requested_pages.append(params["pageNo"])
            return load_soup(f"momstouch/list_p{params['pageNo']}.html")
        if "/menu/view.php" in url:
            return load_soup("momstouch/view_80.html")
        raise AssertionError(f"예상하지 못한 요청: {url}")

    monkeypatch.setattr(crawler, "fetch_soup", fake_fetch_soup)
    return crawler.crawl(), requested_pages


def test_momstouch_paginates_until_empty_page(momstouch_crawl):
    items, pages = momstouch_crawl
    assert pages == [1, 2, 3, 4]  # 4페이지가 비어 있으면 중단
    assert len(items) == 25
    assert len({item.source_id for item in items}) == 25


def test_momstouch_thigh_burger(momstouch_crawl):
    burger = by_name(momstouch_crawl[0])["싸이버거"]
    assert burger.name_en == "Thigh Burger"
    assert burger.source_id == "80"
    assert burger.detail_url == "https://www.momstouch.co.kr/menu/view.php?idx=80"
    assert burger.description
    assert burger.price is None  # 사이트가 가격 미제공

    # 영양성분은 판독 CSV에서 매칭
    n = burger.nutrition
    assert (n.serving_size_g, n.calories_kcal, n.protein_g) == (230, 594, 28)
    assert (n.sodium_mg, n.sugar_g, n.saturated_fat_g) == (1009, 14, 8.6)
    assert n.basis_note.startswith("단품 기준 (맘스터치 영양성분표")


def test_momstouch_nutrition_matched_for_most_burgers(momstouch_crawl):
    items = momstouch_crawl[0]
    matched = [item for item in items if item.nutrition.calories_kcal is not None]
    assert len(matched) >= 20


def test_momstouch_nutrition_csv_is_complete():
    exact, _ = load_nutrition_csv(MOMSTOUCH_NUTRITION_CSV)
    assert len(exact) >= 25
    for row in exact.values():
        assert all(parse_number(row[col]) for col in NUTRITION_CSV_FIELDS if col in row), row["name"]


def test_momstouch_warns_when_nutrition_image_changes(caplog):
    # 픽스처(view_80.html)는 이전 영양성분표 이미지를 참조
    caplog.set_level("WARNING")
    crawler = MomsTouchCrawler()
    crawler.fetch_soup = lambda url, params=None, encoding="utf-8": load_soup("momstouch/view_80.html")
    crawler.request_delay = 0
    crawler._check_nutrition_image("https://www.momstouch.co.kr/menu/view.php?idx=80")
    assert "영양성분표 이미지가 바뀌었습니다" in caplog.text


# ---------------------------------------------------------------- 판독 영양성분 CSV


@pytest.mark.parametrize(
    "filename, min_rows",
    [
        ("momstouch_nutrition.csv", 25),
        ("kfc_nutrition.csv", 10),
        ("frankburger_nutrition.csv", 15),
        ("nobrandburger_nutrition.csv", 20),
    ],
)
def test_nutrition_csv_rows_have_core_values(filename, min_rows):
    exact, _ = load_nutrition_csv(filename)
    assert len(exact) >= min_rows
    for row in exact.values():
        for field in ("serving_size_g", "calories_kcal", "sodium_mg", "protein_g"):
            assert parse_number(row[field]), (row["name"], field)


def _no_source_check(crawler):
    """영양성분표 갱신 확인(HEAD 요청)을 끔"""
    crawler.last_modified = lambda url: None
    return crawler


# ---------------------------------------------------------------- KFC


@pytest.fixture
def kfc_items():
    crawler = _no_source_check(KFCCrawler())
    posted = {}

    def fake_post_form(url, data, headers):
        posted.update(data=data, headers=headers)
        return load_json("kfc/delivery_burger.json")

    crawler.fetch_json = lambda url, params=None: load_json("kfc/session.json")
    crawler._post_form = fake_post_form
    items = crawler.crawl()
    assert posted["headers"] == {"X-CSRF-TOKEN": "test-token"}
    assert posted["data"]["delivery_subGroupCd"] == "BEGR"
    return items


def test_kfc_keeps_only_burgers_with_set_price(kfc_items):
    names = [item.name for item in kfc_items]
    assert len(names) == 9
    assert not [name for name in names if name.endswith(("세트", "박스", "콤보"))]
    assert "툼켄치밥" not in names  # 영양성분표 버거 목록에 없는 메뉴 제외

    zinger = by_name(kfc_items)["징거"]
    assert (zinger.price, zinger.set_price) == (6800, 9400)
    assert zinger.detail_url == "https://www.kfckorea.com/menu/detail/N/1249525"
    assert zinger.image_url is None  # 저작권 문제로 브랜드 공식 이미지는 수집하지 않음
    n = zinger.nutrition
    assert (n.serving_size_g, n.calories_kcal, n.protein_g, n.sodium_mg) == (225, 553, 33, 866)


def test_kfc_restores_chik_character(kfc_items):
    assert "칰폴레맵징거타워" in by_name(kfc_items)


# ---------------------------------------------------------------- 프랭크버거


@pytest.fixture
def frankburger_items():
    crawler = _no_source_check(FrankBurgerCrawler())
    crawler.fetch_soup = lambda url, params=None, encoding="utf-8": load_soup("frankburger/menu_1.html")
    return crawler.crawl()


def test_frankburger_burgers(frankburger_items):
    assert len(frankburger_items) == 15
    burger = by_name(frankburger_items)["K불고기버거"]  # 'K 불고기 버거' → 공백 제거
    assert burger.description.startswith("전통 궁중식")
    assert burger.price is None
    assert (burger.nutrition.calories_kcal, burger.nutrition.sodium_mg) == (491.99, 656.9)


def test_frankburger_nutrition_matched_for_every_burger(frankburger_items):
    assert [item.name for item in frankburger_items if item.nutrition.calories_kcal is None] == []


# ---------------------------------------------------------------- 노브랜드버거


def _nobrandburger_soup(url, params=None, encoding="utf-8"):
    if url.endswith("/popup/nobrandburger_02.html"):
        return load_soup("nobrandburger/nutrition_popup.html")
    return load_soup("nobrandburger/index.html")


@pytest.fixture
def nobrandburger_items():
    crawler = NoBrandBurgerCrawler()
    crawler.fetch_soup = _nobrandburger_soup
    return crawler.crawl()


def test_nobrandburger_no_warning_for_current_nutrition_image(caplog):
    crawler = NoBrandBurgerCrawler()
    crawler.fetch_soup = _nobrandburger_soup
    caplog.set_level("WARNING")
    crawler._check_nutrition_image()
    assert "영양성분표 이미지가 바뀌었습니다" not in caplog.text


def test_nobrandburger_burgers(nobrandburger_items):
    assert len(nobrandburger_items) == 22
    burger = by_name(nobrandburger_items)["진짜 비빔밥 버거"]
    assert burger.name_en == "Real Bibimbap Burger"
    assert burger.description.startswith("쌀과 5종 야채로")
    assert (burger.nutrition.calories_kcal, burger.nutrition.sodium_mg) == (674, 1351)


def test_nobrandburger_nutrition_matched_for_every_burger(nobrandburger_items):
    assert [item.name for item in nobrandburger_items if item.nutrition.calories_kcal is None] == []


# ---------------------------------------------------------------- 쉐이크쉑


@pytest.fixture
def shakeshack_items():
    crawler = ShakeShackCrawler()
    crawler.fetch_soup = lambda url, params=None, encoding="utf-8": load_soup("shakeshack/menu.html")
    return crawler.crawl()


@pytest.mark.parametrize("text, won", [("W 10,9", 10900), ("Single W 9,2 Double W 14,2", 9200), ("", None)])
def test_shakeshack_price_format(text, won):
    assert parse_won(text) == won


def test_shakeshack_burgers_and_chicken_burgers(shakeshack_items):
    items = by_name(shakeshack_items)
    assert len(items) == 12
    assert "치킨 바이트" not in items  # 치킨 탭의 버거가 아닌 메뉴 제외
    assert "헤리티지 떡갈비 쉑" not in items  # HTML 주석으로 숨긴 메뉴 제외

    shack = items["쉑버거"]
    assert (shack.name_en, shack.price) == ("ShackBurger", 9200)
    assert shack.image_url is None  # 저작권 문제로 브랜드 공식 이미지는 수집하지 않음
    assert items["쉑하우스 바비큐 버거"].is_limited  # 시즌 한정
    assert items["핫 치킨"].price == 9700  # 닭가슴살 기준


# ---------------------------------------------------------------- 파이브가이즈


@pytest.fixture
def fiveguys_items():
    crawler = _no_source_check(FiveGuysCrawler())
    crawler.fetch_soup = lambda url, params=None, encoding="utf-8": load_soup("fiveguys/burgers.html")
    return crawler.crawl()


@pytest.mark.parametrize(
    "name, recipe",
    [
        ("햄버거", {"bun": 1, "patty": 2}),
        ("베이컨 치즈버거", {"bun": 1, "patty": 2, "cheese": 2, "bacon": 1}),
        ("리틀 치즈버거", {"bun": 1, "patty": 1, "cheese": 1}),
    ],
)
def test_fiveguys_recipe(name, recipe):
    assert burger_recipe(name) == recipe


def test_fiveguys_burgers_sum_components(fiveguys_items):
    assert len(fiveguys_items) == 8  # 토핑 추천 카드 제외
    n = by_name(fiveguys_items)["치즈버거"].nutrition
    # 번 238 + 패티 195x2 + 치즈 61.2x2, 소금 (0.49 + 0.13x2 + 0.79x2)g x 400
    assert n.calories_kcal == 750.4
    assert n.sodium_mg == 932
    assert n.basis_note.startswith("기본 구성 합산, 토핑 제외")


# ---------------------------------------------------------------- 크라이치즈버거


@pytest.fixture
def crycheeseburger_items():
    crawler = CryCheeseBurgerCrawler()
    crawler.fetch_soup = lambda url, params=None, encoding="utf-8": load_soup("crycheeseburger/menu.html")
    return crawler.crawl()


def test_crycheeseburger_prices_and_set_prices(crycheeseburger_items):
    items = by_name(crycheeseburger_items)
    assert len(items) == 4
    double = items["더블치즈버거"]
    assert (double.price, double.set_price) == (7900, 10900)
    assert double.image_url is None  # 저작권 문제로 브랜드 공식 이미지는 수집하지 않음
    assert items["치킨버거"].description is None  # 소개 문구가 없으면 빈 문자열 대신 None


# ---------------------------------------------------------------- 공통


@pytest.mark.parametrize(
    "fixture_name",
    [
        "mcdonalds_items",
        "burgerking_items",
        "lotteria_items",
        "kfc_items",
        "frankburger_items",
        "nobrandburger_items",
        "shakeshack_items",
        "fiveguys_items",
        "crycheeseburger_items",
    ],
)
def test_crawlers_do_not_collect_brand_images(fixture_name, request):
    items = request.getfixturevalue(fixture_name)
    assert items and all(item.image_url is None for item in items)


def test_momstouch_does_not_collect_brand_images(momstouch_crawl):
    assert all(item.image_url is None for item in momstouch_crawl[0])
