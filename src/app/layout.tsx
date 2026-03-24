import type { ReactNode } from "react";

// ルートレイアウトは[locale]レイアウトに委譲するための最小構成
export default function RootLayout({ children }: { children: ReactNode }) {
  return children;
}
