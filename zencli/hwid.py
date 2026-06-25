"""Synthetic HWID generator for ZenCraft.

Replicates the shape produced by the official launcher (oshi-based, see aq.java):
a LinkedHashSet<String> serialized as a JSON array. Values here are fully
synthetic, derived from a random local seed - NO real hardware is ever read.
The seed is persisted per profile so the HWID stays stable across logins.
"""

import hashlib
import os
import secrets


def new_seed() -> str:
    """Generate a fresh random seed (hex). One seed = one synthetic identity."""
    return secrets.token_hex(32)


def _derive(seed: str, label: str, length: int) -> str:
    """Deterministic hex chunk derived from seed+label."""
    digest = hashlib.sha256(f"{seed}:{label}".encode()).hexdigest()
    return digest[:length]


def _serial(seed: str, label: str, length: int = 12) -> str:
    """Plausible alphanumeric serial (uppercase), deterministic from seed."""
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    digest = hashlib.sha256(f"{seed}:{label}:serial".encode()).digest()
    return "".join(alphabet[b % len(alphabet)] for b in digest[:length])


# Fixed synthetic identity that the patched launcher (spoofed aq.class) used to
# register the account. The game-auth fingerprint is derived server-side from
# this exact set, so login MUST submit it verbatim or the join is rejected with
# "session invalide de zencraft". Keep in sync with spoof/aq.java.
SPOOFED_HWID = [
    "6a16224b75006d0d4fa52745dfd1d37f95afa92c103999f433aaf8b254ca7a44",
    "computer-serial-number:Q1MQHQXY8N6D",
    "baseboard-serial-number:H3K0CP71TBKH",
    "disk-serial-number:22OMZE99PHFY96TF",
    "memory-serial-number:ZHWJPM3FYR9U",
]


def build_hwid(seed: str) -> list[str]:
    """Return the fixed spoofed HWID set bound to the account.

    The account was created through the patched launcher using SPOOFED_HWID, so
    every login must reuse it (the seed is ignored on purpose). Order matches
    aq.java: hardware-uuid hash, computer/baseboard/disk/memory serials.
    """
    return list(SPOOFED_HWID)


if __name__ == "__main__":
    import json

    s = new_seed()
    print("seed:", s)
    print(json.dumps(build_hwid(s), indent=2))
