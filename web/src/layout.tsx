import type { ReactNode } from "react";

import type { Language } from "./contracts/chat";
import { TEXTS } from "./texts";

export function Page({
  language,
  label,
  aside,
  wide = false,
  children,
}: {
  language: Language;
  label?: string;
  aside?: ReactNode;
  // The console lays a queue and a case side by side; the chat reads best narrow.
  wide?: boolean;
  children: ReactNode;
}) {
  const width = wide ? "max-w-6xl" : "max-w-3xl";
  return (
    <div lang={language} className="flex min-h-dvh flex-col">
      <header className="border-b border-rule">
        <div
          className={`mx-auto flex ${width} items-center justify-between gap-4 px-4 py-3`}
        >
          <div>
            <p className="font-medium">LATAM Bank</p>
            {label && <p className="text-sm text-ink-muted">{label}</p>}
          </div>
          {aside}
        </div>
      </header>
      <main className={`mx-auto flex w-full ${width} flex-1 flex-col px-4`}>
        {children}
      </main>
      <footer className="border-t border-rule">
        <p className={`mx-auto ${width} px-4 py-3 text-sm text-ink-muted`}>
          {TEXTS[language].notice}
        </p>
      </footer>
    </div>
  );
}
