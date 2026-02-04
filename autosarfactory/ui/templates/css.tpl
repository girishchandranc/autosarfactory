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

    /* Context Menu Styles */
    #context-menu {
        display: none;
        position: fixed;
        background-color: white;
        border: 1px solid #ccc;
        border-radius: 5px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        z-index: 10001;
        min-width: 180px;
        padding: 5px 0;
    }

    .context-menu-item {
        padding: 10px 15px;
        cursor: pointer;
        font-size: 14px;
        color: #333;
        border-bottom: 1px solid #eee;
    }

    .context-menu-item:last-child {
        border-bottom: none;
    }

    .context-menu-item:hover {
        background-color: #f0f0f0;
    }

    .context-menu-item:active {
        background-color: #e0e0e0;
    }

    .context-menu-separator {
        height: 1px;
        background-color: #ddd;
        margin: 5px 0;
    }

    // expand/collapse button styling
    .expand-button {
        position: absolute;
        width: 24px;
        height: 24px;
        border-radius: 50%;
        background-color: #2196F3;
        color: white;
        border: 2px solid white;
        cursor: pointer;
        display: none;  /* Hidden by default */
        align-items: center;
        justify-content: center;
        font-size: 16px;
        font-weight: bold;
        box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        transition: all 0.2s;
        z-index: 1000;
        user-select: none;
        opacity: 0;
        transform: scale(0.8);
    }

    .expand-button.visible {
        display: flex;
        opacity: 1;
        transform: scale(1);
    }

    .expand-button:hover {
        background-color: #1976D2;
        transform: scale(1.15);
        box-shadow: 0 3px 6px rgba(0,0,0,0.4);
    }

    .expand-button.expanded {
        background-color: #4CAF50;
    }

    .expand-button.expanded:hover {
        background-color: #388E3C;
    }

    .expand-button.collapsed {
        background-color: #FF9800;
    }

    .expand-button.collapsed:hover {
        background-color: #F57C00;
    }

    #button-container {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
        z-index: 999;
    }

    #button-container .expand-button {
        pointer-events: auto;
    }

    /* Visual feedback for expandable nodes on hover */
    .node-hoverable {
        cursor: pointer;
    }

    /* Style for nodes that can be expanded */
    .node-expanded {
        background-color: #e8f5e9;
        border-color: #4CAF50;
    }

    .node-collapsed {
        background-color: #ffffff;
    }
</style>