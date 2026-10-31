"""실제 브랜드 사이트에 접속하는 스모크 테스트. 사이트 구조 변경 감지용이며 `pytest --live`로만 실행됩니다."""

import pytest

from src.crawlers import CRAWLERS

pytestmark = pytest.mark.live

MIN_ITEMS = 10
# 버거 메뉴 자체가 적은 브랜드
MIN_ITEMS_BY_BRAND = {"kfc": 8, "fiveguys": 8, "crycheeseburger": 3}
# 영양성분을 제공하는 브랜드의 매칭률 (판독 CSV 브랜드는 신메뉴가 생기면 떨어질 수 있음)
MIN_NUTRITION_RATIO = {
    "mcdonalds": 0.8,
    "burgerking": 0.8,
    "lotteria": 0.8,
    "momstouch": 0.8,
    "kfc": 0.8,
    "frankburger": 0.8,
    "nobrandburger": 0.8,
    "fiveguys": 1.0,
}
PRICED_BRANDS = ("burgerking", "lotteria", "kfc", "shakeshack", "crycheeseburger")


@pytest.mark.parametrize("slug", list(CRAWLERS))
def test_live_crawl(slug):
    items = CRAWLERS[slug]().crawl()

    assert len(items) >= MIN_ITEMS_BY_BRAND.get(slug, MIN_ITEMS), f"{slug}: {len(items)}건만 수집됨"
    assert all(item.name and item.detail_url for item in items)
    assert len({item.name for item in items}) == len(items), "중복 메뉴명"

    if slug in MIN_NUTRITION_RATIO:
        matched = sum(item.nutrition.calories_kcal is not None for item in items)
        assert matched / len(items) >= MIN_NUTRITION_RATIO[slug], f"{slug}: 영양성분 매칭 {matched}/{len(items)}"
    if slug in PRICED_BRANDS:
        priced = sum(item.price is not None for item in items)
        assert priced / len(items) >= 0.8, f"{slug}: 가격 수집 {priced}/{len(items)}"
