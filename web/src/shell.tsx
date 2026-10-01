import { type ReactNode, useState } from "react";

import type { Language } from "./contracts/chat";
import { PanelLeft } from "./icons";
import { TEXTS } from "./texts";

// One button per action, whatever the width: a label beside the icon in the open rail, a label for screen readers
// otherwise, so a test or a reader finds each action once.
export function RailButton({
  icon,
  label,
  expanded,
  disabled = false,
  className = "",
  onClick,
}: {
  icon: ReactNode;
  label: string;
  expanded: boolean;
  disabled?: boolean;
  className?: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`flex h-10 items-center gap-3 rounded-full px-2.5 text-bone-muted transition-colors hover:bg-white/5 hover:text-bone disabled:opacity-40 disabled:hover:bg-transparent ${className}`}
    >
      {icon}
      <span
        className={expanded ? "sr-only sm:not-sr-only sm:truncate" : "sr-only"}
      >
        {label}
      </span>
    </button>
  );
}

// The customer's pages, in Night: the rail once signed in (a pill of icons on phones), LATAM Bank's name and Faro's
// label, and the synthetic-data notice on every page (SEC-02).
export function Shell({
  language,
  note,
  rail,
  children,
}: {
  language: Language;
  note?: string;
  rail?: (expanded: boolean) => ReactNode;
  children: ReactNode;
}) {
  const texts = TEXTS[language];
  const [expanded, setExpanded] = useState(false);
  return (
    <div
      lang={language}
      data-mode="night"
      className="flex h-dvh flex-col sm:flex-row"
    >
      {rail && (
        <nav
          aria-label={texts.rail.label}
          className={`fixed top-2 right-2 z-20 flex gap-1 rounded-full border border-white/10 glass p-1 sm:static sm:h-full sm:shrink-0 sm:flex-col sm:rounded-none sm:border-y-0 sm:border-l-0 sm:px-2 sm:py-3 ${expanded ? "sm:w-64" : "sm:w-14"}`}
        >
          <button
            type="button"
            aria-expanded={expanded}
            aria-label={expanded ? texts.rail.close : texts.rail.open}
            onClick={() => {
              setExpanded(!expanded);
            }}
            className="hidden h-10 w-10 items-center justify-center rounded-full text-bone-muted hover:bg-white/5 hover:text-bone sm:flex"
          >
            <PanelLeft />
          </button>
          {rail(expanded)}
        </nav>
      )}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-baseline gap-x-3 px-4 py-4 pr-28 sm:px-6 sm:pr-6">
          <p className="font-medium">LATAM Bank</p>
          <p className="text-sm text-bone-muted">{texts.assistant}</p>
        </header>
        <main className="flex min-h-0 flex-1 flex-col overflow-y-auto">
          {children}
        </main>
        <footer className="px-4 pt-2 pb-3 text-xs text-bone-muted sm:px-6">
          <p>
            <span>{texts.notice}</span>
            {note && <span> {note}</span>}
          </p>
        </footer>
      </div>
    </div>
  );
}
