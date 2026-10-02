import type { ReactNode } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

// ADR-0007: no raw HTML, no images, and links as plain text, so an injected reply can't make the browser fetch
// anything. react-markdown shows raw HTML as text unless a plugin parses it.
const ALLOWED = [
  "p",
  "br",
  "strong",
  "em",
  "del",
  "ul",
  "ol",
  "li",
  "code",
  "pre",
  "blockquote",
  "h1",
  "h2",
  "h3",
  "h4",
  "hr",
  "table",
  "thead",
  "tbody",
  "tr",
  "th",
  "td",
  "a",
];

function LinkText({ children }: { children?: ReactNode }) {
  return <span>{children}</span>;
}

// A wide table scrolls on its own, so a phone's page never does.
function ScrollingTable({ children }: { children?: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table>{children}</table>
    </div>
  );
}

export function Reply({ text }: { text: string }) {
  return (
    <div className="reply space-y-3">
      <Markdown
        remarkPlugins={[remarkGfm]}
        allowedElements={ALLOWED}
        unwrapDisallowed
        components={{ a: LinkText, table: ScrollingTable }}
      >
        {text}
      </Markdown>
    </div>
  );
}
