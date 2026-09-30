// Lapisan bantuan modul Konten AI.
// Karena backend Fase 1 masih dikerjakan paralel dan belum tersedia saat
// frontend ini dibangun, setiap pemanggilan API dibungkus apiOrDemo:
// bila backend gagal menjawab, halaman memakai DATA CONTOH lokal agar
// tetap bisa dibuka dan diverifikasi.
//
// FLAG: DEMO_FALLBACK = true berarti halaman sedang menampilkan data contoh,
// bukan data nyata. Jangan hapus flag ini sampai backend benar-benar live.

import { api, ApiError } from "./api";
import type {
  AnalisaKesesuaian,
  AnalisaLanjutan,
  Brand,
  BrandDNA,
  BrandDashboard,
  CsvColumnInfo,
  Interview,
  InterviewQuestion,
  LaporanNiche,
  NicheSuggestion,
  PerbandinganBulan,
  PerbandinganData,
  PerbandinganDelta,
  Rekomendasi,
} from "./types";

export const DEMO_FALLBACK = true;

const BRAND_KEY = "dkai_brand_id";

export function getSelectedBrandId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(BRAND_KEY);
}

export function setSelectedBrandId(id: string | null) {
  if (typeof window === "undefined") return;
  if (id) window.localStorage.setItem(BRAND_KEY, id);
  else window.localStorage.removeItem(BRAND_KEY);
}

export interface ApiResult<T> {
  data: T;
  demo: boolean; // true = data contoh (backend belum tersedia)
}

/** Coba panggil API; bila backend tidak terjangkau (network error), pakai data contoh.
 *  Error HTTP dari backend (401/403/404/422/500) TIDAK ditelan — dilempar agar
 *  UI menampilkan pesan error yang sebenarnya, bukan diam-diam memakai data contoh. */
export async function apiOrDemo<T>(
  panggil: () => Promise<T>,
  contoh: T | (() => T | Promise<T>)
): Promise<ApiResult<T>> {
  try {
    const data = await panggil();
    return { data, demo: false };
  } catch (err) {
    // Backend menjawab dengan error HTTP → teruskan, jangan tutupi dengan demo.
    if (err instanceof ApiError) throw err;
    const mentah = typeof contoh === "function" ? (contoh as () => T | Promise<T>)() : contoh;
    const data = mentah instanceof Promise ? await mentah : mentah;
    return { data, demo: DEMO_FALLBACK };
  }
}

// ============================================================
// DATA CONTOH (dipakai hanya bila backend belum tersedia)
// ============================================================

export const demoBrands: Brand[] = [
  { id: "brand-demo-1", name: "@kopisenja", platform: "instagram", display_name: "Instagram @kopisenja", industry: "F&B" },
  { id: "brand-demo-2", name: "@sakinahskincare", platform: "tiktok", display_name: "TikTok @sakinahskincare", industry: "Beauty" },
];

export const demoCsvColumns: CsvColumnInfo[] = [
  { nama: "platform", deskripsi: "Platform: tiktok | instagram", wajib: true },
  { nama: "post_id", deskripsi: "ID unik postingan", wajib: true },
  { nama: "post_url", deskripsi: "URL postingan", wajib: false },
  { nama: "tanggal_posting", deskripsi: "Tanggal posting, format YYYY-MM-DD", wajib: true },
  { nama: "format", deskripsi: "Format: carousel | reels | story | foto | live", wajib: true },
  { nama: "tujuan", deskripsi: "Tujuan: edukasi | hiburan | interaksi | jualan | branding | account_growth", wajib: true },
  { nama: "caption", deskripsi: "Teks caption postingan", wajib: false },
  { nama: "views", deskripsi: "Jumlah tayangan/views", wajib: true },
  { nama: "reach", deskripsi: "Jangkauan unik", wajib: false },
  { nama: "likes", deskripsi: "Jumlah like", wajib: false },
  { nama: "comments", deskripsi: "Jumlah komentar", wajib: false },
  { nama: "shares", deskripsi: "Jumlah share/bagikan", wajib: false },
  { nama: "saves", deskripsi: "Jumlah save/simpan", wajib: false },
  { nama: "avg_watch_seconds", deskripsi: "Rata-rata detik ditonton (video)", wajib: false },
  { nama: "profile_clicks", deskripsi: "Klik profil", wajib: false },
  { nama: "link_clicks", deskripsi: "Klik tautan", wajib: false },
  { nama: "replies", deskripsi: "Balasan (story)", wajib: false },
  { nama: "sticker_taps", deskripsi: "Ketukan stiker (story)", wajib: false },
];

export const demoDashboard: BrandDashboard = {
  kartu: {
    tiktok: {
      jumlah_konten: 42,
      rata_skor: 0.714,
      rata_wer: 0.038,
      menang: 9,
      cukup: 21,
      kurang: 12,
    },
    instagram: {
      jumlah_konten: 35,
      rata_skor: 0.642,
      rata_wer: 0.026,
      menang: 5,
      cukup: 18,
      kurang: 12,
    },
  },
  tren: [
    { label: "Mgg 1", rata_skor: 0.58, rata_wer: 0.024 },
    { label: "Mgg 2", rata_skor: 0.62, rata_wer: 0.029 },
    { label: "Mgg 3", rata_skor: 0.66, rata_wer: 0.031 },
    { label: "Mgg 4", rata_skor: 0.63, rata_wer: 0.027 },
    { label: "Mgg 5", rata_skor: 0.7, rata_wer: 0.034 },
    { label: "Mgg 6", rata_skor: 0.74, rata_wer: 0.039 },
    { label: "Mgg 7", rata_skor: 0.71, rata_wer: 0.035 },
    { label: "Mgg 8", rata_skor: 0.76, rata_wer: 0.041 },
  ],
  konten: [
    { content_id: "c-001", post_id: "TT-92814", platform: "tiktok", format: "video_pendek", tujuan: "awareness", posted_at: "2026-09-20", views: 182400, wer: 0.062, score: 0.88, status: "MENANG", labels: ["winner"] },
    { content_id: "c-002", post_id: "TT-92755", platform: "tiktok", format: "video_pendek", tujuan: "engagement", posted_at: "2026-09-18", views: 96400, wer: 0.051, score: 0.79, status: "MENANG", labels: ["winner"] },
    { content_id: "c-003", post_id: "TT-92601", platform: "tiktok", format: "video_pendek", tujuan: "konversi", posted_at: "2026-09-15", views: 31200, wer: 0.022, score: 0.61, status: "CUKUP", labels: [] },
    { content_id: "c-004", post_id: "TT-92540", platform: "tiktok", format: "live", tujuan: "konversi", posted_at: "2026-09-12", views: 8400, wer: 0.011, score: 0.44, status: "KURANG", labels: [] },
    { content_id: "c-005", post_id: "TT-92412", platform: "tiktok", format: "video_pendek", tujuan: "edukasi", posted_at: "2026-09-10", views: 55800, wer: 0.044, score: 0.76, status: "MENANG", labels: ["winner"] },
    { content_id: "c-006", post_id: "TT-92388", platform: "tiktok", format: "video_pendek", tujuan: "awareness", posted_at: "2026-09-08", views: 12400, wer: 0.016, score: 0.52, status: "KURANG", labels: [] },
    { content_id: "c-007", post_id: "IG-55210", platform: "instagram", format: "carousel", tujuan: "edukasi", posted_at: "2026-09-21", views: 42300, wer: 0.048, score: 0.82, status: "MENANG", labels: ["winner"] },
    { content_id: "c-008", post_id: "IG-55187", platform: "instagram", format: "carousel", tujuan: "awareness", posted_at: "2026-09-19", views: 28700, wer: 0.032, score: 0.68, status: "CUKUP", labels: [] },
    { content_id: "c-009", post_id: "IG-55102", platform: "instagram", format: "foto", tujuan: "konversi", posted_at: "2026-09-16", views: 9100, wer: 0.014, score: 0.47, status: "KURANG", labels: [] },
    { content_id: "c-010", post_id: "IG-55044", platform: "instagram", format: "video_pendek", tujuan: "engagement", posted_at: "2026-09-13", views: 35600, wer: 0.039, score: 0.73, status: "CUKUP", labels: [] },
    { content_id: "c-011", post_id: "IG-54990", platform: "instagram", format: "story", tujuan: "awareness", posted_at: "2026-09-11", views: 6200, wer: null, score: null, status: "DATA_BELUM_CUKUP", labels: [] },
    { content_id: "c-012", post_id: "TT-92301", platform: "tiktok", format: "video_pendek", tujuan: "edukasi", posted_at: "2026-09-06", views: 22100, wer: 0.028, score: 0.64, status: "CUKUP", labels: [] },
  ],
};

export const demoAnalisa: AnalisaKesesuaian = {
  ringkasan: [
    { format: "video_pendek", tujuan: "awareness", jumlah: 14, rata_skor: 0.742, dominan_status: "MENANG" },
    { format: "video_pendek", tujuan: "edukasi", jumlah: 11, rata_skor: 0.705, dominan_status: "CUKUP" },
    { format: "carousel", tujuan: "edukasi", jumlah: 9, rata_skor: 0.728, dominan_status: "MENANG" },
    { format: "video_pendek", tujuan: "konversi", jumlah: 12, rata_skor: 0.551, dominan_status: "KURANG" },
    { format: "foto", tujuan: "konversi", jumlah: 10, rata_skor: 0.513, dominan_status: "KURANG" },
    { format: "live", tujuan: "konversi", jumlah: 6, rata_skor: 0.467, dominan_status: "KURANG" },
  ],
  bermasalah: [
    {
      content_id: "c-004",
      post_id: "TT-92540",
      format: "live",
      tujuan: "konversi",
      verdict: "Tidak sesuai",
      diagnoses: [
        { metrik: "Views", nilai: "8.400", harapan: "≥ 25.000 (median live brand ini)", masalah: "Jangkauan live jauh di bawah median; kemungkinan jam tayang sepi & minim promosi pra-live." },
        { metrik: "Weighted ER", nilai: "1,1%", harapan: "≥ 2,5%", masalah: "Interaksi rendah untuk format live — penonton pasif, sedikit komentar/pertanyaan." },
        { metrik: "Skor", nilai: "44/100", harapan: "≥ 60", masalah: "Skor di bawah ambang CUKUP; konten tidak memenuhi ekspektasi tujuan konversi." },
      ],
      suggestions: [
        "Umumkan live H-1 lewat story + video pendek teaser dengan CTA pengingat.",
        "Siapkan 5 pertanyaan pancingan di 10 menit pertama agar kolom komentar hidup.",
        "Sematkan CTA konversi (link/kode promo) setiap 15 menit, bukan hanya di akhir.",
      ],
    },
    {
      content_id: "c-009",
      post_id: "IG-55102",
      format: "foto",
      tujuan: "konversi",
      verdict: "Kurang sesuai",
      diagnoses: [
        { metrik: "Weighted ER", nilai: "1,4%", harapan: "≥ 2,5%", masalah: "Foto statis kurang memicu interaksi dibanding carousel untuk tujuan konversi." },
        { metrik: "Skor", nilai: "47/100", harapan: "≥ 60", masalah: "Di bawah ambang; pola foto→konversi konsisten underperform di brand ini." },
      ],
      suggestions: [
        "Ubah foto konversi menjadi carousel 3–5 slide: masalah → solusi → bukti → CTA.",
        "Tambahkan testimoni pelanggan pada slide kedua untuk menaikkan kepercayaan.",
      ],
    },
  ],
  rekomendasi_pola: [
    "Perbanyak video pendek edukasi di TikTok: 11 konten dengan rata-rata skor 70,5 — pola paling stabil.",
    "Hentikan sementara format live untuk tujuan konversi sampai ada strategi pra-live yang jelas.",
    "Uji ulang foto konversi sebagai carousel; 10 foto konversi terakhir semuanya di bawah skor 55.",
    "Jadwalkan posting video awareness di jam 19.00–21.00 — 3 winner terakhir semuanya tayang di jam tersebut.",
  ],
};

export const demoRekomendasi: Rekomendasi[] = [
  {
    id: "r-001",
    type: "perbanyak",
    title: "Perbanyak video pendek edukasi di TikTok",
    narrative: "Video pendek edukasi adalah pola paling konsisten menghasilkan skor di atas 70. Audiens merespons penjelasan singkat 30–60 detik jauh lebih baik daripada konten hard selling.",
    evidence: "11 konten • win rate 64% • rata-rata skor 74,2 • rata-rata WER 4,6%",
    reference_content_ids: ["c-005", "c-001", "c-012"],
    status: "baru",
    period_start: "2026-08-26",
    period_end: "2026-09-26",
  },
  {
    id: "r-002",
    type: "perbaiki",
    title: "Perbaiki CTA pada konten konversi",
    narrative: "Konten konversi underperform bukan karena jangkauan, tapi karena CTA lemah: 70% konten konversi tidak menyebut penawaran dalam 5 detik pertama.",
    evidence: "22 konten konversi • win rate 9% • rata-rata skor 52,4",
    reference_content_ids: ["c-003", "c-009"],
    status: "baru",
    period_start: "2026-08-26",
    period_end: "2026-09-26",
  },
  {
    id: "r-003",
    type: "kurangi",
    title: "Kurangi live dadakan tanpa promosi",
    narrative: "Live tanpa teaser H-1 konsisten menghasilkan views di bawah 10 ribu. Energi tim lebih baik dialihkan ke 2 video pendek per sesi live.",
    evidence: "6 konten live • win rate 0% • rata-rata skor 46,7",
    reference_content_ids: ["c-004"],
    status: "baru",
    period_start: "2026-08-26",
    period_end: "2026-09-26",
  },
  {
    id: "r-004",
    type: "coba_baru",
    title: "Coba format 'behind the scene' 15 detik",
    narrative: "Kompetitor sejenis mendapat WER 2× lipat dari konten BTS singkat. Brand ini belum pernah mencoba format ini — risiko rendah, potensi discovery tinggi.",
    evidence: "0 konten brand • benchmark kompetitor: WER 5,8%",
    reference_content_ids: [],
    status: "baru",
    period_start: "2026-08-26",
    period_end: "2026-09-26",
  },
];

export const demoNicheQuestions: InterviewQuestion[] = [
  {
    key: "tujuan", nomor: 1, tipe: "pilihan_tunggal",
    pertanyaan: "Pilih 1 tujuan kamu",
    subteks: "Tujuan menentukan arah seluruh rekomendasi di laporan.",
    wajib: true, alasan: "Akun baru butuh fondasi niche; akun lama butuh analisa data performa.",
    opsi: [
      { value: "bikin_baru", judul: "Bikin akun baru", deskripsi: "Temukan niche dari topik, pengalaman, dan orang yang paling ingin kamu bantu." },
      { value: "pivot", judul: "Pivot atau re-branding", deskripsi: "Analisa akunmu saat ini, lalu temukan arah niche baru yang paling sesuai." },
      { value: "tajamkan", judul: "Tajamkan niche sekarang", deskripsi: "Cari sub-niche, audiens, dan masalah paling kuat dari pola konten yang sudah terbukti." },
    ],
  },
  {
    key: "topik", nomor: 2, tipe: "teks_ganda",
    pertanyaan: "Topik apa yang ingin kamu bahas di kontenmu?",
    wajib: true, alasan: "Satu topik utama yang tajam mengalahkan tiga topik yang tanggung.",
    contoh: "Topik utama: strategi branding yayasan agar dilirik donatur.",
    fields: [
      { key: "utama", label: "1 · Topik utama", wajib: true, placeholder: "mis. tips konten TikTok untuk UMKM pemula", contoh: "" },
      { key: "side_2", label: "2 · Side topic", wajib: false, placeholder: "Topik pendukung (opsional)", contoh: "" },
      { key: "side_3", label: "3 · Side topic", wajib: false, placeholder: "Topik pendukung lain (opsional)", contoh: "" },
    ],
  },
  {
    key: "pengalaman", nomor: 3, tipe: "pilihan_ganda",
    pertanyaan: "Di topik yang kamu sebutkan, kamu punya pengalaman apa?",
    subteks: "Pilih minimal 1. Setiap pilihan wajib disertai bukti singkat.",
    wajib: true, min_pilih: 1,
    alasan: "Kredibilitas niche dibangun dari bukti nyata, bukan sekadar klaim.",
    label_bukti: "Ceritakan bukti singkat",
    placeholder_bukti: "Pengalaman, contoh, hasil, atau kenapa ini nyambung dengan topikmu…",
    opsi: [
      { value: "pengalaman", judul: "Pengalaman", deskripsi: "Hal berat yang pernah kamu lewati, atau orang sering minta bantuanmu soal ini." },
      { value: "pencapaian", judul: "Pencapaian", deskripsi: "Hasil nyata yang pernah kamu raih di topik ini." },
      { value: "passion", judul: "Passion / hobi", deskripsi: "Hal yang terakhir kamu cari di TikTok/YouTube murni karena penasaran." },
      { value: "masalah", judul: "Masalah / keresahan", deskripsi: "Hal yang bikin kamu gemas kalau orang menjelaskannya dengan salah." },
    ],
  },
  {
    key: "target_audiens", nomor: 4, tipe: "teks",
    pertanyaan: "Orang seperti apa yang ingin kamu targetkan?",
    wajib: true, alasan: "Konten yang bicara ke semua orang tidak didengar siapa pun.",
    cara_menjawab: "Sebutkan ciri spesifik: profesi, usia, kondisi, atau komunitasnya.",
    placeholder: "Contoh: fresh graduate yang baru masuk dunia kerja",
  },
  {
    key: "dikenal_untuk", nomor: 5, tipe: "teks",
    pertanyaan: "Biasanya orang cari kamu untuk hal apa?",
    subteks: "Atau: teman-teman ingat kamu jago di bidang apa?",
    wajib: true, alasan: "Reputasi yang sudah ada adalah modal niche yang paling murah.",
    placeholder: "Contoh: dimintai tolong bikin desain presentasi yang rapi",
  },
  {
    key: "harapan_perubahan", nomor: 6, tipe: "teks",
    pertanyaan: "Kalau orang follow kamu, perubahan apa yang kamu harapkan terjadi?",
    subteks: "Opsional, tapi makin jelas harapanmu, makin tajam rekomendasinya.",
    wajib: false, alasan: "Niche yang kuat menjanjikan transformasi yang jelas bagi audiens.",
    placeholder: "Contoh: jadi lebih pede tampil di depan kamera",
  },
  {
    key: "kreator_inspirasi", nomor: 7, tipe: "kreator",
    pertanyaan: "Sebutkan kreator atau akun yang jadi inspirasi kamu",
    subteks: "Minimal 1, maksimal 3. Tulis username (tanpa @) dan kenapa kamu suka.",
    wajib: true, min_slot: 1, maks_slot: 3,
    alasan: "Gaya kreator favoritmu adalah petunjuk selera audiens yang ingin kamu tarik.",
    placeholder_username: "username (tanpa @), mis. karyakreatifid",
    placeholder_alasan: "Kenapa kamu suka gaya kontennya…",
  },
  {
    key: "kata_persona", nomor: 8, tipe: "kata",
    pertanyaan: "Kamu ingin dikenal sebagai orang yang seperti apa?",
    subteks: "Tulis 1–3 kata sifat, satu kata per kotak. Minimal 1 kata.",
    wajib: true, min_kata: 1, maks_kata: 3,
    alasan: "Persona yang konsisten bikin audiens mudah mengingat dan merekomendasikanmu.",
    contoh: "praktis, hangat, punya bukti",
  },
  {
    key: "platform", nomor: 9, tipe: "pilihan_ganda",
    pertanyaan: "Kamu bakal ngonten di platform apa?",
    subteks: "Boleh pilih dua-duanya.",
    wajib: true, min_pilih: 1,
    alasan: "Format dan gaya konten mengikuti kebiasaan tiap platform.",
    opsi: [
      { value: "instagram", judul: "Instagram", deskripsi: "Feed, Reels, Stories, bio." },
      { value: "tiktok", judul: "TikTok", deskripsi: "Short video, hooks, trends." },
    ],
  },
  {
    key: "pantangan", nomor: 10, tipe: "teks",
    pertanyaan: "Apa hal yang kamu tidak mau ada dalam kontenmu?",
    wajib: false, alasan: "Batasan yang jelas menjaga konsistensi persona dan kepercayaan audiens.",
    placeholder: "Misal: kata gue/lo, hard selling, flexing, kata kasar, muncul muka",
  },
  {
    key: "audiens_inggris", nomor: 11, tipe: "pilihan_tunggal",
    pertanyaan: "Mau sekalian jangkau audiens berbahasa Inggris (market global)?",
    subteks: "Opsional. Kalau iya, kami tambahkan referensi kreator global + ide konten bilingual sebagai pelengkap.",
    wajib: false,
    alasan: "Yang works untuk audiens berbahasa Inggris belum tentu seefektif itu untuk audiens Indonesia.",
    opsi: [
      { value: "ya", judul: "Iya, sekalian", deskripsi: "Tambah referensi kreator global + ide konten bilingual." },
      { value: "tidak", judul: "Nggak, fokus Indonesia dulu", deskripsi: "Fokus penuh ke audiens Indonesia." },
    ],
  },
];

export const demoInterview: Interview = {
  id: "interview-demo-1",
  brand_id: "brand-demo-1",
  current_step: 0,
  answers: {},
  skipped: [],
  status: "berjalan",
  questions: demoNicheQuestions,
};

export const demoNicheLaporan: LaporanNiche = {
  tujuan: "bikin_baru",
  tujuan_label: "Bikin akun baru",
  dibuat_pada: "2026-09-30",
  brand: { id: "brand-demo-1", nama: "@kopisenja" },
  kartu_terjawab: 11,
  kartu_total: 11,
  kartu_dilewati: [],
  skor: {
    dimensi: [
      { key: "spesifik", label: "Spesifik", skor: 3, maksimal: 3, alasan: "Target audiens spesifik: detail + penanda jelas." },
      { key: "kredibilitas", label: "Kredibilitas", skor: 2, maksimal: 3, alasan: "Ada bukti pengalaman, tapi bisa diperkuat dengan angka." },
      { key: "cocok_pasar", label: "Cocok pasar", skor: 3, maksimal: 3, alasan: "Topik selaras kuat dengan reputasi yang dikenal orang." },
      { key: "pembeda", label: "Pembeda", skor: 2, maksimal: 3, alasan: "Ada persona, tapi pembeda dari kreator lain belum tajam." },
      { key: "tahan_lama", label: "Tahan lama", skor: 3, maksimal: 3, alasan: "Motivasi jelas + topik yang dinikmati." },
    ],
    total: 13, maksimal: 15, grade: "A",
    ringkasan: "Niche sangat kuat — siap dieksekusi agresif.",
  },
  bagian: {
    ringkasan: {
      judul: "Ringkasan",
      niche_utama: "tips konten TikTok untuk UMKM pemula untuk pemilik UMKM kuliner di Surabaya",
      grade: "A", total_skor: 13,
      kalimat: "Contoh laporan mode demo — isi lengkap tersedia setelah kuesioner diisi via backend.",
      disclaimer: "Laporan ini disusun dari jawaban kuesionermu. Ini panduan strategi, bukan jaminan hasil.",
    },
    temuan_akun: {
      judul: "Temuan akun", mode: "fondasi", sumber: "ESTIMASI",
      narasi: "Kamu memilih bikin akun baru — bagian ini adalah fondasi awal. Setelah 30 hari konsisten posting, kembali dengan tujuan 'Tajamkan niche' agar rekomendasi memakai data nyatamu.",
      yang_dilacak: ["Format konten vs engagement rate", "Topik mana yang paling sering menang", "Jam posting vs performa"],
    },
    pengemasan_konten: {
      judul: "Pengemasan konten",
      hook: ["Buka dengan masalah audiens, bukan perkenalan diri.", "3 detik pertama menentukan — tulis hook dulu sebelum isi."],
      cta: ["Akhiri dengan 1 ajakan jelas: simpan, komen, atau follow."],
      optimasi: ["Konsisten format 30 hari sebelum menilai.", "Pelajari pola hook kreator inspirasimu."],
      inspirasi_gaya: "@karyakreatifid (hook jelas, gaya santai)",
      pantangan: "hard selling, flexing",
    },
    target_market: {
      judul: "Target market",
      kalimat_niche: "tips konten TikTok untuk UMKM pemula untuk pemilik UMKM kuliner di Surabaya",
      siapa: "pemilik UMKM kuliner di Surabaya",
      masalah_mereka: "Mereka butuh bantuan soal: konten TikTok yang konsisten.",
      tujuan_mereka: "UMKM jadi lebih pede tampil di depan kamera",
    },
    positioning: {
      judul: "Positioning",
      opsi: [
        { nama: "Si Praktis", deskripsi: "Dikenal sebagai sosok praktis dalam membahas tips konten.", pembeda: "Pembeda kamu: pengalaman jualan lewat live.", risiko: "Terlalu generik bila tidak didukung bukti konkret." },
        { nama: "Si Hangat", deskripsi: "Dikenal sebagai sosok hangat dalam membahas tips konten.", pembeda: "Pembeda kamu: pengalaman jualan lewat live.", risiko: "Bisa terasa menggurui bila nada tidak dijaga." },
        { nama: "Si Berbukti", deskripsi: "Dikenal sebagai sosok berbukti dalam membahas tips konten.", pembeda: "Pembeda kamu: pengalaman jualan lewat live.", risiko: "Butuh konsistensi lama sebelum audiens percaya." },
      ],
    },
    strategi_transisi: {
      judul: "Strategi transisi", nama: "Fondasi dari nol",
      kenapa_cocok: "Akun baru menang lewat kejelasan, bukan kuantitas.",
      cara_jalan: ["Tetapkan 1 topik utama selama 30 hari.", "Bangun 9-12 konten fondasi.", "Optimasi bio sebelum posting pertama."],
      yang_perlu_diwaspadai: ["Jangan ganti niche sebelum 30 hari konsisten."],
    },
    pilar_konten: {
      judul: "Pilar konten", fase: "Fase A · Validasi Awal",
      mix: [
        { nama: "Topik utama", porsi: 50, keterangan: "Fondasi niche." },
        { nama: "Topik luas", porsi: 20, keterangan: "Jangkau audiens baru." },
        { nama: "Personal life", porsi: 30, keterangan: "Bangun kedekatan." },
      ],
    },
    ide_siap_posting: {
      judul: "Ide siap posting",
      ide: [
        { judul: "3 kesalahan UMKM soal konten TikTok", hook: "Stop lakukan ini…", format: "Reels/TikTok 30 detik", cta: "Simpan buat besok.", tips: "Satu kesalahan satu contoh nyata." },
        { judul: "Cara mulai konten dari nol", hook: "Panduan buat pemula — tanpa ribet.", format: "Reels/TikTok 30 detik", cta: "Follow biar nggak ketinggalan part 2.", tips: "Pecah jadi 3 part." },
      ],
    },
    opsi_bio: {
      judul: "Opsi bio",
      catatan: "Struktur bio yang baik: A = value proposition, B = kredibilitas, C = call to action.",
      opsi: [
        { nama: "Bio A · To the point", baris: ["Bantu UMKM kuliner", "Lewat tips konten TikTok", "👇 Mulai dari sini"], nada: "Langsung dan jelas." },
      ],
    },
    kekuatan_niche: {
      judul: "Kekuatan niche",
      dimensi: [
        { key: "spesifik", label: "Spesifik", skor: 3, maksimal: 3, alasan: "Target audiens spesifik." },
        { key: "kredibilitas", label: "Kredibilitas", skor: 2, maksimal: 3, alasan: "Bukti bisa diperkuat." },
        { key: "cocok_pasar", label: "Cocok pasar", skor: 3, maksimal: 3, alasan: "Topik selaras reputasi." },
        { key: "pembeda", label: "Pembeda", skor: 2, maksimal: 3, alasan: "Pembeda belum tajam." },
        { key: "tahan_lama", label: "Tahan lama", skor: 3, maksimal: 3, alasan: "Motivasi + passion kuat." },
      ],
      total: 13, maksimal: 15, grade: "A", ringkasan: "Niche sangat kuat — siap dieksekusi agresif.",
    },
    swot: {
      judul: "SWOT",
      kekuatan: ["Punya pengalaman di topik ini"],
      kelemahan: ["Belum ada kelemahan menonjol dari jawaban."],
      peluang: ["Audiens Indonesia yang haus konten praktis."],
      ancaman: ["Kreator se-topik dengan tim lebih besar.", "Perubahan algoritma platform."],
    },
    minggu_pertama: {
      judul: "Minggu pertama",
      aksi: [
        { judul: "Pasang bio baru", detail: "Pilih salah satu opsi bio dan pasang hari ini.", level: "Gampang" },
        { judul: "Posting 3 konten pilar", detail: "Ambil 3 ide dari daftar. Satu format, satu gaya.", level: "Sedang" },
        { judul: "Riset 5 kreator se-niche", detail: "Catat 3 hook terbaik tiap kreator inspirasimu.", level: "Gampang" },
      ],
    },
    kesimpulan: {
      judul: "Kesimpulan",
      niche: "tips konten TikTok untuk UMKM pemula untuk pemilik UMKM kuliner di Surabaya",
      grade: "A (13/15)",
      arah_selanjutnya: "Fokus 30 hari pertama: validasi 1 topik utama dengan posting konsisten.",
      langkah_pertama: "Pasang bio baru hari ini, lalu posting konten pertama dari daftar ide siap posting.",
    },
  },
};

/** Label tujuan kuesioner untuk mode demo. */
const DEMO_TUJUAN_LABEL: Record<string, string> = {
  bikin_baru: "Bikin akun baru",
  pivot: "Pivot atau re-branding",
  tajamkan: "Tajamkan niche sekarang",
};

const kapital = (s: string) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);

/**
 * Bangun laporan contoh dari jawaban kuesioner mode demo.
 * Dipakai hanya bila backend belum tersedia — isi penting (niche utama,
 * target market, inspirasi gaya, pantangan, persona, bio) mengikuti jawaban
 * user, bukan data contoh statis.
 */
export function buatLaporanDemo(answers: Record<string, unknown>): LaporanNiche {
  const lap: LaporanNiche = JSON.parse(JSON.stringify(demoNicheLaporan));
  const a = (k: string) => answers[k] as Record<string, unknown> | undefined;
  const teks = (k: string): string => {
    const v = a(k);
    return typeof v?.teks === "string" ? (v.teks as string).trim() : "";
  };

  const tujuan = typeof a("tujuan")?.pilihan === "string" ? (a("tujuan")!.pilihan as string) : "bikin_baru";
  const topik = (a("topik") as { utama?: string; side_2?: string; side_3?: string } | undefined) ?? {};
  const topikUtama = (topik.utama ?? "").trim();
  const audiens = teks("target_audiens");
  const dikenal = teks("dikenal_untuk");
  const harapan = teks("harapan_perubahan");
  const pantangan = teks("pantangan");
  const kreator = (answers["kreator_inspirasi"] as { username?: string; alasan?: string }[] | undefined ?? [])
    .filter((k) => k?.username?.trim())
    .map((k) => `@${k.username!.trim()}${k.alasan?.trim() ? ` (${k.alasan.trim()})` : ""}`);
  const persona = ((answers["kata_persona"] as string[] | undefined) ?? [])
    .map((k) => (k ?? "").trim()).filter(Boolean);

  const nicheUtama = topikUtama && audiens ? `${topikUtama} untuk ${audiens}` : topikUtama || "niche dari jawaban kuesionermu";

  lap.tujuan = tujuan;
  lap.tujuan_label = DEMO_TUJUAN_LABEL[tujuan] ?? lap.tujuan_label;

  const ringkasan = lap.bagian["ringkasan"] as Record<string, unknown>;
  ringkasan["niche_utama"] = nicheUtama;
  ringkasan["kalimat"] = `Contoh laporan (mode demo) untuk niche "${nicheUtama}". Isi mengikuti jawaban kuesionermu — hubungkan backend untuk analisa skor penuh dari data performa.`;

  const target = lap.bagian["target_market"] as Record<string, unknown>;
  target["kalimat_niche"] = nicheUtama;
  if (audiens) target["siapa"] = audiens;
  if (dikenal) target["masalah_mereka"] = `Mereka mengenalimu sebagai orang yang ${dikenal}.`;

  const kemas = lap.bagian["pengemasan_konten"] as Record<string, unknown>;
  if (kreator.length > 0) kemas["inspirasi_gaya"] = kreator.join("; ");
  if (pantangan) kemas["pantangan"] = pantangan;

  if (persona.length > 0) {
    const positioning = lap.bagian["positioning"] as Record<string, unknown>;
    positioning["opsi"] = persona.map((p) => ({
      nama: `Si ${kapital(p)}`,
      deskripsi: `Dikenal sebagai sosok ${p} dalam membahas ${topikUtama || "topikmu"}.`,
      pembeda: dikenal ? `Reputasimu: ${dikenal}.` : "Bangun pembeda dari bukti pengalamanmu.",
      risiko: "Butuh konsistensi sebelum audiens percaya.",
    }));
  }

  const bio = lap.bagian["opsi_bio"] as Record<string, unknown>;
  const opsiBio = bio["opsi"] as { nama: string; baris: string[]; nada: string }[];
  if (opsiBio?.[0]) {
    opsiBio[0] = {
      nama: "Bio A · To the point",
      baris: [
        audiens ? `Bantu ${audiens}` : "Bantu audiensmu",
        topikUtama ? `Lewat ${topikUtama}` : "Lewat konten yang relevan",
        harapan ? `👇 ${harapan}` : "👇 Mulai dari sini",
      ],
      nada: "Langsung dan jelas.",
    };
  }

  const simpulan = lap.bagian["kesimpulan"] as Record<string, unknown>;
  simpulan["niche"] = nicheUtama;

  return lap;
}

export const demoDNA: BrandDNA = {  id: "dna-demo-1",
  misi: "Membantu pecinta kopi rumahan menyeduh kopi seenak kafe tanpa alat mahal.",
  nilai_inti: ["Kejujuran bahan", "Edukasi praktis", "Keakraban komunitas"],
  kepribadian: "Hangat dan apa adanya seperti kakak yang hobi ngopi — santai tapi serius soal rasa.",
  positioning_statement: "Untuk pecinta kopi rumahan, Kopi Senja adalah teman belajar seduh yang jujur dan praktis, berbeda dari brand kopi yang hanya jual gaya hidup.",
  diferensiasi: "Sangrai sendiri setiap pagi dengan biji dari petani lokal — dibuktikan 92% pelanggan kembali karena aroma dan rasa.",
  version: 1,
  confirmed: false,
};

export const demoNiches: NicheSuggestion[] = [
  {
    id: "n-001",
    name: "Edukasi seduh kopi rumahan untuk pemula",
    match_percent: 92,
    alasan: "Selaras dengan misi edukasi praktis dan topik yang paling dikuasai. Kompetitor besar fokus ke gaya hidup, bukan tutorial.",
    angles: [
      "3 kesalahan seduh V60 yang bikin kopi pahit",
      "Racikan kopi susu 15 ribu seenak kafe",
      "Bedah biji: arabika vs robusta untuk pemula",
      "Cara simpan biji kopi agar tahan 1 bulan",
      "Resep es kopi gula aren versi hemat",
      "Kenapa air 90°C lebih enak dari air mendidih?",
      "Review grinder murah di bawah 300 ribu",
      "Rutinitas pagi barista: dari giling sampai seduh",
      "Kuis: tebak daerah asal kopi dari aromanya",
      "Mitos kopi yang masih dipercaya banyak orang",
    ],
    monetisasi: "Kelas online seduh dasar (Rp149rb), langganan biji kopi bulanan, afiliasi alat seduh.",
    persaingan: "Sedang — banyak kreator kopi, tapi sedikit yang fokus murni ke pemula rumahan.",
    label_sumber: "DATA",
    is_selected: false,
  },
  {
    id: "n-002",
    name: "Cerita petani & traceability kopi lokal",
    match_percent: 85,
    alasan: "Menguatkan diferensiasi sangrai sendiri + biji petani lokal. Konten cerita punya retensi tinggi.",
    angles: [
      "Sehari bersama petani kopi di lereng gunung",
      "Perjalanan biji: dari kebun sampai cangkirmu",
      "Kenapa kami bayar petani 20% di atas harga pasar",
      "Panen raya: seperti apa seleksi cherry merah",
      "Wawancara: mimpi petani kopi generasi kedua",
      "Proses natural vs washed, bedanya di rasa",
      "Harga kopi naik? Ini penjelasan jujurnya",
      "Kunjungan ke kebun: musim hujan vs kemarau",
      "Dari gagal panen sampai blend andalan",
      "Test rasa: kopi kebun A vs kebun B",
    ],
    monetisasi: "Paket 'adopt a farm' / pre-order panen, merchandise cerita petani, kemitraan B2B kafe.",
    persaingan: "Rendah–sedang — butuh akses ke kebun, jadi sulit ditiru.",
    label_sumber: "ESTIMASI",
    is_selected: false,
  },
  {
    id: "n-003",
    name: "Eksperimen resep minuman kopi kekinian",
    match_percent: 78,
    alasan: "Sesuai kepribadian yang playful dan topik eksperimen resep. Format eksperimen terbukti viral-friendly.",
    angles: [
      "Bikin es kopi susu kekinian pakai kopi tubruk?",
      "Eksperimen: kopi + rempah dapur, enak atau aneh?",
      "Duplikat menu kafe mahal versi 10 ribu",
      "Battle: susu UHT vs susu oat untuk latte",
      "Resep dalgona versi tidak terlalu manis",
      "Kopi mocktail untuk yang tidak suka pahit",
      "Uji coba 5 gula aren berbeda, mana juaranya?",
      "Minuman kopi 2 bahan untuk anak kos",
      "Es kopi klepon: gimmick atau legit?",
      "Resep andalan pelanggan, kami buatkan ulang",
    ],
    monetisasi: "Ebook 50 resep (Rp49rb), endorsement bahan, kelas kreasi menu untuk UMKM.",
    persaingan: "Tinggi — banyak kreator resep; menang lewat angle eksperimen jujur + data rasa.",
    label_sumber: "DATA",
    is_selected: false,
  },
  {
    id: "n-004",
    name: "Komunitas & gaya hidup slow morning",
    match_percent: 70,
    alasan: "Cocok dengan kepribadian hangat, tapi monetisasi tidak langsung dan persaingan gaya hidup sangat padat.",
    angles: [
      "Rutinitas pagi 15 menit sebelum kerja",
      "Sudut ngopi favorit pelanggan kami",
      "Playlist jazz untuk teman ngopi pagi",
      "Journaling ditemani kopi: panduan 5 menit",
      "Cerita pelanggan: kenangan dengan secangkir kopi",
      "Rekomendasi buku ringan untuk weekend",
      "Slow living di tengah target kerja",
      "Foto flatlay kopi: tips komposisi sederhana",
      "Ngobrol santai: apa arti 'cukup' bagimu?",
      "Morning routine 3 generasi dalam 1 keluarga",
    ],
    monetisasi: "Tidak langsung — cocok untuk brand awareness, monetisasi via produk utama.",
    persaingan: "Sangat tinggi — ranah lifestyle creator besar.",
    label_sumber: "KLAIM",
    is_selected: false,
  },
  {
    id: "n-005",
    name: "Review jujur alat & biji kopi budget",
    match_percent: 88,
    alasan: "Memanfaatkan nilai kejujuran + keunggulan teknis. Konten review punya search intent kuat dan afiliasi jelas.",
    angles: [
      "Grinder 200 ribuan, layak atau buang uang?",
      "Biji kopi supermarket vs specialty, blind test",
      "Review French press termurah di marketplace",
      "Alat seduh wajib vs gimmick: panduan hemat",
      "Biji kopi 100 ribuan yang rasanya premium",
      "Unboxing paket starter ngopi di rumah",
      "Skala dapur untuk kopi: perlu atau tidak?",
      "Perbandingan dripper plastik vs keramik",
      "Kopi sachet premium: ada yang enak?",
      "Setup ngopi rumahan total 500 ribu",
    ],
    monetisasi: "Afiliasi marketplace (komisi 4–10%), sponsored review, panduan pembelian premium.",
    persaingan: "Sedang — butuh kredibilitas rasa yang sudah dimiliki brand.",
    label_sumber: "ESTIMASI",
    is_selected: false,
  },
  {
    id: "n-006",
    name: "Kopi & kesehatan: fakta tanpa nakut-nakuti",
    match_percent: 64,
    alasan: "Topik dicari, tapi butuh kehati-hatian klaim kesehatan dan agak jauh dari diferensiasi utama.",
    angles: [
      "Berapa cangkir kopi yang aman per hari?",
      "Kopi dan asam lambung: fakta vs mitos",
      "Kafein dan kualitas tidur, penjelasan sains ringan",
      "Kopi hitam vs kopi susu: mana lebih sehat?",
      "Kenapa kopi bikin deg-degan? Ini sebabnya",
      "Alternatif kopi untuk yang sensitif kafein",
      "Manfaat kopi menurut riset terbaru",
      "Waktu terbaik minum kopi menurut sains",
      "Kopi decaf: beneran tanpa kafein?",
      "Tanya jawab: mitos kopi dari followers",
    ],
    monetisasi: "Ebook panduan, kolaborasi brand wellness, konsultasi menu sehat untuk kafe.",
    persaingan: "Sedang — butuh riset agar tidak menyebar misinformasi.",
    label_sumber: "KLAIM",
    is_selected: false,
  },
];

/** Data demo perbandingan MoM/YoY: 12 bulan sintetis dengan delta terisi sebagian. */
export function demoPerbandingan(): Promise<PerbandinganData> {
  const namaBulan = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
  const sekarang = new Date();
  const historis: {
    views: number;
    engagement: number;
    jumlah_konten: number;
    reach: number;
    rata_skor: number;
    likes: number;
    comments: number;
    shares: number;
    saves: number;
    follows: number;
  }[] = [];
  for (let i = 23; i >= 0; i--) {
    const faktor = 1 + Math.sin(i / 2.4) * 0.35 + (23 - i) * 0.03;
    const views = Math.round(12000 * faktor);
    const engagement = Math.round(views * 0.06 * (1 + Math.sin(i) * 0.15));
    historis.push({
      views,
      engagement,
      jumlah_konten: 8 + (i % 5),
      reach: Math.round(views * 0.8),
      rata_skor: 0.55 + Math.sin(i / 3) * 0.15,
      likes: Math.round(engagement * 0.6),
      comments: Math.round(engagement * 0.2),
      shares: Math.round(engagement * 0.12),
      saves: Math.round(engagement * 0.08),
      follows: Math.round(engagement * 0.05),
    });
  }
  const bulan: PerbandinganBulan[] = [];
  for (let i = 0; i < 12; i++) {
    const idx = i + 12; // 12 bulan tampilan = paruh kedua historis
    const h = historis[idx];
    const d = new Date(sekarang.getFullYear(), sekarang.getMonth() - (11 - i), 1);
    const kunci = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    const momH = historis[idx - 1];
    const yoyH = i === 0 ? null : historis[idx - 12];
    const delta = (cur: number, prev: number | null | undefined): number | null =>
      prev === null || prev === undefined || prev === 0
        ? null
        : Math.round(((cur - prev) / prev) * 1000) / 10;
    const mom: PerbandinganDelta = {
      bulan_pembanding: momH ? `${d.getFullYear()}-${String(d.getMonth()).padStart(2, "0")}` : null,
      views_pct: delta(h.views, momH?.views),
      engagement_pct: delta(h.engagement, momH?.engagement),
      jumlah_konten_pct: delta(h.jumlah_konten, momH?.jumlah_konten),
      reach_pct: delta(h.reach, momH?.reach),
      rata_skor_pct: delta(h.rata_skor, momH?.rata_skor),
      likes_pct: delta(h.likes, momH?.likes),
      comments_pct: delta(h.comments, momH?.comments),
      shares_pct: delta(h.shares, momH?.shares),
      saves_pct: delta(h.saves, momH?.saves),
      follows_pct: delta(h.follows, momH?.follows),
    };
    const yoy: PerbandinganDelta = {
      bulan_pembanding: yoyH ? `${d.getFullYear() - 1}-${String(d.getMonth() + 1).padStart(2, "0")}` : null,
      views_pct: delta(h.views, yoyH?.views),
      engagement_pct: delta(h.engagement, yoyH?.engagement),
      jumlah_konten_pct: delta(h.jumlah_konten, yoyH?.jumlah_konten),
      reach_pct: delta(h.reach, yoyH?.reach),
      rata_skor_pct: delta(h.rata_skor, yoyH?.rata_skor),
      likes_pct: delta(h.likes, yoyH?.likes),
      comments_pct: delta(h.comments, yoyH?.comments),
      shares_pct: delta(h.shares, yoyH?.shares),
      saves_pct: delta(h.saves, yoyH?.saves),
      follows_pct: delta(h.follows, yoyH?.follows),
    };
    bulan.push({
      bulan: kunci,
      label: `${namaBulan[d.getMonth()]} ${d.getFullYear()}`,
      jumlah_konten: h.jumlah_konten,
      views: h.views,
      likes: h.likes,
      comments: h.comments,
      shares: h.shares,
      saves: h.saves,
      follows: h.follows,
      reach: h.reach,
      engagement: h.engagement,
      rata_skor: Math.round(h.rata_skor * 100) / 100,
      rata_wer: 0.06,
      mom,
      yoy,
    });
  }
  return Promise.resolve({
    rentang: { mulai: bulan[0].bulan + "-01", selesai: "demo" },
    platform: "semua",
    bulan,
  });
}

/** Data contoh untuk seksi analisa lanjutan (dipakai bila backend tak menjawab). */
export function demoAnalisaLanjutan(): Promise<AnalisaLanjutan> {
  const sekarang = new Date();
  const kunciBulan = `${sekarang.getFullYear()}-${String(sekarang.getMonth() + 1).padStart(2, "0")}`;
  const labelBulan = sekarang.toLocaleDateString("id-ID", { month: "short", year: "numeric" });
  const detail = [
    {
      content_id: "demo-1",
      post_id: "DcyaotLP3_M",
      tanggal: `${kunciBulan}-12`,
      format: "reels",
      caption:
        "Alhamdulillah, amanah kebaikan kembali tersampaikan untuk warga terdampak gempa. Salurkan donasi terbaikmu melalui link di bio. Like, save, dan share ke teman-temanmu!",
      views: 5291,
      reach: 4213,
      likes: 224,
      comments: 15,
      saves: 12,
      shares: 31,
      follows: 8,
      total_engagement: 282,
      wer: 0.0533,
      cta: ["konversi", "link_bio", "share", "simpan", "like"],
      cta_label: ["Donasi / Beli / Daftar", "Link di bio", "Share / Tag", "Simpan", "Like"],
      kategori: "donasi_sosial",
      kategori_label: "Donasi & Aksi Sosial",
    },
    {
      content_id: "demo-2",
      post_id: "DcvLhuCj4CZ",
      tanggal: `${kunciBulan}-05`,
      format: "carousel",
      caption:
        "5 tips healing untuk pikiran yang penuh. Simpan dulu biar bisa dibaca ulang. Komen pendapatmu di bawah ya!",
      views: 2161,
      reach: 1659,
      likes: 105,
      comments: 12,
      saves: 55,
      shares: 22,
      follows: 3,
      total_engagement: 194,
      wer: 0.0897,
      cta: ["simpan", "komentar"],
      cta_label: ["Simpan", "Komentar"],
      kategori: "edukasi",
      kategori_label: "Edukasi",
    },
  ];
  return Promise.resolve({
    kosong: false,
    komposisi: {
      views: 7452,
      reach: 5872,
      likes: 329,
      comments: 27,
      saves: 67,
      shares: 53,
      follows: 11,
      total_engagement: 476,
      jumlah_konten: 2,
      rata_engagement_per_konten: 238,
      rata_wer: 0.0715,
    },
    per_format: [
      {
        format: "reels",
        jumlah: 1,
        views: 5291,
        reach: 4213,
        likes: 224,
        comments: 15,
        saves: 12,
        shares: 31,
        follows: 8,
        total_engagement: 282,
        rata_wer: 0.0533,
      },
      {
        format: "carousel",
        jumlah: 1,
        views: 2161,
        reach: 1659,
        likes: 105,
        comments: 12,
        saves: 55,
        shares: 22,
        follows: 3,
        total_engagement: 194,
        rata_wer: 0.0897,
      },
    ],
    filter_options: {
      bulan: [{ value: kunciBulan, label: labelBulan }],
      format: ["reels", "carousel"],
      kategori: [
        { value: "donasi_sosial", label: "Donasi & Aksi Sosial" },
        { value: "edukasi", label: "Edukasi" },
      ],
      cta: [
        { value: "konversi", label: "Donasi / Beli / Daftar" },
        { value: "simpan", label: "Simpan" },
        { value: "komentar", label: "Komentar" },
      ],
      heuristik:
        "CTA & kategori terdeteksi otomatis dari kata kunci caption (heuristik, bukan klasifikasi manual).",
    },
    bulan_aktif: kunciBulan,
    detail_bulanan: detail,
    skor_akun: {
      skor: 6.8,
      grade: "Baik",
      komponen: [
        {
          nama: "Kualitas engagement",
          nilai: 9.5,
          bobot: 0.3,
          penjelasan: "Rata-rata WER 7,1% vs baseline sehat 5% (skor penuh pada 1,5× baseline).",
        },
        {
          nama: "Volume & konsistensi",
          nilai: 2.8,
          bobot: 0.2,
          penjelasan: "1,4 postingan/minggu (skor penuh pada ≥5/minggu).",
        },
        {
          nama: "Tren pertumbuhan",
          nilai: 5,
          bobot: 0.25,
          penjelasan: "belum cukup data bulanan untuk tren",
        },
        {
          nama: "Proporsi konten kuat",
          nilai: 6.7,
          bobot: 0.25,
          penjelasan: "2 dari 2 konten yang diskor berstatus menang/cukup (100%; skor penuh pada ≥30%).",
        },
      ],
      cara_hitung:
        "Skor 1–10 gabungan empat komponen berbobot: kualitas engagement (30%), volume & konsistensi (20%), tren pertumbuhan (25%), proporsi konten kuat (25%).",
    },
    diagnosis: [
      {
        tingkat: "baik",
        judul: "Engagement di atas baseline",
        detail: "Rata-rata WER 7,1% sudah melewati baseline. Pertahankan polanya.",
      },
      {
        tingkat: "perhatian",
        judul: "Frekuensi posting rendah",
        detail:
          "Hanya 1,4 postingan/minggu. Algoritma dan audiens butuh keteraturan — targetkan minimal 3–5 postingan/minggu.",
      },
    ],
    saran: [
      {
        judul: "Perbanyak format carousel",
        detail:
          "1 dari 2 konten terbaik adalah carousel (rata-rata WER 9,0%). Jadikan format utama minggu ini.",
        dasar: "Berdasarkan 2 konten terbaik (10% WER teratas, min. 500 views).",
        contoh: [
          {
            post_id: "DcvLhuCj4CZ",
            caption_singkat: "5 tips healing untuk pikiran yang penuh. Simpan dulu biar bisa dibaca ulang…",
            wer: 9.0,
            format: "carousel",
          },
        ],
      },
    ],
  });
}
