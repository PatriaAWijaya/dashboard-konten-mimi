// Util format: rupiah & tanggal Indonesia.

export function formatRupiah(nilai: number | string | null | undefined): string {
  const angka = typeof nilai === "string" ? Number(nilai) : nilai;
  if (angka === null || angka === undefined || Number.isNaN(angka))
    return "Rp0";
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(angka);
}

export function formatTanggal(
  iso: string | null | undefined,
  denganJam = false
): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "-";
  return d.toLocaleString("id-ID", {
    day: "numeric",
    month: "long",
    year: "numeric",
    ...(denganJam
      ? { hour: "2-digit", minute: "2-digit", hour12: false }
      : {}),
  });
}

// "2 hari 3 jam 15 menit" dari selisih milidetik.
export function formatSisaWaktu(ms: number): string {
  if (ms <= 0) return "Kedaluwarsa";
  const totalDetik = Math.floor(ms / 1000);
  const hari = Math.floor(totalDetik / 86400);
  const jam = Math.floor((totalDetik % 86400) / 3600);
  const menit = Math.floor((totalDetik % 3600) / 60);
  const detik = totalDetik % 60;
  if (hari > 0) return `${hari} hari ${jam} jam ${menit} mnt`;
  if (jam > 0) return `${jam} jam ${menit} mnt ${detik} dtk`;
  return `${menit} mnt ${detik} dtk`;
}

// Angka dengan pemisah ribuan id-ID. Tanpa `desimal` = apa adanya
// (n.toLocaleString("id-ID")); dengan `desimal` = digit desimal dipaksa.
export function formatAngka(
  nilai: number | null | undefined,
  desimal?: number
): string {
  if (nilai === null || nilai === undefined) return "-";
  return desimal === undefined
    ? nilai.toLocaleString("id-ID")
    : nilai.toLocaleString("id-ID", {
        minimumFractionDigits: desimal,
        maximumFractionDigits: desimal,
      });
}

// Persen dari rasio 0-1 (mis. 0,5 → "50,0%").
// `tetap = true` (default): digit desimal selalu tampil sejumlah `desimal`.
// `tetap = false`: digit desimal hanya tampil bila perlu ("50%").
export function formatPersen(
  nilai: number | null | undefined,
  desimal = 1,
  tetap = true
): string {
  if (nilai === null || nilai === undefined) return "-";
  const opsi = tetap
    ? { minimumFractionDigits: desimal, maximumFractionDigits: desimal }
    : { maximumFractionDigits: desimal };
  return (nilai * 100).toLocaleString("id-ID", opsi) + "%";
}
