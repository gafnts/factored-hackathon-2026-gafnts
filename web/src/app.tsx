import { useEffect } from "react";

import { Customer } from "./customer";
import { browserLanguage } from "./language";
import { NotFound, Placeholder } from "./pages/placeholder";

export type Route = "home" | "chat" | "agent" | "ops" | "unknown";

export function routeOf(path: string): Route {
  switch (path.replace(/\/+$/, "")) {
    case "":
    case "/index.html":
      return "home";
    case "/chat":
      return "chat";
    case "/agent":
      return "agent";
    case "/ops":
      return "ops";
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
    case "chat":
      return <Customer language={browserLanguage()} />;
    case "agent":
    case "ops":
      return <Placeholder console={route} />;
    case "unknown":
      return <NotFound language={browserLanguage()} />;
  }
}
