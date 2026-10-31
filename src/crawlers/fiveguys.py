import csv
import logging
from typing import Dict, List

from src.crawlers.base import BaseCrawler
from src.crawlers.utils import NUTRITION_DATA_DIR, clean_name, parse_number
from src.models.burger import BurgerItem, NutritionInfo

logger = logging.getLogger(__name__)

BASE_URL = "https://www.fiveguys.co.kr"
BURGER_URL = f"{BASE_URL}/menu/%eb%b2%84%ea%b1%b0-%eb%a9%94%eb%89%b4-%ed%96%84%eb%b2%84%ea%b1%b0-%ec%b9%98%ec%a6%88%eb%b2%84%ea%b1%b0-%eb%93%b1/"

# 영양 정보 PDF는 버거 완제품이 아니라 재료(번·패티·치즈·베이컨)별 값만 공개하므로,
# 판독한 재료 CSV를 기본 구성대로 합산합니다 (토핑 제외). PDF가 갱신되면 경고 로그를 남기므로
# 새 PDF를 판독해 CSV와 아래 값을 갱신
NUTRITION_CSV = "fiveguys_components.csv"
NUTRITION_PDF_URL = (
    "https://www.fiveguys.com/-/media/public-site/files/allergen-ingredients-and-nutrition-info/"
    "combined-guide/Korea-KO.pdf"
)
NUTRITION_LAST_MODIFIED = "Mon, 28 Sep 2026 10:16:38 GMT"
NUTRITION_VERSION = "V011026"
# 식품 표시 기준 환산: 나트륨(mg) = 소금(g) / 2.5 * 1000
SODIUM_MG_PER_SALT_G = 400
SUM_FIELDS = (
    "serving_size_g",
    "calories_kcal",
    "fat_g",
    "saturated_fat_g",
    "carbohydrate_g",
    "sugar_g",
    "protein_g",
)


def load_components() -> Dict[str, dict]:
    with open(NUTRITION_DATA_DIR / NUTRITION_CSV, encoding="utf-8") as f:
        return {row["component"]: row for row in csv.DictReader(f)}


def burger_recipe(name: str) -> Dict[str, int]:
    """메뉴명 → 재료 개수. 일반 버거는 패티 2장, '리틀'은 1장, 치즈는 패티 수만큼, 베이컨은 1인분(2조각)"""
    patties = 1 if "리틀" in name else 2
    recipe = {"bun": 1, "patty": patties}
    if "치즈" in name:
        recipe["cheese"] = patties
    if "베이컨" in name:
        recipe["bacon"] = 1
    return recipe


def recipe_nutrition(recipe: Dict[str, int], components: Dict[str, dict]) -> NutritionInfo:
    totals = {field: 0.0 for field in SUM_FIELDS}
    salt = 0.0
    for component, count in recipe.items():
        row = components[component]
        for field in SUM_FIELDS:
            totals[field] += parse_number(row[field]) * count
        salt += parse_number(row["salt_g"]) * count
    return NutritionInfo(
        basis_note=f"기본 구성 합산, 토핑 제외 (파이브가이즈 영양 정보 {NUTRITION_VERSION})",
        sodium_mg=round(salt * SODIUM_MG_PER_SALT_G),
        **{field: round(value, 1) for field, value in totals.items()},
    )


class FiveGuysCrawler(BaseCrawler):
    """파이브가이즈 코리아 공식 사이트(WordPress, 정적 HTML) 크롤러.

    가격은 사이트에 노출되지 않습니다.
    """

    brand_name = "파이브가이즈"
    brand_slug = "fiveguys"

    def crawl(self) -> List[BurgerItem]:
        soup = self.fetch_soup(BURGER_URL)
        components = load_components()

        items = []
        for card in soup.select("li[id^=menu-item-] .card-menu-item"):
            name = clean_name(card.select_one("h3").get_text())
            if not name.endswith("버거"):
                continue
            description = card.select_one(".card-menu-item-content p")
            items.append(
                BurgerItem(
                    brand=self.brand_name,
                    brand_slug=self.brand_slug,
                    name=name,
                    source_id=card.find_parent("li")["id"].removeprefix("menu-item-"),
                    description=description.get_text(" ", strip=True) if description else None,
                    detail_url=BURGER_URL,
                    nutrition=recipe_nutrition(burger_recipe(name), components),
                )
            )

        self.warn_if_nutrition_source_changed(
            NUTRITION_LAST_MODIFIED, self.last_modified(NUTRITION_PDF_URL), NUTRITION_CSV
        )
        logger.info("[%s] 버거 %d건 수집", self.brand_name, len(items))
        return items
