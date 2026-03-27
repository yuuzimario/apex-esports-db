import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { supabase } from "@/lib/supabase";

async function getHomeData() {
  // 最新の大会結果（結果データがある大会のみ、上位3大会）
  // まず結果がある大会IDを取得
  const { data: resultTournamentIds } = await supabase
    .from("tournament_results")
    .select("tournament_id")
    .limit(2000);
  const hasResultsSet = new Set(
    resultTournamentIds?.map((r) => r.tournament_id) || []
  );

  const { data: allCompleted } = await supabase
    .from("tournaments")
    .select("id, slug, name, series, event_type, region, start_date, end_date, prize_pool_usd, is_lan, location, status")
    .eq("status", "completed")
    .neq("series", "DEPRECATED")
    .order("end_date", { ascending: false })
    .limit(20);

  // 結果がある大会だけフィルタし、GLOBAL→APAC_N優先でソート
  const regionPriority: Record<string, number> = {
    GLOBAL: 0,
    APAC_N: 1,
    APAC_S: 2,
    NA: 3,
    EMEA: 4,
  };
  const recentTournaments = (allCompleted || [])
    .filter((t) => hasResultsSet.has(t.id))
    .sort((a, b) => {
      // まず日付降順（同じ期間の大会をグループ化）
      const dateA = a.end_date || "";
      const dateB = b.end_date || "";
      if (dateA !== dateB) return dateB.localeCompare(dateA);
      // 同日ならリージョン優先度
      return (regionPriority[a.region] ?? 5) - (regionPriority[b.region] ?? 5);
    })
    .slice(0, 3);

  // 各大会のTOP3チーム
  const tournamentsWithResults = [];
  for (const t of recentTournaments) {
    const { data: results } = await supabase
      .from("tournament_results")
      .select("placement, total_points, teams(name, slug, logo_url)")
      .eq("tournament_id", t.id)
      .order("placement")
      .limit(3);
    tournamentsWithResults.push({ ...t, top3: results || [] });
  }

  // DB統計
  const [
    { count: teamCount },
    { count: playerCount },
    { count: tournamentCount },
  ] = await Promise.all([
    supabase.from("teams").select("*", { count: "exact", head: true }),
    supabase.from("players").select("*", { count: "exact", head: true }),
    supabase.from("tournaments").select("*", { count: "exact", head: true }),
  ]);

  return {
    recentTournaments: tournamentsWithResults,
    stats: {
      teams: teamCount || 0,
      players: playerCount || 0,
      tournaments: tournamentCount || 0,
    },
  };
}

export default async function HomePage() {
  const { recentTournaments, stats } = await getHomeData();

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return <HomeContent recentTournaments={recentTournaments as any} stats={stats} />;
}

function HomeContent({
  recentTournaments,
  stats,
}: {
  recentTournaments: Array<{
    slug: string;
    name: string;
    series: string;
    event_type: string;
    region: string;
    start_date: string;
    end_date: string;
    prize_pool_usd: number | null;
    is_lan: boolean;
    location: string | null;
    top3: Array<{
      placement: number;
      total_points: number | null;
      teams: { name: string; slug: string; logo_url: string | null } | null;
    }>;
  }>;
  stats: { teams: number; players: number; tournaments: number };
}) {
  const t = useTranslations("home");
  const tc = useTranslations("common");

  const placementColors = ["text-yellow-400", "text-gray-300", "text-orange-400"];
  const placementLabels = ["🥇", "🥈", "🥉"];

  return (
    <div>
      {/* ヒーローセクション */}
      <section className="relative overflow-hidden bg-gradient-to-br from-gray-950 via-red-950/20 to-gray-950 py-20 px-4">
        <div className="max-w-5xl mx-auto text-center">
          <h1 className="text-4xl md:text-6xl font-bold mb-4 bg-gradient-to-r from-red-500 to-orange-400 bg-clip-text text-transparent">
            {t("hero")}
          </h1>
          <p className="text-lg md:text-xl text-gray-400 mb-8">
            {t("heroSub")}
          </p>
          <div className="flex gap-4 justify-center flex-wrap">
            <Link
              href="/players"
              className="px-6 py-3 bg-red-600 hover:bg-red-700 rounded-lg font-medium transition-colors"
            >
              {tc("players")}
            </Link>
            <Link
              href="/teams"
              className="px-6 py-3 bg-gray-800 hover:bg-gray-700 rounded-lg font-medium transition-colors"
            >
              {tc("teams")}
            </Link>
            <Link
              href="/tournaments"
              className="px-6 py-3 bg-gray-800 hover:bg-gray-700 rounded-lg font-medium transition-colors"
            >
              {tc("tournaments")}
            </Link>
          </div>
        </div>
      </section>

      {/* 統計カウンター */}
      <section className="max-w-4xl mx-auto px-4 -mt-8 relative z-10">
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: tc("players"), value: stats.players, href: "/players" },
            { label: tc("teams"), value: stats.teams, href: "/teams" },
            { label: tc("tournaments"), value: stats.tournaments, href: "/tournaments" },
          ].map((s) => (
            <Link
              key={s.label}
              href={s.href}
              className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center hover:border-red-800 transition-colors"
            >
              <div className="text-2xl md:text-3xl font-bold text-red-400">
                {s.value.toLocaleString()}
              </div>
              <div className="text-xs md:text-sm text-gray-400 mt-1">
                {s.label}
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* 最新の大会結果セクション */}
      <section className="max-w-6xl mx-auto px-4 py-12">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold">{t("latestResults")}</h2>
          <Link
            href="/tournaments"
            className="text-red-400 hover:text-red-300 text-sm"
          >
            {t("viewAll")} →
          </Link>
        </div>

        {recentTournaments.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {recentTournaments.map((tournament) => (
              <Link
                key={tournament.slug}
                href={`/tournaments/${tournament.slug}`}
                className="bg-gray-900 rounded-xl border border-gray-800 hover:border-gray-700 transition-colors overflow-hidden block"
              >
                {/* 大会ヘッダー */}
                <div className="p-4 border-b border-gray-800">
                  <h3 className="font-bold text-white text-sm leading-tight mb-1">
                    {tournament.name}
                  </h3>
                  <div className="flex flex-wrap gap-2 text-xs text-gray-400">
                    <span>{tournament.region}</span>
                    {tournament.end_date && <span>{tournament.end_date}</span>}
                    {tournament.prize_pool_usd && (
                      <span className="text-yellow-500">
                        ${tournament.prize_pool_usd.toLocaleString()}
                      </span>
                    )}
                    {tournament.is_lan && (
                      <span className="text-orange-400">LAN</span>
                    )}
                  </div>
                </div>

                {/* TOP3 */}
                <div className="p-4 space-y-2">
                  {tournament.top3.map((result, i) => {
                    const team = result.teams as { name: string; slug: string; logo_url: string | null } | null;
                    return (
                      <div key={i} className="flex items-center gap-3">
                        <span className={`text-lg ${placementColors[i]}`}>
                          {placementLabels[i]}
                        </span>
                        {team?.logo_url ? (
                          <img
                            src={team.logo_url}
                            alt=""
                            className="w-5 h-5 object-contain"
                          />
                        ) : (
                          <div className="w-5 h-5 bg-gray-800 rounded text-[8px] flex items-center justify-center text-gray-500">
                            {team?.name?.[0]}
                          </div>
                        )}
                        <span className="text-white text-sm font-medium truncate flex-1">
                          {team?.name || "Unknown"}
                        </span>
                        {result.total_points != null && (
                          <span className="text-gray-400 text-xs">
                            {result.total_points}pts
                          </span>
                        )}
                      </div>
                    );
                  })}
                  {tournament.top3.length === 0 && (
                    <p className="text-gray-500 text-xs text-center py-2">
                      結果なし
                    </p>
                  )}
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="bg-gray-900 rounded-xl p-8 text-center text-gray-400">
            Coming soon...
          </div>
        )}
      </section>
    </div>
  );
}
