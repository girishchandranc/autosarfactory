"""
Gather the live autosarfactory API context needed to write a plan in one call,
instead of many individual lookups.

gather_context("system", use_cases=[...], elements=[...], enums=[...])
gather_context("ecuc", modules=[...], containers=[...], depth=1)
Both results start with an explicit `mcp_connectivity` block.
"""

import re

from . import srv
from .af_api import all_classes, all_enums, connectivity, creators, suggest


def _lower_bound(mult) -> int:
    m = re.match(r"\s*(\d+)", str(mult or "0"))
    return int(m.group(1)) if m else 0


def _enum_preview(name: str, limit: int = 12):
    vals = all_enums()[name]
    if len(vals) <= limit:
        return vals
    return vals[:limit] + [f"... {len(vals) - limit} more - get_enum('{name}')"]


def _class_summary(name: str) -> dict:
    if name not in all_classes():
        out = {"error": f"Class '{name}' not found", "did_you_mean": suggest(name, all_classes())}
        enums = suggest(name, all_enums())
        if enums:
            out["matching_enums"] = enums
        return out
    c = srv().get_class(name, "all")
    out = {"hasShortName": c.get("hasShortName"),
           "references": c.get("references", {}),
           "attributes": {k: v for k, v in c.get("attributes", {}).items()
                          if k not in ("set_uuid", "set_shortName")}}
    chain = srv().find_creation_chain(name)
    out["creation_chain"] = [f'{s["createdBy"]}.{s["method"]}({"name" if s["hasName"] else ""}) -> {s["element"]}'
                             for s in chain.get("chain", [])]
    if chain.get("ambiguous_elements"):
        out["ambiguous_parents"] = {e: sorted({c["parentClass"] for c in creators(e)})[:12]
                                    for e in chain["ambiguous_elements"]}
    enums = sorted({t for t in out["attributes"].values() if t in all_enums()})
    if enums:
        out["enum_attributes"] = {e: _enum_preview(e) for e in enums}
    return out


def system_context(use_cases: list, elements: list, enums: list) -> dict:
    ctx = {}
    if use_cases:
        ctx["element_map"] = {u: srv().get_system_element_map(u) for u in use_cases}
    else:
        ctx["element_map_use_cases"] = srv().get_system_element_map("").get("use_cases", [])
    ctx["classes"] = {e: _class_summary(e) for e in elements}
    if enums:
        ctx["enums"] = {e: srv().get_enum(e) for e in enums}
    return ctx


def _container_detail(entry: dict) -> dict:
    """Full (not lean) container detail including constraints - the plan needs min/max/default."""
    def p(item):
        d = {k: item[k] for k in ("name", "type", "path", "valueClass", "multiplicity") if k in item}
        d["mandatory"] = _lower_bound(item.get("multiplicity")) > 0
        for k in ("min", "max", "default", "destination"):
            if k in item:
                d[k] = item[k]
        if item.get("type") == "EcucEnumerationParamDef":
            d["literals"] = item.get("literals", [])
        return d
    return {
        "path": entry["path"], "type": entry["type"], "valueClass": entry["valueClass"],
        "multiplicity": entry.get("multiplicity"),
        "mandatory": _lower_bound(entry.get("multiplicity")) > 0,
        "parent": entry["parent"], "parentType": entry["parentType"],
        "create_with": ("moduleValue.new_Container(name)"
                        if entry["parentType"] == "EcucModuleDef"
                        else "parentContainer.new_SubContainer(name)"),
        "parameters": [p(x) for x in entry["parameters"]],
        "references": [p(x) for x in entry["references"]],
        "subContainers": entry["subContainers"],
    }


def ecuc_context(modules: list, containers: list, depth: int) -> dict:
    ctx = {"value_class_api": {
        "EcucModuleConfigurationValues": "arPkg.new_EcucModuleConfigurationValues(name); .set_definition(EcucModuleDef); .set_implementationConfigVariant(AF.EcucConfigurationVariantEnum.VALUE_...)",
        "EcucContainerValue": "module.new_Container(name) | container.new_SubContainer(name); .set_definition(EcucContainerDef)",
        "EcucNumericalParamValue": "container.new_EcucNumericalParamValue(); .set_definition(def); .new_Value().set(v)",
        "EcucTextualParamValue": "container.new_EcucTextualParamValue(); .set_definition(def); .set_value(str)",
        "EcucReferenceValue": "container.new_EcucReferenceValue(); .set_definition(def); .set_value(targetContainerValue)",
        "EcucConfigurationVariantEnum": all_enums().get("EcucConfigurationVariantEnum", []),
    }}
    mods = {}
    for m in modules:
        info = srv().get_ecuc_module(m)
        if "error" in info:
            mods[m] = info
            continue
        mod_raw = srv()._ecuc_modules[m]
        info["path"] = mod_raw.get("path")
        info["type"] = mod_raw.get("type", "EcucModuleDef")
        mods[m] = info
    ctx["modules"] = mods

    # Containers: explicitly requested ones, else all mandatory top-level ones of each module.
    wanted = [(c, "") for c in containers]
    if not containers:
        for m, info in mods.items():
            for c in info.get("containers", []):
                wanted.append((c["name"], m))
    out, seen = {}, set()
    frontier = [(c, m, 0) for c, m in wanted]
    while frontier:
        name, mod, d = frontier.pop(0)
        if (name, mod) in seen:
            continue
        seen.add((name, mod))
        matches = srv()._ecuc_containers.get(name)
        if not matches:
            out[name] = {"error": f"Container '{name}' not found",
                         "similar": [k for k in srv()._ecuc_containers if name.lower() in k.lower()][:8]}
            continue
        if mod or modules:
            filt = [x for x in matches if x["module"] == mod or (not mod and x["module"] in modules)]
            matches = filt or matches
        details = [_container_detail(x) for x in matches]
        out[name] = details[0] if len(details) == 1 else details
        if d < depth:
            for det in details:
                for sub in det["subContainers"]:
                    frontier.append((sub, mod or matches[0]["module"], d + 1))
    ctx["containers"] = out
    return ctx


def gather_context(request_type: str, use_cases: list | None = None, elements: list | None = None,
                   enums: list | None = None, modules: list | None = None,
                   containers: list | None = None, depth: int = 1) -> dict:
    result = {"mcp_connectivity": connectivity()}
    if request_type == "system":
        result.update(system_context(use_cases or [], elements or [], enums or []))
    elif request_type == "ecuc":
        result.update(ecuc_context(modules or [], containers or [], depth))
    else:
        result["error"] = "request_type must be 'system' or 'ecuc'"
    return result
