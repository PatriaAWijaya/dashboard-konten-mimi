"""Abstraksi LLM dengan prinsip "agregat dulu, narasi kemudian".

LLM hanya menerima dict agregat (angka ringkasan / jawaban wawancara), tidak
pernah data mentah per konten. Mock provider selalu mencantumkan angka-angka
bukti dari context dan tidak mengarang angka baru.
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
import httpx

from app.core.config import get_settings

# Jenis narasi yang didukung oleh narrate().
NARRATE_KINDS = ("rekomendasi", "brand_dna", "niche", "ringkasan", "copywriting")


class LLMProvider(ABC):
    """Kontrak provider LLM."""

    @abstractmethod
    async def narrate(self, kind: str, context: dict) -> str:
        """Susun narasi Bahasa Indonesia dari dict agregat `context`.

        kind: 'rekomendasi' | 'brand_dna' | 'niche'.
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Helper format angka (gaya Indonesia: koma desimal)
# ---------------------------------------------------------------------------

def _fmt(x: float | int | None, digits: int = 1) -> str:
    if x is None:
        return "-"
    try:
        return f"{float(x):.{digits}f}".replace(".", ",")
    except (TypeError, ValueError):
        return str(x)


def _pct(x: float | int | None) -> str:
    """0.583 -> '58,3%'."""
    if x is None:
        return "-"
    return f"{_fmt(float(x) * 100)}%"


# ---------------------------------------------------------------------------
# Mock provider (template-based, tanpa panggilan jaringan)
# ---------------------------------------------------------------------------

class MockLLMProvider(LLMProvider):
    """Narasi template Bahasa Indonesia. Selalu memakai angka dari context."""

    async def narrate(self, kind: str, context: dict) -> str:
        if kind == "rekomendasi":
            return self._narrate_rekomendasi(context)
        if kind == "brand_dna":
            return self._narrate_brand_dna(context)
        if kind == "niche":
            return self._narrate_niche(context)
        if kind == "ringkasan":
            return self._narrate_ringkasan(context)
        if kind == "copywriting":
            return self._narrate_copywriting(context)
        raise ValueError(f"Jenis narasi tidak dikenal: '{kind}'. Pilihan: {', '.join(NARRATE_KINDS)}.")

    # -- rekomendasi ------------------------------------------------------

    def _narrate_rekomendasi(self, ctx: dict) -> str:
        tipe = str(ctx.get("type", "")).lower()
        fmt = ctx.get("format") or "-"
        tujuan = ctx.get("tujuan") or "-"
        n = int(ctx.get("n", 0) or 0)
        menang = int(ctx.get("menang", 0) or 0)
        wr = _pct(ctx.get("win_rate", 0.0))
        avg_skor = _fmt(ctx.get("avg_score"))
        avg_er = _fmt(ctx.get("avg_er"))
        contoh = ctx.get("contoh_post_ids") or []
        contoh_txt = ", ".join(str(p) for p in contoh[:3]) if contoh else "-"

        bukti = (
            f"Bukti data periode ini: {n} konten, {menang} di antaranya berstatus 'menang' "
            f"(win rate {wr}), rata-rata skor {avg_skor}, rata-rata ER {avg_er}%. "
            f"Contoh konten: {contoh_txt}."
        )

        if tipe == "perbanyak":
            return (
                f"Rekomendasi: PERBANYAK format '{fmt}' untuk tujuan '{tujuan}'.\n\n"
                f"{bukti}\n\n"
                "Artinya pola ini terbukti berhasil untuk audiens Anda. Pertahankan gaya, "
                "hook, dan struktur yang sama, lalu tingkatkan frekuensi publikasinya "
                "pada periode berikutnya."
            )
        if tipe == "kurangi":
            return (
                f"Rekomendasi: KURANGI format '{fmt}' untuk tujuan '{tujuan}'.\n\n"
                f"{bukti}\n\n"
                "Pola ini jarang menang sehingga menghabiskan slot publikasi. Kurangi "
                "porsinya, lalu evaluasi ulang setelah ada perbaikan konsep."
            )
        if tipe == "perbaiki":
            verdict = ctx.get("suitability_verdict", "tidak_sesuai")
            pola = ctx.get("pola_bermasalah") or "-"
            return (
                f"Rekomendasi: PERBAIKI format '{fmt}' untuk tujuan '{tujuan}'.\n\n"
                f"{bukti}\n\n"
                f"Hasil evaluasi kesesuaian: '{verdict}' (pola bermasalah: {pola}). "
                "Konten-konten berstatus 'kurang' pada pola ini perlu diperbaiki "
                "angle atau eksekusinya sebelum dipublikasikan lagi."
            )
        if tipe == "coba_baru":
            niche = ctx.get("niche")
            total = int(ctx.get("total_konten", 0) or 0)
            if niche:
                match = _pct(ctx.get("match_percent", 0.0))
                return (
                    f"Rekomendasi: COBA BARU — format '{fmt}' untuk niche '{niche}'.\n\n"
                    f"Niche ini terpilih dengan kecocokan {match} terhadap DNA brand. "
                    f"Belum ada konten (n={n}) untuk kombinasi ini dari total {total} konten "
                    "yang dianalisis. Uji 2-3 konten dulu, lalu ukur win rate-nya sebelum "
                    "dijadikan pola rutin."
                )
            return (
                f"Rekomendasi: COBA BARU — kombinasi format '{fmt}' + tujuan '{tujuan}'.\n\n"
                f"Kombinasi ini belum pernah dicoba (n={n}) dari total {total} konten yang "
                "dianalisis. Uji 2-3 konten dulu sebagai eksperimen terkontrol, lalu "
                "bandingkan skornya dengan pola yang sudah menang."
            )
        return (
            f"Rekomendasi ({tipe or 'umum'}): format '{fmt}' / tujuan '{tujuan}'.\n\n{bukti}"
        )

    # -- brand_dna --------------------------------------------------------

    def _narrate_brand_dna(self, ctx: dict) -> str:
        brand = ctx.get("brand_name") or "brand Anda"
        jawaban: dict = ctx.get("jawaban") or {}
        dilewati: list = ctx.get("dilewati") or []
        label: dict = ctx.get("label_pertanyaan") or {}
        terjawab = int(ctx.get("terjawab", len(jawaban)) or 0)
        total = int(ctx.get("total", 0) or 0)

        baris = [f'Ringkasan DNA Brand "{brand}"', "",
                 f"Terjawab {terjawab} dari {total} pertanyaan.", ""]
        for key, teks in jawaban.items():
            tanya = label.get(key, key)
            baris.append(f"- {tanya}: {teks}")
        baris.append("")
        if dilewati:
            celah = ", ".join(label.get(k, k) for k in dilewati)
            baris.append(f"Celah (pertanyaan yang dilewati dan perlu dilengkapi): {celah}.")
        else:
            baris.append("Tidak ada celah: semua pertanyaan terjawab.")
        return "\n".join(baris)

    # -- niche ------------------------------------------------------------

    def _narrate_niche(self, ctx: dict) -> str:
        # Konteks baru: hasil kuesioner Niche Finder 11 kartu (tujuan/jawaban).
        # Fallback ke konteks lama {"niches": [...]} bila masih dipakai pemanggil lama.
        if ctx.get("niches"):
            brand = ctx.get("brand_name") or "brand Anda"
            niches: list = ctx.get("niches") or []
            baris = [
                f'Daftar niche yang paling selaras dengan DNA brand "{brand}":',
                "",
            ]
            for i, nic in enumerate(niches, start=1):
                nama = nic.get("name", "-")
                match = _pct(nic.get("match_percent", 0.0))
                alasan = nic.get("alasan", "")
                baris.append(f"{i}. {nama} — kecocokan {match}. {alasan}".strip())
            baris += [
                "",
                "Pilih 1-2 niche untuk difokuskan 90 hari ke depan, lalu ukur "
                "win rate kontennya sebelum menambah niche baru.",
            ]
            return "\n".join(baris)

        brand = ctx.get("brand_name") or "brand Anda"
        tujuan = ctx.get("tujuan") or "-"
        terjawab = int(ctx.get("terjawab") or 0)
        total = int(ctx.get("total") or 11)
        dilewati = ctx.get("dilewati") or []
        jawaban = ctx.get("jawaban") or {}
        topik = ((jawaban.get("topik") or {}).get("utama")) if isinstance(jawaban.get("topik"), dict) else None
        baris = [
            f'Laporan niche "{brand}" selesai disusun.',
            "",
            f"Tujuan kuesioner: {tujuan}.",
            f"Kartu terjawab: {terjawab} dari {total}"
            + (f" ({len(dilewati)} dilewati)." if dilewati else "."),
        ]
        if topik:
            baris.append(f"Topik utama: {topik}.")
        baris += [
            "",
            "Fokus 30 hari ke depan pada satu topik utama, ukur pola konten yang "
            "menang, lalu tajamkan niche berdasarkan data — bukan asumsi.",
        ]
        return "\n".join(baris)

    # -- ringkasan ----------------------------------------------------------

    def _narrate_ringkasan(self, ctx: dict) -> str:
        brand = ctx.get("brand_name") or "brand Anda"
        awal = ctx.get("period_start") or "-"
        akhir = ctx.get("period_end") or "-"
        total = int(ctx.get("total_konten") or 0)
        rata_skor = _fmt(ctx.get("rata_skor"))
        rata_er = _fmt(ctx.get("rata_er"))
        pola = ctx.get("pola_top3") or []
        terbaik = ctx.get("konten_terbaik") or []
        terburuk = ctx.get("konten_terburuk") or []

        baris = [
            f'Ringkasan kinerja konten "{brand}" periode {awal} s.d. {akhir}.',
            "",
            f"Total {total} konten dianalisis; rata-rata skor {rata_skor}, "
            f"rata-rata ER {rata_er}%.",
            "",
        ]
        if pola:
            baris.append("Pola format×tujuan terbaik:")
            for i, p in enumerate(pola, start=1):
                baris.append(
                    f"{i}. {p.get('format')}/{p.get('tujuan')}: "
                    f"{p.get('menang')}/{p.get('n')} menang "
                    f"(win rate {_pct(p.get('win_rate'))})."
                )
            baris.append("")
        if terbaik:
            ids = ", ".join(str(t.get("post_id")) for t in terbaik)
            baris.append(f"Konten terbaik: {ids}.")
        if terburuk:
            ids = ", ".join(str(t.get("post_id")) for t in terburuk)
            baris.append(f"Konten terburuk: {ids}.")
        baris += [
            "",
            "Fokuskan produksi berikutnya pada pola dengan win rate tertinggi "
            "dan perbaiki atau kurangi pola yang consistently kalah.",
        ]
        return "\n".join(baris)

    # -- copywriting ------------------------------------------------------

    def _narrate_copywriting(self, ctx: dict) -> str:
        """Template copywriting mengikuti struktur framework terpilih.

        Versi mock: menyusun draf terstruktur dari input pengguna.
        Untuk hasil yang lebih natural, aktifkan provider openai/anthropic.
        """
        fw = str(ctx.get("framework") or "")
        what = ctx.get("what") or "-"
        who = ctx.get("who") or "-"
        why = ctx.get("why") or "-"
        how = ctx.get("how") or "-"
        pov = ctx.get("pov") or "-"
        audiens = ctx.get("target_audiens") or "-"
        goals = ctx.get("goals") or "-"
        cta = ctx.get("cta") or "-"
        gaya = ctx.get("gaya_bahasa") or "-"
        platform = ctx.get("platform") or "-"

        pembuka = f"[Draf {fw} — {platform} | {gaya} | tujuan: {goals}]"
        if fw == "storybrand":
            isi = (
                f"HOOK (pahlawan = audiens): {who} — {what}.\n\n"
                f"MASALAH: {why}.\n\n"
                f"PANDUAN (brand sebagai pemandu): {how}.\n\n"
                f"RENCANA: {pov}.\n\n"
                f"AJAKAN: {cta}."
            )
        elif fw == "pas":
            isi = (
                f"MASALAH: {who} menghadapi {what}.\n\n"
                f"AGITASI: {why} — kalau dibiarkan, dampaknya ke {audiens}.\n\n"
                f"SOLUSI: {how}.\n\n"
                f"AJAKAN: {cta}."
            )
        elif fw == "bab":
            isi = (
                f"SEBELUM: {who} — {what} ({why}).\n\n"
                f"SESUDAH: {how}.\n\n"
                f"JEMBATAN: {pov}.\n\n"
                f"AJAKAN: {cta}."
            )
        elif fw == "freytag":
            isi = (
                f"PEMBUKA: {who} — {what}.\n\n"
                f"PEMICU: {why}.\n\n"
                f"KLIMAKS: {how}.\n\n"
                f"PENUTUP ({pov}): {cta}."
            )
        elif fw == "truth_gap":
            isi = (
                f"FAKTA MENGEJUTKAN: {what}.\n\n"
                f"KESENJANGAN: {who} mengira {why}, padahal {how}.\n\n"
                f"WAWASAN BARU ({pov}): {cta}."
            )
        else:
            isi = f"{what}\n\n{pov}\n\nAJAKAN: {cta}."
        return f"{pembuka}\n\n{isi}\n\n(Catatan: ini draf template. Aktifkan provider LLM (OpenAI/Anthropic) untuk copywriting yang lebih natural.)"


# ---------------------------------------------------------------------------
# Provider OpenAI (chat completions via httpx)
# ---------------------------------------------------------------------------

def _build_prompt(kind: str, context: dict) -> tuple[str, str]:
    if kind == "copywriting":
        system = (
            "Kamu adalah copywriter profesional berbahasa Indonesia. "
            "Tulis copywriting yang natural, mengalir, dan siap posting — "
            "bukan template kaku. Sesuaikan panjang dan format dengan platform: "
            "Instagram/Facebook/TikTok/Threads singkat dan memikat (maksimal 150 kata, "
            "boleh pakai emoji secukupnya dan hashtag relevan), "
            "Blog Artikel lebih panjang dan terstruktur. "
            "Ikuti struktur framework storytelling yang diminta. "
            "Gunakan HANYA fakta dari konteks; jangan mengarang klaim baru."
        )
        user = (
            "Buatkan copywriting berdasarkan brief berikut.\n"
            f"Konteks (JSON):\n{json.dumps(context, ensure_ascii=False, default=str)}\n\n"
            "Hasilkan hanya copywriting-nya saja, tanpa penjelasan tambahan."
        )
        return system, user
    system = (
        "Kamu adalah asisten strategi konten. Tulis SELALU dalam Bahasa Indonesia. "
        "Gunakan HANYA angka dan fakta yang ada di konteks JSON berikut; "
        "jangan mengarang angka, nama, atau klaim baru. "
        "Bila data tidak cukup, katakan apa adanya."
    )
    user = (
        f"Jenis narasi: {kind}\n"
        f"Konteks (JSON, hanya ini sumber faktamu):\n"
        f"{json.dumps(context, ensure_ascii=False, default=str)}\n\n"
        "Tulis narasi singkat, jelas, dan siap tampil di dashboard."
    )
    return system, user


class OpenAIProvider(LLMProvider):
    """Provider OpenAI via chat completions. Butuh LLM_API_KEY (+ LLM_MODEL opsional)."""

    API_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key: str | None = None) -> None:
        settings = get_settings()
        self.api_key = (api_key or settings.LLM_API_KEY or "").strip()
        if not self.api_key:
            raise RuntimeError("LLM_API_KEY belum dikonfigurasi untuk provider OpenAI.")
        self.model = (settings.LLM_MODEL or "gpt-4o-mini").strip()

    async def narrate(self, kind: str, context: dict) -> str:
        if kind not in NARRATE_KINDS:
            raise ValueError(f"Jenis narasi tidak dikenal: '{kind}'.")
        system, user = _build_prompt(kind, context)
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    self.API_URL,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        "temperature": 0.7,
                        "max_tokens": 800,
                    },
                )
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Panggilan LLM OpenAI gagal: {exc}.") from exc
        if resp.status_code != 200:
            raise RuntimeError(
                f"LLM OpenAI mengembalikan HTTP {resp.status_code}. Periksa LLM_API_KEY/LLM_MODEL."
            )
        try:
            return resp.json()["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise RuntimeError("Respons LLM OpenAI tidak dapat dibaca.") from exc


# ---------------------------------------------------------------------------
# Provider Anthropic (messages API via httpx)
# ---------------------------------------------------------------------------

class AnthropicProvider(LLMProvider):
    """Provider Anthropic via messages API. Butuh LLM_API_KEY (+ LLM_MODEL opsional)."""

    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str | None = None) -> None:
        settings = get_settings()
        self.api_key = (api_key or settings.LLM_API_KEY or "").strip()
        if not self.api_key:
            raise RuntimeError("LLM_API_KEY belum dikonfigurasi untuk provider Anthropic.")
        self.model = (settings.LLM_MODEL or "claude-3-5-haiku-latest").strip()

    async def narrate(self, kind: str, context: dict) -> str:
        if kind not in NARRATE_KINDS:
            raise ValueError(f"Jenis narasi tidak dikenal: '{kind}'.")
        system, user = _build_prompt(kind, context)
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    self.API_URL,
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "max_tokens": 800,
                        "system": system,
                        "messages": [{"role": "user", "content": user}],
                    },
                )
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Panggilan LLM Anthropic gagal: {exc}.") from exc
        if resp.status_code != 200:
            raise RuntimeError(
                f"LLM Anthropic mengembalikan HTTP {resp.status_code}. Periksa LLM_API_KEY/LLM_MODEL."
            )
        try:
            blocks = resp.json()["content"]
            teks = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
            return teks.strip()
        except (KeyError, TypeError, AttributeError) as exc:
            raise RuntimeError("Respons LLM Anthropic tidak dapat dibaca.") from exc


# ---------------------------------------------------------------------------
# Provider Gemini (generateContent API via httpx)
# ---------------------------------------------------------------------------

class GeminiProvider(LLMProvider):
    """Provider Google Gemini via generateContent API.

    Butuh LLM_API_KEY (gratis dari Google AI Studio) + LLM_MODEL opsional.
    Key dikirim sebagai query param ?key= sesuai API Gemini.
    """

    def __init__(self, api_key: str | None = None) -> None:
        settings = get_settings()
        self.api_key = (api_key or settings.LLM_API_KEY or "").strip()
        if not self.api_key:
            raise RuntimeError("LLM_API_KEY belum dikonfigurasi untuk provider Gemini.")
        self.model = (settings.LLM_MODEL or "gemini-3.5-flash-lite").strip()

    async def narrate(self, kind: str, context: dict) -> str:
        if kind not in NARRATE_KINDS:
            raise ValueError(f"Jenis narasi tidak dikenal: '{kind}'.")
        system, user = _build_prompt(kind, context)
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 1200,
            },
        }
        # Retry 1x untuk error transient (429/503) dengan jeda singkat.
        resp = None
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        url, params={"key": self.api_key}, json=payload
                    )
            except httpx.HTTPError as exc:
                raise RuntimeError(f"Panggilan LLM Gemini gagal: {exc}.") from exc
            if resp.status_code not in (429, 503) or attempt == 1:
                break
            await asyncio.sleep(3)
        assert resp is not None
        if resp.status_code != 200:
            raise RuntimeError(
                f"LLM Gemini mengembalikan HTTP {resp.status_code}. Periksa LLM_API_KEY/LLM_MODEL."
            )
        try:
            data = resp.json()
            if data.get("promptFeedback", {}).get("blockReason"):
                raise RuntimeError(
                    f"Prompt diblokir Gemini: {data['promptFeedback']['blockReason']}."
                )
            cand = data["candidates"][0]
            if cand.get("finishReason") not in (None, "STOP"):
                raise RuntimeError(
                    f"Gemini berhenti dengan alasan: {cand.get('finishReason')}."
                )
            parts = cand["content"]["parts"]
            return "".join(p.get("text", "") for p in parts).strip()
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise RuntimeError("Respons LLM Gemini tidak dapat dibaca.") from exc


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_llm_provider(api_key: str | None = None) -> LLMProvider:
    """Pilih provider dari env LLM_PROVIDER ('mock' default, 'openai', 'anthropic', 'gemini').

    api_key: override eksplisit (dipakai resolver app_settings bila tersedia).
    """
    nama = (get_settings().LLM_PROVIDER or "mock").strip().lower()
    if nama == "mock":
        return MockLLMProvider()
    if nama == "openai":
        return OpenAIProvider(api_key=api_key)
    if nama == "anthropic":
        return AnthropicProvider(api_key=api_key)
    if nama == "gemini":
        return GeminiProvider(api_key=api_key)
    raise ValueError(
        f"LLM_PROVIDER tidak dikenal: '{nama}'. Pilihan: mock, openai, anthropic, gemini."
    )


async def resolve_llm_api_key(db) -> str | None:
    """API key efektif: app_settings 'llm_api_key' didahulukan, lalu env LLM_API_KEY.

    Import get_setting dilakukan lazy agar modul llm tidak bergantung pada
    lapisan DB saat dipakai di konteks tanpa sesi.
    """
    try:
        from app.services.settings import get_setting

        nilai = await get_setting(db, "llm_api_key")
        if nilai:
            return nilai
    except Exception:  # noqa: BLE001 — fallback ke env bila DB tidak tersedia
        pass
    return (get_settings().LLM_API_KEY or "").strip() or None


async def get_llm_provider_for_db(db) -> LLMProvider:
    """Factory untuk konteks yang punya sesi DB (rekomendasi/niche/ringkasan)."""
    return get_llm_provider(api_key=await resolve_llm_api_key(db))
