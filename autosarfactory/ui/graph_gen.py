import json, os
from enum import Enum
from autosarfactory import autosarfactory

# Types to skip when walking children
_SKIP_TYPES = (
    autosarfactory.EcucParameterValue,
    autosarfactory.MultiLanguageOverviewParagraph,
    autosarfactory.MultilanguageLongName,
    autosarfactory.AttributeValueVariationPoint,
    autosarfactory.DocumentationBlock,
    autosarfactory.AdminData,
    autosarfactory.EcucValueConfigurationClass,
    autosarfactory.EcucMultiplicityConfigurationClass,
    autosarfactory.ValueSpecification,
)


def __scalar_props(node) -> dict:
    props = {}
    if isinstance(node, autosarfactory.EcucContainerValue):
        params = [p for p in node.get_parameterValues() if (p.get_value() is not None and p.get_definition_as_string() is not None)]
        for p in params:
            value = ''
            if isinstance(p, autosarfactory.EcucTextualParamValue):
                value = p.get_value()
            elif isinstance(p, autosarfactory.EcucNumericalParamValue):
                value = p.get_value().get()
            props[p.get_definition_as_string().split("/")[-1]] = value
    else:
        for k, v in node.get_property_values().items():
            if k in ('File', 'ShortName'):
                continue
            if isinstance(v, (str, int, float, bool)) and v != '':
                props[k] = v
            elif isinstance(v, Enum):
                props[k] = v.literal
    return props


def __node_label(node) -> str:
    if node.name:
        return node.name
    # EcucReferenceValue etc. — use the definition's last segment as a readable label
    if isinstance(node, autosarfactory.EcucAbstractReferenceValue):
        defn = node.get_definition_as_string()
        if defn:
            return defn.split('/')[-1]
    return node.__class__.__name__


def __node_def_name(node) -> str:
    """Return the ECUC definition short name if available."""
    if hasattr(node, 'get_definition_as_string') and callable(node.get_definition_as_string):
        defn = node.get_definition_as_string()
        if defn:
            return defn.split('/')[-1]
    return ''


def __node_entry(node, is_root=False) -> dict:
    return {
        'id':       node.get_unique_hash(),
        'label':    __node_label(node),
        'tag':      node.__class__.__name__,
        'path':     getattr(node, 'autosar_path', None) or node.path or '',
        'defName':  __node_def_name(node),
        'props':    __scalar_props(node),
        'isRoot':   is_root,
    }


# ── graph builder ─────────────────────────────────────────────────────────────

def __add_edge(edges: list, edges_set: set, source, target, etype, label):
    key = (source, target, etype, label)
    if key not in edges_set:
        edges_set.add(key)
        edges.append({'source': source, 'target': target, 'type': etype, 'label': label})


def __build_graph(node, nodes_map: dict, edges: list, visited: set, edges_set: set):
    node_hash = node.get_unique_hash()
    if node_hash in visited:
        return
    visited.add(node_hash)

    if node_hash not in nodes_map:
        nodes_map[node_hash] = __node_entry(node)

    # ── child relationships (solid edges) ─────────────────────────────────────
    if hasattr(node, 'get_children') and callable(node.get_children):
        for child in node.get_children():
            if isinstance(child, _SKIP_TYPES):
                continue

            # ECUC reference values → dashed edge to the referenced node
            if isinstance(child, autosarfactory.EcucAbstractReferenceValue) and child.get_value() is not None:
                target = child.get_value().get_target() \
                    if isinstance(child, autosarfactory.EcucInstanceReferenceValue) \
                    else child.get_value()
                t_hash = target.get_unique_hash()
                if t_hash not in nodes_map:
                    nodes_map[t_hash] = __node_entry(target)
                label = ''
                if child.get_definition_as_string() is not None:
                    label = child.get_definition_as_string().split('/')[-1]
                __add_edge(edges, edges_set, node_hash, t_hash, 'ref', label)
                __ensure_parent_chain(target, nodes_map, edges, edges_set)
                if t_hash not in visited:
                    __build_graph(target, nodes_map, edges, visited, edges_set)
                continue

            c_hash = child.get_unique_hash()
            if c_hash not in nodes_map:
                nodes_map[c_hash] = __node_entry(child)
            __add_edge(edges, edges_set, node_hash, c_hash, 'child', '')
            if c_hash not in visited:
                __build_graph(child, nodes_map, edges, visited, edges_set)

    # ── outgoing property references (dashed edges) ───────────────────────────
    for prop_name, value in node.get_property_values().items():
        # single reference (Referrable or non-Referrable AutosarNode)
        if isinstance(value, autosarfactory.AutosarNode):
            r_hash = value.get_unique_hash()
            if r_hash not in nodes_map:
                nodes_map[r_hash] = __node_entry(value)
            __add_edge(edges, edges_set, node_hash, r_hash, 'ref', prop_name)
            __ensure_parent_chain(value, nodes_map, edges, edges_set)
            if r_hash not in visited:
                __build_graph(value, nodes_map, edges, visited, edges_set)
        # collection references stored as {AutosarNode: None} dicts
        elif isinstance(value, dict):
            for ref in value:
                if isinstance(ref, autosarfactory.AutosarNode):
                    r_hash = ref.get_unique_hash()
                    if r_hash not in nodes_map:
                        nodes_map[r_hash] = __node_entry(ref)
                    __add_edge(edges, edges_set, node_hash, r_hash, 'ref', prop_name)
                    __ensure_parent_chain(ref, nodes_map, edges, edges_set)
                    if r_hash not in visited:
                        __build_graph(ref, nodes_map, edges, visited, edges_set)

    # ── incoming references: nodes that point to this node ────────────────────
    if hasattr(node, 'referenced_by') and node.referenced_by:
        for ref_node in node.referenced_by:
            if isinstance(ref_node, (_SKIP_TYPES + (autosarfactory.EcucAbstractReferenceValue,))):
                continue
            r_hash = ref_node.get_unique_hash()
            if r_hash not in nodes_map:
                nodes_map[r_hash] = __node_entry(ref_node)
            # find the property name on the referencing node
            prop_name = ''
            try:
                if isinstance(ref_node, autosarfactory.EcucAbstractReferenceValue) and ref_node.get_definition_as_string() is not None:
                    prop_name = ref_node.get_definition_as_string().split('/')[-1]
                else:
                    for k, v in ref_node.get_property_values().items():
                        if isinstance(v, autosarfactory.Referrable) and v.get_unique_hash() == node_hash:
                            prop_name = k
                            break
            except Exception:
                pass
            __add_edge(edges, edges_set, r_hash, node_hash, 'ref', prop_name)
            __ensure_parent_chain(ref_node, nodes_map, edges, edges_set)


def __ensure_parent_chain(node, nodes_map: dict, edges: list, edges_set: set):
    """Walk up the parent chain from node to root, adding missing nodes + child edges."""
    child = node
    while True:
        parent = getattr(child, 'parent', None)
        if parent is None:
            break
        p_hash = parent.get_unique_hash()
        c_hash = child.get_unique_hash()
        if (p_hash, c_hash, 'child', '') in edges_set:
            break  # already connected from here up
        if p_hash not in nodes_map:
            nodes_map[p_hash] = __node_entry(parent)
        __add_edge(edges, edges_set, p_hash, c_hash, 'child', '')
        child = parent


# ── template loader ───────────────────────────────────────────────────────────

def __get_template(name) -> str:
    path = os.path.join(os.path.dirname(__file__), 'templates', name)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


# ── HTML scaffold ─────────────────────────────────────────────────────────────

_HTML_SCAFFOLD = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AUTOSAR Interactive Graph — {{ stem }}</title>
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
{{ css_style }}
</head>
<body>

<header>
  <h1>AUTOSAR Interactive Graph — {{ stem }}</h1>
  <div id="search-wrap">
    <input id="search" type="text" placeholder="Search nodes…" autocomplete="off"
           oninput="onSearchInput(this.value)" onfocus="onSearchInput(this.value)">
    <ul id="search-dropdown"></ul>
  </div>
  <span id="match-count"></span>
  <select id="view-filter" onchange="onFilterChange(this.value)">
    <option value="all">All elements</option>
    <option value="system">System Model elements</option>
    <option value="ecuc">Ecu Configuration elements</option>
  </select>
  <button id="sidebar-toggle" onclick="toggleSidebar()">&#9664; Hide panel</button>
</header>

<div class="main">
  <div id="graph-panel">
    <div id="mynetwork"></div>
    <div id="legend">
      <div class="legend-item"><span class="leg-dot" style="background:#f97316;border-color:#ea580c"></span> System element</div>
      <div class="legend-item"><span class="leg-dot" style="background:#10b981;border-color:#059669"></span> ECUC configuration</div>
      <div class="legend-item"><span class="leg-dot" style="background:#3b82f6;border-color:#1d4ed8"></span> AR-Package</div>
      <div class="legend-item"><span class="leg-dot" style="background:#a78bfa;border-color:#7c3aed;transform:rotate(45deg)"></span> Via reference</div>
      <div class="legend-item"><span class="leg-solid"></span> Child</div>
      <div class="legend-item"><span class="leg-dashed"></span> Reference</div>
    </div>
    <button id="reset-btn" onclick="resetView()">Reset view</button>
  </div>

  <div id="sidebar">
    <div id="prop-panel">
      <div id="prop-placeholder">
        <p>Click a node to view its properties.</p>
        <p class="hint-small">
          <strong>Click</strong> — expand / collapse one level<br>
          <strong>Shift+Click</strong> — expand all descendants<br>
          <strong>Scroll</strong> — zoom &nbsp;·&nbsp; <strong>Drag</strong> — pan<br>
          Blue = AR-Package &nbsp;·&nbsp; Orange = system &nbsp;·&nbsp; Green = ECUC<br>
          Grey = collapsed &nbsp;·&nbsp; Purple ◆ = via reference<br>
          Dashed edge = reference &nbsp;·&nbsp; <strong>Dbl-click</strong> ◆ = show in tree<br>
          <strong>Right-click</strong> node or panel = copy menu
        </p>
      </div>
      <div id="prop-content">
        <div id="prop-header">
          <div id="prop-name"></div>
          <div id="prop-meta"></div>
          <div id="prop-path"></div>
        </div>
        <div class="prop-section-title">Properties</div>
        <table id="prop-table">
          <thead><tr><th>Property</th><th>Value</th></tr></thead>
          <tbody id="prop-tbody"></tbody>
        </table>
        <div id="prop-refs-section">
          <div class="prop-section-title">References</div>
          <table id="prop-refs-table">
            <thead><tr><th>Property</th><th>Target</th></tr></thead>
            <tbody id="prop-refs-tbody"></tbody>
          </table>
        </div>
        <div id="prop-refby-section">
          <div class="prop-section-title">Referenced By</div>
          <table id="prop-refby-table">
            <thead><tr><th>Property</th><th>Source</th></tr></thead>
            <tbody id="prop-refby-tbody"></tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</div>

<div id="tip"></div>
<ul id="ctx-menu"></ul>

{{ java_script }}
</body>
</html>
"""


# ── public API ────────────────────────────────────────────────────────────────

def create_graph_report(node: autosarfactory.AutosarNode, output_filename='graph_report.html'):
    """
    Generate a self-contained interactive D3.js force-directed graph.
    Children shown as solid edges, references as dashed edges.
    Shared referenced nodes appear once with multiple incoming edges.
    Click nodes to expand/collapse children.
    """
    stem = node.name or node.__class__.__name__

    nodes_map: dict = {}
    edges:     list = []

    # mark root
    root_hash = node.get_unique_hash()
    nodes_map[root_hash] = __node_entry(node, is_root=True)
    __build_graph(node, nodes_map, edges, visited=set(), edges_set=set())

    nodes_list = list(nodes_map.values())
    graph_data = {'nodes': nodes_list, 'edges': edges}

    js = __get_template('javascripts.tpl') \
        .replace('{{ graph_data_json }}', json.dumps(graph_data))

    html = (
        _HTML_SCAFFOLD
        .replace('{{ css_style }}',   __get_template('css.tpl'))
        .replace('{{ java_script }}', js)
        .replace('{{ stem }}',        stem)
    )

    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(html)
