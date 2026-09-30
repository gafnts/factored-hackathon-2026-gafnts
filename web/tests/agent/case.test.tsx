import { render, screen, within } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { CaseView } from "../../src/agent/case";
import { AGENT } from "../../src/agent/texts";
import type { CaseDetail } from "../../src/contracts/console";
import { example } from "../contract";

const [verified, flagged] = example<CaseDetail>("case_detail", "console") as [
  CaseDetail,
  CaseDetail,
];
const SCRIPT = '<script>alert("x")</script>';
const IMAGE = '<img src="x" onerror="alert(1)">';

function shown(detail: CaseDetail) {
  return render(<CaseView detail={detail} onClose={vi.fn()} />);
}

// A case whose every free-text field, and a merchant's name, holds markup (ADR-0007, Rendering what others wrote).
function injected(): CaseDetail {
  const detail = structuredClone(verified);
  const payload = detail.case.payload;
  payload.request.summary = `Resumen ${SCRIPT}`;
  payload.customer_statements = [`Dice ${IMAGE}`];
  payload.unresolved_questions = [`Pregunta ${SCRIPT}`];
  for (const fact of payload.verified_facts) {
    if (fact.field === "merchant_name") fact.value = `Comercio ${IMAGE}`;
  }
  const [search] = detail.calls;
  const row = search?.rows?.[0];
  if (row) row.merchant_name = `Comercio ${IMAGE}`;
  return detail;
}

test("every string a case holds is shown as text, never as markup", () => {
  const { container } = shown(injected());

  expect(container.querySelector("script, img")).toBeNull();
  expect(screen.getByText(`Resumen ${SCRIPT}`)).toBeInTheDocument();
  expect(screen.getByText(`Dice ${IMAGE}`)).toBeInTheDocument();
  expect(screen.getByText(`Pregunta ${SCRIPT}`)).toBeInTheDocument();
  expect(screen.getAllByText(`Comercio ${IMAGE}`)).toHaveLength(2);
});

test("each verified fact is shown next to the tool call that read it", () => {
  shown(verified);

  const facts = screen.getByRole("region", { name: AGENT.case.facts });
  const merchant = within(facts)
    .getByText(AGENT.field("merchant_name"))
    .closest("div") as HTMLElement;
  expect(within(merchant).getByText("Comercio Ejemplo")).toBeInTheDocument();
  expect(within(merchant).getByText("find_transactions")).toBeInTheDocument();
  expect(merchant).toHaveTextContent(AGENT.case.attempt(2));
  const fraud = within(facts)
    .getByText(AGENT.field("is_fraud"))
    .closest("div") as HTMLElement;
  expect(within(fraud).getByText("No")).toBeInTheDocument();
  expect(within(fraud).getByText("file_handoff")).toBeInTheDocument();
});

test("the verified block is among the actions, with the card it blocked", () => {
  shown(verified);

  const actions = screen.getByRole("region", { name: AGENT.case.actions });
  expect(
    within(actions).getByText(AGENT.outcomes.verified),
  ).toBeInTheDocument();
  expect(actions).toHaveTextContent("••4821");
  expect(within(actions).getByText("block_card")).toBeInTheDocument();
});

test("the header gives the queue, the priority, the reason, and both clocks", () => {
  shown(verified);

  expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent(
    "7K2M-9QXA",
  );
  expect(screen.getByText(AGENT.priorities.normal)).toBeInTheDocument();
  expect(screen.getByText(AGENT.queues.dispute_intake)).toBeInTheDocument();
  expect(
    screen.getAllByText(AGENT.reason("unrecognized_charge")).length,
  ).toBeGreaterThan(0);
  expect(screen.getByText(AGENT.statuses.filed)).toBeInTheDocument();
  expect(
    screen.getByText(AGENT.case.answerIn(AGENT.languages.pt)),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/Fecha del banco: 17 de junio de 2026/),
  ).toBeInTheDocument();
  expect(screen.getByText("POL-39")).toBeInTheDocument();
});

test("the evidence shows each call's recorded rows, not the conversation", () => {
  shown(verified);

  const evidence = screen.getByRole("region", { name: AGENT.case.evidence });
  expect(within(evidence).getByText("gw-3e4f5a6b7c8d")).toBeInTheDocument();
  expect(within(evidence).getByText(AGENT.via.direct)).toBeInTheDocument();
  expect(within(evidence).getByText("block_outcome")).toBeInTheDocument();
});

test("a flagged case says so, naming each part and rule without a value", () => {
  shown(flagged);

  const alert = screen.getByRole("alert");
  expect(alert).toHaveTextContent(AGENT.case.flagged);
  expect(alert).toHaveTextContent(
    `${AGENT.path("/customer_statements/0")}: ${AGENT.rule("not")}`,
  );
});

test("a call the record doesn't hold yet says so", () => {
  shown(flagged);

  const evidence = screen.getByRole("region", { name: AGENT.case.evidence });
  expect(
    within(evidence).getByText(AGENT.case.notRecorded),
  ).toBeInTheDocument();
  expect(within(evidence).getByText("file_handoff")).toBeInTheDocument();
});

test.each([
  ["/verified_facts/3", "Hecho verificado n.º 4"],
  ["/evidence/0", "Evidencia n.º 1"],
  ["/priority", "Prioridad"],
  ["/something/else", "/something/else"],
])("the path %s reads as %s", (path, read) => {
  expect(AGENT.path(path)).toBe(read);
});

test("a rule the console doesn't name is still shown, as the rule", () => {
  expect(AGENT.rule("unrecorded")).toBe(
    "no consta en el registro de ejecución",
  );
  expect(AGENT.rule("uniqueItems")).toContain("uniqueItems");
});
