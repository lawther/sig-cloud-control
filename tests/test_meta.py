import re
from pathlib import Path

_TEST_DIR = Path(__file__).parent

# Matches assignments to sys.modules, e.g. sys.modules["foo"] = MagicMock()
# This pattern is used to paper over missing dependencies rather than fixing them.
_SYS_MODULES_PATCH = re.compile(r"sys\.modules\[.+\]\s*=")


def test_no_sys_modules_patching() -> None:
    # Regression: AI agents have previously papered over missing dependencies by
    # injecting fake modules into sys.modules at import time rather than fixing
    # the root cause (e.g. adding the missing package to the right dependency group).
    violations: list[str] = []
    for path in sorted(_TEST_DIR.glob("*.py")):
        if path.name == Path(__file__).name:
            continue
        for i, line in enumerate(path.read_text().splitlines(), start=1):
            if _SYS_MODULES_PATCH.search(line):
                violations.append(f"{path.name}:{i}: {line.strip()}")

    assert not violations, "sys.modules patching found in tests — fix the missing dependency instead:\n" + "\n".join(
        violations
    )
