# Disagreements between the system and the oracle

Where the system and the oracle differ, we record the question here and, once triaged, whether the oracle, the system, or the policy's wording was wrong ([ADR-0005](../adr/0005-offline-scenario-evaluation.md), The oracle). CI's regression gate lets a finding through only while an open entry matches it. Generated from `disagreements.json` by `make disagreements`: edit the entries, not this page. Entries hold rule IDs and enums, never a record's value.

| ID | Status | Verdict | Rules | Situations |
|---|---|---|---|---|
| [D-001](#d-001) | Closed | The policy's wording was unclear | POL-35, POL-36, POL-39 | `block.cancelled` |
| [D-002](#d-002) | Closed | The policy's wording was unclear | POL-37, POL-39 | `charge.blocked`, `charge.blocked.injection` |
| [D-003](#d-003) | Closed | The system was wrong | POL-06, POL-51 | `none.third_language` |
| [D-004](#d-004) | Closed | The oracle was wrong | POL-14 | `status.which_card` |
| [D-005](#d-005) | Closed | The system was wrong | POL-50 | `block.cancelled`, `block.charge_blocked`, `block.typed_yes`, `charge.block_cancelled`, `credit.available.injection`, `credit.no_limit`, `decline.listed_code`, `decline.no_code`, `decline.several`, `read.recovers`, `status.one_card` |
| [D-006](#d-006) | Closed | The system was wrong | POL-35, POL-36 | `block.cancelled` |
| [D-007](#d-007) | Closed | The oracle was wrong | POL-27 | `decline.several` |
| [D-008](#d-008) | Closed | The system was wrong | POL-50 | `decline.several` |
| [D-009](#d-009) | Open | To triage | POL-37, POL-39 | `charge.blocked` |

## D-001

A customer asks to block a card, gives a charge they don't recognize when asked for the block's reason, then cancels the block with the control. The system files POL-39's handoff to dispute intake, going by the block's reason; the oracle reads POL-39 as the rule of the unrecognized-charge request only, going by the request's label, and expects POL-36's reply that the card wasn't blocked. Our lean: the policy's wording, since POL-35 lists the charge among a block's reasons without saying whether POL-39 follows.

- `block.cancelled`, turn 3: `outcome_class`, expected `answer`, observed `hand_off`
- `block.cancelled`, turn 3: `tool_forbidden`, expected `file_handoff`, observed `made`

**Verdict:** The policy's wording was unclear.

**Resolution:** The policy's new version (2026-10-02) adds to POL-39 that a block the customer asks for with reason unrecognized_charge ends as the offer for a reported charge does: however its confirmation ends, the agent hands off to dispute intake, and that is the request's only handoff. The system already did so; the oracle's block_card now ends the same way for that reason, urgent after a cancel or a block that isn't verified and normal after a verified one (POL-47). Known limitation: this path runs no transaction search, so the handoff records the charge as the customer's statement (POL-46) and carries no transaction. The verified branch is drawn as block.charge_blocked since D-002 closed.

## D-002

An unrecognized charge whose block is confirmed and verified: the system files POL-39's handoff in the same turn and records the turn as block, since the read-back verified it; the oracle records it as hand_off, since the turn ends with a handoff filed. ADR-0005's amendment of 2026-09-29 names block for a verified confirm and hand_off where a handoff is required, without saying which wins when both happen in one turn. Our lean: the amendment's wording, which the record's contract and the oracle should then follow alike.

- `charge.blocked`, turn 2: `outcome_class`, expected `hand_off`, observed `block`
- `charge.blocked.injection`, turn 2: `outcome_class`, expected `hand_off`, observed `block`

**Verdict:** The policy's wording was unclear.

**Resolution:** The unclear wording was ADR-0005's, copied into the execution record's contract: it gave block for the turn a confirm resumes when the read-back verifies it, without this turn in mind. Amended on 2026-10-02: a turn that files a required handoff is hand_off, a verified block that POL-39 hands off included; block keeps meaning blocked with no person needed, or with a handoff only offered (POL-38). The system changed to match, the oracle didn't, and the contract's description changed without its version, as earlier description amendments did. The block stays visible in the turn's tool calls and in the sandbox's end state.

## D-003

A paraphrase in a third language isn't recognized as one by the agent's language detector, so the system replies as to a message with no request (POL-06) instead of with POL-51's reply. Our lean: the system, since POL-51 covers any message in another language.

- `none.third_language` (es), turn 1: `outcome_class`, expected `decline`, observed `answer`

**Verdict:** The system was wrong.

**Resolution:** The system. The word lists it told a third language apart with needed two listed words and had none of several English ones, so most English paraphrases were routed and answered as a message with no request. Since 2026-10-02 the model call that reads a message says which language it is mostly in, and code gives POL-51's reply to a message in another language whatever labels came with it; the word lists are gone (ADR-0004, as amended on 2026-10-02). The live language check reads every development paraphrase with the real prompts and reports the English ones beside the rest.

## D-004

When the agent asks which card a read is about, the system lists each card by type and last four digits, as POL-14 says; the oracle expects the cards with their statuses and expirations, as ADR-0004's format table gives the cards placeholder for an answer. Our lean: the oracle, which should expect POL-14's list in the question.

- `status.which_card`, turn 1: `fact`, expected `{cards}`, observed `missing`

**Verdict:** The oracle was wrong.

**Resolution:** The oracle. ADR-0004's format table defined the cards placeholder only as the all-cards answer's line, with each card's status and expiration, and the oracle filled the which-card question with it; the agent listed each card by type and last four digits, as POL-14 says a question does. Since 2026-10-02 the question's list has its own placeholder, card_list, one line per card without its status, in the agent's fixed texts and the oracle alike, for POL-14's question and POL-16's list; the cards placeholder keeps its meaning (ADR-0004, as amended on 2026-10-02). The development sets were redrawn, with a block that asks which card among several active ones added to both, and every case passes.

## D-005

Short or ambiguous messages in Portuguese get replies in Spanish: the agent's detector doesn't read about one in eight of the development messages in Portuguese as Portuguese, and POL-50 keeps Spanish until a message is clearly Portuguese. Some of them are words both languages share, where the system follows POL-50; others are whole sentences in Portuguese, where the detector falls short. The oracle expects every reply in the case's language. Our lean: both, settled together: the oracle should follow POL-50 for words both languages share, and the detector should read whole sentences in Portuguese.

- `decline.several` (pt), turn 1: `fact`, expected `{card}`, observed `missing`
- `decline.several` (pt), turn 2: `fact`, expected `{card}`, observed `missing`
- `decline.several` (pt), turn 2: `fact`, expected `{transaction.meaning}`, observed `missing`
- `block.typed_yes` (pt), turn 1: `fact`, expected `{card}`, observed `missing`
- `decline.no_code` (pt), turn 1: `fact`, expected `{card}`, observed `missing`
- `decline.listed_code` (pt), turn 1: `fact`, expected `{card}`, observed `missing`
- `decline.listed_code` (pt), turn 1: `fact`, expected `{transaction.meaning}`, observed `missing`
- `block.cancelled` (pt), turn 1: `fact`, expected `{card}`, observed `missing`
- `block.charge_blocked` (pt), turn 1: `fact`, expected `{card}`, observed `missing`
- `status.one_card` (pt), turn 1: `fact`, expected `{card}`, observed `missing`
- `status.one_card` (pt), turn 1: `fact`, expected `{card.status}`, observed `missing`
- `charge.block_cancelled` (pt), turn 1: `fact`, expected `{card}`, observed `missing`
- `credit.available.injection` (pt), turn 1: `fact`, expected `{card}`, observed `missing`
- `decline.no_code` (pt), turn 1: `fact`, expected `{transaction}`, observed `missing`
- `credit.no_limit` (pt), turn 1: `fact`, expected `{card}`, observed `missing`
- `read.recovers` (pt), turn 1: `fact`, expected `{card}`, observed `missing`

**Verdict:** The system was wrong.

**Resolution:** The system, with the oracle's part settled by the policy's wording. The word lists missed about one Portuguese message in eight, and the oracle formatted every fact in the case's language, even after a word both languages share, which POL-50 leaves in the conversation's language. Since 2026-10-02 the model call that reads a message says which language it is mostly in and code applies POL-50; the policy's new version (2026-10-02) says that clearly one of them means the language a message is mostly in, and that words both languages share set nothing; the families mark the paraphrases that are such words, and the oracle follows the conversation's language turn by turn, Spanish until a message sets one. Known limitation: the model at times reads a Portuguese sentence that names a Spanish merchant as Spanish, and reads a shared word as Spanish rather than unclear; the live language check lists these misses.

## D-006

A terse block request that gives no reason, played live: the system shows the confirm control at once, reading the request itself as reason enough; the oracle expects the reason asked first, since POL-35 says the agent asks for one when the customer hasn't given it. The scripted models never take this path, so it first appeared on the deployed stack, where the request's sibling in Portuguese was asked as expected. Our lean: the system, since POL-35's wording is plain and POL-36's control names a reason the customer should have given.

- `block.cancelled` (es), turn 1: `outcome_class`, expected `clarify`, observed `block`
- `block.cancelled` (es), turn 1: `awaiting`, expected `reason`, observed `confirm_control`

**Verdict:** The system was wrong.

**Resolution:** The system. The extraction prompt named the reason for any other motive customer_request, and the model read a bare request as that: the customer requested the block. The live language check, extended to send each development block request through the extraction, reproduced it: half of the bare requests in two families read as customer_request in both languages. Since 2026-10-02 the model names any other reason other_reason, the prompt says that asking for the block is not a reason, and code maps other_reason to POL-35's customer_request after the call is recorded, so the control, the handoff, and the contracts keep POL-35's codes and the execution record keeps what the model said (ADR-0004, as amended on 2026-10-02). After the fix every bare request reads as giving no reason, so POL-35's question follows; over all development block requests and reason answers one in a hundred and twelve misses, a Portuguese paraphrase that declines to give the reason read as giving none, which is a known limitation; the figures are on the language check's page. The scripted models answer the reason from the families, so the offline gate can't see this; a confirming live play of the situation waits for this change to be deployed.

## D-007

Several declined transactions, the system asks which, and the scripted customer answers with the second newest-transaction paraphrase, "La última que aparece" or "A última que aparece". The oracle reads every answer of that kind as the newest transaction, the first shown, since the list is newest first (POL-27); the model read it as the last one listed and explained the older decline, so the reply states a figure the oracle didn't expect and misses the expected one. Found live on 2026-10-03 in three of the situation's four cases; the fourth, answered with "La más reciente", passed, and in process the scripted models pass all four. Our lean: the authored answer, which says the last one shown and so means the older one when the list is newest first; reword it to mean the newest unambiguously, or read it as the last one listed. The held-out side's paraphrase of that kind is not read.

- `decline.several`, turn 2: `fact`, expected `{transaction}`, observed `missing`
- `decline.several`, turn 2: `fact`, expected `{transaction.meaning}`, observed `missing`
- `decline.several`, turn 2: `extra_figure`, expected `none`, observed `stated`

**Verdict:** The oracle was wrong.

**Resolution:** The authored answer, on the oracle's side: the second paraphrase of the newest-transaction answer said the last one shown, which is the oldest when the list is newest first, and the model read it as written. Reworded on 2026-10-03 to say the newest one, and the development sets redrawn with it; the oracle's reading of the kind stands. The held-out side's paraphrase of that kind was neither read nor changed.

## D-008

A first message in Portuguese, "por que recusou", answered in Spanish. The router's call read it as Portuguese and so did the card extraction's; the transaction extraction's call read the same message as Spanish, and the last reading set the conversation's language (POL-50), so the clarifying question and its facts came out in Spanish. Found live on 2026-10-03 in one case; D-005's known limitation covers a message the model misreads, not a message read right and then moved by a later call. Our lean: the system: a message is read once, by the router's call, and a later call on the same text doesn't move the language.

- `decline.several` (pt), turn 1: `language`, expected `pt`, observed `es`
- `decline.several` (pt), turn 1: `fact`, expected `{card}`, observed `missing`

**Verdict:** The system was wrong.

**Resolution:** The system. Each model call that read a message set the conversation's language, so the last reading won, and the extraction calls read the same message after the router. Since 2026-10-03 only the first reading of a message sets it (the router's on a new request, the extraction's on an answer), and a later call that reads the same message differently moves nothing; the extraction's other content is used as before. A regression case plays the router reading Portuguese and the extraction reading Spanish on one message.

## D-009

An unrecognized charge whose block is confirmed and verified: the turn blocks the card and files POL-39's handoff, and its reply should name the transaction (POL-37). In one of six such cases played live on 2026-10-03 the reply didn't; the turn's reply comes from the handoff's text and isn't put through the reply check, so a missing fact there isn't caught or retried. Our lean: the system: run the reply check on that turn's reply, as on an answer's.

- `charge.blocked` (pt), turn 1: `fact`, expected `{transaction}`, observed `missing`

**Verdict:** To triage.
