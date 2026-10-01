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

export function Reply({ text }: { text: string }) {
  return (
    <div className="reply space-y-3 [&_li]:my-1 [&_ol]:list-decimal [&_ol]:pl-5 [&_ul]:list-disc [&_ul]:pl-5">
      <Markdown
        remarkPlugins={[remarkGfm]}
        allowedElements={ALLOWED}
        unwrapDisallowed
        components={{ a: LinkText }}
      >
        {text}
      </Markdown>
    </div>
  );
}
