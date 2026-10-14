// Asserts which ModCourt app controls appear per role and case state (run: node app/check-actions.mjs app/index.html).
import { readFileSync } from "node:fs";
const html = readFileSync(process.argv[2], "utf8");
const js = html.match(/<script type="module">([\s\S]*?)<\/script>/)[1];
const body = js.slice(js.indexOf("function actions"), js.indexOf("async function show"));
const esc = (s) => String(s ?? "");
const gen = (w, d = 4) => (Number(w) / 1e18).toFixed(d).replace(/\.?0+$/, "");
const make = new Function("esc", "gen", "when", "ctx", `let me = ctx.me; ${body}; return actions;`);
const OWN = "0xowner", MOD = "0xmod", U = "0xUser", now = Date.now() / 1000;
const comm = { owner: OWN, rules: ["No insults at members"], appeal_bond: 1e15, reward: 2e15, free: 4e15 };
const open = { id: 0, status: "ACTIVE", target: U, moderator: MOD, action: "remove", rule: 1, appeal_until: now + 999 };
const run = (me, cases = [], isMod = false, c = {}, recov = 0) => make(esc, gen, () => "T", { me })({ ...comm, ...c }, cases, isMod, recov);
const check = (name, ok) => { console.log(ok ? "ok  " : "FAIL", name); if (!ok) process.exitCode = 1; };

check("no wallet: prompt only", run(null, [open]).includes("Connect a wallet"));
check("affected user (case-insensitive) can appeal an open case", run("0xuser", [open]).includes('data-form="appeal" data-case="0"'));
check("others cannot appeal", !run(MOD, [open], true).includes("appeal") && !run("0xother", [open]).includes('data-form="appeal"'));
check("closed window: no appeal, anyone can finalise", !run(U, [{ ...open, appeal_until: now - 1 }]).includes('data-form="appeal"') && run("0xother", [{ ...open, appeal_until: now - 1 }]).includes('data-act="release"'));
check("decided cases: no case actions", run(U, [{ ...open, status: "UPHELD" }, { ...open, status: "OVERTURNED" }]) === "");
check("moderator: record form, disabled when the pool is out", run(MOD, [], true).includes('data-form="act"') && /Record action<\/button>/.test(run(MOD, [], true)) && run(MOD, [], true, { free: 1e15 }).includes("disabled"));
check("owner: fund, moderators, withdraw only with a free pool", run(OWN).includes('data-form="fund"') && run(OWN).includes('data-form="set_moderator"') && run(OWN).includes("withdraw_pool") && !run(OWN, [], false, { free: 0 }).includes("withdraw_pool"));
check("member with no cases: nothing", run("0xother") === "");
check("recover only with a failed transfer", run("0xother", [], false, {}, 5).includes('data-form="recover"'));
