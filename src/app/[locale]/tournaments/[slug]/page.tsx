import { supabase } from "@/lib/supabase";
import { getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";
import { Link } from "@/i18n/navigation";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const { data: tournament } = await supabase
    .from("tournaments")
    .select("name")
    .eq("slug", slug)
    .single();

  return { title: tournament?.name || "Tournament" };
}

export default async function TournamentDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const t = await getTranslations("tournaments");
  const tr = await getTranslations("regions");

  const { data: tournament } = await supabase
    .from("tournaments")
    .select("*")
    .eq("slug", slug)
    .single();

  if (!tournament) notFound();

  // 順位表
  const { data: results } = await supabase
    .from("tournament_results")
    .select("*, teams(name, slug, short_name)")
    .eq("tournament_id", tournament.id)
    .order("placement");

  // ステージ一覧
  const { data: stages } = await supabase
    .from("tournament_stages")
    .select("*")
    .eq("tournament_id", tournament.id)
    .order("stage_order");

  const statusColors: Record<string, string> = {
    ongoing: "bg-green-600",
    upcoming: "bg-blue-600",
    completed: "bg-gray-600",
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* 大会ヘッダー */}
      <div className="bg-gray-900 rounded-xl p-6 mb-6 border border-gray-800">
        <div className="flex items-start justify-between gap-2 mb-2">
          <h1 className="text-3xl font-bold">{tournament.name}</h1>
          <span
            className={`${statusColors[tournament.status]} text-xs px-2 py-1 rounded shrink-0`}
          >
            {t(tournament.status as "ongoing" | "upcoming" | "completed")}
          </span>
        </div>
        {tournament.name_ja && (
          <p className="text-white mb-4">{tournament.name_ja}</p>
        )}

        <div className="flex flex-wrap gap-4 text-sm text-white">
          {tournament.region && (
            <span>
              {tr(tournament.region as "APAC_N" | "APAC_S" | "NA" | "EMEA" | "GLOBAL")}
            </span>
          )}
          {tournament.event_type && (
            <span className="capitalize">{tournament.event_type.replace("_", " ")}</span>
          )}
          {tournament.start_date && (
            <span>
              {tournament.start_date}
              {tournament.end_date ? ` ~ ${tournament.end_date}` : ""}
            </span>
          )}
          {tournament.prize_pool_usd && (
            <span className="text-yellow-500 font-medium">
              {t("prizePool")}: ${tournament.prize_pool_usd.toLocaleString()}
            </span>
          )}
          {tournament.is_lan && (
            <span className="text-orange-400">LAN</span>
          )}
          {tournament.location && <span>{tournament.location}</span>}
        </div>
      </div>

      {/* 順位表 */}
      <section className="mb-6">
        <h2 className="text-xl font-bold mb-4">{t("standings")}</h2>
        {results && results.length > 0 ? (
          <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-white">
                  <th className="text-center p-3 w-16">{t("placement")}</th>
                  <th className="text-left p-3">{t("team")}</th>
                  <th className="text-center p-3">{t("points")}</th>
                  <th className="text-center p-3">{t("kills")}</th>
                  <th className="text-center p-3">{t("match")}</th>
                  <th className="text-right p-3">Prize</th>
                </tr>
              </thead>
              <tbody>
                {results.map((result) => {
                  const team = result.teams as { name: string; slug: string; short_name?: string } | null;
                  return (
                    <tr
                      key={result.id}
                      className="border-b border-gray-800/50 hover:bg-gray-800/50"
                    >
                      <td className="text-center p-3">
                        <span
                          className={
                            result.placement === 1
                              ? "text-yellow-400 font-bold text-lg"
                              : result.placement === 2
                                ? "text-gray-300 font-bold"
                                : result.placement === 3
                                  ? "text-orange-400 font-bold"
                                  : "text-white"
                          }
                        >
                          #{result.placement}
                        </span>
                      </td>
                      <td className="p-3">
                        <Link
                          href={`/teams/${team?.slug}`}
                          className="text-white hover:text-red-400 font-medium"
                        >
                          {team?.name}
                        </Link>
                      </td>
                      <td className="text-center p-3 text-white">
                        {result.total_points ?? "-"}
                      </td>
                      <td className="text-center p-3 text-white">
                        {result.total_kills ?? "-"}
                      </td>
                      <td className="text-center p-3 text-white">
                        {result.games_played ?? "-"}
                      </td>
                      <td className="text-right p-3 text-yellow-500">
                        {result.prize_usd
                          ? `$${result.prize_usd.toLocaleString()}`
                          : "-"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="bg-gray-900 rounded-lg p-6 text-center text-gray-500 text-sm">
            データなし
          </div>
        )}
      </section>
    </div>
  );
}
