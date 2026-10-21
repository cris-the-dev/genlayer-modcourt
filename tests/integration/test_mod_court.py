"""Integration test against Testnet Bradbury, on the packed code that is deployed:

    python deploy/shrink.py contracts/mod_court.py build/mod_court.py --pack
    cd tests/integration && gltest . -v -s --network testnet_bradbury   # config in this folder

The member signs commitments to two posts hosted at EVIDENCE (byte for byte
the FINE and SPAM texts below). A forged signature and a disproportionate
action are rejected; one appeal is overturned after two failed rulings (the
original is unavailable, then a different post sits at the URL) that leave it
waiting; one is upheld and its bond goes to the bond fund; the owner withdraws
the free pool; both payouts are found as unsettled and settled from their own
transfers once the paying transactions finalize.

The 3-day expiry needs a clock this test cannot move; Direct Mode covers it.
"""

import hashlib
import json
import os
from pathlib import Path

import pytest
from dotenv import dotenv_values
from eth_account import Account
from eth_account.messages import encode_defunct
from gltest import get_accounts

from .bradbury import deploy, ok, reverted, send, settle, view

BOND, REWARD = 5 * 10**14, 10**15
RULES = [
    {"text": "No personal attacks or insults aimed at other members", "max_action": "ban"},
    {"text": "No spam or unsolicited advertising", "max_action": "remove"},
    {"text": "Stay on topic: posts must be about GenLayer", "max_action": "remove"},
]
FINE = "Has anyone benchmarked Bradbury finality? My GenLayer contract takes about 40 seconds to finalize."
SPAM = "BUY CHEAP FOLLOWERS NOW at cheap-followers.example, 50% off today only, DM me!!!"
EVIDENCE = "https://modcourt.cristhedev.com/evidence/"
SLOW = {"wait_interval": 10_000, "wait_retries": 60}


def sha(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


def member_key() -> str:
    return os.environ.get("GL_PK1") or dotenv_values(Path(__file__).with_name(".env"))["GL_PK1"]


def sign(c, text: str, key: str) -> str:
    """The member's personal_sign of the commitment, exactly as a wallet makes it."""
    msg = view(c, "get_commitment", [0, sha(text)])
    return "0x" + Account.sign_message(encode_defunct(text=msg), key).signature.hex().removeprefix("0x")


@pytest.mark.integration
def test_appeals_end_to_end():
    c = deploy("ModCourt", "mod_court.py")
    member = get_accounts()[1]
    key = member_key()
    assert Account.from_key(key).address.lower() == member.address.lower()
    ok(c.create_community(args=["GenLayer builders", json.dumps(RULES), BOND, REWARD]).transact(value=2 * REWARD))
    fine_sig, spam_sig = sign(c, FINE, key), sign(c, SPAM, key)

    # Provenance and proportionality are checked when the action is recorded.
    assert reverted(c.act(args=[0, member.address, sha(SPAM), fine_sig, 2, "remove"]).transact())  # signature for another post
    assert reverted(c.act(args=[0, member.address, sha(SPAM), spam_sig, 2, "ban"]).transact())  # rule 2 allows at most remove
    ok(c.act(args=[0, member.address, sha(FINE), fine_sig, 3, "remove"]).transact())
    ok(c.act(args=[0, member.address, sha(SPAM), spam_sig, 2, "remove"]).transact())
    assert reverted(c.act(args=[0, member.address, sha(FINE), fine_sig, 1, "hide"]).transact())  # pool fully reserved

    as_member = c.connect(member)
    ok(as_member.appeal(args=[0]).transact(value=BOND))
    k = view(c, "get_case", [0])
    assert k["status"] == "APPEALED" and k["resolve_by"] == k["appealed_at"] + 3 * 86_400, k

    # Failed rulings revert and leave the appeal waiting.
    assert reverted(as_member.decide(args=[0, EVIDENCE + "missing.txt", "It is about GenLayer."]).transact(**SLOW))
    assert reverted(as_member.decide(args=[0, EVIDENCE + "spam.txt", "It is about GenLayer."]).transact(**SLOW))
    assert view(c, "get_case", [0])["status"] == "APPEALED"
    paid = send(lambda: as_member.decide(args=[0, EVIDENCE + "fine.txt", "It is a question about GenLayer's testnet."]).transact(**SLOW))
    k = view(c, "get_case", [0])
    assert k["status"] == "OVERTURNED" and k["cited_rule_violated"] is False, k
    assert "content" not in k and "statement" not in k

    ok(as_member.appeal(args=[1]).transact(value=BOND))
    send(lambda: as_member.decide(args=[1, EVIDENCE + "spam.txt", "Just sharing a deal."]).transact(**SLOW))
    k = view(c, "get_case", [1])
    assert k["status"] == "UPHELD" and k["cited_rule_violated"] is True, k
    print("case 0 explanation (unverified):", view(c, "get_case", [0])["explanation_unverified"])
    print("case 1 explanation (unverified):", k["explanation_unverified"])

    # The overturn was paid from the pool (the bond fund was empty); the upheld bond stays out of the owner's reach.
    com = view(c, "get_community", [0])
    assert (com["reserved"], com["pool"], com["bond_fund"], com["withdrawable"]) == (0, REWARD, BOND, REWARD), com
    assert view(c, "get_moderator_stats", [0, get_accounts()[0].address]) == {"actions": 2, "appeals": 2, "overturned": 1}
    withdrawn = ok(c.withdraw_pool(args=[0, REWARD]).transact())

    unsettled = view(c, "get_payouts", [0, 50, True])
    assert [(p["id"], p["kind"]) for p in unsettled["items"]] == [(0, "overturn"), (1, "withdraw")], unsettled
    assert unsettled["items"][0]["amount"] == BOND + REWARD and unsettled["items"][0]["to"].lower() == member.address.lower()
    settle(c, 0, paid)
    settle(c, 1, withdrawn)
    assert view(c, "get_payouts", [0, 50, True])["items"] == []
    # Once the transfers have left, the balance matches what the contract expects to hold.
    assert view(c, "get_accounting")["unaccounted"] == 0
