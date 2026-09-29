"""Schema API modul konten (Pydantic v2). Deskripsi dalam Bahasa Indonesia."""

import uuid
from datetime import date, datetime

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


class PerbandinganBulan(BaseModel):
    bulan: str = Field(description="Bulan (YYYY-MM).")
    label: str = Field(description="Label bulan, mis. 'Jul 2026'.")
    jumlah_konten: int = 0
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    saves: int = 0
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
    current_step: int = Field(description="Indeks langkah berikutnya (0-7).")
    pertanyaan_berikut: dict | None = Field(description="Pertanyaan berikutnya bila masih berjalan.")


class InterviewDetailOut(BaseModel):
    id: uuid.UUID
    status: str
    current_step: int
    answers: dict = Field(description="Jawaban per key pertanyaan.")
    skipped: list[str] = Field(description="Key pertanyaan yang dilewati.")
    questions: list[dict] = Field(description="8 pertanyaan wawancara + panduan.")


class JawabIn(BaseModel):
    step: int = Field(ge=0, le=7, description="Indeks langkah (0-7).")
    jawaban: str | None = Field(default=None, description="Isi jawaban.")
    dilewati: bool = Field(default=False, description="True bila pertanyaan dilewati.")


class JawabOut(BaseModel):
    status: str = Field(description="'ok' atau 'butuh_elaborasi'.")
    next_step: int = Field(description="Langkah berikutnya.")
    pertanyaan_berikut: dict | None = Field(default=None, description="Pertanyaan berikutnya/elaborasi.")


class DnaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    misi: str
    nilai_inti: list[str]
    kepribadian: str
    positioning_statement: str
    diferensiasi: str
    confirmed: bool
    created_at: datetime


class NicheSaranOut(BaseModel):
    saran: list["NicheOut"] = Field(description="Daftar saran niche.")
    dibuat_baru: bool = Field(description="True bila saran baru saja dibuat.")


class NicheOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    match_percent: int = Field(description="Kecocokan 0-100 berdasar kata kunci jawaban.")
    alasan: str
    angles: list[str] = Field(description="10 angle konten.")
    monetisasi: str
    persaingan: str = Field(description="rendah, sedang, atau tinggi.")
    label_sumber: str = Field(description="DATA, ESTIMASI, atau KLAIM.")
    is_selected: bool


class PilihNicheIn(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=2, description="1-2 ID niche yang dipilih.")
