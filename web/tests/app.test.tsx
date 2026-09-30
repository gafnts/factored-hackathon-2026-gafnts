import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { App, routeOf } from "../src/app";
import { CONSOLES, TEXTS } from "../src/texts";

vi.mock(import("../src/customer"), () => ({
  Customer: () => <p>the customer's chat</p>,
}));

test.each([
  ["/", "home"],
  ["/index.html", "home"],
  ["/chat", "chat"],
  ["/chat/", "chat"],
  ["/agent", "agent"],
  // The AI team's page isn't built (ADR-0007's amendment of 2026-09-30).
  ["/ops", "unknown"],
  ["/agent/cases", "unknown"],
  ["/nope", "unknown"],
])("%s is the %s route", (path, route) => {
  expect(routeOf(path)).toBe(route);
});

test("the root opens the chat, at /chat", async () => {
  window.history.pushState(null, "", "/");
  render(<App path="/" />);

  expect(await screen.findByText("the customer's chat")).toBeInTheDocument();
  expect(window.location.pathname).toBe("/chat");
});

test("/agent says its console comes later, in Spanish, with the notice", () => {
  render(<App path="/agent" />);

  expect(screen.getByRole("heading")).toHaveTextContent(CONSOLES.agent.title);
  expect(screen.getByText(CONSOLES.agent.body)).toBeInTheDocument();
  expect(screen.getByText(TEXTS.es.notice)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: TEXTS.es.toChat })).toHaveAttribute(
    "href",
    "/chat",
  );
});

test.each(["/nope", "/ops"])("%s says the page doesn't exist", (path) => {
  render(<App path={path} />);

  expect(screen.getByRole("link")).toHaveAttribute("href", "/chat");
  expect(screen.getByRole("heading")).toBeInTheDocument();
});
