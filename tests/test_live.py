"""실제 브랜드 사이트에 접속하는 스모크 테스트. 사이트 구조 변경 감지용이며 `pytest --live`로만 실행됩니다."""

import pytest

from src.crawlers import CRAWLERS

pytestmark = pytest.mark.live

MIN_ITEMS = 10
# 영양성분을 텍스트로 공개하는 브랜드만 매칭률 확인 (맘스터치는 이미지)
MIN_NUTRITION_RATIO = {"mcdonalds": 0.8, "burgerking": 0.8, "lotteria": 0.8}


@pytest.mark.parametrize("slug", list(CRAWLERS))
def test_live_crawl(slug):
    items = CRAWLERS[slug]().crawl()

    assert len(items) >= MIN_ITEMS, f"{slug}: {len(items)}건만 수집됨"
    assert all(item.name and item.detail_url for item in items)
    assert len({item.name for item in items}) == len(items), "중복 메뉴명"

    if slug in MIN_NUTRITION_RATIO:
        matched = sum(item.nutrition.calories_kcal is not None for item in items)
        assert matched / len(items) >= MIN_NUTRITION_RATIO[slug], f"{slug}: 영양성분 매칭 {matched}/{len(items)}"
    if slug in ("burgerking", "lotteria"):
        priced = sum(item.price is not None for item in items)
        assert priced / len(items) >= 0.8, f"{slug}: 가격 수집 {priced}/{len(items)}"
