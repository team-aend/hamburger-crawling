import logging
from typing import List

from src.crawlers.base import BaseCrawler
from src.models.burger import BurgerItem, NutritionInfo

logger = logging.getLogger(__name__)


class SampleBurgerCrawler(BaseCrawler):
    """프랜차이즈 크롤러 구현 예시 (정적/동적 크롤링 템플릿)"""

    brand_name = "샘플버거"

    def crawl(self) -> List[BurgerItem]:
        """
        실제 브랜드 크롤러를 작성할 때 이 메서드를 오버라이드합니다.
        - 정적 크롤링: soup = self.fetch_soup("https://...")
        - 동적 크롤링:
            with self.playwright_page() as page:
                page.goto("https://...")
                html = page.content()
        """
        logger.info("[%s] 샘플 햄버거 크롤링 데이터를 생성합니다...", self.brand_name)

        return [
            BurgerItem(
                brand="맥도날드",
                name="빅맥",
                name_en="Big Mac",
                category="버거",
                price=5500,
                set_price=6900,
                description="100% 순 쇠고기 패티 두 장에 빅맥만의 특별한 소스",
                image_url="https://www.mcdonalds.co.kr/upload/product/pcfile/1583727855319.png",
                detail_url="https://www.mcdonalds.co.kr/kor/menu/detail.do?seq=1",
                allergens="난류, 우유, 대두, 밀, 쇠고기",
                origin_info="쇠고기: 호주산",
                nutrition=NutritionInfo(
                    weight_g=223.0,
                    calories_kcal=583.0,
                    protein_g=27.0,
                    saturated_fat_g=11.0,
                    sodium_mg=902.0,
                    sugars_g=8.0,
                ),
            ),
            BurgerItem(
                brand="버거킹",
                name="와퍼",
                name_en="Whopper",
                category="버거",
                price=7100,
                set_price=9100,
                description="불에 직접 구운 100% 순 쇠고기 패티가 들어간 버거킹의 대표 메뉴",
                allergens="밀, 대두, 우유, 토마토, 쇠고기, 난류",
                origin_info="쇠고기: 호주산/뉴질랜드산",
                nutrition=NutritionInfo(
                    weight_g=278.0,
                    calories_kcal=619.0,
                    protein_g=29.0,
                    saturated_fat_g=11.0,
                    sodium_mg=830.0,
                    sugars_g=11.0,
                ),
            ),
        ]
