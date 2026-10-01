"use client";

import { useBrandId } from "@/lib/brand";
import { RequireAuth } from "@/lib/auth";
import BrandNav from "@/components/BrandNav";
import NicheFinder from "@/components/NicheFinder";

export default function NichePage() {
  const brandId = useBrandId();
  return (
    <RequireAuth>
      <NicheFinder
        key={brandId}
        brandId={brandId}
        atas={<BrandNav brandId={brandId} />}
      />
    </RequireAuth>
  );
}
