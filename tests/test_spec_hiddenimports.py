"""Guard: modules imported by name at run time must be bundled by Imprint.spec.

PyInstaller follows only static imports. agents/recommendation_profiles.py
(import_module) and services/recommendations/catalog.py (__import__) pick
modules from a string, so a frozen build crashed at startup with
ModuleNotFoundError for agents.chat.recommendations. This test needs no
frozen build: it reads the spec and the dynamic-import targets.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = (ROOT / "Imprint.spec").read_text()


def _collected_packages() -> set[str]:
    """Packages the spec bundles whole: `for _pkg in (...)` + collect_submodules."""
    assert "collect_submodules(_pkg)" in SPEC
    m = re.search(r"for _pkg in \(([^)]*)\):\s*\n\s*hiddenimports \+= collect_submodules\(_pkg\)", SPEC)
    assert m, "spec lost its collect_submodules loop"
    return set(re.findall(r"[\"']([\w.]+)[\"']", m.group(1)))


def _covered(module: str, pkgs: set[str]) -> bool:
    return any(module == p or module.startswith(p + ".") for p in pkgs)


def test_every_agent_recommendation_module_is_covered():
    from agents.catalog import AGENT_SPECS
    pkgs = _collected_packages()
    targets = {s.recommendation_profile or f"agents.{s.key}.recommendations"
               for s in AGENT_SPECS}
    assert targets
    missing = sorted(t for t in targets if not _covered(t, pkgs))
    assert not missing, f"not bundled by Imprint.spec: {missing}"


def test_provider_client_modules_are_covered():
    src = (ROOT / "services/recommendations/catalog.py").read_text()
    mods = set(re.findall(r'\("(services\.\w+)",\s*"\w+"\)', src))
    assert mods
    pkgs = _collected_packages()
    missing = sorted(m for m in mods if not _covered(m, pkgs))
    assert not missing, f"not bundled by Imprint.spec: {missing}"


def test_no_new_dynamic_import_outside_known_files():
    """A new import_module/__import__ user must be added here and to the spec."""
    known = {"agents/recommendation_profiles.py",
             "services/recommendations/catalog.py", "main.py"}
    found = set()
    for top in ("agents", "services", "providers", "ui"):
        for f in (ROOT / top).rglob("*.py"):
            t = f.read_text()
            if re.search(r"\bimport_module\(|\b__import__\(", t):
                found.add(str(f.relative_to(ROOT)))
    assert found <= known, f"new dynamic import needs a spec entry: {sorted(found - known)}"


def test_bundle_version_is_derived_not_typed():
    assert "1.0.1" not in SPEC
    assert re.search(r'"CFBundleShortVersionString":\s*BUNDLE_VERSION', SPEC)
