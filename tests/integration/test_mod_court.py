"""Integration test against Testnet Bradbury, on the packed code that is deployed:

    python deploy/shrink.py contracts/mod_court.py build/mod_court.py --pack
    cd tests/integration && gltest . -v -s --network testnet_bradbury   # config in this folder
"""

import hashlib
import json

import pytest
from gltest import get_accounts, get_contract_factory
from gltest.assertions import tx_execution_failed, tx_execution_succeeded

BOND, REWARD = 5 * 10**14, 10**15
RULES = ["No personal attacks or insults aimed at other members", "No spam or unsolicited advertising", "Stay on topic: posts must be about GenLayer"]
FINE = "Has anyone benchmarked Bradbury finality? My GenLayer contract takes about 40 seconds to finalize."
SPAM = "BUY CHEAP FOLLOWERS NOW at cheap-followers.example, 50% off today only, DM me!!!"


def sha(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


@pytest.mark.integration
def test_overturned_and_upheld():
    c = get_contract_factory("ModCourt").deploy(args=[])
    member = get_accounts()[1]
    assert tx_execution_succeeded(c.create_community(args=["GenLayer builders", json.dumps(RULES), BOND, REWARD]).transact(value=2 * REWARD))
    assert tx_execution_succeeded(c.act(args=[0, member.address, sha(FINE), 3, "remove"]).transact())
    assert tx_execution_succeeded(c.act(args=[0, member.address, sha(SPAM), 2, "remove"]).transact())
    assert tx_execution_failed(c.act(args=[0, member.address, sha("x"), 1, "hide"]).transact())  # pool fully reserved

    as_member = c.connect(member)
    assert tx_execution_succeeded(as_member.appeal(args=[0, FINE, "It is a question about GenLayer's testnet."]).transact(value=BOND))
    assert c.get_case(args=[0]).call()["status"] == "OVERTURNED"
    assert tx_execution_succeeded(as_member.appeal(args=[1, SPAM, "Just sharing a deal."]).transact(value=BOND))
    assert c.get_case(args=[1]).call()["status"] == "UPHELD"
    assert c.get_community(args=[0]).call()["reserved"] == 0
    assert c.get_accounting(args=[]).call()["unaccounted"] == 0
