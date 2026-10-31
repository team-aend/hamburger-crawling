from .base import BaseCrawler
from .burgerking import BurgerKingCrawler
from .crycheeseburger import CryCheeseBurgerCrawler
from .fiveguys import FiveGuysCrawler
from .frankburger import FrankBurgerCrawler
from .kfc import KFCCrawler
from .lotteria import LotteriaCrawler
from .mcdonalds import McDonaldsCrawler
from .momstouch import MomsTouchCrawler
from .nobrandburger import NoBrandBurgerCrawler
from .shakeshack import ShakeShackCrawler

# CLI에서 --brand 로 선택하는 브랜드 slug → 크롤러
CRAWLERS = {
    crawler.brand_slug: crawler
    for crawler in (
        McDonaldsCrawler,
        BurgerKingCrawler,
        LotteriaCrawler,
        MomsTouchCrawler,
        KFCCrawler,
        FrankBurgerCrawler,
        NoBrandBurgerCrawler,
        ShakeShackCrawler,
        FiveGuysCrawler,
        CryCheeseBurgerCrawler,
    )
}

__all__ = [
    "BaseCrawler",
    "BurgerKingCrawler",
    "CRAWLERS",
    "CryCheeseBurgerCrawler",
    "FiveGuysCrawler",
    "FrankBurgerCrawler",
    "KFCCrawler",
    "LotteriaCrawler",
    "McDonaldsCrawler",
    "MomsTouchCrawler",
    "NoBrandBurgerCrawler",
    "ShakeShackCrawler",
]
