"""Lapisan integrasi defensif ke backend Fase 2.

Backend (apps/api) sedang dibangun paralel oleh agen lain, sehingga SEMUA
import `app.*` di sini dilakukan malas (lazy, di dalam fungsi) dan dibungkus.
Bila ada bagian kontrak yang belum tersedia, worker gagal dengan pesan yang
jelas, bukan ImportError/AttributeError misterius.

Kontrak backend yang dipakai (lihat task Fase 2):
- app.services.sync_service.sync_account(db, account)
    -> dict {"contents_baru": int, "contents_diupdate": int}
- app.services.summaries.get_or_generate_summary(
      db, brand, org_id, period_start: date, period_end: date, llm) -> Summary
- app.services.notifications.notify(db, user, jenis: str, payload: dict)
- app.services.llm.get_llm_provider() -> LLMProvider
- app.db.session.get_session() -> AsyncSession
  (fallback: get_session_factory()() — pola yang ada di Fase 1)
- Model: ConnectedAccount(status, last_sync_at, brand_id, organization_id),
  Brand, Organization, OrganizationMember, Membership, User.
"""
from __future__ import annotations

import importlib
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator

PESAN_BACKEND_BELUM_SIAP = (
    "modul backend Fase 2 belum tersedia — jalankan setelah backend selesai"
)


class BackendNotReadyError(RuntimeError):
    """Backend Fase 2 (service/model yang dikontrak) belum tersedia."""


def _need(nama_modul: str, nama_objek: str) -> Any:
    """Import malas satu objek; gagal dengan BackendNotReadyError yang jelas."""
    try:
        modul = importlib.import_module(nama_modul)
    except ImportError as exc:
        raise BackendNotReadyError(
            f"{PESAN_BACKEND_BELUM_SIAP} (tidak bisa import {nama_modul}: {exc})"
        ) from exc
    try:
        return getattr(modul, nama_objek)
    except AttributeError as exc:
        raise BackendNotReadyError(
            f"{PESAN_BACKEND_BELUM_SIAP} ({nama_modul} belum mendefinisikan {nama_objek})"
        ) from exc


class RealBackend:
    """Implementasi akses backend memakai modul app.* asli (Fase 2).

    Antarmuka kelas ini (nama method + signature) adalah yang dipakai jobs.py;
    StubBackend di tests/test_worker_jobs.py mengimplementasikan antarmuka
    yang sama dengan fungsi palsu bernama sama seperti kontrak.
    """

    # ------------------------------------------------------------------ sesi
    @asynccontextmanager
    async def open_session(self) -> AsyncIterator[Any]:
        """Buka AsyncSession baru.

        Kontrak meminta app.db.session.get_session(); bila belum ada, pakai
        get_session_factory()() yang sudah ada sejak Fase 1.
        """
        try:
            get_session = _need("app.db.session", "get_session")
        except BackendNotReadyError:
            factory = _need("app.db.session", "get_session_factory")
            async with factory()() as db:  # AsyncSession
                yield db
            return
        async with get_session() as db:  # AsyncSession (kontrak)
            yield db

    # --------------------------------------------------------------- query
    async def list_active_accounts(self, db: Any) -> list:
        """Semua ConnectedAccount dengan status='aktif'."""
        ConnectedAccount = _need("app.models", "ConnectedAccount")
        select = _need("sqlalchemy", "select")
        hasil = await db.execute(
            select(ConnectedAccount).where(ConnectedAccount.status == "aktif")
        )
        return list(hasil.scalars().all())

    async def list_brands_with_active_membership(self, db: Any) -> list:
        """Daftar (brand, organization) yang membership org-nya aktif."""
        Brand = _need("app.models", "Brand")
        Organization = _need("app.models", "Organization")
        Membership = _need("app.models", "Membership")
        try:
            status_aktif = _need("app.models.billing", "MembershipStatus").ACTIVE
        except BackendNotReadyError:
            status_aktif = "active"  # nilai literal dari kontrak Fase 1
        select = _need("sqlalchemy", "select")
        stmt = (
            select(Brand, Organization)
            .join(Organization, Organization.id == Brand.organization_id)
            .join(Membership, Membership.organization_id == Organization.id)
            .where(Membership.status == status_aktif)
        )
        rows = await db.execute(stmt)
        return [(brand, org) for brand, org in rows.all()]

    async def list_org_members(self, db: Any, org_id: Any) -> list:
        """Semua User anggota sebuah organisasi."""
        User = _need("app.models", "User")
        OrganizationMember = _need("app.models", "OrganizationMember")
        select = _need("sqlalchemy", "select")
        stmt = (
            select(User)
            .join(OrganizationMember, OrganizationMember.user_id == User.id)
            .where(OrganizationMember.organization_id == org_id)
        )
        hasil = await db.execute(stmt)
        return list(hasil.scalars().all())

    async def list_memberships_expiring(self, db: Any, tanggal_target: set) -> list:
        """Daftar (membership, organization) aktif yang kedaluwarsa pada tanggal_target.

        tanggal_target: set[date] (zona Asia/Jakarta). Bandingkan dengan
        tanggal ends_at dalam zona yang sama.
        """
        Membership = _need("app.models", "Membership")
        Organization = _need("app.models", "Organization")
        try:
            status_aktif = _need("app.models.billing", "MembershipStatus").ACTIVE
        except BackendNotReadyError:
            status_aktif = "active"  # nilai literal dari kontrak Fase 1
        select = _need("sqlalchemy", "select")
        func = _need("sqlalchemy", "func")
        stmt = (
            select(Membership, Organization)
            .join(Organization, Organization.id == Membership.organization_id)
            .where(
                Membership.status == status_aktif,
                Membership.ends_at.isnot(None),
                func.date(func.timezone("Asia/Jakarta", Membership.ends_at)).in_(
                    list(tanggal_target)
                ),
            )
        )
        rows = await db.execute(stmt)
        return [(m, o) for m, o in rows.all()]

    # ------------------------------------------------- guard & pencatatan
    def should_sync_account(self, account: Any, interval_hours: int) -> bool:
        """True bila akun belum pernah/disync dalam `interval_hours` terakhir.

        Guard idempotensi: bila scheduler restart, akun yang baru saja
        tersinkronisasi tidak disync ulang.
        """
        last = getattr(account, "last_sync_at", None)
        if last is None:
            return True
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - last >= timedelta(hours=interval_hours)

    async def mark_account_synced(self, db: Any, account: Any) -> None:
        """Catat last_sync_at setelah sync sukses."""
        account.last_sync_at = datetime.now(timezone.utc)
        await db.commit()

    def member_wants_summary(self, user: Any) -> bool:
        """Preferensi notifikasi ringkasan mingguan.

        Asumsi: backend Fase 2 memakai atribut `notif_ringkasan_mingguan`;
        bila atribut belum ada, default True (perilaku lama tetap jalan).
        """
        return bool(getattr(user, "notif_ringkasan_mingguan", True))

    # ------------------------------------------------- fungsi kontrak
    async def sync_account(self, db: Any, account: Any) -> dict:
        fn = _need("app.services.sync_service", "sync_account")
        return await fn(db, account)

    async def get_or_generate_summary(
        self,
        db: Any,
        brand: Any,
        org_id: Any,
        period_start: Any,
        period_end: Any,
        llm: Any,
    ) -> Any:
        fn = _need("app.services.summaries", "get_or_generate_summary")
        return await fn(db, brand, org_id, period_start, period_end, llm)

    async def notify(self, db: Any, user: Any, jenis: str, payload: dict) -> Any:
        fn = _need("app.services.notifications", "notify")
        hasil = await fn(db, user, jenis, payload)
        # notify() hanya menulis baris notification_logs ke sesi; worker tidak
        # punya commit otomatis seperti request API, jadi commit di sini agar
        # jejak pengiriman benar-benar tersimpan.
        await db.commit()
        return hasil

    async def notify_org(self, db: Any, organization_id: Any, jenis: str, payload: dict) -> Any:
        fn = _need("app.services.notifications", "notify_org")
        hasil = await fn(db, organization_id, jenis, payload)
        # Alasan sama seperti notify(): tanpa commit, baris notification_logs
        # hilang saat sesi worker ditutup (rollback).
        await db.commit()
        return hasil

    def get_llm_provider(self) -> Any:
        fn = _need("app.services.llm", "get_llm_provider")
        return fn()

    # ------------------------------------------------- kesiapan
    def check_ready(self) -> None:
        """Gagal cepat bila ada bagian kontrak yang belum tersedia."""
        try:
            _need("app.db.session", "get_session")
        except BackendNotReadyError:
            # Fallback Fase 1 juga boleh.
            _need("app.db.session", "get_session_factory")
        for nama_modul, nama_objek in [
            ("app.models", "ConnectedAccount"),
            ("app.models", "Brand"),
            ("app.models", "Organization"),
            ("app.models", "OrganizationMember"),
            ("app.models", "Membership"),
            ("app.models", "User"),
            ("app.services.sync_service", "sync_account"),
            ("app.services.summaries", "get_or_generate_summary"),
            ("app.services.notifications", "notify"),
            ("app.services.llm", "get_llm_provider"),
        ]:
            _need(nama_modul, nama_objek)
