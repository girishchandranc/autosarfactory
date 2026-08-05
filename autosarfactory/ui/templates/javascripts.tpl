<script>

// This file has code generated using AI

const GRAPH = {{ graph_data_json }};

// ── index structures ──────────────────────────────────────────────────────────
const nodeById = {};
GRAPH.nodes.forEach(n => { nodeById[n.id] = n; });

// outgoing ref edges per node
const refEdgesOf   = {};   // id -> [{target, label}, ...]
// incoming ref edges per node
const refSourcesOf = {};   // id -> [{source, label}, ...]
// child edges
const childrenOf   = {};   // id -> [target_id, ...]
const parentsOf    = {};   // id -> [source_id, ...]

GRAPH.edges.forEach(e => {
  if (e.type === 'child') {
    if (!childrenOf[e.source]) childrenOf[e.source] = [];
    childrenOf[e.source].push(e.target);
    if (!parentsOf[e.target]) parentsOf[e.target] = [];
    parentsOf[e.target].push(e.source);
  } else if (e.type === 'ref') {
    if (!refEdgesOf[e.source]) refEdgesOf[e.source] = [];
    refEdgesOf[e.source].push({ target: e.target, label: e.label || '' });
    if (!refSourcesOf[e.target]) refSourcesOf[e.target] = [];
    refSourcesOf[e.target].push({ source: e.source, label: e.label || '' });
  }
});

// ── ECUC node index (EcucModuleConfigurationValues + all descendants) ─────────
const _ecucNodes = new Set();
(function buildEcucIndex() {
  function markDescendants(id) {
    _ecucNodes.add(id);
    (childrenOf[id] || []).forEach(cid => { if (!_ecucNodes.has(cid)) markDescendants(cid); });
  }
  GRAPH.nodes.forEach(n => {
    if (n.tag === 'EcucModuleConfigurationValues') markDescendants(n.id);
  });
})();

// ── visibility state ──────────────────────────────────────────────────────────
let _filterMode = 'all';          // 'all' | 'system' | 'ecuc'
const visible  = new Set();
const expanded = new Set();

const rootNode = GRAPH.nodes.find(n => n.isRoot) || GRAPH.nodes[0];

function showNode(id)   { visible.add(id); }

function expandNode(id) {
  if (expanded.has(id)) return;
  expanded.add(id);
  (childrenOf[id] || []).forEach(cid => showNode(cid));
}

function expandAll(id) {
  expanded.add(id);
  (childrenOf[id] || []).forEach(cid => { showNode(cid); expandAll(cid); });
}

function collapseSubtree(id) {
  if (!expanded.has(id)) return;
  expanded.delete(id);
  (childrenOf[id] || []).forEach(cid => {
    const otherParent = (parentsOf[cid] || []).some(p => p !== id && visible.has(p));
    if (!otherParent) { visible.delete(cid); collapseSubtree(cid); }
  });
}

showNode(rootNode.id);
expandNode(rootNode.id);

// ── vis-network setup ─────────────────────────────────────────────────────────
const nodesDS = new vis.DataSet();
const edgesDS = new vis.DataSet();

const network = new vis.Network(
  document.getElementById('mynetwork'),
  { nodes: nodesDS, edges: edgesDS },
  {
    nodes: {
      shape: 'dot',
      size: 10,
      font: { size: 11, face: '-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif' },
      borderWidth: 2,
    },
    edges: {
      arrows: { to: { enabled: true, scaleFactor: 0.55 } },
      smooth: { enabled: true, type: 'cubicBezier', roundness: 0.5 },
      font:   { size: 9, align: 'middle', strokeWidth: 2, strokeColor: '#fff' },
    },
    physics: {
      solver: 'forceAtlas2Based',
      forceAtlas2Based: {
        gravitationalConstant: -60,
        centralGravity: 0.008,
        springLength: 130,
        springConstant: 0.07,
        damping: 0.5,
      },
      stabilization: { iterations: 250, updateInterval: 25 },
    },
    interaction: {
      tooltipDelay: 200,
      hideEdgesOnDrag: true,
      hover: false,
    },
  }
);

// ── orphan detection ─────────────────────────────────────────────────────────
let _currentVisSet = new Set();

function isOrphaned(id) {
  if (id === rootNode.id) return false;
  const parents = parentsOf[id] || [];
  if (!parents.length) return true;
  return !parents.some(pid => _currentVisSet.has(pid));
}

// ── node / edge builders ──────────────────────────────────────────────────────
function nodeColor(n) {
  if (n.isRoot) return {
    background: '#1a1a2e', border: '#0f0f1a',
    highlight:  { background: '#2e3a6e', border: '#0f0f1a' },
    hover:      { background: '#2e3a6e', border: '#0f0f1a' },
  };
  if (n.tag === 'ARPackage') return {
    background: '#3b82f6', border: '#1d4ed8',
    highlight:  { background: '#60a5fa', border: '#1d4ed8' },
    hover:      { background: '#60a5fa', border: '#1d4ed8' },
  };
  if (isOrphaned(n.id)) return {
    background: '#a78bfa', border: '#7c3aed',
    highlight:  { background: '#c4b5fd', border: '#7c3aed' },
    hover:      { background: '#c4b5fd', border: '#7c3aed' },
  };
  const hasCollapsed = (childrenOf[n.id] || []).some(c => !visible.has(c));
  if (hasCollapsed) return {
    background: '#9ca3af', border: '#6b7280',
    highlight:  { background: '#d1d5db', border: '#6b7280' },
    hover:      { background: '#d1d5db', border: '#6b7280' },
  };
  if (_ecucNodes.has(n.id)) return {
    background: '#10b981', border: '#059669',
    highlight:  { background: '#34d399', border: '#059669' },
    hover:      { background: '#34d399', border: '#059669' },
  };
  return {
    background: '#f97316', border: '#ea580c',
    highlight:  { background: '#fb923c', border: '#ea580c' },
    hover:      { background: '#fb923c', border: '#ea580c' },
  };
}

function makeVisNode(n) {
  const lbl = n.label.length > 24 ? n.label.substring(0, 22) + '…' : n.label;
  const orphan = isOrphaned(n.id);
  return {
    id:    n.id,
    label: lbl,
    title: orphan ? n.label + ' (double-click to show in tree)' : n.label,
    color: nodeColor(n),
    shape: orphan ? 'diamond' : 'dot',
    size:  n.isRoot ? 14 : (orphan ? 12 : 10),
    font:  { color: n.isRoot ? '#ffffff' : '#333333' },
  };
}

function makeVisEdge(e) {
  const eid = e.source + '||' + e.target + '||' + e.type + '||' + (e.label || '');
  if (e.type === 'child') {
    return { id: eid, from: e.source, to: e.target, dashes: false,
             color: { color: '#aaaaaa', highlight: '#555555', hover: '#555555' }, label: '' };
  }
  return { id: eid, from: e.source, to: e.target, dashes: [6, 4],
           color: { color: '#e67e22', highlight: '#c0392b', hover: '#c0392b' },
           label: e.label || '',
           font:  { color: '#e67e22', size: 9, strokeWidth: 2, strokeColor: '#fff' },
           width: 1.5 };
}

// ── render ────────────────────────────────────────────────────────────────────
function render() {
  const visSet = new Set(visible);
  // also show direct ref targets AND ref sources of visible nodes
  GRAPH.edges.forEach(e => {
    if (e.type !== 'ref') return;
    if (visSet.has(e.source) && nodeById[e.target]) visSet.add(e.target);
    if (visSet.has(e.target) && nodeById[e.source]) visSet.add(e.source);
  });

  // apply view filter
  if (_filterMode === 'ecuc') {
    visSet.forEach(id => { if (!_ecucNodes.has(id) && !(nodeById[id] && nodeById[id].tag === 'ARPackage')) visSet.delete(id); });
  } else if (_filterMode === 'system') {
    visSet.forEach(id => { if (_ecucNodes.has(id)) visSet.delete(id); });
  }
  // always keep root visible
  visSet.add(rootNode.id);

  // expose to isOrphaned() — computes fresh from visSet each time
  _currentVisSet = visSet;

  const wantNodes = GRAPH.nodes.filter(n => visSet.has(n.id)).map(makeVisNode);
  const wantEdges = GRAPH.edges
    .filter(e => visSet.has(e.source) && visSet.has(e.target))
    .map(makeVisEdge);

  const existNodeIds = new Set(nodesDS.getIds());
  const wantNodeIds  = new Set(wantNodes.map(n => n.id));
  const removedNodes = [...existNodeIds].filter(id => !wantNodeIds.has(id));
  nodesDS.remove(removedNodes);

  // position new children in a fan arc below their parent
  const positions = network.getPositions();
  const addedNodes = [];

  // group new nodes by parent so we can fan them out
  const newByParent = {};
  wantNodes.forEach(n => {
    if (!existNodeIds.has(n.id)) {
      const pids = parentsOf[n.id] || [];
      const pid = pids.length ? pids[0] : '__none__';
      if (!newByParent[pid]) newByParent[pid] = [];
      newByParent[pid].push(n);
    }
  });

  const toUpdate = [];
  const toAdd = [];
  wantNodes.forEach(n => {
    if (existNodeIds.has(n.id)) {
      const cur = nodesDS.get(n.id);
      if (cur.label !== n.label || cur.shape !== n.shape
          || (cur.color && cur.color.background) !== (n.color && n.color.background)) {
        const p = positions[n.id];
        if (p) { n.x = p.x; n.y = p.y; }
        toUpdate.push(n);
      }
    } else {
      addedNodes.push(n.id);
      const pids = parentsOf[n.id] || [];
      const pid = pids.length ? pids[0] : null;
      const parentPos = pid && positions[pid];
      if (parentPos) {
        const siblings = newByParent[pid] || [n];
        const idx = siblings.indexOf(n);
        const count = siblings.length;
        const spread = Math.min(Math.PI, count * 0.3);
        const startAngle = (Math.PI / 2) - spread / 2;
        const angle = count === 1 ? Math.PI / 2 : startAngle + (spread * idx / (count - 1));
        const dist = 100 + count * 5;
        n.x = parentPos.x + Math.cos(angle) * dist;
        n.y = parentPos.y + Math.sin(angle) * dist;
      }
      toAdd.push(n);
    }
  });
  // batch all DataSet mutations — single event per operation
  if (toUpdate.length) nodesDS.update(toUpdate);
  if (toAdd.length) nodesDS.add(toAdd);

  const existEdgeIds = new Set(edgesDS.getIds());
  const removedEdges = [...existEdgeIds].filter(id => !new Set(wantEdges.map(e => e.id)).has(id));
  const newEdges = wantEdges.filter(e => !existEdgeIds.has(e.id));
  if (removedEdges.length) edgesDS.remove(removedEdges);
  if (newEdges.length) edgesDS.add(newEdges);
}

// ── properties panel ──────────────────────────────────────────────────────────
function showNodeProperties(id) {
  const n = nodeById[id];
  if (!n) return;

  document.getElementById('prop-placeholder').style.display = 'none';
  const content = document.getElementById('prop-content');
  content.style.display = 'block';

  document.getElementById('prop-name').textContent = n.label;
  const orphan = isOrphaned(id);
  const isEcuc = _ecucNodes.has(id);
  document.getElementById('prop-meta').innerHTML =
    '<span class="type-badge">' + esc(n.tag) + '</span>'
    + (n.defName ? '<span class="type-badge" style="background:#d1fae5;color:#065f46">' + esc(n.defName) + '</span>' : '')
    + (isEcuc ? '<span class="type-badge" style="background:#d1fae5;color:#065f46">ECUC</span>' : '')
    + (orphan ? '<span class="orphan-badge">via reference</span>' : '');
  document.getElementById('prop-path').textContent = n.path || '';

  // action buttons row
  let btnRow = document.getElementById('prop-action-btns');
  if (btnRow) btnRow.remove();
  const hasChildren = (childrenOf[id] || []).length > 0;
  if (orphan || hasChildren) {
    btnRow = document.createElement('div');
    btnRow.id = 'prop-action-btns';
    btnRow.style.cssText = 'padding:.35rem 1rem .1rem;display:flex;gap:.4rem;flex-wrap:wrap';
    if (orphan) {
      const treeBtn = document.createElement('button');
      treeBtn.className = 'show-in-tree-btn';
      treeBtn.textContent = '↑ Show in tree';
      treeBtn.onclick = function() { expandToRoot(id); };
      btnRow.appendChild(treeBtn);
    }
    if (hasChildren) {
      const expAllBtn = document.createElement('button');
      expAllBtn.className = 'show-in-tree-btn';
      expAllBtn.style.background = '#22c55e';
      expAllBtn.textContent = '+ Expand all';
      expAllBtn.onclick = function() {
        expandAll(id);
        render();
        showNodeProperties(id);
      };
      btnRow.appendChild(expAllBtn);

      if (expanded.has(id)) {
        const colBtn = document.createElement('button');
        colBtn.className = 'show-in-tree-btn';
        colBtn.style.background = '#ef4444';
        colBtn.textContent = '− Collapse';
        colBtn.onclick = function() {
          collapseSubtree(id);
          render();
          showNodeProperties(id);
        };
        btnRow.appendChild(colBtn);
      }
    }
    document.getElementById('prop-header').appendChild(btnRow);
  }

  // scalar properties
  const tbody = document.getElementById('prop-tbody');
  const props = n.props || {};
  const keys  = Object.keys(props);
  if (keys.length) {
    tbody.innerHTML = keys.map(k => {
      const v = String(props[k]);
      return '<tr><td class="prop-key">' + esc(k) + '</td>'
           + '<td class="prop-val"><code>' + esc(v.length > 80 ? v.substring(0, 80) + '…' : v) + '</code></td></tr>';
    }).join('');
  } else {
    tbody.innerHTML = '<tr><td colspan="2" style="color:#bbb;font-style:italic">No scalar properties</td></tr>';
  }

  // outgoing reference edges from this node
  const refs  = refEdgesOf[id] || [];
  const rSect = document.getElementById('prop-refs-section');
  if (refs.length) {
    rSect.style.display = 'block';
    document.getElementById('prop-refs-tbody').innerHTML = refs.map(r => {
      const tn = nodeById[r.target];
      const tLabel = tn ? tn.label : r.target.substring(0, 20) + '…';
      const tPath  = tn ? tn.path  : '';
      return '<tr><td class="prop-key">' + esc(r.label || '—') + '</td>'
           + '<td><a onclick="focusNode(\'' + r.target + '\')" title="' + esc(tPath) + '">'
           + esc(tLabel) + '</a></td></tr>';
    }).join('');
  } else {
    rSect.style.display = 'none';
  }

  // incoming references: nodes that point to this node
  const srcs   = refSourcesOf[id] || [];
  const rbSect = document.getElementById('prop-refby-section');
  if (srcs.length) {
    rbSect.style.display = 'block';
    document.getElementById('prop-refby-tbody').innerHTML = srcs.map(r => {
      const sn = nodeById[r.source];
      const sLabel = sn ? sn.label : r.source.substring(0, 20) + '…';
      const sPath  = sn ? sn.path  : '';
      return '<tr><td class="prop-key">' + esc(r.label || '—') + '</td>'
           + '<td><a onclick="focusNode(\'' + r.source + '\')" title="' + esc(sPath) + '">'
           + esc(sLabel) + '</a></td></tr>';
    }).join('');
  } else {
    rbSect.style.display = 'none';
  }
}

// click on a ref target link → expand parent chain if needed, then select & pan
function focusNode(id) {
  if (!nodesDS.get(id) || isOrphaned(id)) expandToRoot(id);
  network.selectNodes([id]);
  network.focus(id, { animation: { duration: 300, easingFunction: 'easeInOutQuad' }, scale: 1.2 });
  showNodeProperties(id);
}

// ── expand-to-root: show minimal path from root to target node ───────────────
function expandToRoot(id) {
  const chain = [];
  const seen  = new Set();
  let current = id;
  while (current && !seen.has(current)) {
    seen.add(current);
    chain.unshift(current);
    const parents = parentsOf[current] || [];
    if (!parents.length) break;
    current = parents[0];
  }
  // make each chain node visible; expand it only to reveal the next node in the chain
  for (let i = 0; i < chain.length; i++) {
    const nid = chain[i];
    showNode(nid);
    if (i < chain.length - 1) {
      // this ancestor needs to be expanded to show the next chain node
      expanded.add(nid);
      showNode(chain[i + 1]);
    }
  }
  render();
  network.focus(id, { animation: { duration: 400, easingFunction: 'easeInOutQuad' }, scale: 1.2 });
  showNodeProperties(id);
}

// ── double-click: expand-to-root for orphaned nodes ──────────────────────────
network.on('doubleClick', function(params) {
  if (!params.nodes.length) return;
  const id = params.nodes[0];
  if (isOrphaned(id)) expandToRoot(id);
});

// ── click: show properties; expand/collapse only on +/- badge ────────────────
function _clickedOnBadge(params, nodeId) {
  if (!(childrenOf[nodeId] || []).length) return false;
  const pos = network.getPositions([nodeId])[nodeId];
  if (!pos) return false;
  const n = nodeById[nodeId];
  const orphan = isOrphaned(nodeId);
  const nodeSize = n && n.isRoot ? 14 : (orphan ? 12 : 10);
  const offset = orphan ? 1.1 : 0.7;
  const bx = pos.x + nodeSize * offset;
  const by = pos.y + nodeSize * offset;
  // click position in canvas coordinates
  const canvasXY = params.pointer.canvas;
  const dx = canvasXY.x - bx;
  const dy = canvasXY.y - by;
  const r  = Math.max(8, 10 / network.getScale());     // generous hit area
  return (dx * dx + dy * dy) <= r * r;
}

network.on('click', function(params) {
  if (!params.nodes.length) return;
  const id = params.nodes[0];
  const shiftKey = params.event && params.event.srcEvent && params.event.srcEvent.shiftKey;
  const hitBadge = _clickedOnBadge(params, id);

  // always show properties
  showNodeProperties(id);

  // only expand/collapse when the +/- badge was clicked
  if (hitBadge) {
    if ((childrenOf[id] || []).length) {
      if (expanded.has(id)) {
        collapseSubtree(id);
      } else {
        shiftKey ? expandAll(id) : expandNode(id);
      }
      render();
    }
  }
});

// ── draw overlays: +/- badges and search highlights ──────────────────────────
network.on('afterDrawing', function(ctx) {
  const allPositions = network.getPositions();
  const scale = network.getScale();
  const ids = nodesDS.getIds();

  for (const id of ids) {
    const pos = allPositions[id];
    if (!pos) continue;
    const n = nodeById[id];
    const orphan = isOrphaned(id);
    const nodeSize = n && n.isRoot ? 14 : (orphan ? 12 : 10);

    // search highlight ring (canvas overlay — no DataSet mutation)
    if (_searchHits.size && _searchHits.has(id)) {
      ctx.save();
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, nodeSize + 5, 0, 2 * Math.PI);
      ctx.strokeStyle = '#d97706';
      ctx.lineWidth = 3 / scale;
      ctx.stroke();
      ctx.restore();
    }
    if (_selectedHit === id) {
      ctx.save();
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, nodeSize + 5, 0, 2 * Math.PI);
      ctx.strokeStyle = '#ef4444';
      ctx.lineWidth = 4 / scale;
      ctx.stroke();
      ctx.restore();
    }

    // +/- badge for expandable nodes
    if (!(childrenOf[id] || []).length) continue;
    const offset = orphan ? 1.1 : 0.7;
    const bx = pos.x + nodeSize * offset;
    const by = pos.y + nodeSize * offset;
    const r  = Math.max(5, 6 / scale);

    ctx.save();
    ctx.beginPath();
    ctx.arc(bx, by, r, 0, 2 * Math.PI);
    ctx.fillStyle = expanded.has(id) ? '#ef4444' : '#22c55e';
    ctx.fill();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 1.5 / scale;
    ctx.stroke();
    ctx.fillStyle = '#fff';
    ctx.font = 'bold ' + Math.max(9, 10 / scale) + 'px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(expanded.has(id) ? '−' : '+', bx, by);
    ctx.restore();
  }
});

// fit only on initial load, then just freeze physics on subsequent stabilizations
let _initialStabilization = true;
network.on('stabilizationIterationsDone', function() {
  if (_initialStabilization) {
    _initialStabilization = false;
    network.fit({ animation: { duration: 400, easingFunction: 'easeInOutQuad' } });
  }
  network.setOptions({ physics: false });
});

// ── view filter (all / system / ecuc) ─────────────────────────────────────────
function onFilterChange(mode) {
  _filterMode = mode;
  render();
  network.fit({ animation: { duration: 300, easingFunction: 'easeInOutQuad' } });
}

// ── sidebar toggle ────────────────────────────────────────────────────────────
let sidebarVisible = true;
function toggleSidebar() {
  const sb  = document.getElementById('sidebar');
  const btn = document.getElementById('sidebar-toggle');
  sidebarVisible = !sidebarVisible;
  sb.classList.toggle('collapsed', !sidebarVisible);
  btn.innerHTML = sidebarVisible ? '&#9664; Hide panel' : '&#9654; Show panel';
  setTimeout(() => { network.redraw(); network.fit(); }, 280);
}

// ── search / highlight with dropdown ──────────────────────────────────────────
const _searchInput = document.getElementById('search');
const _dropdown    = document.getElementById('search-dropdown');
let _ddActive      = -1;          // keyboard-selected index
let _searchHits    = new Set();   // ids of matched nodes (drawn via canvas overlay)
let _selectedHit   = null;        // single selected search result id

function _matchNode(n, lq) {
  return n.label.toLowerCase().includes(lq)
      || n.tag.toLowerCase().includes(lq)
      || n.path.toLowerCase().includes(lq)
      || Object.values(n.props || {}).some(v => String(v).toLowerCase().includes(lq));
}

function onSearchInput(q) {
  const counter = document.getElementById('match-count');
  _ddActive = -1;
  _selectedHit = null;

  if (!q) {
    counter.textContent = '';
    _dropdown.style.display = 'none';
    _searchHits = new Set();
    network.redraw();
    return;
  }

  const lq = q.toLowerCase();
  const matches = GRAPH.nodes.filter(n => {
    if (!_matchNode(n, lq)) return false;
    // skip nodes with no meaningful name (label == class name)
    if (n.label === n.tag) return false;
    // respect active view filter
    if (_filterMode === 'ecuc' && !_ecucNodes.has(n.id) && n.tag !== 'ARPackage') return false;
    if (_filterMode === 'system' && _ecucNodes.has(n.id)) return false;
    return true;
  });
  _searchHits = new Set(matches.map(n => n.id));
  network.redraw();

  counter.textContent = matches.length
    ? matches.length + ' match' + (matches.length > 1 ? 'es' : '')
    : 'no matches';

  // populate dropdown (cap at 30 items)
  const shown = matches.slice(0, 30);
  if (shown.length) {
    _dropdown.innerHTML = shown.map((n, i) => {
      const shortPath = n.path ? ' (' + n.path.split('/').slice(-3).join('/') + ')' : '';
      return '<li data-id="' + n.id + '" onmousedown="selectSearchResult(\'' + n.id + '\')">'
        + '<span>' + esc(n.label) + '<span class="dd-path">' + esc(shortPath) + '</span></span>'
        + '<span class="dd-tag">' + esc(n.tag) + '</span></li>';
    }).join('');
    if (matches.length > 30) {
      _dropdown.innerHTML += '<li style="color:#999;font-style:italic;cursor:default">… and '
        + (matches.length - 30) + ' more</li>';
    }
    _dropdown.style.display = 'block';
  } else {
    _dropdown.style.display = 'none';
  }
}

function selectSearchResult(id) {
  _dropdown.style.display = 'none';
  _searchInput.value = nodeById[id] ? nodeById[id].label : '';
  _searchHits = new Set();
  _selectedHit = id;
  document.getElementById('match-count').textContent = '';

  // ensure the node is visible — expand its parent chain if needed
  if (!nodesDS.get(id) || isOrphaned(id)) {
    expandToRoot(id);                    // already does render + focus + showNodeProperties
  } else {
    network.selectNodes([id]);
    network.focus(id, { animation: { duration: 300, easingFunction: 'easeInOutQuad' }, scale: 1.2 });
    showNodeProperties(id);
  }
  network.redraw();
}

// keyboard navigation in dropdown
_searchInput.addEventListener('keydown', function(e) {
  const items = _dropdown.querySelectorAll('li[data-id]');
  if (!items.length || _dropdown.style.display === 'none') return;
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    _ddActive = Math.min(_ddActive + 1, items.length - 1);
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    _ddActive = Math.max(_ddActive - 1, 0);
  } else if (e.key === 'Enter' && _ddActive >= 0) {
    e.preventDefault();
    selectSearchResult(items[_ddActive].dataset.id);
    return;
  } else if (e.key === 'Escape') {
    _dropdown.style.display = 'none';
    return;
  } else { return; }
  items.forEach((li, i) => li.classList.toggle('active', i === _ddActive));
  items[_ddActive].scrollIntoView({ block: 'nearest' });
});

// close dropdown when clicking outside
document.addEventListener('click', function(e) {
  if (!e.target.closest('#search-wrap')) _dropdown.style.display = 'none';
});

// ── reset view ────────────────────────────────────────────────────────────────
function resetView() {
  network.fit({ animation: { duration: 350, easingFunction: 'easeInOutQuad' } });
}

function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ── context menu (right-click) ───────────────────────────────────────────────
const _ctxMenu = document.getElementById('ctx-menu');
let _ctxNodeId = null;

function _copyText(text) {
  navigator.clipboard.writeText(text).then(function() {
    _ctxMenu.style.display = 'none';
  });
}

function _showCtxMenu(x, y, id) {
  const n = nodeById[id];
  if (!n) return;
  _ctxNodeId = id;
  const items = [];
  items.push('<li onclick="_copyText(\'' + esc(n.label).replace(/'/g, "\\'") + '\')">Copy short name</li>');
  if (n.path) {
    items.push('<li onclick="_copyText(\'' + esc(n.path).replace(/'/g, "\\'") + '\')">Copy path</li>');
  }
  if (n.defName) {
    items.push('<li onclick="_copyText(\'' + esc(n.defName).replace(/'/g, "\\'") + '\')">Copy definition name</li>');
  }
  // copy all properties as text
  const props = n.props || {};
  const propKeys = Object.keys(props);
  if (propKeys.length) {
    const propText = propKeys.map(function(k) { return k + ': ' + props[k]; }).join('\\n');
    items.push('<li class="ctx-sep" onclick="_copyText(\'' + propText.replace(/'/g, "\\'") + '\')">Copy all properties</li>');
  }
  // copy full node summary
  let summary = 'Name: ' + n.label + '\\nType: ' + n.tag;
  if (n.defName) summary += '\\nDefinition: ' + n.defName;
  if (n.path) summary += '\\nPath: ' + n.path;
  propKeys.forEach(function(k) { summary += '\\n' + k + ': ' + props[k]; });
  items.push('<li onclick="_copyText(\'' + summary.replace(/'/g, "\\'") + '\')">Copy full summary</li>');

  _ctxMenu.innerHTML = items.join('');
  _ctxMenu.style.display = 'block';
  _ctxMenu.style.left = Math.min(x, window.innerWidth - 200) + 'px';
  _ctxMenu.style.top = Math.min(y, window.innerHeight - 200) + 'px';
}

// right-click on graph node
network.on('oncontext', function(params) {
  params.event.preventDefault();
  var nodeId = null;
  if (params.nodes && params.nodes.length) {
    nodeId = params.nodes[0];
  } else {
    // check if right-click is near a node
    var nearest = network.getNodeAt(params.pointer.DOM);
    if (nearest) nodeId = nearest;
  }
  if (nodeId) {
    var domEvent = params.event.srcEvent || params.event;
    _showCtxMenu(domEvent.clientX || domEvent.pageX, domEvent.clientY || domEvent.pageY, nodeId);
  }
});

// right-click on properties panel header
document.getElementById('prop-header').addEventListener('contextmenu', function(e) {
  e.preventDefault();
  if (_ctxNodeId || document.getElementById('prop-name').textContent) {
    // find node by displayed name
    const name = document.getElementById('prop-name').textContent;
    const n = GRAPH.nodes.find(function(nd) { return nd.label === name; });
    if (n) _showCtxMenu(e.clientX, e.clientY, n.id);
  }
});

// close context menu on click elsewhere
document.addEventListener('click', function() { _ctxMenu.style.display = 'none'; });

render();
</script>
