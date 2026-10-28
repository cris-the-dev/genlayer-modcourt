// End-to-end on Testnet Bradbury (Phase 2), on the packed code that is deployed:
//
//   python deploy/shrink.py contracts/mod_court.py build/mod_court.py --pack
//   npm i genlayer-js@2.0.0-rc.2   # plus the estimateTransactionFees patch in app/README.md
//   GL_PK0=0x... GL_PK1=0x... node tests/integration/bradbury.mjs build/mod_court.py [contract]
//
// GL_PK0 owns the community and moderates; GL_PK1 is the member. The member signs commitments
// to two posts hosted at EVIDENCE (byte for byte FINE and SPAM). A forged signature and a
// disproportionate action are rejected; one appeal is overturned after two failed rulings (the
// original is unavailable, then a different post sits at the URL) that leave it waiting; one is
// upheld; the owner withdraws the free pool; both payouts settle from their own transfers once
// the paying transactions finalize. The 3-day expiry needs a clock this test cannot move; Direct
// Mode covers it. Every transaction carries a fee deposit; a paying one also allocates its payout's gas.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { createAccount, createClient, MessageType, encodeExternalMessageFeeParams } from "genlayer-js";
import { testnetBradbury } from "genlayer-js/chains";

const BOND = 5n * 10n ** 14n, REWARD = 10n ** 15n;
const RULES = JSON.stringify([
  { text: "No personal attacks or insults aimed at other members", max_action: "ban" },
  { text: "No spam or unsolicited advertising", max_action: "remove" },
  { text: "Stay on topic: posts must be about GenLayer", max_action: "remove" },
]);
const FINE = "Has anyone benchmarked Bradbury finality? My GenLayer contract takes about 40 seconds to finalize.";
const SPAM = "BUY CHEAP FOLLOWERS NOW at cheap-followers.example, 50% off today only, DM me!!!";
const EVIDENCE = "https://modcourt.cristhedev.com/evidence/";
const CONSENSUS_MAIN = "0x2e2766cbc3e5e61ce93bbcdcbb3eacb82082a019";
const T_FINALIZED = "0x24196ec40f90671b7144e716978686b4f3c7d6b00b23da3971ef2b52af27d87f";
const PAYOUT_GAS = 100000n, PAYOUT_GAS_PRICE = 1000000000n;
// rpc.testnet-chain.genlayer.com (the chain default) does not serve gen_call; this one serves the same chain.
const endpoint = "https://rpc-bradbury.genlayer.com";
const a0 = createAccount(process.env.GL_PK0);
const a1 = createAccount(process.env.GL_PK1);
const c0 = createClient({ chain: testnetBradbury, endpoint, account: a0 });
const c1 = createClient({ chain: testnetBradbury, endpoint, account: a1 });
const sha = (t) => createHash("sha256").update(t).digest("hex");

const fees = async (c, payee) => {
  const messageAllocations = payee && [{
    messageType: MessageType.External, onAcceptance: false, recipient: payee, budget: PAYOUT_GAS * PAYOUT_GAS_PRICE,
    callKey: "0x" + "00".repeat(32), feeParams: encodeExternalMessageFeeParams({ gasLimit: PAYOUT_GAS, maxGasPrice: PAYOUT_GAS_PRICE }),
  }];
  const e = await c.estimateTransactionFees(payee ? { messageAllocations } : {});
  return { distribution: e.distribution, feeValue: e.feeValue, ...(payee && { messageAllocations: e.messageAllocations }) };
};
// The public RPC drops connections now and then; retry the wait, never the write.
async function wait(c, hash, waitUntil = "decided") {
  for (let i = 0; ; i++) {
    try {
      return await c.waitForTransactionReceipt({ hash, waitUntil, interval: 10000, retries: 360 });
    } catch (e) {
      if (i >= 5 || !/fetch failed|ECONNRESET|timed out|socket/i.test(String(e?.details ?? e?.message))) throw e;
      await new Promise((r) => setTimeout(r, 10000));
    }
  }
}
const check = (ok, what) => {
  console.log(ok ? "  ok  " : "  FAIL", what);
  if (!ok) process.exit(1);
};
// A leader timeout (NOT_VOTED) executed nothing, so sending the call again is safe. Bradbury still
// moves such a transaction's value into the contract, where get_accounting shows it as unaccounted.
let stray = 0n;
async function tx(c, label, functionName, args, { value = 0n, payee } = {}) {
  for (let i = 0; ; i++) {
    const hash = await c.writeContract({ address, functionName, args, value, fees: await fees(c, payee) });
    const r = await wait(c, hash);
    console.log(`${label}: ${hash} ${r.txExecutionResultName}`);
    if (r.txExecutionResultName !== "NOT_VOTED" || i >= 2) return { ...r, hash };
    stray += value;
  }
}
const ok = async (...a) => { const r = await tx(...a); check(r.txExecutionResultName === "FINISHED_WITH_RETURN", `${a[1]} succeeds`); return r; };
const fails = async (what, ...a) => check((await tx(...a)).txExecutionResultName !== "FINISHED_WITH_RETURN", what);
const read = async (functionName, args = []) => {
  const v = await c0.readContract({ address, functionName, args });
  const plain = (x) => (x instanceof Map ? Object.fromEntries([...x].map(([k, y]) => [k, plain(y)])) : Array.isArray(x) ? x.map(plain) : x);
  return plain(v);
};
// RPC nodes behind the edge can lag the one that reported the receipt: re-read until `ok` holds (or give up).
async function settled(fn, args, ok) {
  for (let i = 0; ; i++) {
    const v = await read(fn, args);
    if (ok(v) || i >= 12) return v;
    await new Promise((r) => setTimeout(r, 10000));
  }
}
const rpc = async (method, params) => {
  const r = await fetch(endpoint, { method: "POST", headers: { "content-type": "application/json", "user-agent": "modcourt-e2e" }, body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }) });
  return (await r.json()).result;
};
// The consensus-layer transaction that finalized `hash`: it emits TransactionFinalized(txId).
async function finalizeTx(hash, fromBlock) {
  for (;;) {
    const to = BigInt(await rpc("eth_blockNumber", []));
    for (let b = fromBlock; b <= to; b += 1000n) {
      const end = b + 999n > to ? to : b + 999n;
      const logs = await rpc("eth_getLogs", [{ address: CONSENSUS_MAIN, topics: [T_FINALIZED, hash], fromBlock: "0x" + b.toString(16), toBlock: "0x" + end.toString(16) }]);
      if (logs?.length) return logs[0].transactionHash;
    }
    await new Promise((r) => setTimeout(r, 30000));
  }
}
// Settle payout `id`, paid by `paid` (a tx() result), once its transaction finalizes; once only.
async function settle(id, paid, fromBlock) {
  await wait(c0, paid.hash, "finalized");
  const fin = await finalizeTx(paid.hash, fromBlock);
  console.log(`finalized by ${fin}`);
  await ok(c1, `settle payout ${id}`, "settle_payout", [id, paid.hash, fin]);
  check((await settled("get_payout", [id], (x) => x.status === "DELIVERED")).status === "DELIVERED", `payout ${id} DELIVERED`);
  await fails("a payout settles once", c1, "settle again", "settle_payout", [id, paid.hash, fin]);
}

let address = process.argv[3];
if (!address) {
  const hash = await c0.deployContract({ code: readFileSync(process.argv[2], "utf8"), args: [], fees: await fees(c0) });
  const r = await wait(c0, hash);
  address = r.txDataDecoded?.contractAddress;
  console.log(`deploy: ${hash} ${r.txExecutionResultName} -> ${address}`);
  check(r.txExecutionResultName === "FINISHED_WITH_RETURN", "deployed");
}
const fromBlock = BigInt(await rpc("eth_blockNumber", []));
stray = BigInt((await read("get_accounting")).unaccounted);
const cid = Number(await read("get_community_count"));
await ok(c0, "create_community", "create_community", ["GenLayer builders", RULES, BOND, REWARD], { value: 2n * REWARD });
const sign = async (text) => a1.signMessage({ message: await read("get_commitment", [cid, sha(text)]) });
const [fineSig, spamSig] = [await sign(FINE), await sign(SPAM)];
const m = a1.address;

// Provenance and proportionality are checked when the action is recorded.
await fails("a signature for another post is rejected", c0, "act with wrong signature", "act", [cid, m, sha(SPAM), fineSig, 2, "remove"]);
await fails("rule 2 allows at most remove", c0, "ban under rule 2", "act", [cid, m, sha(SPAM), spamSig, 2, "ban"]);
await ok(c0, "act remove (on-topic question)", "act", [cid, m, sha(FINE), fineSig, 3, "remove"]);
await ok(c0, "act remove (spam)", "act", [cid, m, sha(SPAM), spamSig, 2, "remove"]);
await fails("the pool is fully reserved", c0, "third action", "act", [cid, m, sha(FINE), fineSig, 1, "hide"]);
const ids = (await settled("get_cases", [cid, 0, 10], (x) => x.items.length === 2)).items.map((k) => Number(k.id));
check(ids.length === 2, `cases ${ids}`);
const [k0, k1] = ids;

await ok(c1, `appeal case ${k0}`, "appeal", [k0], { value: BOND });
let k = await settled("get_case", [k0], (x) => x.status === "APPEALED");
check(k.status === "APPEALED" && Number(k.resolve_by) === Number(k.appealed_at) + 3 * 86400, "appealed, 3 days to rule");
// Failed rulings revert and leave the appeal waiting.
await fails("an unavailable post reverts", c1, "decide missing.txt", "decide", [k0, EVIDENCE + "missing.txt", "It is about GenLayer."], { payee: m });
await fails("a different post at the URL reverts", c1, "decide spam.txt for case 0", "decide", [k0, EVIDENCE + "spam.txt", "It is about GenLayer."], { payee: m });
check((await read("get_case", [k0])).status === "APPEALED", "still APPEALED");
const pid = Number((await read("get_accounting")).payout_count);
const paid = await ok(c1, "decide fine.txt", "decide", [k0, EVIDENCE + "fine.txt", "It is a question about GenLayer's testnet."], { payee: m });
k = await settled("get_case", [k0], (x) => x.status === "OVERTURNED");
check(k.status === "OVERTURNED" && k.cited_rule_violated === false && !("content" in k) && !("statement" in k), "OVERTURNED, nothing of the post stored");
console.log("    explanation (unverified):", k.explanation_unverified);

await ok(c1, `appeal case ${k1}`, "appeal", [k1], { value: BOND });
await ok(c1, "decide spam.txt", "decide", [k1, EVIDENCE + "spam.txt", "Just sharing a deal."], { payee: m });
k = await settled("get_case", [k1], (x) => x.status === "UPHELD");
check(k.status === "UPHELD" && k.cited_rule_violated === true, "UPHELD");
console.log("    explanation (unverified):", k.explanation_unverified);

// The overturn was paid from the pool (the bond fund was empty); the upheld bond stays out of the owner's reach.
const com = await settled("get_community", [cid], (x) => BigInt(x.bond_fund) === BOND);
check([com.reserved, com.pool, com.bond_fund, com.withdrawable].map(BigInt).join() === [0n, REWARD, BOND, REWARD].join(), "reserved 0, pool = reward, bond fund = bond, withdrawable = reward");
const st = await read("get_moderator_stats", [cid, a0.address]);
check(Number(st.actions) === 2 && Number(st.appeals) === 2 && Number(st.overturned) === 1, "moderator stats 2/2/1");
const withdrawn = await ok(c0, "withdraw_pool", "withdraw_pool", [cid, REWARD], { payee: a0.address });

const p0 = await read("get_payout", [pid]), p1 = await settled("get_payout", [pid + 1], (x) => x.kind === "withdraw");
check(p0.kind === "overturn" && BigInt(p0.amount) === BOND + REWARD && p0.to.toLowerCase() === m.toLowerCase(), `payout ${pid}: bond + reward to the member`);
check(p1.kind === "withdraw" && BigInt(p1.amount) === REWARD, `payout ${pid + 1}: pool withdrawal`);
await settle(pid, paid, fromBlock);
await settle(pid + 1, withdrawn, fromBlock);
// Once the transfers have left, the balance matches what the contract expects to hold.
check(BigInt((await read("get_accounting")).unaccounted) === stray, `balance matches what the contract expects to hold (+${stray} from unexecuted txs)`);
console.log("contract", address, "community", cid);
