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
owner     ── create_community(name, rules, appeal_bond, reward) + pool ─▶ ModCourt   (policy v0)
owner     ── amend_rules(community, rules) ─▶ policy v1, v2, …   new actions only
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
Testnet Bradbury Phase 2 (chainId 4221, GenVM v0.3): [`0xEE326047878EF72e24a52Ee9841ab9F8Cee97229`](https://explorer-bradbury.genlayer.com/address/0xEE326047878EF72e24a52Ee9841ab9F8Cee97229)

## Bradbury evidence

Run by [`tests/integration/bradbury.mjs`](tests/integration/bradbury.mjs) on Bradbury Phase 2 (all checks passed). Contract `0xEE326047878EF72e24a52Ee9841ab9F8Cee97229` (deploy [`0x170a92ce…`](https://explorer-bradbury.genlayer.com/tx/0x170a92cec38eb822fb77b83b6838116bba87bb2680e60f82d467f982bb158f4b)), code `build/mod_court.py` (sha256 `516d5d43…`). Owner (also moderator) and member are separate accounts. Every transaction carries a fee deposit; paying calls also allocate their payout's gas. Neither post nor statement appears in any view afterwards; the explanations below are the leader's, as returned in `explanation_unverified`:

- case 0 (judged under policy v0 after rule 3 was removed in v1): "The post asks about finality timing for a GenLayer contract, which is directly on-topic under Rule 3."
- case 1: "The content is unsolicited advertising promoting a commercial service with promotional language and a call to action, which constitutes spam or unsolicited advertising under rule 2."

| Step | Transaction | Outcome |
|---|---|---|
| create community: 3 rules capped ban / remove / remove, bond 0.0005, reward 0.001, pool 0.002 GEN | [`0x74f24bc3…`](https://explorer-bradbury.genlayer.com/tx/0x74f24bc33f153af8720e210815439dc0df67848886986a3962d372090cbcb013) | ok |
| act with the member's signature for a *different* post | [`0x13fff77a…`](https://explorer-bradbury.genlayer.com/tx/0x13fff77a1877fe10fac856e20ea37be13c554097d5aff908c27cd882581d8db3) | rejected: signature does not match the hash |
| act `ban` under rule 2 (max remove) | [`0x7f0fd2bc…`](https://explorer-bradbury.genlayer.com/tx/0x7f0fd2bc3b76b885a9141c43da3960c97d10fcd48c9f0638a51088b650005609) | rejected: disproportionate |
| remove an on-topic question (rule 3), member-signed hash | [`0xf0e78168…`](https://explorer-bradbury.genlayer.com/tx/0xf0e78168ae2d032b4266a56dcc1911f4b1f45ef7c9121c8f19e1c7c46b18ea01) | case 0, reward reserved |
| remove a spam post (rule 2), member-signed hash | [`0xd57467f8…`](https://explorer-bradbury.genlayer.com/tx/0xd57467f8b7f83818a81da81378ff9543905999041eca5bc08dc7111844e19337) | case 1, reward reserved |
| a third action | [`0x0d7d2aca…`](https://explorer-bradbury.genlayer.com/tx/0x0d7d2acadbd8489fdaf9d27137a9b61b5f0ca4cc2d67aa4001b5ed2ce44b231a) | rejected: the pool is fully reserved |
| the member tries to amend the policy | [`0xd401c574…`](https://explorer-bradbury.genlayer.com/tx/0xd401c57461640afde1b5824d2d5b7a91e1598688df175fc9abb8a6d019314af9) | rejected: owner only |
| owner amends: policy v1 drops rule 3 | [`0xc343164a…`](https://explorer-bradbury.genlayer.com/tx/0xc343164a95833ae3479802004fdca20c0debaf2057c03661a8c7b34ae4513182) | v1 has 2 rules, `get_policy(0)` still returns 3; both open cases stay on v0 |
| member appeals case 0 (bond only, no AI) | [`0xbcf0f857…`](https://explorer-bradbury.genlayer.com/tx/0xbcf0f857aa3d0da0601219e98cc0767b9eb79c208f181751b8bf4df335d36dbf) | APPEALED, `resolve_by` = appeal + 3 days |
| ruling from `evidence/missing.txt` (404) | [`0x2ad0fcab…`](https://explorer-bradbury.genlayer.com/tx/0x2ad0fcabff6907de1b7739b1a6415a346379cd9ce18be98e8231719a0ea920d0) | rejected: original unavailable; case still APPEALED |
| ruling from `evidence/spam.txt` (another post) | [`0x75e93d5b…`](https://explorer-bradbury.genlayer.com/tx/0x75e93d5bcccbf1aa43b5b55d2905df0732208b5f79218f1078b3a76a53397d7e) | rejected: hash mismatch; case still APPEALED |
| ruling from `evidence/fine.txt` (retry) | [`0x1e19df09…`](https://explorer-bradbury.genlayer.com/tx/0x1e19df097175c2fc51e108eee7a3873d2759c8c2714b120c4e9b4cc9ce351e57) | **OVERTURNED** (`cited_rule_violated: false`): bond + reward = payout 0 |
| member appeals case 1 | [`0x4a1d6a1a…`](https://explorer-bradbury.genlayer.com/tx/0x4a1d6a1ad431f53164d4e3fac39d4338b1d9fce5a4c285e3551687fcbea81148) | APPEALED |
| ruling from `evidence/spam.txt` | [`0xb093b288…`](https://explorer-bradbury.genlayer.com/tx/0xb093b288c243ca696201568cffff7424525bb967be16ce969106a7d4f9700718) | **UPHELD**: bond goes to the bond fund |
| owner withdraws all it may (0.001; reserved 0, bond fund 0.0005 not withdrawable) | [`0x58a15ed7…`](https://explorer-bradbury.genlayer.com/tx/0x58a15ed76a3023211ad6f0ef7a32c4ecb9ee2004595b7007c424c304c7dc5b3f) | payout 1 |

Moderator stats afterwards: 2 actions, 2 appeals, 1 overturned. Both payouts were settled from their own transfer once the paying transaction finalized (`settle_payout` checks the paying tx, its finalization and the executed message):

| Payout | Kind | Amount | Paid by | Finalized by | `settle_payout` | Result |
|---|---|---|---|---|---|---|
| 0 | overturn → member | 0.0015 GEN | [`0x1e19df09…`](https://explorer-bradbury.genlayer.com/tx/0x1e19df097175c2fc51e108eee7a3873d2759c8c2714b120c4e9b4cc9ce351e57) | [`0x665b0a7f…`](https://explorer-bradbury.genlayer.com/tx/0x665b0a7fbc5ee0fd836698b23b94749ceeecfae22884c06930182d351cc99ed3) | [`0x44462001…`](https://explorer-bradbury.genlayer.com/tx/0x44462001ff540c497483ce42997f1e06ad64dfdf5dfe105ab77647273d3e5425) | DELIVERED |
| 1 | withdraw → owner | 0.001 GEN | [`0x58a15ed7…`](https://explorer-bradbury.genlayer.com/tx/0x58a15ed76a3023211ad6f0ef7a32c4ecb9ee2004595b7007c424c304c7dc5b3f) | [`0xe9d0ccd8…`](https://explorer-bradbury.genlayer.com/tx/0xe9d0ccd8f02e1030d2cce20d96811bf9f3a1d7b6394b08636901d3cf6cfa376e) | [`0xb60c1fc6…`](https://explorer-bradbury.genlayer.com/tx/0xb60c1fc6cd5953ee43f023a5385cec42ecad60c63badf5598f6fbf3ba07e7917) | DELIVERED |

Settling the same payout again is rejected ([`0xafc0c20f…`](https://explorer-bradbury.genlayer.com/tx/0xafc0c20ff6f149cc22e2dc0cba24aaf42e2cc34f19cd769fec7577e4b618e42f), [`0x7be235a7…`](https://explorer-bradbury.genlayer.com/tx/0x7be235a7c19c58e78ebf2abcbff8f3b5dd6ef4a344181fd4b5622ed2128ff41f)). Afterwards `get_accounting` reports `unaccounted: 0`. The resolution deadline (3 days) and `expire_unresolved` are covered in Direct Mode only. Case 0 cites rule 3, which policy v1 no longer has: its ruling succeeded because `decide` reads the case's own version.

## Policy amendments

Rules change; a member should not lose an appeal because the owner rewrote
the rule after the fact. `amend_rules(community, rules_json)` (owner only,
same validation as at creation, an unchanged policy is rejected) publishes
the next version and keeps every earlier one: `get_policy(community, version)`
returns any of them. Each case records the `policy_version` in force when the
moderator acted, and `decide` judges it against *that* version's rule and
cap, never the current text. New actions are checked against the current
version. The app shows the version on every case and lets the owner amend
from the community page.

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
and case state the amend form prefilled with caps, and exact money formatting.

## API

| Method | Who | Notes |
|---|---|---|
| `create_community(name, rules_json, appeal_bond, reward)` payable | owner | pool = `msg.value`; rules: strings or `{"text", "max_action"}`, 1–20 |
| `amend_rules(id, rules_json)` | owner | publishes the next policy version; open and future cases keep the version they were taken under |
| `fund(id)` payable / `set_moderator(id, who, enabled)` / `withdraw_pool(id, amount)` | anyone / owner / owner | withdraw ≤ `withdrawable` |
| `act(id, target, content_sha256, signature, rule, action)` | moderator | member-signed hash; action within the rule's cap; not suspended |
| `appeal(case_id)` payable | affected member | exactly the bond, within 7 days; returns the resolution deadline |
| `decide(case_id, content_url, statement)` | affected member | until 3 days after the appeal; retryable |
| `expire_unresolved(case_id)` / `release(case_id)` | anyone | bond refund after the deadline / final after 7 days unappealed |
| `settle_payout(payout_id, tx_hash, finalize_tx)` / `recover(to)` | anyone / payee | |
| `get_community`, `get_community_count`, `get_policy(id, version)`, `get_commitment`, `get_cases(id, offset, limit)`, `get_case`, `is_moderator`, `get_moderator_stats`, `get_payout`, `get_payouts(start, limit, only_unsettled)`, `get_accounting`, `get_recoverable` | view | |

## Run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
genvm-lint check contracts/mod_court.py
pytest tests/direct -v                         # 67 tests
# end-to-end on Bradbury Phase 2, against the packed code (keys in GL_PK0, GL_PK1)
python deploy/shrink.py contracts/mod_court.py build/mod_court.py --pack
npm i genlayer-js@2.0.0-rc.2   # plus the fee-estimate patch in app/README.md
node tests/integration/bradbury.mjs build/mod_court.py
```

Bradbury rejects deploys above ~20 KB of code; deploy the output of
`deploy/shrink.py` (AST-checked, 40.5 KB → 10.8 KB packed). CI re-runs all
direct tests against the packed code.

## Tests (67 direct, Bradbury E2E)

- **Provenance** — the member-signed commitment is recorded; rejected: someone else's signature, a signature for another post, another community or another deployment, garbage, zero and empty signatures, a fabricated hash.
- **Appeals and deadlines** — appeal only registers (no fetch, no LLM) and blocks release; late appeal rejected; failed rulings (404, 503, unreachable host, a different post at the URL, a post over 4000 characters) keep the appeal and a retry succeeds; deadline boundary to the second; competing `release` / `expire_unresolved` / `decide` / repeated `appeal` on the same case; a decided case cannot expire; the bond refund settles as its own payout.
- **Policy amendments** — owner only; empty or unchanged policy rejected; every version readable; new actions follow the new rules and caps; a case taken under v0 is judged against v0's rule after the amendment.
- **Standard and proportionality** — only the cited rule is judged (an insult removed as spam is overturned), harshness is not asked; per-rule action caps; nothing of the post or statement in any view.
- **Money and safeguards** — overturned pays bond + reward, from the bond fund first; upheld bond goes to the bond fund, which the owner cannot withdraw; reservation stops moderation when the pool runs out; moderator suspension the owner cannot lift; paginated cases and payouts with old unsettled payouts found.
- **Settlement** — delivered, failed then recovered, refund and withdraw payouts; wrong sender, time, method, args, an `ACCEPTED`-but-not-finalized or reverted tx, another tx's finalization, RPC down, double settle, one payout per paying tx, one payment per second.
- **Consensus (validator replay)** — agreement on the cited-rule boolean, disagreement on an overturn, the explanation outside consensus, forged payloads, a validator holding a different copy disagrees, same fetch error agreed only when reproduced, never on an LLM error, malformed output reverts, fenced inputs.
- **App** — `check-actions.mjs`: controls per role and state (appeal is bond only, the ruling form requires the privacy acknowledgement, refund after the deadline), consensus vs unverified explanation display, exact GEN amounts beyond 2^53, `toWei` rejecting malformed input.

## License

MIT
