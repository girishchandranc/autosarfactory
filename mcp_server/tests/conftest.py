"""
Pytest fixtures for the autosarfactory MCP server evals.

The server module is loaded through the offline CLI loader (FastMCP stubbed),
so the suite runs even where the `mcp` package is missing or broken - the tools
under test are plain functions.
"""

import pathlib
import sys

import pytest

MCP_SERVER_DIR = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = MCP_SERVER_DIR.parent
sys.path.insert(0, str(MCP_SERVER_DIR))

from autosarfactory_mcp.cli import load_server  # noqa: E402


@pytest.fixture(scope="session")
def srv():
    """The server module with every tool callable as a plain function."""
    return load_server()


@pytest.fixture()
def system_plan(tmp_path):
    """A small, valid system-model plan writing into tmp_path."""
    return {
        "schema_version": 1, "request_type": "system", "title": "test", "request": "test",
        "output": {"arxml": str(tmp_path / "out.arxml"), "script": str(tmp_path / "gen.py"),
                   "root_package": "TestPkg"},
        "inputs": {"read_arxmls": [], "ecuc_definition_arxmls": []},
        "assumptions": [],
        "steps": [
            {"id": "S1", "action": "root", "var": "pkg", "class": "ARPackage",
             "args": {"name": "TestPkg"}, "depends_on": [], "description": "root"},
            {"id": "S2", "action": "new", "var": "srIf", "class": "SenderReceiverInterface",
             "parent": "pkg", "method": "new_SenderReceiverInterface", "args": {"name": "SrIf"},
             "depends_on": ["S1"], "description": "interface"},
            {"id": "S3", "action": "new", "var": "de", "class": "VariableDataPrototype",
             "parent": "srIf", "method": "new_DataElement", "args": {"name": "Speed"},
             "depends_on": ["S2"], "description": "data element"},
        ],
    }


@pytest.fixture()
def ecuc_plan(tmp_path):
    """A small, valid ECUC plan (no definition arxml -> DEFINITION-REF post-processing)."""
    return {
        "schema_version": 1, "request_type": "ecuc", "title": "test", "request": "test",
        "output": {"arxml": str(tmp_path / "os.arxml"), "script": str(tmp_path / "gen_os.py"),
                   "root_package": "EcucConfig"},
        "inputs": {"read_arxmls": [], "ecuc_definition_arxmls": []},
        "assumptions": [],
        "steps": [
            {"id": "S1", "action": "root", "var": "pkg", "class": "ARPackage",
             "args": {"name": "EcucConfig"}, "depends_on": [], "description": "root"},
            {"id": "S2", "action": "new", "var": "osVal", "class": "EcucModuleConfigurationValues",
             "parent": "pkg", "method": "new_EcucModuleConfigurationValues", "args": {"name": "Os"},
             "definition": {"path": "/AUTOSAR/EcucDefs/Os", "type": "EcucModuleDef"},
             "depends_on": ["S1"], "description": "Os module"},
            {"id": "S3", "action": "new", "var": "task1", "class": "EcucContainerValue",
             "parent": "osVal", "method": "new_Container", "args": {"name": "Task_10ms"},
             "definition": {"path": "/AUTOSAR/EcucDefs/Os/OsTask", "type": "EcucParamConfContainerDef"},
             "depends_on": ["S2"], "description": "task"},
            {"id": "S4", "action": "new", "var": "prio", "class": "EcucNumericalParamValue",
             "parent": "task1", "method": "new_EcucNumericalParamValue",
             "definition": {"path": "/AUTOSAR/EcucDefs/Os/OsTask/OsTaskPriority", "type": "EcucIntegerParamDef"},
             "value": {"literal": 3}, "depends_on": ["S3"], "description": "priority"},
        ],
    }
