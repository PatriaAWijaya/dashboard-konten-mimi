"""Schema API modul konten (Pydantic v2). Deskripsi dalam Bahasa Indonesia."""

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PRESET_PERIODE = ("7d", "30d", "90d", "bulan_ini", "12bln", "custom")


class PeriodeIn(BaseModel):
    """Periode analisis: preset cepat atau rentang custom (maks 12 bulan)."""

    preset: str = Field(default="30d", description="Preset periode: 7d, 30d, 90d, bulan_ini, 12bln, custom.")
    start: date | None = Field(default=None, description="Tanggal mulai (wajib bila preset=custom).")
    end: date | None = Field(default=None, description="Tanggal selesai (wajib bila preset=custom).")

    @field_validator("preset")
    @classmethod
    def _preset_valid(cls, v: str) -> str:
        if v not in PRESET_PERIODE:
            raise ValueError(f"Preset tidak valid. Pilihan: {', '.join(PRESET_PERIODE)}.")
        return v

    @model_validator(mode="after")
    def _custom_valid(self):
        if self.preset == "custom":
            if not self.start or not self.end:
                raise ValueError("Preset 'custom' wajib menyertakan start dan end.")
            if self.start > self.end:
                raise ValueError("Tanggal mulai tidak boleh setelah tanggal selesai.")
            if (self.end - self.start).days > 366:
                raise ValueError("Rentang custom maksimal 12 bulan.")
        return self


class CsvFormatColumn(BaseModel):
    nama: str = Field(description="Nama kolom di file CSV.")
    deskripsi: str = Field(description="Penjelasan isi kolom.")
    wajib: bool = Field(description="True bila kolom wajib diisi.")


class CsvUploadOut(BaseModel):
    contents_baru: int = Field(description="Jumlah konten baru yang dibuat.")
    contents_diupdate: int = Field(description="Jumlah konten yang datanya diperbarui.")
    metrics_rows: int = Field(description="Jumlah baris metrik harian yang disimpan.")
    baris_gagal: list = Field(description="Daftar baris gagal {baris, alasan}.")
    warnings: list[str] = Field(description="Peringatan non-fatal selama import.")
    kolom: list[str] = Field(description="Daftar kolom CSV yang diharapkan (dokumentasi).")


class ScoreOut(BaseModel):
    diskor: int = Field(description="Jumlah konten yang berhasil diskor.")
    periode: dict = Field(description="Periode skoring {mulai, selesai}.")


class DashboardKartu(BaseModel):
    jumlah_konten: int
    rata_skor: float
    rata_wer: float
    menang: int
    cukup: int
    kurang: int


class DashboardTren(BaseModel):
    label: str = Field(description="Label minggu, mis. W1, W2.")
    rata_skor: float
    rata_wer: float


class DashboardKontenItem(BaseModel):
    content_id: uuid.UUID
    post_id: str
    platform: str
    format: str | None
    tujuan: str | None
    posted_at: datetime | None
    views: int = Field(description="Views agregat dari snapshot skor.")
    wer: float = Field(description="Weighted engagement rate dari snapshot skor.")
    score: float | None
    status: str
    labels: list[str]


class DashboardOut(BaseModel):
    kartu: dict[str, DashboardKartu] = Field(description="Agregat per platform: tiktok, instagram.")
    tren: list[DashboardTren] = Field(description="Agregasi mingguan skor & WER.")
    konten: list[DashboardKontenItem] = Field(description="Daftar konten terperinci.")


class AnalisaOut(BaseModel):
    ringkasan: list = Field(description="Ringkasan per pola (format, tujuan).")
    bermasalah: list = Field(description="Pola/konten yang bermasalah.")
    rekomendasi_pola: list = Field(description="Rekomendasi pola dari analisa.")


class BatchFileOut(BaseModel):
    filename: str = Field(description="Nama file dalam batch.")
    sukses: bool = Field(description="True bila file berhasil diproses.")
    error: str | None = Field(default=None, description="Pesan error bila gagal.")
    contents_baru: int = 0
    contents_diupdate: int = 0
    metrics_rows: int = 0
    baris_gagal: list = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class BatchUploadOut(BaseModel):
    files: list[BatchFileOut] = Field(description="Hasil per file.")
    total_baru: int = Field(description="Total konten baru dari seluruh file.")
    total_diupdate: int = Field(description="Total konten diupdate dari seluruh file.")
    total_metrics_rows: int = Field(description="Total baris metrik dari seluruh file.")
    total_baris_gagal: int = Field(description="Total baris gagal dari seluruh file.")
    kolom: list[str] = Field(description="Daftar kolom CSV yang diharapkan (dokumentasi).")


class PerbandinganDelta(BaseModel):
    """Perubahan persen satu metrik vs bulan pembanding (None = data pembanding tidak ada)."""

    bulan_pembanding: str | None = Field(description="Bulan pembanding (YYYY-MM) atau None.")
    views_pct: float | None = None
    engagement_pct: float | None = None
    jumlah_konten_pct: float | None = None
    reach_pct: float | None = None
    rata_skor_pct: float | None = None
    likes_pct: float | None = None
    comments_pct: float | None = None
    shares_pct: float | None = None
    saves_pct: float | None = None
    follows_pct: float | None = None


class PerbandinganBulan(BaseModel):
    bulan: str = Field(description="Bulan (YYYY-MM).")
    label: str = Field(description="Label bulan, mis. 'Jul 2026'.")
    jumlah_konten: int = 0
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    saves: int = 0
    follows: int = 0
    reach: int = 0
    engagement: int = Field(default=0, description="likes+comments+shares+saves.")
    rata_skor: float | None = None
    rata_wer: float = 0.0
    mom: PerbandinganDelta | None = Field(default=None, description="Perbandingan month-on-month.")
    yoy: PerbandinganDelta | None = Field(default=None, description="Perbandingan year-on-year.")


class PerbandinganOut(BaseModel):
    rentang: dict = Field(description="Rentang tampilan {mulai, selesai}.")
    platform: str = Field(description="Filter platform yang dipakai.")
    bulan: list[PerbandinganBulan] = Field(description="Deret bulanan kronologis.")


class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str = Field(description="Jenis: perbanyak, kurangi, perbaiki, coba_baru.")
    title: str = Field(description="Judul rekomendasi.")
    narrative: str = Field(description="Narasi rekomendasi (dari LLM, berbasis angka bukti).")
    evidence: dict = Field(description="Angka bukti: n, win_rate, avg_score, avg_wer, contoh, format, tujuan.")
    reference_content_ids: list = Field(description="Contoh post_id pendukung.")
    status: str = Field(description="Status: baru, diterima, ditolak.")
    period_start: date | None
    period_end: date | None
    config_version: int | None
    created_at: datetime


class GenerateOut(BaseModel):
    dibuat: list[RecommendationOut] = Field(description="Rekomendasi yang dibuat/ditemukan.")
    pesan: str | None = Field(default=None, description="Pesan bila tidak ada rekomendasi dibuat.")


class InterviewStartOut(BaseModel):
    id: uuid.UUID
    status: str
    current_step: int = Field(description="Indeks kartu berikutnya (0-10).")
    pertanyaan_berikut: dict | None = Field(description="Kartu berikutnya bila masih berjalan.")


class InterviewDetailOut(BaseModel):
    id: uuid.UUID
    status: str
    current_step: int
    answers: dict = Field(description="Jawaban terstruktur per key kartu.")
    skipped: list[str] = Field(description="Key kartu yang dilewati.")
    questions: list[dict] = Field(description="11 kartu kuesioner niche finder.")


class JawabIn(BaseModel):
    step: int = Field(ge=0, le=10, description="Indeks kartu (0-10).")
    jawaban: Any = Field(
        default=None,
        description="Jawaban terstruktur (dict/list) sesuai tipe kartu.",
    )
    dilewati: bool = Field(default=False, description="True bila kartu dilewati.")


class JawabOut(BaseModel):
    status: str = Field(description="'ok' atau 'butuh_elaborasi'.")
    next_step: int = Field(description="Kartu berikutnya.")
    pertanyaan_berikut: dict | None = Field(default=None, description="Kartu berikutnya/elaborasi.")


class LaporanNicheOut(BaseModel):
    laporan: dict = Field(description="Laporan strategi niche 13 bagian + skor.")


class PilihNicheIn(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=2, description="1-2 ID niche yang dipilih.")


class KomposisiEngagement(BaseModel):
    views: int
    reach: int
    likes: int
    comments: int
    saves: int
    shares: int
    follows: int
    total_engagement: int = Field(description="likes+comments+saves+shares.")
    jumlah_konten: int
    rata_engagement_per_konten: float
    rata_wer: float = Field(description="Rata-rata weighted engagement rate (fraksi).")


class FormatTotal(BaseModel):
    format: str
    jumlah: int
    views: int
    reach: int
    likes: int
    comments: int
    saves: int
    shares: int
    follows: int
    total_engagement: int
    rata_wer: float


class OpsiLabel(BaseModel):
    value: str
    label: str


class FilterOptions(BaseModel):
    bulan: list[OpsiLabel]
    format: list[str]
    kategori: list[OpsiLabel]
    cta: list[OpsiLabel]
    heuristik: str = Field(description="Penjelasan bahwa CTA & kategori terdeteksi heuristik.")


class KontenDetailItem(BaseModel):
    content_id: uuid.UUID
    post_id: str
    tanggal: str
    format: str
    caption: str
    views: int
    reach: int
    likes: int
    comments: int
    saves: int
    shares: int
    follows: int
    total_engagement: int
    wer: float
    cta: list[str]
    cta_label: list[str]
    kategori: str
    kategori_label: str


class SkorKomponen(BaseModel):
    nama: str
    nilai: float = Field(description="0-10.")
    bobot: float
    penjelasan: str


class SkorAkun(BaseModel):
    skor: float = Field(description="Skor performa akun 1-10.")
    grade: str
    komponen: list[SkorKomponen]
    cara_hitung: str


class DiagnosisItem(BaseModel):
    tingkat: str = Field(description="kritis | perhatian | baik.")
    judul: str
    detail: str


class SaranItem(BaseModel):
    judul: str
    detail: str
    dasar: str = Field(description="Data yang mendasari saran.")
    contoh: list = Field(default_factory=list, description="Contoh konten terbaik bila ada.")


class AnalisaLanjutanOut(BaseModel):
    kosong: bool = False
    komposisi: KomposisiEngagement | None = None
    per_format: list[FormatTotal] = Field(default_factory=list)
    filter_options: FilterOptions | None = None
    bulan_aktif: str | None = None
    detail_bulanan: list[KontenDetailItem] = Field(default_factory=list)
    skor_akun: SkorAkun | None = None
    diagnosis: list[DiagnosisItem] = Field(default_factory=list)
    saran: list[SaranItem] = Field(default_factory=list)
