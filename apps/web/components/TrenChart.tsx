"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export type TrenItem = {
  label: string;
  rata_skor: number | null;
  rata_er: number | null;
};

function fmtPersen(n: number | null | undefined): string {
  if (n === null || n === undefined) return "-";
  return `${(n * 100).toLocaleString("id-ID", { maximumFractionDigits: 1 })}%`;
}

/** Grafik tren mingguan — di-load lazy agar bundle awal ringan. */
export default function TrenChart({ data }: { data: TrenItem[] }) {
  if (data.length === 0) {
    return <p className="text-sm text-slate-500">Belum ada data tren.</p>;
  }
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} stroke="#64748b" />
          <YAxis tick={{ fontSize: 12 }} stroke="#64748b" />
          <Tooltip
            formatter={(value, name) => {
              const v = typeof value === "number" ? value : null;
              const n = String(name ?? "");
              return [
                `${fmtPersen(v)}`,
                n === "rata_er" ? "Rata-rata ER" : "Rata-rata skor",
              ];
            }}
          />
          <Legend />
          <Line type="monotone" dataKey="rata_skor" name="Rata-rata skor" stroke="#4f46e5" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="rata_er" name="Rata-rata ER (%)" stroke="#f59e0b" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
