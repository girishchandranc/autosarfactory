"""
Validate an AUTOSAR modelling plan (see prompts/plan_schema.md) against the
live autosarfactory API data, auto-correcting what can be corrected unambiguously.

validate_plan(plan, fix=False, out=None)
  -> {valid, errors, warnings, corrections, applied, stats[, plan][, written_to]}
"""

import copy
import difflib
import json
import keyword
import pathlib
import re

from . import srv
from .af_api import af_runtime, all_classes, all_enums, creators, is_subclass, load_plan, suggest

ACTIONS = {"root", "get_node", "new", "set_ref", "add_ref", "set_attr", "set_value"}
ECUC_VALUE_CLASSES = {"EcucModuleConfigurationValues", "EcucContainerValue", "EcucNumericalParamValue",
                      "EcucTextualParamValue", "EcucReferenceValue", "EcucInstanceReferenceValue",
                      "EcucAddInfoParamValue"}
# Names the generated script itself uses - plan vars must not shadow them.
RESERVED_VARS = {"AF", "os", "sys", "etree", "main", "ok", "_root", "_step", "_def", "_defref",
                 "_apply_definition_refs", "_DEF_REFS", "_DEFREF_AFTER",
                 "OUTPUT_ARXML", "INPUT_ARXMLS", "ECUC_DEFS"}


def _lower(mult) -> int:
    m = re.match(r"\s*(\d+)", str(mult or "0"))
    return int(m.group(1)) if m else 0


def _ecuc_index() -> dict:
    """def path -> {kind, type, data, owner}"""
    idx = {}
    for name, mod in srv()._ecuc_modules.items():
        if mod.get("path"):
            idx[mod["path"]] = {"kind": "module", "type": mod.get("type", "EcucModuleDef"), "data": mod}
    for entries in srv()._ecuc_containers.values():
        for e in entries:
            idx[e["path"]] = {"kind": "container", "type": e["type"], "data": e}
            for p in e["parameters"]:
                idx.setdefault(p["path"], {"kind": "param", "type": p["type"], "data": p, "owner": e["path"]})
            for r in e["references"]:
                idx.setdefault(r["path"], {"kind": "reference", "type": r["type"], "data": r, "owner": e["path"]})
    return idx


class Validator:
    def __init__(self, plan: dict, fix: bool):
        self.plan, self.fix = plan, fix
        self.errors, self.warnings, self.corrections = [], [], []
        self.vars = {}        # var -> {"class", "step", "def_path"}
        self.step_ids = set()
        self.names = {}       # (parent var, shortName) -> step id
        self.children = {}    # parent var -> list of child def paths
        self.classes = all_classes()
        self.enums = all_enums()
        self._ecuc = None

    # -- reporting -----------------------------------------------------------
    def err(self, sid, msg):
        self.errors.append({"step": sid, "msg": msg})

    def warn(self, sid, msg):
        self.warnings.append({"step": sid, "msg": msg})

    def correct(self, sid, step, field, old, new, why):
        self.corrections.append({"step": sid, "field": field, "from": old, "to": new, "why": why})
        if self.fix:
            step[field] = new

    @property
    def ecuc(self):
        if self._ecuc is None:
            self._ecuc = _ecuc_index()
        return self._ecuc

    # -- helpers ---------------------------------------------------------------
    def _var(self, sid, step, name, role):
        if not isinstance(name, str) or name not in self.vars:
            self.err(sid, f"{role} variable '{name}' is not defined by an earlier step")
            return None
        v = self.vars[name]
        deps = step.setdefault("depends_on", [])
        if v["step"] not in deps:
            self.correct(sid, step, "depends_on", list(deps), deps + [v["step"]],
                         f"uses '{name}' defined in {v['step']}")
        return v

    def _class(self, sid, step):
        cls = step.get("class")
        if not cls:
            self.err(sid, "missing 'class'")
            return None
        if cls in self.classes:
            return cls
        cand = suggest(cls, self.classes, 3)
        if cand and difflib.SequenceMatcher(None, cls.lower(), cand[0].lower()).ratio() >= 0.8:
            self.correct(sid, step, "class", cls, cand[0], "unknown class; closest API class")
            return cand[0]
        self.err(sid, f"unknown class '{cls}'" + (f"; did you mean {cand}?" if cand else ""))
        return None

    def _method_map(self, cls, section):
        """Full (incl. common) {method: type} for references/attributes."""
        return {m["method"]: m["type"] for m in self.classes[cls].get(section, [])}

    # -- step checks -------------------------------------------------------------
    def check_new(self, sid, step):
        parent = self._var(sid, step, step.get("parent"), "parent")
        cls = self._class(sid, step)
        if not parent or not cls:
            return
        pcls = parent["class"]
        kids = self.classes.get(pcls, {}).get("children", [])
        method = step.get("method")
        match = next((k for k in kids if k["method"] == method), None)
        if match is None:
            by_type = [k for k in kids if k["returns"] == cls]
            if len(by_type) == 1:
                self.correct(sid, step, "method", method, by_type[0]["method"],
                             f"{pcls} creates {cls} via {by_type[0]['method']}")
                match = by_type[0]
            else:
                near = difflib.get_close_matches(method or "", [k["method"] for k in kids], 1, 0.85)
                if near and not by_type:
                    match = next(k for k in kids if k["method"] == near[0])
                    self.correct(sid, step, "method", method, near[0], "closest new_ method on parent")
                else:
                    alts = [f'{c["parentClass"]}.{c["method"]}' for c in creators(cls)][:8]
                    opts = [k["method"] for k in by_type]
                    self.err(sid, f"{pcls} has no method '{method}' creating {cls}"
                                  + (f"; candidates on parent: {opts}" if opts else "")
                                  + (f"; {cls} is created by: {alts}" if alts else ""))
                    return
        if match["returns"] != cls:
            self.correct(sid, step, "class", cls, match["returns"], f"{match['method']} returns {match['returns']}")
            cls = match["returns"]
        args = step.setdefault("args", {})
        if match.get("hasShortName", True) and not args.get("name"):
            self.err(sid, f"{match['method']} requires a shortName (args.name)")
        if not match.get("hasShortName", True) and args.get("name"):
            self.warn(sid, f"{match['method']} takes no shortName; args.name '{args['name']}' ignored")
            if self.fix:
                args.pop("name")
        if match.get("hasShortName", True) and args.get("name"):
            key = (step["parent"], args["name"])
            if key in self.names:
                self.err(sid, f"duplicate shortName '{args['name']}' under '{step['parent']}' (also {self.names[key]})")
            self.names[key] = sid
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", args["name"]):
                self.err(sid, f"shortName '{args['name']}' is not a valid AUTOSAR identifier")
        self._define(sid, step, cls)
        if cls in ECUC_VALUE_CLASSES or step.get("definition"):
            self.check_ecuc_value(sid, step, cls)

    def _define(self, sid, step, cls):
        var = step.get("var")
        if not var or not var.isidentifier() or keyword.iskeyword(var):
            self.err(sid, f"invalid or missing var '{var}'")
            return
        if var in RESERVED_VARS or var in self.enums or var in self.classes:
            self.err(sid, f"var '{var}' shadows a name used by the generated script; rename it (e.g. '{var}Val')")
            return
        if var in self.vars:
            self.err(sid, f"var '{var}' already defined in {self.vars[var]['step']}")
            return
        self.vars[var] = {"class": cls, "step": sid, "def_path": (step.get("definition") or {}).get("path")}

    def check_ref(self, sid, step, action):
        target = self._var(sid, step, step.get("target"), "target")
        if not target:
            return
        tcls = target["class"]
        refs = self._method_map(tcls, "references")
        method = step.get("method")
        if method not in refs:
            near = difflib.get_close_matches(method or "", list(refs), 1, 0.8)
            if near:
                self.correct(sid, step, "method", method, near[0], f"closest reference method on {tcls}")
                method = near[0]
            else:
                self.err(sid, f"{tcls} has no reference method '{method}'; available: {sorted(refs)}")
                return
        want = "add_ref" if method.startswith("add_") else "set_ref"
        if action != want:
            self.correct(sid, step, "action", action, want, f"{method} is a {want.split('_')[0]}_ method")
        val = (step.get("value") or {})
        if "var" not in val:
            self.err(sid, "reference value must be {\"var\": ...}")
            return
        v = self._var(sid, step, val["var"], "value")
        if v:
            ok = is_subclass(v["class"], refs[method])
            if ok is False:
                self.err(sid, f"{method} expects {refs[method]}, but '{val['var']}' is {v['class']}")
            elif ok is None:
                self.warn(sid, f"could not verify {v['class']} is a {refs[method]}")

    def check_attr(self, sid, step):
        target = self._var(sid, step, step.get("target"), "target")
        if not target:
            return
        tcls = target["class"]
        attrs = self._method_map(tcls, "attributes")
        method = step.get("method")
        if method not in attrs:
            near = difflib.get_close_matches(method or "", list(attrs), 1, 0.8)
            if near:
                self.correct(sid, step, "method", method, near[0], f"closest attribute method on {tcls}")
                method = near[0]
            else:
                self.err(sid, f"{tcls} has no attribute method '{method}'; available: {sorted(attrs)}")
                return
        self._check_value(sid, step, attrs[method], method)

    def _check_value(self, sid, step, expected, method):
        val = step.get("value") or {}
        if "enum" in val:
            raw = val["enum"].removeprefix("AF.")
            ename, _, lit = raw.partition(".")
            if expected in self.enums and ename != expected:
                self.correct(sid, val, "enum", val["enum"], f"{expected}.{lit}", f"{method} takes {expected}")
                ename = expected
            if ename not in self.enums:
                self.err(sid, f"unknown enum '{ename}'; did you mean {suggest(ename, self.enums, 3)}?")
                return
            if lit not in self.enums[ename]:
                near = difflib.get_close_matches(lit, self.enums[ename], 1, 0.75)
                if near:
                    self.correct(sid, val, "enum", val["enum"], f"{ename}.{near[0]}", "closest enum literal")
                else:
                    self.err(sid, f"'{lit}' not in {ename}: {self.enums[ename][:15]}")
        elif "literal" in val:
            if expected in self.enums:
                self.err(sid, f"{method} takes enum {expected}; use {{\"enum\": \"{expected}.<VALUE>\"}} "
                              f"from {self.enums[expected][:10]}")
            elif expected == "str" and not isinstance(val["literal"], str):
                self.warn(sid, f"{method} takes str; literal {val['literal']!r} will be passed as-is")
        else:
            self.err(sid, "set_attr needs value {\"literal\": ...} or {\"enum\": ...}")

    def check_set_value(self, sid, step):
        target = self._var(sid, step, step.get("target"), "target")
        if target and not hasattr(getattr(af_runtime(), target["class"], None), "set"):
            self.err(sid, f"{target['class']} has no set() method")
        if "literal" not in (step.get("value") or {}):
            self.err(sid, "set_value needs value {\"literal\": ...}")

    # -- ECUC ------------------------------------------------------------------------
    def check_ecuc_value(self, sid, step, cls):
        d = step.get("definition")
        if not d or not d.get("path"):
            self.err(sid, f"{cls} needs definition.path (from get_ecuc_container)")
            return
        info = self.ecuc.get(d["path"])
        if info is None:
            near = difflib.get_close_matches(d["path"], list(self.ecuc), 1, 0.9)
            if near:
                self.correct(sid, d, "path", d["path"], near[0], "closest ECUC definition path")
                info = self.ecuc[near[0]]
                if self.fix:
                    self.vars[step["var"]]["def_path"] = near[0]
            else:
                self.err(sid, f"ECUC definition path '{d['path']}' not found")
                return
        if d.get("type") != info["type"]:
            self.correct(sid, d, "type", d.get("type"), info["type"], "type from ecuc_param_def.json")
        expected_cls = srv()._DEF_TO_VALUE.get(info["type"])
        if expected_cls and expected_cls != cls:
            self.err(sid, f"definition {info['type']} needs value class {expected_cls}, plan uses {cls}")
        # parent/child consistency
        parent = self.vars.get(step.get("parent"), {})
        owner = info.get("owner") or (info["data"].get("path", "").rsplit("/", 1)[0] if info["kind"] == "container" else None)
        if parent.get("def_path") and owner and parent["def_path"] != owner:
            self.err(sid, f"'{d['path']}' does not belong under parent definition '{parent['def_path']}'")
        if step.get("parent"):
            self.children.setdefault(step["parent"], []).append(info["data"].get("path", d["path"]))
        # inline values
        val = step.get("value")
        data = info["data"]
        if val is None:
            if info["kind"] == "param":
                self.warn(sid, f"parameter {data['name']} has no value" +
                          (f" (default {data['default']})" if "default" in data else ""))
            return
        if info["kind"] == "reference":
            if "var" not in val:
                self.err(sid, "reference value must be {\"var\": <target container value>}")
            else:
                tgt = self._var(sid, step, val["var"], "reference target")
                if tgt and data.get("destination") and tgt.get("def_path") and tgt["def_path"] != data["destination"]:
                    self.warn(sid, f"reference destination is {data['destination']}, target var is {tgt['def_path']}")
            return
        lit = val.get("literal")
        if info["type"] == "EcucEnumerationParamDef":
            lits = data.get("literals", [])
            if lits and lit not in lits:
                near = difflib.get_close_matches(str(lit), lits, 1, 0.8)
                if near:
                    self.correct(sid, val, "literal", lit, near[0], "closest ECUC enum literal")
                else:
                    self.err(sid, f"'{lit}' not a literal of {data['name']}: {lits}")
        elif info["type"] in ("EcucIntegerParamDef", "EcucFloatParamDef"):
            try:
                num = float(lit)
            except (TypeError, ValueError):
                self.err(sid, f"{data['name']} needs a numeric value, got {lit!r}")
                return
            for bound, cmp in (("min", lambda a, b: a < b), ("max", lambda a, b: a > b)):
                try:
                    if bound in data and cmp(num, float(data[bound])):
                        self.err(sid, f"{data['name']}={lit} outside [{data.get('min')}, {data.get('max')}]")
                except ValueError:
                    pass  # non-numeric bound like INF

    def check_mandatory(self):
        for var, meta in self.vars.items():
            info = self.ecuc.get(meta.get("def_path") or "")
            if not info or info["kind"] not in ("module", "container"):
                continue
            created = set(self.children.get(var, []))
            if info["kind"] == "module":
                needed = [(c["name"], c.get("path"), c.get("multiplicity")) for c in info["data"].get("containers", [])]
            else:
                e = info["data"]
                needed = [(p["name"], p["path"], p.get("multiplicity")) for p in e["parameters"] + e["references"]]
                for sub in e["subContainers"]:
                    for s in srv()._ecuc_containers.get(sub, []):
                        if s["path"].rsplit("/", 1)[0] == e["path"]:
                            needed.append((sub, s["path"], s.get("multiplicity")))
            missing = [n for n, p, m in needed if _lower(m) > 0 and p not in created]
            if missing:
                self.warn(meta["step"], f"'{var}' is missing mandatory items: {missing}")

    # -- driver ----------------------------------------------------------------------------
    def run(self):
        p = self.plan
        if p.get("request_type") not in ("system", "ecuc"):
            self.err("-", "request_type must be 'system' or 'ecuc'")
        if not (p.get("output") or {}).get("arxml"):
            self.err("-", "output.arxml is required")
        steps = p.get("steps") or []
        if not steps:
            self.err("-", "plan has no steps")
        if p.get("request_type") == "ecuc" and not (p.get("inputs") or {}).get("ecuc_definition_arxmls"):
            self.warn("-", "no ecuc_definition_arxmls: generator will emit DEFINITION-REF post-processing")
        roots = 0
        for i, step in enumerate(steps):
            sid = step.get("id") or f"#{i + 1}"
            if sid in self.step_ids:
                self.err(sid, "duplicate step id")
            for dep in step.get("depends_on", []):
                if dep not in self.step_ids:
                    self.err(sid, f"depends_on '{dep}' is not an earlier step")
            self.step_ids.add(sid)
            action = step.get("action")
            if action not in ACTIONS:
                self.err(sid, f"unknown action '{action}'; expected one of {sorted(ACTIONS)}")
                continue
            if not step.get("description"):
                self.warn(sid, "missing description")
            if action == "root":
                roots += 1
                if step.get("class") != "ARPackage":
                    self.correct(sid, step, "class", step.get("class"), "ARPackage", "root is always ARPackage")
                if not (step.get("args") or {}).get("name"):
                    self.err(sid, "root needs args.name (root package name)")
                self._define(sid, step, "ARPackage")
            elif action == "get_node":
                cls = self._class(sid, step)
                if not (step.get("args") or {}).get("path", "").startswith("/"):
                    self.err(sid, "get_node needs an absolute args.path")
                if cls:
                    self._define(sid, step, cls)
            elif action == "new":
                self.check_new(sid, step)
            elif action in ("set_ref", "add_ref"):
                self.check_ref(sid, step, action)
            elif action == "set_attr":
                self.check_attr(sid, step)
            elif action == "set_value":
                self.check_set_value(sid, step)
        if roots == 0 and not (p.get("inputs") or {}).get("read_arxmls"):
            self.err("-", "plan needs a 'root' step (or inputs.read_arxmls + get_node steps)")
        if p.get("request_type") == "ecuc":
            self.check_mandatory()
        return {
            "valid": not self.errors,
            "errors": self.errors,
            "warnings": self.warnings,
            "corrections": self.corrections,
            "applied": self.fix,
            "stats": {"steps": len(steps), "variables": len(self.vars)},
        }


def validate_plan(plan, fix: bool = False, out: str | None = None) -> dict:
    """
    plan: dict, JSON string or path to a plan file.
    fix:  apply unambiguous corrections. When plan came from a file, the corrected
          plan is written back to it (or to `out`); the corrected plan is always
          returned under "plan" when fixes were applied.
    """
    plan_obj, src_path = load_plan(plan)
    if fix:
        plan_obj = copy.deepcopy(plan_obj)
    report = Validator(plan_obj, fix).run()
    if fix and report["corrections"]:
        # Re-validate the corrected plan so the report reflects the final state.
        final = Validator(plan_obj, False).run()
        final["corrections"] = report["corrections"]
        final["applied"] = True
        final["plan"] = plan_obj
        target = out or src_path
        if target:
            pathlib.Path(target).write_text(json.dumps(plan_obj, indent=2, ensure_ascii=False), encoding="utf-8")
            final["written_to"] = str(target)
        report = final
    return report
