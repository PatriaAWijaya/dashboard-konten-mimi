"""Titik masuk aplikasi FastAPI."""

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.routers import admin, auth, billing, content, dev, fase2, onboarding, organizations

settings = get_settings()

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Dashboard Konten AI — API",
    description=(
        "Backend: auth, multi-tenant, membership, pembayaran manual, admin "
        "(fase 0); konten + scoring + rekomendasi (fase 1); "
        "koneksi OAuth TikTok/Instagram, sinkronisasi, planner, undangan, "
        "ringkasan mingguan, notifikasi (fase 2); onboarding (fase 3)."
    ),
    version="0.3.0",
)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Terlalu banyak percobaan. Silakan coba lagi beberapa saat."},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else "Terjadi kesalahan."
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    if errors:
        first = errors[0]
        loc = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        msg = first.get("msg", "")
        detail = f"Data tidak valid pada '{loc}': {msg}." if loc else f"Data tidak valid: {msg}."
    else:
        detail = "Data yang dikirim tidak valid."
    return JSONResponse(status_code=422, content={"detail": detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Catat traceback di log server; klien tetap hanya menerima pesan generik.
    logger.exception("Unhandled exception pada %s %s", request.method, request.url.path)
    detail = f"Terjadi kesalahan pada server: {type(exc).__name__}: {exc}"
    return JSONResponse(status_code=500, content={"detail": detail})


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Header keamanan standar pada setiap respons."""
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


_cors_origins = (
    ["*"]
    if settings.CORS_ORIGINS.strip() == "*"
    else [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


API_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(organizations.router, prefix=API_PREFIX)
app.include_router(billing.router, prefix=API_PREFIX)
app.include_router(content.router, prefix=API_PREFIX)
app.include_router(fase2.router, prefix=API_PREFIX)
app.include_router(onboarding.router, prefix=API_PREFIX)
app.include_router(admin.router, prefix=API_PREFIX)

if settings.is_dev:
    app.include_router(dev.router, prefix=API_PREFIX)
