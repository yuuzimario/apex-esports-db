import { redirect } from "next/navigation";

// ルートにアクセスしたらデフォルトロケール（日本語）にリダイレクト
export default function RootPage() {
  redirect("/ja");
}
