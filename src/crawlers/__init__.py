from .base import BaseCrawler
from .burgerking import BurgerKingCrawler
from .lotteria import LotteriaCrawler
from .mcdonalds import McDonaldsCrawler
from .momstouch import MomsTouchCrawler

# CLI에서 --brand 로 선택하는 브랜드 slug → 크롤러
CRAWLERS = {
    crawler.brand_slug: crawler
    for crawler in (McDonaldsCrawler, BurgerKingCrawler, LotteriaCrawler, MomsTouchCrawler)
}

__all__ = [
    "BaseCrawler",
    "BurgerKingCrawler",
    "CRAWLERS",
    "LotteriaCrawler",
    "McDonaldsCrawler",
    "MomsTouchCrawler",
]
