import re
import json
import argparse
import glob
from autosarfactory import autosarfactory

def __get_label_name(node):
    return node.__class__.__name__ if node.name is None else (node.__class__.__name__ + '\n' + node.name)

def __build_nodes_map(node:autosarfactory.AutosarNode, nodes_map: dict, edges: list):
    # Add the child nodes
    for v in node.get_children():
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
        elif isinstance(v, autosarfactory.EcucAbstractReferenceValue) and v.get_value() != None:
            edge = v.get_value().get_target() if isinstance(v, autosarfactory.EcucInstanceReferenceValue) else v.get_value()
            nodes_map[edge.get_unique_hash()] = {'id': edge.get_unique_hash(), 'label': __get_label_name(edge)}
            edges.append({'from': node.get_unique_hash(), 'to': edge.get_unique_hash(), 'dashes': True, 'label': v.get_definition_as_string().split("/")[-1], 'font': {'align': 'middle', 'size': 10} })
            __build_nodes_map(edge, nodes_map, edges)
        else:
            nodes_map[v.get_unique_hash()] = {'id': v.get_unique_hash(), 'label': __get_label_name(v)}
            edges.append({'from': node.get_unique_hash(), 'to': v.get_unique_hash(), 'dashes': False})
            __build_nodes_map(v, nodes_map, edges)

    # Add the referenced nodes
    for k,v in node.get_property_values().items():
        if isinstance(v, autosarfactory.AutosarNode):
            nodes_map[v.get_unique_hash()] = {'id': v.get_unique_hash(), 'label': __get_label_name(v)}
            edges.append({'from': node.get_unique_hash(), 'to': v.get_unique_hash(), 'dashes': True, 'label': str(k), 'font': {'align': 'middle', 'size': 10} })
            __build_nodes_map(v, nodes_map, edges)


def create_graph_report(node:autosarfactory.AutosarNode, output_filename='graph_report.html'):
    """
    Process the given node to find inter-links, and generates a self-contained interactive HTML graph report.
    """
    nodes_map = {}
    edges = []

    nodes_map[node.get_unique_hash()] = {'id': node.get_unique_hash(), 'label': node.__class__.__name__ + '\n' + node.name if node.name is not None else ''}
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
        <style>
            html, body { margin: 0; 
                        padding: 0; 
                        height: 100%; 
                        width: 100%; 
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }
            
            #mynetwork { width: 100%; height: 100vh; }
            .ui-panel {
                position: fixed; 
                z-index: 10000; 
                display: flex; 
                align-items: center; 
                gap: 15px;
                background-color: rgba(255, 255, 255, 0.95); 
                padding: 10px; 
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.15);
            }
            
            #top-right-controls {
                position: fixed; 
                top: 15px; 
                right: 20px; 
                z-index: 10000; 
                display: flex;
                align-items: center; 
                gap: 15px; 
                background-color: rgba(255, 255, 255, 0.9);
                padding: 10px; 
                border-radius: 8px; 
                box-shadow: 0 2px 6px rgba(0,0,0,0.15);
            }
            
            #top-right-controls > select { max-width: 250px; 
                                           height: 34px; 
                                           border: 1px 
                                           solid #ccc; 
                                           border-radius: 5px; 
                                           font-size: 14px; }
            .control-button { padding: 8px 12px; 
                              background-color: #3498db; 
                              color: white; 
                              border: none; 
                              border-radius: 5px; 
                              cursor: pointer; 
                              font-size: 14px; }
            
            #depth-input { width: 40px; 
                           padding: 5px; 
                           font-size: 14px; 
                           text-align: center; 
                           border: 1px solid #ccc; 
                           border-radius: 4px; }
            #reset-button { display: none; }
            
            #legend {
                top: 15px; 
                left: 20px; 
                flex-direction: column; 
                align-items: flex-start; 
                gap: 8px;
                background-color: transparent;
                box-shadow: none;
            }
            .legend-item { display: flex; align-items: center; font-size: 14px; color: #333; }
            .legend-line { border-top-width: 2px; width: 40px; margin-right: 10px; }
            .legend-line.solid { border-top-style: solid; border-top-color: #2B2B2B; }
            .legend-line.dashed { border-top-style: dashed; border-top-color: #007bff; }
        </style>
    </head>
    <body>
        <!-- The main container for the graph -->
        <div id="mynetwork"></div>
        <!-- The Top-Right Control Panel -->
        <div id="top-right-controls">
            <button id="reset-button" class="control-button">Reset</button>
            <div style="display:flex; align-items:center; gap:8px;">
                <label for="depth-input">Depth:</label>
                <input type="number" id="depth-input" value="1" min="1" max="20">
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
        <script type="text/javascript">
            document.addEventListener('DOMContentLoaded', function() {
                const graphData = {{ graph_data_json }};
                const container = document.getElementById('mynetwork');
                const options = {
                    layout: { improvedLayout: true,  hierarchical: false },
                    nodes: { shape: 'box', font: {size: 16},  margin: 15, borderWidth: 2},
                    edges: { arrows: { to: { enabled: true, scaleFactor: 0.7 } }, smooth: { type: 'continuous' },  width: 1.5 },
                    interaction: { hover: true, navigationButtons: true },
                    physics: { enabled: true, 
								barnesHut: {gravitationalConstant: -20000, centralGravity: 0.3, springLength: 200, springConstant: 0.04, damping: 0.09, avoidOverlap: 0.6
							 },
					stabilization: { enabled: true, iterations: 1000, updateInterval: 20 },
					solver: 'barnesHut'},
                };
                const data = { nodes: new vis.DataSet(graphData.nodes), edges: new vis.DataSet(graphData.edges) };
                const network = new vis.Network(container, data, options);

                const resetButton = document.getElementById('reset-button');
                const depthInput = document.getElementById('depth-input');
                const controlsContainer = document.getElementById('top-right-controls');
                const input = document.createElement('input');
				input.type = 'text';
				input.id = 'node-search-input';
				input.placeholder = 'Search or select a node...';
				input.style.cssText = 'width: 250px; height: 34px; border: 1px solid #ccc; border-radius: 5px; font-size: 14px; padding: 0 10px;';
				input.setAttribute('list', 'node-datalist');

				const datalist = document.createElement('datalist');
				datalist.id = 'node-datalist';

				// Create a mapping of labels to IDs
				const labelToIdMap = {};
				data.nodes.get({order: 'label'}).forEach(n => {
					labelToIdMap[n.label.replace("\\n", "")] = n.id;
					datalist.innerHTML += `<option value="${n.label}"></option>`;
				});

				controlsContainer.prepend(datalist);
				controlsContainer.prepend(input);
				
				let isCurrentlyFiltered = false;
				let currentFilteredNode = null;

                // function to filter the graph node
                function filterGraphToNode(nodeId) {
                    if (!nodeId) return;

                    resetButton.style.display = 'inline-block';
                    let currentDepth = parseInt(depthInput.value, 10);
                    if (isNaN(currentDepth) || currentDepth < 1) { currentDepth = 1; }

                    const visibleNodesSet = getNodesWithinDepth(nodeId, currentDepth);

                    data.nodes.update(data.nodes.getIds().map(id => ({ id: id, hidden: !visibleNodesSet.has(id) })));
                    data.edges.update(data.edges.getIds().map(id => {
                        const edge = data.edges.get(id);
                        return { id: id, hidden: !(visibleNodesSet.has(edge.from) && visibleNodesSet.has(edge.to)) };
                    }));
                    const shouldFit = !isCurrentlyFiltered || currentFilteredNode !== nodeId;
                    isCurrentlyFiltered = true;
                    currentFilteredNode = nodeId;
                     if (shouldFit) {
                        network.fit({ nodes: Array.from(visibleNodesSet), animation: true }); 
                    }
                }
                
                // reset the graph view
                function resetGraphView() {
                    data.nodes.update(data.nodes.getIds().map(id => ({ id: id, hidden: false })));
                    data.edges.update(data.edges.getIds().map(id => ({ id: id, hidden: false })));
                    resetButton.style.display = 'none';
                    network.unselectAll();
                    input.value = "";
                }

                // filter based on the depth
                function getNodesWithinDepth(startNode, maxDepth) {
					let visibleNodes = new Set();
					let queue = [[startNode, 0]];
					visibleNodes.add(startNode);

					while (queue.length > 0) {
						let [currentNode, currentDepth] = queue.shift();

						if (currentDepth < maxDepth) {
							const connectedEdges = network.getConnectedEdges(currentNode);
							connectedEdges.forEach(edgeId => {
								const edge = data.edges.get(edgeId);

								// Follow outgoing edges (children and outgoing references)
								if (edge.from === currentNode && !visibleNodes.has(edge.to)) {
									visibleNodes.add(edge.to);
									queue.push([edge.to, currentDepth + 1]);
								}

								// Also follow incoming dashed edges (where this node is referenced)
								if (edge.to === currentNode && edge.dashes === true && !visibleNodes.has(edge.from)) {
									visibleNodes.add(edge.from);
									queue.push([edge.from, currentDepth + 1]);
								}
							});
						}
					}

					return visibleNodes;
				}

                // Dropdown change event
                // Function to handle node selection from input
				function handleInputSelection() {
					const selectedLabel = input.value.trim();
					console.log('Label selected'+ selectedLabel);
					if (selectedLabel && labelToIdMap[selectedLabel]) {
						const nodeId = labelToIdMap[selectedLabel];
						network.selectNodes([nodeId]);
						filterGraphToNode(nodeId);
					} else if (!selectedLabel) {
					    resetGraphView();
					}
				}

				// Trigger on input change (fires when selecting from datalist)
				input.addEventListener('input', (e) => {
					handleInputSelection();
				});

				// Also listen to change event
				input.addEventListener('change', (e) => {
					handleInputSelection();
				});
				
				// Also listen to Enter key
				input.addEventListener('keydown', (e) => {
					if (e.key === 'Enter') {
						handleInputSelection();
					}
				});

                // Direct click event
                network.on("selectNode", function (params) {
                    if (params.nodes.length > 0) {
                        const nodeId = params.nodes[0];
                        filterGraphToNode(nodeId);
                    }
                });

                // when depth is changed
                depthInput.addEventListener('input', () => {
                    const selection = network.getSelection();
                    if (selection.nodes.length > 0) {
                        const selectedNodeId = selection.nodes[0];
                        // Re-run the filter for the currently selected node
                        filterGraphToNode(selectedNodeId);
                    }
                });

                // When user clicks off a node
                network.on("deselectNode", function(params) {
                     resetGraphView();
                });

                // Disable physics after initial stabilization
				network.once('stabilizationIterationsDone', function() {
					console.log('calling once stabilization done');
					network.setOptions({ physics: { enabled: false } });
				});

                // Reset button click
                resetButton.addEventListener('click', resetGraphView);
				
                // Export png action
				document.getElementById('export-png-button').addEventListener('click', function() {
					try {
						const networkCanvas = document.querySelector('#mynetwork canvas');
						if (!networkCanvas) {
							alert('Could not find graph canvas');
							return;
						}

						// You can adjust the scale factor for higher/lower resolution
						const scaleFactor = 2; // 2x resolution for better quality

						const exportCanvas = document.createElement('canvas');
						const ctx = exportCanvas.getContext('2d');

						exportCanvas.width = networkCanvas.width * scaleFactor;
						exportCanvas.height = networkCanvas.height * scaleFactor;

						// Scale context for higher resolution
						ctx.scale(scaleFactor, scaleFactor);

						// White background
						ctx.fillStyle = '#ffffff';
						ctx.fillRect(0, 0, exportCanvas.width, exportCanvas.height);

						// Draw network
						ctx.drawImage(networkCanvas, 0, 0);

						// Download
						exportCanvas.toBlob(function(blob) {
							const url = URL.createObjectURL(blob);
							const link = document.createElement('a');
							const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
							link.download = `autosar-graph-${timestamp}.png`;
							link.href = url;
							document.body.appendChild(link);
							link.click();
							document.body.removeChild(link);
							URL.revokeObjectURL(url);
						}, 'image/png', 1.0);

					} catch (error) {
						console.error('Export failed:', error); // for debug
					}
				});
            });
        </script>
    </body>
    </html>
    """

    # Safely inject the Python dictionary as a JSON object into the template
    final_html = html_template.replace('{{ graph_data_json }}', json.dumps(graph_data))

    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(final_html)
