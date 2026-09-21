from __future__ import annotations


def score_case(actual: dict, expected: dict) -> tuple[bool, float, dict]:
    checks = {}
    for key, expected_value in expected.items():
        value = actual.get(key)
        if isinstance(expected_value, list):
            checks[key] = all(item in value if isinstance(value, list) else False for item in expected_value)
        else:
            checks[key] = value == expected_value
    passed = sum(bool(v) for v in checks.values())
    total = len(checks) or 1
    score = round(passed / total * 100, 2)
    return passed == total, score, checks
