import logging
from typing import List, Optional
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from src.config import DATABASE_URL
from src.models.burger import Base, BurgerItem, BurgerORM, NutritionInfo

logger = logging.getLogger(__name__)


class DatabaseStorage:
    """SQLAlchemy 기반 데이터베이스 저장 및 조회 클래스 (SQLite / MySQL / PostgreSQL 지원)"""

    def __init__(self, db_url: str = DATABASE_URL):
        self.engine = create_engine(db_url, echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def upsert_burgers(self, items: List[BurgerItem]) -> int:
        """브랜드+메뉴명을 기준으로 데이터를 추가하거나 업데이트(Upsert)"""
        saved_count = 0
        with self.SessionLocal() as session:
            for item in items:
                flat_data = item.to_flat_dict()
                stmt = select(BurgerORM).where(
                    BurgerORM.brand == item.brand,
                    BurgerORM.name == item.name,
                )
                existing = session.execute(stmt).scalar_one_or_none()

                if existing:
                    for key, value in flat_data.items():
                        setattr(existing, key, value)
                else:
                    session.add(BurgerORM(**flat_data))
                saved_count += 1

            session.commit()

        logger.info("DB 저장(Upsert) 완료: %d건", saved_count)
        return saved_count

    def get_burgers(
        self, brand: Optional[str] = None, keyword: Optional[str] = None
    ) -> List[BurgerItem]:
        """저장된 햄버거 정보를 브랜드 또는 메뉴명 키워드로 조회"""
        with self.SessionLocal() as session:
            stmt = select(BurgerORM)
            if brand:
                stmt = stmt.where(BurgerORM.brand == brand)
            if keyword:
                stmt = stmt.where(BurgerORM.name.contains(keyword))

            records = session.execute(stmt).scalars().all()
            return [
                BurgerItem(
                    brand=r.brand,
                    name=r.name,
                    name_en=r.name_en,
                    category=r.category,
                    price=r.price,
                    set_price=r.set_price,
                    description=r.description,
                    image_url=r.image_url,
                    detail_url=r.detail_url,
                    allergens=r.allergens,
                    origin_info=r.origin_info,
                    crawled_at=r.crawled_at,
                    nutrition=NutritionInfo(
                        weight_g=r.weight_g,
                        calories_kcal=r.calories_kcal,
                        protein_g=r.protein_g,
                        saturated_fat_g=r.saturated_fat_g,
                        sodium_mg=r.sodium_mg,
                        sugars_g=r.sugars_g,
                        caffeine_mg=r.caffeine_mg,
                    ),
                )
                for r in records
            ]
