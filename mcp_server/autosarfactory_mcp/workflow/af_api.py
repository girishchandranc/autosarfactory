"""Shared lookups over the server's API / ECUC data, plus runtime-library checks."""

import contextlib
import difflib
import io
import json
import pathlib
import sys

from . import srv

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
ROOT_CLASS = "ARPackage"


def all_classes() -> dict:
    return srv()._db["classes"]


def all_enums() -> dict:
    return srv()._db["enums"]


def creators(class_name: str) -> list:
    return srv()._creators_index.get(class_name, [])


def suggest(name: str, pool, n: int = 5) -> list:
    """Closest names in pool: case-insensitive exact, then substring, then fuzzy."""
    pool = list(pool)
    low = {p.lower(): p for p in pool}
    if name.lower() in low:
        return [low[name.lower()]]
    subs = [p for p in pool if name.lower() in p.lower()]
    fuzzy = difflib.get_close_matches(name, pool, n=n, cutoff=0.6)
    return list(dict.fromkeys(subs[:n] + fuzzy))[:n]


_af = None


def af_runtime():
    """The autosarfactory module itself, for issubclass/hasattr checks the JSON DB can't answer."""
    global _af
    if _af is None:
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                from autosarfactory import autosarfactory as AF
        except ImportError:
            sys.path.insert(0, str(REPO_ROOT))
            with contextlib.redirect_stderr(io.StringIO()):
                from autosarfactory import autosarfactory as AF
        _af = AF
    return _af


def is_subclass(child: str, base: str):
    """True/False, or None when either name isn't an autosarfactory class."""
    AF = af_runtime()
    c, b = getattr(AF, child, None), getattr(AF, base, None)
    if not isinstance(c, type) or not isinstance(b, type):
        return None
    return issubclass(c, b)


def connectivity() -> dict:
    """Explicit status of every data source the planner/generator relies on."""
    s = srv()
    return {
        "api_db": {"loaded": bool(all_classes()), "classes": len(all_classes()), "enums": len(all_enums())},
        "ecuc_db": {"loaded": bool(s._ecuc_modules), "modules": len(s._ecuc_modules)},
        "element_map": {"loaded": bool(s._elem_map_sections), "use_cases": len(s._elem_map_sections)},
        "spec_kb": {"loaded": s._kb is not None},
    }


def load_plan(plan) -> tuple[dict, str | None]:
    """Accept a plan dict, a JSON string, or a path to a plan file. Returns (plan, path_or_None)."""
    if isinstance(plan, dict):
        return plan, None
    text = str(plan).strip()
    if text.startswith("{"):
        return json.loads(text), None
    path = pathlib.Path(text)
    return json.loads(path.read_text(encoding="utf-8")), str(path)
