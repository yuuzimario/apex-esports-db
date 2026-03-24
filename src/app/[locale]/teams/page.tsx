import { supabase } from "@/lib/supabase";
import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { RegionFilter } from "@/components/RegionFilter";

export async function generateMetadata() {
  const t = await getTranslations("teams");
  return { title: t("title") };
}

function TeamCard({ team }: { team: { id: string; slug: string; name: string; name_ja?: string; short_name?: string; region?: string } }) {
  return (
    <Link
      href={`/teams/${team.slug}`}
      className="bg-gray-900 rounded-xl p-5 hover:bg-gray-800 transition-colors border border-gray-800 hover:border-gray-700"
    >
      <div className="flex items-center gap-4">
        <div className="w-14 h-14 rounded-lg bg-gray-700 flex items-center justify-center text-xl font-bold text-gray-400 shrink-0">
          {team.short_name || team.name.substring(0, 2).toUpperCase()}
        </div>
        <div className="min-w-0">
          <p className="font-bold text-white truncate">{team.name}</p>
          {team.name_ja && (
            <p className="text-sm text-gray-400 truncate">{team.name_ja}</p>
          )}
          {team.region && (
            <span className="text-xs bg-gray-700 px-2 py-0.5 rounded mt-1 inline-block">
              {team.region}
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}

export default async function TeamsPage() {
  const t = await getTranslations("teams");

  const { data: teams } = await supabase
    .from("teams")
    .select("id, slug, name, name_ja, short_name, region, logo_url, is_active")
    .eq("is_active", true)
    .order("name");

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">{t("title")}</h1>

      {teams && teams.length > 0 ? (
        <RegionFilter
          items={teams}
          getRegion={(t) => t.region}
          renderItems={(filtered) => (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {filtered.map((team) => (
                <TeamCard key={team.id} team={team} />
              ))}
            </div>
          )}
        />
      ) : (
        <div className="bg-gray-900 rounded-xl p-12 text-center text-gray-500">
          <p className="text-lg mb-2">Coming soon...</p>
          <p className="text-sm">データ投入準備中です</p>
        </div>
      )}
    </div>
  );
}
