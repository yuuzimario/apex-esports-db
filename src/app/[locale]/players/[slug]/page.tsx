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
  const { data: player } = await supabase
    .from("players")
    .select("ign")
    .eq("slug", slug)
    .single();

  return { title: player?.ign || "Player" };
}

export default async function PlayerDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const t = await getTranslations("players");
  const td = await getTranslations("devices");
  const tr = await getTranslations("regions");

  const { data: player } = await supabase
    .from("players")
    .select("*")
    .eq("slug", slug)
    .single();

  if (!player) notFound();

  // チーム履歴を取得
  const { data: rosters } = await supabase
    .from("team_rosters")
    .select("*, teams(name, slug, short_name, logo_url)")
    .eq("player_id", player.id)
    .order("joined_at", { ascending: false });

  // デバイス情報を取得
  const { data: devices } = await supabase
    .from("devices")
    .select("*")
    .eq("player_id", player.id)
    .order("category");

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* プロフィールヘッダー */}
      <div className="bg-gray-900 rounded-xl p-6 mb-6 border border-gray-800">
        <div className="flex items-center gap-4 mb-4">
          <div className="w-20 h-20 rounded-full bg-gray-700 flex items-center justify-center text-3xl font-bold text-gray-400">
            {player.ign.charAt(0).toUpperCase()}
          </div>
          <div>
            <h1 className="text-3xl font-bold">{player.ign}</h1>
            {player.real_name_ja && (
              <p className="text-gray-400">{player.real_name_ja}</p>
            )}
            {player.real_name && player.real_name !== player.real_name_ja && (
              <p className="text-gray-500 text-sm">{player.real_name}</p>
            )}
          </div>
        </div>

        <div className="flex flex-wrap gap-3 text-sm">
          {player.region && (
            <span className="bg-gray-800 px-3 py-1 rounded">
              {tr(player.region as "APAC_N" | "APAC_S" | "NA" | "EMEA" | "GLOBAL")}
            </span>
          )}
          {player.role && (
            <span className="bg-gray-800 px-3 py-1 rounded">{player.role}</span>
          )}
          {player.nationality && (
            <span className="bg-gray-800 px-3 py-1 rounded">
              {player.nationality}
            </span>
          )}
        </div>

        {/* SNSリンク */}
        <div className="flex gap-4 mt-4 text-sm">
          {player.twitter_url && (
            <a
              href={player.twitter_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-400 hover:text-blue-300"
            >
              X (Twitter)
            </a>
          )}
          {player.twitch_url && (
            <a
              href={player.twitch_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-purple-400 hover:text-purple-300"
            >
              Twitch
            </a>
          )}
          {player.youtube_url && (
            <a
              href={player.youtube_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-red-400 hover:text-red-300"
            >
              YouTube
            </a>
          )}
        </div>

        {/* Bio */}
        {player.bio_ja && (
          <p className="text-gray-400 text-sm mt-4 leading-relaxed">
            {player.bio_ja}
          </p>
        )}
      </div>

      {/* チーム履歴 */}
      <section className="mb-6">
        <h2 className="text-xl font-bold mb-4">{t("teamHistory")}</h2>
        {rosters && rosters.length > 0 ? (
          <div className="space-y-3">
            {rosters.map((roster) => (
              <div
                key={roster.id}
                className="bg-gray-900 rounded-lg p-4 border border-gray-800 flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  {(roster.teams as { logo_url?: string | null })?.logo_url ? (
                    <img
                      src={(roster.teams as { logo_url: string }).logo_url}
                      alt={(roster.teams as { name: string })?.name}
                      className="w-10 h-10 rounded bg-gray-700 object-contain p-0.5 shrink-0"
                    />
                  ) : (
                    <div className="w-10 h-10 bg-gray-700 rounded flex items-center justify-center text-sm font-bold text-gray-400 shrink-0">
                      {(roster.teams as { short_name?: string; name: string })?.short_name ||
                        (roster.teams as { name: string })?.name?.substring(0, 2).toUpperCase()}
                    </div>
                  )}
                  <div>
                    <Link
                      href={`/teams/${(roster.teams as { slug: string })?.slug}`}
                      className="font-medium text-white hover:text-red-400"
                    >
                      {(roster.teams as { name: string })?.name}
                    </Link>
                    {roster.role && (
                      <p className="text-xs text-gray-500">{roster.role}</p>
                    )}
                  </div>
                </div>
                <div className="text-xs text-gray-500 text-right">
                  <p>{roster.joined_at}</p>
                  {roster.left_at && <p>~ {roster.left_at}</p>}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="bg-gray-900 rounded-lg p-6 text-center text-gray-500 text-sm">
            データなし
          </div>
        )}
      </section>

      {/* デバイス */}
      <section>
        <h2 className="text-xl font-bold mb-4">{t("devices")}</h2>
        {devices && devices.length > 0 ? (
          <p className="text-xs text-gray-500 mb-3">{t("deviceDisclaimer")}</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {devices.map((device) => {
              const categoryIcons: Record<string, string> = {
                mouse: "🖱️",
                keyboard: "⌨️",
                headset: "🎧",
                monitor: "🖥️",
                mousepad: "🟫",
                controller: "🎮",
              };
              const icon = categoryIcons[device.category] || "🔧";
              return (
                <div
                  key={device.id}
                  className="bg-gray-900 rounded-lg border border-gray-800 overflow-hidden"
                >
                  <div className="flex items-start gap-3 p-4">
                    <div className="w-12 h-12 rounded-lg bg-gray-800 flex items-center justify-center text-2xl shrink-0">
                      {icon}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs text-gray-500 mb-0.5">
                        {td(device.category as "mouse" | "keyboard" | "headset" | "monitor" | "mousepad" | "controller")}
                      </p>
                      <p className="text-sm font-bold text-white leading-tight">
                        {device.brand}
                      </p>
                      <p className="text-sm text-gray-300 leading-tight">
                        {device.model}
                      </p>
                    </div>
                  </div>
                  {device.amazon_url_ja && (
                    <a
                      href={device.amazon_url_ja}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-center gap-1.5 bg-amber-600 hover:bg-amber-500 text-white text-sm font-medium py-2 px-4 transition-colors"
                    >
                      {td("buyOnAmazon")}
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                    </a>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="bg-gray-900 rounded-lg p-6 text-center text-gray-500 text-sm">
            {t("noDeviceInfo")}
          </div>
        )}
      </section>
    </div>
  );
}
