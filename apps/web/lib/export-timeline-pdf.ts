import {
  INFO_FASE,
  LABEL_TUJUAN,
  type BriefCampaign,
  type RencanaFunnel,
} from "./funnel";
import {
  LABEL_KANAL,
  type ItemTimeline,
  type KanalTimeline,
} from "./timeline";
import type { RekomendasiTema } from "./tema";
import type { Kompetitor } from "./kompetitor";
import {
  PRINSIP_SINKRONISASI_WA,
  SEKUENS_PASCA_WA,
  STRATEGI_WA_KOMPETITOR,
  buatJadwalWA,
} from "./wa-marketing";

export interface InfoKompetitorPdf {
  nicheLabel?: string;
  kompetitor: Kompetitor[];
}

function formatTanggalPanjang(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Intl.DateTimeFormat("id-ID", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(y, m - 1, d));
}

function namaFileAman(nama: string): string {
  return nama
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
}

/**
 * Membuat dan mengunduh PDF berisi brief 5W1H + ringkasan fase +
 * timeline campaign terintegrasi.
 *
 * jspdf diimpor dinamis agar tidak membebani bundle halaman Planner
 * (diunduh hanya saat pengguna menekan Export PDF).
 */
export async function exportTimelinePdf(
  brief: BriefCampaign,
  rencana: RencanaFunnel,
  timeline: ItemTimeline[],
  filterKanal: KanalTimeline | "semua" = "semua",
  tema: RekomendasiTema | null = null,
  infoKompetitor: InfoKompetitorPdf | null = null
) {
  const [{ jsPDF }, { default: autoTable }] = await Promise.all([
    import("jspdf"),
    import("jspdf-autotable"),
  ]);
  const doc = new jsPDF({ unit: "mm", format: "a4" });
  const lebar = doc.internal.pageSize.getWidth();
  let y = 16;

  // Judul
  doc.setFont("helvetica", "bold");
  doc.setFontSize(16);
  doc.text("Timeline Campaign Terintegrasi", 14, y);
  y += 7;
  doc.setFont("helvetica", "normal");
  doc.setFontSize(11);
  doc.setTextColor(90);
  doc.text(brief.apa, 14, y);
  y += 6;
  doc.setFontSize(9);
  doc.text(
    `${formatTanggalPanjang(rencana.tanggalMulai)} — ${formatTanggalPanjang(
      rencana.tanggalTarget
    )} · ${rencana.totalHari} hari`,
    14,
    y
  );
  doc.setTextColor(0);
  y += 8;

  // Brief 5W1H
  doc.setFont("helvetica", "bold");
  doc.setFontSize(12);
  doc.text("Brief Campaign (5W1H)", 14, y);
  y += 6;
  autoTable(doc, {
    startY: y,
    head: [["Unsur", "Keterangan"]],
    body: [
      ["Apa", brief.apa],
      ["Mengapa", LABEL_TUJUAN[brief.mengapa]],
      ["Siapa", brief.siapa || "—"],
      ["Kapan", formatTanggalPanjang(rencana.tanggalTarget)],
      ["Di mana", brief.dimana || "—"],
      ["Bagaimana", brief.bagaimana || "—"],
    ],
    theme: "grid",
    headStyles: { fillColor: [249, 115, 22], fontSize: 9 },
    bodyStyles: { fontSize: 9 },
    columnStyles: { 0: { cellWidth: 28, fontStyle: "bold" } },
    margin: { left: 14, right: 14 },
  });
  y = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable
    .finalY + 8;

  // Tema campaign terpilih
  if (tema) {
    doc.setFont("helvetica", "bold");
    doc.setFontSize(12);
    doc.text("Tema Campaign Terpilih", 14, y);
    y += 6;
    autoTable(doc, {
      startY: y,
      head: [["Unsur", "Keterangan"]],
      body: [
        ["Tema", tema.namaTema],
        ["Big idea", tema.bigIdea],
        ["Momentum", tema.momentum],
        ["Dasar tren", tema.tren],
        ["Pola acuan", tema.polaAcuan],
      ],
      theme: "grid",
      headStyles: { fillColor: [249, 115, 22], fontSize: 9 },
      bodyStyles: { fontSize: 9 },
      columnStyles: { 0: { cellWidth: 28, fontStyle: "bold" } },
      margin: { left: 14, right: 14 },
    });
    y = (doc as unknown as { lastAutoTable: { finalY: number } })
      .lastAutoTable.finalY + 8;
  }

  // Kompetitor se-niche
  if (infoKompetitor && infoKompetitor.kompetitor.length > 0) {
    doc.setFont("helvetica", "bold");
    doc.setFontSize(12);
    doc.text(
      infoKompetitor.nicheLabel
        ? `Kompetitor Se-Niche — ${infoKompetitor.nicheLabel}`
        : "Kompetitor Se-Niche",
      14,
      y
    );
    y += 6;
    autoTable(doc, {
      startY: y,
      head: [["Kompetitor", "Pola andalan untuk ditiru"]],
      body: infoKompetitor.kompetitor.map((k) => [
        k.handle ? `${k.nama} (@${k.handle})` : k.nama,
        k.polaAndalan.length > 0 ? k.polaAndalan.join(" • ") : "—",
      ]),
      theme: "grid",
      headStyles: { fillColor: [249, 115, 22], fontSize: 9 },
      bodyStyles: { fontSize: 9 },
      columnStyles: { 0: { cellWidth: 48, fontStyle: "bold" } },
      margin: { left: 14, right: 14 },
    });
    y = (doc as unknown as { lastAutoTable: { finalY: number } })
      .lastAutoTable.finalY + 8;
  }

  // Sinkronisasi WA Marketing
  const jadwalWA = buatJadwalWA(rencana, brief);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(12);
  doc.text("Sinkronisasi WA Marketing", 14, y);
  y += 6;

  doc.setFont("helvetica", "bold");
  doc.setFontSize(10);
  doc.text("Strategi WA 5 kompetitor se-niche", 14, y);
  y += 5;
  autoTable(doc, {
    startY: y,
    head: [["Kompetitor", "Ringkasan strategi"]],
    body: STRATEGI_WA_KOMPETITOR.map((s) => [
      s.handle ? `${s.nama} (@${s.handle})` : s.nama,
      `${s.ringkasan} Pola: ${s.pola.join(" • ")}`,
    ]),
    theme: "grid",
    headStyles: { fillColor: [22, 163, 74], fontSize: 9 },
    bodyStyles: { fontSize: 8 },
    columnStyles: { 0: { cellWidth: 44, fontStyle: "bold" } },
    margin: { left: 14, right: 14 },
  });
  y = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable
    .finalY + 6;

  doc.setFont("helvetica", "bold");
  doc.setFontSize(10);
  doc.text("Jadwal broadcast tersinkron", 14, y);
  y += 5;
  autoTable(doc, {
    startY: y,
    head: [["Tanggal", "Fase", "Kegiatan", "Segmen", "Detail"]],
    body: jadwalWA.map((w) => [
      formatTanggalPanjang(w.tanggal),
      w.fase,
      w.kegiatan,
      w.segmen,
      w.detail,
    ]),
    theme: "striped",
    headStyles: { fillColor: [22, 163, 74], fontSize: 8 },
    bodyStyles: { fontSize: 8 },
    columnStyles: {
      0: { cellWidth: 26 },
      1: { cellWidth: 13 },
      3: { cellWidth: 30 },
    },
    margin: { left: 14, right: 14 },
  });
  y = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable
    .finalY + 6;

  doc.setFont("helvetica", "bold");
  doc.setFontSize(10);
  doc.text("4 prinsip sinkronisasi", 14, y);
  y += 5;
  autoTable(doc, {
    startY: y,
    head: [["No", "Prinsip", "Isi"]],
    body: PRINSIP_SINKRONISASI_WA.map((p, i) => [
      String(i + 1),
      p.judul,
      p.isi,
    ]),
    theme: "grid",
    headStyles: { fillColor: [22, 163, 74], fontSize: 9 },
    bodyStyles: { fontSize: 8 },
    columnStyles: {
      0: { cellWidth: 10 },
      1: { cellWidth: 42, fontStyle: "bold" },
    },
    margin: { left: 14, right: 14 },
  });
  y = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable
    .finalY + 6;

  doc.setFont("helvetica", "bold");
  doc.setFontSize(10);
  doc.text("Template sekuens pasca-event", 14, y);
  y += 5;
  autoTable(doc, {
    startY: y,
    head: [["Momen", "Kegiatan", "Detail"]],
    body: SEKUENS_PASCA_WA.map((s) => [s.momen, s.kegiatan, s.detail]),
    theme: "grid",
    headStyles: { fillColor: [22, 163, 74], fontSize: 9 },
    bodyStyles: { fontSize: 8 },
    columnStyles: {
      0: { cellWidth: 16, fontStyle: "bold" },
      1: { cellWidth: 52 },
    },
    margin: { left: 14, right: 14 },
  });
  y = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable
    .finalY + 8;

  // Ringkasan fase
  doc.setFont("helvetica", "bold");
  doc.setFontSize(12);
  doc.text("Ringkasan Fase", 14, y);
  y += 6;
  autoTable(doc, {
    startY: y,
    head: [["Fase", "Fokus", "Durasi", "Konten"]],
    body: (Object.keys(INFO_FASE) as (keyof typeof INFO_FASE)[]).map((f) => [
      f,
      INFO_FASE[f].deskripsi.split(".")[0] + ".",
      `${rencana.perFase[f].hari} hari`,
      `${rencana.perFase[f].konten} konten`,
    ]),
    theme: "grid",
    headStyles: { fillColor: [249, 115, 22], fontSize: 9 },
    bodyStyles: { fontSize: 9 },
    margin: { left: 14, right: 14 },
  });
  y = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable
    .finalY + 8;

  // Timeline
  doc.setFont("helvetica", "bold");
  doc.setFontSize(12);
  const judulTimeline =
    filterKanal === "semua"
      ? "Timeline Lengkap"
      : `Timeline — ${LABEL_KANAL[filterKanal]}`;
  doc.text(judulTimeline, 14, y);
  y += 6;

  const rows =
    filterKanal === "semua"
      ? timeline
      : timeline.filter((it) => it.kanal === filterKanal);

  autoTable(doc, {
    startY: y,
    head: [["Tanggal", "Fase", "Kanal", "Kegiatan", "Detail"]],
    body: rows.map((it) => [
      formatTanggalPanjang(it.tanggal),
      it.fase,
      LABEL_KANAL[it.kanal],
      it.kegiatan,
      it.referensiKompetitor
        ? `${it.detail}\n${it.referensiKompetitor}`
        : it.detail,
    ]),
    theme: "striped",
    headStyles: { fillColor: [249, 115, 22], fontSize: 8 },
    bodyStyles: { fontSize: 8 },
    columnStyles: {
      0: { cellWidth: 28 },
      1: { cellWidth: 14 },
      2: { cellWidth: 24 },
      3: { cellWidth: 42 },
    },
    margin: { left: 14, right: 14 },
    didDrawPage: () => {
      doc.setFontSize(8);
      doc.setTextColor(150);
      doc.text(
        `Dibuat ${new Intl.DateTimeFormat("id-ID", {
          day: "numeric",
          month: "long",
          year: "numeric",
        }).format(new Date())} · MySocial Watch`,
        14,
        doc.internal.pageSize.getHeight() - 8
      );
      doc.setTextColor(0);
    },
  });

  const nama = namaFileAman(brief.apa) || "campaign";
  doc.save(`timeline-${nama}.pdf`);
}
