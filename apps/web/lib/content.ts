// Lapisan bantuan modul Konten AI.
// Karena backend Fase 1 masih dikerjakan paralel dan belum tersedia saat
// frontend ini dibangun, setiap pemanggilan API dibungkus apiOrDemo:
// bila backend gagal menjawab, halaman memakai DATA CONTOH lokal agar
// tetap bisa dibuka dan diverifikasi.
//
// FLAG: DEMO_FALLBACK = true berarti halaman sedang menampilkan data contoh,
// bukan data nyata. Jangan hapus flag ini sampai backend benar-benar live.

import { api } from "./api";
import type {
  AnalisaKesesuaian,
  Brand,
  BrandDNA,
  BrandDashboard,
  CsvColumnInfo,
  Interview,
  NicheSuggestion,
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

/** Coba panggil API; bila gagal (backend belum siap), pakai data contoh. */
export async function apiOrDemo<T>(
  panggil: () => Promise<T>,
  contoh: T | (() => T | Promise<T>)
): Promise<ApiResult<T>> {
  try {
    const data = await panggil();
    return { data, demo: false };
  } catch {
    const mentah = typeof contoh === "function" ? (contoh as () => T | Promise<T>)() : contoh;
    const data = mentah instanceof Promise ? await mentah : mentah;
    return { data, demo: DEMO_FALLBACK };
  }
}

// ============================================================
// DATA CONTOH (dipakai hanya bila backend belum tersedia)
// ============================================================

export const demoBrands: Brand[] = [
  { id: "brand-demo-1", name: "Kopi Senja (Demo)", industry: "F&B" },
  { id: "brand-demo-2", name: "Sakinah Skincare (Demo)", industry: "Beauty" },
];

export const demoCsvColumns: CsvColumnInfo[] = [
  { nama: "platform", deskripsi: "Platform: tiktok | instagram", wajib: true },
  { nama: "post_id", deskripsi: "ID unik postingan", wajib: true },
  { nama: "post_url", deskripsi: "URL postingan", wajib: false },
  { nama: "tanggal_posting", deskripsi: "Tanggal posting, format YYYY-MM-DD", wajib: true },
  { nama: "format", deskripsi: "Format: video_pendek | carousel | foto | live | story", wajib: true },
  { nama: "tujuan", deskripsi: "Tujuan: awareness | edukasi | interaksi | branding | jualan", wajib: true },
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

export const demoInterview: Interview = {
  id: "interview-demo-1",
  brand_id: "brand-demo-1",
  current_step: 1,
  answers: {},
  skipped: [],
  status: "berjalan",
  questions: [
    {
      key: "misi",
      pertanyaan: "Apa misi brand Anda dalam satu kalimat? Masalah apa yang ingin Anda selesaikan untuk audiens?",
      alasan: "Misi menjadi kompas seluruh keputusan konten. Tanpa misi yang jelas, konten mudah ikut-ikutan tren dan kehilangan arah.",
      cara_menjawab: "Tulis satu kalimat: 'Kami membantu [siapa] untuk [hasil] tanpa [hambatan]'.",
      contoh: "Kami membantu pemilik UMKM kuliner menaikkan omzet lewat branding yang rapi tanpa biaya agensi mahal.",
    },
    {
      key: "audiens",
      pertanyaan: "Siapa audiens utama Anda? Sebutkan usia, pekerjaan, dan kebiasaan digital mereka.",
      alasan: "Niche yang tepat lahir dari pemahaman audiens yang spesifik. Semakin detail, semakin mudah menemukan angle konten yang nendang.",
      cara_menjawab: "Deskripsikan 1 persona utama sedetail mungkin, bukan 'semua orang'.",
      contoh: "Ibu rumah tangga 28–40 tahun di kota besar, aktif di Instagram jam 20.00–22.00, suka menyimpan tips praktis.",
    },
    {
      key: "nilai",
      pertanyaan: "Nilai apa yang tidak bisa ditawar oleh brand Anda? (maksimal 3)",
      alasan: "Nilai inti membedakan brand Anda dari kompetitor yang menjual produk serupa. Ini bahan bakar positioning.",
      cara_menjawab: "Pilih 3 kata sifat yang benar-benar Anda jalani, bukan sekadar slogan.",
      contoh: "Jujur soal bahan, konsisten rasa, ramah ke pelanggan baru.",
    },
    {
      key: "kepribadian",
      pertanyaan: "Jika brand Anda adalah seseorang, seperti apa kepribadiannya?",
      alasan: "Kepribadian menentukan tone of voice konten: kaku atau santai, serius atau jenaka.",
      cara_menjawab: "Bayangkan brand sebagai teman. Bagaimana ia bicara dan bercanda?",
      contoh: "Seperti kakak yang hangat dan apa adanya — banyak bercanda tapi serius soal kualitas.",
    },
    {
      key: "keunggulan",
      pertanyaan: "Apa yang Anda lakukan lebih baik dari kompetitor? Apa buktinya?",
      alasan: "Diferensiasi harus berbasis bukti, bukan klaim. Ini yang membuat niche Anda defensibel.",
      cara_menjawab: "Sebutkan 1–2 keunggulan + bukti konkret (angka, testimoni, proses).",
      contoh: "Sangrai kopi sendiri setiap pagi — 92% pelanggan menyebut aroma sebagai alasan kembali.",
    },
    {
      key: "topik",
      pertanyaan: "Topik apa yang paling Anda kuasai dan senang dibahas berjam-jam?",
      alasan: "Niche yang sustainable butuh topik yang tidak membuat Anda bosan dalam 6 bulan.",
      cara_menjawab: "Tulis 3 topik yang Anda bahas tanpa perlu persiapan panjang.",
      contoh: "Teknik seduh manual, cerita petani kopi, eksperimen resep minuman.",
    },
    {
      key: "monetisasi",
      pertanyaan: "Bagaimana brand Anda menghasilkan uang saat ini, dan bagaimana dalam 1 tahun ke depan?",
      alasan: "Saran niche harus realistis dimonetisasi. Jawaban ini menyaring niche yang 'ramai tapi tidak menghasilkan'.",
      cara_menjawab: "Jujur soal kondisi sekarang dan target 12 bulan ke depan.",
      contoh: "Sekarang: penjualan kedai. Target: kelas seduh online + langganan biji kopi.",
    },
    {
      key: "batasan",
      pertanyaan: "Topik atau gaya konten apa yang TIDAK akan Anda buat, apa pun trennya?",
      alasan: "Batasan menjaga brand tetap otentik dan menghindari niche yang bertentangan dengan nilai Anda.",
      cara_menjawab: "Sebutkan 2–3 hal yang pantang bagi brand Anda.",
      contoh: "Tidak akan ikut tren joget, tidak membahas politik, tidak diskon besar-besaran.",
    },
  ],
};

export const demoDNA: BrandDNA = {
  id: "dna-demo-1",
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
