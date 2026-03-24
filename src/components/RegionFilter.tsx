"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

type Region = "APAC_N" | "APAC_S" | "NA" | "EMEA";

interface RegionFilterProps<T> {
  items: T[];
  getRegion: (item: T) => string | null;
  renderItems: (filtered: T[]) => React.ReactNode;
}

export function RegionFilter<T>({ items, getRegion, renderItems }: RegionFilterProps<T>) {
  const [selected, setSelected] = useState<Region | null>(null);
  const t = useTranslations("players");
  const tr = useTranslations("regions");

  const regions: Region[] = ["APAC_N", "APAC_S", "NA", "EMEA"];

  const filtered = selected
    ? items.filter((item) => getRegion(item) === selected)
    : items;

  return (
    <>
      <div className="flex gap-2 mb-6 flex-wrap">
        <button
          onClick={() => setSelected(null)}
          className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
            selected === null
              ? "bg-red-600 text-white"
              : "bg-gray-800 hover:bg-gray-700 text-gray-300"
          }`}
        >
          {t("allRegions")}
        </button>
        {regions.map((r) => (
          <button
            key={r}
            onClick={() => setSelected(selected === r ? null : r)}
            className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
              selected === r
                ? "bg-red-600 text-white"
                : "bg-gray-800 hover:bg-gray-700 text-gray-300"
            }`}
          >
            {tr(r)}
          </button>
        ))}
      </div>
      {renderItems(filtered)}
    </>
  );
}
