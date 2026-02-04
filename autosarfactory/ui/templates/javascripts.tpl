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
        const idToLabelMap = {};
        data.nodes.get({order: 'label'}).forEach(n => {
            labelToIdMap[n.label] = n.id;
            idToLabelMap[n.id] = n.label
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
            network.setOptions({ physics: { enabled: false } });
        });

        // Reset button click
        resetButton.addEventListener('click', resetGraphView);

        // show properties
        document.getElementById('show-properties-checkbox').addEventListener('change', function(e) {
            const showProperties = e.target.checked;
            const updates = data.nodes.map(node => {
                let newLabel = idToLabelMap[node.id];
                if (showProperties && node.properties) {
                    // Append properties to label
                    const propsText = Object.entries(node.properties)
                        .map(([key, value]) => `${key}: ${value}`)
                        .join('\\n');

                    if (propsText) {
                        newLabel = newLabel + '\\n' + ''.padStart(newLabel.length, '-') + '\\n' + propsText;
                    }
                }

                return {
                    id: node.id,
                    label: newLabel
                };
            });

            data.nodes.update(updates);
        });
        
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

        // context menu
        const contextMenu = document.getElementById('context-menu');
        let currentContextNode = null;

        // Show context menu on right-click
        network.on("oncontext", function(params) {
            params.event.preventDefault();

            const nodeId = network.getNodeAt(params.pointer.DOM);

            if (nodeId) {
                currentContextNode = data.nodes.get(nodeId);

                // Position the menu at mouse location
                contextMenu.style.left = params.event.pageX + 'px';
                contextMenu.style.top = params.event.pageY + 'px';
                contextMenu.style.display = 'block';
            }
        });

        // Hide context menu when clicking elsewhere
        document.addEventListener('click', function(e) {
            if (!contextMenu.contains(e.target)) {
                contextMenu.style.display = 'none';
                currentContextNode = null;
            }
        });

        // Handle context menu item clicks
        contextMenu.addEventListener('click', function(e) {
            const menuItem = e.target.closest('.context-menu-item');
            if (!menuItem || !currentContextNode){
                return;
            }

            const action = menuItem.getAttribute('data-action');
            let textToCopy = '';

            switch(action) {
                case 'copy-path':
                    textToCopy = currentContextNode.path;
                    break;

                case 'copy-properties':
                    if (currentContextNode.properties) {
                        textToCopy = Object.entries(currentContextNode.properties)
                                        .map(([key, value]) => `${key}: ${value}`)
                                        .join('\\n');
                    } else {
                        textToCopy = 'No properties available';
                    }
                    break;
            }

            // Copy to clipboard
            copyToClipboard(textToCopy);

            // Hide menu
            contextMenu.style.display = 'none';
            currentContextNode = null;
        });

        // Helper function to copy text to clipboard
        function copyToClipboard(text) {
            if (!text) {
                return;
            }

            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).then(function() {
                }).catch(function(err) {
                    console.error('Failed to copy:', err);
                });
            }
        }
    });
</script>