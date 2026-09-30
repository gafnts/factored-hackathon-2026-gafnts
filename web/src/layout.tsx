import type { ReactNode } from "react";

import type { Language } from "./contracts/chat";
import { TEXTS } from "./texts";

export function Page({
  language,
  label,
  aside,
  children,
}: {
  language: Language;
  label?: string;
  aside?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div lang={language} className="flex min-h-dvh flex-col">
      <header className="border-b border-rule">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-4 px-4 py-3">
          <div>
            <p className="font-medium">LATAM Bank</p>
            {label && <p className="text-sm text-ink-muted">{label}</p>}
          </div>
          {aside}
        </div>
      </header>
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4">
        {children}
      </main>
      <footer className="border-t border-rule">
        <p className="mx-auto max-w-3xl px-4 py-3 text-sm text-ink-muted">
          {TEXTS[language].notice}
        </p>
      </footer>
    </div>
  );
}
