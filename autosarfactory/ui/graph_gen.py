import re, json, os
from enum import Enum
from autosarfactory import autosarfactory

def __get_label_name(node):
    return node.__class__.__name__ if node.name is None else (node.name + '('+node.__class__.__name__ + ')')

def __build_nodes_map(node: autosarfactory.AutosarNode, nodes_map: dict, edges: list):
    visited = set()
    stack = [node]

    while stack:
        current = stack.pop()
        node_hash = current.get_unique_hash()

        # Skip if already processed
        if node_hash in visited:
            continue
        visited.add(node_hash)

        # Process child nodes
        for v in current.get_children():
            if isinstance(v, (autosarfactory.EcucParameterValue, 
                              autosarfactory.MultiLanguageOverviewParagraph, 
                              autosarfactory.MultilanguageLongName, 
                              autosarfactory.AttributeValueVariationPoint,
                              autosarfactory.DocumentationBlock,
                              autosarfactory.AdminData,
                              autosarfactory.EcucValueConfigurationClass,
                              autosarfactory.EcucMultiplicityConfigurationClass,
                              autosarfactory.ValueSpecification)):
                continue

            elif isinstance(v, autosarfactory.EcucAbstractReferenceValue) and v.get_value() is not None:
                edge = v.get_value().get_target() if isinstance(v, autosarfactory.EcucInstanceReferenceValue) else v.get_value()
                edge_hash = edge.get_unique_hash()

                nodes_map[edge_hash] = {
                    'id': edge_hash, 
                    'label': __get_label_name(edge), 
                    'properties': __get_properties(edge),
                    'path': edge.path
                }
                edges.append({
                    'from': node_hash, 
                    'to': edge_hash, 
                    'dashes': True, 
                    'label': (v.get_definition_as_string().split("/")[-1] if v.get_definition_as_string() is not None else 'EcucReferenceValue'),
                    'font': {'align': 'middle', 'size': 10}
                })

                if edge_hash not in visited:
                    stack.append(edge)

            else:
                v_hash = v.get_unique_hash()

                nodes_map[v_hash] = {
                    'id': v_hash, 
                    'label': __get_label_name(v),
                    'properties': __get_properties(v),
                    'path': v.path
                }
                edges.append({
                    'from': node_hash, 
                    'to': v_hash, 
                    'dashes': False
                })

                if v_hash not in visited:
                    stack.append(v)

        # Process referenced nodes
        for k, v in current.get_property_values().items():
            if isinstance(v, autosarfactory.AutosarNode):
                v_hash = v.get_unique_hash()

                nodes_map[v_hash] = {
                    'id': v_hash, 
                    'label': __get_label_name(v),
                    'properties': __get_properties(v),
                    'path': v.path
                }
                edges.append({
                    'from': node_hash, 
                    'to': v_hash, 
                    'dashes': True, 
                    'label': str(k),
                    'font': {'align': 'middle', 'size': 10}
                })

                if v_hash not in visited:
                    stack.append(v)

def __get_properties(node: autosarfactory.AutosarNode):
    properties = {}
    if isinstance(node, autosarfactory.EcucContainerValue):
        params = [p for p in node.get_parameterValues() if (p.get_value() is not None and p.get_definition_as_string() is not None)]
        for p in params:
            value = ''
            if isinstance(p, autosarfactory.EcucTextualParamValue):
                value = p.get_value()
            elif isinstance(p, autosarfactory.EcucNumericalParamValue):
                value = p.get_value().get()
            properties[p.get_definition_as_string().split("/")[-1]] = value

    for k,v in node.get_property_values().items():
        if isinstance(v, (str, int, float, bool, Enum)) and v != '' and k != 'File' and k!= 'ShortName':
            properties[k] = v.literal if isinstance(v, Enum) else v
    
    return properties

def __get_template(name) -> str:
    with open(os.path.join(os.path.join(os.path.dirname(__file__), 'templates'), name), 'r', encoding='utf-8') as f:
        return f.read()

def create_graph_report(node:autosarfactory.AutosarNode, output_filename='graph_report.html'):
    """
    Process the given node to find inter-links, and generates a self-contained interactive HTML graph report.
    """
    nodes_map = {}
    edges = []

    nodes_map[node.get_unique_hash()] = {'id': node.get_unique_hash(), 
                                         'label': node.__class__.__name__ + '\n' + node.name if node.name is not None else '',
                                         'properties': __get_properties(node),
                                         'path' : node.path}
    __build_nodes_map(node, nodes_map, edges)

    nodes = list(nodes_map.values())
    graph_data = {'nodes': nodes, 'edges': edges}

    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Autosar Interactive Model Graph</title>
        <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
        {{ css_style }}
    </head>
    <body>
        <!-- The main container for the graph -->
        <div id="mynetwork"></div>
        <div id="button-container"></div>
        <!-- The Top-Right Control Panel -->
        <div id="top-right-controls">
            <button id="reset-button" class="control-button">Reset</button>
            <div style="display:flex; align-items:center; gap:8px;">
                <label for="depth-input">Depth:</label>
                <input type="number" id="depth-input" value="1" min="1" max="20">
            </div>
             <div style="display:flex; align-items:center; gap:8px;">
                <input type="checkbox" id="show-properties-checkbox">
                <label for="show-properties-checkbox">Show Properties</label>
            </div>
            <button id="export-png-button" class="control-button" style="background-color: #27ae60;">Export as PNG</button>
        </div>
        <!-- The Top-Left Control Panel -->
        <div id="legend" class="ui-panel">
            <div class="legend-item">
                <span class="legend-line solid"></span> Child Relationship
            </div>
            <div class="legend-item">
                <span class="legend-line dashed"></span> Reference
            </div>
        </div>
        {{ java_script }}
        <div id="context-menu">
            <div class="context-menu-item" data-action="copy-path">Copy Path</div>
            <div class="context-menu-separator"></div>
            <div class="context-menu-item" data-action="copy-properties">Copy Properties</div>
        </div>
    </body>
    </html>
    """

    # Safely inject the Python dictionary as a JSON object into the template
    javaScripts_txt = __get_template('javascripts.tpl').replace('{{ graph_data_json }}', json.dumps(graph_data))
    final_html = html_template.replace('{{ css_style }}', __get_template('css.tpl')).replace('{{ java_script }}', javaScripts_txt)

    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(final_html)
