import { supabase } from "@/lib/supabase";
import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";

export async function generateMetadata() {
  const t = await getTranslations("teams");
  return { title: t("title") };
}

export default async function TeamsPage() {
  const t = await getTranslations("teams");
  const tr = await getTranslations("regions");

  const { data: teams } = await supabase
    .from("teams")
    .select("id, slug, name, name_ja, short_name, region, logo_url, is_active")
    .eq("is_active", true)
    .order("name");

  const regions = ["APAC_N", "APAC_S", "NA", "EMEA"] as const;

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">{t("title")}</h1>

      {/* リージョンフィルター */}
      <div className="flex gap-2 mb-6 flex-wrap">
        <span className="px-3 py-1 bg-red-600 rounded-full text-sm font-medium">
          All
        </span>
        {regions.map((r) => (
          <span
            key={r}
            className="px-3 py-1 bg-gray-800 hover:bg-gray-700 rounded-full text-sm cursor-pointer transition-colors"
          >
            {tr(r)}
          </span>
        ))}
      </div>

      {/* チーム一覧 */}
      {teams && teams.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {teams.map((team) => (
            <Link
              key={team.id}
              href={`/teams/${team.slug}`}
              className="bg-gray-900 rounded-xl p-5 hover:bg-gray-800 transition-colors border border-gray-800 hover:border-gray-700"
            >
              <div className="flex items-center gap-4">
                {/* チームロゴ */}
                <div className="w-14 h-14 rounded-lg bg-gray-700 flex items-center justify-center text-xl font-bold text-gray-400 shrink-0">
                  {team.short_name || team.name.substring(0, 2).toUpperCase()}
                </div>
                <div className="min-w-0">
                  <p className="font-bold text-white truncate">{team.name}</p>
                  {team.name_ja && (
                    <p className="text-sm text-gray-400 truncate">
                      {team.name_ja}
                    </p>
                  )}
                  {team.region && (
                    <span className="text-xs bg-gray-700 px-2 py-0.5 rounded mt-1 inline-block">
                      {tr(team.region as keyof typeof tr)}
                    </span>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="bg-gray-900 rounded-xl p-12 text-center text-gray-500">
          <p className="text-lg mb-2">Coming soon...</p>
          <p className="text-sm">データ投入準備中です</p>
        </div>
      )}
    </div>
  );
}
