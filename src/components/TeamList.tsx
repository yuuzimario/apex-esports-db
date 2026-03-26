"use client";

import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { useCallback, useMemo } from "react";

type Team = {
  id: string;
  slug: string;
  name: string;
  name_ja?: string | null;
  short_name?: string | null;
  region?: string | null;
  logo_url?: string | null;
};

type Region = "APAC_N" | "APAC_S" | "NA" | "EMEA";

const VALID_REGIONS: Region[] = ["APAC_N", "APAC_S", "NA", "EMEA"];

export function TeamList({ teams, proTeamIds = [] }: { teams: Team[]; proTeamIds?: string[] }) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const t = useTranslations("players");
  const tt = useTranslations("teams");
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

  const filtered = selected ? teams.filter((t) => t.region === selected) : teams;

  const proSet = useMemo(() => new Set(proTeamIds), [proTeamIds]);
  const proTeams = filtered.filter((t) => proSet.has(t.id));
  const otherTeams = filtered.filter((t) => !proSet.has(t.id));

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

      {/* プロリーグチーム */}
      {proTeams.length > 0 && (
        <section className="mb-8">
          <div className="flex items-center gap-2 mb-4 bg-gray-900 rounded-lg px-4 py-2 border border-gray-800">
            <span className="w-2 h-2 bg-red-500 rounded-full shrink-0" />
            <h2 className="text-lg font-bold text-white">{tt("proLeague")}</h2>
            <span className="text-sm font-normal text-gray-400">({proTeams.length})</span>
          </div>
          <TeamGrid teams={proTeams} />
        </section>
      )}

      {/* その他のチーム */}
      {otherTeams.length > 0 && (
        <section>
          {proTeams.length > 0 && (
            <div className="flex items-center gap-2 mb-4 bg-gray-900 rounded-lg px-4 py-2 border border-gray-800">
              <span className="w-2 h-2 bg-gray-500 rounded-full shrink-0" />
              <h2 className="text-lg font-bold text-white">{tt("otherTeams")}</h2>
              <span className="text-sm font-normal text-gray-400">({otherTeams.length})</span>
            </div>
          )}
          <TeamGrid teams={otherTeams} />
        </section>
      )}
    </>
  );
}

function TeamGrid({ teams }: { teams: Team[] }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {teams.map((team) => (
        <Link
          key={team.id}
          href={`/teams/${team.slug}`}
          className="bg-gray-900 rounded-xl p-5 hover:bg-gray-800 transition-colors border border-gray-800 hover:border-gray-700"
        >
          <div className="flex items-center gap-4">
            {team.logo_url ? (
              <img
                src={team.logo_url}
                alt={team.name}
                className="w-14 h-14 rounded-lg bg-gray-700 object-contain p-1 shrink-0"
              />
            ) : (
              <div className="w-14 h-14 rounded-lg bg-gray-700 flex items-center justify-center text-xl font-bold text-gray-400 shrink-0">
                {team.short_name || team.name.substring(0, 2).toUpperCase()}
              </div>
            )}
            <div className="min-w-0">
              <p className="font-bold text-white truncate">{team.name}</p>
              {team.name_ja && (
                <p className="text-sm text-gray-400 truncate">{team.name_ja}</p>
              )}
              {team.region && (
                <span className="text-xs bg-gray-700 text-white px-2 py-0.5 rounded mt-1 inline-block">
                  {team.region}
                </span>
              )}
            </div>
          </div>
        </Link>
      ))}
    </div>
  );
}
