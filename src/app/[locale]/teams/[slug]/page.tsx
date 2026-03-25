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
  const { data: team } = await supabase
    .from("teams")
    .select("name")
    .eq("slug", slug)
    .single();

  return { title: team?.name || "Team" };
}

export default async function TeamDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const t = await getTranslations("teams");
  const tr = await getTranslations("regions");

  const { data: team } = await supabase
    .from("teams")
    .select("*")
    .eq("slug", slug)
    .single();

  if (!team) notFound();

  // 現在のロスター
  const { data: currentRoster } = await supabase
    .from("team_rosters")
    .select("*, players(id, slug, ign, real_name_ja, role, nationality)")
    .eq("team_id", team.id)
    .is("left_at", null)
    .order("joined_at");

  // ロスター変更履歴
  const { data: rosterHistory } = await supabase
    .from("team_rosters")
    .select("*, players(id, slug, ign)")
    .eq("team_id", team.id)
    .not("left_at", "is", null)
    .order("left_at", { ascending: false });

  // 大会成績
  const { data: results } = await supabase
    .from("tournament_results")
    .select("*, tournaments(name, slug, start_date)")
    .eq("team_id", team.id)
    .order("placement");

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* チームヘッダー */}
      <div className="bg-gray-900 rounded-xl p-6 mb-6 border border-gray-800">
        <div className="flex items-center gap-4 mb-4">
          {team.logo_url ? (
            <img
              src={team.logo_url}
              alt={team.name}
              className="w-20 h-20 rounded-lg bg-gray-700 object-contain p-1 shrink-0"
            />
          ) : (
            <div className="w-20 h-20 rounded-lg bg-gray-700 flex items-center justify-center text-2xl font-bold text-gray-400 shrink-0">
              {team.short_name || team.name.substring(0, 3).toUpperCase()}
            </div>
          )}
          <div>
            <h1 className="text-3xl font-bold">{team.name}</h1>
            {team.name_ja && (
              <p className="text-white">{team.name_ja}</p>
            )}
          </div>
        </div>

        <div className="flex flex-wrap gap-3 text-sm">
          {team.region && (
            <span className="bg-gray-800 px-3 py-1 rounded">
              {t("region")}: {tr(team.region as "APAC_N" | "APAC_S" | "NA" | "EMEA" | "GLOBAL")}
            </span>
          )}
          {team.founded_date && (
            <span className="bg-gray-800 px-3 py-1 rounded">
              {t("founded")}: {team.founded_date}
            </span>
          )}
        </div>

        {/* リンク */}
        <div className="flex gap-4 mt-4 text-sm">
          {team.website_url && (
            <a
              href={team.website_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-400 hover:text-blue-300"
            >
              Website
            </a>
          )}
          {team.twitter_url && (
            <a
              href={team.twitter_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-400 hover:text-blue-300"
            >
              X (Twitter)
            </a>
          )}
        </div>

        {team.bio_ja && (
          <p className="text-white text-sm mt-4 leading-relaxed">
            {team.bio_ja}
          </p>
        )}
      </div>

      {/* 現在のロスター */}
      <section className="mb-6">
        <h2 className="text-xl font-bold mb-4">{t("roster")}</h2>
        {currentRoster && currentRoster.length > 0 ? (
          <div className="space-y-3">
            {currentRoster.map((member) => {
              const player = member.players as { id: string; slug: string; ign: string; real_name_ja?: string; role?: string; nationality?: string } | null;
              if (!player) return null;
              return (
                <Link
                  key={member.id}
                  href={`/players/${player.slug}`}
                  className="bg-gray-900 rounded-lg p-4 border border-gray-800 flex items-center justify-between hover:bg-gray-800 transition-colors block"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-gray-700 flex items-center justify-center font-bold text-gray-400">
                      {player.ign.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <p className="font-medium text-white">{player.ign}</p>
                      {player.real_name_ja && (
                        <p className="text-xs text-white">
                          {player.real_name_ja}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="text-xs text-white">
                    {member.role && <span>{member.role}</span>}
                  </div>
                </Link>
              );
            })}
          </div>
        ) : (
          <div className="bg-gray-900 rounded-lg p-6 text-center text-gray-400 text-sm">
            データなし
          </div>
        )}
      </section>

      {/* 大会成績 */}
      <section className="mb-6">
        <h2 className="text-xl font-bold mb-4">{t("results")}</h2>
        {results && results.length > 0 ? (
          <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-white">
                  <th className="text-left p-3">大会</th>
                  <th className="text-center p-3">順位</th>
                  <th className="text-center p-3">Pts</th>
                  <th className="text-center p-3">Kills</th>
                </tr>
              </thead>
              <tbody>
                {results.map((result) => {
                  const tournament = result.tournaments as { name: string; slug: string; start_date?: string } | null;
                  return (
                    <tr
                      key={result.id}
                      className="border-b border-gray-800/50 hover:bg-gray-800/50"
                    >
                      <td className="p-3">
                        <Link
                          href={`/tournaments/${tournament?.slug}`}
                          className="text-white hover:text-red-400"
                        >
                          {tournament?.name}
                        </Link>
                      </td>
                      <td className="text-center p-3">
                        <span
                          className={
                            result.placement === 1
                              ? "text-yellow-400 font-bold"
                              : result.placement <= 3
                                ? "text-orange-400 font-bold"
                                : ""
                          }
                        >
                          #{result.placement}
                        </span>
                      </td>
                      <td className="text-center p-3 text-white">
                        {result.total_points ?? "-"}
                      </td>
                      <td className="text-center p-3 text-white">
                        {result.total_kills ?? "-"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="bg-gray-900 rounded-lg p-6 text-center text-gray-400 text-sm">
            データなし
          </div>
        )}
      </section>

      {/* ロスター変更履歴 */}
      {rosterHistory && rosterHistory.length > 0 && (
        <section>
          <h2 className="text-xl font-bold mb-4">{t("rosterHistory")}</h2>
          <div className="space-y-2">
            {rosterHistory.map((member) => {
              const player = member.players as { id: string; slug: string; ign: string } | null;
              if (!player) return null;
              return (
                <div
                  key={member.id}
                  className="bg-gray-900 rounded-lg p-3 border border-gray-800 flex items-center justify-between text-sm"
                >
                  <Link
                    href={`/players/${player.slug}`}
                    className="text-white hover:text-red-400"
                  >
                    {player.ign}
                  </Link>
                  <span className="text-white">
                    {member.joined_at} ~ {member.left_at}
                  </span>
                </div>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
