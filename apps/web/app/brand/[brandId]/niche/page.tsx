"use client";

import { useParams } from "next/navigation";
import { RequireAuth } from "@/lib/auth";
import BrandNav from "@/components/BrandNav";
import NicheFinder from "@/components/NicheFinder";

export default function NichePage() {
  const params = useParams();
  const brandId = params.brandId as string;
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
