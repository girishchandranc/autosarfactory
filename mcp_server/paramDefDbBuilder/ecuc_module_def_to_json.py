"""
ecuc_module_def_to_json.py

Reads one or more AUTOSAR ECUC module definition arxml files and outputs a JSON
representation of the module -> container -> parameter / reference hierarchy.

Usage:
    python ecuc_module_def_to_json.py <file.arxml> [<file2.arxml> ...]
    python ecuc_module_def_to_json.py <folder/> -o out.json
    python ecuc_module_def_to_json.py <file.arxml> --module CanIf

Updating an existing JSON (merge mode):
    python ecuc_module_def_to_json.py <file.arxml> --update ecuc_param_def.json

    Modules found in the arxml replace their counterpart in the existing JSON
    by name.  Modules present in the existing JSON but absent from the arxml
    are left untouched.  New modules are appended.  The result is written back
    to the same file (use -o to redirect to a different file).
"""

from autosarfactory import autosarfactory as AF
import json
import argparse
import sys


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe(obj, *method_names, default=None):
    """
    Try each method name in order; return the first successful non-None result.
    Silently returns `default` if none of the methods exist or all raise.
    """
    for name in method_names:
        fn = getattr(obj, name, None)
        if fn is None:
            continue
        try:
            value = fn()
            if value is not None:
                return value
        except Exception:
            continue
    return default


def _multiplicity(node):
    lower: AF.PositiveIntegerValueVariationPoint = _safe(node, "get_lowerMultiplicity")
    upper: AF.PositiveIntegerValueVariationPoint = _safe(node, "get_upperMultiplicity")
    if lower is None and upper is None:
        return None
    min = str(lower.get()) if lower is not None else "0"
    max = str(upper.get()) if upper is not None else "*"
    return f"{min}:{max}"


# ---------------------------------------------------------------------------
# Parameter / reference serialisers
# ---------------------------------------------------------------------------

def _param_to_dict(param):
    info = {
        "name": param.name,
        "type": type(param).__name__,
        "path": param.path,
    }
    default = _safe(param, "get_defaultValue")
    if default is not None:
        info["default"] = default.get() if isinstance(default, AF.UnlimitedIntegerValueVariationPoint) else str(default)

    # Numeric range (INTEGER / FLOAT)
    lo: AF.UnlimitedIntegerValueVariationPoint = _safe(param, "get_min")
    hi: AF.UnlimitedIntegerValueVariationPoint = _safe(param, "get_max")
    if lo is not None:
        info["min"] = lo.get()
    if hi is not None:
        info["max"] = hi.get()

    # Enumeration literals
    literals = _safe(param, "get_literals") or []
    if literals:
        info["literals"] = [lit.name for lit in literals]

    mult = _multiplicity(param)
    if mult:
        info["multiplicity"] = mult

    return info


def _ref_to_dict(ref):
    info = {
        "name": ref.name,
        "type": type(ref).__name__,
        "path": ref.path,
    }

    dest_obj = _safe(ref, "get_destinationType") if isinstance(ref, AF.EcucForeignReferenceDef) else _safe(ref, "get_destination")
    if dest_obj is not None:
        # Keep full /AUTOSAR/EcucDefs/... path — used directly as definitionRef target
        raw = dest_obj.path if isinstance(ref, AF.EcucReferenceDef) else str(dest_obj)
        info["destination"] = raw

    mult = _multiplicity(ref)
    if mult:
        info["multiplicity"] = mult

    return info


# ---------------------------------------------------------------------------
# Container serialiser (recursive)
# ---------------------------------------------------------------------------

def _container_to_dict(container):
    result = {
        "name": container.name,
        "type": type(container).__name__,
        "path": container.path,
        "parameters": [],
        "references": [],
        "subContainers": [],
    }

    mult = _multiplicity(container)
    if mult:
        result["multiplicity"] = mult

    # Parameters — EcucParamConfContainerDef exposes these
    params = _safe(container, "get_parameters", "get_parameterDef") or []
    for p in params:
        result["parameters"].append(_param_to_dict(p))

    # References
    refs = _safe(container, "get_references", "get_referenceDef") or []
    for r in refs:
        result["references"].append(_ref_to_dict(r))

    # Sub-containers — EcucParamConfContainerDef uses subContainers;
    # EcucChoiceContainerDef uses choices
    subs = _safe(container, "get_subContainers", "get_containers", "get_choices") or []
    for sub in subs:
        result["subContainers"].append(_container_to_dict(sub))

    return result


# ---------------------------------------------------------------------------
# Module serialiser
# ---------------------------------------------------------------------------

def _module_to_dict(module):
    result = {
        "name": module.name,
        "type": "EcucModuleDef",
        "path": module.path,
        "containers": [],
    }

    containers = _safe(module, "get_containers") or []
    for c in containers:
        result["containers"].append(_container_to_dict(c))

    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Export AUTOSAR ECUC module definitions to JSON."
    )
    parser.add_argument(
        "input", nargs="+",
        help="Input arxml file(s) or folder(s) containing arxml files."
    )
    parser.add_argument(
        "-o", "--output", default=None,
        help="Write JSON to this file (default: print to stdout)."
    )
    parser.add_argument(
        "--module", default=None,
        help="Export only the named module (default: all modules)."
    )
    parser.add_argument(
        "--update", default=None, metavar="EXISTING_JSON",
        help=(
            "Merge into an existing JSON file instead of starting fresh. "
            "Modules found in the arxml replace their counterpart by name; "
            "all other modules in the existing file are preserved. "
            "The result is written back to EXISTING_JSON unless -o is also given."
        )
    )
    parser.add_argument(
        "--pretty", action="store_true", default=True,
        help="Pretty-print JSON (default: True)."
    )
    args = parser.parse_args()

    root, status = AF.read(files=args.input)
    if not status:
        print("ERROR: Failed to read input file(s).", file=sys.stderr)
        sys.exit(1)

    modules = AF.get_all_instances(root, AF.EcucModuleDef)
    if not modules:
        print("No EcucModuleDef elements found in the provided files.", file=sys.stderr)
        sys.exit(1)

    if args.module:
        modules = [m for m in modules if m.name == args.module]
        if not modules:
            print(f"No module named '{args.module}' found.", file=sys.stderr)
            sys.exit(1)

    new_modules = [_module_to_dict(m) for m in modules]

    if args.update:
        import pathlib
        update_path = pathlib.Path(args.update)
        if not update_path.exists():
            print(f"ERROR: --update file not found: {update_path}", file=sys.stderr)
            sys.exit(1)
        existing = json.loads(update_path.read_text(encoding="utf-8"))
        new_by_name = {m["name"]: m for m in new_modules}
        merged = [new_by_name.pop(m["name"], m) for m in existing.get("modules", [])]
        # append any modules from the arxml not already present in the existing JSON
        merged.extend(new_by_name.values())
        output = {"modules": merged}
        destination = args.output or args.update
        added   = [m["name"] for m in new_modules if m["name"] not in {e["name"] for e in existing.get("modules", [])}]
        updated = [m["name"] for m in new_modules if m["name"] in {e["name"] for e in existing.get("modules", [])}]
        print(f"Merged: {len(updated)} module(s) updated, {len(added)} module(s) added.", file=sys.stderr)
    else:
        output = {"modules": new_modules}
        destination = args.output

    indent = 2 if args.pretty else None
    json_str = json.dumps(output, indent=indent, ensure_ascii=False)

    if destination:
        with open(destination, "w", encoding="utf-8") as f:
            f.write(json_str)
        print(f"Written to {destination}", file=sys.stderr)
    else:
        print(json_str)


if __name__ == "__main__":
    main()
