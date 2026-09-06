import json
from pathlib import Path
import pytest
from backend.temporal import resolve
from backend.db import DEFAULTS

CASES = json.loads(
    (Path(__file__).resolve().parents[1] / "benchmarks/temporal_cases.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize(
    "case", CASES, ids=[str(i + 1) + " " + c["text"] for i, c in enumerate(CASES)]
)
def test_ground_truth(case):
    result = resolve(
        case["text"],
        "2026-09-03T10:00:00+05:00",
        {**DEFAULTS, **case.get("settings", {})},
    )
    if case.get("review"):
        assert result["warnings"]
    for field in ["start", "end", "rrule"]:
        if field in case:
            assert result[field] and result[field].startswith(case[field]), result
