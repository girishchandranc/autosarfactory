"""
Static checks for a generated autosarfactory script - no AI, no execution.

check_script(script, plan=None) -> {ok, errors, warnings}

Checks: Python syntax, the AF import, quoted enums, enum names/literals,
every new_/set_/add_ method name against the API DB, file-save workflow rules
(system vs ECUC), and - with a plan - that every plan step has its section.
"""

import ast
import pathlib
import re

from .af_api import all_classes, all_enums, load_plan, suggest

AF_MODULE_FUNCS = {"new_file", "read", "save", "saveAs", "get_node", "get_all_instances",
                   "get_root", "reinit", "export_to_file"}


_known_methods = None


def known_methods() -> set:
    global _known_methods
    if _known_methods is not None:
        return _known_methods
    names = set()
    for c in all_classes().values():
        for section in ("children", "references", "attributes"):
            names.update(m["method"] for m in c.get(section, []))
    _known_methods = names
    return names


def _check(src: str, plan: dict | None) -> dict:
    errors, warnings = [], []
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return {"ok": False, "errors": [f"SyntaxError line {e.lineno}: {e.msg}"], "warnings": []}

    if "from autosarfactory import autosarfactory as AF" not in src:
        errors.append("missing `from autosarfactory import autosarfactory as AF`")

    for m in re.finditer(r"""["'](?:AF\.)?(\w+Enum)\.(VALUE_\w+)["']""", src):
        errors.append(f"quoted enum {m.group(0)} - write it as a bare expression")

    methods, enums = known_methods(), all_enums()
    aliases = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign)
               for t in n.targets if isinstance(t, ast.Name)
               and isinstance(n.value, ast.Attribute) and isinstance(n.value.value, ast.Name)
               and n.value.value.id == "AF" and n.value.attr in enums}
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            base = node.value
            # Enum access: AF.XEnum.VALUE_Y or alias XEnum.VALUE_Y
            ename = None
            if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name) and base.value.id == "AF":
                ename = base.attr
            elif isinstance(base, ast.Name) and (base.id in aliases or base.id in enums):
                ename = base.id
            if ename and node.attr.startswith("VALUE_"):
                if ename not in enums:
                    errors.append(f"line {node.lineno}: unknown enum {ename}")
                elif node.attr not in enums[ename]:
                    errors.append(f"line {node.lineno}: {ename}.{node.attr} is not a valid literal "
                                  f"(closest: {suggest(node.attr, enums[ename], 3)})")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            attr, base = node.func.attr, node.func.value
            if isinstance(base, ast.Name) and base.id == "AF":
                if attr not in AF_MODULE_FUNCS and not (attr in enums or attr in all_classes()):
                    warnings.append(f"line {node.lineno}: AF.{attr}() is not a known module function")
                calls.append(("AF", attr, node))
                continue
            if re.match(r"(new|set|add)_", attr) and attr not in methods:
                errors.append(f"line {node.lineno}: unknown API method {attr}() "
                              f"(closest: {suggest(attr, methods, 3)})")
            calls.append((None, attr, node))

    # --- file-save workflow rules -------------------------------------------
    af_calls = [(a, n) for b, a, n in calls if b == "AF"]
    saves = [n for a, n in af_calls if a == "save"]
    if not saves and not any(a == "saveAs" for a, _ in af_calls):
        errors.append("no AF.save() call - nothing would be written")
    uses_defref = "_defref(" in src
    uses_set_def = any(a == "set_definition" for b, a, _ in calls if b is None)
    is_ecuc = uses_defref or uses_set_def or "EcucModuleConfigurationValues" in src
    if is_ecuc:
        for n in saves:
            if not n.args and not n.keywords:
                errors.append(f"line {n.lineno}: ECUC script must call AF.save([OUTPUT_ARXML]) - "
                              "a bare AF.save() rewrites the loaded definition arxml")
        if uses_set_def and not any(a == "read" for a, _ in af_calls):
            errors.append("set_definition() used but no AF.read() of the ECUC definition arxml")
        if uses_defref:
            if uses_set_def:
                warnings.append("both set_definition() and _defref() used - pick one mode")
            post = [n for b, a, n in calls if b is None and a == "_apply_definition_refs"] + \
                   [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                    and n.func.id == "_apply_definition_refs"]
            if not post:
                errors.append("_defref() used but _apply_definition_refs() is never called")
            elif saves and min(p.lineno for p in post) < max(s.lineno for s in saves):
                errors.append("_apply_definition_refs() must run AFTER AF.save()")
        if not uses_defref and not uses_set_def:
            warnings.append("ECUC values without set_definition()/_defref() - DEFINITION-REF will be missing")

    # --- plan coverage -----------------------------------------------------------------------
    if plan:
        for step in plan.get("steps", []):
            if not re.search(rf"#\s*---\s*{re.escape(step['id'])}\b", src):
                warnings.append(f"no section comment for plan step {step['id']}")
        out = (plan.get("output") or {}).get("arxml")
        if out and pathlib.Path(out).name not in src:
            warnings.append(f"output file {out} from the plan does not appear in the script")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def check_script(script: str, plan=None) -> dict:
    """script: path to a .py file or the script source itself. plan: dict / JSON / path, optional."""
    src = script
    try:
        if "\n" not in script and script.strip().endswith(".py"):
            src = pathlib.Path(script.strip()).read_text(encoding="utf-8")
        plan_obj = load_plan(plan)[0] if plan else None
    except (OSError, ValueError) as e:
        return {"ok": False, "errors": [f"could not load input: {e}"], "warnings": []}
    return _check(src, plan_obj)
