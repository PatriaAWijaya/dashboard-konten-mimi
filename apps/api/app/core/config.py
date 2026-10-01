"""Konfigurasi aplikasi dari environment variables (pydantic-settings).

Semua angka/limit bisnis diambil dari sini — jangan hardcode di kode lain.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://app_user:app_password@localhost:5432/dashboard_konten"
    SUPERUSER_DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/dashboard_konten"
    MIGRATION_DATABASE_URL: str = ""
    APP_DB_USER: str = "app_user"
    APP_DB_PASSWORD: str = "app_password"

    # --- Redis (cadangan fase berikutnya) ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- JWT ---
    JWT_SECRET_KEY: str = "ganti-secret-ini-di-production-minimal-32-karakter"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- Environment: dev | staging | prod ---
    ENV: str = "dev"

    # --- Batasan bisnis ---
    MAX_BRANDS_PER_ORG: int = 3
    GRACE_PERIOD_DAYS: int = 7
    MEMBERSHIP_DURATION_DAYS: int = 365
    INVOICE_EXPIRY_HOURS: int = 24
    # Kode unik 3 digit untuk transfer manual
    UNIQUE_CODE_MIN: int = 1
    UNIQUE_CODE_MAX: int = 999
    UNIQUE_CODE_MAX_RETRIES: int = 20
    # Kuota anggota bila organisasi belum punya paket
    DEFAULT_SEATS_NO_PLAN: int = 1

    # --- Rekening transfer manual ---
    BANK_NAME: str = "Bank Central Asia (BCA)"
    BANK_ACCOUNT_NUMBER: str = "1234567890"
    BANK_ACCOUNT_NAME: str = "PT MySocial Watch"

    # --- Storage file ---
    STORAGE_DIR: str = "./storage"
    MAX_UPLOAD_MB: int = 5
    ALLOWED_PROOF_EXTENSIONS: str = "jpg,jpeg,png,pdf"

    # --- Seed superadmin ---
    SEED_ADMIN_EMAIL: str = "admin@example.com"
    SEED_ADMIN_PASSWORD: str = "Admin123!"

    # --- Token email ---
    EMAIL_VERIFICATION_EXPIRE_MINUTES: int = 15
    PASSWORD_RESET_EXPIRE_HOURS: int = 24

    # --- Password ---
    PASSWORD_MIN_LENGTH: int = 8
    BCRYPT_ROUNDS: int = 12

    # --- LLM (narasi agregat; tidak pernah menerima data mentah per konten) ---
    LLM_PROVIDER: str = "mock"  # mock | openai | anthropic
    LLM_API_KEY: str = ""
    LLM_MODEL: str = ""

    # --- Enkripsi token (Fase 2) ---
    # Kunci Fernet base64. KOSONG = mode dev (kunci sementara per proses + warning).
    FERNET_KEY: str = ""

    # --- URL publik (Fase 2: OAuth callback & redirect frontend) ---
    FRONTEND_URL: str = "http://localhost:3000"
    API_BASE_URL: str = "http://localhost:8000"
    # --- CORS: daftar origin dipisah koma, atau "*" untuk uji publik ---
    CORS_ORIGINS: str = "*"

    # --- SMTP (SmtpEmailService, dipakai saat ENV != dev) ---
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@dashboard.local"
    SMTP_USE_TLS: bool = True
    # Brevo HTTP API (pengiriman via port 443; untuk hosting yang memblokir
    # outbound SMTP seperti Render free tier). Format: xkeysib-...
    BREVO_API_KEY: str = ""

    @property
    def is_dev(self) -> bool:
        return self.ENV.lower() == "dev"

    @property
    def migration_database_url(self) -> str:
        return self.MIGRATION_DATABASE_URL or self.SUPERUSER_DATABASE_URL or self.DATABASE_URL

    @property
    def allowed_proof_extensions_set(self) -> set[str]:
        return {e.strip().lower().lstrip(".") for e in self.ALLOWED_PROOF_EXTENSIONS.split(",") if e.strip()}

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
 """Kembalikan konfigurasi aplikasi (di-cache per proses).

 URL database diambil langsung dari environment bila tersedia, agar tidak
 tergantung pada perilaku pembacaan env var oleh pydantic-settings di
 dalam container hosting. URL migrasi lain dikosongkan bila tidak di-set
 agar tidak mengalahkan DATABASE_URL.
 """
 import os

 settings = Settings()
 env_database_url = os.environ.get("DATABASE_URL")
 if env_database_url:
         settings.DATABASE_URL = env_database_url
 for field_name in ("SUPERUSER_DATABASE_URL", "MIGRATION_DATABASE_URL"):
         env_value = os.environ.get(field_name)
         setattr(settings, field_name, env_value or "")
 return settings

