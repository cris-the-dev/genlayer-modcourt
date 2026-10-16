"""Community, moderation actions, appeals and the reward pool."""

import json

import pytest

from tests.direct.conftest import BOND, CONTENT, POOL, REWARD, RULES, appeal, chain_balance, sha, tick, to_hex


def test_create(mc, direct_alice, direct_bob, direct_charlie):
    c = mc.get_community(0)
    assert c["owner"].lower() == to_hex(direct_alice).lower() and c["rules"] == RULES
    assert c["pool"] == POOL and c["free"] == POOL and c["appeal_bond"] == BOND
    assert mc.is_moderator(0, to_hex(direct_alice)) and mc.is_moderator(0, to_hex(direct_bob))
    assert not mc.is_moderator(0, to_hex(direct_charlie))


@pytest.mark.parametrize(
    "name, rules, bond, reward, msg",
    [
        ("Ok name", "not json", BOND, REWARD, "JSON list"),
        ("Ok name", json.dumps([]), BOND, REWARD, "1-20 rules"),
        ("Ok name", json.dumps(["rule"]), BOND, REWARD, "1-20 rules"),
        ("Ok name", json.dumps(["A good rule"] * 21), BOND, REWARD, "1-20 rules"),
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
        mc.act(0, to_hex(direct_bob), sha("x"), 1, "remove")


@pytest.mark.parametrize(
    "sha_, rule, action, msg",
    [("abc", 1, "remove", "64 hex"), (sha("x"), 0, "remove", "no such rule"), (sha("x"), 4, "remove", "no such rule"), (sha("x"), 1, "delete", "action must be")],
)
def test_act_validation(mc, direct_vm, direct_bob, direct_charlie, sha_, rule, action, msg):
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert(msg):
        mc.act(0, to_hex(direct_charlie), sha_, rule, action)


def test_act_reserves_the_reward_and_stops_when_the_pool_is_out(mc, direct_vm, direct_alice, direct_bob, direct_charlie):
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("cannot moderate yourself"):
        mc.act(0, to_hex(direct_bob), sha("x"), 1, "remove")
    mc.act(0, to_hex(direct_charlie), "0x" + sha("a").upper(), 1, "hide")
    mc.act(0, to_hex(direct_charlie), sha("b"), 2, "mute")
    assert mc.get_community(0)["free"] == 0 and mc.get_case(0)["content_sha256"] == sha("a")
    with direct_vm.expect_revert("reward pool exhausted"):
        mc.act(0, to_hex(direct_charlie), sha("c"), 2, "ban")
    direct_vm.sender = direct_alice
    direct_vm.value = REWARD
    mc.fund(0)
    direct_vm.value = 0
    direct_vm.sender = direct_bob
    mc.act(0, to_hex(direct_charlie), sha("c"), 2, "ban")
    assert mc.get_moderator_stats(0, to_hex(direct_bob)) == {"actions": 3, "appeals": 0, "overturned": 0}
    assert [k["id"] for k in mc.get_cases(0)] == [0, 1, 2]


def test_overturned_pays_bond_and_reward(case, direct_vm, direct_bob, direct_charlie, ledger):
    r = appeal(direct_vm, case, direct_charlie, violated=())
    assert r["status"] == "OVERTURNED" and r["violated"] == []
    assert ledger.paid_to(direct_charlie) == BOND + REWARD
    c = case.get_community(0)
    assert c["pool"] == POOL - REWARD and c["reserved"] == 0
    k = case.get_case(0)
    assert k["content"] == CONTENT and k["reason"] == "ruled"
    assert case.get_moderator_stats(0, to_hex(direct_bob)) == {"actions": 1, "appeals": 1, "overturned": 1}


def test_upheld_keeps_the_bond(case, direct_vm, direct_bob, direct_charlie, ledger):
    r = appeal(direct_vm, case, direct_charlie, violated=(1, 3, 3))
    assert r["status"] == "UPHELD" and r["violated"] == [1, 3]
    assert ledger.transfers == []
    c = case.get_community(0)
    assert c["pool"] == POOL + BOND and c["reserved"] == 0
    assert case.get_moderator_stats(0, to_hex(direct_bob))["overturned"] == 0


def test_appeal_guards(case, direct_vm, direct_bob, direct_charlie):
    with direct_vm.expect_revert("only the affected user"):
        appeal(direct_vm, case, direct_bob)
    with direct_vm.expect_revert("exactly the appeal bond"):
        appeal(direct_vm, case, direct_charlie, value=BOND - 1)
    with direct_vm.expect_revert("does not match the moderator's record"):
        appeal(direct_vm, case, direct_charlie, content=CONTENT + " (edited)")
    with direct_vm.expect_revert("up to 4000"):
        appeal(direct_vm, case, direct_charlie, content="x" * 4001)
    appeal(direct_vm, case, direct_charlie)
    with direct_vm.expect_revert("appeal window closed"):
        appeal(direct_vm, case, direct_charlie)


def test_window_release_and_late_appeal(case, direct_vm, direct_alice, direct_charlie):
    with direct_vm.expect_revert("still open for appeal"):
        case.release(0)
    direct_vm.warp("2030-01-08T10:00:01Z")
    with direct_vm.expect_revert("appeal window closed"):
        appeal(direct_vm, case, direct_charlie)
    case.release(0)
    assert case.get_case(0)["status"] == "FINAL" and case.get_community(0)["reserved"] == 0
    with direct_vm.expect_revert("still open for appeal"):
        case.release(0)


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


def test_delivered_overturn_settles(case, direct_vm, direct_charlie, direct_bob, chain):
    appeal(direct_vm, case, direct_charlie)
    tx, fin = chain.pay(case, 0, "appeal", [0, CONTENT, "s"])
    direct_vm.sender = direct_bob
    assert case.settle_payout(0, tx, fin) == "DELIVERED"
    assert case.get_payout(0)["tx"] == tx and case.get_payout(0)["ref"] == 0
    assert case.get_recoverable(to_hex(direct_charlie)) == 0
    assert direct_vm.run_validator(leader_result="failed") is False
    with direct_vm.expect_revert("already settled"):
        case.settle_payout(0, tx, fin)


def test_failed_overturn_is_recoverable_and_recovery_settles_too(case, direct_vm, direct_charlie, chain, ledger):
    appeal(direct_vm, case, direct_charlie)
    tx, fin = chain.pay(case, 0, "appeal", [0, CONTENT, "s"], delivered=False)
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
        ({"args": [1, CONTENT, "s"]}, "did not create this payout"),
        ({"sender": "0x" + "99" * 20}, "did not create this payout"),
        ({"at": 1}, "did not create this payout"),
        ({"result": 2}, "did not create this payout"),
        ({"status": 5}, "not finalized yet"),
        # same sender, second, method and id, but it sent nothing (a call that did not pay)
        ({"delivered": None}, "did not create this payout"),
    ],
)
def test_settle_rejects_a_transaction_that_is_not_this_payout(kw, err, case, direct_vm, direct_charlie, chain):
    appeal(direct_vm, case, direct_charlie)
    method, args = kw.pop("method", "appeal"), kw.pop("args", [0, CONTENT, "s"])
    tx, fin = chain.pay(case, 0, method, args, **{"delivered": False, **kw})
    with direct_vm.expect_revert(err):
        case.settle_payout(0, tx, fin)
    assert case.get_payout(0)["status"] == "SENT"


def test_settle_needs_the_finalization_of_that_transaction(case, direct_vm, direct_charlie, chain):
    appeal(direct_vm, case, direct_charlie)
    tx, _ = chain.pay(case, 0, "appeal", [0, CONTENT, "s"], delivered=False)
    _, other_fin = chain.pay(case, 0, "appeal", [0, CONTENT, "s"])
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
