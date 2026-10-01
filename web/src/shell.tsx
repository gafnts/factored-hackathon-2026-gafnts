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

// The customer's pages, in Night: the rail once signed in (a pair of icons in the bar on phones), the bar with LATAM
// Bank's name and Faro's label, and the synthetic-data notice on every page (SEC-02). The rail and the bar are glass
// over the page, which runs on under them; main's padding keeps the content clear of them, by --rail and --bar.
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
  const width = rail
    ? expanded
      ? "sm:[--rail:16rem]"
      : "sm:[--rail:3.5rem]"
    : "";
  return (
    <div
      lang={language}
      data-mode="night"
      className={`relative flex h-dvh flex-col [--bar:3.5rem] [--rail:0px] ${width}`}
    >
      {rail && (
        <nav
          aria-label={texts.rail.label}
          className="fixed top-1 right-2 z-20 flex gap-1 p-1 sm:absolute sm:inset-y-0 sm:left-0 sm:w-(--rail) sm:flex-col sm:border-r sm:border-white/10 sm:glass-thin sm:px-2 sm:py-3"
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
      <header className="absolute top-0 right-0 left-(--rail) z-10 flex h-(--bar) items-center gap-3 border-b border-white/10 glass-thin px-4 pr-28 sm:px-6 sm:pr-6">
        <p className="font-medium">LATAM Bank</p>
        <p className="text-sm text-bone-muted">{texts.assistant}</p>
      </header>
      <main className="flex min-h-0 flex-1 flex-col overflow-y-auto pt-(--bar) pl-(--rail)">
        {children}
      </main>
      <footer className="pt-2 pr-4 pb-3 pl-[calc(var(--rail)+1rem)] text-xs text-bone-muted sm:pr-6 sm:pl-[calc(var(--rail)+1.5rem)]">
        <p>
          <span>{texts.notice}</span>
          {note && <span> {note}</span>}
        </p>
      </footer>
    </div>
  );
}
