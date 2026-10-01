"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatAngka } from "@/lib/format";

export type BandingItem = {
  label: string;
  Nilai: number | null;
  mom?: number | null;
  yoy?: number | null;
};

/** Grafik batang perbandingan MoM/YoY — di-load lazy agar bundle awal ringan. */
export default function BandingChart({
  data,
  warna,
  label,
}: {
  data: BandingItem[];
  warna: string;
  label: string;
}) {
  return (
    <div className="mb-6 h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} stroke="#64748b" />
          <YAxis tick={{ fontSize: 12 }} stroke="#64748b" />
          <Tooltip
            formatter={(value, _name, item) => {
              const p = item?.payload as { mom?: number | null; yoy?: number | null } | undefined;
              const ket: string[] = [];
              if (p?.mom !== null && p?.mom !== undefined) ket.push(`MoM ${p.mom > 0 ? "+" : ""}${p.mom}%`);
              if (p?.yoy !== null && p?.yoy !== undefined) ket.push(`YoY ${p.yoy > 0 ? "+" : ""}${p.yoy}%`);
              return [formatAngka(typeof value === "number" ? value : null, 1), ket.join(" · ") || label];
            }}
          />
          <Bar dataKey="Nilai" fill={warna} radius={[6, 6, 0, 0]} name={label} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
