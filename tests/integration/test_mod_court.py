"""Integration test against Testnet Bradbury, on the packed code that is deployed:

    python deploy/shrink.py contracts/mod_court.py build/mod_court.py --pack
    cd tests/integration && gltest . -v -s --network testnet_bradbury   # config in this folder

One appeal overturned (bond + reward to the member), one upheld (the bond
stays in the pool), then the owner withdraws the kept bond; both payouts are
settled from their own transfers once the paying transactions finalize.
"""

import hashlib
import json

import pytest
from gltest import get_accounts

from .bradbury import deploy, ok, reverted, send, settle, view

BOND, REWARD = 5 * 10**14, 10**15
RULES = ["No personal attacks or insults aimed at other members", "No spam or unsolicited advertising", "Stay on topic: posts must be about GenLayer"]
FINE = "Has anyone benchmarked Bradbury finality? My GenLayer contract takes about 40 seconds to finalize."
SPAM = "BUY CHEAP FOLLOWERS NOW at cheap-followers.example, 50% off today only, DM me!!!"


def sha(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


@pytest.mark.integration
def test_overturned_and_upheld():
    c = deploy("ModCourt", "mod_court.py")
    member = get_accounts()[1]
    ok(c.create_community(args=["GenLayer builders", json.dumps(RULES), BOND, REWARD]).transact(value=2 * REWARD))
    ok(c.act(args=[0, member.address, sha(FINE), 3, "remove"]).transact())
    ok(c.act(args=[0, member.address, sha(SPAM), 2, "remove"]).transact())
    assert reverted(c.act(args=[0, member.address, sha("x"), 1, "hide"]).transact())  # pool fully reserved

    as_member = c.connect(member)
    paid = send(lambda: as_member.appeal(args=[0, FINE, "It is a question about GenLayer's testnet."]).transact(value=BOND, wait_interval=10_000, wait_retries=60))
    assert view(c, "get_case", [0])["status"] == "OVERTURNED"
    send(lambda: as_member.appeal(args=[1, SPAM, "Just sharing a deal."]).transact(value=BOND, wait_interval=10_000, wait_retries=60))
    assert view(c, "get_case", [1])["status"] == "UPHELD"
    com = view(c, "get_community", [0])
    assert com["reserved"] == 0 and com["pool"] == REWARD + BOND, com
    withdrawn = ok(c.withdraw_pool(args=[0, BOND]).transact())

    p = view(c, "get_payout", [0])
    assert p["kind"] == "overturn" and p["to"].lower() == member.address.lower() and p["amount"] == BOND + REWARD, p
    assert view(c, "get_payout", [1])["kind"] == "withdraw"
    settle(c, 0, paid)
    settle(c, 1, withdrawn)
    # Once the transfers have left, the balance matches what the contract expects to hold.
    assert view(c, "get_accounting")["unaccounted"] == 0
