"use client";

import { useState } from "react";
import type { PresetPeriode } from "@/lib/types";

export interface PilihanPeriode {
  preset: PresetPeriode;
  start?: string;
  end?: string;
}

// Pemilih periode: 7 hari / 30 hari / Bulan ini / Kustom (date input).
export default function PeriodPicker({
  value,
  onChange,
}: {
  value: PilihanPeriode;
  onChange: (p: PilihanPeriode) => void;
}) {
  const [customOpen, setCustomOpen] = useState(value.preset === "custom");

  const opsi: { key: PresetPeriode; label: string }[] = [
    { key: "7d", label: "7 hari" },
    { key: "30d", label: "30 hari" },
    { key: "bulan_ini", label: "Bulan ini" },
    { key: "custom", label: "Kustom" },
  ];

  function pilih(key: PresetPeriode) {
    setCustomOpen(key === "custom");
    onChange({ preset: key });
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-1 rounded-xl border border-slate-200 bg-white p-1">
        {opsi.map((o) => (
          <button
            key={o.key}
            type="button"
            onClick={() => pilih(o.key)}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
              value.preset === o.key
                ? "bg-indigo-600 text-white"
                : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>
      {customOpen && (
        <div className="flex items-center gap-2 text-sm">
          <input
            type="date"
            value={value.start ?? ""}
            onChange={(e) =>
              onChange({ preset: "custom", start: e.target.value, end: value.end })
            }
            className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <span className="text-slate-400">s/d</span>
          <input
            type="date"
            value={value.end ?? ""}
            onChange={(e) =>
              onChange({ preset: "custom", start: value.start, end: e.target.value })
            }
            className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      )}
    </div>
  );
}
