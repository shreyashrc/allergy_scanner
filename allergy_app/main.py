from __future__ import annotations

import base64
import io
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Path, UploadFile, File
from starlette.middleware.cors import CORSMiddleware
from PIL import Image
from pyzbar.pyzbar import decode
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from allergy_app.core.config import CORS_ALLOW_ORIGINS, STALE_DAYS
from allergy_app.core.logging import configure_logging, RequestIdFilter
from allergy_app.db.session import engine, AsyncSessionMaker
from allergy_app.db.tables import Base, User, Product, ScanHistory, RiskLevel
from allergy_app.security.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user,
)
from allergy_app.services.off_client import fetch_product
from allergy_app.utils.allergens import detect_allergens, compute_risk_level


logger = configure_logging()

app = FastAPI(title="Allergy Scanner API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*" if CORS_ALLOW_ORIGINS == "*" else origin.strip() for origin in CORS_ALLOW_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id(request, call_next):
    import uuid

    rid = str(uuid.uuid4())
    RequestIdFilter.request_id_var.set(rid)
    request.state.request_id = rid
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    allergens: List[str] = Field(default_factory=list)

    @field_validator("allergens")
    @classmethod
    def lower_allergens(cls, v: List[str]) -> List[str]:
        return [a.lower().strip() for a in v]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProfileResponse(BaseModel):
    email: EmailStr
    allergens: List[str]


class ScanRequest(BaseModel):
    barcode: Optional[str] = None
    image: Optional[str] = None

    @field_validator("barcode")
    @classmethod
    def strip_barcode(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v


class ScanResponse(BaseModel):
    product_name: Optional[str]
    brand: Optional[str]
    risk_level: RiskLevel
    matched_allergens: List[str]
    user_allergens: List[str]
    ingredients: Optional[str]
    image_url: Optional[str]
    message: str


class ProductResponse(BaseModel):
    name: Optional[str]
    brand: Optional[str]
    ingredients: Optional[str]
    allergens_found: List[str]


class ScanHistoryEntry(BaseModel):
    product_name: Optional[str]
    brand: Optional[str]
    barcode: str
    risk_level: RiskLevel
    date_scanned: datetime


def decode_barcode_from_image(image_b64: str) -> Optional[str]:
    try:
        image_bytes = base64.b64decode(image_b64)
    except Exception:
        return None
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            barcodes = decode(img.convert("RGB"))
            if not barcodes:
                return None
            return barcodes[0].data.decode("utf-8")
    except Exception:
        return None


async def get_db():
    async with AsyncSessionMaker() as session:
        yield session


@app.post("/register", response_model=TokenResponse)
async def register_user(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = get_password_hash(payload.password)
    user = User(email=str(payload.email), hashed_password=hashed, allergens=[a.lower() for a in payload.allergens])
    db.add(user)
    await db.commit()
    token = create_access_token(subject=user.email)
    return TokenResponse(access_token=token)


@app.post("/login", response_model=TokenResponse)
async def login_user(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = await db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(subject=user.email)
    return TokenResponse(access_token=token)


@app.get("/profile", response_model=ProfileResponse)
async def get_profile(current_user: User = Depends(get_current_user)) -> ProfileResponse:
    return ProfileResponse(email=current_user.email, allergens=current_user.allergens or [])


async def upsert_product_from_off(barcode: str, db: AsyncSession) -> Product:
    try:
        data = await fetch_product(barcode, db=db)
        if data.get("status") != 1:
            raise HTTPException(status_code=404, detail="Product not found")
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Failed to fetch product data: {str(e)}")
    p = data.get("product", {})
    name = p.get("product_name") or p.get("product_name_en") or p.get("generic_name")
    brand = p.get("brands")
    ingredients_text = p.get("ingredients_text") or p.get("ingredients_text_en")
    image_url = p.get("image_url")

    direct, may_c, confidences = detect_allergens(ingredients_text)
    allergens_found = sorted(direct)

    existing = await db.scalar(select(Product).where(Product.barcode == barcode))
    now = datetime.now(timezone.utc)
    if existing:
        existing.name = name
        existing.brand = brand
        existing.ingredients_text = ingredients_text
        existing.allergens_found = allergens_found
        existing.image_url = image_url
        existing.last_fetched = now
        await db.flush()
        return existing
    new_product = Product(
        barcode=barcode,
        name=name,
        brand=brand,
        ingredients_text=ingredients_text,
        allergens_found=allergens_found,
        image_url=image_url,
        last_fetched=now,
    )
    db.add(new_product)
    await db.flush()
    return new_product


async def get_or_refresh_product(barcode: str, db: AsyncSession) -> Product:
    product = await db.scalar(select(Product).where(Product.barcode == barcode))
    now = datetime.now(timezone.utc)
    if product and product.last_fetched:
        # Ensure both datetimes have the same timezone awareness
        last_fetched = product.last_fetched
        if last_fetched.tzinfo is None:
            last_fetched = last_fetched.replace(tzinfo=timezone.utc)
        if (now - last_fetched) <= timedelta(days=STALE_DAYS):
            return product
    return await upsert_product_from_off(barcode, db)


@app.post("/scan", response_model=ScanResponse)
async def scan_product(payload: ScanRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> ScanResponse:
    barcode: Optional[str] = payload.barcode
    if not barcode:
        if not payload.image:
            raise HTTPException(status_code=400, detail="Provide either 'barcode' or 'image'")
        # Validate base64
        try:
            base64.b64decode(payload.image, validate=True)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 image data")
        decoded = decode_barcode_from_image(payload.image)
        if not decoded:
            raise HTTPException(status_code=400, detail="No barcode detected in image")
        barcode = decoded

    product = await get_or_refresh_product(barcode, db)
    direct, may_c, confidences = detect_allergens(product.ingredients_text)
    risk_level, matched_for_user = compute_risk_level(current_user.allergens or [], direct, may_c, confidences)

    scan = ScanHistory(
        user_id=int(current_user.id),
        product_id=int(product.id),
        risk_level=risk_level,
        matched_allergens=matched_for_user,
        scanned_at=datetime.now(timezone.utc),
    )
    db.add(scan)
    await db.commit()

    message = {
        RiskLevel.DANGER: f"WARNING: Contains {', '.join(matched_for_user)}",
        RiskLevel.WARNING: f"CAUTION: May contain {', '.join(matched_for_user)}",
        RiskLevel.SAFE: "SAFE: No matching allergens detected",
    }[risk_level]

    return ScanResponse(
        product_name=product.name,
        brand=product.brand,
        risk_level=risk_level,
        matched_allergens=matched_for_user,
        user_allergens=current_user.allergens or [],
        ingredients=product.ingredients_text,
        image_url=product.image_url,
        message=message,
    )


@app.post("/scan/test-image")
async def scan_test_image(file: UploadFile = File(...)) -> Dict[str, Any]:
    try:
        contents = await file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to read uploaded file")

    b64 = base64.b64encode(contents).decode("ascii")
    decoded = decode_barcode_from_image(b64)
    if not decoded:
        raise HTTPException(status_code=400, detail="No barcode detected in uploaded image")
    return {"barcode": decoded, "filename": file.filename}


@app.get("/scan-history", response_model=List[ScanHistoryEntry])
async def get_scan_history(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> List[ScanHistoryEntry]:
    from sqlalchemy import select
    stmt = (
        select(ScanHistory, Product)
        .join(Product, Product.id == ScanHistory.product_id)
        .where(ScanHistory.user_id == current_user.id)
        .order_by(ScanHistory.scanned_at.desc())
        .limit(20)
    )
    rows = (await db.execute(stmt)).all()
    results: List[ScanHistoryEntry] = []
    for scan, product in rows:
        results.append(
            ScanHistoryEntry(
                product_name=product.name,
                brand=product.brand,
                barcode=product.barcode,
                risk_level=scan.risk_level,
                date_scanned=scan.scanned_at,
            )
        )
    return results


@app.get("/product/{barcode}", response_model=ProductResponse)
async def get_product(barcode: str = Path(..., min_length=4, max_length=64), db: AsyncSession = Depends(get_db)) -> ProductResponse:
    product = await get_or_refresh_product(barcode, db)
    return ProductResponse(
        name=product.name,
        brand=product.brand,
        ingredients=product.ingredients_text,
        allergens_found=product.allergens_found or [],
    )


@app.get("/health")
async def healthcheck() -> Dict[str, Any]:
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.on_event("startup")
async def on_startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionMaker() as session:
        count = await session.scalar(select(func.count(User.id)))
        if count == 0:
            test_email = "test@example.com"
            test_password = "test123"
            test_allergens = ["nuts", "dairy"]
            user = User(
                email=test_email,
                hashed_password=get_password_hash(test_password),
                allergens=test_allergens,
                created_at=datetime.now(timezone.utc),
            )
            session.add(user)
            await session.commit()

