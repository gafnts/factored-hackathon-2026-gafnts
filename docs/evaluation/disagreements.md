# Disagreements between the system and the oracle

Where the system and the oracle differ, we record the question here and, once triaged, whether the oracle, the system, or the policy's wording was wrong ([ADR-0005](../adr/0005-offline-scenario-evaluation.md), The oracle). CI's regression gate lets a finding through only while an open entry matches it. Generated from `disagreements.json` by `make disagreements`: edit the entries, not this page. Entries hold rule IDs and enums, never a record's value.

| ID | Status | Verdict | Rules | Situations |
|---|---|---|---|---|
| [D-001](#d-001) | Closed | The policy's wording was unclear | POL-35, POL-36, POL-39 | `block.cancelled` |
| [D-002](#d-002) | Closed | The policy's wording was unclear | POL-37, POL-39 | `charge.blocked`, `charge.blocked.injection` |
| [D-003](#d-003) | Open | To triage | POL-06, POL-51 | `none.third_language` |
| [D-004](#d-004) | Open | To triage | POL-14 | `status.which_card` |
| [D-005](#d-005) | Open | To triage | POL-50 | `block.cancelled`, `block.charge_blocked`, `block.typed_yes`, `charge.block_cancelled`, `credit.available.injection`, `credit.no_limit`, `decline.listed_code`, `decline.no_code`, `decline.several`, `read.recovers`, `status.one_card` |
| [D-006](#d-006) | Open | To triage | POL-35, POL-36 | `block.cancelled` |

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

**Verdict:** To triage.

## D-004

When the agent asks which card a read is about, the system lists each card by type and last four digits, as POL-14 says; the oracle expects the cards with their statuses and expirations, as ADR-0004's format table gives the cards placeholder for an answer. Our lean: the oracle, which should expect POL-14's list in the question.

- `status.which_card`, turn 1: `fact`, expected `{cards}`, observed `missing`

**Verdict:** To triage.

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

**Verdict:** To triage.

## D-006

A terse block request that gives no reason, played live: the system shows the confirm control at once, reading the request itself as reason enough; the oracle expects the reason asked first, since POL-35 says the agent asks for one when the customer hasn't given it. The scripted models never take this path, so it first appeared on the deployed stack, where the request's sibling in Portuguese was asked as expected. Our lean: the oracle, since POL-35's wording is plain and POL-36's control names a reason the customer should have given.

- `block.cancelled` (es), turn 1: `outcome_class`, expected `clarify`, observed `block`
- `block.cancelled` (es), turn 1: `awaiting`, expected `reason`, observed `confirm_control`

**Verdict:** To triage.
