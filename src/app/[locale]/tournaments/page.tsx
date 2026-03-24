import { supabase } from "@/lib/supabase";
import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";

export async function generateMetadata() {
  const t = await getTranslations("tournaments");
  return { title: t("title") };
}

export default async function TournamentsPage() {
  const t = await getTranslations("tournaments");
  const tr = await getTranslations("regions");

  const { data: tournaments } = await supabase
    .from("tournaments")
    .select("id, slug, name, name_ja, series, event_type, region, start_date, end_date, prize_pool_usd, is_lan, location, status")
    .order("start_date", { ascending: false });

  // ステータスごとに分類
  const ongoing = tournaments?.filter((t) => t.status === "ongoing") || [];
  const upcoming = tournaments?.filter((t) => t.status === "upcoming") || [];
  const completed = tournaments?.filter((t) => t.status === "completed") || [];

  const statusColors: Record<string, string> = {
    ongoing: "bg-green-600",
    upcoming: "bg-blue-600",
    completed: "bg-gray-600",
  };

  function TournamentCard({ tournament }: { tournament: (typeof tournaments extends (infer T)[] | null ? T : never) }) {
    if (!tournament) return null;
    return (
      <Link
        href={`/tournaments/${tournament.slug}`}
        className="bg-gray-900 rounded-xl p-5 hover:bg-gray-800 transition-colors border border-gray-800 hover:border-gray-700 block"
      >
        <div className="flex items-start justify-between gap-2 mb-2">
          <h3 className="font-bold text-white">{tournament.name}</h3>
          <span
            className={`${statusColors[tournament.status]} text-xs px-2 py-0.5 rounded shrink-0`}
          >
            {t(tournament.status as "ongoing" | "upcoming" | "completed")}
          </span>
        </div>
        {tournament.name_ja && (
          <p className="text-sm text-gray-400 mb-2">{tournament.name_ja}</p>
        )}
        <div className="flex flex-wrap gap-3 text-xs text-gray-500">
          {tournament.region && (
            <span>{tr(tournament.region as "APAC_N" | "APAC_S" | "NA" | "EMEA" | "GLOBAL")}</span>
          )}
          {tournament.start_date && (
            <span>
              {tournament.start_date}
              {tournament.end_date ? ` ~ ${tournament.end_date}` : ""}
            </span>
          )}
          {tournament.prize_pool_usd && (
            <span className="text-yellow-500">
              ${tournament.prize_pool_usd.toLocaleString()}
            </span>
          )}
          {tournament.is_lan && (
            <span className="text-orange-400">LAN</span>
          )}
          {tournament.location && <span>{tournament.location}</span>}
        </div>
      </Link>
    );
  }

  const hasData = tournaments && tournaments.length > 0;

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">{t("title")}</h1>

      {hasData ? (
        <div className="space-y-10">
          {/* 開催中 */}
          {ongoing.length > 0 && (
            <section>
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                {t("ongoing")}
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {ongoing.map((tour) => (
                  <TournamentCard key={tour.id} tournament={tour} />
                ))}
              </div>
            </section>
          )}

          {/* 今後 */}
          {upcoming.length > 0 && (
            <section>
              <h2 className="text-xl font-bold mb-4">{t("upcoming")}</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {upcoming.map((tour) => (
                  <TournamentCard key={tour.id} tournament={tour} />
                ))}
              </div>
            </section>
          )}

          {/* 終了 */}
          {completed.length > 0 && (
            <section>
              <h2 className="text-xl font-bold mb-4">{t("completed")}</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {completed.map((tour) => (
                  <TournamentCard key={tour.id} tournament={tour} />
                ))}
              </div>
            </section>
          )}
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
