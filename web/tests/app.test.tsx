import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { App, routeOf } from "../src/app";
import { CONSOLES, TEXTS } from "../src/texts";

test.each([
  ["/", "home"],
  ["/index.html", "home"],
  ["/chat", "chat"],
  ["/chat/", "chat"],
  ["/agent", "agent"],
  ["/ops", "ops"],
  ["/agent/cases", "unknown"],
  ["/nope", "unknown"],
])("%s is the %s route", (path, route) => {
  expect(routeOf(path)).toBe(route);
});

test("the root opens the chat, at /chat", () => {
  window.history.pushState(null, "", "/");
  render(<App path="/" />);

  expect(screen.getByText(TEXTS.es.assistant)).toBeInTheDocument();
  expect(window.location.pathname).toBe("/chat");
});

test.each(["agent", "ops"] as const)(
  "/%s says its console comes later, in Spanish, with the notice",
  (console) => {
    render(<App path={`/${console}`} />);

    expect(screen.getByRole("heading")).toHaveTextContent(
      CONSOLES[console].title,
    );
    expect(screen.getByText(CONSOLES[console].body)).toBeInTheDocument();
    expect(screen.getByText(TEXTS.es.notice)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: TEXTS.es.toChat })).toHaveAttribute(
      "href",
      "/chat",
    );
  },
);

test("an unknown path says the page doesn't exist", () => {
  render(<App path="/nope" />);

  expect(screen.getByRole("link")).toHaveAttribute("href", "/chat");
  expect(screen.getByRole("heading")).toBeInTheDocument();
});
