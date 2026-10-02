/**
 * Sinkronisasi WA Marketing untuk Generate Planner.
 *
 * Sumber pola: riset benchmark campaign Ramadhan & Qurban 2026
 * (tab "CRM & WhatsApp", "Konten WA per Funnel", "Sinkronisasi Timeline & WA").
 * Catatan riset: isi pesan broadcast aktual bersifat privat dan tidak ada
 * arsip publik — yang direkonstruksi adalah jenis konten & momen kirimnya.
 */

import type {
  BriefCampaign,
  FaseFunnel,
  RencanaFunnel,
  TujuanCampaign,
} from "./funnel";

/** Strategi WA satu kompetitor se-niche (id cocok dengan lib/kompetitor.ts). */
export interface StrategiWAKompetitor {
  kompetitorId: string;
  nama: string;
  handle: string;
  /** Satu kalimat inti strategi. */
  ringkasan: string;
  /** Pola WA yang layak ditiru. */
  pola: string[];
  /** "riset" = dari riset benchmark mendalam; "umum" = pola umum teramati. */
  sumberPola: "riset" | "umum";
}

export const STRATEGI_WA_KOMPETITOR: StrategiWAKompetitor[] = [
  {
    kompetitorId: "dompet-dhuafa",
    nama: "Dompet Dhuafa",
    handle: "dompetdhuafaorg",
    ringkasan:
      "Notifikasi otomatis berlapis (KIS) + blast edukasi mingguan + WA cabang sebagai kanal konversi.",
    pola: [
      "Sekuens KIS Qurban 2026: konfirmasi transaksi + kuitansi PDF → info lokasi sembelih H-3 (konfirmasi nama H-7) → notifikasi hewan dipotong saat Hari Raya → laporan akhir + sertifikat digital H+45",
      "Blast edukasi mingguan via WA di fase awal campaign",
      "WA cabang dipakai sebagai jalur konversi langsung (contoh: Bareng Yatim Ramadhan 2026)",
      "Segmentasi donatur: milenial (jumlah terbanyak) vs Gen X (nilai terbesar) — pesan disesuaikan",
      "Laporan penggunaan dana dikirim via WA + laporan berkala menjaga loyalitas",
    ],
    sumberPola: "riset",
  },
  {
    kompetitorId: "rumah-zakat",
    nama: "Rumah Zakat",
    handle: "rumahzakat",
    ringkasan:
      "AI 24/7 (Cekat.ai) + broadcast tersegmentasi + laporan berlapis sampai video personal via WA.",
    pola: [
      "Cekat.ai (Meta Business Partner resmi): AI jawab chat 24/7 di WA/IG/web dalam satu inbox, dimaksimalkan di luar jam kerja",
      "Broadcast tersegmentasi: donatur rutin vs donatur sekali vs peserta event — isi pesan berbeda",
      "Sekuens konten WA: edukasi → urgency 10 hari terakhir → ajakan program spesifik → laporan berlapis",
      "Laporan berlapis: broadcast massal + video personal via WA + laporan berkala + ucapan personal",
      "WA Center sebagai kanal resmi konfirmasi transfer",
    ],
    sumberPola: "riset",
  },
  {
    kompetitorId: "dt-peduli",
    nama: "DT Peduli",
    handle: "dtpeduli",
    ringkasan:
      "Broadcast kajian & program + konfirmasi donasi via admin WA.",
    pola: [
      "Broadcast jadwal kajian dan program sosial ke jamaah/donatur",
      "Konfirmasi donasi dilayani admin WA dengan template balasan cepat",
      "Update penyaluran program dikirim berkala ke grup donatur",
    ],
    sumberPola: "umum",
  },
  {
    kompetitorId: "lazismu",
    nama: "Lazismu",
    handle: "lazismu",
    ringkasan:
      "Jaringan cabang/ranting sebagai simpul broadcast WA komunitas.",
    pola: [
      "Cabang dan ranting meneruskan broadcast ke grup WA komunitas masing-masing",
      "Laporan kegiatan ranting dikumpulkan lalu disebar sebagai bukti amanah",
      "Ajakan zakat fitrah/mal disebar terjadwal menjelang momentum",
    ],
    sumberPola: "umum",
  },
  {
    kompetitorId: "sos-childrens-villages",
    nama: "SOS Children's Villages",
    handle: "desaanaksos",
    ringkasan:
      "Journey sponsor: update berkala perkembangan anak asuh via pesan personal.",
    pola: [
      "Donatur/sponsor rutin menerima update perkembangan anak asuh secara berkala",
      "Momen personal (ulang tahun anak, tahun ajaran baru) jadi pemicu pesan",
      "Cerita sebelum–sesudah sebagai bahan retensi donatur",
    ],
    sumberPola: "umum",
  },
];

/** 4 prinsip sinkronisasi timeline konten vs WA marketing (dari riset). */
export const PRINSIP_SINKRONISASI_WA: { judul: string; isi: string }[] = [
  {
    judul: "Satu pesan, dua kecepatan",
    isi: "IG mengejar jangkauan, WA untuk nurturing — pesan sama, kedalaman beda.",
  },
  {
    judul: "WA dulu, baru konten IG",
    isi: "Notifikasi/pengingat penting dikirim via WA lebih dulu, konten publik menyusul.",
  },
  {
    judul: "CTA silang antar kanal",
    isi: "Konten IG mengarah ke WA (mis. “ketik MAU”), broadcast WA mengarah ke landing/IG.",
  },
  {
    judul: "Segmentasi menentukan isi",
    isi: "Donatur rutin, donatur sekali, dan prospek menerima pesan yang berbeda.",
  },
];

/** Satu kiriman WA terjadwal dalam periode campaign. */
export interface ItemWA {
  tanggal: string; // ISO yyyy-mm-dd
  fase: FaseFunnel;
  kegiatan: string;
  detail: string;
  segmen: string;
}

/** Template sekuens WA pasca-event (momen relatif terhadap hari-H). */
export const SEKUENS_PASCA_WA: {
  momen: string;
  kegiatan: string;
  detail: string;
}[] = [
  {
    momen: "H+1",
    kegiatan: "Ucapan terima kasih + angka awal capaian",
    detail:
      "Broadcast ke semua donatur: terima kasih + angka sementara (pola: laporan RZ “289.716 paket tersalurkan”).",
  },
  {
    momen: "H+7",
    kegiatan: "Laporan penyaluran tahap awal",
    detail:
      "Foto/video lapangan + testimoni penerima via WA; versi personal untuk donatur besar (pola RZ: video personal via WA).",
  },
  {
    momen: "H+14",
    kegiatan: "Laporan lengkap + testimoni",
    detail:
      "Ringkasan distribusi per wilayah dengan angka spesifik sebagai bukti amanah.",
  },
  {
    momen: "H+45",
    kegiatan: "Laporan akhir + sertifikat digital",
    detail:
      "Pola KIS Dompet Dhuafa: laporan akhir/SLA + sertifikat digital via email/WA sebagai penutup yang rapi.",
  },
];

const CTA_SEGMEN: Record<TujuanCampaign, string> = {
  jualan: "prospek hangat",
  donasi: "donatur & calon donatur",
  pendaftaran: "calon peserta",
  awareness: "audiens komunitas",
};

function tambahHari(iso: string, hari: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const t = new Date(y, m - 1, d);
  t.setDate(t.getDate() + hari);
  const b = (n: number) => String(n).padStart(2, "0");
  return `${t.getFullYear()}-${b(t.getMonth() + 1)}-${b(t.getDate())}`;
}

/**
 * Susun jadwal broadcast WA yang tersinkron dengan fase campaign.
 * Semua tanggal dijepit dalam [tanggalMulai, tanggalTarget].
 */
export function buatJadwalWA(
  rencana: RencanaFunnel,
  brief: BriefCampaign
): ItemWA[] {
  const t0 = rencana.tanggalMulai;
  const akhir = rencana.tanggalTarget;
  const hT = rencana.perFase.TOFU.hari;
  const hM = rencana.perFase.MOFU.hari;
  const hB = rencana.perFase.BOFU.hari;
  const awalMofu = tambahHari(t0, hT);
  const awalBofu = tambahHari(t0, hT + hM);
  const tgl = (iso: string) => (iso <= akhir ? iso : akhir);
  const tengah = (awal: string, hari: number) =>
    tgl(tambahHari(awal, Math.floor(hari / 2)));
  const segmen = CTA_SEGMEN[brief.mengapa];
  const halaman =
    brief.mengapa === "donasi"
      ? "donasi"
      : brief.mengapa === "jualan"
        ? "pembelian"
        : brief.mengapa === "pendaftaran"
          ? "pendaftaran"
          : "partisipasi";

  const items: ItemWA[] = [
    {
      tanggal: tgl(tambahHari(t0, 2)),
      fase: "TOFU",
      kegiatan: "Broadcast edukasi #1",
      detail:
        "Edukasi ringan seputar tema campaign (pola DD: blast edukasi mingguan; RZ: edukasi fiqih). Tanpa ajakan transaksi.",
      segmen: "Semua kontak",
    },
    {
      tanggal: tengah(t0, hT),
      fase: "TOFU",
      kegiatan: "Broadcast edukasi #2 + perkenalan program",
      detail:
        "Lanjutan edukasi + perkenalan program unggulan. Di konten IG hari yang sama: versi publik yang mengarah ke WA (“ketik MAU”).",
      segmen: "Semua kontak",
    },
    {
      tanggal: tgl(tambahHari(awalMofu, 1)),
      fase: "MOFU",
      kegiatan: "Broadcast cerita penerima manfaat",
      detail:
        "Kisah personal bernama + foto lapangan sebagai bukti dampak (pola RZ: cerita Afrizal; DD: penerima Ber-ojol).",
      segmen: segmen,
    },
    {
      tanggal: tengah(awalMofu, hM),
      fase: "MOFU",
      kegiatan: "Broadcast ajakan program spesifik",
      detail:
        "Ajakan ke satu program bernama (bukan “donasi umum”) + link/CTA yang jelas (pola RZ: ajakan program spesifik).",
      segmen: `${segmen} — prioritas yang pernah berinteraksi`,
    },
    {
      tanggal: tgl(tambahHari(awalBofu, 1)),
      fase: "BOFU",
      kegiatan: "Broadcast urgency",
      detail:
        "Hitung mundur & keterbatasan kuota/waktu (pola RZ: urgency 10 hari terakhir, “STOCK MENIPIS”). Kirim WA dulu, konten IG menyusul.",
      segmen: segmen,
    },
    {
      tanggal: tgl(tambahHari(akhir, -3)),
      fase: "BOFU",
      kegiatan: "Pengingat H-3 + tutorial",
      detail: `Pengingat 3 hari sebelum hari-H + tutorial langkah ${halaman} (pola KIS: info H-3; RZ: tutorial bayar step-by-step).`,
      segmen: `${segmen} — yang belum berkonversi`,
    },
  ];

  // Urut kronologis & buang duplikat tanggal+kegiatan yang sama
  const unik = new Map<string, ItemWA>();
  for (const it of items) {
    const kunci = `${it.tanggal}|${it.kegiatan}`;
    if (!unik.has(kunci)) unik.set(kunci, it);
  }
  const hasil: ItemWA[] = [];
  unik.forEach((it) => hasil.push(it));
  return hasil.sort((a, b) =>
    a.tanggal < b.tanggal ? -1 : a.tanggal > b.tanggal ? 1 : 0
  );
}
