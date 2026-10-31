import logging
from typing import List

from src.crawlers.base import BaseCrawler
from src.crawlers.utils import (
    clean_name,
    load_nutrition_csv,
    match_by_name,
    name_key,
    nutrition_from_row,
    parse_price,
)
from src.models.burger import BurgerItem

logger = logging.getLogger(__name__)

BASE_URL = "https://www.kfckorea.com"
SESSION_URL = f"{BASE_URL}/kfc/interface/session"
DELIVERY_LIST_URL = f"{BASE_URL}/kfc/interface/selectDeliveryList"
BURGER_SUB_GROUP = "BEGR"
# API가 '칰'을 표현하지 못해 '_CHIK_'으로 내려줌
NAME_REPLACEMENTS = {"_CHIK_": "칰"}

# 영양성분표는 원산지 표시판과 합쳐진 이미지 한 장이라 사람이 판독·검수한 CSV를 사용
# 이미지가 갱신되면(Last-Modified 변경) 경고 로그를 남기므로, 새 표를 판독해 CSV와 아래 두 값을 갱신
NUTRITION_CSV = "kfc_nutrition.csv"
NUTRITION_LAST_MODIFIED = "Mon, 19 Oct 2026 18:58:22 GMT"
NUTRITION_VERSION = "Ver. 20261020"


class KFCCrawler(BaseCrawler):
    """KFC 공식 사이트 딜리버리 메뉴 API 크롤러.

    버거&세트 목록(단품·세트·박스)에서 영양성분표에 있는 단품만 버거로 보고,
    '{버거명}세트' 가격을 세트가로 붙입니다. 가격은 딜리버리 기준입니다.
    """

    brand_name = "KFC"
    brand_slug = "kfc"

    def crawl(self) -> List[BurgerItem]:
        session_info = self.fetch_json(SESSION_URL)
        csrf = session_info["csrf"]
        menus = self._post_form(
            DELIVERY_LIST_URL,
            {"product_ordertype": "D", "delivery_subGroupCd": BURGER_SUB_GROUP, "merchantId": ""},
            headers={csrf["headerName"]: csrf["token"]},
        )["kfcs"]["data"]["list"]

        nutrition_table = load_nutrition_csv(NUTRITION_CSV)
        prices = {name_key(self._name(menu)): parse_price(menu.get("price")) for menu in menus}

        items = []
        for menu in menus:
            name = self._name(menu)
            row = match_by_name(name, *nutrition_table)
            if row is None:  # 세트·박스·켄치밥 등은 영양성분표의 버거 목록에 없음
                continue
            items.append(
                BurgerItem(
                    brand=self.brand_name,
                    brand_slug=self.brand_slug,
                    name=name,
                    source_id=menu["menuCd"],
                    price=parse_price(menu.get("price")),
                    set_price=prices.get(name_key(f"{name}세트")),
                    description=menu.get("menuDesc") or None,
                    detail_url=f"{BASE_URL}/menu/detail/N/{menu['menuCd']}",
                    nutrition=nutrition_from_row(row, f"단품 기준 (KFC 영양정보표 {NUTRITION_VERSION})"),
                )
            )

        image_path = session_info.get("infoNutrition")
        if image_path:
            self.warn_if_nutrition_source_changed(
                NUTRITION_LAST_MODIFIED, self.last_modified(f"{BASE_URL}{image_path}"), NUTRITION_CSV
            )
        logger.info("[%s] 버거 %d건 수집", self.brand_name, len(items))
        return items

    def _post_form(self, url: str, data: dict, headers: dict) -> dict:
        logger.info("[%s] POST %s", self.brand_name, url)
        response = self.session.post(url, data=data, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _name(menu: dict) -> str:
        name = menu.get("menuNm") or ""
        for placeholder, char in NAME_REPLACEMENTS.items():
            name = name.replace(placeholder, char)
        return clean_name(name)
