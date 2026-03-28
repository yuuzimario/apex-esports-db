"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";

type Tournament = {
  id: string;
  slug: string;
  name: string;
  name_ja: string | null;
  series: string;
  event_type: string;
  region: string;
  start_date: string;
  end_date: string;
  prize_pool_usd: number | null;
  is_lan: boolean;
  location: string | null;
  status: string;
};

export default function TournamentFilters({
  allSeries,
  grouped,
  tournamentsWithResults,
}: {
  allSeries: string[];
  grouped: Record<string, Tournament[] | null>;
  tournamentsWithResults: string[];
}) {
  const t = useTranslations("tournaments");
  const tr = useTranslations("regions");
  const [selectedSeries, setSelectedSeries] = useState<string>("all");

  const resultsSet = new Set(tournamentsWithResults);

  const statusColors: Record<string, string> = {
    ongoing: "bg-green-600",
    upcoming: "bg-blue-600",
    completed: "bg-gray-600",
  };

  const eventTypeLabels: Record<string, string> = {
    championship: "Championship",
    playoffs: "Playoffs",
    pro_league: "Pro League",
    qualifier: "Qualifier",
    lcq: "LCQ",
    open: "Open",
  };

  const visibleGroups =
    selectedSeries === "all"
      ? Object.entries(grouped)
      : Object.entries(grouped).filter(([key]) => key === selectedSeries);

  return (
    <>
      {/* シリーズフィルター */}
      <div className="flex flex-wrap gap-2 mb-8">
        <button
          onClick={() => setSelectedSeries("all")}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            selectedSeries === "all"
              ? "bg-red-600 text-white"
              : "bg-gray-800 text-gray-300 hover:bg-gray-700"
          }`}
        >
          All
        </button>
        {allSeries.map((s) => (
          <button
            key={s}
            onClick={() => setSelectedSeries(s)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              selectedSeries === s
                ? "bg-red-600 text-white"
                : "bg-gray-800 text-gray-300 hover:bg-gray-700"
            }`}
          >
            {s.replace("ALGS ", "")}
          </button>
        ))}
      </div>

      {/* グループ別表示（completedのみ。upcoming/ongoingはスケジュールページに分離） */}
      <div className="space-y-10">
        {visibleGroups.map(([series, tournaments]) => {
          if (!tournaments || tournaments.length === 0) return null;

          const completed = tournaments.filter((t) => t.status === "completed");
          if (completed.length === 0) return null;

          return (
            <section key={series}>
              <h2 className="text-xl font-bold mb-4 flex items-center gap-3">
                <span className="bg-gradient-to-r from-red-500 to-orange-400 bg-clip-text text-transparent">
                  {series}
                </span>
                <span className="text-xs text-gray-500 font-normal">
                  {completed.length} events
                </span>
              </h2>

              <div className="space-y-3">
                {completed.map((tour) => (
                  <TournamentRow
                    key={tour.id}
                    tournament={tour}
                    statusColors={statusColors}
                    eventTypeLabels={eventTypeLabels}
                    hasResults={resultsSet.has(tour.id)}
                    t={t}
                    tr={tr}
                  />
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </>
  );
}

function TournamentRow({
  tournament,
  statusColors,
  eventTypeLabels,
  hasResults,
  t,
  tr,
}: {
  tournament: Tournament;
  statusColors: Record<string, string>;
  eventTypeLabels: Record<string, string>;
  hasResults: boolean;
  t: ReturnType<typeof useTranslations>;
  tr: ReturnType<typeof useTranslations>;
}) {
  return (
    <Link
      href={`/tournaments/${tournament.slug}`}
      className="flex items-center gap-4 bg-gray-900 rounded-lg px-4 py-3 hover:bg-gray-800 transition-colors border border-gray-800 hover:border-gray-700 group"
    >
      {/* ステータス */}
      <div className="shrink-0">
        {tournament.status === "ongoing" ? (
          <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse inline-block" />
        ) : (
          <span
            className={`w-2 h-2 rounded-full inline-block ${
              tournament.status === "upcoming" ? "bg-blue-500" : "bg-gray-600"
            }`}
          />
        )}
      </div>

      {/* 大会名 + メタ情報 */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <h3 className="font-medium text-white text-sm truncate group-hover:text-red-400 transition-colors">
            {tournament.name}
          </h3>
          {tournament.is_lan && (
            <span className="text-[10px] px-1.5 py-0.5 bg-orange-900/50 text-orange-400 rounded shrink-0">
              LAN
            </span>
          )}
        </div>
        <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-gray-400 mt-0.5">
          {tournament.event_type && (
            <span>
              {eventTypeLabels[tournament.event_type] ||
                tournament.event_type}
            </span>
          )}
          {tournament.region && tournament.region !== "GLOBAL" && (
            <span>
              {tr(
                tournament.region as
                  | "APAC_N"
                  | "APAC_S"
                  | "NA"
                  | "EMEA"
                  | "GLOBAL"
              )}
            </span>
          )}
          {tournament.location && <span>{tournament.location}</span>}
        </div>
      </div>

      {/* 日付 */}
      <div className="text-xs text-gray-500 shrink-0 hidden sm:block">
        {tournament.start_date?.slice(0, 7)}
      </div>

      {/* 賞金 */}
      {tournament.prize_pool_usd ? (
        <div className="text-xs text-yellow-500 font-medium shrink-0 hidden md:block w-24 text-right">
          ${tournament.prize_pool_usd.toLocaleString()}
        </div>
      ) : (
        <div className="w-24 shrink-0 hidden md:block" />
      )}

      {/* 結果有無 */}
      <div className="shrink-0 w-16 text-right">
        {hasResults ? (
          <span className="text-[10px] px-2 py-0.5 bg-green-900/30 text-green-400 rounded">
            Results
          </span>
        ) : (
          <span className="text-[10px] px-2 py-0.5 bg-gray-800 text-gray-500 rounded">
            No data
          </span>
        )}
      </div>
    </Link>
  );
}
