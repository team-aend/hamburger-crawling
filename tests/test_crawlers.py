"""저장해 둔 실제 사이트 응답(tests/fixtures)으로 브랜드별 파싱 결과를 검증 (네트워크 접속 없음)"""

import pytest

from src.crawlers import BurgerKingCrawler, LotteriaCrawler, McDonaldsCrawler, MomsTouchCrawler
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
    assert big_mac.image_url.startswith("https://www.mcdonalds.co.kr/upload/")
    assert "%EB%B9%85%EB%A7%A5" in big_mac.image_url  # 한글 경로는 퍼센트 인코딩
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
    assert whopper.image_url.startswith("https://")
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
    assert burger.image_url == "https://img.lotteeatz.com/upload/product/2023/02/10/20230210102118259_1.png"
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
    assert burger.image_url.startswith("https://www.momstouch.co.kr/")
    assert burger.description
    assert burger.price is None  # 사이트가 가격 미제공
    assert burger.nutrition.calories_kcal is None  # 영양성분은 이미지로만 공개
