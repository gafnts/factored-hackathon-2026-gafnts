import type { Language } from "../contracts/chat";
import { WORDS } from "../contracts/words";
import {
  anyOf,
  capitalized,
  escaped,
  type Found,
  itemTexts,
  LANGUAGES,
  type Node,
  readAll,
  type Tone,
  TONE_CLASS,
  tones,
} from "./lines";

export interface Card {
  name: string;
  status: string;
  tone: Tone;
  expiration: string;
}

const TONES = tones(WORDS.product_status, {
  Active: "good",
  Blocked: "bad",
  Suspended: "bad",
  Closed: "neutral",
});

// A card in a status answer, as the agent's code writes it (formats.card_line), in the reply words. The reply check
// keeps every digit the model writes inside a placeholder, so no line of the model's own can pass for one.
function cardLine(language: Language): RegExp {
  const types = anyOf(WORDS.product_type[language], capitalized);
  const ending = escaped(WORDS.card_ending[language]);
  const statuses = anyOf(WORDS.product_status[language]);
  const label = escaped(WORDS.expiration_label[language]);
  const unrecorded = escaped(WORDS.expiration_unrecorded[language]);
  return new RegExp(
    `^((?:${types}) ${ending} [0-9]{4}): (${statuses}); (${label}): ([0-9]{2}/[0-9]{4}|${unrecorded})$`,
  );
}

const LINES = LANGUAGES.map(cardLine);

function card([, name, status, label, expiration]: Found): Card | null {
  if (!name || !status || !label || !expiration) return null;
  return {
    name,
    status: capitalized(status),
    tone: TONES(status),
    expiration: `${capitalized(label)}: ${expiration}`,
  };
}

// The cards a list states, when every item is a card line of one language; otherwise null, and the list stays one.
export function cardsIn(list: Node | undefined): Card[] | null {
  const texts = itemTexts(list);
  if (!texts) return null;
  for (const line of LINES) {
    const cards = readAll(texts, line, card);
    if (cards) return cards;
  }
  return null;
}

// The confirm control's frame without its glass: a reply sits on the ground (the identity guide's Motifs).
export function Cards({ cards }: { cards: Card[] }) {
  return (
    <ul data-cards className="grid list-none gap-2 pl-0 sm:grid-cols-2">
      {/* Two cards of a type can share the last four digits (POL-15), so the key is the place. */}
      {cards.map((card, index) => (
        <li
          key={index}
          className="my-0 flex flex-col gap-1 border border-white/10 p-4"
        >
          <p className="font-medium text-balance">{card.name}</p>
          <p className={TONE_CLASS[card.tone]}>{card.status}</p>
          <p className="text-sm text-bone-muted">{card.expiration}</p>
        </li>
      ))}
    </ul>
  );
}
