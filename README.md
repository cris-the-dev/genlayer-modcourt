# ModCourt — moderation appeals judged against the written policy

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Every community has rules and moderators, and every banned user says the
moderator was wrong. Appeals usually go to the same team that made the call.
**ModCourt** sends them somewhere else: the community writes its policy on
chain, moderators record each action against a rule, and an appeal is judged
by GenLayer validators on one narrow question: does the post violate the rule
the moderator cited? The community also puts money behind its moderation:
every action reserves a reward that the member receives if it is overturned.

```
owner     ── create_community(name, rules, appeal_bond, reward) + pool ─▶ ModCourt
member    ── personal_sign(commitment to sha256(post))  in their wallet, off chain
moderator ── act(community, member, sha256, member's signature, rule, action)   reserves one reward
member    ── appeal(case) + exact bond, within 7 days            registers only: no LLM, no web
member    ── decide(case, url, statement), within 3 days of the appeal; retry on failure
             validators fetch url, check sha256, and rule on the cited rule only
             not violated ─▶ OVERTURNED: bond + reward to the member
             violated     ─▶ UPHELD: bond to the community's bond fund
anyone    ── expire_unresolved(case) after the 3 days ─▶ UNRESOLVED: bond refunded, action stands
anyone    ── release(case) after 7 days without an appeal ─▶ FINAL, reservation freed
```

## Live deployment

App: https://modcourt.cristhedev.com (communities, policy, moderator stats, cases and every role's actions; source in [`app/`](app/))  
Testnet Bradbury Phase 2 (chainId 4221, GenVM v0.3): [`0x7fB191BDCeF0C9E38A71AF62bF3bF6E2169a1DFE`](https://explorer-bradbury.genlayer.com/address/0x7fB191BDCeF0C9E38A71AF62bF3bF6E2169a1DFE)

## Bradbury evidence

Run by [`tests/integration/bradbury.mjs`](tests/integration/bradbury.mjs) on Bradbury Phase 2 (all checks passed). Contract `0x7fB191BDCeF0C9E38A71AF62bF3bF6E2169a1DFE` (deploy [`0xd9533d6e…`](https://explorer-bradbury.genlayer.com/tx/0xd9533d6e3e9d3dca78a466aa830eda73fa5008e86e525e7b3f55052852ddc55f)), code `build/mod_court.py` (sha256 `00ee340f…`). Owner (also moderator) and member are separate accounts. Every transaction carries a fee deposit; paying calls also allocate their payout's gas. Neither post nor statement appears in any view afterwards; the explanations below are the leader's, as returned in `explanation_unverified`:

- case 0: "The content is a direct technical question about performance on the GenLayer network, which is on-topic."
- case 1: "The content is a clear and unsolicited advertisement for a commercial service."

| Step | Transaction | Outcome |
|---|---|---|
| create community: 3 rules capped ban / remove / remove, bond 0.0005, reward 0.001, pool 0.002 GEN | [`0xddf76324…`](https://explorer-bradbury.genlayer.com/tx/0xddf76324d0adb34c25ad63cd9c499ec14c78a6b11863b3eaab121f6bfddab2c7) | ok |
| act with the member's signature for a *different* post | [`0xf3094913…`](https://explorer-bradbury.genlayer.com/tx/0xf3094913e6eadf967d5ded1e41b359309ea9922258a33f96d84d6cdd2c67df8f) | rejected: signature does not match the hash |
| act `ban` under rule 2 (max remove) | [`0xb24bce1a…`](https://explorer-bradbury.genlayer.com/tx/0xb24bce1a1823d969854977859d419869f378345aedcef38598a228c59235e22a) | rejected: disproportionate |
| remove an on-topic question (rule 3), member-signed hash | [`0xebc03228…`](https://explorer-bradbury.genlayer.com/tx/0xebc03228b181c01de7d1538c7a4fb9d65720f8fd9d87fcf686d069ad604e34ce) | case 0, reward reserved |
| remove a spam post (rule 2), member-signed hash | [`0x1155c4e3…`](https://explorer-bradbury.genlayer.com/tx/0x1155c4e371f95a82ce8b58be07935cc08d0338fb8887feb8d6cd0724d8f75c9a) | case 1, reward reserved |
| a third action | [`0xe8d6a932…`](https://explorer-bradbury.genlayer.com/tx/0xe8d6a932c48dc5792d6f39aa22f880310160fbe1ead768c11e8806b10cfca0e7) | rejected: the pool is fully reserved |
| member appeals case 0 (bond only, no AI) | [`0x5abde8ae…`](https://explorer-bradbury.genlayer.com/tx/0x5abde8aea571b21b5745445e17dbb9795056a2592b956495ae89da6fd4dbcd03) | APPEALED, `resolve_by` = appeal + 3 days |
| ruling from `evidence/missing.txt` (404) | [`0x8ed817cb…`](https://explorer-bradbury.genlayer.com/tx/0x8ed817cbaa3839899d75a8f0ffe89b7d396b24076ebec1caf6fed3378587e49e) | rejected: original unavailable; case still APPEALED |
| ruling from `evidence/spam.txt` (another post) | [`0x9aabb65a…`](https://explorer-bradbury.genlayer.com/tx/0x9aabb65aabdfe555e0ecc1a786e666ed1dd891b81765f769fb151e7eaf35bfec) | rejected: hash mismatch; case still APPEALED |
| ruling from `evidence/fine.txt` (retry) | [`0xc1840d45…`](https://explorer-bradbury.genlayer.com/tx/0xc1840d457eab741bdd5e24e8526c688196f84d42c4e2407400d49324dc79cbe3) | **OVERTURNED** (`cited_rule_violated: false`): bond + reward = payout 0 |
| member appeals case 1 | [`0xf1da26c4…`](https://explorer-bradbury.genlayer.com/tx/0xf1da26c4e4082c8a1474bc0dee0ca5460383473be932ace44f7efdc515428fea) | APPEALED |
| ruling from `evidence/spam.txt` | [`0x643cba33…`](https://explorer-bradbury.genlayer.com/tx/0x643cba33186577a77b5b03ba7e2e3e809341cc4182dc35b406756e55dcb772ec) | **UPHELD**: bond goes to the bond fund |
| owner withdraws all it may (0.001; reserved 0, bond fund 0.0005 not withdrawable) | [`0x45976d58…`](https://explorer-bradbury.genlayer.com/tx/0x45976d58d94e1a8644066b5a3719af0789087f31626766076709ac48e2ab48dc) | payout 1 |

Moderator stats afterwards: 2 actions, 2 appeals, 1 overturned. Both payouts were settled from their own transfer once the paying transaction finalized (`settle_payout` checks the paying tx, its finalization and the executed message):

| Payout | Kind | Amount | Paid by | Finalized by | `settle_payout` | Result |
|---|---|---|---|---|---|---|
| 0 | overturn → member | 0.0015 GEN | [`0xc1840d45…`](https://explorer-bradbury.genlayer.com/tx/0xc1840d457eab741bdd5e24e8526c688196f84d42c4e2407400d49324dc79cbe3) | [`0x46ff360a…`](https://explorer-bradbury.genlayer.com/tx/0x46ff360a0c76e8cee630ffc2a511f95a6350c7212697a973975435f1b946d78f) | [`0x1508e17b…`](https://explorer-bradbury.genlayer.com/tx/0x1508e17bb64f7fae296621f53f45d9a29e557a271e9cd23d8cf749d663592302) | DELIVERED |
| 1 | withdraw → owner | 0.001 GEN | [`0x45976d58…`](https://explorer-bradbury.genlayer.com/tx/0x45976d58d94e1a8644066b5a3719af0789087f31626766076709ac48e2ab48dc) | [`0xec24b9db…`](https://explorer-bradbury.genlayer.com/tx/0xec24b9db51159794013dbaf7038d30e7720b2f01e132a7443b06eeacc614b840) | [`0x602b963b…`](https://explorer-bradbury.genlayer.com/tx/0x602b963b45bf9090acbe7194de54d1a5a479ca524358371b2493b68a97236d45) | DELIVERED |

Settling the same payout again is rejected ([`0x309e379b…`](https://explorer-bradbury.genlayer.com/tx/0x309e379b80bce70bba10ee7de69147ba0f174ab38a97b103b3e382eb6912f667), [`0x5ba25400…`](https://explorer-bradbury.genlayer.com/tx/0x5ba2540094b5b0d18371cb830105999b58709048184370cdb030ec9515ec64ec)). Afterwards `get_accounting` reports `unaccounted: 0`. The resolution deadline (3 days) and `expire_unresolved` are covered in Direct Mode only.

## Appeals: registration first, ruling second

An appeal used to be one transaction that also fetched, prompted and paid; if
validators disagreed or the LLM failed, the member's appeal was simply lost
when the window closed. Now:

- `appeal(case)` only takes the exact bond and marks the case `APPEALED`. It
  touches no network and no LLM, so a timely appeal is never lost. An appealed
  case can no longer be `release`d as final.
- `decide(case, url, statement)` asks for the ruling. A fetch error, a hash
  mismatch, malformed LLM output or validator disagreement reverts it and
  changes nothing: the case stays `APPEALED` and the member retries — with
  the same URL, a fixed one, or after the host is back — until the deadline.
- The deadline is 3 days after the appeal. After it, `expire_unresolved(case)`
  (anyone) refunds the bond and the case becomes `UNRESOLVED`: the action
  stands, unreviewed, and the reserved reward is freed. `decide` and
  `expire_unresolved` meet exactly at the deadline (`≤` vs `>`), so they can
  never both succeed; Direct Mode tests the boundary second.

## Provenance of the content

A moderator could otherwise record any hash against any member. Now the
member's wallet signs the post: an EIP-191 `personal_sign` of

```
ModCourt content commitment
contract: <this contract, lowercase>
community: <id>
sha256: <hex sha256 of the post's UTF-8 bytes>
```

(`get_commitment(community, sha256)` returns the exact text; the app's "Sign a
post" panel does it). `act` recovers the signer in the contract (pure-Python
secp256k1, ~30 ms) and requires it to be the member the action targets. A
fabricated hash, a signature for another post, another community or another
deployment, or anyone else's signature is rejected. At ruling time validators
fetch the member's URL and require the body's sha256 to equal the signed hash;
an unavailable original fails the ruling (retryable) rather than being judged
blind, and a different post at the URL fails it with `[EXPECTED]`.

## Privacy

Neither the post nor the statement is stored in contract state or returned by
any view: a case holds only the hash and the signature. The post is fetched
from the member's URL during the ruling, so the member can take the page down
afterwards. **The statement is still transaction calldata — public and
permanent.** The app makes the member acknowledge that before sending.

## The judging standard

Validators are asked one question: *does the content violate rule N, the rule
the moderator cited, read as a reasonable moderator would?* They must agree
on the boolean.

- Only the cited rule counts. A post that breaks a different rule but not the
  cited one is overturned: the moderator must cite the right rule (an insult
  removed as "spam" is overturned; this is tested).
- Proportionality is not left to the LLM. Each rule carries the strongest
  action it allows (`hide < remove < mute < ban`), enforced by `act`: "ban" under
  a rule capped at "remove" is rejected before it exists.
- The explanation is the leader's own sentence and is not part of consensus.
  It is stored and shown as `explanation_unverified`; `cited_rule_violated`
  is what consensus decided. The reason must not quote the post or statement.
- Policy, post and statement are fenced between `<<<` and `>>>` with markers
  inside neutralised; the statement can give context but not change the post.
- Errors: validators agree on a leader's fetch error only if they hit the same
  `[EXPECTED]`/`[EXTERNAL]` error themselves; never on an `[LLM_ERROR]`.

## Where the money goes

- **Each action reserves one reward.** `act` reverts unless pool + bond fund −
  reserved covers one more reward.
- **Overturned:** the member gets bond + reward. The reward comes from the
  bond fund first, then the pool.
- **Upheld:** the bond goes to the community's **bond fund**, which only pays
  later overturn rewards. The owner can never withdraw it.
- **Owner withdrawals** are limited to `withdrawable = min(pool, pool + bond
  fund − reserved)`: never money reserved for open cases, never bonds.
- **Unresolved:** the bond goes back to the member.
- **Abusive moderators:** a moderator with at least 3 overturned actions,
  more than half of their appealed ones, is suspended from `act`; the owner
  cannot lift it (the stats are append-only). Stats are public per moderator.

## Payments and settlement

Every transfer is a recorded payout (with its sender and creation time). A
payout is judged by its own transfer, never by the contract balance:
`settle_payout(payout_id, tx_hash, finalize_tx)` has validators read the paying
transaction (it must be this contract's `decide`, `expire_unresolved`,
`withdraw_pool` or `recover` call for that payout, sent by the recorded sender
at the recorded time, and finalized with a successful result) and the
consensus transaction that finalized it, and check that the transfer to the
payee was executed. Delivered payouts are marked `DELIVERED`; a failed one is
`FAILED` and its amount becomes recoverable by the payee (by the sender, for a
failed `recover`), who sends it anywhere with `recover`. One paying transaction
settles at most one payout, and a sender can create one payout per second.
`get_payouts(start, limit, only_unsettled)` pages through payouts (bounded
scan per call, continue from `next`), so old unsettled payouts are always
found. `get_accounting` (balance vs. `expected_balance`) is informational only.

## The app

https://modcourt.cristhedev.com ([`app/`](app/)) reads the **finalized** state
(`latest-final`) and treats a write as done only when it is `FINALIZED` with
execution result `FINISHED_WITH_RETURN` **and** reading the contract back shows
the change (e.g. the case is `APPEALED`, the pool moved by exactly the amount).
`ACCEPTED` is shown as "waiting for finality", `UNDETERMINED`/timeouts as
"nothing changed, retry", a finalized error as "rejected". GEN amounts are
parsed and formatted with BigInt only (`toWei` rejects more than 18 decimals),
and reads keep integers above 2^53 exact. Cases and unsettled payouts are
paginated ("Older cases", "More transfers"). "Settle" finds the paying
transaction (remembered by the browser that sent it, or pasted) and looks up
its finalizing transaction from the `TransactionFinalized` log itself.
`node app/check-actions.mjs app/index.html` (CI) asserts the controls per role
and case state and exact money formatting.

## API

| Method | Who | Notes |
|---|---|---|
| `create_community(name, rules_json, appeal_bond, reward)` payable | owner | pool = `msg.value`; rules: strings or `{"text", "max_action"}`, 1–20 |
| `fund(id)` payable / `set_moderator(id, who, enabled)` / `withdraw_pool(id, amount)` | anyone / owner / owner | withdraw ≤ `withdrawable` |
| `act(id, target, content_sha256, signature, rule, action)` | moderator | member-signed hash; action within the rule's cap; not suspended |
| `appeal(case_id)` payable | affected member | exactly the bond, within 7 days; returns the resolution deadline |
| `decide(case_id, content_url, statement)` | affected member | until 3 days after the appeal; retryable |
| `expire_unresolved(case_id)` / `release(case_id)` | anyone | bond refund after the deadline / final after 7 days unappealed |
| `settle_payout(payout_id, tx_hash, finalize_tx)` / `recover(to)` | anyone / payee | |
| `get_community`, `get_community_count`, `get_commitment`, `get_cases(id, offset, limit)`, `get_case`, `is_moderator`, `get_moderator_stats`, `get_payout`, `get_payouts(start, limit, only_unsettled)`, `get_accounting`, `get_recoverable` | view | |

## Run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
genvm-lint check contracts/mod_court.py
pytest tests/direct -v                         # 66 tests
# end-to-end on Bradbury Phase 2, against the packed code (keys in GL_PK0, GL_PK1)
python deploy/shrink.py contracts/mod_court.py build/mod_court.py --pack
npm i genlayer-js@2.0.0-rc.2   # plus the fee-estimate patch in app/README.md
node tests/integration/bradbury.mjs build/mod_court.py
```

Bradbury rejects deploys above ~20 KB of code; deploy the output of
`deploy/shrink.py` (AST-checked, 39.1 KB → 10.7 KB packed). CI re-runs all
direct tests against the packed code.

## Tests (66 direct, Bradbury E2E)

- **Provenance** — the member-signed commitment is recorded; rejected: someone else's signature, a signature for another post, another community or another deployment, garbage, zero and empty signatures, a fabricated hash.
- **Appeals and deadlines** — appeal only registers (no fetch, no LLM) and blocks release; late appeal rejected; failed rulings (404, 503, unreachable host, a different post at the URL, a post over 4000 characters) keep the appeal and a retry succeeds; deadline boundary to the second; competing `release` / `expire_unresolved` / `decide` / repeated `appeal` on the same case; a decided case cannot expire; the bond refund settles as its own payout.
- **Standard and proportionality** — only the cited rule is judged (an insult removed as spam is overturned), harshness is not asked; per-rule action caps; nothing of the post or statement in any view.
- **Money and safeguards** — overturned pays bond + reward, from the bond fund first; upheld bond goes to the bond fund, which the owner cannot withdraw; reservation stops moderation when the pool runs out; moderator suspension the owner cannot lift; paginated cases and payouts with old unsettled payouts found.
- **Settlement** — delivered, failed then recovered, refund and withdraw payouts; wrong sender, time, method, args, an `ACCEPTED`-but-not-finalized or reverted tx, another tx's finalization, RPC down, double settle, one payout per paying tx, one payment per second.
- **Consensus (validator replay)** — agreement on the cited-rule boolean, disagreement on an overturn, the explanation outside consensus, forged payloads, a validator holding a different copy disagrees, same fetch error agreed only when reproduced, never on an LLM error, malformed output reverts, fenced inputs.
- **App** — `check-actions.mjs`: controls per role and state (appeal is bond only, the ruling form requires the privacy acknowledgement, refund after the deadline), consensus vs unverified explanation display, exact GEN amounts beyond 2^53, `toWei` rejecting malformed input.

## License

MIT
