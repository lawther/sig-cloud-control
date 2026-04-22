import inspect
import re
from pathlib import Path

import typer

import sig_cloud_control.cli_app
import sig_cloud_control.client

_TEST_DIR = Path(__file__).parent
_SRC_DIR = Path(__file__).parent.parent / "src"

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


def test_cli_app_api_surface_is_minimal() -> None:
    """Intention: The cli_app package should only ever expose the Typer application.

    It is an entry point, not a library. Any other symbols (config, actions, etc.)
    should be kept in their respective submodules.
    """
    exports = sig_cloud_control.cli_app.__all__
    assert len(exports) == 1, f"cli_app should only export 1 symbol, found: {exports}"

    app_name = exports[0]
    app_obj = getattr(sig_cloud_control.cli_app, app_name)
    assert isinstance(app_obj, typer.Typer), f"cli_app export '{app_name}' must be a Typer app"


def test_cli_app_does_not_import_client_submodules() -> None:
    """Intention: cli_app must only consume the public sig_cloud_control.client facade.

    Importing from sig_cloud_control.client.<submodule> directly couples cli_app to
    internal implementation details and breaks the facade contract.
    """
    # Matches any direct import from a client submodule, e.g.:
    #   from sig_cloud_control.client.encryption import ...
    #   import sig_cloud_control.client.core
    _client_submodule_import = re.compile(r"sig_cloud_control\.client\.\w+")

    cli_app_dir = _SRC_DIR / "sig_cloud_control" / "cli_app"
    violations: list[str] = []
    for path in sorted(cli_app_dir.glob("*.py")):
        for i, line in enumerate(path.read_text().splitlines(), start=1):
            if _client_submodule_import.search(line):
                violations.append(f"{path.name}:{i}: {line.strip()}")

    assert not violations, (
        "cli_app must only import from sig_cloud_control.client (the public facade), "
        "not from its internal submodules:\n" + "\n".join(violations)
    )


def test_public_api_facades_do_not_leak_internals() -> None:
    """Intention: Root __init__.py files should be clean facades.

    They must not leak submodules, internal names (starting with '_'), or
    non-explicitly exported symbols.
    """
    for module in [sig_cloud_control.client, sig_cloud_control.cli_app]:
        # 1. Every exported symbol must be explicitly listed in __all__
        assert hasattr(module, "__all__"), f"Module {module.__name__} is missing __all__"

        for name in module.__all__:
            # 2. No internal names should be exported
            assert not name.startswith("_"), f"Internal symbol '{name}' leaked in {module.__name__}.__all__"

            attr = getattr(module, name)

            # 3. Facades should export types or functions, not the submodules they were imported from.
            # (Leaking a module like 'sig_cloud_control.client.core' is a common refactoring bug.)
            assert not inspect.ismodule(attr), f"Submodule '{name}' leaked in {module.__name__}.__all__"

            # 4. Check that everything in __all__ actually exists in the module
            assert hasattr(module, name), f"Symbol '{name}' listed in {module.__name__}.__all__ but not found"
