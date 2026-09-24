import pytest

from notice_monitor.triage import AUTOMATED, HUMAN, classify


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("CITACAO", AUTOMATED),
        ("NOTIFICACAO", AUTOMATED),
        ("citacao", AUTOMATED),  # case-insensitive
        (" NOTIFICACAO ", AUTOMATED),  # whitespace-tolerant
        ("INTIMACAO", HUMAN),
        ("VISTA", HUMAN),
        ("IPTA", HUMAN),
        ("BRAND_NEW_UNKNOWN_TYPE", HUMAN),  # unknown is NEVER automated
        ("", HUMAN),
        (None, HUMAN),
    ],
)
def test_classify(kind, expected):
    assert classify(kind) == expected
