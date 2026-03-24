import { useTranslations } from "next-intl";

export function Footer() {
  const t = useTranslations("common");

  return (
    <footer className="bg-gray-900 border-t border-gray-800 py-8 px-4 mt-12">
      <div className="max-w-6xl mx-auto text-center space-y-2">
        <p className="text-gray-500 text-xs">{t("unofficial")}</p>
        <p className="text-gray-600 text-xs">{t("dataCredit")}</p>
        <p className="text-gray-600 text-xs">
          © {new Date().getFullYear()} APEX Esports DB
        </p>
      </div>
    </footer>
  );
}
