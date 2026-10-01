// Logika murni generator rencana konten TOFU → MOFU → BOFU.
//
// Dipakai tab "Generate Planner": user mengisi frekuensi posting per minggu,
// tanggal mulai, tanggal target konversi/event, dan platform — lalu fungsi
// buatRencanaFunnel() menghasilkan daftar tanggal beserta jenis kontennya.
//
// Aturan:
// - Durasi minimal 2 minggu (14 hari), maksimal 3 bulan (90 hari).
// - Pembagian fase mengikuti funnel standar: TOFU 50% – MOFU 30% – BOFU 20%.
// - Hari posting disebar merata dalam tiap rentang 7 hari.

export type FaseFunnel = "TOFU" | "MOFU" | "BOFU";
export type PlatformFunnel = "instagram" | "tiktok" | "facebook";

export const LABEL_PLATFORM: Record<PlatformFunnel, string> = {
  instagram: "Instagram",
  tiktok: "TikTok",
  facebook: "Facebook",
};

export const INFO_FASE: Record<
  FaseFunnel,
  { label: string; deskripsi: string; tone: string }
> = {
  TOFU: {
    label: "TOFU — Top of Funnel",
    deskripsi:
      "Bangun awareness: edukasi ringan, hiburan, dan konten yang mudah dibagikan agar orang baru kenal brand Anda.",
    tone: "bg-sky-100 text-sky-800",
  },
  MOFU: {
    label: "MOFU — Middle of Funnel",
    deskripsi:
      "Bangun kepercayaan: bukti, studi kasus, dan konten mendalam yang menjawab keraguan audiens.",
    tone: "bg-violet-100 text-violet-800",
  },
  BOFU: {
    label: "BOFU — Bottom of Funnel",
    deskripsi:
      "Dorong konversi: penawaran, urgensi, dan ajakan bertindak yang jelas menjelang tanggal target.",
    tone: "bg-orange-100 text-orange-800",
  },
};

interface JenisKonten {
  nama: string;
  tujuan: string;
  format: Record<PlatformFunnel, string>;
}

// Bank jenis konten per fase — dirotasi berurutan agar variasinya merata.
const BANK_KONTEN: Record<FaseFunnel, JenisKonten[]> = {
  TOFU: [
    {
      nama: "Video edukasi singkat",
      tujuan: "edukasi",
      format: { instagram: "Reels", tiktok: "Video 30–60 detik", facebook: "Video" },
    },
    {
      nama: "Carousel tips / infografik",
      tujuan: "edukasi",
      format: { instagram: "Carousel", tiktok: "Slideshow foto", facebook: "Carousel" },
    },
    {
      nama: "Video explainer masalah audiens",
      tujuan: "edukasi",
      format: { instagram: "Reels", tiktok: "Video", facebook: "Video" },
    },
    {
      nama: "Konten hiburan & tren",
      tujuan: "hiburan",
      format: { instagram: "Reels", tiktok: "Video tren", facebook: "Video" },
    },
    {
      nama: "Mitos vs fakta",
      tujuan: "edukasi",
      format: { instagram: "Carousel", tiktok: "Video", facebook: "Postingan gambar" },
    },
  ],
  MOFU: [
    {
      nama: "Studi kasus / before-after",
      tujuan: "edukasi",
      format: { instagram: "Carousel", tiktok: "Video", facebook: "Album foto" },
    },
    {
      nama: "Testimoni pelanggan",
      tujuan: "branding",
      format: { instagram: "Reels", tiktok: "Video", facebook: "Video" },
    },
    {
      nama: "Panduan mendalam / tutorial",
      tujuan: "edukasi",
      format: { instagram: "Carousel", tiktok: "Video berseri", facebook: "Video" },
    },
    {
      nama: "Live / webinar edukasi",
      tujuan: "engagement",
      format: { instagram: "Live", tiktok: "Live", facebook: "Live" },
    },
    {
      nama: "Perbandingan solusi",
      tujuan: "edukasi",
      format: { instagram: "Carousel", tiktok: "Video", facebook: "Postingan" },
    },
    {
      nama: "Behind the scenes",
      tujuan: "branding",
      format: { instagram: "Reels", tiktok: "Video", facebook: "Video" },
    },
  ],
  BOFU: [
    {
      nama: "Penawaran khusus / diskon",
      tujuan: "jualan",
      format: { instagram: "Postingan + Reels", tiktok: "Video", facebook: "Postingan" },
    },
    {
      nama: "Countdown event / promo",
      tujuan: "jualan",
      format: { instagram: "Stories", tiktok: "Video", facebook: "Postingan" },
    },
    {
      nama: "Demo produk / free trial",
      tujuan: "jualan",
      format: { instagram: "Reels", tiktok: "Video", facebook: "Video" },
    },
    {
      nama: "Ajakan daftar / beli (CTA)",
      tujuan: "jualan",
      format: { instagram: "Postingan", tiktok: "Video", facebook: "Postingan" },
    },
    {
      nama: "Jaminan & garansi",
      tujuan: "jualan",
      format: { instagram: "Carousel", tiktok: "Video", facebook: "Postingan" },
    },
    {
      nama: "Kesempatan terakhir",
      tujuan: "jualan",
      format: { instagram: "Reels", tiktok: "Video", facebook: "Postingan" },
    },
  ],
};

export const DURASI_MIN_HARI = 14; // 2 minggu
export const DURASI_MAX_HARI = 90; // 3 bulan

// Tujuan campaign (dari 5W1H "Mengapa") — dipakai menyesuaikan rekomendasi
// konten BOFU agar CTA-nya relevan dengan campaign yang dijalankan.
export type TujuanCampaign = "jualan" | "donasi" | "pendaftaran" | "awareness";

export const LABEL_TUJUAN: Record<TujuanCampaign, string> = {
  jualan: "Penjualan produk",
  donasi: "Donasi / fundraising",
  pendaftaran: "Pendaftaran event",
  awareness: "Brand awareness",
};

const ADAPTASI_BOFU: Record<TujuanCampaign, { penawaran: string; cta: string }> = {
  jualan: { penawaran: "Penawaran khusus / diskon", cta: "Ajakan beli (CTA)" },
  donasi: { penawaran: "Program donasi spesial", cta: "Ajakan berdonasi (CTA)" },
  pendaftaran: { penawaran: "Early bird / promo tiket", cta: "Ajakan daftar event (CTA)" },
  awareness: { penawaran: "Konten unggulan brand", cta: "Ajakan follow & share (CTA)" },
};

/** 5W1H event campaign — dasar pelaksanaan campaign. */
export interface BriefCampaign {
  apa: string; // nama event/campaign
  mengapa: TujuanCampaign; // tujuan campaign
  siapa: string; // target audiens
  dimana: string; // lokasi / platform event
  bagaimana: string; // mekanisme pelaksanaan
}

export interface ItemJadwal {
  tanggal: string; // ISO yyyy-mm-dd
  fase: FaseFunnel;
  jenisKonten: string;
  formatSaran: string;
  tujuan: string;
}

export interface RencanaFunnel {
  tanggalMulai: string;
  tanggalTarget: string;
  totalHari: number;
  totalKonten: number;
  perFase: Record<FaseFunnel, { hari: number; konten: number }>;
  items: ItemJadwal[];
}

export interface OpsiFunnel {
  tanggalMulai: string;
  tanggalTarget: string;
  frekuensi: number; // posting per minggu, 1–7
  platform: PlatformFunnel[];
  tujuan?: TujuanCampaign; // default "jualan"
}

/** Bank konten per fase; BOFU disesuaikan dengan tujuan campaign. */
function bankFase(fase: FaseFunnel, tujuan: TujuanCampaign): JenisKonten[] {
  if (fase !== "BOFU") return BANK_KONTEN[fase];
  const adapt = ADAPTASI_BOFU[tujuan];
  return BANK_KONTEN.BOFU.map((j) => {
    if (j.nama === "Penawaran khusus / diskon") return { ...j, nama: adapt.penawaran };
    if (j.nama === "Ajakan daftar / beli (CTA)") return { ...j, nama: adapt.cta };
    return j;
  });
}

function parseLokal(iso: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return null;
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return Number.isNaN(d.getTime()) ? null : d;
}

function keIso(d: Date): string {
  const b = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${b(d.getMonth() + 1)}-${b(d.getDate())}`;
}

function tambahHari(d: Date, n: number): Date {
  const c = new Date(d);
  c.setDate(c.getDate() + n);
  return c;
}

/** Indeks hari (0 = hari pertama periode) untuk disebar merata dalam 7 hari. */
function sebarHari(frekuensi: number): number[] {
  const hasil: number[] = [];
  for (let i = 0; i < frekuensi; i += 1) {
    hasil.push(Math.round((i * 7) / frekuensi));
  }
  return Array.from(new Set(hasil)).sort((a, b) => a - b);
}

export function buatRencanaFunnel(opsi: OpsiFunnel): RencanaFunnel {
  const { tanggalMulai, tanggalTarget, frekuensi, platform } = opsi;
  const tujuan: TujuanCampaign = opsi.tujuan ?? "jualan";

  if (!Number.isInteger(frekuensi) || frekuensi < 1 || frekuensi > 7) {
    throw new Error("Frekuensi posting harus 1–7 kali seminggu.");
  }
  if (platform.length === 0) {
    throw new Error("Pilih minimal satu platform.");
  }
  const mulai = parseLokal(tanggalMulai);
  const target = parseLokal(tanggalTarget);
  if (!mulai || !target) {
    throw new Error("Tanggal mulai dan tanggal target wajib diisi.");
  }
  const totalHari =
    Math.round((target.getTime() - mulai.getTime()) / 86_400_000) + 1;
  if (totalHari < 1) {
    throw new Error("Tanggal target harus sesudah tanggal mulai.");
  }
  if (totalHari < DURASI_MIN_HARI) {
    throw new Error(
      `Durasi ${totalHari} hari terlalu pendek — minimal 2 minggu (${DURASI_MIN_HARI} hari). Mundurkan tanggal target.`
    );
  }
  if (totalHari > DURASI_MAX_HARI) {
    throw new Error(
      `Durasi ${totalHari} hari terlalu panjang — maksimal 3 bulan (${DURASI_MAX_HARI} hari). Majukan tanggal target atau mulai.`
    );
  }

  // Bagi durasi ke 3 fase: TOFU 50%, MOFU 30%, sisanya BOFU.
  const hariTofu = Math.round(totalHari * 0.5);
  const hariMofu = Math.round(totalHari * 0.3);
  const hariBofu = totalHari - hariTofu - hariMofu;
  const batas: { fase: FaseFunnel; sampaiOffset: number }[] = [
    { fase: "TOFU", sampaiOffset: hariTofu },
    { fase: "MOFU", sampaiOffset: hariTofu + hariMofu },
    { fase: "BOFU", sampaiOffset: totalHari },
  ];

  const pola = sebarHari(frekuensi);
  const items: ItemJadwal[] = [];
  const hitungFase: Record<FaseFunnel, number> = { TOFU: 0, MOFU: 0, BOFU: 0 };

  const mingguTotal = Math.ceil(totalHari / 7);
  for (let m = 0; m < mingguTotal; m += 1) {
    for (const p of pola) {
      const offset = m * 7 + p;
      if (offset >= totalHari) continue;
      const slot = batas.find((b) => offset < b.sampaiOffset) ?? batas[2];
      const bank = bankFase(slot.fase, tujuan);
      const jenis = bank[hitungFase[slot.fase] % bank.length];
      hitungFase[slot.fase] += 1;
      const formatUnik = Array.from(
        new Set(platform.map((pl) => jenis.format[pl]))
      ).join(" • ");
      items.push({
        tanggal: keIso(tambahHari(mulai, offset)),
        fase: slot.fase,
        jenisKonten: jenis.nama,
        formatSaran: formatUnik,
        tujuan: jenis.tujuan,
      });
    }
  }

  return {
    tanggalMulai,
    tanggalTarget,
    totalHari,
    totalKonten: items.length,
    perFase: {
      TOFU: { hari: hariTofu, konten: hitungFase.TOFU },
      MOFU: { hari: hariMofu, konten: hitungFase.MOFU },
      BOFU: { hari: hariBofu, konten: hitungFase.BOFU },
    },
    items,
  };
}
