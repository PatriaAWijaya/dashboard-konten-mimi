"""Konfigurasi pytest: siapkan test DB, jalankan migrasi, sediakan fixtures."""

import asyncio
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

API_DIR = os.path.dirname(os.path.abspath(__file__)) + "/.."


def _derive_test_url() -> str:
    url = os.getenv("TEST_DATABASE_URL")
    if url:
        return url
    base = os.getenv("DATABASE_URL")
    if not base:
        raise RuntimeError(
            "Set TEST_DATABASE_URL atau DATABASE_URL untuk menjalankan tes."
        )
    parts = urlparse(base)
    dbname = (parts.path or "/dashboard_konten").lstrip("/") or "dashboard_konten"
    new_path = f"/{dbname}_test"
    return urlunparse(parts._replace(path=new_path))


def _strip_driver(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg2://", "postgresql://"
    )


def _ensure_database_exists(url: str) -> None:
    """Buat database tes bila belum ada (butuh hak CREATEDB pada role)."""
    import asyncpg

    plain = _strip_driver(url)

    async def _run() -> None:
        try:
            conn = await asyncpg.connect(plain)
            await conn.close()
            return
        except Exception as exc:  # noqa: BLE001
            if "does not exist" not in str(exc):
                raise
        parts = urlparse(plain)
        dbname = parts.path.lstrip("/")
        maint = urlunparse(parts._replace(path="/postgres"))
        conn = await asyncpg.connect(maint)
        try:
            await conn.execute(f'CREATE DATABASE "{dbname}"')
        finally:
            await conn.close()

    asyncio.run(_run())


TEST_URL = _derive_test_url()

# Set env SEBELUM import modul app (settings dibaca saat import pertama).
os.environ["DATABASE_URL"] = TEST_URL
os.environ["MIGRATION_DATABASE_URL"] = TEST_URL
os.environ["ENV"] = "dev"
os.environ["STORAGE_DIR"] = tempfile.mkdtemp(prefix="dka-test-storage-")

_ensure_database_exists(TEST_URL)


def _run_alembic(target: str) -> None:
    cfg = Config(os.path.join(API_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(API_DIR, "alembic"))
    command.upgrade(cfg, target) if target == "head" else command.downgrade(cfg, target)


# Reset skema lalu migrasi penuh — kondisi awal yang deterministik.
_run_alembic("base")
_run_alembic("head")

# Kontrak Worker Data (app.models.content, app.services.scoring/csv_import/
# suitability) kini sudah tersedia sebagai modul asli; tidak ada lagi modul
# palsu. Helper seeding untuk tes ada di tests/kontrak_palsu.py.

from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models.billing import MembershipPlan  # noqa: E402
from app.models.organization import Organization, OrganizationMember  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.email import clear_dev_outbox  # noqa: E402


@pytest_asyncio.fixture(scope="session")
async def engine():
    from app.db.session import dispose_engine, get_engine

    eng = get_engine()
    yield eng
    await dispose_engine()


@pytest_asyncio.fixture(scope="session")
async def session_factory(engine):
    """Factory sesi untuk tes: engine NullPool khusus dengan server_settings.

    Setiap checkout membuka koneksi fisik BARU sehingga
    ``app.is_superadmin='on'`` selalu diterapkan di awal sesi — kebal terhadap
    commit di tengah tes (SQLAlchemy 2.0 me-recycle koneksi pool) maupun
    RESET GUC oleh get_db di request HTTP lain. Engine aplikasi (pooled)
    tidak diubah.
    """
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    test_eng = create_async_engine(
        TEST_URL,
        poolclass=NullPool,
        connect_args={"server_settings": {"app.is_superadmin": "on"}},
    )
    yield async_sessionmaker(test_eng, class_=AsyncSession, expire_on_commit=False)
    await test_eng.dispose()


async def _set_ctx(session: AsyncSession, *, user_id="", is_superadmin="off", tenant_id=""):
    await session.execute(text("SELECT set_config('app.user_id', :v, false)"), {"v": user_id})
    await session.execute(text("SELECT set_config('app.is_superadmin', :v, false)"), {"v": is_superadmin})
    await session.execute(text("SELECT set_config('app.tenant_id', :v, false)"), {"v": tenant_id})


@pytest_asyncio.fixture()
async def db_super(session_factory):
    """Sesi dengan hak superadmin (bypass RLS) untuk setup data tes."""
    async with session_factory() as session:
        await _set_ctx(session, is_superadmin="on")
        yield session
        await session.rollback()


@pytest_asyncio.fixture()
async def client():
    clear_dev_outbox()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture(scope="session")
async def rls_engine(session_factory):
    """Engine sebagai role non-superuser untuk tes isolasi RLS.

    Bila koneksi tes adalah superuser, buat role terbatas khusus tes.
    """
    from app.db.session import get_engine

    eng = get_engine()
    async with eng.connect() as conn:
        is_super = await conn.scalar(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user"))
        dbname = await conn.scalar(text("SELECT current_database()"))

    if is_super:
        async with eng.connect() as conn:
            # Idempoten: buat hanya bila belum ada (re-run aman).
            await conn.execute(
                text(
                    "DO $$ BEGIN "
                    "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rls_tester') THEN "
                    "CREATE ROLE rls_tester WITH LOGIN PASSWORD 'rls_tester_pw'; "
                    "END IF; END $$"
                )
            )
            await conn.execute(text("ALTER ROLE rls_tester WITH LOGIN PASSWORD 'rls_tester_pw'"))
            await conn.execute(text(f'GRANT CONNECT ON DATABASE "{dbname}" TO rls_tester'))
            await conn.execute(text("GRANT USAGE ON SCHEMA public TO rls_tester"))
            await conn.execute(
                text("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO rls_tester")
            )
            await conn.execute(text("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO rls_tester"))
            await conn.commit()

        parts = urlparse(_strip_driver(TEST_URL))
        netloc = f"rls_tester:rls_tester_pw@{parts.hostname}"
        if parts.port:
            netloc += f":{parts.port}"
        rls_url = urlunparse(("postgresql+asyncpg", netloc, parts.path, "", "", ""))
        rls_eng = create_async_engine(rls_url, pool_pre_ping=True)
    else:
        rls_eng = eng  # sudah non-superuser: RLS berlaku langsung

    yield rls_eng

    if rls_eng is not eng:
        await rls_eng.dispose()


@pytest_asyncio.fixture()
async def rls_session_factory(rls_engine):
    return async_sessionmaker(rls_engine, class_=AsyncSession, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utcnow():
    return datetime.now(timezone.utc)


async def create_user_direct(
    session: AsyncSession,
    *,
    name="Test User",
    email=None,
    password="Password123",
    is_superadmin=False,
    email_verified=True,
    is_active=True,
) -> User:
    email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
    user = User(
        name=name,
        email=email.lower(),
        password_hash=hash_password(password),
        is_superadmin=is_superadmin,
        email_verified=email_verified,
        is_active=is_active,
    )
    session.add(user)
    await session.flush()
    await session.commit()
    # Kembalikan konteks superadmin: commit melepas koneksi ke pool (SQLAlchemy 2.0),
    # sehingga checkout berikutnya bisa mendapat koneksi dengan GUC basi.
    await _set_ctx(session, is_superadmin="on")
    return user


async def create_org_direct(session: AsyncSession, owner: User, name=None) -> Organization:
    from app.services.membership import ensure_membership

    name = name or f"Org {uuid.uuid4().hex[:6]}"
    org_id = uuid.uuid4()
    await _set_ctx(session, user_id=str(owner.id), is_superadmin="on", tenant_id=str(org_id))
    org = Organization(id=org_id, name=name)
    session.add(org)
    await session.flush()
    session.add(OrganizationMember(organization_id=org.id, user_id=owner.id, role="owner"))
    await ensure_membership(session, org.id)
    await session.commit()
    await _set_ctx(session, is_superadmin="on")  # kembalikan ke konteks superadmin
    return org


async def create_plan_direct(session: AsyncSession, **kwargs) -> MembershipPlan:
    defaults = dict(name=f"Paket {uuid.uuid4().hex[:6]}", price=990000, period_months=12, seats=5, features=["a"])
    defaults.update(kwargs)
    plan = MembershipPlan(**defaults)
    session.add(plan)
    await session.flush()
    await session.commit()
    # Kembalikan konteks superadmin (commit melepas koneksi ke pool).
    await _set_ctx(session, is_superadmin="on")
    return plan


def auth_headers(token: str, org_id=None) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    if org_id:
        headers["X-Organization-Id"] = str(org_id)
    return headers


@pytest.fixture(autouse=True)
def _reset_rate_limiter_antar_tes():
    """Reset bucket rate-limit (slowapi, in-memory & global per proses) sebelum
    tiap tes.

    Tanpa ini, puluhan login/register dari tes-tes sebelumnya menumpuk pada
    kunci IP yang sama ("testclient") sehingga tes yang jalan belakangan bisa
    kena 429 secara acak tergantung urutan eksekusi (flaky).
    """
    try:
        from app.core.rate_limit import limiter

        storage = getattr(limiter, "_storage", None)
        reset = getattr(storage, "reset", None)
        if callable(reset):
            reset()
    except Exception:  # noqa: BLE001 — rate limit opsional; jangan gagalkan tes
        pass
    yield
