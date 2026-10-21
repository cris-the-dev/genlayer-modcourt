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
Testnet Bradbury (chainId 4221): [`0xC7E388a86d225e4bA721325b76322A389639d897`](https://explorer-bradbury.genlayer.com/address/0xC7E388a86d225e4bA721325b76322A389639d897)

## Bradbury evidence

Run by [`tests/integration/test_mod_court.py`](tests/integration/test_mod_court.py) (1 passed, 55 min). Contract `0xC7E388a86d225e4bA721325b76322A389639d897` (deploy [`0x7a17c8da…`](https://explorer-bradbury.genlayer.com/tx/0x7a17c8daa3cb46079e7b05712ba80c5e634e35013c9a4602df0c83aa21ce3e13)), code `build/mod_court.py` (sha256 `03731525…`). Owner (also moderator) and member are separate accounts. Neither post nor statement appears in any view afterwards; the explanations below are the leader's, as returned in `explanation_unverified`:

- case 0: "The post explicitly discusses the required topic by asking a technical question about its functionality."
- case 1: "The content is an unsolicited advertisement for a commercial service, which constitutes spam."

| Step | Transaction | Outcome |
|---|---|---|
| create community: 3 rules capped ban / remove / remove, bond 0.0005, reward 0.001, pool 0.002 GEN | [`0xb0868e1c…`](https://explorer-bradbury.genlayer.com/tx/0xb0868e1ced8acf47c67ac163be20f26c885818887165780cf65a369ce60e44ba) | ok |
| act with the member's signature for a *different* post | [`0x45516c2f…`](https://explorer-bradbury.genlayer.com/tx/0x45516c2f5999001edb958e42e377f053b7bb9884fa8320f6cb19fc3e5e6af706) | rejected: signature does not match the hash |
| act `ban` under rule 2 (max remove) | [`0x57663d8a…`](https://explorer-bradbury.genlayer.com/tx/0x57663d8a81adaac0a36b4871c36dda5630d23d752dbeba5faf0da671ce99b64e) | rejected: disproportionate |
| remove an on-topic question (rule 3), member-signed hash | [`0xa56f1617…`](https://explorer-bradbury.genlayer.com/tx/0xa56f1617ac3ddd82729c60bc69730a17d2b499eb130a86b61a777406e941723e) | case 0, reward reserved |
| remove a spam post (rule 2), member-signed hash | [`0x13e2b4a9…`](https://explorer-bradbury.genlayer.com/tx/0x13e2b4a9af5768f207de002f57c69e0fc2bc04f5becbdc0b833588c6a25b2383) | case 1, reward reserved |
| a third action | [`0x18b32936…`](https://explorer-bradbury.genlayer.com/tx/0x18b3293668d790356bba67c76dc976ac7420d9c4ea8c93d6ac4f549fae7cdced) | rejected: the pool is fully reserved |
| member appeals case 0 (bond only, no AI) | [`0x7564ddc0…`](https://explorer-bradbury.genlayer.com/tx/0x7564ddc026b814100cf43f2807d1889dee1378b7310b6d0a8f303cccd7fd9424) | APPEALED, `resolve_by` set |
| ruling from `evidence/missing.txt` (404) | [`0x862ae7be…`](https://explorer-bradbury.genlayer.com/tx/0x862ae7be14a1899bb768afc3b66ce579fb044110e323013a6e3c6f0770032ed6) | rejected: original unavailable; case still APPEALED |
| ruling from `evidence/spam.txt` (another post) | [`0xef9abd16…`](https://explorer-bradbury.genlayer.com/tx/0xef9abd160eadac7f686182b55112e838f595edf7926f3b556699f17756d3f398) | rejected: hash mismatch; case still APPEALED |
| ruling from `evidence/fine.txt` (retry) | [`0xf14cadae…`](https://explorer-bradbury.genlayer.com/tx/0xf14cadae6da5abeafd8f079ee09383b2c8e92b248f39d889d40419afc81db077) | **OVERTURNED** (`cited_rule_violated: false`): bond + reward = payout 0 |
| member appeals case 1 | [`0xc380ce7b…`](https://explorer-bradbury.genlayer.com/tx/0xc380ce7bde0dd102632da113ca189db817ad8a6a6db57d68ff4eaaf69392269f) | APPEALED |
| ruling from `evidence/spam.txt` | [`0x8f5d769f…`](https://explorer-bradbury.genlayer.com/tx/0x8f5d769fca10d7d6162cf9608f651a15a41d5810be49c0a771fa2f02ee4f8bdf) | **UPHELD**: bond goes to the bond fund |
| owner withdraws all it may (0.001; reserved 0, bond fund 0.0005 not withdrawable) | [`0xd08607ce…`](https://explorer-bradbury.genlayer.com/tx/0xd08607ce2d88ab97ed1777aedbce717c04ea1b055b820c6fd9394e16a9be0d91) | payout 1 |

Both payouts were listed by `get_payouts(0, 50, true)` and settled from their own transfer after the paying transaction finalized. Balance change is the recipient's `eth_getBalance` at the finalizing block minus the block before, checked by the test:

| Payout | Kind | Paid by | Finalized by (block) | Recipient balance | `settle_payout` | Result |
|---|---|---|---|---|---|---|
| 0 | overturn → member | [`0xf14cadae…`](https://explorer-bradbury.genlayer.com/tx/0xf14cadae6da5abeafd8f079ee09383b2c8e92b248f39d889d40419afc81db077) | [`0x58291745…`](https://explorer-bradbury.genlayer.com/tx/0x58291745fda0a013202538ac6a27612e0fbf590b5e8086ffd5ce8518fd4d4de5) (25745621) | +0.0015 GEN | [`0x6f69b6c5…`](https://explorer-bradbury.genlayer.com/tx/0x6f69b6c5c3be8826feb38586e92a4c63c3bad07806ab66463f35cd2e526c8e13) | DELIVERED |
| 1 | withdraw → owner | [`0xd08607ce…`](https://explorer-bradbury.genlayer.com/tx/0xd08607ce2d88ab97ed1777aedbce717c04ea1b055b820c6fd9394e16a9be0d91) | [`0xaea516c5…`](https://explorer-bradbury.genlayer.com/tx/0xaea516c50d2dfc1bffdb7ce1d2da3815a43e2f2f70acbcab787564e2a542299f) (25746392) | +0.001 GEN | [`0x4bc7b969…`](https://explorer-bradbury.genlayer.com/tx/0x4bc7b9691a82d0e2bde8860b440498731a717fd8160f6129e7d3c60f5398b044) | DELIVERED |

Settling the same payout again is rejected ([`0xb6926ad2…`](https://explorer-bradbury.genlayer.com/tx/0xb6926ad2a4ffbc86c4ca805de38ad038ac9deb946f567944b7b920495f1d41d5), [`0x53b0a194…`](https://explorer-bradbury.genlayer.com/tx/0x53b0a1947e38a2440f6f027a2dcd11783ffbe290209398b76012444cb83811a2)). Afterwards no payout is unsettled and `get_accounting` reports `unaccounted: 0`. The resolution deadline (3 days) and `expire_unresolved` are covered in Direct Mode only.

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
# integration, on Bradbury, against the packed code (keys in GL_PK0..2 env vars)
python deploy/shrink.py contracts/mod_court.py build/mod_court.py --pack
cd tests/integration && gltest . -v -s --network testnet_bradbury
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
