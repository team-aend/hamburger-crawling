import logging
import re
from typing import List
from urllib.parse import quote

from src.crawlers.base import BaseCrawler
from src.crawlers.utils import build_name_tables, clean_name, match_by_name, parse_number, strip_html
from src.models.burger import BurgerItem, NutritionInfo

logger = logging.getLogger(__name__)

BASE_URL = "https://www.mcdonalds.co.kr"
API_URL = f"{BASE_URL}/api/v1/kor"
BURGER_MAIN_CATEGORY = 1
BURGER_SUB_CATEGORY_ALL = 16

# nutritionFacts 문자열의 라벨 → NutritionInfo 필드
NUTRITION_LABELS = {
    "중량": "serving_size_g",
    "열량": "calories_kcal",
    "포화지방": "saturated_fat_g",
    "당": "sugar_g",
    "단백질": "protein_g",
    "나트륨": "sodium_mg",
}


class McDonaldsCrawler(BaseCrawler):
    """맥도날드 공식 사이트 JSON API 크롤러.

    메뉴 목록은 대부분 '세트'로만 노출되므로 세트명에서 버거명을 뽑고,
    영양성분은 /product/nutrition 의 '버거' 그룹(단품)과 이름으로 매칭합니다.
    가격은 공식 사이트에서 제공하지 않습니다.
    """

    brand_name = "맥도날드"
    brand_slug = "mcdonalds"

    def crawl(self) -> List[BurgerItem]:
        products = self.fetch_json(
            f"{API_URL}/product/product/list",
            params={
                "page": 1,
                "view_rows": 100,
                "mainCategory": BURGER_MAIN_CATEGORY,
                "subCategory": BURGER_SUB_CATEGORY_ALL,
                "searchWord": "",
            },
        )["resultObject"]["list"]

        nutrition_rows = [
            row
            for row in self.fetch_json(f"{API_URL}/product/nutrition")["resultObject"]["list"]
            if row.get("menuGroup") == "버거"
        ]
        nutrition_tables = build_name_tables(nutrition_rows, lambda r: r["menuName"])

        items = []
        seen = set()
        for product in products:
            name = re.sub(r"\s*세트$", "", clean_name(product["korName"]))
            if not name or name in seen:
                continue
            seen.add(name)

            row = match_by_name(name, *nutrition_tables)
            if row is None:
                logger.warning("[%s] 영양성분 매칭 실패: %s", self.brand_name, name)

            name_en = clean_name(product.get("engName") or "")
            items.append(
                BurgerItem(
                    brand=self.brand_name,
                    brand_slug=self.brand_slug,
                    name=name,
                    name_en=re.sub(r"\s*Meal$", "", name_en) or None,
                    source_id=str(product["seq"]),
                    description=strip_html(product.get("korContent")),
                    image_url=self._image_url(product.get("pcImageUrl")),
                    detail_url=(
                        f"{BASE_URL}/kor/menu/detail/{product['seq']}/"
                        f"{product['rnum']}/{product['subCategorySeq']}"
                    ),
                    is_limited=self._is_limited(product.get("openTimeEnd")),
                    nutrition=self._parse_nutrition(row) if row else NutritionInfo(),
                )
            )

        logger.info("[%s] 버거 %d건 수집", self.brand_name, len(items))
        return items

    @staticmethod
    def _image_url(path: str) -> str:
        return f"{BASE_URL}{quote(path, safe='/%')}" if path else None

    @staticmethod
    def _is_limited(open_time_end: str) -> bool:
        """상시 메뉴는 판매 종료일이 2099/9999년으로 들어 있음"""
        year = re.search(r"\d{4}", open_time_end or "")
        return bool(year) and int(year.group()) < 2090

    @staticmethod
    def _parse_nutrition(row: dict) -> NutritionInfo:
        values = {}
        for part in (row.get("nutritionFacts") or "").split(","):
            label, _, value = part.partition(";")
            field = NUTRITION_LABELS.get(label.strip())
            if field:
                values[field] = parse_number(value)
        values.setdefault("calories_kcal", parse_number(row.get("calorie")))
        return NutritionInfo(basis_note="단품 기준 (맥도날드 영양정보)", **values)
