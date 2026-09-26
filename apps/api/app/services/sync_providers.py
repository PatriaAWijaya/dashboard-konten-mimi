"""Provider sinkronisasi konten Fase 2: TikTok Login Kit v2 & Meta Graph API.

Kontrak:
- SyncProvider.fetch_posts(account, since) -> list[dict]: baris mentah dengan
  key SAMA dengan kolom CSV Fase 1; selalu dinormalisasi lewat
  normalize_content_row oleh sync_service (satu pintu validasi).
- get_provider(platform, settings_getter): provider nyata bila kredensial
  admin lengkap, else MockSyncProvider (data demo, tanpa jaringan).

CATATAN: TikTokSyncProvider & InstagramSyncProvider adalah implementasi nyata
berdasarkan dokumentasi publik API masing-masing, tetapi BELUM TERUJI tanpa
kredensial asli (butuh aplikasi terdaftar di TikTok Developers / Meta
Developers + akun asli untuk OAuth). Jangan klaim sudah berfungsi end-to-end
sebelum diuji dengan kredensial asli.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Callable
from urllib.parse import urlencode

import httpx


# ---------------------------------------------------------------------------
# SyncedPost: baris mentah dengan key = kolom CSV Fase 1
# ---------------------------------------------------------------------------

CSV_KEYS = (
    "platform",
    "post_id",
    "post_url",
    "tanggal_posting",
    "format",
    "tujuan",
    "caption",
    "views",
    "reach",
    "likes",
    "comments",
    "shares",
    "saves",
    "avg_watch_seconds",
    "profile_clicks",
    "link_clicks",
    "replies",
    "sticker_taps",
)


@dataclass
class SyncedPost:
    """Satu postingan hasil fetch provider. to_row() → dict siap normalize."""

    platform: str = ""
    post_id: str = ""
    post_url: str = ""
    tanggal_posting: str = ""  # YYYY-MM-DD
    format: str = ""
    tujuan: str = ""
    caption: str = ""
    views: int = 0
    reach: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    saves: int = 0
    avg_watch_seconds: float = 0.0
    profile_clicks: int = 0
    link_clicks: int = 0
    replies: int = 0
    sticker_taps: int = 0

    def to_row(self) -> dict:
        row = asdict(self)
        return {k: ("" if row.get(k) is None else str(row.get(k))) for k in CSV_KEYS}


# ---------------------------------------------------------------------------
# Kontrak provider
# ---------------------------------------------------------------------------

class SyncProvider(ABC):
    """Kontrak provider sinkronisasi satu platform."""

    platform_name: str = ""

    @abstractmethod
    def build_authorize_url(
        self,
        *,
        client_id: str,
        redirect_uri: str,
        state: str,
        code_challenge: str,
        scopes: str | None = None,
    ) -> str:
        """Rakit URL halaman authorize OAuth."""
        raise NotImplementedError

    @abstractmethod
    async def exchange_code(
        self,
        *,
        code: str,
        code_verifier: str,
        redirect_uri: str,
        client_id: str,
        client_secret: str,
    ) -> dict:
        """Tukar authorization code → dict token.

        Return: {"access_token", "refresh_token"|None, "expires_in"|None,
                 "account_name"|None, "account_external_id"|None}.
        """
        raise NotImplementedError

    @abstractmethod
    async def fetch_posts(self, account, since: date) -> list[dict]:
        """Ambil postingan sejak `since` → list dict baris mentah (key CSV)."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Mock provider (data demo, tanpa jaringan)
# ---------------------------------------------------------------------------

_MOCK_TUJUAN = ["edukasi", "hiburan", "interaksi", "jualan", "branding"]
_MOCK_FORMAT = {
    "tiktok": ["reels", "reels", "reels", "foto", "carousel"],
    "instagram": ["reels", "carousel", "carousel", "foto", "reels"],
}


class MockSyncProvider(SyncProvider):
    """Provider demo: ~15 postingan fixture realistis, tanpa panggilan jaringan.

    Baris fixture TETAP melewati normalize_content_row yang sama di
    sync_service — jadi yang diuji adalah alur normalisasi & upsert, bukan
    parsing khusus mock.
    """

    def __init__(self, platform_name: str = "tiktok") -> None:
        self.platform_name = platform_name

    # -- OAuth pura-pura -------------------------------------------------
    def build_authorize_url(self, *, client_id, redirect_uri, state, code_challenge, scopes=None) -> str:
        params = urlencode(
            {
                "client_id": client_id or "mock-client-id",
                "redirect_uri": redirect_uri,
                "state": state,
                "code_challenge": code_challenge,
                "response_type": "code",
            }
        )
        return f"https://mock-oauth.local/{self.platform_name}/authorize?{params}"

    async def exchange_code(self, *, code, code_verifier, redirect_uri, client_id, client_secret) -> dict:
        return {
            "access_token": f"mock-access-{self.platform_name}-{code[:8]}",
            "refresh_token": f"mock-refresh-{self.platform_name}-{code[:8]}",
            "expires_in": 3600 * 24 * 60,
            "account_name": f"Akun Demo {self.platform_name.title()}",
            "account_external_id": f"mock-{self.platform_name}-001",
        }

    # -- Fetch fixture ----------------------------------------------------
    def _fixture_posts(self, since: date) -> list[SyncedPost]:
        # Tanggal fixture STABIL (tidak tergantung `since`): 15 postingan tersebar
        # di 21 hari terakhir. Ini membuat sync ulang idempoten — post_id yang sama
        # selalu punya tanggal_posting yang sama, tidak "bergeser" mengikuti
        # last_sync_at. (Sejak Fase 2: sync ulang mock pernah menggeser posted_at
        # ke masa depan karena tanggal dihitung relatif terhadap `since`.)
        formats = _MOCK_FORMAT.get(self.platform_name, _MOCK_FORMAT["tiktok"])
        base = date.today() - timedelta(days=21)
        posts: list[SyncedPost] = []
        for i in range(15):
            tgl = base + timedelta(days=i)
            views = 1200 + (i * 1373) % 18000
            likes = int(views * (0.04 + (i % 5) * 0.012))
            comments = int(views * 0.008) + (i % 7)
            shares = int(views * 0.011)
            saves = int(views * 0.014)
            posts.append(
                SyncedPost(
                    platform=self.platform_name,
                    post_id=f"mock-{self.platform_name}-{i + 1:03d}",
                    post_url=f"https://{self.platform_name}.com/mock/{i + 1:03d}",
                    tanggal_posting=tgl.isoformat(),
                    format=formats[i % len(formats)],
                    tujuan=_MOCK_TUJUAN[i % len(_MOCK_TUJUAN)],
                    caption=f"Caption demo #{i + 1} untuk {_MOCK_TUJUAN[i % len(_MOCK_TUJUAN)]}",
                    views=views,
                    reach=int(views * 0.92),
                    likes=likes,
                    comments=comments,
                    shares=shares,
                    saves=saves,
                    avg_watch_seconds=round(6.5 + (i % 9) * 1.7, 1),
                    profile_clicks=int(views * 0.02),
                    link_clicks=int(views * 0.004),
                    replies=i % 4,
                    sticker_taps=0,
                )
            )
        return posts

    async def fetch_posts(self, account, since: date) -> list[dict]:
        return [p.to_row() for p in self._fixture_posts(since)]


# ---------------------------------------------------------------------------
# TikTok Login Kit v2 (nyata — BELUM TERUJI tanpa kredensial asli)
# ---------------------------------------------------------------------------

class TikTokSyncProvider(SyncProvider):
    """Implementasi nyata TikTok Login Kit v2 (PKCE).

    Alur: authorize (tiktok.com/v2/auth/authorize) → tukar code di
    open.tiktokapis.com/v2/oauth/token/ → daftar video di /v2/video/list/.

    BELUM TERUJI tanpa kredensial asli: butuh aplikasi terdaftar di
    TikTok Developers dengan scope user.info.basic + video.list.
    """

    platform_name = "tiktok"
    AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
    TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
    VIDEO_LIST_URL = "https://open.tiktokapis.com/v2/video/list/"
    DEFAULT_SCOPES = "user.info.basic,video.list"

    def __init__(self, client_key: str, client_secret: str) -> None:
        self.client_key = client_key
        self.client_secret = client_secret

    def build_authorize_url(self, *, client_id, redirect_uri, state, code_challenge, scopes=None) -> str:
        params = urlencode(
            {
                "client_key": client_id,
                "scope": scopes or self.DEFAULT_SCOPES,
                "response_type": "code",
                "redirect_uri": redirect_uri,
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"{self.AUTHORIZE_URL}?{params}"

    async def exchange_code(self, *, code, code_verifier, redirect_uri, client_id, client_secret) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                self.TOKEN_URL,
                json={
                    "client_key": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                    "code_verifier": code_verifier,
                },
            )
        if resp.status_code != 200:
            raise RuntimeError(f"TikTok token exchange gagal (HTTP {resp.status_code}).")
        data = resp.json()
        if data.get("error"):
            raise RuntimeError(f"TikTok token exchange gagal: {data.get('error_description') or data.get('error')}.")
        return {
            "access_token": data.get("access_token"),
            "refresh_token": data.get("refresh_token"),
            "expires_in": data.get("expires_in"),
            "account_name": None,
            "account_external_id": data.get("open_id"),
        }

    async def fetch_posts(self, account, since: date) -> list[dict]:
        from app.core.crypto import decrypt_text

        access_token = decrypt_text(account.access_token_encrypted)
        fields = "id,create_time,title,share_url,view_count,like_count,comment_count,share_count,duration"
        posts: list[SyncedPost] = []
        cursor = 0
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                resp = await client.post(
                    self.VIDEO_LIST_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={"max_count": 20, "cursor": cursor},
                    params={"fields": fields},
                )
                if resp.status_code != 200:
                    raise RuntimeError(f"TikTok video/list gagal (HTTP {resp.status_code}).")
                data = resp.json().get("data") or {}
                for v in data.get("videos") or []:
                    tgl = date.fromtimestamp(int(v.get("create_time") or 0))
                    if tgl < since:
                        continue
                    posts.append(
                        SyncedPost(
                            platform="tiktok",
                            post_id=str(v.get("id") or ""),
                            post_url=str(v.get("share_url") or ""),
                            tanggal_posting=tgl.isoformat(),
                            format="reels",
                            # TikTok API tidak memberi "tujuan" konten; default
                            # netral, bisa dikoreksi manual setelah sync.
                            tujuan="branding",
                            caption=str(v.get("title") or ""),
                            views=int(v.get("view_count") or 0),
                            likes=int(v.get("like_count") or 0),
                            comments=int(v.get("comment_count") or 0),
                            shares=int(v.get("share_count") or 0),
                            avg_watch_seconds=float(v.get("duration") or 0),
                        )
                    )
                if not data.get("has_more"):
                    break
                cursor = data.get("cursor") or 0
        return [p.to_row() for p in posts]


# ---------------------------------------------------------------------------
# Instagram / Meta Graph API (nyata — BELUM TERUJI tanpa kredensial asli)
# ---------------------------------------------------------------------------

class InstagramSyncProvider(SyncProvider):
    """Implementasi nyata Meta Graph API untuk Instagram.

    Alur: dialog OAuth Facebook → tukar code → long-lived token →
    GET /me/media + insights per media (graceful degradation bila bukan
    akun bisnis/kreator atau izin insights tidak diberikan).

    BELUM TERUJI tanpa kredensial asli: butuh aplikasi di Meta Developers
    dengan produk Instagram Graph API.
    """

    platform_name = "instagram"
    GRAPH_VERSION = "v20.0"
    AUTHORIZE_URL = "https://www.facebook.com/v20.0/dialog/oauth"
    DEFAULT_SCOPES = "instagram_basic,instagram_manage_insights,pages_show_list,pages_read_engagement"

    def __init__(self, app_id: str, app_secret: str) -> None:
        self.app_id = app_id
        self.app_secret = app_secret

    def _graph(self, path: str) -> str:
        return f"https://graph.facebook.com/{self.GRAPH_VERSION}/{path.lstrip('/')}"

    def build_authorize_url(self, *, client_id, redirect_uri, state, code_challenge, scopes=None) -> str:
        params = urlencode(
            {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "state": state,
                "scope": scopes or self.DEFAULT_SCOPES,
                "response_type": "code",
            }
        )
        return f"{self.AUTHORIZE_URL}?{params}"

    async def exchange_code(self, *, code, code_verifier, redirect_uri, client_id, client_secret) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. code → short-lived token
            r1 = await client.get(
                self._graph("oauth/access_token"),
                params={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )
            if r1.status_code != 200:
                raise RuntimeError(f"Meta token exchange gagal (HTTP {r1.status_code}).")
            short = r1.json().get("access_token")
            if not short:
                raise RuntimeError("Meta token exchange: access_token tidak ada di respons.")
            # 2. short-lived → long-lived (60 hari)
            r2 = await client.get(
                self._graph("oauth/access_token"),
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "fb_exchange_token": short,
                },
            )
            long_token, expires_in = short, None
            if r2.status_code == 200:
                long_token = r2.json().get("access_token", short)
                expires_in = r2.json().get("expires_in")
            # 3. info akun (best effort)
            nama, ext_id = None, None
            try:
                r3 = await client.get(
                    self._graph("me"),
                    params={"fields": "id,username", "access_token": long_token},
                )
                if r3.status_code == 200:
                    nama = r3.json().get("username")
                    ext_id = r3.json().get("id")
            except httpx.HTTPError:
                pass
        return {
            "access_token": long_token,
            "refresh_token": None,  # Meta memakai long-lived token, bukan refresh token
            "expires_in": expires_in,
            "account_name": f"@{nama}" if nama else None,
            "account_external_id": ext_id,
        }

    async def fetch_posts(self, account, since: date) -> list[dict]:
        from app.core.crypto import decrypt_text

        access_token = decrypt_text(account.access_token_encrypted)
        posts: list[SyncedPost] = []
        url = self._graph("me/media")
        params = {
            "fields": "id,caption,media_type,timestamp,like_count,comments_count,permalink",
            "access_token": access_token,
            "limit": 50,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            while url:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    raise RuntimeError(f"Meta /me/media gagal (HTTP {resp.status_code}).")
                data = resp.json()
                for m in data.get("data") or []:
                    ts = str(m.get("timestamp") or "")
                    try:
                        tgl = date.fromisoformat(ts[:10])
                    except ValueError:
                        continue
                    if tgl < since:
                        continue
                    media_type = (m.get("media_type") or "").upper()
                    fmt = {"VIDEO": "reels", "REELS": "reels", "CAROUSEL_ALBUM": "carousel"}.get(
                        media_type, "foto"
                    )
                    # Insights: best effort — akun non-bisnis / tanpa izin
                    # akan gagal di sini; metrik dasar tetap dipakai.
                    reach = saves = shares = 0
                    try:
                        ins = await client.get(
                            self._graph(f"{m['id']}/insights"),
                            params={
                                "metric": "reach,saved,shares",
                                "access_token": access_token,
                            },
                        )
                        if ins.status_code == 200:
                            for item in ins.json().get("data") or []:
                                vals = item.get("values") or []
                                val = vals[0].get("value") if vals else 0
                                if item.get("name") == "reach":
                                    reach = int(val or 0)
                                elif item.get("name") == "saved":
                                    saves = int(val or 0)
                                elif item.get("name") == "shares":
                                    shares = int(val or 0)
                    except httpx.HTTPError:
                        pass
                    posts.append(
                        SyncedPost(
                            platform="instagram",
                            post_id=str(m.get("id") or ""),
                            post_url=str(m.get("permalink") or ""),
                            tanggal_posting=tgl.isoformat(),
                            format=fmt,
                            # Graph API tidak memberi "tujuan"; default netral.
                            tujuan="branding",
                            caption=str(m.get("caption") or ""),
                            reach=reach,
                            likes=int(m.get("like_count") or 0),
                            comments=int(m.get("comments_count") or 0),
                            shares=shares,
                            saves=saves,
                        )
                    )
                paging = data.get("paging") or {}
                url = paging.get("next")
                params = {}
        return [p.to_row() for p in posts]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

SettingsGetter = Callable[[str], str | None]


def get_provider(platform: str, settings_getter: SettingsGetter) -> SyncProvider:
    """Kembalikan provider nyata bila kredensial lengkap, else MockSyncProvider.

    settings_getter: callable(key) -> str | None untuk app_settings
    (tiktok_client_key/secret, instagram_app_id/secret); env
    TIKTOK_CLIENT_KEY/SECRET & INSTAGRAM_APP_ID/SECRET sebagai fallback.
    """
    platform = (platform or "").strip().lower()
    if platform == "tiktok":
        key = (settings_getter("tiktok_client_key") or "").strip() or os.environ.get("TIKTOK_CLIENT_KEY", "").strip()
        secret = (settings_getter("tiktok_client_secret") or "").strip() or os.environ.get("TIKTOK_CLIENT_SECRET", "").strip()
        if key and secret:
            return TikTokSyncProvider(client_key=key, client_secret=secret)
        return MockSyncProvider("tiktok")
    if platform == "instagram":
        app_id = (settings_getter("instagram_app_id") or "").strip() or os.environ.get("INSTAGRAM_APP_ID", "").strip()
        secret = (settings_getter("instagram_app_secret") or "").strip() or os.environ.get("INSTAGRAM_APP_SECRET", "").strip()
        if app_id and secret:
            return InstagramSyncProvider(app_id=app_id, app_secret=secret)
        return MockSyncProvider("instagram")
    raise ValueError(f"Platform tidak dikenal: '{platform}'. Pilihan: tiktok, instagram.")
