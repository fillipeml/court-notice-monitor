"""Synthetic identifiers for tests: CNJ-shaped case numbers with an invalid check digit."""


def case_number(
    seq: int, year: int = 2026, segment: str = "8", court: str = "26", unit: str = "0001"
) -> str:
    n = f"{seq:07d}"
    base = int(f"{n}{year}{segment}{court}{unit}00")
    dd = (98 - (base % 97) + 1) % 100  # valid value + 1 -> invalid by construction
    return f"{n}-{dd:02d}.{year}.{segment}.{court}.{unit}"
