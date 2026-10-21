"""Evals for the plan/generate workflow MCP tools and prompts."""

import subprocess
import sys


# --- detect_request_type ----------------------------------------------------

def test_detect_system(srv):
    res = srv.detect_request_type("Create a sender-receiver interface between two SWCs with ports")
    assert res["type"] == "system" and res["confidence"] >= 0.7


def test_detect_ecuc(srv):
    res = srv.detect_request_type("Configure the Os module with two OsTask containers and an OsAlarm")
    assert res["type"] == "ecuc"
    assert "Os" in res["ecuc_modules"]
    assert "OsTask" in res["signals"]["ecuc_containers"]


def test_detect_unknown(srv):
    assert srv.detect_request_type("hello there")["type"] == "unknown"


# --- gather_modelling_context -------------------------------------------------

def test_gather_system_context(srv):
    res = srv.gather_modelling_context("system", elements=["PPortPrototype", "SenderRecieverInterface"])
    assert res["mcp_connectivity"]["api_db"]["loaded"]
    pp = res["classes"]["PPortPrototype"]
    assert any("new_PPortPrototype" in c for c in pp["creation_chain"])
    assert "ApplicationSwComponentType" in pp["ambiguous_parents"]["PPortPrototype"]
    # misspelled name must come back with suggestions, never silently missing
    assert "SenderReceiverInterface" in res["classes"]["SenderRecieverInterface"]["did_you_mean"]


def test_gather_ecuc_context(srv):
    res = srv.gather_modelling_context("ecuc", modules=["Os"], containers=["OsTask"], depth=0)
    task = res["containers"]["OsTask"]
    prio = next(p for p in task["parameters"] if p["name"] == "OsTaskPriority")
    assert prio["mandatory"] and prio["min"] == "0"
    sched = next(p for p in task["parameters"] if p["name"] == "OsTaskSchedule")
    assert sched["literals"] == ["FULL", "NON"]


def test_gather_bad_type(srv):
    assert "error" in srv.gather_modelling_context("nonsense")


# --- get_plan_schema / prompts --------------------------------------------------

def test_plan_schema_served(srv):
    schema = srv.get_plan_schema()
    assert "request_type" in schema and "set_ref" in schema and "DEFINITION-REF" in schema.upper()


def test_prompts_substitute_arguments(srv):
    text = srv.autosar_plan_prompt("Model a CAN network")
    assert "Model a CAN network" in text and "{{REQUEST}}" not in text
    text = srv.autosar_generate_prompt("")
    assert "{{PLAN}}" not in text


# --- validate_plan -----------------------------------------------------------------

def test_validate_good_plan(srv, system_plan):
    res = srv.validate_plan(system_plan)
    assert res["valid"] and not res["errors"]


def test_validate_autocorrects(srv, system_plan):
    system_plan["steps"][1]["class"] = "SenderRecieverInterface"       # typo -> corrected
    system_plan["steps"][2]["method"] = "new_DataElements"             # wrong method -> corrected
    res = srv.validate_plan(system_plan, fix=True)
    assert res["valid"]
    fixed = {(c["field"], c["to"]) for c in res["corrections"]}
    assert ("class", "SenderReceiverInterface") in fixed
    assert ("method", "new_DataElement") in fixed


def test_validate_catches_wrong_parent_and_type(srv, system_plan):
    system_plan["steps"].append({"id": "S4", "action": "set_ref", "target": "de", "method": "set_type",
                                 "value": {"var": "srIf"}, "depends_on": ["S3"], "description": "bad type"})
    res = srv.validate_plan(system_plan)
    assert not res["valid"] and any("set_type expects" in e["msg"] for e in res["errors"])


def test_validate_ecuc_constraints(srv, ecuc_plan):
    ecuc_plan["steps"][3]["value"] = {"literal": -1}  # below OsTaskPriority min
    res = srv.validate_plan(ecuc_plan)
    assert not res["valid"] and any("outside" in e["msg"] for e in res["errors"])


def test_validate_missing_file_is_graceful(srv):
    res = srv.validate_plan("C:/does/not/exist.plan.json")
    assert res["valid"] is False and "could not load plan" in res["errors"][0]["msg"]


# --- render_script_draft + end-to-end execution ----------------------------------------

def _run(script_path):
    return subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True, timeout=300)


def test_render_and_execute_system(srv, system_plan, tmp_path):
    res = srv.render_script_draft(system_plan, draft_path=str(tmp_path / "gen.py"))
    assert res["mode"] == "system_new"
    proc = _run(tmp_path / "gen.py")
    assert proc.returncode == 0, proc.stderr
    verify = srv.verify_arxml(system_plan["output"]["arxml"], system_plan)
    assert verify["ok"] and not verify["missing_from_plan"]


def test_render_and_execute_ecuc_defref(srv, ecuc_plan, tmp_path):
    res = srv.render_script_draft(ecuc_plan, draft_path=str(tmp_path / "gen_os.py"))
    assert res["mode"] == "ecuc_defref_postprocess"
    assert any("do NOT call set_definition" in r for r in res["rules"])
    proc = _run(tmp_path / "gen_os.py")
    assert proc.returncode == 0, proc.stderr
    verify = srv.verify_arxml(ecuc_plan["output"]["arxml"], ecuc_plan)
    assert verify["ok"] and verify["definition_refs"] == 3


def test_render_mode_ecuc_with_defs(srv, ecuc_plan):
    ecuc_plan["inputs"]["ecuc_definition_arxmls"] = ["defs.arxml"]
    res = srv.render_script_draft(ecuc_plan, summary=True)
    assert res["mode"] == "ecuc_with_defs"
    assert "set_definition(_def(" in res["script"]


# --- check_generated_script --------------------------------------------------------------

def test_check_catches_quoted_enum_and_bare_save(srv, ecuc_plan):
    res = srv.render_script_draft(ecuc_plan, summary=True)
    bad = res["script"].replace("AF.save([OUTPUT_ARXML])", "AF.save()")
    bad = bad.replace("prio.new_Value().set(3)",
                      'osVal.set_implementationConfigVariant("EcucConfigurationVariantEnum.VALUE_VARIANT_PRE_COMPILE")')
    report = srv.check_generated_script(bad, ecuc_plan)
    assert not report["ok"]
    msgs = " | ".join(report["errors"])
    assert "quoted enum" in msgs and "AF.save([OUTPUT_ARXML])" in msgs


def test_check_catches_invented_method(srv):
    src = ("from autosarfactory import autosarfactory as AF\n"
           "pkg = AF.new_file('x.arxml', defaultArPackage='P', overWrite=True)\n"
           "pkg.new_TotallyMadeUpElement('x')\n"
           "AF.save()\n")
    report = srv.check_generated_script(src)
    assert not report["ok"] and any("new_TotallyMadeUpElement" in e for e in report["errors"])


def test_verify_detects_missing_elements(srv, system_plan, tmp_path):
    srv.render_script_draft(system_plan, draft_path=str(tmp_path / "gen.py"), summary=True)
    assert _run(tmp_path / "gen.py").returncode == 0
    system_plan["steps"].append({"id": "S9", "action": "new", "var": "ghost",
                                 "class": "ApplicationSwComponentType", "parent": "pkg",
                                 "method": "new_ApplicationSwComponentType", "args": {"name": "GhostSwc"},
                                 "depends_on": ["S1"], "description": "never generated"})
    verify = srv.verify_arxml(system_plan["output"]["arxml"], system_plan)
    assert verify["ok"] is False and verify["missing_from_plan"] == ["GhostSwc"]
