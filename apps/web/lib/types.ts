// Tipe data sesuai kontrak API Dashboard Konten AI.

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

export type Platform = "tiktok" | "instagram";
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
  reach: number;
  engagement: number;
  rata_skor: number | null;
  rata_wer: number;
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
  rata_wer: number | null;
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
  wer: number | null;
  score: number | null;
  status: StatusKonten;
  labels: string[];
}

export interface BrandDashboard {
  kartu: { tiktok: KartuPlatform; instagram: KartuPlatform };
  tren: { label: string; rata_skor: number | null; rata_wer: number | null }[];
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

export type TipeRekomendasi = "perbanyak" | "perbaiki" | "kurangi" | "coba_baru";
export type StatusRekomendasi = "baru" | "diterima" | "ditolak";

export interface Rekomendasi {
  id: string;
  type: TipeRekomendasi;
  title: string;
  narrative: string;
  evidence: string;
  reference_content_ids: string[];
  status: StatusRekomendasi;
  period_start: string | null;
  period_end: string | null;
}

export interface GenerateRekomendasiResult {
  dibuat: Rekomendasi[];
  pesan?: string;
}

export interface InterviewQuestion {
  key: string;
  pertanyaan: string;
  alasan: string;
  cara_menjawab: string;
  contoh: string;
}

export interface Interview {
  id: string;
  brand_id: string;
  current_step: number;
  answers: Record<string, string>;
  skipped: string[];
  status: string;
  questions: InterviewQuestion[];
}

export interface JawabResult {
  status: "ok" | "butuh_elaborasi";
  next_step: number;
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
