"""
Programmatic grader for the autosar-generate MCP prompt evals.

Usage (from the repo root):
    python mcp_server/evals/autosar-generate/grade_run.py --eval-id 2 --outputs <dir> [--out grading.json]

Checks every expectation of the given eval against the run's outputs directory
and writes a grading.json ({expectations: [{text, passed, evidence}], summary}).
Exit code 0 when all expectations pass.
"""

import argparse
import hashlib
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
MCP_SERVER_DIR = HERE.parents[1]
sys.path.insert(0, str(MCP_SERVER_DIR))
from autosarfactory_mcp.cli import load_server  # noqa: E402

srv = load_server()

PLAN_NAMES = {1: "plan_system_sr.plan.json", 2: "plan_ecuc_defref.plan.json", 3: "plan_ecuc_withdefs.plan.json"}


def _call_linenos(src: str):
    """(AF.save call lines, bare AF.save() call lines, _apply_definition_refs call lines) via AST."""
    import ast
    saves, bare, applies = [], [], []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return saves, bare, applies
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if (isinstance(f, ast.Attribute) and f.attr == "save"
                and isinstance(f.value, ast.Name) and f.value.id == "AF"):
            saves.append(node.lineno)
            if not node.args and not node.keywords:
                bare.append(node.lineno)
        elif isinstance(f, ast.Name) and f.id == "_apply_definition_refs":
            applies.append(node.lineno)
    return saves, bare, applies


def _count_defrefs(arxml: pathlib.Path) -> int:
    from lxml import etree
    return len(etree.parse(str(arxml)).findall(".//{*}DEFINITION-REF"))


def grade(eval_id: int, outdir: pathlib.Path) -> list:
    results = []

    def add(text, passed, evidence):
        results.append({"text": text, "passed": bool(passed), "evidence": str(evidence)[:400]})

    plan_path = outdir / PLAN_NAMES[eval_id]
    if not plan_path.is_file():
        found = sorted(outdir.rglob("*.plan.json"))
        plan_path = found[0] if found else None
    if plan_path is None:
        add("An executable Python script was produced at the plan's output.script path",
            False, f"input plan {PLAN_NAMES[eval_id]} not found in {outdir}")
        return results
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    script_path = pathlib.Path(plan["output"]["script"])
    arxml_path = pathlib.Path(plan["output"]["arxml"])

    add("An executable Python script was produced at the plan's output.script path",
        script_path.is_file(), str(script_path))
    if not script_path.is_file():
        return results
    src = script_path.read_text(encoding="utf-8")

    check = srv.check_generated_script(str(script_path), str(plan_path))
    add("check_generated_script passes with zero errors", check.get("ok"), check.get("errors") or "ok")

    add("The output arxml file was created", arxml_path.is_file(), str(arxml_path))
    if arxml_path.is_file():
        verify = srv.verify_arxml(str(arxml_path), str(plan_path))
        add("verify_arxml confirms the arxml loads and contains every planned shortName",
            verify.get("ok") and not verify.get("missing_from_plan"),
            {k: verify.get(k) for k in ("ok", "definition_refs", "missing_from_plan")})
    else:
        add("verify_arxml confirms the arxml loads and contains every planned shortName", False, "arxml missing")

    missing_sections = [s["id"] for s in plan["steps"] if not re.search(rf"#\s*---\s*{re.escape(s['id'])}\b", src)]
    add("The script keeps one section comment per plan step",
        not missing_sections, f"missing sections: {missing_sections or 'none'}")

    if eval_id == 1:
        has_tref = arxml_path.is_file() and "PROVIDED-INTERFACE-TREF" in arxml_path.read_text(encoding="utf-8")
        add("The arxml links the P-port to the interface (PROVIDED-INTERFACE-TREF present)", has_tref,
            "found" if has_tref else "PROVIDED-INTERFACE-TREF not found")

    if eval_id in (2, 3):
        saves, bare, applies = _call_linenos(src)
        add("AF.save is called with an explicit file list (never a bare AF.save())",
            saves and not bare, f"AF.save calls at lines {saves}, bare calls at lines {bare}")
        expected = 5 if eval_id == 2 else 3
        n = _count_defrefs(arxml_path) if arxml_path.is_file() else -1
        add(f"The arxml contains exactly {expected} DEFINITION-REF elements", n == expected, f"found {n}")

    if eval_id in (2, 3) and arxml_path.is_file():
        from lxml import etree
        want = {(s["definition"]["path"], re.sub(r"(?<!^)(?=[A-Z])", "-", s["definition"]["type"]).upper())
                for s in plan["steps"] if s.get("definition")}
        got = {(d.text, d.get("DEST")) for d in etree.parse(str(arxml_path)).findall(".//{*}DEFINITION-REF")}
        add("Every DEFINITION-REF has the definition path and DEST tag the plan specifies",
            want == got, f"missing={sorted(want - got)}, unexpected={sorted(got - want)}")

    if eval_id == 3:
        fixture = HERE / "files" / "defs.arxml"
        used = outdir / "defs.arxml"
        same = (used.is_file() and
                hashlib.sha256(used.read_bytes()).hexdigest() == hashlib.sha256(fixture.read_bytes()).hexdigest())
        add("The ECUC definition arxml (defs.arxml) was not modified by the run", same,
            "unchanged" if same else "defs.arxml content differs from the fixture (or is missing)")

    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-id", type=int, required=True)
    ap.add_argument("--outputs", required=True)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    expectations = grade(a.eval_id, pathlib.Path(a.outputs))
    passed = sum(1 for e in expectations if e["passed"])
    grading = {"expectations": expectations,
               "summary": {"passed": passed, "failed": len(expectations) - passed,
                           "total": len(expectations),
                           "pass_rate": round(passed / len(expectations), 4) if expectations else 0.0}}
    text = json.dumps(grading, indent=1, ensure_ascii=False)
    if a.out:
        pathlib.Path(a.out).write_text(text, encoding="utf-8")
    print(text)
    sys.exit(0 if passed == len(expectations) else 1)


if __name__ == "__main__":
    main()
