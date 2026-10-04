import type { Language } from "../contracts/chat";
import { WORDS } from "../contracts/words";
import {
  AMOUNT,
  anyOf,
  capitalized,
  escaped,
  type Found,
  itemTexts,
  LANGUAGES,
  type Node,
  readAll,
  TONE_CLASS,
} from "./lines";

export interface Credit {
  card: string;
  // The credit available, or that there is none.
  value: string;
  // How far the balance exceeds the limit, when there is none.
  over: string | null;
}

// A card in an answer about the credit of several, as the agent's code writes it (formats.credit_line), in the reply
// words. The reply check keeps every digit the model writes inside a placeholder, so no line of the model's own can
// pass for one.
function creditLine(language: Language): RegExp {
  const types = anyOf(WORDS.product_type[language], capitalized);
  const ending = escaped(WORDS.card_ending[language]);
  const none = escaped(WORDS.credit_none[language]);
  const over = escaped(WORDS.over_limit_label[language]);
  return new RegExp(
    `^((?:${types}) ${ending} [0-9]{4}): (?:(${AMOUNT})|(${none}); (${over}) (${AMOUNT}))$`,
  );
}

const LINES = LANGUAGES.map(creditLine);

function credit([, card, available, none, label, over]: Found): Credit | null {
  if (!card) return null;
  if (available) return { card, value: available, over: null };
  if (!none || !label || !over) return null;
  return {
    card,
    value: capitalized(none),
    over: `${capitalized(label)} ${over}`,
  };
}

// The credit a list states, when every item is a credit line of one language; otherwise null, and the list stays one.
export function creditsIn(list: Node | undefined): Credit[] | null {
  const texts = itemTexts(list);
  if (!texts) return null;
  for (const line of LINES) {
    const credits = readAll(texts, line, credit);
    if (credits) return credits;
  }
  return null;
}

// Several cards' credit in one frame, as a statement is: the card, and its credit flush right, or none in port's red,
// with the amount over the limit under the card.
export function Credits({ credits }: { credits: Credit[] }) {
  return (
    <ul
      data-credits
      className="list-none divide-y divide-white/10 border border-white/10 pl-0"
    >
      {/* Two cards of a type can share the last four digits (POL-15), so the key is the place. */}
      {credits.map((credit, index) => (
        <li
          key={index}
          className="my-0 flex items-start justify-between gap-4 px-4 py-3"
        >
          <div className="min-w-0">
            <p className="font-medium text-balance">{credit.card}</p>
            {credit.over && (
              <p className="text-sm text-bone-muted tabular-nums">
                {credit.over}
              </p>
            )}
          </div>
          <p
            className={`shrink-0 text-right whitespace-nowrap tabular-nums ${credit.over ? `text-sm ${TONE_CLASS.bad}` : ""}`}
          >
            {credit.value}
          </p>
        </li>
      ))}
    </ul>
  );
}
