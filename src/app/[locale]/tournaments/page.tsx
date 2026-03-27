import { supabase } from "@/lib/supabase";
import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import TournamentFilters from "@/components/TournamentFilters";

export async function generateMetadata() {
  const t = await getTranslations("tournaments");
  return { title: t("title") };
}

export default async function TournamentsPage() {
  const t = await getTranslations("tournaments");

  const { data: tournaments } = await supabase
    .from("tournaments")
    .select("id, slug, name, name_ja, series, event_type, region, start_date, end_date, prize_pool_usd, is_lan, location, status")
    .neq("series", "DEPRECATED")
    .order("start_date", { ascending: false });

  // 各大会の結果件数を取得（結果があるかどうかの判定用）
  const { data: resultCounts } = await supabase
    .from("tournament_results")
    .select("tournament_id")
    .limit(1000);

  const tournamentsWithResults = new Set(
    resultCounts?.map((r) => r.tournament_id) || []
  );

  // series一覧（Year順ソート）
  const allSeries = [
    ...new Set(tournaments?.map((t) => t.series).filter(Boolean) || []),
  ].sort((a, b) => {
    const getYear = (s: string) => {
      const m = s.match(/Year\s*(\d+)/);
      return m ? parseInt(m[1]) : 0;
    };
    return getYear(b) - getYear(a);
  });

  // seriesでグループ化
  const grouped: Record<string, typeof tournaments> = {};
  for (const t of tournaments || []) {
    const key = t.series || "Other";
    if (!grouped[key]) grouped[key] = [];
    grouped[key]!.push(t);
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-2">{t("title")}</h1>
      <p className="text-gray-400 text-sm mb-6">
        {tournaments?.length || 0} tournaments across ALGS Year 2-6
      </p>

      <TournamentFilters
        allSeries={allSeries}
        grouped={grouped}
        tournamentsWithResults={[...tournamentsWithResults]}
      />
    </div>
  );
}
