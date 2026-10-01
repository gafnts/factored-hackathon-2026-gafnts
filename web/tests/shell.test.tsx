import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { RailButton, Shell } from "../src/shell";
import { TEXTS } from "../src/texts";

test("every page says it is a prototype over synthetic data (SEC-02)", () => {
  render(<Shell language="pt">{null}</Shell>);

  expect(screen.getByText(TEXTS.pt.notice)).toBeInTheDocument();
  expect(screen.getByRole("banner")).toHaveTextContent(/^Faro$/);
  expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
});

test("the sign-in's bar carries the bank's name, and no link", () => {
  render(
    <Shell language="es" signIn>
      {null}
    </Shell>,
  );

  expect(screen.getByRole("banner")).toHaveTextContent(/^LATAM Bank$/);
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
  expect(screen.getByText(TEXTS.es.notice)).toBeInTheDocument();
});

test("the console's bar reads the bank's name and the console's, signed in or not, with no link", () => {
  const { rerender } = render(
    <Shell language="es" label="Consola de agentes" signIn>
      {null}
    </Shell>,
  );

  expect(screen.getByRole("banner")).toHaveTextContent(
    /^LATAM BankConsola de agentes$/,
  );
  rerender(
    <Shell language="es" label="Consola de agentes">
      {null}
    </Shell>,
  );
  expect(screen.getByRole("banner")).toHaveTextContent(
    /^LATAM BankConsola de agentes$/,
  );
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
});

test("the wordmark starts a new conversation in place, and waits while a turn runs", () => {
  const onNew = vi.fn();
  const { rerender } = render(
    <Shell language="es" onNew={onNew}>
      {null}
    </Shell>,
  );
  const link = screen.getByRole("link", { name: "Faro" });

  expect(link).toHaveAttribute("href", "/chat");
  expect(link).not.toHaveAttribute("aria-disabled");
  expect(fireEvent.click(link)).toBe(false);
  expect(onNew).toHaveBeenCalledOnce();
  rerender(
    <Shell language="es" onNew={onNew} running>
      {null}
    </Shell>,
  );
  expect(link).toHaveAttribute("aria-disabled", "true");
  expect(fireEvent.click(link)).toBe(false);
  expect(onNew).toHaveBeenCalledOnce();
});

test("the rail opens and closes, and each action is one button by its name", async () => {
  const signOut = vi.fn();
  render(
    <Shell
      language="es"
      note={TEXTS.es.signIn.endsAt("19:05")}
      rail={(expanded) => (
        <RailButton
          icon={null}
          label={TEXTS.es.signIn.signOut}
          expanded={expanded}
          onClick={signOut}
        />
      )}
    >
      {null}
    </Shell>,
  );
  const user = userEvent.setup();
  const rail = TEXTS.es.rail;

  expect(screen.getByRole("navigation", { name: rail.label })).toBeVisible();
  expect(
    screen.getByText(/Su sesión terminará a las 19:05/),
  ).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: rail.open }));
  expect(screen.getByRole("button", { name: rail.close })).toHaveAttribute(
    "aria-expanded",
    "true",
  );
  await user.click(
    screen.getByRole("button", { name: TEXTS.es.signIn.signOut }),
  );
  expect(signOut).toHaveBeenCalledOnce();
});
