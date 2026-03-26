import { supabase } from "@/lib/supabase";
import { getTranslations } from "next-intl/server";
import { TeamList } from "@/components/TeamList";

export async function generateMetadata() {
  const t = await getTranslations("teams");
  return { title: t("title") };
}

export default async function TeamsPage() {
  const t = await getTranslations("teams");

  const { data: teams } = await supabase
    .from("teams")
    .select("id, slug, name, name_ja, short_name, region, logo_url")
    .eq("is_active", true)
    .order("name");

  // プロリーグチーム判定: ALGSソースのアクティブロスターが3人以上あるチーム
  const { data: proRosters } = await supabase
    .from("team_rosters")
    .select("team_id")
    .is("left_at", null)
    .like("source_url", "%algs%");

  const proTeamCounts = new Map<string, number>();
  for (const r of proRosters || []) {
    proTeamCounts.set(r.team_id, (proTeamCounts.get(r.team_id) || 0) + 1);
  }
  const proTeamIds = new Set(
    [...proTeamCounts.entries()]
      .filter(([, count]) => count >= 3)
      .map(([id]) => id)
  );

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">{t("title")}</h1>
      {teams && teams.length > 0 ? (
        <TeamList teams={teams} proTeamIds={[...proTeamIds]} />
      ) : (
        <div className="bg-gray-900 rounded-xl p-12 text-center text-gray-400">
          <p className="text-lg mb-2">Coming soon...</p>
          <p className="text-sm">データ投入準備中です</p>
        </div>
      )}
    </div>
  );
}
