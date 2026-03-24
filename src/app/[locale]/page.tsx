import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";

export default function HomePage() {
  const t = useTranslations("home");
  const tc = useTranslations("common");

  return (
    <div>
      {/* ヒーローセクション */}
      <section className="relative overflow-hidden bg-gradient-to-br from-gray-950 via-red-950/20 to-gray-950 py-20 px-4">
        <div className="max-w-5xl mx-auto text-center">
          <h1 className="text-4xl md:text-6xl font-bold mb-4 bg-gradient-to-r from-red-500 to-orange-400 bg-clip-text text-transparent">
            {t("hero")}
          </h1>
          <p className="text-lg md:text-xl text-gray-400 mb-8">
            {t("heroSub")}
          </p>
          <div className="flex gap-4 justify-center flex-wrap">
            <Link
              href="/players"
              className="px-6 py-3 bg-red-600 hover:bg-red-700 rounded-lg font-medium transition-colors"
            >
              {tc("players")}
            </Link>
            <Link
              href="/teams"
              className="px-6 py-3 bg-gray-800 hover:bg-gray-700 rounded-lg font-medium transition-colors"
            >
              {tc("teams")}
            </Link>
            <Link
              href="/tournaments"
              className="px-6 py-3 bg-gray-800 hover:bg-gray-700 rounded-lg font-medium transition-colors"
            >
              {tc("tournaments")}
            </Link>
          </div>
        </div>
      </section>

      {/* 最新の大会結果セクション */}
      <section className="max-w-6xl mx-auto px-4 py-12">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold">{t("latestResults")}</h2>
          <Link
            href="/tournaments"
            className="text-red-400 hover:text-red-300 text-sm"
          >
            {t("viewAll")} →
          </Link>
        </div>
        <div className="bg-gray-900 rounded-xl p-8 text-center text-gray-500">
          Coming soon...
        </div>
      </section>

      {/* 今後の大会セクション */}
      <section className="max-w-6xl mx-auto px-4 py-12">
        <h2 className="text-2xl font-bold mb-6">
          {t("upcomingTournaments")}
        </h2>
        <div className="bg-gray-900 rounded-xl p-8 text-center text-gray-500">
          Coming soon...
        </div>
      </section>
    </div>
  );
}
