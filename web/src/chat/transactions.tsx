import type { Language } from "../contracts/chat";
import { WORDS } from "../contracts/words";
import {
  anyOf,
  capitalized,
  type Found,
  itemTexts,
  LANGUAGES,
  type Node,
  readAll,
  type Tone,
  TONE_CLASS,
  tones,
} from "./lines";

export interface Transaction {
  title: string;
  when: string;
  about: string | null;
  amount: string;
  status: string | null;
  tone: Tone;
}

const MOMENT = "[0-9]{2}/[0-9]{2}/[0-9]{4} [0-9]{2}:[0-9]{2}";
const AMOUNT = "-?[0-9][0-9.,]* [A-Z]{3}";
const SEPARATOR = " · ";
// The words the agent's code writes in place of a merchant's name, which take a capital as a title.
const WORDED = new Set<string>([
  ...Object.values(WORDS.merchant_unrecorded),
  ...LANGUAGES.flatMap((language) =>
    Object.values(WORDS.transaction_type[language]),
  ),
]);
const TONES = tones(WORDS.transaction_status, {
  Approved: "good",
  Declined: "bad",
  Pending: "neutral",
  Reversed: "neutral",
});

// As the agent's code writes them, in the reply words; the reply check keeps every digit the model writes inside a
// placeholder, so no line of the model's own can pass for one. A page's transaction (formats.transaction_line): its
// time and type, the merchant for a purchase, its amount, its status, and a country not the customer's.
function pageLine(language: Language): RegExp {
  const types = anyOf(WORDS.transaction_type[language], capitalized);
  const statuses = anyOf(WORDS.transaction_status[language], capitalized);
  return new RegExp(
    `^(${MOMENT}) · (${types}) · (?:(.+?) · )?(${AMOUNT}) · (${statuses})(?: · (.+))?$`,
  );
}

// A transaction the customer picks from (formats.transaction_name): its time, its merchant for a purchase or its type
// otherwise, and its amount.
const NAME_LINE = new RegExp(`^(${MOMENT}), (.+), (${AMOUNT})$`);

function merchant(name: string): string {
  return WORDED.has(name) ? capitalized(name) : name;
}

function fromPage([
  ,
  moment,
  type,
  name,
  amount,
  status,
  country,
]: Found): Transaction | null {
  if (!moment || !type || !amount || !status) return null;
  const about = [name ? type : null, country].filter((part) => !!part);
  return {
    title: name ? merchant(name) : type,
    when: moment,
    about: about.length > 0 ? about.join(SEPARATOR) : null,
    amount,
    status,
    tone: TONES(status),
  };
}

function fromName([, moment, name, amount]: Found): Transaction | null {
  if (!moment || !name || !amount) return null;
  return {
    title: merchant(name),
    when: moment,
    about: null,
    amount,
    status: null,
    tone: "neutral",
  };
}

type Reader = [RegExp, (found: Found) => Transaction | null];

const READERS: Reader[] = [
  ...LANGUAGES.map((language): Reader => [pageLine(language), fromPage]),
  [NAME_LINE, fromName],
];

// The transactions a list states, when every item is a line of one kind; otherwise null, and the list stays one.
export function transactionsIn(list: Node | undefined): Transaction[] | null {
  const texts = itemTexts(list);
  if (!texts) return null;
  for (const [line, read] of READERS) {
    const transactions = readAll(texts, line, read);
    if (transactions) return transactions;
  }
  return null;
}

// A statement in one frame, as the cards are: a hairline between transactions, the amount and status flush right.
export function Transactions({
  transactions,
}: {
  transactions: Transaction[];
}) {
  return (
    <ul
      data-transactions
      className="list-none divide-y divide-white/10 border border-white/10 pl-0"
    >
      {/* Two transactions can read alike, so the key is the place. */}
      {transactions.map((transaction, index) => (
        <li
          key={index}
          className="my-0 flex items-start justify-between gap-4 px-4 py-3"
        >
          <div className="min-w-0">
            <p className="font-medium">{transaction.title}</p>
            {/* On a phone the type and country take a line of their own, so no separator ends a line. */}
            <p className="text-sm text-bone-muted tabular-nums">
              {transaction.when}
              {transaction.about && (
                <>
                  <span className="max-sm:hidden">{SEPARATOR}</span>
                  <span className="max-sm:block">{transaction.about}</span>
                </>
              )}
            </p>
          </div>
          <div className="shrink-0 text-right">
            <p className="whitespace-nowrap tabular-nums">
              {transaction.amount}
            </p>
            {transaction.status && (
              <p className={`text-sm ${TONE_CLASS[transaction.tone]}`}>
                {transaction.status}
              </p>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
