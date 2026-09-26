"""Layanan penyimpanan file: ABC + implementasi lokal."""

import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import get_settings


class StorageService(ABC):
    @abstractmethod
    async def save_payment_proof(self, data: bytes, extension: str) -> str:
        """Simpan file, kembalikan path relatif terhadap STORAGE_DIR."""
        ...

    @abstractmethod
    async def save_brand_logo(self, data: bytes, extension: str) -> str:
        """Simpan logo brand, kembalikan path relatif terhadap STORAGE_DIR."""
        ...

    @abstractmethod
    def absolute_path(self, relative_path: str) -> Path:
        ...


class LocalStorageService(StorageService):
    """Simpan di STORAGE_DIR/payment_proofs/<uuid>.<ext>."""

    def __init__(self, storage_dir: str | None = None) -> None:
        settings = get_settings()
        self.base_dir = Path(storage_dir or settings.STORAGE_DIR)
        self.proof_dir = self.base_dir / "payment_proofs"
        self.proof_dir.mkdir(parents=True, exist_ok=True)
        self.logo_dir = self.base_dir / "brand_logos"
        self.logo_dir.mkdir(parents=True, exist_ok=True)

    async def save_payment_proof(self, data: bytes, extension: str) -> str:
        ext = extension.lower().lstrip(".")
        filename = f"{uuid.uuid4().hex}.{ext}"
        dest = self.proof_dir / filename
        dest.write_bytes(data)
        return str(Path("payment_proofs") / filename)

    async def save_brand_logo(self, data: bytes, extension: str) -> str:
        ext = extension.lower().lstrip(".")
        filename = f"{uuid.uuid4().hex}.{ext}"
        dest = self.logo_dir / filename
        dest.write_bytes(data)
        return str(Path("brand_logos") / filename)

    def absolute_path(self, relative_path: str) -> Path:
        # Cegah path traversal: pastikan hasil tetap di dalam base_dir.
        candidate = (self.base_dir / relative_path).resolve()
        if not str(candidate).startswith(str(self.base_dir.resolve())):
            raise ValueError("Path file tidak valid.")
        return candidate


def get_storage_service() -> StorageService:
    return LocalStorageService()
