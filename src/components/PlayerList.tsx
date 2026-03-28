"use client";

import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { useCallback } from "react";

type Player = {
  id: string;
  slug: string;
  ign: string;
  real_name_ja?: string | null;
  region?: string | null;
  role?: string | null;
  profile_image_url?: string | null;
};

type Region = "APAC_N" | "APAC_S" | "NA" | "EMEA";

const VALID_REGIONS: Region[] = ["APAC_N", "APAC_S", "NA", "EMEA"];

export function PlayerList({ players }: { players: Player[] }) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const t = useTranslations("players");
  const tr = useTranslations("regions");

  const regionParam = searchParams.get("region");
  const selected: Region | null =
    regionParam === "ALL"
      ? null
      : regionParam && VALID_REGIONS.includes(regionParam as Region)
        ? (regionParam as Region)
        : "APAC_N";

  const setSelected = useCallback(
    (region: Region | null) => {
      const params = new URLSearchParams(searchParams.toString());
      if (region) {
        params.set("region", region);
      } else {
        params.set("region", "ALL");
      }
      const qs = params.toString();
      router.replace(`${pathname}${qs ? `?${qs}` : ""}`, { scroll: false });
    },
    [searchParams, router, pathname]
  );

  const filtered = selected ? players.filter((p) => p.region === selected) : players;

  return (
    <>
      <div className="flex gap-2 mb-6 flex-wrap">
        {VALID_REGIONS.map((r) => (
          <button
            key={r}
            onClick={() => setSelected(r)}
            className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
              selected === r ? "bg-red-600 text-white" : "bg-gray-800 hover:bg-gray-700 text-gray-300"
            }`}
          >
            {tr(r)}
          </button>
        ))}
        <button
          onClick={() => setSelected(null)}
          className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
            selected === null ? "bg-red-600 text-white" : "bg-gray-800 hover:bg-gray-700 text-gray-300"
          }`}
        >
          {t("allRegions")}
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map((player) => (
          <Link
            key={player.id}
            href={`/players/${player.slug}`}
            className="bg-gray-900 rounded-xl p-4 hover:bg-gray-800 transition-colors border border-gray-800 hover:border-gray-700"
          >
            <div className="flex items-center gap-3">
              {player.profile_image_url ? (
                <img
                  src={player.profile_image_url}
                  alt={player.ign}
                  className="w-12 h-12 rounded-full bg-gray-700 object-cover shrink-0"
                />
              ) : (
                <div className="w-12 h-12 rounded-full bg-gray-700 flex items-center justify-center text-lg font-bold text-gray-400 shrink-0">
                  {player.ign.charAt(0).toUpperCase()}
                </div>
              )}
              <div className="min-w-0">
                <p className="font-bold text-white truncate">{player.ign}</p>
                {player.real_name_ja && (
                  <p className="text-sm text-gray-400 truncate">{player.real_name_ja}</p>
                )}
                <div className="flex items-center gap-2 mt-1">
                  {player.region && (
                    <span className="text-xs bg-gray-700 px-2 py-0.5 rounded">{player.region}</span>
                  )}
                  {player.role && (
                    <span className="text-xs text-gray-400">{player.role}</span>
                  )}
                </div>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </>
  );
}
