"""Evals for the API-lookup MCP tools (the original server surface)."""


def test_find_creation_chain_can_signal(srv):
    res = srv.find_creation_chain("ISignalTriggering")
    chain = [s["element"] for s in res["chain"]]
    assert chain[0] == "CanCluster", "chain must start below ARPackage, not with a spurious ARPackage self-step"
    assert chain[-1] == "ISignalTriggering"
    assert "ISignalTriggering" in res.get("ambiguous_elements", []), "multi-parent element must be flagged"


def test_find_creation_chain_root_is_arpackage(srv):
    res = srv.find_creation_chain("ARPackage")
    assert "info" in res and "AF.new_file" in res["info"]


def test_find_creation_chain_ecuc_value(srv):
    res = srv.find_creation_chain("EcucNumericalParamValue")
    pairs = [(s["createdBy"], s["method"]) for s in res["chain"]]
    assert ("EcucModuleConfigurationValues", "new_Container") in pairs
    assert ("EcucContainerValue", "new_EcucNumericalParamValue") in pairs


def test_find_creators_of_unknown_gives_hints(srv):
    res = srv.find_creators_of("NoSuchClass")
    assert "info" in res[0] and res[0].get("hints")


def test_get_class_sections(srv):
    refs = srv.get_class("PPortPrototype", "references")["references"]
    assert refs == {"set_providedInterface": "PortInterface"}
    attrs = srv.get_class("EcucTextualParamValue", "attributes")["attributes"]
    assert attrs.get("set_value") == "str"


def test_get_class_unknown_suggests_similar(srv):
    res = srv.get_class("SenderReceiver", "all")
    assert "error" in res and "SenderReceiverInterface" in res["similar"]


def test_search_classes(srv):
    assert "CanFrameTriggering" in srv.search_classes("CanFrame")


def test_get_enum_values_are_expressions(srv):
    res = srv.get_enum("EcucConfigurationVariantEnum")
    assert "EcucConfigurationVariantEnum.VALUE_VARIANT_PRE_COMPILE" in res["values"]


def test_get_enum_unknown_suggests(srv):
    res = srv.get_enum("ConfigurationVariant")
    assert "error" in res and any("EcucConfigurationVariantEnum" in s for s in res["similar"])


def test_element_map_lists_use_cases(srv):
    cases = srv.get_system_element_map("")["use_cases"]
    assert any("Sender-Receiver" in c for c in cases)


def test_element_map_resolves_dependencies(srv):
    res = srv.get_system_element_map("Send signal from SWC over CAN bus")
    sections = res.get("sections", {})
    assert any("Sender-Receiver" in t for t in sections), "prerequisite section must be merged in"


def test_ecuc_modules_loaded(srv):
    mods = srv.list_ecuc_modules()
    assert "Os" in mods and "CanIf" in mods and len(mods) > 50


def test_get_ecuc_container_value_classes(srv):
    entry = srv.get_ecuc_container("OsTask", "Os")[0]
    assert entry["valueClass"] == "EcucContainerValue"
    assert entry["parentValueClass"] == "EcucModuleConfigurationValues"
    prio = next(p for p in entry["parameters"] if p["name"] == "OsTaskPriority")
    assert prio["valueClass"] == "EcucNumericalParamValue"
    assert prio["path"] == "/AUTOSAR/EcucDefs/Os/OsTask/OsTaskPriority"


def test_get_ecuc_param_literals(srv):
    res = srv.get_ecuc_param_literals("/AUTOSAR/EcucDefs/Os/OsTask/OsTaskSchedule")
    assert sorted(res["literals"]) == ["FULL", "NON"]


def test_script_templates(srv):
    t = srv.new_file_script_template("MyPkg", "out.arxml")
    assert "AF.new_file(" in t and "defaultArPackage='MyPkg'" in t
    t = srv.read_file_script_template(["in.arxml"])
    assert "AF.read(files=" in t
