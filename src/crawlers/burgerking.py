import json
import logging
import re
import time
from typing import List, Optional

from src.crawlers.base import BaseCrawler
from src.crawlers.utils import (
    build_name_tables,
    clean_name,
    match_by_name,
    name_key,
    parse_number,
    parse_price,
    strip_html,
)
from src.models.burger import BurgerItem, NutritionInfo

logger = logging.getLogger(__name__)

BASE_URL = "https://www.burgerking.co.kr"
# 오리지널스&맥시멈, 프리미엄, 와퍼&주니어, 치킨&슈림프
BURGER_CATEGORIES = {"K200002", "K200003", "K200004", "K200005"}
KEYWORD_LIMITED = "2002"  # 기간한정
# 'X2', '+프라이R+콜라R', '와주X불고기와주' 같은 묶음 상품
PACK_RE = re.compile(r"X\d|\+|[가-힣]X[가-힣]")


class BurgerKingCrawler(BaseCrawler):
    """버거킹 공식 사이트(bizMOB) 내부 API 크롤러.

    BKR0632(전체 메뉴) → BKR0634(메뉴 상세: 매장가·설명·키워드) → BKR0347(영양성분, 메뉴명으로 매칭)
    """

    brand_name = "버거킹"
    brand_slug = "burgerking"
    request_delay = 0.2

    def crawl(self) -> List[BurgerItem]:
        menus = {}
        for category in self._call("BKR0632", {"menuKeywordList": []})["allMenuList"]:
            if category["menuCategoryCd"] in BURGER_CATEGORIES:
                for menu in category["menuInfo"]:
                    menus.setdefault(menu["menuCd"], menu)

        singles, sets = {}, {}
        for menu in menus.values():
            name = clean_name(menu["menuNm"])
            if PACK_RE.search(name) or name.endswith("라지세트"):
                continue
            if name.endswith("세트"):
                sets.setdefault(name_key(name[: -len("세트")]), menu)
            else:
                singles.setdefault(name_key(name), menu)

        nutrient_rows = [r for r in self._call("BKR0347", {})["allNutrientList"] if parse_number(r.get("calory"))]
        nutrition_tables = build_name_tables(nutrient_rows, lambda r: r["menuNm"])

        items = []
        for key, menu in singles.items():
            detail = self._detail(menu["menuCd"])
            if detail is None:
                continue
            set_menu = sets.get(key)
            set_detail = self._detail(set_menu["menuCd"]) if set_menu else None

            name = clean_name(detail.get("menuNm") or menu["menuNm"])
            keywords = {str(k.get("menuKeywordPk")) for k in detail.get("menuKeywordList") or []}
            row = match_by_name(name, *nutrition_tables)
            if row is None:
                logger.warning("[%s] 영양성분 매칭 실패: %s", self.brand_name, name)

            items.append(
                BurgerItem(
                    brand=self.brand_name,
                    brand_slug=self.brand_slug,
                    name=name,
                    source_id=menu["menuCd"],
                    price=parse_price(detail.get("dineInprc")),
                    set_price=parse_price(set_detail.get("dineInprc")) if set_detail else None,
                    description=strip_html(detail.get("menuDesc")),
                    detail_url=f"{BASE_URL}/menu/detail/{menu['menuCd']}",
                    is_limited=KEYWORD_LIMITED in keywords,
                    nutrition=self._parse_nutrition(row) if row else NutritionInfo(),
                )
            )

        logger.info("[%s] 버거 %d건 수집", self.brand_name, len(items))
        return items

    def _call(self, trcode: str, body: dict) -> dict:
        message = {"header": {"result": True, "trcode": trcode, "cd_call_chnn": "01"}, "body": body}
        response = self.session.post(
            f"{BASE_URL}/burgerking/{trcode}.json",
            data={"message": json.dumps(message, ensure_ascii=False)},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        header = payload.get("header", {})
        if not header.get("result"):
            raise RuntimeError(f"{trcode} 실패: {header.get('error_code')} {header.get('error_text')}")
        return payload["body"]

    def _detail(self, menu_cd: str) -> Optional[dict]:
        time.sleep(self.request_delay)
        try:
            return self._call("BKR0634", {"menuCd": menu_cd})
        except Exception as exc:  # 상세 1건 실패로 전체 크롤링을 멈추지 않음
            logger.warning("[%s] 상세 조회 실패 %s: %s", self.brand_name, menu_cd, exc)
            return None

    @staticmethod
    def _parse_nutrition(row: dict) -> NutritionInfo:
        return NutritionInfo(
            serving_size_g=parse_number(row.get("weight")),
            calories_kcal=parse_number(row.get("calory")),
            protein_g=parse_number(row.get("protein")),
            sugar_g=parse_number(row.get("sugars")),
            saturated_fat_g=parse_number(row.get("satufat")),
            sodium_mg=parse_number(row.get("natrium")),
            basis_note="단품 기준 (버거킹 영양정보)",
        )
