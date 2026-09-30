import { lazy, Suspense, useEffect } from "react";

import { browserLanguage } from "./language";
import { Page } from "./layout";
import { NotFound, Placeholder } from "./pages/placeholder";

export type Route = "home" | "chat" | "agent" | "unknown";

// Each route's code is its own chunk, so the console never downloads the chat, nor the chat the console.
const Customer = lazy(() =>
  import("./customer").then((module) => ({ default: module.Customer })),
);

export function routeOf(path: string): Route {
  switch (path.replace(/\/+$/, "")) {
    case "":
    case "/index.html":
      return "home";
    case "/chat":
      return "chat";
    case "/agent":
      return "agent";
    default:
      return "unknown";
  }
}

export function App({ path }: { path: string }) {
  const route = routeOf(path);

  useEffect(() => {
    if (route === "home") window.history.replaceState(null, "", "/chat");
  }, [route]);

  switch (route) {
    case "home":
    case "chat": {
      const language = browserLanguage();
      return (
        <Suspense fallback={<Page language={language}>{null}</Page>}>
          <Customer language={language} />
        </Suspense>
      );
    }
    case "agent":
      return <Placeholder />;
    case "unknown":
      return <NotFound language={browserLanguage()} />;
  }
}
