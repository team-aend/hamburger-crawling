from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# SQLite는 BIGINT 자동증가를 지원하지 않으므로 로컬 테스트용으로 INTEGER로 대체
BigIntId = BigInteger().with_variant(Integer(), "sqlite")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NutritionInfo(BaseModel):
    """햄버거 영양성분 데이터 스키마 (DB nutrition 테이블과 동일한 항목)"""

    serving_size_g: Optional[float] = Field(None, description="1회 제공량(g)")
    calories_kcal: Optional[float] = Field(None, description="열량(kcal)")
    protein_g: Optional[float] = Field(None, description="단백질(g)")
    carbohydrate_g: Optional[float] = Field(None, description="탄수화물(g)")
    sugar_g: Optional[float] = Field(None, description="당류(g)")
    fat_g: Optional[float] = Field(None, description="지방(g)")
    saturated_fat_g: Optional[float] = Field(None, description="포화지방(g)")
    sodium_mg: Optional[float] = Field(None, description="나트륨(mg)")
    basis_note: Optional[str] = Field(None, description="기준 메모 (예: 단품 기준)")


class BurgerItem(BaseModel):
    """크롤링된 햄버거 정보 통합 모델 (Pydantic)"""

    brand: str = Field(..., description="브랜드명 (예: 맥도날드, 버거킹, 롯데리아)")
    brand_slug: str = Field(..., description="브랜드 slug (예: mcdonalds, burgerking)")
    name: str = Field(..., description="메뉴명 (한국어)")
    name_en: Optional[str] = Field(None, description="메뉴명 (영어)")
    source_id: Optional[str] = Field(None, description="브랜드 사이트의 메뉴 ID")
    category: str = Field(default="버거", description="카테고리")
    price: Optional[int] = Field(None, description="단품 매장 가격(원)")
    set_price: Optional[int] = Field(None, description="세트 매장 가격(원)")
    description: Optional[str] = Field(None, description="메뉴 설명")
    image_url: Optional[str] = Field(None, description="메뉴 이미지 URL")
    detail_url: Optional[str] = Field(None, description="상세 페이지 URL")
    is_limited: bool = Field(default=False, description="한정 메뉴 여부")
    nutrition: NutritionInfo = Field(default_factory=NutritionInfo, description="단품 영양성분")
    crawled_at: datetime = Field(default_factory=utcnow, description="수집 일시(UTC)")

    def to_flat_dict(self) -> dict:
        """CSV 저장을 위해 중첩된 영양성분 필드를 평탄화한 딕셔너리 반환"""
        data = self.model_dump(exclude={"nutrition"})
        nutrition_data = self.nutrition.model_dump()
        return {**data, **nutrition_data}


# ---------------------------------------------------------------------------
# 버거픽 DB(Supabase PostgreSQL) 상품 테이블 매핑
# 운영 DB는 테이블이 이미 있으므로 create_all은 로컬 SQLite 테스트에서만 사용합니다.
# updated_at 트리거가 없어 UPDATE 시 직접 갱신해야 합니다.
# ---------------------------------------------------------------------------


class TimestampMixin:
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class CategoryORM(TimestampMixin, Base):
    __tablename__ = "categories"

    id = Column(BigIntId, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    slug = Column(String(50), nullable=False, unique=True)


class BrandORM(TimestampMixin, Base):
    __tablename__ = "brands"

    id = Column(BigIntId, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), nullable=False, unique=True)
    logo_url = Column(Text)
    homepage_url = Column(Text)
    is_active = Column(Boolean, nullable=False, default=True)


class ProductORM(TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("brand_id", "slug"),)

    id = Column(BigIntId, primary_key=True, autoincrement=True)
    brand_id = Column(BigInteger, ForeignKey("brands.id"), nullable=False)
    category_id = Column(BigInteger, ForeignKey("categories.id"), nullable=False)
    name = Column(String(150), nullable=False)
    slug = Column(String(200), nullable=False)
    description = Column(Text)
    image_url = Column(Text)
    status = Column(String(20), nullable=False, default="ACTIVE")
    is_limited = Column(Boolean, nullable=False, default=False)
    released_at = Column(Date)
    discontinued_at = Column(Date)


class ProductVariantORM(TimestampMixin, Base):
    __tablename__ = "product_variants"
    __table_args__ = (
        Index(
            "uq_product_default_variant",
            "product_id",
            unique=True,
            postgresql_where=text("is_default"),
            sqlite_where=text("is_default"),
        ),
    )

    id = Column(BigIntId, primary_key=True, autoincrement=True)
    product_id = Column(BigInteger, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    variant_type = Column(String(30), nullable=False)  # SINGLE / SET / LARGE_SET
    size_code = Column(String(30))
    is_default = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)


class ProductPriceORM(Base):
    """가격 이력. 변경 시 기존 행의 ended_at을 채우고 새 행을 추가합니다."""

    __tablename__ = "product_prices"
    __table_args__ = (
        Index(
            "uq_variant_active_price",
            "product_variant_id",
            "channel",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
            sqlite_where=text("ended_at IS NULL"),
        ),
    )

    id = Column(BigIntId, primary_key=True, autoincrement=True)
    product_variant_id = Column(
        BigInteger, ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=False
    )
    price = Column(Integer, nullable=False)
    channel = Column(String(30), nullable=False)  # STORE / DELIVERY
    started_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    ended_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class NutritionORM(TimestampMixin, Base):
    __tablename__ = "nutrition"

    id = Column(BigIntId, primary_key=True, autoincrement=True)
    product_variant_id = Column(
        BigInteger,
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    serving_size_g = Column(Numeric(6, 1))
    calories_kcal = Column(Numeric(6, 1), nullable=False)
    protein_g = Column(Numeric(5, 1))
    carbohydrate_g = Column(Numeric(5, 1))
    sugar_g = Column(Numeric(5, 1))
    fat_g = Column(Numeric(5, 1))
    saturated_fat_g = Column(Numeric(5, 1))
    sodium_mg = Column(Numeric(6, 1))
    basis_note = Column(String(150))
