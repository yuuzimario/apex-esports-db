import { supabase } from "@/lib/supabase";
import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";

export async function generateMetadata() {
  const t = await getTranslations("players");
  return { title: t("title") };
}

export default async function PlayersPage() {
  const t = await getTranslations("players");
  const tr = await getTranslations("regions");

  const { data: players } = await supabase
    .from("players")
    .select("id, slug, ign, real_name, real_name_ja, nationality, region, role, profile_image_url, is_active")
    .eq("is_active", true)
    .order("ign");

  const regions = ["APAC_N", "APAC_S", "NA", "EMEA"] as const;

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">{t("title")}</h1>

      {/* リージョンフィルター */}
      <div className="flex gap-2 mb-6 flex-wrap">
        <span className="px-3 py-1 bg-red-600 rounded-full text-sm font-medium">
          {t("allRegions")}
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

      {/* 選手一覧 */}
      {players && players.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {players.map((player) => (
            <Link
              key={player.id}
              href={`/players/${player.slug}`}
              className="bg-gray-900 rounded-xl p-4 hover:bg-gray-800 transition-colors border border-gray-800 hover:border-gray-700"
            >
              <div className="flex items-center gap-3">
                {/* アバター */}
                <div className="w-12 h-12 rounded-full bg-gray-700 flex items-center justify-center text-lg font-bold text-gray-400 shrink-0">
                  {player.ign.charAt(0).toUpperCase()}
                </div>
                <div className="min-w-0">
                  <p className="font-bold text-white truncate">{player.ign}</p>
                  {player.real_name_ja && (
                    <p className="text-sm text-gray-400 truncate">
                      {player.real_name_ja}
                    </p>
                  )}
                  <div className="flex items-center gap-2 mt-1">
                    {player.region && (
                      <span className="text-xs bg-gray-700 px-2 py-0.5 rounded">
                        {tr(player.region as keyof typeof tr)}
                      </span>
                    )}
                    {player.role && (
                      <span className="text-xs text-gray-500">
                        {player.role}
                      </span>
                    )}
                  </div>
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
