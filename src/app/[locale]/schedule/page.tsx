import { supabase } from "@/lib/supabase";
import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";

export async function generateMetadata() {
  const t = await getTranslations("schedule");
  return { title: t("title") };
}

export default async function SchedulePage() {
  const t = await getTranslations("schedule");
  const tt = await getTranslations("tournaments");
  const tr = await getTranslations("regions");

  const { data: tournaments } = await supabase
    .from("tournaments")
    .select("id, slug, name, series, event_type, region, start_date, end_date, prize_pool_usd, is_lan, location, status")
    .in("status", ["upcoming", "ongoing"])
    .neq("series", "DEPRECATED")
    .order("start_date", { ascending: true });

  const eventTypeLabels: Record<string, string> = {
    championship: "Championship",
    playoffs: "Playoffs",
    pro_league: "Pro League",
    challenger_circuit: "Challenger Circuit",
    open_qualifier: "Open Qualifier",
    community: "Community",
  };

  // 日付でグループ化
  const grouped = new Map<string, typeof tournaments>();
  for (const tour of tournaments || []) {
    const month = tour.start_date?.slice(0, 7) || "TBD";
    if (!grouped.has(month)) grouped.set(month, []);
    grouped.get(month)!.push(tour);
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-2">{t("title")}</h1>
      <p className="text-gray-400 text-sm mb-8">
        ALGS Year 6 — {tournaments?.length || 0} events
      </p>

      {tournaments && tournaments.length > 0 ? (
        <div className="space-y-8">
          {[...grouped.entries()].map(([month, tours]) => (
            <section key={month}>
              <h2 className="text-lg font-bold text-gray-300 mb-3 border-b border-gray-800 pb-2">
                {month}
              </h2>
              <div className="space-y-2">
                {tours!.map((tour) => (
                  <Link
                    key={tour.id}
                    href={`/tournaments/${tour.slug}`}
                    className="flex items-center gap-4 bg-gray-900 rounded-lg px-4 py-3 hover:bg-gray-800 transition-colors border border-gray-800 hover:border-gray-700"
                  >
                    {/* ステータスドット */}
                    <div className="shrink-0">
                      {tour.status === "ongoing" ? (
                        <span className="w-2.5 h-2.5 bg-green-500 rounded-full animate-pulse inline-block" />
                      ) : (
                        <span className="w-2.5 h-2.5 bg-blue-500 rounded-full inline-block" />
                      )}
                    </div>

                    {/* 日付 */}
                    <div className="shrink-0 w-20 text-center">
                      <div className="text-white font-bold text-sm">
                        {tour.start_date?.slice(5) || "TBD"}
                      </div>
                      <div className="text-[10px] text-gray-500">
                        {tour.status === "ongoing" ? tt("ongoing") : tt("upcoming")}
                      </div>
                    </div>

                    {/* 大会情報 */}
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium text-white text-sm truncate">
                        {tour.name}
                      </h3>
                      <div className="flex flex-wrap gap-x-3 text-xs text-gray-400 mt-0.5">
                        <span>{eventTypeLabels[tour.event_type] || tour.event_type}</span>
                        {tour.region && tour.region !== "GLOBAL" && (
                          <span>{tr(tour.region as "APAC_N" | "APAC_S" | "NA" | "EMEA" | "GLOBAL")}</span>
                        )}
                        {tour.is_lan && <span className="text-orange-400">LAN</span>}
                      </div>
                    </div>

                    {/* 賞金 */}
                    {tour.prize_pool_usd && (
                      <div className="text-xs text-yellow-500 font-medium shrink-0">
                        ${tour.prize_pool_usd.toLocaleString()}
                      </div>
                    )}
                  </Link>
                ))}
              </div>
            </section>
          ))}
        </div>
      ) : (
        <div className="bg-gray-900 rounded-xl p-12 text-center text-gray-400">
          <p>{t("noUpcoming")}</p>
        </div>
      )}
    </div>
  );
}
