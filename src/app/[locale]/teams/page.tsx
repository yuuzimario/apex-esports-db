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
    .select("id, slug, name, name_ja, short_name, region")
    .eq("is_active", true)
    .order("name");

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">{t("title")}</h1>
      {teams && teams.length > 0 ? (
        <TeamList teams={teams} />
      ) : (
        <div className="bg-gray-900 rounded-xl p-12 text-center text-gray-500">
          <p className="text-lg mb-2">Coming soon...</p>
          <p className="text-sm">データ投入準備中です</p>
        </div>
      )}
    </div>
  );
}
