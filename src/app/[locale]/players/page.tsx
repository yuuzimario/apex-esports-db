import { supabase } from "@/lib/supabase";
import { getTranslations } from "next-intl/server";
import { PlayerList } from "@/components/PlayerList";

export async function generateMetadata() {
  const t = await getTranslations("players");
  return { title: t("title") };
}

export default async function PlayersPage() {
  const t = await getTranslations("players");

  const { data: players } = await supabase
    .from("players")
    .select("id, slug, ign, real_name_ja, region, role")
    .eq("is_active", true)
    .order("ign");

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">{t("title")}</h1>
      {players && players.length > 0 ? (
        <PlayerList players={players} />
      ) : (
        <div className="bg-gray-900 rounded-xl p-12 text-center text-gray-400">
          <p className="text-lg mb-2">Coming soon...</p>
          <p className="text-sm">データ投入準備中です</p>
        </div>
      )}
    </div>
  );
}
