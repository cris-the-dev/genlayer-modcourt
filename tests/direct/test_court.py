"""Community, provenance, the two-step appeal, deadlines, funds and discovery."""

import json

import pytest

from tests.direct.conftest import (
    BOND,
    CHARLIE,
    CONTENT,
    MALLORY,
    POOL,
    REWARD,
    RULES,
    STATEMENT,
    URL,
    act,
    appeal,
    chain_balance,
    decide,
    sha,
    sign,
    tick,
    to_hex,
)


def test_create(mc, direct_alice, direct_bob, direct_charlie):
    c = mc.get_community(0)
    assert c["owner"].lower() == to_hex(direct_alice).lower() and c["rules"] == RULES
    assert c["max_actions"] == ["ban"] * 3 and c["bond_fund"] == 0
    assert c["pool"] == POOL and c["free"] == POOL and c["withdrawable"] == POOL and c["appeal_bond"] == BOND
    assert mc.is_moderator(0, to_hex(direct_alice)) and mc.is_moderator(0, to_hex(direct_bob))
    assert not mc.is_moderator(0, to_hex(direct_charlie))


@pytest.mark.parametrize(
    "name, rules, bond, reward, msg",
    [
        ("Ok name", "not json", BOND, REWARD, "JSON list"),
        ("Ok name", json.dumps([]), BOND, REWARD, "1-20 rules"),
        ("Ok name", json.dumps(["rule"]), BOND, REWARD, "1-20 rules"),
        ("Ok name", json.dumps(["A good rule"] * 21), BOND, REWARD, "1-20 rules"),
        ("Ok name", json.dumps([{"text": "A good rule", "max_action": "jail"}]), BOND, REWARD, "max_action must be"),
        ("Ok name", json.dumps([{"max_action": "hide"}]), BOND, REWARD, "JSON list"),
        ("x", json.dumps(RULES), BOND, REWARD, "3-80"),
        ("Ok name", json.dumps(RULES), 0, REWARD, "positive"),
    ],
)
def test_create_validation(mc, direct_vm, name, rules, bond, reward, msg):
    with direct_vm.expect_revert(msg):
        mc.create_community(name, rules, bond, reward)


def test_moderators_are_managed_by_the_owner(mc, direct_vm, direct_bob, direct_charlie):
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("not authorised"):
        mc.set_moderator(0, to_hex(direct_charlie), True)
    direct_vm.sender = direct_charlie
    with direct_vm.expect_revert("not a moderator"):
        act(direct_vm, mc, signer=MALLORY)


@pytest.mark.parametrize(
    "sha_, rule, action, msg",
    [("abc", 1, "remove", "64 hex"), (sha("x"), 0, "remove", "no such rule"), (sha("x"), 4, "remove", "no such rule"), (sha("x"), 1, "delete", "action must be")],
)
def test_act_validation(mc, direct_vm, direct_bob, sha_, rule, action, msg):
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert(msg):
        mc.act(0, CHARLIE.address, sha_, sign(direct_vm, sha_), rule, action)


# ── Provenance: the member's signed commitment ──────────────────────────────


def test_a_signed_commitment_records_the_action(case, direct_charlie):
    k = case.get_case(0)
    assert k["target"].lower() == CHARLIE.address.lower() and k["content_sha256"] == sha(CONTENT)
    assert k["status"] == "ACTIVE" and len(k["signature"]) == 132


def test_forged_records_are_rejected(mc, direct_vm, direct_bob):
    """A moderator cannot attribute content to a member who never signed it."""
    direct_vm.sender = direct_bob
    forged = {
        "someone else signed": sign(direct_vm, sha(CONTENT), MALLORY),
        "signed another post": sign(direct_vm, sha(CONTENT + " (edited)")),
        "signed in another community": sign(direct_vm, sha(CONTENT), community_id=1),
        "signed for another deployment": sign(direct_vm, sha(CONTENT), contract="0x" + "ab" * 20),
        "garbage": "0x1234",
        "zeros": "0x" + "00" * 65,
        "empty": "",
    }
    for sig in forged.values():
        with direct_vm.expect_revert("not the member's commitment"):
            act(direct_vm, mc, sig=sig)
    # A fabricated hash nobody signed, with a real signature of the true one.
    with direct_vm.expect_revert("not the member's commitment"):
        mc.act(0, CHARLIE.address, sha("fabricated"), sign(direct_vm, sha(CONTENT)), 3, "remove")
    assert mc.get_community(0)["case_count"] == 0 and mc.get_community(0)["reserved"] == 0


def test_commitment_text_is_published(mc, direct_vm):
    text = mc.get_commitment(0, "0x" + sha(CONTENT).upper())
    assert text == f"ModCourt content commitment\ncontract: {to_hex(direct_vm._contract_address).lower()}\ncommunity: 0\nsha256: {sha(CONTENT)}"


# ── Proportionality is checked deterministically ────────────────────────────


def test_disproportionate_penalty_is_rejected(direct_vm, direct_deploy, direct_alice):
    direct_vm.warp("2030-01-01T10:00:00Z")
    c = direct_deploy("contracts/mod_court.py")
    direct_vm.sender = direct_alice
    direct_vm.value = POOL
    c.create_community("Capped", json.dumps([{"text": "Stay on topic please", "max_action": "remove"}, "No personal attacks"]), BOND, REWARD)
    direct_vm.value = 0
    assert c.get_community(0)["max_actions"] == ["remove", "ban"]
    for action in ("mute", "ban"):
        with direct_vm.expect_revert("rule 1 allows at most remove"):
            act(direct_vm, c, rule=1, action=action)
    act(direct_vm, c, rule=1, action="remove")
    act(direct_vm, c, content="other post", rule=2, action="ban")


def test_reservation_stops_when_the_pool_is_out(mc, direct_vm, direct_alice, direct_bob):
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("cannot moderate yourself"):
        mc.act(0, to_hex(direct_bob), sha("x"), sign(direct_vm, sha("x")), 1, "remove")
    act(direct_vm, mc, content="a", rule=1, action="hide")
    act(direct_vm, mc, content="b", rule=2, action="mute")
    assert mc.get_community(0)["free"] == 0
    with direct_vm.expect_revert("reward pool exhausted"):
        act(direct_vm, mc, content="c", rule=2, action="ban")
    direct_vm.sender = direct_alice
    direct_vm.value = REWARD
    mc.fund(0)
    direct_vm.value = 0
    direct_vm.sender = direct_bob
    act(direct_vm, mc, content="c", rule=2, action="ban")
    assert mc.get_moderator_stats(0, to_hex(direct_bob)) == {"actions": 3, "appeals": 0, "overturned": 0}


# ── Two-step appeal ─────────────────────────────────────────────────────────


def test_appeal_only_registers_and_blocks_release(case, direct_vm, direct_bob, direct_charlie, ledger):
    with direct_vm.expect_revert("only the affected user"):
        appeal(direct_vm, case, direct_bob)
    with direct_vm.expect_revert("exactly the appeal bond"):
        appeal(direct_vm, case, direct_charlie, value=BOND - 1)
    direct_vm.warp("2030-01-08T09:59:59Z")  # last second of the window
    resolve_by = appeal(direct_vm, case, direct_charlie)
    k = case.get_case(0)
    assert k["status"] == "APPEALED" and k["resolve_by"] == resolve_by == k["appealed_at"] + 3 * 86_400
    assert ledger.transfers == [] and case.get_moderator_stats(0, to_hex(direct_bob))["appeals"] == 1
    with direct_vm.expect_revert("appeal window closed"):
        appeal(direct_vm, case, direct_charlie)
    direct_vm.warp("2030-01-09T10:00:00Z")  # the appeal window is over, the appeal is not
    with direct_vm.expect_revert("still open for appeal"):
        case.release(0)
    assert case.get_case(0)["status"] == "APPEALED"


def test_late_appeal_is_rejected_and_release_finalizes(case, direct_vm, direct_charlie):
    with direct_vm.expect_revert("still open for appeal"):
        case.release(0)
    direct_vm.warp("2030-01-08T10:00:01Z")
    with direct_vm.expect_revert("appeal window closed"):
        appeal(direct_vm, case, direct_charlie)
    case.release(0)
    assert case.get_case(0)["status"] == "FINAL" and case.get_community(0)["reserved"] == 0
    with direct_vm.expect_revert("still open for appeal"):
        case.release(0)
    with direct_vm.expect_revert("appeal window closed"):
        appeal(direct_vm, case, direct_charlie)


def test_overturned_pays_bond_and_reward(case, direct_vm, direct_bob, direct_charlie, ledger):
    appeal(direct_vm, case, direct_charlie)
    r = decide(direct_vm, case, direct_charlie, violated=False)
    assert r == {"status": "OVERTURNED", "cited_rule_violated": False, "explanation_unverified": "ruled"}
    assert ledger.paid_to(direct_charlie) == BOND + REWARD
    c = case.get_community(0)
    assert c["pool"] == POOL - REWARD and c["reserved"] == 0
    k = case.get_case(0)
    assert k["cited_rule_violated"] is False and k["explanation_unverified"] == "ruled"
    assert case.get_moderator_stats(0, to_hex(direct_bob)) == {"actions": 1, "appeals": 1, "overturned": 1}


def test_nothing_of_the_post_or_statement_is_stored(case, direct_vm, direct_charlie):
    appeal(direct_vm, case, direct_charlie)
    decide(direct_vm, case, direct_charlie, violated=True)
    k = case.get_case(0)
    assert not ({"content", "statement", "url"} & set(k))
    assert CONTENT not in json.dumps(k) and STATEMENT not in json.dumps(k)


def test_upheld_bond_goes_to_the_bond_fund_not_the_owner(case, direct_vm, direct_alice, direct_bob, direct_charlie, ledger):
    appeal(direct_vm, case, direct_charlie)
    r = decide(direct_vm, case, direct_charlie, violated=True)
    assert r["status"] == "UPHELD" and r["cited_rule_violated"] is True
    assert ledger.transfers == []
    c = case.get_community(0)
    assert c["pool"] == POOL and c["bond_fund"] == BOND and c["reserved"] == 0 and c["withdrawable"] == POOL
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("unreserved pool"):
        case.withdraw_pool(0, POOL + 1)  # the bond fund is never withdrawable
    case.withdraw_pool(0, POOL)
    assert ledger.paid_to(direct_alice) == POOL and case.get_community(0)["bond_fund"] == BOND


def test_bond_fund_pays_overturn_rewards_first(case, direct_vm, direct_bob, direct_charlie):
    appeal(direct_vm, case, direct_charlie)
    decide(direct_vm, case, direct_charlie, violated=True)  # bond fund: BOND
    direct_vm.sender = direct_bob
    act(direct_vm, case, content="second post")
    appeal(direct_vm, case, direct_charlie, case_id=1)
    decide(direct_vm, case, direct_charlie, violated=False, body="second post", case_id=1)
    c = case.get_community(0)
    assert c["bond_fund"] == 0 and c["pool"] == POOL - (REWARD - BOND)


# ── A ruling that fails changes nothing and can be retried ──────────────────


@pytest.mark.parametrize(
    "kw, err",
    [
        ({"status": 404}, "content URL returned HTTP 404"),  # original taken down
        ({"status": 503}, "content URL returned HTTP 503"),  # temporarily unavailable
        ({"body": CONTENT + " (edited)"}, "does not match the signed hash"),  # mismatched copy
        ({"body": "x" * 4001}, "does not match the signed hash"),
    ],
)
def test_failed_rulings_keep_the_appeal_and_can_be_retried(case, direct_vm, direct_charlie, ledger, kw, err):
    appeal(direct_vm, case, direct_charlie)
    with direct_vm.expect_revert(err):
        decide(direct_vm, case, direct_charlie, **kw)
    assert case.get_case(0)["status"] == "APPEALED" and ledger.transfers == []
    assert decide(direct_vm, case, direct_charlie)["status"] == "OVERTURNED"


def test_unreachable_original(case, direct_vm, direct_charlie):
    appeal(direct_vm, case, direct_charlie)
    direct_vm.clear_mocks()  # no copy anywhere
    direct_vm.sender = direct_charlie
    with direct_vm.expect_revert("content unreachable"):
        case.decide(0, "https://gone.example/post", STATEMENT)
    assert case.get_case(0)["status"] == "APPEALED"


def test_decide_guards(case, direct_vm, direct_bob, direct_charlie):
    with direct_vm.expect_revert("no appeal waiting"):
        decide(direct_vm, case, direct_charlie)  # not appealed yet
    appeal(direct_vm, case, direct_charlie)
    with direct_vm.expect_revert("only the affected user"):
        decide(direct_vm, case, direct_bob)
    for url in ("ftp://x.example/a", "member.example/post", "https://" + "a" * 400):
        with direct_vm.expect_revert("http(s) URL"):
            decide(direct_vm, case, direct_charlie, url=url)
    with direct_vm.expect_revert("statement up to 1000"):
        decide(direct_vm, case, direct_charlie, statement="x" * 1001)
    decide(direct_vm, case, direct_charlie)
    with direct_vm.expect_revert("no appeal waiting"):
        decide(direct_vm, case, direct_charlie)


# ── Resolution deadline and competing expiry operations ─────────────────────


def test_unresolved_appeal_refunds_the_bond(case, direct_vm, direct_bob, direct_charlie, ledger):
    direct_vm.warp("2030-01-08T09:00:00Z")
    appeal(direct_vm, case, direct_charlie)
    direct_vm.sender = direct_bob
    direct_vm.warp("2030-01-11T09:00:00Z")  # exactly the deadline: still decidable
    with direct_vm.expect_revert("no appeal past its resolution deadline"):
        case.expire_unresolved(0)
    with direct_vm.expect_revert("still open for appeal"):
        case.release(0)
    direct_vm.warp("2030-01-11T09:00:01Z")
    with direct_vm.expect_revert("no appeal waiting"):
        decide(direct_vm, case, direct_charlie)
    direct_vm.sender = direct_bob  # anyone may expire it
    chain_balance(direct_vm, POOL + BOND)
    case.expire_unresolved(0)
    assert ledger.paid_to(direct_charlie) == BOND
    k = case.get_case(0)
    assert k["status"] == "UNRESOLVED" and k["cited_rule_violated"] is None
    c = case.get_community(0)
    assert c["reserved"] == 0 and c["pool"] == POOL and c["bond_fund"] == 0
    assert case.get_payout(0)["kind"] == "refund" and case.get_payout(0)["ref"] == 0
    with direct_vm.expect_revert("no appeal past its resolution deadline"):
        case.expire_unresolved(0)
    with direct_vm.expect_revert("still open for appeal"):
        case.release(0)
    with direct_vm.expect_revert("appeal window closed"):
        appeal(direct_vm, case, direct_charlie)
    assert case.get_moderator_stats(0, to_hex(direct_bob))["overturned"] == 0


def test_a_decided_case_cannot_expire(case, direct_vm, direct_charlie):
    appeal(direct_vm, case, direct_charlie)
    decide(direct_vm, case, direct_charlie, violated=True)
    direct_vm.warp("2030-02-01T10:00:00Z")
    with direct_vm.expect_revert("no appeal past its resolution deadline"):
        case.expire_unresolved(0)
    with direct_vm.expect_revert("still open for appeal"):
        case.release(0)


# ── Safeguard against repeated questionable actions ─────────────────────────


def test_moderator_with_mostly_overturned_actions_is_suspended(mc, direct_vm, direct_alice, direct_bob, direct_charlie):
    direct_vm.sender = direct_alice
    direct_vm.value = 4 * REWARD
    mc.fund(0)
    direct_vm.value = 0
    for i in range(3):
        direct_vm.sender = direct_bob
        act(direct_vm, mc, content=f"post {i}")
        appeal(direct_vm, mc, direct_charlie, case_id=i)
        tick(direct_vm)
        chain_balance(direct_vm, 10 * REWARD)
        decide(direct_vm, mc, direct_charlie, violated=False, body=f"post {i}", case_id=i)
    assert mc.get_moderator_stats(0, to_hex(direct_bob)) == {"actions": 3, "appeals": 3, "overturned": 3}
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("moderator suspended"):
        act(direct_vm, mc, content="post 3")
    direct_vm.sender = direct_alice  # the owner cannot lift it by re-enabling
    mc.set_moderator(0, to_hex(direct_bob), True)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("moderator suspended"):
        act(direct_vm, mc, content="post 3")


# ── Discovery ───────────────────────────────────────────────────────────────


def test_cases_are_paginated(mc, direct_vm, direct_alice, direct_bob):
    direct_vm.sender = direct_alice
    direct_vm.value = 3 * REWARD
    mc.fund(0)
    direct_vm.value = 0
    direct_vm.sender = direct_bob
    for i in range(5):
        act(direct_vm, mc, content=f"p{i}")
    page = mc.get_cases(0, 0, 2)
    assert page["total"] == 5 and [k["id"] for k in page["items"]] == [0, 1]
    assert [k["id"] for k in mc.get_cases(0, 4, 10)["items"]] == [4]
    assert mc.get_cases(0, 9, 10)["items"] == [] and len(mc.get_cases(0, 0, 1000)["items"]) == 5


def test_payouts_are_paginated_and_unsettled_ones_found(case, direct_vm, direct_alice, direct_charlie, chain):
    appeal(direct_vm, case, direct_charlie)
    decide(direct_vm, case, direct_charlie)  # payout 0
    direct_vm.sender = direct_alice
    for _ in range(3):  # payouts 1-3
        tick(direct_vm)
        case.withdraw_pool(0, 1)
    tx, fin = chain.pay(case, 1, "withdraw_pool", [0, 1])
    case.settle_payout(1, tx, fin)
    everything = case.get_payouts(0, 50, False)
    assert everything["total"] == 4 and [p["id"] for p in everything["items"]] == [0, 1, 2, 3] and everything["next"] is None
    first = case.get_payouts(0, 2, True)
    assert [p["id"] for p in first["items"]] == [0, 2] and first["next"] == 3
    rest = case.get_payouts(first["next"], 2, True)
    assert [p["id"] for p in rest["items"]] == [3] and rest["next"] is None
    with direct_vm.expect_revert("payout not found"):
        case.get_payout(4)


def test_owner_withdraws_only_the_unreserved_pool(case, direct_vm, direct_alice, direct_bob, ledger):
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("not authorised"):
        case.withdraw_pool(0, 1)
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("unreserved pool"):
        case.withdraw_pool(0, REWARD + 1)
    case.withdraw_pool(0, REWARD)
    assert ledger.paid_to(direct_alice) == REWARD and case.get_community(0)["free"] == 0


# ── Each payout settles from its own transfer ───────────────────────────────

OTHER = "0x" + "77" * 20
DECIDE = [0, URL, STATEMENT]


def overturned(case, vm, who):
    appeal(vm, case, who)
    decide(vm, case, who)


def test_delivered_overturn_settles(case, direct_vm, direct_charlie, direct_bob, chain):
    overturned(case, direct_vm, direct_charlie)
    tx, fin = chain.pay(case, 0, "decide", DECIDE)
    direct_vm.sender = direct_bob
    assert case.settle_payout(0, tx, fin) == "DELIVERED"
    assert case.get_payout(0)["tx"] == tx and case.get_payout(0)["ref"] == 0
    assert case.get_recoverable(to_hex(direct_charlie)) == 0
    assert direct_vm.run_validator(leader_result="failed") is False
    with direct_vm.expect_revert("already settled"):
        case.settle_payout(0, tx, fin)


def test_refund_settles(case, direct_vm, direct_charlie, chain):
    appeal(direct_vm, case, direct_charlie)
    direct_vm.warp("2030-01-05T10:00:00Z")
    case.expire_unresolved(0)
    tx, fin = chain.pay(case, 0, "expire_unresolved", [0])
    wrong, wrong_fin = chain.pay(case, 0, "decide", [0, URL, ""])  # a ruling did not pay this refund
    with direct_vm.expect_revert("did not create this payout"):
        case.settle_payout(0, wrong, wrong_fin)
    assert case.settle_payout(0, tx, fin) == "DELIVERED"


def test_failed_overturn_is_recoverable_and_recovery_settles_too(case, direct_vm, direct_charlie, chain, ledger):
    overturned(case, direct_vm, direct_charlie)
    tx, fin = chain.pay(case, 0, "decide", DECIDE, delivered=False)
    assert case.settle_payout(0, tx, fin) == "FAILED"
    assert case.get_recoverable(to_hex(direct_charlie)) == BOND + REWARD
    assert case.get_accounting()["expected_balance"] == POOL + BOND
    tick(direct_vm)
    direct_vm.sender = direct_charlie
    assert case.recover(OTHER) == BOND + REWARD
    assert ledger.paid_to(OTHER) == BOND + REWARD
    with direct_vm.expect_revert("nothing to recover"):
        case.recover(OTHER)
    tx2, fin2 = chain.pay(case, 1, "recover", [OTHER], delivered=False)
    assert case.settle_payout(1, tx2, fin2) == "FAILED"
    assert case.get_recoverable(to_hex(direct_charlie)) == BOND + REWARD


def test_failed_withdraw_goes_back_to_the_owner(case, direct_vm, direct_alice, chain):
    direct_vm.sender = direct_alice
    case.withdraw_pool(0, REWARD)
    tx, fin = chain.pay(case, 0, "withdraw_pool", [0, REWARD], delivered=False)
    assert case.settle_payout(0, tx, fin) == "FAILED"
    assert case.get_recoverable(to_hex(direct_alice)) == REWARD


def test_withdraw_amount_is_bound_to_the_transaction(case, direct_vm, direct_alice, chain):
    direct_vm.sender = direct_alice
    case.withdraw_pool(0, REWARD)
    tx, fin = chain.pay(case, 0, "withdraw_pool", [0, REWARD - 1], delivered=False)
    with direct_vm.expect_revert("did not create this payout"):
        case.settle_payout(0, tx, fin)


@pytest.mark.parametrize(
    "kw,err",
    [
        ({"method": "release", "args": [0]}, "did not create this payout"),
        ({"method": "expire_unresolved", "args": [0]}, "did not create this payout"),
        ({"args": [1, URL, STATEMENT]}, "did not create this payout"),
        ({"sender": "0x" + "99" * 20}, "did not create this payout"),
        ({"at": 1}, "did not create this payout"),
        ({"result": 2}, "did not create this payout"),
        ({"status": 5}, "not finalized yet"),  # accepted but not finalized
        # same sender, second, method and id, but it sent nothing (a call that did not pay)
        ({"delivered": None}, "did not create this payout"),
    ],
)
def test_settle_rejects_a_transaction_that_is_not_this_payout(kw, err, case, direct_vm, direct_charlie, chain):
    overturned(case, direct_vm, direct_charlie)
    method, args = kw.pop("method", "decide"), kw.pop("args", DECIDE)
    tx, fin = chain.pay(case, 0, method, args, **{"delivered": False, **kw})
    with direct_vm.expect_revert(err):
        case.settle_payout(0, tx, fin)
    assert case.get_payout(0)["status"] == "SENT"


def test_settle_needs_the_finalization_of_that_transaction(case, direct_vm, direct_charlie, chain):
    overturned(case, direct_vm, direct_charlie)
    tx, _ = chain.pay(case, 0, "decide", DECIDE, delivered=False)
    _, other_fin = chain.pay(case, 0, "decide", DECIDE)
    with direct_vm.expect_revert("not the finalization"):
        case.settle_payout(0, tx, other_fin)
    with direct_vm.expect_revert("not found"):
        case.settle_payout(0, tx, "0x" + "ab" * 32)
    with direct_vm.expect_revert("0x + 64 hex"):
        case.settle_payout(0, tx, "latest")
    chain.down = True
    with direct_vm.expect_revert("RPC unavailable"):
        case.settle_payout(0, tx, other_fin)


def test_one_paying_transaction_settles_one_payout_and_one_payment_per_second(case, direct_vm, direct_alice, chain):
    direct_vm.sender = direct_alice
    case.withdraw_pool(0, 1)
    with direct_vm.expect_revert("one payment per sender per second"):
        case.withdraw_pool(0, 1)
    tick(direct_vm)
    case.withdraw_pool(0, 1)
    tx, fin = chain.pay(case, 0, "withdraw_pool", [0, 1])
    assert case.settle_payout(0, tx, fin) == "DELIVERED"
    with direct_vm.expect_revert("already settled a payout"):
        case.settle_payout(1, tx, fin)
