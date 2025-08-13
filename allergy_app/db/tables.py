from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum as PyEnum
from sqlalchemy import JSON, Column, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, Index
from sqlalchemy.orm import relationship, declarative_base


Base = declarative_base()


class RiskLevel(PyEnum):
    SAFE = "safe"
    WARNING = "warning"
    DANGER = "danger"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(320), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    allergens = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    scans = relationship("ScanHistory", back_populates="user", lazy="raise")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    barcode = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(512), nullable=True)
    brand = Column(String(512), nullable=True)
    ingredients_text = Column(Text, nullable=True)
    allergens_found = Column(JSON, nullable=False, default=list)
    image_url = Column(String(1024), nullable=True)
    last_fetched = Column(DateTime(timezone=True), nullable=True)

    scans = relationship("ScanHistory", back_populates="product", lazy="raise")

    __table_args__ = (
        Index("ix_products_barcode_unique", "barcode", unique=True),
    )


class ScanHistory(Base):
    __tablename__ = "scan_history"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    risk_level = Column(SAEnum(RiskLevel, native_enum=False), nullable=False)
    matched_allergens = Column(JSON, nullable=False, default=list)
    scanned_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="scans", lazy="raise")
    product = relationship("Product", back_populates="scans", lazy="raise")


class ApiCache(Base):
    __tablename__ = "api_cache"

    id = Column(Integer, primary_key=True)
    key = Column(String(512), unique=True, index=True, nullable=False)
    data = Column(Text, nullable=False)
    fetched_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

