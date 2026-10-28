// Asserts which ModCourt app controls appear per role and case state, and that GEN amounts are exact
// (run: node app/check-actions.mjs app/index.html).
import { readFileSync } from "node:fs";
const html = readFileSync(process.argv[2], "utf8");
const js = html.match(/<script type="module">([\s\S]*?)<\/script>/)[1];
const body = js.slice(js.indexOf("function actions"), js.indexOf("async function show"));
// gen / toWei come straight from gl.js (which imports the browser bundle, so it is not loaded whole).
const gl = readFileSync(new URL("./gl.js", import.meta.url), "utf8");
const pick = (name) => gl.slice(gl.indexOf(`export const ${name} =`), gl.indexOf("\n};\n", gl.indexOf(`export const ${name} =`)) + 3).replace("export ", "");
const { gen, toWei } = new Function(`${pick("gen")}\n${pick("toWei")}\nreturn { gen, toWei };`)();
const esc = (s) => String(s ?? "");
const make = new Function("esc", "gen", "when", "B", "ctx", `let me = ctx.me; const cls = { OVERTURNED: "ok", UPHELD: "bad" }; ${body}; return { actions, ruling };`);
const OWN = "0xowner", MOD = "0xmod", U = "0xUser", now = Date.now() / 1000;
const comm = { owner: OWN, rules: ["No insults at members"], max_actions: ["ban"], appeal_bond: 10n ** 15n, reward: 2n * 10n ** 15n, free: 4n * 10n ** 15n, withdrawable: 10n ** 15n, policy_version: 0 };
const open = { id: 0, status: "ACTIVE", target: U, moderator: MOD, action: "remove", rule: 1, appeal_until: now + 999, resolve_by: 0, content_sha256: "ab".repeat(32) };
const appealed = { ...open, status: "APPEALED", resolve_by: now + 999 };
const fns = (me) => make(esc, gen, () => "T", BigInt, { me });
const run = (me, cases = [], isMod = false, c = {}, recov = 0) => fns(me).actions({ ...comm, ...c }, cases, isMod, recov);
const check = (name, ok) => { console.log(ok ? "ok  " : "FAIL", name); if (!ok) process.exitCode = 1; };

check("no wallet: prompt only", run(null, [open]).includes("Connect a wallet"));
check("affected user (case-insensitive) can appeal an open case, bond only", run("0xuser", [open]).includes('data-act="appeal" data-arg="0"') && !run("0xuser", [open]).includes("textarea"));
check("others cannot appeal", !run(MOD, [open], true).includes('data-act="appeal"') && !run("0xother", [open]).includes('data-act="appeal"'));
check("closed window: no appeal, anyone can finalise", !run(U, [{ ...open, appeal_until: now - 1 }]).includes('data-act="appeal"') && run("0xother", [{ ...open, appeal_until: now - 1 }]).includes('data-act="release"'));
check("appealed: the member gets the ruling form with the privacy acknowledgement", /data-form="decide"[\s\S]*name="url"[\s\S]*type="checkbox" name="ok" required/.test(run(U, [appealed])));
check("appealed: nobody else can ask for the ruling, nobody can finalise", !run("0xother", [appealed]).includes("decide") && !run(U, [appealed]).includes("release"));
check("past the resolution deadline: anyone can refund, no ruling form", run("0xother", [{ ...appealed, resolve_by: now - 1 }]).includes('data-act="expire_unresolved"') && !run(U, [{ ...appealed, resolve_by: now - 1 }]).includes("decide"));
check("decided or unresolved cases: no case actions", run(U, ["UPHELD", "OVERTURNED", "UNRESOLVED", "FINAL"].map((s) => ({ ...open, status: s }))) === "");
check("moderator: hash + signature form, shows rule caps, disabled when the pool is out", run(MOD, [], true).includes('name="sig"') && run(MOD, [], true).includes("(max ban)") && !run(MOD, [], true).includes("disabled") && run(MOD, [], true, { free: 10n ** 15n }).includes("disabled"));
check("owner: fund, moderators, withdraw only the withdrawable amount", run(OWN).includes('data-form="fund"') && run(OWN).includes('data-form="set_moderator"') && run(OWN).includes("max 0.001 GEN") && !run(OWN, [], false, { withdrawable: 0 }).includes("withdraw_pool"));
check("owner: amend form prefilled with caps, publishes the next version", run(OWN, [], false, { rules: ["No spam", "Be kind"], max_actions: ["remove", "ban"], policy_version: 2 }).includes('data-form="amend_rules"') && run(OWN, [], false, { rules: ["No spam", "Be kind"], max_actions: ["remove", "ban"], policy_version: 2 }).includes("No spam | remove\nBe kind</textarea>") && run(OWN).includes("Publish v1") && !run("0xother").includes("amend_rules"));
check("member with no cases: nothing", run("0xother") === "");
check("recover only with a failed transfer", run("0xother", [], false, {}, 5).includes('data-form="recover"') && !run("0xother", [], false, {}, 0n).includes("recover"));
const r = fns(U).ruling;
check("ruling: consensus verdict and unverified explanation kept apart", /Consensus: rule 1 not violated[\s\S]*not verified by consensus\): because/.test(r({ ...open, status: "OVERTURNED", cited_rule_violated: false, explanation_unverified: "because" })) && r({ ...open, status: "UPHELD", cited_rule_violated: true }).includes("rule 1 violated"));
check("ruling: unresolved says the action stands unreviewed", r({ ...open, status: "UNRESOLVED" }).includes("unreviewed") && r(open) === "");

// Money: exact in both directions, no floating point.
check("exact bond amounts", gen(500000000000000n) === "0.0005" && gen(1) === "0.000000000000000001" && gen(123456789012345678901234567890n) === "123456789012.34567890123456789" && gen(0) === "0");
check("amounts past 2^53 stay exact", gen(9007199254740993n) === "0.009007199254740993" && toWei("0.009007199254740993") === 9007199254740993n);
check("toWei round-trips and rejects bad input", toWei("0.0005") === 5n * 10n ** 14n && toWei("1") === 10n ** 18n && toWei(".5") === 5n * 10n ** 17n &&
  ["", ".", "1e3", "-1", "0.1234567890123456789", "1,5"].every((s) => { try { toWei(s); return false; } catch { return true; } }));
