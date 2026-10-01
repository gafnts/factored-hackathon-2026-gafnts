import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { RailButton, Shell } from "../src/shell";
import { TEXTS } from "../src/texts";

test("every customer page says it is a prototype over synthetic data, in Night (SEC-02)", () => {
  const { container } = render(<Shell language="pt">{null}</Shell>);

  expect(screen.getByText(TEXTS.pt.notice)).toBeInTheDocument();
  expect(screen.getByText(TEXTS.pt.assistant)).toBeInTheDocument();
  expect(container.firstElementChild).toHaveAttribute("data-mode", "night");
  expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
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
  expect(screen.getByText(/Su sesión termina a las 19:05/)).toBeInTheDocument();
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
