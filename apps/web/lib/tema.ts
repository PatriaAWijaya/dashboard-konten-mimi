import type {
  BriefCampaign,
  FaseFunnel,
  TemaKonten,
  TujuanCampaign,
} from "./funnel";

/**
 * Rekomendasi Tema Campaign — big idea yang diambil dari tren sosial &
 * keagamaan 6 bulan terakhir (Apr–Sep 2026) serta pola campaign Dompet
 * Dhuafa & Rumah Zakat dari riset benchmark Ramadhan & Qurban 2026.
 */

export type { TemaKonten };

export interface RekomendasiTema extends TemaKonten {
  id: string;
  bigIdea: string;
  momentum: string;
  tren: string;
  polaAcuan: string;
  penjelasan: string;
}

interface Momentum {
  id: string;
  nama: string;
  mulai: string; // ISO
  selesai: string; // ISO
  persiapanHari: number; // campaign boleh mulai sekian hari sebelumnya
}

// Tanggal terverifikasi: Ramadhan 1448 H = 8 Feb 2027 (KHGT Muhammadiyah +
// prediksi BMKG; penetapan resmi pemerintah via sidang isbat), Idul Adha
// 1448 H = 16 Mei 2027, Nisfu Syaban = 23 Jan 2027, Isra Mikraj = 5 Jan 2027.
const DAFTAR_MOMENTUM: Momentum[] = [
  {
    id: "ramadhan",
    nama: "Ramadhan 1448 H (8 Feb – 9 Mar 2027)",
    mulai: "2027-02-08",
    selesai: "2027-03-09",
    persiapanHari: 90,
  },
  {
    id: "idulfitri",
    nama: "Idul Fitri 1448 H (9 Mar 2027)",
    mulai: "2027-03-09",
    selesai: "2027-03-11",
    persiapanHari: 30,
  },
  {
    id: "qurban",
    nama: "Idul Adha / Qurban 1448 H (16 Mei 2027)",
    mulai: "2027-05-16",
    selesai: "2027-05-19",
    persiapanHari: 60,
  },
  {
    id: "nisfusyaban",
    nama: "Nisfu Syaban 1448 H (23 Jan 2027)",
    mulai: "2027-01-16",
    selesai: "2027-01-23",
    persiapanHari: 21,
  },
  {
    id: "isramikraj",
    nama: "Isra Mikraj 1448 H (5 Jan 2027)",
    mulai: "2026-12-29",
    selesai: "2027-01-05",
    persiapanHari: 21,
  },
];

function tambahHariIso(iso: string, hari: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const t = new Date(y, m - 1, d);
  t.setDate(t.getDate() + hari);
  const b = (n: number) => String(n).padStart(2, "0");
  return `${t.getFullYear()}-${b(t.getMonth() + 1)}-${b(t.getDate())}`;
}

/** Deteksi momentum keagamaan dari rentang campaign. */
export function deteksiMomentum(
  tanggalMulai: string,
  tanggalTarget: string
): Momentum | null {
  for (const mo of DAFTAR_MOMENTUM) {
    const batasAwal = tambahHariIso(mo.mulai, -mo.persiapanHari);
    if (tanggalTarget >= batasAwal && tanggalTarget <= mo.selesai) return mo;
    if (tanggalMulai <= mo.selesai && tanggalTarget >= mo.mulai) return mo;
  }
  return null;
}

type KunciTema = `${string}__${TujuanCampaign}`;

const BANK_TEMA: Record<KunciTema, RekomendasiTema[]> = {
  ramadhan__donasi: [
    {
      id: "ramadhan-baik",
      namaTema: "Ramadhan Baik",
      bigIdea:
        "Jadikan sedekah sebagai budaya harian — bukan sekadar agenda musiman.",
      momentum: "Ramadhan 1448 H (8 Feb – 9 Mar 2027)",
      tren: "Bahasa santai khas Gen-Z terbukti menaikkan kedekatan di campaign Ramadhan 1447 H; video pendek masih format perhatian #1 dan TikTok menjadi medsos terbanyak dipakai di Indonesia 2026.",
      polaAcuan:
        "Dompet Dhuafa — “Berzakat Itu Kalcer” (Ramadhan 1447 H) dan Rumah Zakat — “Road to Ramadhan #BikinBahagia”: satu frasa pendek berbahasa audiens, dipakai konsisten di semua konten selama campaign.",
      penjelasan:
        "Frasa “Ramadhan Baik” mudah diingat, mudah dijadikan hashtag, dan menempel natural di semua jenis konten — dari video edukasi sampai ajakan donasi.",
      angle: {
        TOFU: "Big idea: edukasi ringan kenapa sedekah harian di Ramadhan berlipat pahala — kemas dengan gaya bahasa sehari-hari, bukan ceramah.",
        MOFU: "Big idea: menangkan kepercayaan lewat angka penyaluran + wajah penerima + admin yang aktif membalas keraguan di komentar.",
        BOFU: "Big idea: satu CTA besar per momen — mis. “DONASI SEKARANG” + countdown 10 hari terakhir Ramadhan.",
      },
    },
    {
      id: "sedekah-subuh",
      namaTema: "Sedekah Subuh",
      bigIdea:
        "Ritual kecil setiap subuh: sedekah rutin yang menenangkan hati dan konsisten terkumpul.",
      momentum: "Ramadhan 1448 H (8 Feb – 9 Mar 2027)",
      tren: "Program donasi rutin berulang tumbuh di 2026 karena donatur menyukai nominal kecil yang otomatis dan terasa ringan.",
      polaAcuan:
        "Rumah Zakat — program sedekah rutin + Dompet Dhuafa: jadikan produk donasi “bernama & bermekanisme unik”, bukan donasi umum.",
      penjelasan:
        "Mengubah donasi sekali-bayar menjadi kebiasaan harian — cocok untuk audiens 25–55 tahun yang ingin istiqamah tanpa terbebani.",
      angle: {
        TOFU: "Big idea: bangun kebiasaan — konten pengingat lembut “sudah sedekah subuh hari ini?” dengan visual rutinitas pagi.",
        MOFU: "Big idea: tunjukkan akumulasi — “Rp10 ribu × 30 hari = 30 paket buka puasa”, pakai data visual yang disukai Gen-Z.",
        BOFU: "Big idea: ajak komit sekarang — “Mulai besok subuh”, satu tombol daftar sedekah rutin + pengingat otomatis.",
      },
    },
  ],
  ramadhan__pendaftaran: [
    {
      id: "ramadhan-fest",
      namaTema: "Ramadhan Fest",
      bigIdea:
        "Festival kebaikan: kumpul, belajar, dan berbagi dalam satu event yang tidak terlupakan.",
      momentum: "Ramadhan 1448 H (8 Feb – 9 Mar 2027)",
      tren: "Event komunitas hijrah ramai di Ramadhan 1447 H; kolaborasi charity-partner terbukti mendatangkan massa + donasi sekaligus.",
      polaAcuan:
        "Rumah Zakat — Official Charity Partner “Hijrahfest Ramadan: Comeback Stronger” (28 Feb 2026): tiket event sudah termasuk donasi.",
      penjelasan:
        "Format festival memudahkan pendaftaran (tiket) sekaligus fundraising — dua tujuan tercapai dalam satu momentum.",
      angle: {
        TOFU: "Big idea: bangun FOMO — teaser line-up, keseruan tahun lalu, dan “tiketmu = donasi”.",
        MOFU: "Big idea: yakinkan dengan rundown lengkap, FAQ, dan testimoni peserta sebelumnya.",
        BOFU: "Big idea: tutup dengan urgensi — “tiket batch terakhir”, countdown, dan ajakan daftar sekarang.",
      },
    },
  ],
  ramadhan__jualan: [
    {
      id: "parsel-berkah",
      namaTema: "Parsel Berkah",
      bigIdea:
        "Setiap parsel yang dibeli = satu paket buka puasa untuk yang membutuhkan.",
      momentum: "Ramadhan 1448 H (8 Feb – 9 Mar 2027)",
      tren: "Pembeli 2026 memilih brand yang transaksinya berdampak sosial; paket berbuka massal jadi konten favorit korporat.",
      polaAcuan:
        "Rumah Zakat — 5.000 paket berbuka puasa bersama korporat; Dompet Dhuafa — “Borong Dagangan Saudaramu”.",
      penjelasan:
        "Mekanisme “beli 1 = berbagi 1” memberi alasan emosional membeli — bukan sekadar diskon.",
      angle: {
        TOFU: "Big idea: kenalkan misi — cerita siapa yang menerima paket buka dari setiap pembelian.",
        MOFU: "Big idea: buktikan — hitung “1.200 parsel terjual = 1.200 paket buka tersalurkan”, tampilkan datanya.",
        BOFU: "Big idea: dorong checkout — stok parsel terbatas + “pengiriman terakhir sebelum Lebaran”.",
      },
    },
  ],
  ramadhan__awareness: [
    {
      id: "cerita-ramadhan",
      namaTema: "Cerita Ramadhan",
      bigIdea:
        "Kumpulkan cerita kebaikan Ramadhan dari audiens — jadikan mereka bintangnya.",
      momentum: "Ramadhan 1448 H (8 Feb – 9 Mar 2027)",
      tren: "Konten partisipatif (UGC) naik di 2026; audiens lebih percaya cerita sesama daripada klaim brand.",
      polaAcuan:
        "Dompet Dhuafa — dokumentasi distribusi real-time saat puncak Ramadhan sebagai pemicu donasi susulan.",
      penjelasan:
        "Awareness tumbuh organik saat audiens ikut bercerita — campaign menjadi milik bersama, bukan milik brand.",
      angle: {
        TOFU: "Big idea: pancing cerita — “momen Ramadhan paling berkesanmu?” dengan template mudah diikuti.",
        MOFU: "Big idea: kurasi & angkat — repost cerita terbaik + data “2.300 cerita terkumpul”.",
        BOFU: "Big idea: rayakan bersama — kompilasi penutup + ajakan follow agar tak ketinggalan cerita tahun depan.",
      },
    },
  ],
  qurban__donasi: [
    {
      id: "kurban-terbaik",
      namaTema: "Kurban Terbaik",
      bigIdea:
        "Siapkan kurban terbaik versimu — hewan kurban adalah kendaraan menuju surga.",
      momentum: "Idul Adha / Qurban 1448 H (16 Mei 2027)",
      tren: "Carousel edukasi mendominasi 48% konten Qurban 2026; angka spesifik (harga, bobot, jumlah penerima) menjadi bahasa kepercayaan.",
      polaAcuan:
        "Dompet Dhuafa — “Kurbanaval 2026: Siapkan Kendaraan Terbaik Versimu!” (Qurban 1447 H) dan Rumah Zakat — “Superqurban + Desaku Berqurban”: produk kurban diberi nama khas, bukan sekadar “kurban”.",
      penjelasan:
        "Metafora “kendaraan terbaik” mengubah kurban dari kewajiban menjadi aspirasi — audiens memilih yang terbaik, bukan yang termurah.",
      angle: {
        TOFU: "Big idea: edukasi fiqih kurban lewat carousel ber-slide — syarat hewan, waktu, dan keutamaannya.",
        MOFU: "Big idea: menangkan dengan transparansi — harga per paket, laporan pemotongan, dan testimoni pekurban tahun lalu.",
        BOFU: "Big idea: urgensi stok — “STOK HEWAN SEMAKIN MENIPIS”, flash sale + tutorial bayar semudah pesan ojek online.",
      },
    },
    {
      id: "patungan-kurban",
      namaTema: "Patungan Kurban",
      bigIdea:
        "Belum mampu sapi sendiri? Patungan 1/7 sapi — pahala kurban tetap penuh.",
      momentum: "Idul Adha / Qurban 1448 H (16 Mei 2027)",
      tren: "Paket harga bertingkat laris di 2026 karena menurunkan hambatan nominal tanpa menurunkan niat.",
      polaAcuan:
        "Rumah Zakat — “HAJI BELUM MAMPU? PATUNGAN QURBAN SAPI AJA DULU!” + paket harga 1 jutaan.",
      penjelasan:
        "Menjawab keberatan harga — segmen anak muda dan keluarga baru yang ingin berkurban tapi terbatas budget.",
      angle: {
        TOFU: "Big idea: edukasi — “bolehkah patungan kurban?” jawab dengan dalil yang mudah dipahami.",
        MOFU: "Big idea: hitung bareng — “Rp300 ribu/bulan × 7 orang = 1 sapi”, pakai data visual.",
        BOFU: "Big idea: amankan slot — kuota patungan terbatas + link daftar per kelompok.",
      },
    },
  ],
  qurban__pendaftaran: [
    {
      id: "festival-kurban",
      namaTema: "Festival Kurban",
      bigIdea:
        "Rayakan Idul Adha bareng: shalat, penyembelihan terbuka, dan makan bersama.",
      momentum: "Idul Adha / Qurban 1448 H (16 Mei 2027)",
      tren: "Event offline komunitas kembali ramai 2026; dokumentasi lapangan real-time jadi konten paling dipercaya.",
      polaAcuan:
        "Rumah Zakat — dokumentasi penyembelihan & distribusi dengan dateline kota + testimoni penerima.",
      penjelasan:
        "Event terbuka membangun kepercayaan — peserta melihat sendiri hewan disembelih dan daging disalurkan.",
      angle: {
        TOFU: "Big idea: undang — teaser keseruan festival tahun lalu + “bawa keluarga”.",
        MOFU: "Big idea: yakinkan — rundown, lokasi, dan liputan media tahun sebelumnya.",
        BOFU: "Big idea: daftar sekarang — kuota peserta terbatas + pilihan paket kurban di lokasi.",
      },
    },
  ],
  qurban__jualan: [
    {
      id: "kurban-ekpress",
      namaTema: "Kurban Express",
      bigIdea:
        "Pesan hewan kurban semudah pesan makanan — bayar via e-wallet & marketplace favoritmu.",
      momentum: "Idul Adha / Qurban 1448 H (16 Mei 2027)",
      tren: "Kanal pembayaran digital (BRImo, Tokopedia, BSI) mendongkrak konversi kurban 2026.",
      polaAcuan:
        "Rumah Zakat — kurban via BRImo/Tokopedia/Byond BSI + Dompet Dhuafa — “Kurban Express”.",
      penjelasan:
        "Menghilangkan friksi bayar — audiens sibuk tetap bisa berkurban dalam 2 menit dari HP.",
      angle: {
        TOFU: "Big idea: kenalkan kemudahan — “qurban 2 menit dari HP”, tunjukkan langkahnya.",
        MOFU: "Big idea: buktikan aman — tutorial bayar + garansi laporan pemotongan transparan.",
        BOFU: "Big idea: kejar — promo cashback e-wallet + “tutup 3 hari sebelum Idul Adha”.",
      },
    },
  ],
  qurban__awareness: [
    {
      id: "jejak-kurban",
      namaTema: "Jejak Kurban",
      bigIdea:
        "Ikuti perjalanan hewan kurban: dari kandang peternak lokal sampai ke pelosok penerima.",
      momentum: "Idul Adha / Qurban 1448 H (16 Mei 2027)",
      tren: "Konten behind-the-scenes & pemberdayaan peternak lokal disukai audiens 2026.",
      polaAcuan:
        "Dompet Dhuafa — 5 alasan berkurban: distribusi pelosok + berdayakan peternak lokal.",
      penjelasan:
        "Awareness yang mendidik — audiens paham ke mana kurbannya pergi dan siapa yang diberdayakan.",
      angle: {
        TOFU: "Big idea: kenalkan peternak — wajah & cerita mereka di balik hewan kurban.",
        MOFU: "Big idea: tunjukkan rantai — peta distribusi + angka desa penerima.",
        BOFU: "Big idea: ajak ikut — “jadilah bagian jejak tahun ini”, satu CTA.",
      },
    },
  ],
  generik__donasi: [
    {
      id: "kebaikan-berlipat",
      namaTema: "Kebaikan Berlipat",
      bigIdea:
        "Tunjukkan setiap rupiah berlipat dampaknya — dengan angka dan bukti lapangan.",
      momentum: "Sepanjang tahun",
      tren: "43% Gen-Z lebih tertarik konten data visual untuk isu sosial (IDN Research Institute, Sep 2026); angka spesifik mengalahkan klaim umum.",
      polaAcuan:
        "Rumah Zakat — “Alhamdulillah, 289.716 paket Ramadhan tersalurkan”; Dompet Dhuafa — “27 ribu hewan kurban, 28 provinsi”.",
      penjelasan:
        "Tanpa momentum hari besar, kepercayaan dibangun lewat transparansi angka — cocok untuk fundraising rutin.",
      angle: {
        TOFU: "Big idea: edukasi masalah — satu data kuat per konten, divisualkan sederhana.",
        MOFU: "Big idea: bukti penyaluran — laporan lapangan + testimoni penerima + nominal terkumpul real-time.",
        BOFU: "Big idea: ajak sekarang — “Rp50 ribu = 1 paket sembako”, satu CTA + bukti transfer amanah.",
      },
    },
    {
      id: "donasi-rutin",
      namaTema: "Donasi Rutin",
      bigIdea:
        "Sedikit tapi istiqamah: donasi otomatis tiap bulan tanpa terasa berat.",
      momentum: "Sepanjang tahun",
      tren: "Donasi berlangganan tumbuh 2026; donatur menyukai nominal kecil yang terjadwal.",
      polaAcuan:
        "Dompet Dhuafa — arsitektur digital berlapis: edukasi di web utama, konversi di halaman khusus yang simpel.",
      penjelasan:
        "Mengubah donatur insidental menjadi pendukung tetap — pendapatan fundraising lebih terprediksi.",
      angle: {
        TOFU: "Big idea: normalisasi — “kopi Rp20 ribu bisa, donasi Rp10 ribu kenapa tidak?”.",
        MOFU: "Big idea: hitung dampak — “Rp10 ribu × 12 bulan = 1 anak sekolah setahun”.",
        BOFU: "Big idea: mudahkan — satu klik daftar autodebet + bisa berhenti kapan saja.",
      },
    },
  ],
  generik__pendaftaran: [
    {
      id: "kumpul-kebaikan",
      namaTema: "Kumpul Kebaikan",
      bigIdea:
        "Satu hari penuh inspirasi: belajar, networking, dan aksi kebaikan bareng.",
      momentum: "Sepanjang tahun",
      tren: "Event komunitas + kolaborasi micro-influencer menjadi mesin pendaftaran organik 2026.",
      polaAcuan:
        "Rumah Zakat — charity partner event + influencer sebagai wajah kampanye dengan link terukur.",
      penjelasan:
        "Event menjadi pintu masuk komunitas — peserta hari ini adalah donatur/relawan tahun depan.",
      angle: {
        TOFU: "Big idea: bangun antisipasi — bocoran pembicara & keseruan tahun lalu.",
        MOFU: "Big idea: hilangkan ragu — rundown, harga transparan, testimoni alumni.",
        BOFU: "Big idea: kejar kursi — “batch terakhir”, early bird berakhir, countdown.",
      },
    },
  ],
  generik__jualan: [
    {
      id: "beli-sambil-berbagi",
      namaTema: "Beli Sambil Berbagi",
      bigIdea:
        "Setiap pembelian menyisihkan donasi — belanja jadi amal.",
      momentum: "Sepanjang tahun",
      tren: "Konsumen 2026 memilih brand berdampak; mekanisme “beli 1 = donasi 1” terbukti menaikkan konversi.",
      polaAcuan:
        "Dompet Dhuafa — “Borong Dagangan Saudaramu”; Rumah Zakat — kolaborasi CSR korporat.",
      penjelasan:
        "Diferensiasi dari kompetitor harga — alasan membeli yang tidak bisa ditiru diskon.",
      angle: {
        TOFU: "Big idea: kenalkan misi — siapa yang terbantu dari setiap pembelian.",
        MOFU: "Big idea: buktikan — “10.000 produk terjual = 10.000 paket tersalurkan”.",
        BOFU: "Big idea: dorong beli — bundling + “stok batch donasi terbatas”.",
      },
    },
  ],
  generik__awareness: [
    {
      id: "kenali-lebih-dekat",
      namaTema: "Kenali Lebih Dekat",
      bigIdea:
        "Buka dapur kami: siapa kami, ke mana dana mengalir, dan apa dampaknya.",
      momentum: "Sepanjang tahun",
      tren: "Transparansi adalah mata uang kepercayaan 2026; konten behind-the-scenes menaikkan kedekatan brand.",
      polaAcuan:
        "Dompet Dhuafa — CEO & ketua program tampil sebagai wajah; Rumah Zakat — CEO ikut menyembelihan & MoU.",
      penjelasan:
        "Awareness yang berfondasi trust — audiens kenal orangnya, bukan cuma logonya.",
      angle: {
        TOFU: "Big idea: perkenalan — wajah tim, kantor, dan keseharian lapangan.",
        MOFU: "Big idea: transparansi — alur dana divisualkan + laporan teraudit.",
        BOFU: "Big idea: ajak terlibat — follow, share, atau jadi relawan.",
      },
    },
  ],
};

export interface HasilRekomendasi {
  momentum: Momentum | null;
  daftar: RekomendasiTema[];
}

/**
 * Menghasilkan 1–2 rekomendasi tema campaign dari brief + rentang tanggal.
 * Momentum keagamaan diprioritaskan bila campaign menyentuhnya.
 */
export function rekomendasiTema(
  brief: Pick<BriefCampaign, "mengapa">,
  tanggalMulai: string,
  tanggalTarget: string
): HasilRekomendasi {
  const momentum = deteksiMomentum(tanggalMulai, tanggalTarget);
  const kunci: KunciTema = `${momentum ? momentum.id : "generik"}__${brief.mengapa}`;
  const daftar = BANK_TEMA[kunci] ?? BANK_TEMA[`generik__${brief.mengapa}`];
  return { momentum, daftar };
}
