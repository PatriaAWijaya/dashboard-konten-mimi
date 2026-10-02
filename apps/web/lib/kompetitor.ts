/**
 * Bank kompetitor se-niche untuk ide konten di Generate Planner.
 *
 * Prinsip: untuk ide konten, kenali minimal 5 kompetitor dengan niche yang sama,
 * lalu tiru pola konten andalan mereka (bukan jiplak mentah-mentah).
 *
 * Data kompetitor untuk niche "Lembaga Zakat & Filantropi Islam" memakai nama
 * yang diminta Patria (Dompet Dhuafa, Rumah Zakat, DT Peduli, Lazismu,
 * SOS Children's Villages). Handle Instagram diverifikasi 2026-10-02.
 * Pola andalan Dompet Dhuafa & Rumah Zakat berasal dari riset benchmark
 * campaign Ramadhan & Qurban 2026; sisanya pola umum teramati.
 */

export interface Kompetitor {
  id: string;
  nama: string;
  /** handle Instagram tanpa @ */
  handle: string;
  /** 1-3 pola konten andalan yang layak ditiru */
  polaAndalan: string[];
  /** sumber pola: "riset" (benchmark mendalam) atau "umum" (pola teramati) */
  sumberPola: "riset" | "umum";
}

export interface NicheKompetitor {
  id: string;
  label: string;
  deskripsi: string;
  kompetitor: Kompetitor[];
}

export const BANK_NICHE_KOMPETITOR: NicheKompetitor[] = [
  {
    id: "filantropi-islam",
    label: "Lembaga Zakat & Filantropi Islam",
    deskripsi:
      "LAZ, lembaga amil zakat, dan NGO kemanusiaan Islam di Indonesia",
    kompetitor: [
      {
        id: "dompet-dhuafa",
        nama: "Dompet Dhuafa",
        handle: "dompetdhuafaorg",
        polaAndalan: [
          "Satu big idea berbahasa audiens dipakai konsisten 1–2 bulan (“Berzakat Itu Kalcer”)",
          "Angka spesifik sebagai bahasa kepercayaan (“27 ribu hewan kurban, 28 provinsi”)",
          "Satu CTA besar + penghilang risiko + social proof nominal",
        ],
        sumberPola: "riset",
      },
      {
        id: "rumah-zakat",
        nama: "Rumah Zakat",
        handle: "rumahzakat",
        polaAndalan: [
          "Caption = landing page mini: hook 1–2 baris → cerita → dalil → CTA → hashtag",
          "Urgency dimainkan di sosmed (flash sale, “STOCK MENIPIS”), bukan di web",
          "Link afiliasi per mitra/influencer (linkrz.id/…) untuk atribusi donasi",
        ],
        sumberPola: "riset",
      },
      {
        id: "dt-peduli",
        nama: "DT Peduli",
        handle: "dtpeduli",
        polaAndalan: [
          "Fundraising dibungkus dakwah & kajian — otoritas keulamaan sebagai trust anchor",
          "Cerita penerima manfaat yang personal dan emosional",
        ],
        sumberPola: "umum",
      },
      {
        id: "lazismu",
        nama: "Lazismu",
        handle: "lazismu",
        polaAndalan: [
          "Jaringan persyarikatan: cabang & ranting sebagai mesin distribusi dan amplifikasi",
          "Program rutin pendidikan & kesehatan sebagai bukti keberlanjutan",
        ],
        sumberPola: "umum",
      },
      {
        id: "sos-childrens-villages",
        nama: "SOS Children's Villages",
        handle: "desaanaksos",
        polaAndalan: [
          "Storytelling anak asuh yang longitudinal — donatur mengikuti perjalanan anak",
          "Program sponsor/donasi rutin dengan update berkala ke donatur",
        ],
        sumberPola: "umum",
      },
    ],
  },
  {
    id: "kustom",
    label: "Niche lain (isi manual)",
    deskripsi: "Tambahkan kompetitor sesuai niche Anda sendiri",
    kompetitor: [],
  },
];

/** Ambil niche dari bank berdasarkan id. */
export function dapatkanNiche(id: string): NicheKompetitor | undefined {
  return BANK_NICHE_KOMPETITOR.find((n) => n.id === id);
}

/** Niche default untuk Generate Planner. */
export const NICHE_DEFAULT = "filantropi-islam";

/**
 * Referensi pola kompetitor untuk satu item jadwal.
 * Diputar merata agar tiap item mendapat inspirasi pola yang berbeda.
 */
export function referensiPolaKompetitor(
  kompetitor: Kompetitor[],
  indeksItem: number
): string | undefined {
  if (kompetitor.length === 0) return undefined;
  const k = kompetitor[indeksItem % kompetitor.length];
  const pola =
    k.polaAndalan.length > 0
      ? k.polaAndalan[indeksItem % k.polaAndalan.length]
      : "amati pola konten andalannya, lalu adaptasi ke brand Anda";
  return `Pola ${k.nama}: ${pola}`;
}
