"""
Programmatic grader for the autosar-plan MCP prompt evals.

Usage (from the repo root):
    python mcp_server/evals/autosar-plan/grade_run.py --eval-id 1 --outputs <dir> [--out grading.json]

Checks every expectation of the given eval against the run's outputs directory
and writes a grading.json ({expectations: [{text, passed, evidence}], summary}).
Exit code 0 when all expectations pass.
"""

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
MCP_SERVER_DIR = HERE.parents[1]
sys.path.insert(0, str(MCP_SERVER_DIR))
from autosarfactory_mcp.cli import load_server  # noqa: E402

srv = load_server()


def find_plan(outdir: pathlib.Path):
    cands = sorted(outdir.rglob("*.plan.json"))
    if not cands:
        for p in sorted(outdir.rglob("*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(d, dict) and "steps" in d and "output" in d:
                cands.append(p)
    return cands[0] if cands else None


def grade(eval_id: int, outdir: pathlib.Path) -> list:
    """Returns [(text, passed, evidence)] for the eval's expectations."""
    results = []

    def add(text, passed, evidence):
        results.append({"text": text, "passed": bool(passed), "evidence": str(evidence)[:400]})

    plan_path = find_plan(outdir)
    add("A plan JSON file (*.plan.json) was produced in the outputs directory",
        plan_path is not None, plan_path or f"no plan JSON found under {outdir}")
    if plan_path is None:
        return results
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    steps = plan.get("steps", [])

    report = srv.validate_plan(str(plan_path))
    add("validate_plan reports the plan valid with zero errors",
        report.get("valid") and not report.get("errors"),
        report.get("errors") or f"valid, {report['stats']['steps']} steps")

    expected_type = "ecuc" if eval_id == 2 else "system"
    add(f"The plan's request_type is '{expected_type}'",
        plan.get("request_type") == expected_type, f"request_type={plan.get('request_type')}")

    conn = plan.get("mcp_connectivity")
    api_loaded = isinstance(conn, dict) and (conn.get("api_db") or {}).get("loaded") is True
    add("The plan records MCP connectivity status (mcp_connectivity)",
        api_loaded, conn if conn is not None else "missing")

    # Only a *modelling* script counts as "writing code"; helper scripts are not the deliverable.
    modelling = [p.name for p in outdir.rglob("*.py")
                 if any(k in p.read_text(encoding="utf-8", errors="ignore") for k in ("AF.save(", "new_file("))]
    add("No modelling script was written (the planner writes no code)",
        not modelling, modelling or "no modelling script")

    def new_steps(cls=None):
        return [s for s in steps if s.get("action") == "new" and (cls is None or s.get("class") == cls)]

    def ref_methods():
        return {s.get("method") for s in steps if s.get("action") in ("set_ref", "add_ref")}

    if eval_id == 1:
        add("The plan creates a SenderReceiverInterface", bool(new_steps("SenderReceiverInterface")),
            [s["id"] for s in new_steps("SenderReceiverInterface")] or "none")
        pp, rp = new_steps("PPortPrototype"), new_steps("RPortPrototype")
        add("The plan creates both a PPortPrototype and an RPortPrototype",
            pp and rp, f"PPort steps={[s['id'] for s in pp]}, RPort steps={[s['id'] for s in rp]}")
        m = ref_methods()
        add("Both ports are linked to the interface via set_providedInterface / set_requiredInterface",
            {"set_providedInterface", "set_requiredInterface"} <= m, f"reference methods used: {sorted(m)}")

    elif eval_id == 2:
        ecuc_new = [s for s in new_steps() if str(s.get("class", "")).startswith("Ecuc")]
        missing = [s["id"] for s in ecuc_new
                   if not str((s.get("definition") or {}).get("path", "")).startswith("/AUTOSAR/EcucDefs/")]
        add("Every ECUC value step carries a definition path under /AUTOSAR/EcucDefs/",
            ecuc_new and not missing, f"{len(ecuc_new)} ECUC steps, missing definition on: {missing or 'none'}")
        tasks = [s for s in ecuc_new if (s.get("definition") or {}).get("path") == "/AUTOSAR/EcucDefs/Os/OsTask"]
        add("Two OsTask container values are created", len(tasks) == 2, f"{len(tasks)} OsTask steps")

        def param_values(suffix):
            vals = []
            for s in steps:
                if (s.get("definition") or {}).get("path", "").endswith(suffix):
                    v = s.get("value") or {}
                    vals.append(v.get("literal"))
            return vals
        prios = param_values("/OsTaskPriority")
        add("OsTaskPriority is set for both tasks with the requested values (5 and 1)",
            sorted(int(v) for v in prios if v is not None) == [1, 5], f"priorities found: {prios}")
        scheds = param_values("/OsTaskSchedule")
        add("OsTaskSchedule uses the valid literal FULL",
            len(scheds) >= 1 and all(v == "FULL" for v in scheds), f"schedule values: {scheds}")
        acts = param_values("/OsTaskActivation")
        add("The mandatory OsTaskActivation parameter is set for each task",
            len(acts) == 2 and all(v is not None for v in acts), f"activation values: {acts}")

    elif eval_id == 3:
        reads = (plan.get("inputs") or {}).get("read_arxmls") or []
        add("The plan reads the existing arxml (inputs.read_arxmls is non-empty)", bool(reads), reads or "empty")
        gets = [s["id"] for s in steps if s.get("action") == "get_node"]
        add("The plan locates existing elements via get_node steps", bool(gets), gets or "no get_node steps")
        rp = new_steps("RPortPrototype")
        add("An RPortPrototype is added and linked via set_requiredInterface",
            rp and "set_requiredInterface" in ref_methods(),
            f"RPort steps={[s['id'] for s in rp]}, ref methods={sorted(ref_methods())}")

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
