// Tipe data sesuai kontrak API MySocial Watch.

export interface User {
  id: string;
  name: string;
  email: string;
  whatsapp?: string | null;
  is_active?: boolean;
  is_superadmin: boolean;
  email_verified?: boolean;
}

export interface OrganizationSummary {
  id: string;
  name: string;
  role: string;
  membership_status: string | null;
}

export interface Membership {
  status: string; // active | grace | expired | none
  starts_at: string | null;
  ends_at: string | null;
  grace_ends_at: string | null;
  plan_name: string | null;
}

export interface OrganizationDetail {
  id: string;
  name: string;
  created_at: string;
  membership: Membership | null;
}

export interface Brand {
  id: string;
  name: string;
  platform?: string | null;
  display_name?: string;
  industry?: string | null;
}

export interface OrgMember {
  user_id: string;
  name: string;
  email: string;
  role: string;
}

export interface Plan {
  id: string;
  name: string;
  price: number;
  period_months: number;
  seats: number;
  features: string[];
}

export interface Invoice {
  id: string;
  code: string;
  plan_name: string;
  amount_base: number;
  unique_code: number;
  amount_total: number;
  bank: {
    bank_name: string;
    account_number: string;
    account_name: string;
  };
  status: string;
  expires_at: string;
  payment?: PaymentInfo | null;
}

export interface PaymentInfo {
  id: string;
  status: string; // pending | approved | rejected
  uploaded_at: string;
  file_name: string;
  reason?: string | null;
}

export interface QueuedPayment {
  payment: PaymentInfo;
  invoice: Invoice;
  user: { id: string; name: string; email: string };
  organization: { id: string; name: string };
}

export interface AdminUserRow {
  id: string;
  name: string;
  email: string;
  is_active: boolean;
  is_superadmin: boolean;
  email_verified: boolean;
  created_at?: string;
}

export interface AuditLog {
  id: string;
  created_at: string;
  actor_name?: string | null;
  actor_email?: string | null;
  action: string;
  detail?: string | null;
}

// ============================================================
// Tipe API modul Konten AI (kontrak backend Fase 1).
// ============================================================

export type Platform = "tiktok" | "instagram" | "facebook";
export type PresetPeriode = "7d" | "30d" | "bulan_ini" | "custom";

export interface CsvColumnInfo {
  nama: string;
  deskripsi: string;
  wajib: boolean;
}

export interface UploadResult {
  contents_baru: number;
  contents_diupdate: number;
  metrics_rows: number;
  baris_gagal: { baris: number; alasan: string }[];
  warnings: string[];
}

export interface BatchFileResult {
  filename: string;
  sukses: boolean;
  error: string | null;
  contents_baru: number;
  contents_diupdate: number;
  metrics_rows: number;
  baris_gagal: { baris: number; alasan: string }[];
  warnings: string[];
}

export interface BatchUploadResult {
  files: BatchFileResult[];
  total_baru: number;
  total_diupdate: number;
  total_metrics_rows: number;
  total_baris_gagal: number;
}

export interface PerbandinganDelta {
  bulan_pembanding: string | null;
  views_pct: number | null;
  engagement_pct: number | null;
  jumlah_konten_pct: number | null;
  reach_pct: number | null;
  rata_skor_pct: number | null;
  likes_pct: number | null;
  comments_pct: number | null;
  shares_pct: number | null;
  saves_pct: number | null;
  follows_pct: number | null;
}

export interface PerbandinganBulan {
  bulan: string;
  label: string;
  jumlah_konten: number;
  views: number;
  likes: number;
  comments: number;
  shares: number;
  saves: number;
  follows: number;
  reach: number;
  engagement: number;
  rata_skor: number | null;
  rata_er: number;
  mom: PerbandinganDelta | null;
  yoy: PerbandinganDelta | null;
}

export interface PerbandinganData {
  rentang: { mulai: string; selesai: string };
  platform: string;
  bulan: PerbandinganBulan[];
}

export interface ScoreResult {
  diskor: number;
  periode: string;
}

export interface KartuPlatform {
  jumlah_konten: number;
  rata_skor: number | null;
  rata_er: number | null;
  menang: number;
  cukup: number;
  kurang: number;
}

export type StatusKonten = "MENANG" | "CUKUP" | "KURANG" | "DATA_BELUM_CUKUP";

export interface KontenRow {
  content_id: string;
  post_id: string;
  platform: Platform;
  format: string;
  tujuan: string;
  posted_at: string | null;
  views: number | null;
  er: number | null;
  score: number | null;
  status: StatusKonten;
  labels: string[];
}

export interface BrandDashboard {
  kartu: { tiktok: KartuPlatform; instagram: KartuPlatform; facebook: KartuPlatform };
  tren: { label: string; rata_skor: number | null; rata_er: number | null }[];
  konten: KontenRow[];
}

export interface RingkasanPasangan {
  format: string;
  tujuan: string;
  jumlah: number;
  rata_skor: number | null;
  dominan_status: StatusKonten;
}

export interface Diagnosis {
  metrik: string;
  nilai: string;
  harapan: string;
  masalah: string;
}

export type Verdict = "Sesuai" | "Kurang sesuai" | "Tidak sesuai";

export interface KontenBermasalah {
  content_id: string;
  post_id: string;
  format: string;
  tujuan: string;
  verdict: Verdict;
  diagnoses: Diagnosis[];
  suggestions: string[];
}

export interface AnalisaKesesuaian {
  ringkasan: RingkasanPasangan[];
  bermasalah: KontenBermasalah[];
  rekomendasi_pola: string[];
}

export type TipeRekomendasi = "perbanyak" | "perbaiki" | "kurangi" | "coba_baru" | "umum" | "khusus";
export type StatusRekomendasi = "baru" | "diterima" | "ditolak";

export interface ReferensiKonten {
  post_id: string;
  post_url: string | null;
}

export interface Rekomendasi {
  id: string;
  type: TipeRekomendasi;
  title: string;
  narrative: string;
  evidence: Record<string, unknown> | string;
  reference_content_ids: string[];
  reference_contents?: ReferensiKonten[];
  status: StatusRekomendasi;
  period_start: string | null;
  period_end: string | null;
}

export interface GenerateRekomendasiResult {
  dibuat: Rekomendasi[];
  pesan?: string;
}

export type TipeKartu =
  | "pilihan_tunggal"
  | "pilihan_ganda"
  | "teks"
  | "teks_ganda"
  | "kreator"
  | "kata";

export interface OpsiKartu {
  value: string;
  judul: string;
  deskripsi: string;
}

export interface FieldTeksKartu {
  key: string;
  label: string;
  wajib: boolean;
  placeholder: string;
  contoh: string;
}

export interface InterviewQuestion {
  key: string;
  nomor: number;
  tipe: TipeKartu;
  pertanyaan: string;
  subteks?: string;
  wajib: boolean;
  alasan: string;
  cara_menjawab?: string;
  contoh?: string;
  placeholder?: string;
  opsi?: OpsiKartu[];
  min_pilih?: number;
  fields?: FieldTeksKartu[];
  label_bukti?: string;
  placeholder_bukti?: string;
  min_slot?: number;
  maks_slot?: number;
  min_kata?: number;
  maks_kata?: number;
  placeholder_username?: string;
  placeholder_alasan?: string;
}

export interface Interview {
  id: string;
  brand_id: string;
  current_step: number;
  answers: Record<string, unknown>;
  skipped: string[];
  status: string;
  questions: InterviewQuestion[];
}

export interface JawabResult {
  status: "ok" | "butuh_elaborasi";
  next_step: number;
}

export interface DimensiSkor {
  key: string;
  label: string;
  skor: number;
  maksimal: number;
  alasan: string;
}

export interface SkorNiche {
  dimensi: DimensiSkor[];
  total: number;
  maksimal: number;
  grade: string;
  ringkasan: string;
}

export interface LaporanNiche {
  tujuan: string;
  tujuan_label: string;
  dibuat_pada: string;
  brand: { id: string; nama: string };
  kartu_terjawab: number;
  kartu_total: number;
  kartu_dilewati: string[];
  bagian: Record<string, Record<string, unknown>>;
  skor: SkorNiche;
}

export interface BrandDNA {
  id: string;
  misi: string;
  nilai_inti: string[];
  kepribadian: string;
  positioning_statement: string;
  diferensiasi: string;
  version: number;
  confirmed: boolean;
}

export type LabelSumber = "DATA" | "ESTIMASI" | "KLAIM";

export interface NicheSuggestion {
  id: string;
  name: string;
  match_percent: number;
  alasan: string;
  angles: string[];
  monetisasi: string;
  persaingan: string;
  label_sumber: LabelSumber;
  is_selected: boolean;
}

// ---------------------------------------------------------------------------
// Analisa lanjutan (endpoint /content/brands/{id}/analisa-lanjutan)
// ---------------------------------------------------------------------------

export interface KomposisiEngagement {
  views: number;
  reach: number;
  likes: number;
  comments: number;
  saves: number;
  shares: number;
  follows: number;
  total_engagement: number;
  jumlah_konten: number;
  rata_engagement_per_konten: number;
  rata_er: number;
}

export interface FormatTotal {
  format: string;
  jumlah: number;
  views: number;
  reach: number;
  likes: number;
  comments: number;
  saves: number;
  shares: number;
  follows: number;
  total_engagement: number;
  rata_er: number;
}

export interface OpsiLabel {
  value: string;
  label: string;
}

export interface FilterOptions {
  bulan: OpsiLabel[];
  format: string[];
  kategori: OpsiLabel[];
  cta: OpsiLabel[];
  heuristik: string;
}

export interface KontenDetailItem {
  content_id: string;
  post_id: string;
  tanggal: string;
  format: string;
  caption: string;
  views: number;
  reach: number;
  likes: number;
  comments: number;
  saves: number;
  shares: number;
  follows: number;
  total_engagement: number;
  er: number;
  cta: string[];
  cta_label: string[];
  kategori: string;
  kategori_label: string;
}

export interface SkorKomponen {
  nama: string;
  nilai: number;
  bobot: number;
  penjelasan: string;
}

export interface SkorAkun {
  skor: number;
  grade: string;
  komponen: SkorKomponen[];
  cara_hitung: string;
}

export interface DiagnosisItem {
  tingkat: "kritis" | "perhatian" | "baik";
  judul: string;
  detail: string;
}

export interface SaranItem {
  judul: string;
  detail: string;
  dasar: string;
  contoh: {
    post_id: string;
    post_url?: string | null;
    caption_singkat: string;
    er: number;
    format: string;
  }[];
}

export interface AnalisaLanjutan {
  kosong: boolean;
  komposisi: KomposisiEngagement | null;
  per_format: FormatTotal[];
  filter_options: FilterOptions | null;
  bulan_aktif: string | null;
  detail_bulanan: KontenDetailItem[];
  skor_akun: SkorAkun | null;
  diagnosis: DiagnosisItem[];
  saran: SaranItem[];
}
