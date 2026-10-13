"""
Enrich an approved plan with exact API data and render a deterministic draft
script - no AI involved. The draft is the starting point for autosar-generate.

render_script(plan, draft=None, summary=False)
  -> {mode, mcp_connectivity, rules, enum_aliases, classes, ecuc_defs, steps, script|draft}
"""

import pathlib
import re

from . import srv
from .af_api import REPO_ROOT, all_classes, all_enums, connectivity, load_plan

TEMPLATES = pathlib.Path(__file__).resolve().parent / "templates"


def dest_tag(def_type: str) -> str:
    """EcucParamConfContainerDef -> ECUC-PARAM-CONF-CONTAINER-DEF"""
    return re.sub(r"(?<!^)(?=[A-Z])", "-", def_type).upper()


def mode_of(plan: dict) -> str:
    if plan["request_type"] == "ecuc":
        return "ecuc_with_defs" if plan.get("inputs", {}).get("ecuc_definition_arxmls") else "ecuc_defref_postprocess"
    return "system_modify" if plan.get("inputs", {}).get("read_arxmls") else "system_new"


RULES = {
    "common": [
        "Import exactly: from autosarfactory import autosarfactory as AF (with the sys.path fallback in the draft).",
        "Enums: use the module-level aliases (e.g. ByteOrderEnum.VALUE_X) - never quote enum values.",
        "Only call methods listed for the class in `classes` - never invent new_/set_/add_ names.",
        "Every plan step keeps its '# --- Sx: ...' section comment and _step() progress print.",
        "AF.reinit() first so reruns in one interpreter start clean.",
    ],
    "system_new": [
        "File workflow: AF.new_file(OUTPUT_ARXML, defaultArPackage=..., overWrite=True) -> model -> AF.save().",
    ],
    "system_modify": [
        "File workflow: AF.read(files=INPUT_ARXMLS) (check the status flag) -> AF.get_node(path) (check None) -> model -> AF.save().",
        "AF.save() rewrites every loaded file - confirm with the user that in-place modification is intended.",
    ],
    "ecuc_with_defs": [
        "File workflow: AF.read(ECUC_DEFS) FIRST -> AF.new_file(OUTPUT_ARXML) -> values -> AF.save([OUTPUT_ARXML]).",
        "Never call AF.save() without the file list - it would rewrite the definition arxml.",
        "Link every value with obj.set_definition(_def(path)); _def() raises if the path is missing.",
    ],
    "ecuc_defref_postprocess": [
        "No definition arxml: do NOT call set_definition(). Register each value with _defref(obj, path, DEST).",
        "Order is fixed: AF.save([OUTPUT_ARXML]) THEN _apply_definition_refs(OUTPUT_ARXML).",
        "DEST is the XML tag of the definition type (EcucIntegerParamDef -> ECUC-INTEGER-PARAM-DEF); take it from the draft.",
    ],
}


def _val(value: dict, enum_aliases: set, numeric: bool = False) -> str:
    if "var" in value:
        return value["var"]
    if "enum" in value:
        raw = value["enum"].removeprefix("AF.")
        enum_aliases.add(raw.split(".")[0])
        return raw
    lit = value.get("literal")
    if numeric and isinstance(lit, bool):
        lit = int(lit)
    return repr(lit)


def render_step(step: dict, mode: str, enum_aliases: set) -> list:
    a, sid = step["action"], step["id"]
    desc = step.get("description", "").replace("\n", " ")
    lines = [f"# --- {sid}: {desc} ---", f'_step("{sid}", {desc!r})']
    var = step.get("var")
    if a == "root":
        lines.append(f"{var} = AF.new_file(OUTPUT_ARXML, defaultArPackage={step['args']['name']!r}, overWrite=True)")
    elif a == "get_node":
        path = step["args"]["path"]
        lines += [f"{var} = AF.get_node({path!r})",
                  f"if {var} is None:",
                  f"    raise RuntimeError('Element not found: {path}')"]
    elif a == "new":
        name = (step.get("args") or {}).get("name")
        lines.append(f"{var} = {step['parent']}.{step['method']}({name!r})" if name
                     else f"{var} = {step['parent']}.{step['method']}()")
        d = step.get("definition")
        if d:
            if mode == "ecuc_with_defs":
                lines.append(f"{var}.set_definition(_def({d['path']!r}))")
            elif mode == "ecuc_defref_postprocess":
                lines.append(f"_defref({var}, {d['path']!r}, {dest_tag(d['type'])!r})")
        v = step.get("value")
        if v is not None:
            cls = step["class"]
            if cls == "EcucNumericalParamValue":
                lines.append(f"{var}.new_Value().set({_val(v, enum_aliases, numeric=True)})")
            elif cls == "EcucTextualParamValue":
                lit = v.get("literal")
                lines.append(f"{var}.set_value({str(lit)!r})")
            else:
                lines.append(f"{var}.set_value({_val(v, enum_aliases)})")
    elif a in ("set_ref", "add_ref", "set_attr"):
        lines.append(f"{step['target']}.{step['method']}({_val(step['value'], enum_aliases)})")
    elif a == "set_value":
        lines.append(f"{step['target']}.set({_val(step['value'], enum_aliases)})")
    return lines


def header(plan: dict, mode: str, enum_aliases: set) -> str:
    out = plan["output"]
    doc = ['"""', f'{plan.get("title", "AUTOSAR model")}', "",
           "Generated by /autosar-generate from an approved /autosar-plan plan.",
           f"Request: {plan.get('request', '').strip()}",
           f"Mode: {mode}", '"""', ""]
    h = doc + [
        "import os",
        "import sys",
        "",
    ]
    if (REPO_ROOT / "autosarfactory" / "autosarfactory.py").is_file():
        h += ["try:",
              "    from autosarfactory import autosarfactory as AF",
              "except ImportError:  # running from a source checkout without `pip install`",
              f"    sys.path.insert(0, {str(REPO_ROOT)!r})",
              "    from autosarfactory import autosarfactory as AF",
              ""]
    else:
        h += ["from autosarfactory import autosarfactory as AF", ""]
    if enum_aliases:
        h += ["# Enum aliases - use as bare expressions, never quoted"]
        h += [f"{e} = AF.{e}" for e in sorted(enum_aliases)]
        h += [""]
    h += [f"OUTPUT_ARXML = os.path.abspath({out['arxml']!r})"]
    if mode == "system_modify":
        h += [f"INPUT_ARXMLS = {plan['inputs']['read_arxmls']!r}"]
    if mode == "ecuc_with_defs":
        h += ["",
              "# ---------------------------------------------------------------",
              "# REQUIRED: path(s) to your ECUC module definition arxml file(s).",
              "# AF.get_node() calls for set_definition() will fail without this.",
              "# ---------------------------------------------------------------",
              f"ECUC_DEFS = {plan['inputs']['ecuc_definition_arxmls']!r}  # <-- UPDATE IF NEEDED"]
    h += ["", "",
          "def _step(sid, text):",
          '    print(f"[{sid}] {text}")', ""]
    if mode == "ecuc_with_defs":
        h += ["",
              "def _def(path):",
              "    node = AF.get_node(path)",
              "    if node is None:",
              "        raise RuntimeError(f'ECUC definition not found (is ECUC_DEFS correct?): {path}')",
              "    return node", ""]
    if mode == "ecuc_defref_postprocess":
        h += ["", (TEMPLATES / "ecuc_defref.py").read_text(encoding="utf-8").rstrip(), ""]
    h += ["", "def main():",
          "    os.makedirs(os.path.dirname(OUTPUT_ARXML), exist_ok=True)",
          "    AF.reinit()"]
    if mode == "ecuc_with_defs":
        h += ["    _, ok = AF.read(files=ECUC_DEFS)",
              "    if not ok:",
              "        raise RuntimeError(f'Failed to load ECUC definitions: {ECUC_DEFS}')"]
    if mode == "system_modify":
        h += ["    _root, ok = AF.read(files=INPUT_ARXMLS)",
              "    if not ok:",
              "        raise RuntimeError(f'Failed to read input arxml(s): {INPUT_ARXMLS}')"]
    return "\n".join(h)


def footer(mode: str) -> str:
    f = ["", "    # --- Save ---"]
    if mode.startswith("ecuc"):
        f += ["    AF.save([OUTPUT_ARXML])  # only the values file - never the definition arxml"]
        if mode == "ecuc_defref_postprocess":
            f += ["    _apply_definition_refs(OUTPUT_ARXML)  # must run AFTER AF.save()"]
    else:
        f += ["    AF.save()"]
    f += ['    print(f"[done] saved {OUTPUT_ARXML}")', "", "",
          'if __name__ == "__main__":', "    main()", ""]
    return "\n".join(f)


def class_api(names: set) -> dict:
    out = {}
    for n in sorted(names):
        c = srv().get_class(n, "all")
        if "error" in c:
            out[n] = c
            continue
        out[n] = {"new": [f'{k["method"]}({"name" if k.get("hasShortName", True) else ""}) -> {k["returns"]}'
                          for k in c.get("children", []) if k["method"] != "new_VariationPoint"],
                  "references": c.get("references", {}),
                  "attributes": {k: v for k, v in c.get("attributes", {}).items()
                                 if k not in ("set_uuid", "set_shortName")}}
    return out


def ecuc_defs(plan: dict) -> dict:
    """Constraint data (literals/min/max/default) for every definition path the plan uses."""
    wanted = {s["definition"]["path"] for s in plan["steps"] if s.get("definition")}
    out = {}
    for entries in srv()._ecuc_containers.values():
        for e in entries:
            for item in e["parameters"] + e["references"]:
                if item["path"] in wanted:
                    out[item["path"]] = {k: item[k] for k in
                                         ("type", "multiplicity", "min", "max", "default", "literals", "destination")
                                         if k in item}
    return out


def render_script(plan, draft: str | None = None, summary: bool = False) -> dict:
    """
    plan:    dict, JSON string or path to a plan file.
    draft:   if given, write the rendered draft script to this path.
    summary: omit per-step code (and the script text when a draft file is written).
    """
    plan, _ = load_plan(plan)
    mode = mode_of(plan)

    aliases: set = set()
    rendered = [{"id": s["id"], "code": render_step(s, mode, aliases)} for s in plan["steps"]]
    body = "\n\n".join("\n".join("    " + ln for ln in r["code"]) for r in rendered)
    script = header(plan, mode, aliases) + "\n\n" + body + "\n" + footer(mode)

    used = {s["class"] for s in plan["steps"] if s.get("class")}
    unknown_enums = sorted(e for e in aliases if e not in all_enums())
    result = {
        "mode": mode,
        "mcp_connectivity": connectivity(),
        "rules": RULES["common"] + RULES[mode],
        "enum_aliases": {e: all_enums().get(e, "NOT FOUND") for e in sorted(aliases)},
        "classes": class_api({c for c in used if c in all_classes()}),
    }
    if unknown_enums:
        result["warnings"] = [f"unknown enum(s): {unknown_enums}"]
    if mode.startswith("ecuc"):
        result["ecuc_defs"] = ecuc_defs(plan)
    if draft:
        path = pathlib.Path(draft)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(script, encoding="utf-8")
        result["draft"] = str(path)
    if not summary:
        result["steps"] = rendered
    if not (draft and summary):
        result["script"] = script
    return result
