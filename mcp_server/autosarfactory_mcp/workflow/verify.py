"""
Confirm a generated arxml exists and loads with autosarfactory, and summarise it.

verify_arxml(arxml, plan=None)
  -> {ok, file, size_bytes, element_counts, definition_refs[, missing_from_plan]}
With a plan, every shortName the plan creates must be present in the file.
"""

import collections
import pathlib

from lxml import etree

from .af_api import af_runtime, load_plan


def verify_arxml(arxml: str, plan=None) -> dict:
    path = pathlib.Path(arxml)
    if not path.is_file():
        return {"ok": False, "file": str(path), "error": "file not found"}

    AF = af_runtime()
    AF.reinit()
    try:
        _, ok = AF.read(files=[str(path)])
    finally:
        AF.reinit()  # don't leave the file loaded in a long-running server

    xml = etree.parse(str(path))
    counts = collections.Counter(etree.QName(e).localname for e in xml.iter()
                                 if isinstance(e.tag, str) and e.find("{*}SHORT-NAME") is not None)
    names = {e.text for e in xml.iter("{*}SHORT-NAME")}
    defrefs = xml.findall(".//{*}DEFINITION-REF")
    result = {
        "ok": bool(ok),
        "file": str(path.resolve()),
        "size_bytes": path.stat().st_size,
        "element_counts": dict(counts.most_common()),
        "definition_refs": len(defrefs),
    }
    bad = sorted({d.get("DEST") or "" for d in defrefs if not (d.get("DEST") or "").isupper()})
    if bad:
        result["ok"] = False
        result["bad_dest"] = bad
    if plan:
        plan_obj, _ = load_plan(plan)
        wanted = {(s.get("args") or {}).get("name") for s in plan_obj["steps"] if s["action"] in ("root", "new")}
        result["missing_from_plan"] = sorted(n for n in wanted if n and n not in names)
        result["ok"] = result["ok"] and not result["missing_from_plan"]
    return result
