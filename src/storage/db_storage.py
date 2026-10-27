import logging
import re
from collections import Counter
from typing import List, Optional

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src.config import BURGER_CATEGORY_SLUG, DATABASE_URL
from src.models.burger import (
    Base,
    BrandORM,
    BurgerItem,
    CategoryORM,
    NutritionInfo,
    NutritionORM,
    ProductORM,
    ProductPriceORM,
    ProductVariantORM,
    utcnow,
)

logger = logging.getLogger(__name__)

PRICE_CHANNEL = "STORE"
NUTRITION_FIELDS = list(NutritionInfo.model_fields)


def slugify(name: str) -> str:
    """메뉴명을 slug로 변환 (한글 유지, 공백·특수문자는 '-')"""
    slug = re.sub(r"[^\w]+", "-", name.strip().lower(), flags=re.UNICODE)
    return slug.strip("-")[:200]


class DatabaseStorage:
    """버거픽 DB 상품 테이블(brands/products/product_variants/product_prices/nutrition) 저장·조회"""

    def __init__(self, db_url: str = DATABASE_URL):
        self.engine = create_engine(db_url, echo=False)
        if self.engine.dialect.name == "sqlite":
            # 운영 DB(PostgreSQL)는 스키마가 이미 있으므로 로컬 SQLite에서만 테이블 생성
            Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    # ------------------------------------------------------------------ 저장

    def upsert_burgers(self, items: List[BurgerItem], dry_run: bool = False) -> Counter:
        """상품·변형·가격·영양성분을 저장. 가격은 바뀐 경우에만 이력 행을 추가.

        dry_run=True면 모든 변경을 계산만 하고 롤백합니다.
        """
        stats: Counter = Counter()
        with self.SessionLocal() as session:
            category = self._get_or_create_category(session, stats)
            brands = {}
            for item in items:
                brand = brands.get(item.brand_slug)
                if brand is None:
                    brand = brands[item.brand_slug] = self._get_or_create_brand(session, item, stats)
                self._upsert_item(session, item, brand, category, stats)

            if dry_run:
                session.rollback()
                logger.info("DRY RUN - 롤백했습니다. 변경 예정: %s", dict(stats))
            else:
                session.commit()
                logger.info("DB 저장 완료: %s", dict(stats))
        return stats

    def _get_or_create_category(self, session: Session, stats: Counter) -> CategoryORM:
        category = session.scalar(select(CategoryORM).where(CategoryORM.slug == BURGER_CATEGORY_SLUG))
        if category is None:
            category = CategoryORM(name="버거", slug=BURGER_CATEGORY_SLUG)
            session.add(category)
            session.flush()
            stats["category_created"] += 1
        return category

    def _get_or_create_brand(self, session: Session, item: BurgerItem, stats: Counter) -> BrandORM:
        brand = session.scalar(select(BrandORM).where(BrandORM.slug == item.brand_slug))
        if brand is None:
            brand = BrandORM(name=item.brand, slug=item.brand_slug)
            session.add(brand)
            session.flush()
            stats["brand_created"] += 1
        return brand

    def _upsert_item(
        self,
        session: Session,
        item: BurgerItem,
        brand: BrandORM,
        category: CategoryORM,
        stats: Counter,
    ) -> None:
        now = utcnow()
        slug = slugify(item.name)

        # 기존 상품은 이름 → slug 순으로 찾음 (수기로 넣은 상품의 slug 규칙이 다를 수 있음)
        product = session.scalar(
            select(ProductORM).where(ProductORM.brand_id == brand.id, ProductORM.name == item.name)
        ) or session.scalar(
            select(ProductORM).where(ProductORM.brand_id == brand.id, ProductORM.slug == slug)
        )

        if product is None:
            product = ProductORM(
                brand_id=brand.id,
                category_id=category.id,
                name=item.name,
                slug=slug,
                description=item.description,
                image_url=item.image_url,
                is_limited=item.is_limited,
                status="ACTIVE",
            )
            session.add(product)
            session.flush()
            stats["product_created"] += 1
        else:
            if item.description:
                product.description = item.description
            # 009·010 마이그레이션에서 넣은 자체 이미지 경로는 덮어쓰지 않음
            if item.image_url and not product.image_url:
                product.image_url = item.image_url
            product.is_limited = item.is_limited
            product.status = "ACTIVE"
            product.updated_at = now
            stats["product_updated"] += 1

        single = self._get_or_create_variant(session, product, "SINGLE", "단품", True, stats)
        self._update_price(session, single, item.price, now, stats)
        self._upsert_nutrition(session, single, item.nutrition, now, stats)

        if item.set_price is not None:
            set_variant = self._get_or_create_variant(session, product, "SET", "세트", False, stats)
            self._update_price(session, set_variant, item.set_price, now, stats)

    def _get_or_create_variant(
        self,
        session: Session,
        product: ProductORM,
        variant_type: str,
        name: str,
        is_default: bool,
        stats: Counter,
    ) -> ProductVariantORM:
        variant = session.scalar(
            select(ProductVariantORM)
            .where(
                ProductVariantORM.product_id == product.id,
                ProductVariantORM.variant_type == variant_type,
            )
            .order_by(ProductVariantORM.is_default.desc(), ProductVariantORM.id)
        )
        if variant is None:
            has_default = session.scalar(
                select(ProductVariantORM.id).where(
                    ProductVariantORM.product_id == product.id, ProductVariantORM.is_default
                )
            )
            variant = ProductVariantORM(
                product_id=product.id,
                name=name,
                variant_type=variant_type,
                is_default=is_default and has_default is None,
                is_active=True,
            )
            session.add(variant)
            session.flush()
            stats["variant_created"] += 1
        return variant

    def _update_price(
        self,
        session: Session,
        variant: ProductVariantORM,
        price: Optional[int],
        now,
        stats: Counter,
    ) -> None:
        if price is None:
            return
        current = session.scalar(
            select(ProductPriceORM).where(
                ProductPriceORM.product_variant_id == variant.id,
                ProductPriceORM.channel == PRICE_CHANNEL,
                ProductPriceORM.ended_at.is_(None),
            )
        )
        if current is not None:
            if current.price == price:
                return
            # uq_variant_active_price 때문에 기존 행을 먼저 닫아야 새 행을 넣을 수 있음
            current.ended_at = now
            session.flush()
            stats["price_changed"] += 1
        else:
            stats["price_created"] += 1
        session.add(
            ProductPriceORM(
                product_variant_id=variant.id,
                price=price,
                channel=PRICE_CHANNEL,
                started_at=now,
                created_at=now,
            )
        )

    def _upsert_nutrition(
        self,
        session: Session,
        variant: ProductVariantORM,
        nutrition: NutritionInfo,
        now,
        stats: Counter,
    ) -> None:
        if nutrition.calories_kcal is None:  # calories_kcal은 NOT NULL
            return
        row = session.scalar(select(NutritionORM).where(NutritionORM.product_variant_id == variant.id))
        values = nutrition.model_dump()
        if row is None:
            session.add(NutritionORM(product_variant_id=variant.id, created_at=now, updated_at=now, **values))
            stats["nutrition_created"] += 1
        else:
            for key, value in values.items():
                if value is not None:
                    setattr(row, key, value)
            row.updated_at = now
            stats["nutrition_updated"] += 1

    # ------------------------------------------------------------------ 조회

    def get_burgers(
        self, brand: Optional[str] = None, keyword: Optional[str] = None
    ) -> List[BurgerItem]:
        """저장된 상품을 브랜드(이름 또는 slug)·메뉴명 키워드로 조회 (현재 매장 가격 기준)"""
        with self.SessionLocal() as session:
            stmt = (
                select(ProductORM, BrandORM)
                .join(BrandORM, ProductORM.brand_id == BrandORM.id)
                .order_by(BrandORM.name, ProductORM.name)
            )
            if brand:
                stmt = stmt.where((BrandORM.name == brand) | (BrandORM.slug == brand))
            if keyword:
                stmt = stmt.where(ProductORM.name.contains(keyword))

            results = []
            for product, brand_row in session.execute(stmt).all():
                prices = {}
                nutrition = NutritionInfo()
                variants = session.scalars(
                    select(ProductVariantORM).where(ProductVariantORM.product_id == product.id)
                ).all()
                for variant in variants:
                    price = session.scalar(
                        select(ProductPriceORM.price).where(
                            ProductPriceORM.product_variant_id == variant.id,
                            ProductPriceORM.channel == PRICE_CHANNEL,
                            ProductPriceORM.ended_at.is_(None),
                        )
                    )
                    prices.setdefault(variant.variant_type, price)
                    if variant.variant_type == "SINGLE":
                        row = session.scalar(
                            select(NutritionORM).where(NutritionORM.product_variant_id == variant.id)
                        )
                        if row is not None:
                            nutrition = NutritionInfo(
                                **{
                                    f: (float(v) if v is not None and f != "basis_note" else v)
                                    for f in NUTRITION_FIELDS
                                    for v in [getattr(row, f)]
                                }
                            )
                results.append(
                    BurgerItem(
                        brand=brand_row.name,
                        brand_slug=brand_row.slug,
                        name=product.name,
                        price=prices.get("SINGLE"),
                        set_price=prices.get("SET"),
                        description=product.description,
                        image_url=product.image_url,
                        is_limited=product.is_limited,
                        nutrition=nutrition,
                        crawled_at=product.updated_at or utcnow(),
                    )
                )
            return results
