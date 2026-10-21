# AUTOSAR modelling plan — JSON schema (v1)

The contract between `autosar-plan` (producer) and `autosar-generate` (consumer).
The `validate_plan` tool enforces everything below.

## Top level

```json
{
  "schema_version": 1,
  "request_type": "system",            // "system" | "ecuc"
  "title": "SR interface VehicleSpeed between two SWCs",
  "request": "<the user's original request, verbatim>",
  "output": {
    "arxml": "Examples/generated/vehicle_speed.arxml",   // file the script writes
    "script": "Examples/generated/gen_vehicle_speed.py", // file autosar-generate writes
    "root_package": "VehicleSpeed"                        // AF.new_file(defaultArPackage=...)
  },
  "inputs": {
    "read_arxmls": [],                 // existing arxml to load first (modify workflow), optional
    "ecuc_definition_arxmls": []       // ECUC only: module-definition arxml(s); [] => DEFINITION-REF post-processing
  },
  "assumptions": ["uint8 is used as the implementation data type"],
  "mcp_connectivity": { },             // copied verbatim from gather_context.py output
  "steps": [ /* ordered, see below */ ]
}
```

## Steps

Every step has `id` (`"S1"`, `"S2"`, …, unique), `action`, `description` (one line,
becomes the section comment in the generated script) and `depends_on` (ids of earlier
steps that define any variable this step uses). Steps run strictly in list order.

| action      | required fields                                        | generated code                                   |
|-------------|--------------------------------------------------------|--------------------------------------------------|
| `root`      | `var`, `class: "ARPackage"`, `args.name`               | `var = AF.new_file(output.arxml, defaultArPackage=args.name, overWrite=True)` |
| `get_node`  | `var`, `class`, `args.path`                            | `var = AF.get_node(args.path)` (+ None check)    |
| `new`       | `var`, `class`, `parent`, `method`, `args.name` if the method takes a name | `var = parent.method('name')` / `var = parent.method()` |
| `set_ref`   | `target`, `method`, `value: {"var": "x"}`              | `target.method(x)`                               |
| `add_ref`   | `target`, `method`, `value: {"var": "x"}`              | `target.method(x)`                               |
| `set_attr`  | `target`, `method`, `value`                            | `target.method(<value>)`                         |
| `set_value` | `target`, `value` (method is always `set`)             | `target.set(<value>)` — numerical/limit value objects |

`value` forms:
- `{"var": "srIf"}` — another plan variable
- `{"literal": 8}` / `{"literal": "unsigned char"}` — Python literal
- `{"enum": "ByteOrderEnum.VALUE_MOST_SIGNIFICANT_BYTE_LAST"}` — written as `AF.ByteOrderEnum.VALUE_...` (never quoted)

`var` names are Python identifiers, unique across the plan. `class` is the exact
autosarfactory class name of the object the step produces.

## ECUC extras

On `new` steps that create `EcucModuleConfigurationValues`, `EcucContainerValue`,
`Ecuc*ParamValue` or `EcucReferenceValue`, add:

```json
"definition": {"path": "/AUTOSAR/EcucDefs/Os/OsTask/OsTaskPriority", "type": "EcucIntegerParamDef"}
```

`path` and `type` come from `get_ecuc_container()` output — never hand-built.

Parameter values may carry their value inline on the `new` step instead of a separate step:

```json
{"id": "S7", "action": "new", "var": "osTaskPrio", "class": "EcucNumericalParamValue",
 "parent": "osTask1", "method": "new_EcucNumericalParamValue",
 "definition": {"path": "/AUTOSAR/EcucDefs/Os/OsTask/OsTaskPriority", "type": "EcucIntegerParamDef"},
 "value": {"literal": 5}, "depends_on": ["S6"], "description": "OsTaskPriority = 5"}
```

- `EcucNumericalParamValue` → `p.new_Value().set(v)` (booleans as `1`/`0` or `true`/`false` per the def)
- `EcucTextualParamValue`  → `p.set_value("LITERAL")` (enumeration literals must come from `get_ecuc_param_literals`)
- `EcucReferenceValue`     → `value: {"var": "<target container value var>"}` → `r.set_value(target)`

## Example (system)

```json
{"id": "S1", "action": "root", "var": "pkg", "class": "ARPackage", "args": {"name": "VehicleSpeed"}, "depends_on": [], "description": "Root package"},
{"id": "S2", "action": "new", "var": "ifPkg", "class": "ARPackage", "parent": "pkg", "method": "new_ARPackage", "args": {"name": "Interfaces"}, "depends_on": ["S1"], "description": "Interfaces package"},
{"id": "S3", "action": "new", "var": "srIf", "class": "SenderReceiverInterface", "parent": "ifPkg", "method": "new_SenderReceiverInterface", "args": {"name": "SrIf_VehicleSpeed"}, "depends_on": ["S2"], "description": "SR interface"},
{"id": "S4", "action": "set_ref", "target": "pPort", "method": "set_providedInterface", "value": {"var": "srIf"}, "depends_on": ["S3", "S9"], "description": "Port -> interface"}
```
