"""Guard coverage for the release kit (spec SM6, slice-1 form), static.

In the style of tests/test_request_estimate.py: walk every module under
services/release_kit/ and ui/release_kit/. Any call that can reach a model,
a voice or the network must sit in a function that takes `grant: JobGrant`
and calls `grant.check()` before it. And a JobGrant is minted in exactly one
place: GodAI.authorize_job_item. The runtime half (every fake provider sees
an open job token) is in tests/test_release_kit_e2e.py.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIT_SOURCES = sorted([*(ROOT / "services" / "release_kit").glob("*.py"),
                      *(ROOT / "ui" / "release_kit").glob("*.py")])

GUARDED_NAMES = {"run_backend", "ChatWorker", "_new_chat_worker",
                 "ElevenLabsProvider", "get_voice_provider", "render_short",
                 "authorize_request", "QProcess"}
GUARDED_MODULES = {"requests", "httpx", "urllib", "socket"}


def _call_name(node: ast.Call) -> tuple[str, str]:
    func = node.func
    if isinstance(func, ast.Name):
        return "", func.id
    if isinstance(func, ast.Attribute):
        base = func.value
        root = base.id if isinstance(base, ast.Name) else ""
        return root, func.attr
    return "", ""


def _functions(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _takes_grant(fn) -> bool:
    for arg in [*fn.args.args, *fn.args.kwonlyargs]:
        if arg.arg == "grant" and isinstance(arg.annotation, ast.Name) \
                and arg.annotation.id == "JobGrant":
            return True
    return False


def _first_check_line(fn) -> int | None:
    lines = [n.lineno for n in ast.walk(fn) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == "check"
             and isinstance(n.func.value, ast.Name) and n.func.value.id == "grant"]
    return min(lines) if lines else None


def _guarded_calls(fn):
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            root, name = _call_name(node)
            if name in GUARDED_NAMES or root in GUARDED_MODULES:
                yield node, name or root


def test_the_walk_sees_the_kit_sources():
    names = {p.name for p in KIT_SOURCES}
    assert {"stages.py", "driver.py", "ledger.py", "grant.py"} <= names


def test_every_provider_call_holds_a_checked_job_grant():
    offenders = []
    for path in KIT_SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in _functions(tree):
            # Nested functions are walked on their own; attribute a call to
            # the innermost function that contains it.
            inner = {id(n) for child in _functions(fn) if child is not fn
                     for n in ast.walk(child)}
            calls = [(node, name) for node, name in _guarded_calls(fn)
                     if id(node) not in inner]
            if not calls:
                continue
            check = _first_check_line(fn)
            for node, name in calls:
                if not _takes_grant(fn) or check is None or check > node.lineno:
                    offenders.append(f"{path.relative_to(ROOT)}:{node.lineno} "
                                     f"{fn.name} calls {name}")
    assert not offenders, "\n".join(offenders)


def test_the_kit_imports_no_network_client():
    for path in KIT_SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                names = {(node.module or "").split(".")[0]}
            else:
                continue
            assert not names & GUARDED_MODULES, f"{path.name} imports {names}"


def test_a_job_grant_is_minted_only_by_authorize_job_item():
    sites = []
    for path in [ROOT / "main.py", *ROOT.glob("services/**/*.py"),
                 *ROOT.glob("ui/**/*.py"), *ROOT.glob("agents/**/*.py")]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in _functions(tree):
            for node in ast.walk(fn):
                if isinstance(node, ast.Call) and _call_name(node)[1] == "JobGrant":
                    sites.append((path.name, fn.name))
    assert sites == [("main.py", "authorize_job_item")]


def test_a_grant_cannot_be_built_without_the_mint_key():
    import pytest
    from services.release_kit.grant import JobGrant
    with pytest.raises(TypeError):
        JobGrant(object(), token="t", job_id="j", stage="quotes", item_key="k",
                 provider="ollama", model="m", is_open=lambda t: True)


def test_job_tokens_never_enter_the_by_agent_queue():
    """F7: a by-name resolve from Press or Booth must not take a kit token."""
    tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
    for name in ("authorize_job_item", "record_job_item", "close_job_item"):
        (fn,) = [f for f in _functions(tree) if f.name == name]
        used = {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}
        used |= {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
        assert not used & {"_pending_by_agent", "QMessageBox",
                           "confirm_external_api_request", "offer_failover",
                           "_offer_local_fallback"}, name


# ── review P2-4: references and the replaceable renderer table ───────────────

def _enclosing(tree):
    """node id -> innermost enclosing function."""
    owner = {}
    for fn in _functions(tree):
        for n in ast.walk(fn):
            owner[id(n)] = fn
    return owner


def test_a_guarded_function_is_never_passed_around_without_a_grant():
    """`self.host.run_backend` handed over as a value is a call the name walk
    cannot see. Such a reference is allowed only in a function that first got
    a grant from `authorize_job_item` and passes `grant` along."""
    offenders = []
    for path in KIT_SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        owner = _enclosing(tree)
        call_funcs = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
        for node in ast.walk(tree):
            name = (node.attr if isinstance(node, ast.Attribute)
                    else node.id if isinstance(node, ast.Name) else "")
            if name not in GUARDED_NAMES or id(node) in call_funcs:
                continue
            if isinstance(node, ast.Name) and isinstance(
                    node.ctx, (ast.Store, ast.Param)):
                continue
            fn = owner.get(id(node))
            minted = [n.lineno for n in ast.walk(fn)
                      if isinstance(n, ast.Call)
                      and _call_name(n)[1] == "authorize_job_item"] if fn else []
            if not minted or min(minted) > node.lineno:
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno} "
                                 f"references {name}")
    assert not offenders, "\n".join(offenders)


def test_renderers_that_reach_a_provider_are_called_with_the_grant():
    """`self.render[...]` is a replaceable dict; the text and short renderers
    must receive `grant` so their own `grant.check()` (covered above) runs."""
    seen = set()
    for path in KIT_SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Subscript)
                    and isinstance(node.func.value, ast.Attribute)
                    and node.func.value.attr == "render"):
                continue
            key = node.func.slice
            if isinstance(key, ast.Constant) and key.value in ("text", "short"):
                seen.add(key.value)
                first = node.args[0] if node.args else None
                assert isinstance(first, ast.Name) and first.id == "grant", \
                    f"{path.name}:{node.lineno} render[{key.value!r}] without grant"
    assert seen == {"text", "short"}


def test_the_default_text_and_short_renderers_check_the_grant():
    from ui.release_kit.driver import default_renderers
    from services.release_kit import stages
    table = default_renderers()
    assert table["text"] is stages.ask_text
    assert table["short"] is stages.render_short_item
