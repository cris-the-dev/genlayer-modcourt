"""Fixtures for ModCourt direct-mode tests."""

import hashlib
import json
from datetime import datetime, timedelta

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct

GEN = 10**18
BOND = GEN // 10
REWARD = GEN // 5
POOL = 2 * REWARD  # room for exactly two open actions
RULES = ["No personal attacks or insults aimed at other members", "No spam or unsolicited advertising", "Stay on topic: posts must be about GenLayer"]
CONTENT = "Has anyone benchmarked the Bradbury validators? My contract takes 40s to finalize."
STATEMENT = "It is about Bradbury, which is GenLayer."
URL = "https://member.example/post-0.txt"
LLM = r"independent appeals panel"
# Charlie posts and signs; the other members only need addresses.
CHARLIE = Account.from_key("0x" + "c4" * 32)
MALLORY = Account.from_key("0x" + "4d" * 32)


def to_hex(addr) -> str:
    if hasattr(addr, "as_hex"):
        return addr.as_hex
    from genlayer.py.types import Address

    return Address(addr).as_hex


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sign(vm, sha_, signer=CHARLIE, community_id=0, contract=None) -> str:
    """`signer`'s personal_sign of the commitment to a post, as a wallet produces it."""
    text = f"ModCourt content commitment\ncontract: {(contract or to_hex(vm._contract_address)).lower()}\ncommunity: {community_id}\nsha256: {sha_}"
    return "0x" + Account.sign_message(encode_defunct(text=text), signer.key).signature.hex().removeprefix("0x")


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


def tick(vm, seconds=1):
    t = datetime.fromisoformat(vm._datetime.replace("Z", "+00:00")) + timedelta(seconds=seconds)
    vm.warp(t.strftime("%Y-%m-%dT%H:%M:%SZ"))


@pytest.fixture
def direct_charlie():
    from genlayer.py.types import Address

    return Address(CHARLIE.address)


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


def act(vm, c, content=CONTENT, rule=3, action="remove", signer=CHARLIE, target=None, sig=None):
    return c.act(0, target or signer.address, sha(content), sign(vm, sha(content), signer) if sig is None else sig, rule, action)


@pytest.fixture
def case(mc, direct_vm, direct_bob):
    """Case 0: Bob removes Charlie's signed post citing rule 3."""
    direct_vm.sender = direct_bob
    act(direct_vm, mc)
    return mc


def ruling(vm, violated=False, reason="ruled", body=CONTENT, status=200):
    """The member's copy at URL and the LLM's answer, for leader and validators."""
    vm.clear_mocks()
    vm.mock_web(r"member\.example", {"status": status, "body": body})
    vm.mock_llm(LLM, json.dumps({"violated": violated, "reason": reason}))


def appeal(vm, c, who, case_id=0, value=BOND):
    vm.sender = who
    vm.value = value
    try:
        return c.appeal(case_id)
    finally:
        vm.value = 0


def decide(vm, c, who, violated=False, body=CONTENT, statement=STATEMENT, case_id=0, url=URL, status=200):
    ruling(vm, violated, body=body, status=status)
    vm.sender = who
    chain_balance(vm, POOL + BOND)
    return c.decide(case_id, url, statement)


# ── Fake Bradbury RPC for settle_payout ─────────────────────────────────────

CONSENSUS_MAIN = "0x0112bf6e83497965a5fdd6dad1e447a6e004271d"
MESSAGES = "0x27872802226532fcd7fea2f00addbffbd3380ade"
T_FINALIZED = "0x24196ec40f90671b7144e716978686b4f3c7d6b00b23da3971ef2b52af27d87f"
T_EXECUTED = "0x4aacc1769103d0575734a31601a30d8f74c7843414f868342af438b4fdc4d78e"
T_MESSAGE = "0x1a2b93b175bf31d44b127b5c4c0f72cbf128f5230ad594a52a00dfa559c96b51"
T_MSG_FAILED = "0x5ae8e754fbc8b7b56c89e264bdcd8bb847036b23ac1a0f791f48b62438f2bab9"


def _rlp(item) -> bytes:
    def prefix(n, off):
        if n < 56:
            return bytes([off + n])
        b = n.to_bytes((n.bit_length() + 7) // 8, "big")
        return bytes([off + 55 + len(b)]) + b

    if isinstance(item, list):
        body = b"".join(_rlp(x) for x in item)
        return prefix(len(body), 0xC0) + body
    return item if len(item) == 1 and item[0] < 0x80 else prefix(len(item), 0x80) + item


def _pad(addr: str) -> str:
    return "0x" + addr.lower()[2:].rjust(64, "0")


class Chain:
    """Serves gen_getTransactionReceipt / eth_getTransactionReceipt like Bradbury,
    for paying transactions registered with `pay`."""

    def __init__(self, vm):
        self.vm = vm
        self.receipts = {}
        self.n = 0
        self.down = False

    def _hash(self):
        self.n += 1
        return "0x" + f"{self.n:064x}"

    def pay(self, c, payout_id, method, args, delivered=True, status=7, result=1, sender=None, at=None):
        """Record the paying transaction of `payout_id` and its finalization. Returns (tx, finalize_tx)."""
        from genlayer.py import calldata

        p = c.get_payout(payout_id)
        me = to_hex(self.vm._contract_address).lower()
        tx, fin = self._hash(), self._hash()
        self.receipts[("gen_getTransactionReceipt", tx)] = {
            "sender": (sender or p["sender"]).lower(),
            "recipient": me,
            "status": status,
            "txExecutionResult": result,
            "timestamps": {"Created": p["at"] if at is None else at},
            "txCallData": _rlp([calldata.encode({"method": method, "args": args}), b"\x00"]).hex(),
        }
        msg = "0x" + f"{self.n:064x}"
        logs = [
            {"address": CONSENSUS_MAIN, "topics": [T_FINALIZED, tx], "data": "0x"},
        ]
        if delivered:  # True: delivered; False: the transfer failed; None: the transaction sent nothing
            logs.append({"address": MESSAGES, "topics": [T_MESSAGE, tx, msg], "data": "0x"})
            logs.append({"address": me, "topics": [T_EXECUTED, _pad(p["to"])], "data": msg + "00" * 64})
        elif delivered is False:  # as on Bradbury: the messages contract's failure event, no MessagesOnFinalization
            logs.append({"address": MESSAGES, "topics": [T_MSG_FAILED, tx, msg], "data": "0x"})
        self.receipts[("eth_getTransactionReceipt", fin)] = {"status": "0x1", "to": CONSENSUS_MAIN, "logs": logs}
        return tx, fin

    def answer(self, data):
        body = data.get("body") or b""
        req = json.loads(body.decode() if isinstance(body, (bytes, bytearray)) else body)
        if self.down:
            return {"ok": {"response": {"status": 502, "headers": {}, "body": b"bad gateway"}}}
        params = req["params"][0]
        key = params["txId"] if isinstance(params, dict) else params
        out = {"jsonrpc": "2.0", "id": req["id"], "result": self.receipts.get((req["method"], key))}
        return {"ok": {"response": {"status": 200, "headers": {}, "body": json.dumps(out).encode()}}}


@pytest.fixture
def chain(direct_vm):
    import gltest.direct.wasi_mock as wm

    c = Chain(direct_vm)
    original = wm._handle_web_request

    def route(vm, data):
        if "rpc-bradbury" in data.get("url", ""):
            return c.answer(data)
        return original(vm, data)

    wm._handle_web_request = route
    yield c
    wm._handle_web_request = original
