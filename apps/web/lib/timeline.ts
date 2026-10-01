import {
  type BriefCampaign,
  type FaseFunnel,
  type RencanaFunnel,
  type TujuanCampaign,
} from "./funnel";

/**
 * Timeline campaign terintegrasi: konten organik + placement ads +
 * kolaborasi + web internal + galang dana, tersusun kronologis per fase
 * TOFU → MOFU → BOFU.
 */

export type KanalTimeline =
  | "konten"
  | "ads"
  | "kolaborasi"
  | "web"
  | "galangdana";

export const LABEL_KANAL: Record<KanalTimeline, string> = {
  konten: "Konten Organik",
  ads: "Placement Ads",
  kolaborasi: "Kolaborasi",
  web: "Web Internal",
  galangdana: "Galang Dana",
};

export const TONE_KANAL: Record<KanalTimeline, string> = {
  konten: "bg-slate-100 text-slate-700",
  ads: "bg-blue-100 text-blue-700",
  kolaborasi: "bg-purple-100 text-purple-700",
  web: "bg-emerald-100 text-emerald-700",
  galangdana: "bg-amber-100 text-amber-700",
};

export interface ItemTimeline {
  tanggal: string; // ISO yyyy-mm-dd
  fase: FaseFunnel;
  kanal: KanalTimeline;
  kegiatan: string;
  detail: string;
}

function tambahHari(iso: string, hari: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const t = new Date(y, m - 1, d);
  t.setDate(t.getDate() + hari);
  const b = (n: number) => String(n).padStart(2, "0");
  return `${t.getFullYear()}-${b(t.getMonth() + 1)}-${b(t.getDate())}`;
}

/** Halaman konversi di web internal, menyesuaikan tujuan campaign. */
const HALAMAN_KONVERSI: Record<TujuanCampaign, string> = {
  jualan: "checkout / pembelian",
  donasi: "donasi",
  pendaftaran: "pendaftaran",
  awareness: "follow & keterlibatan",
};

/** Objective iklan BOFU, menyesuaikan tujuan campaign. */
const OBJECTIVE_BOFU: Record<TujuanCampaign, string> = {
  jualan: "purchase",
  donasi: "donate",
  pendaftaran: "lead",
  awareness: "engagement",
};

export function buatTimelineTerintegrasi(
  rencana: RencanaFunnel,
  brief: BriefCampaign
): ItemTimeline[] {
  const items: ItemTimeline[] = rencana.items.map((it) => ({
    tanggal: it.tanggal,
    fase: it.fase,
    kanal: "konten" as KanalTimeline,
    kegiatan: it.jenisKonten,
    detail: it.formatSaran,
  }));

  const t0 = rencana.tanggalMulai;
  const akhir = rencana.tanggalTarget;
  const hT = rencana.perFase.TOFU.hari;
  const hM = rencana.perFase.MOFU.hari;
  const hB = rencana.perFase.BOFU.hari;
  const awalMofu = tambahHari(t0, hT);
  const awalBofu = tambahHari(t0, hT + hM);

  // Jepit tanggal agar tidak melewati tanggal target.
  const tgl = (iso: string) => (iso <= akhir ? iso : akhir);
  const tengah = (awal: string, hari: number) =>
    tgl(tambahHari(awal, Math.floor(hari / 2)));

  const halaman = HALAMAN_KONVERSI[brief.mengapa];

  function dorong(
    tanggal: string,
    fase: FaseFunnel,
    kanal: KanalTimeline,
    kegiatan: string,
    detail: string
  ) {
    items.push({ tanggal: tgl(tanggal), fase, kanal, kegiatan, detail });
  }

  // ---- Placement Ads ----
  dorong(
    tambahHari(t0, 1),
    "TOFU",
    "ads",
    "Iklan awareness tayang",
    "Objective reach / video views memakai potongan konten TOFU terbaik."
  );
  dorong(
    awalMofu,
    "MOFU",
    "ads",
    "Iklan traffic & engagement",
    "Retargeting penonton iklan TOFU dan pengunjung web."
  );
  dorong(
    awalBofu,
    "BOFU",
    "ads",
    "Iklan konversi",
    `Objective ${OBJECTIVE_BOFU[brief.mengapa]} — dorong ${halaman}.`
  );
  dorong(
    tengah(awalBofu, hB),
    "BOFU",
    "ads",
    "Iklan remarketing urgency",
    "Countdown dan pengingat terakhir ke audiens hangat."
  );

  // ---- Kolaborasi ----
  dorong(
    tambahHari(t0, 2),
    "TOFU",
    "kolaborasi",
    "Brief & kirim materi ke KOL/mitra",
    "Siapkan talking points, aset visual, dan jadwal posting."
  );
  dorong(
    tengah(t0, hT),
    "TOFU",
    "kolaborasi",
    "Posting kolaborasi",
    "Collab post / repost bersama KOL atau mitra komunitas."
  );
  dorong(
    tengah(awalMofu, hM),
    "MOFU",
    "kolaborasi",
    "Live bareng / testimoni mitra",
    "Bangun kepercayaan lewat suara pihak ketiga."
  );
  dorong(
    tambahHari(awalBofu, 1),
    "BOFU",
    "kolaborasi",
    "KOL ajakan final",
    "Ajakan konversi memakai link atau kode khusus."
  );

  // ---- Web internal ----
  dorong(
    t0,
    "TOFU",
    "web",
    "Artikel & landing teaser tayang",
    "Konten SEO pemanasan dan halaman tunggu event."
  );
  dorong(
    awalMofu,
    "MOFU",
    "web",
    "Halaman utama event tayang",
    "Info lengkap, rundown, dan FAQ."
  );
  dorong(
    awalBofu,
    "BOFU",
    "web",
    "Halaman konversi aktif",
    `Halaman ${halaman} dilengkapi countdown dan bukti sosial.`
  );

  // ---- Galang dana ----
  dorong(
    tengah(t0, hT),
    "TOFU",
    "galangdana",
    "Halaman galang dana tayang",
    "Cerita yang menyentuh, target dana, dan CTA donasi."
  );
  dorong(
    tengah(awalMofu, hM),
    "MOFU",
    "galangdana",
    "Update progres penggalangan #1",
    "Ceritakan capaian dan sisa target."
  );
  dorong(
    tengah(awalBofu, hB),
    "BOFU",
    "galangdana",
    "Update progres #2 + dorongan akhir",
    "Tekankan dampak donasi dan sisa waktu."
  );

  const urutanKanal: KanalTimeline[] = [
    "konten",
    "ads",
    "kolaborasi",
    "web",
    "galangdana",
  ];
  items.sort(
    (a, b) =>
      a.tanggal.localeCompare(b.tanggal) ||
      urutanKanal.indexOf(a.kanal) - urutanKanal.indexOf(b.kanal)
  );
  return items;
}
