"""Synthetic HWID generator for ZenCraft.

Replicates the shape produced by the official launcher (oshi-based, see aq.java):
a LinkedHashSet<String> serialized as a JSON array. Values here are fully
synthetic, derived from a random local seed - NO real hardware is ever read.
The seed is persisted per profile so the HWID stays stable across logins.
"""

import hashlib
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


def build_hwid(seed: str) -> list[str]:
    """Build the synthetic HWID set (ordered, like the original LinkedHashSet).

    Fully derived from `seed`: a different seed gives a different, stable
    identity. The seed is random per install and persisted (see zencli.py), so
    every user/account gets its own synthetic HWID and NOTHING is hardcoded in
    the repo. The set is internally consistent, which is all the server needs -
    it is not required to match the machine the account was registered on.
    Order matches aq.java: hardware-uuid hash, computer/baseboard/disk/memory.
    """
    return [
        _derive(seed, "hardware-uuid", 64),  # 64-hex, no prefix
        f"computer-serial-number:{_serial(seed, 'computer')}",
        f"baseboard-serial-number:{_serial(seed, 'baseboard')}",
        f"disk-serial-number:{_serial(seed, 'disk', 16)}",
        f"memory-serial-number:{_serial(seed, 'memory')}",
    ]


if __name__ == "__main__":
    import json

    s = new_seed()
    print("seed:", s)
    print(json.dumps(build_hwid(s), indent=2))
