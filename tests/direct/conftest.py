"""Fixtures for ModCourt direct-mode tests."""

import hashlib
import json

import pytest

GEN = 10**18
BOND = GEN // 10
REWARD = GEN // 5
POOL = 2 * REWARD  # room for exactly two open actions
RULES = ["No personal attacks or insults aimed at other members", "No spam or unsolicited advertising", "Stay on topic: posts must be about GenLayer"]
CONTENT = "Has anyone benchmarked the Bradbury validators? My contract takes 40s to finalize."
LLM = r"independent appeals panel"


def to_hex(addr) -> str:
    if hasattr(addr, "as_hex"):
        return addr.as_hex
    from genlayer.py.types import Address

    return Address(addr).as_hex


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Ledger:
    def __init__(self):
        self.transfers = []

    def paid_to(self, addr) -> int:
        h = to_hex(addr).lower()
        return sum(v for a, v in self.transfers if a.lower() == h)


@pytest.fixture
def ledger():
    import gltest.direct.wasi_mock as wm

    book = Ledger()
    original = wm._handle_gl_call

    def spy(vm, request):
        if isinstance(request, dict) and "EthSend" in request:
            r = request["EthSend"]
            book.transfers.append((to_hex(r["address"]), int(r["value"])))
        return original(vm, request)

    wm._handle_gl_call = spy
    yield book
    wm._handle_gl_call = original


def chain_balance(vm, amount):
    """The mock never moves value, so tests set the contract's balance as the chain would show it."""
    vm.deal(vm._contract_address, amount)


@pytest.fixture
def mc(direct_vm, direct_deploy, direct_alice, direct_bob):
    """Community 0 owned by Alice, Bob is a moderator."""
    direct_vm.warp("2030-01-01T10:00:00Z")
    c = direct_deploy("contracts/mod_court.py")
    direct_vm.sender = direct_alice
    direct_vm.value = POOL
    c.create_community("GenLayer builders", json.dumps(RULES), BOND, REWARD)
    direct_vm.value = 0
    c.set_moderator(0, to_hex(direct_bob), True)
    chain_balance(direct_vm, POOL)
    return c


@pytest.fixture
def case(mc, direct_vm, direct_bob, direct_charlie):
    """Case 0: Bob removes Charlie's post citing rule 3."""
    direct_vm.sender = direct_bob
    mc.act(0, to_hex(direct_charlie), sha(CONTENT), 3, "remove")
    return mc


def ruling(vm, violated=(), reason="ruled"):
    vm.clear_mocks()
    vm.mock_llm(LLM, json.dumps({"violated": list(violated), "reason": reason}))


def appeal(vm, c, who, violated=(), content=CONTENT, statement="It is about Bradbury, which is GenLayer.", case_id=0, value=BOND):
    ruling(vm, violated)
    vm.sender = who
    vm.value = value
    chain_balance(vm, POOL + value)
    try:
        return c.appeal(case_id, content, statement)
    finally:
        vm.value = 0
