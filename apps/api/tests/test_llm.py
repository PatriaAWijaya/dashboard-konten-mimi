"""Tes abstraksi LLM: mock selalu memakai angka context, factory, dan error key."""

import pytest

from app.core.config import get_settings
from app.services.llm import (
    AnthropicProvider,
    MockLLMProvider,
    OpenAIProvider,
    get_llm_provider,
)


@pytest.fixture(autouse=True)
def _segarkan_settings(monkeypatch):
    yield
    get_settings.cache_clear()


def _pakai_env(monkeypatch, **env):
    for k, v in env.items():
        if v is None:
            monkeypatch.delenv(k, raising=False)
        else:
            monkeypatch.setenv(k, v)
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# MockLLMProvider
# ---------------------------------------------------------------------------

async def test_mock_rekomendasi_mencantumkan_angka_context():
    ctx = {
        "type": "perbanyak",
        "format": "reels",
        "tujuan": "edukasi",
        "n": 12,
        "menang": 7,
        "win_rate": 0.5833,
        "avg_score": 72.4,
        "avg_er": 4.1,
        "contoh_post_ids": ["abc123", "def456"],
    }
    teks = await MockLLMProvider().narrate("rekomendasi", ctx)
    for angka in ("12", "7", "58,3", "72,4", "4,1", "abc123"):
        assert angka in teks, f"angka {angka} hilang dari narasi"
    assert "99" not in teks  # tidak boleh mengarang angka baru


async def test_mock_rekomendasi_tiap_tipe():
    for tipe in ("perbanyak", "kurangi", "perbaiki", "coba_baru"):
        ctx = {
            "type": tipe, "format": "reels", "tujuan": "edukasi", "n": 5,
            "menang": 1, "win_rate": 0.2, "avg_score": 50.0, "avg_er": 2.5,
            "contoh_post_ids": ["x1"], "niche": "Niche A",
            "match_percent": 0.75, "total_konten": 20,
            "suitability_verdict": "tidak_sesuai", "pola_bermasalah": "reels/edukasi",
        }
        teks = await MockLLMProvider().narrate("rekomendasi", ctx)
        assert isinstance(teks, str) and len(teks) > 20


async def test_mock_brand_dna_merangkai_jawaban():
    ctx = {
        "brand_name": "Brand Tes",
        "jawaban": {"identitas": "Saya brand strategist untuk NGO", "audiens": "pengurus yayasan"},
        "dilewati": ["bukti"],
        "label_pertanyaan": {"identitas": "Siapa Anda?", "audiens": "Siapa audiens?", "bukti": "Bukti?"},
        "terjawab": 2,
        "total": 8,
    }
    teks = await MockLLMProvider().narrate("brand_dna", ctx)
    assert "Saya brand strategist untuk NGO" in teks
    assert "pengurus yayasan" in teks
    assert "bukti" in teks.lower()  # celah ditandai


async def test_mock_niche_mencantumkan_match_percent():
    ctx = {
        "brand_name": "Brand Tes",
        "niches": [
            {"name": "Niche A", "match_percent": 0.82, "alasan": "Selaras misi."},
            {"name": "Niche B", "match_percent": 0.61, "alasan": "Potensi besar."},
        ],
    }
    teks = await MockLLMProvider().narrate("niche", ctx)
    assert "82" in teks and "61" in teks
    assert "Niche A" in teks and "Niche B" in teks


async def test_mock_kind_tidak_dikenal():
    with pytest.raises(ValueError, match="tidak dikenal"):
        await MockLLMProvider().narrate("ramalan", {})


# ---------------------------------------------------------------------------
# Factory & provider berbayar
# ---------------------------------------------------------------------------

def test_get_llm_provider_default_mock(monkeypatch):
    _pakai_env(monkeypatch, LLM_PROVIDER=None)
    assert isinstance(get_llm_provider(), MockLLMProvider)


def test_get_llm_provider_tidak_dikenal(monkeypatch):
    _pakai_env(monkeypatch, LLM_PROVIDER="gemini")
    with pytest.raises(ValueError, match="tidak dikenal"):
        get_llm_provider()


def test_openai_tanpa_key_raise(monkeypatch):
    _pakai_env(monkeypatch, LLM_PROVIDER="openai", LLM_API_KEY="")
    with pytest.raises(RuntimeError, match="belum dikonfigurasi"):
        get_llm_provider()
    with pytest.raises(RuntimeError, match="belum dikonfigurasi"):
        OpenAIProvider()


def test_anthropic_tanpa_key_raise(monkeypatch):
    _pakai_env(monkeypatch, LLM_PROVIDER="anthropic", LLM_API_KEY="")
    with pytest.raises(RuntimeError, match="belum dikonfigurasi"):
        get_llm_provider()
    with pytest.raises(RuntimeError, match="belum dikonfigurasi"):
        AnthropicProvider()


def test_provider_dengan_key_tidak_raise_saat_init(monkeypatch):
    _pakai_env(monkeypatch, LLM_PROVIDER="openai", LLM_API_KEY="kunci-palsu-untuk-tes")
    assert isinstance(get_llm_provider(), OpenAIProvider)
    _pakai_env(monkeypatch, LLM_PROVIDER="anthropic", LLM_API_KEY="kunci-palsu-untuk-tes")
    assert isinstance(get_llm_provider(), AnthropicProvider)
