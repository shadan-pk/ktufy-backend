// ═══════════════════════════════════════════════════════════════════════════════
// KTUfy Knowledge Graph — Force-directed Interactive Visualization
// Shadcn-inspired dark theme, canvas-based, with physics simulation
// ═══════════════════════════════════════════════════════════════════════════════

const GRAPH = {
    nodes: [],
    edges: [],
    filteredNodes: new Set(),   // ids visible after search filter
    canvas: null,
    ctx: null,
    width: 0,
    height: 0,
    dpr: 1,

    // Camera
    offsetX: 0,
    offsetY: 0,
    zoom: 1,

    // Interaction
    dragging: null,          // node being dragged
    panning: false,
    panMoved: false,
    panStart: { x: 0, y: 0 },
    hoveredNode: null,
    selectedNode: null,

    // Physics
    physicsEnabled: true,
    labelsEnabled: true,
    alpha: 1,                // simulation "heat"
    alphaDecay: 0.0028,
    alphaMin: 0.001,
    velocityDecay: 0.55,

    // Forces
    repulsion: 2800,
    linkDistance: 110,
    linkStrength: 0.35,
    centerStrength: 0.012,
    gravity: 0.02,

    // Styling
    colors: {
        subject:  '#f59e0b',
        module:   '#6366f1',
        concept:  '#ec4899',
        edge:     'rgba(148,163,184,0.25)',
        edgeHighlight: 'rgba(148,163,184,0.7)',
        text:     '#e2e8f0',
        textDim:  '#94a3b8',
        bg:       '#09090b',
    },
    nodeRadius: { subject: 22, module: 15, concept: 10 },

    animFrameId: null,
};

// ─────────────────────────────────────────────────────────────────────────────
// Initialization
// ─────────────────────────────────────────────────────────────────────────────

function initGraph(canvasId) {
    GRAPH.canvas = document.getElementById(canvasId);
    if (!GRAPH.canvas) return;
    GRAPH.ctx = GRAPH.canvas.getContext('2d');
    GRAPH.dpr = window.devicePixelRatio || 1;

    resizeGraphCanvas();
    window.addEventListener('resize', resizeGraphCanvas);

    // Mouse events
    GRAPH.canvas.addEventListener('mousedown', onGraphMouseDown);
    GRAPH.canvas.addEventListener('mousemove', onGraphMouseMove);
    GRAPH.canvas.addEventListener('mouseup', onGraphMouseUp);
    GRAPH.canvas.addEventListener('wheel', onGraphWheel, { passive: false });
    GRAPH.canvas.addEventListener('dblclick', onGraphDblClick);

    // Touch events
    GRAPH.canvas.addEventListener('touchstart', onGraphTouchStart, { passive: false });
    GRAPH.canvas.addEventListener('touchmove', onGraphTouchMove, { passive: false });
    GRAPH.canvas.addEventListener('touchend', onGraphTouchEnd);
}

function resizeGraphCanvas() {
    if (!GRAPH.canvas) return;
    const rect = GRAPH.canvas.parentElement.getBoundingClientRect();
    GRAPH.width = rect.width;
    GRAPH.height = rect.height;
    GRAPH.canvas.width = GRAPH.width * GRAPH.dpr;
    GRAPH.canvas.height = GRAPH.height * GRAPH.dpr;
    GRAPH.canvas.style.width = GRAPH.width + 'px';
    GRAPH.canvas.style.height = GRAPH.height + 'px';
    GRAPH.ctx.setTransform(GRAPH.dpr, 0, 0, GRAPH.dpr, 0, 0);
}

// ─────────────────────────────────────────────────────────────────────────────
// Data Loading
// ─────────────────────────────────────────────────────────────────────────────

async function loadGraphData() {
    const regEl = document.getElementById('graph-filter-regulation');
    const semEl = document.getElementById('graph-filter-semester');
    const regulation = regEl ? regEl.value : '';
    const semester = semEl ? semEl.value : '';

    let url = `${API_BASE}/graph/data?`;
    if (regulation) url += `regulation=${regulation}&`;
    if (semester) url += `semester=${semester}&`;

    try {
        const response = await fetch(url);
        const data = await response.json();

        // Re-init canvas if section just became visible
        const section = document.getElementById('graph-section');
        if (section && section.classList.contains('active')) {
            initGraph('graph-canvas');
        }

        setGraphData(data.nodes || [], data.edges || []);
    } catch (err) {
        console.error('Failed to load graph data:', err);
    }
}

function setGraphData(nodes, edges) {
    // Initialize positions in a circle pattern for stable start
    const cx = GRAPH.width / 2;
    const cy = GRAPH.height / 2;

    // Group subjects, then arrange modules and concepts nearby
    const subjectNodes = nodes.filter(n => n.type === 'subject');
    const moduleNodes = nodes.filter(n => n.type === 'module');
    const conceptNodes = nodes.filter(n => n.type === 'concept');

    const angleStep = (2 * Math.PI) / Math.max(subjectNodes.length, 1);

    subjectNodes.forEach((n, i) => {
        n.x = cx + Math.cos(angleStep * i) * 200 + (Math.random() - 0.5) * 30;
        n.y = cy + Math.sin(angleStep * i) * 200 + (Math.random() - 0.5) * 30;
        n.vx = 0; n.vy = 0;
        n.fx = null; n.fy = null; // pinned coords when dragging
    });

    moduleNodes.forEach(n => {
        const parent = subjectNodes.find(s => s.id === n.subject_code);
        const bx = parent ? parent.x : cx;
        const by = parent ? parent.y : cy;
        n.x = bx + (Math.random() - 0.5) * 150;
        n.y = by + (Math.random() - 0.5) * 150;
        n.vx = 0; n.vy = 0;
        n.fx = null; n.fy = null;
    });

    conceptNodes.forEach(n => {
        const parent = moduleNodes.find(m => m.id === n.module_id);
        const bx = parent ? parent.x : cx;
        const by = parent ? parent.y : cy;
        n.x = bx + (Math.random() - 0.5) * 100;
        n.y = by + (Math.random() - 0.5) * 100;
        n.vx = 0; n.vy = 0;
        n.fx = null; n.fy = null;
    });

    GRAPH.nodes = [...subjectNodes, ...moduleNodes, ...conceptNodes];
    GRAPH.edges = edges;
    GRAPH.filteredNodes = new Set(GRAPH.nodes.map(n => n.id));
    GRAPH.alpha = 1;
    GRAPH.selectedNode = null;
    GRAPH.hoveredNode = null;

    // Build adjacency for quick lookup
    GRAPH.adjacency = {};
    GRAPH.edges.forEach(e => {
        if (!GRAPH.adjacency[e.from]) GRAPH.adjacency[e.from] = [];
        if (!GRAPH.adjacency[e.to]) GRAPH.adjacency[e.to] = [];
        GRAPH.adjacency[e.from].push(e.to);
        GRAPH.adjacency[e.to].push(e.from);
    });

    // Center camera
    graphResetView();

    // Build index
    GRAPH.nodeMap = {};
    GRAPH.nodes.forEach(n => GRAPH.nodeMap[n.id] = n);

    // Update stats
    const statsBar = document.getElementById('graph-stats-bar');
    if (statsBar) {
        statsBar.textContent = `${GRAPH.nodes.length} nodes · ${GRAPH.edges.length} edges`;
    }

    // Init canvas & start simulation if not already running
    if (!GRAPH.canvas || GRAPH.width === 0) {
        // Defer init — canvas may not be visible yet (e.g. called from dashboard)
        requestAnimationFrame(() => {
            initGraph('graph-canvas');
            if (GRAPH.width > 0) {
                graphResetView();
                startSimulation();
            }
        });
    } else {
        graphResetView();
        startSimulation();
    }

    // Also render mini graph on dashboard
    renderMiniGraph();
}

// ─────────────────────────────────────────────────────────────────────────────
// Physics Simulation (Force-directed)
// ─────────────────────────────────────────────────────────────────────────────

function startSimulation() {
    if (GRAPH.animFrameId) cancelAnimationFrame(GRAPH.animFrameId);
    GRAPH.alpha = 1;
    tick();
}

function tick() {
    if (GRAPH.physicsEnabled && GRAPH.alpha > GRAPH.alphaMin) {
        simulateForces();
        GRAPH.alpha = Math.max(GRAPH.alpha - GRAPH.alphaDecay, 0);
    }
    renderGraph();
    GRAPH.animFrameId = requestAnimationFrame(tick);
}

function simulateForces() {
    const nodes = GRAPH.nodes;
    const edges = GRAPH.edges;
    const alpha = GRAPH.alpha;

    // Center gravity
    const cx = GRAPH.width / 2;
    const cy = GRAPH.height / 2;

    for (let i = 0; i < nodes.length; i++) {
        const n = nodes[i];
        if (n.fx !== null) { n.x = n.fx; n.y = n.fy; n.vx = 0; n.vy = 0; continue; }

        // Gravity toward center
        n.vx += (cx - n.x) * GRAPH.centerStrength * alpha;
        n.vy += (cy - n.y) * GRAPH.centerStrength * alpha;
    }

    // Node-node repulsion (Barnes-Hut would be better at scale, but direct is fine for <500 nodes)
    for (let i = 0; i < nodes.length; i++) {
        if (nodes[i].fx !== null) continue;
        for (let j = i + 1; j < nodes.length; j++) {
            const a = nodes[i], b = nodes[j];
            let dx = b.x - a.x;
            let dy = b.y - a.y;
            let dist = Math.sqrt(dx * dx + dy * dy) || 1;
            let force = -GRAPH.repulsion * alpha / (dist * dist);
            let fx = dx / dist * force;
            let fy = dy / dist * force;
            if (a.fx === null) { a.vx -= fx; a.vy -= fy; }
            if (b.fx === null) { b.vx += fx; b.vy += fy; }
        }
    }

    // Link attraction
    for (const edge of edges) {
        const a = GRAPH.nodeMap[edge.from];
        const b = GRAPH.nodeMap[edge.to];
        if (!a || !b) continue;
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        let dist = Math.sqrt(dx * dx + dy * dy) || 1;
        let force = (dist - GRAPH.linkDistance) * GRAPH.linkStrength * alpha;
        let fx = dx / dist * force;
        let fy = dy / dist * force;
        if (a.fx === null) { a.vx += fx; a.vy += fy; }
        if (b.fx === null) { b.vx -= fx; b.vy -= fy; }
    }

    // Apply velocity
    for (const n of nodes) {
        if (n.fx !== null) continue;
        n.vx *= GRAPH.velocityDecay;
        n.vy *= GRAPH.velocityDecay;
        n.x += n.vx;
        n.y += n.vy;
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Rendering
// ─────────────────────────────────────────────────────────────────────────────

function renderGraph() {
    const ctx = GRAPH.ctx;
    if (!ctx) return;
    const w = GRAPH.width, h = GRAPH.height;
    const z = GRAPH.zoom, ox = GRAPH.offsetX, oy = GRAPH.offsetY;

    ctx.clearRect(0, 0, w, h);

    // Background
    ctx.fillStyle = GRAPH.colors.bg;
    ctx.fillRect(0, 0, w, h);

    // Subtle grid
    ctx.save();
    ctx.translate(ox, oy);
    ctx.scale(z, z);
    drawGrid(ctx, w, h, z, ox, oy);

    const highlighted = new Set();
    if (GRAPH.hoveredNode || GRAPH.selectedNode) {
        const focusId = (GRAPH.hoveredNode || GRAPH.selectedNode).id;
        highlighted.add(focusId);
        (GRAPH.adjacency[focusId] || []).forEach(id => highlighted.add(id));
    }

    // Draw edges
    for (const edge of GRAPH.edges) {
        const a = GRAPH.nodeMap[edge.from];
        const b = GRAPH.nodeMap[edge.to];
        if (!a || !b) continue;
        if (!GRAPH.filteredNodes.has(a.id) && !GRAPH.filteredNodes.has(b.id)) continue;

        const isHL = highlighted.size > 0 && highlighted.has(a.id) && highlighted.has(b.id);
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.strokeStyle = isHL ? GRAPH.colors.edgeHighlight : GRAPH.colors.edge;
        ctx.lineWidth = isHL ? 1.8 : 0.8;
        ctx.stroke();

        // Edge label
        if (GRAPH.labelsEnabled && z > 0.6 && isHL) {
            const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
            ctx.fillStyle = GRAPH.colors.textDim;
            ctx.font = `${9 / z}px Inter, sans-serif`;
            ctx.textAlign = 'center';
            ctx.fillText(edge.type, mx, my - 4 / z);
        }
    }

    // Draw nodes
    for (const node of GRAPH.nodes) {
        if (!GRAPH.filteredNodes.has(node.id)) continue;
        const r = getNodeRadius(node);
        const isHover = GRAPH.hoveredNode === node;
        const isSelected = GRAPH.selectedNode === node;
        const dim = highlighted.size > 0 && !highlighted.has(node.id);

        // Glow for hovered/selected
        if (isHover || isSelected) {
            ctx.beginPath();
            ctx.arc(node.x, node.y, r + 6, 0, Math.PI * 2);
            ctx.fillStyle = getNodeColor(node, 0.2);
            ctx.fill();
        }

        // Node circle
        ctx.beginPath();
        ctx.arc(node.x, node.y, r, 0, Math.PI * 2);
        ctx.fillStyle = dim ? getNodeColor(node, 0.3) : getNodeColor(node, 0.9);
        ctx.fill();

        // Border
        ctx.strokeStyle = dim ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.15)';
        ctx.lineWidth = isSelected ? 2.5 : 1;
        ctx.stroke();

        // Label
        if (GRAPH.labelsEnabled && z > 0.35) {
            const label = truncateLabel(node.label || node.id, z);
            const fontSize = Math.max(8, Math.min(12, 11 / z));
            ctx.font = `500 ${fontSize}px Inter, sans-serif`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'top';
            ctx.fillStyle = dim ? 'rgba(226,232,240,0.3)' : GRAPH.colors.text;
            ctx.fillText(label, node.x, node.y + r + 4);
        }
    }

    ctx.restore();
}

function drawGrid(ctx, w, h, z, ox, oy) {
    const step = 60;
    ctx.strokeStyle = 'rgba(255,255,255,0.025)';
    ctx.lineWidth = 0.5 / z;
    const startX = Math.floor(-ox / z / step) * step - step;
    const startY = Math.floor(-oy / z / step) * step - step;
    const endX = startX + w / z + step * 2;
    const endY = startY + h / z + step * 2;
    for (let x = startX; x < endX; x += step) {
        ctx.beginPath(); ctx.moveTo(x, startY); ctx.lineTo(x, endY); ctx.stroke();
    }
    for (let y = startY; y < endY; y += step) {
        ctx.beginPath(); ctx.moveTo(startX, y); ctx.lineTo(endX, y); ctx.stroke();
    }
}

function getNodeRadius(node) {
    return GRAPH.nodeRadius[node.type] || 10;
}

function getNodeColor(node, alpha = 1) {
    const c = GRAPH.colors[node.type] || '#94a3b8';
    if (alpha >= 0.9) return c;
    // Convert hex to rgba
    const r = parseInt(c.slice(1,3), 16);
    const g = parseInt(c.slice(3,5), 16);
    const b = parseInt(c.slice(5,7), 16);
    return `rgba(${r},${g},${b},${alpha})`;
}

function truncateLabel(label, zoom) {
    const maxLen = zoom > 0.8 ? 20 : zoom > 0.5 ? 14 : 10;
    return label.length > maxLen ? label.slice(0, maxLen - 1) + '…' : label;
}

// ─────────────────────────────────────────────────────────────────────────────
// Mouse / Touch Interaction
// ─────────────────────────────────────────────────────────────────────────────

function screenToWorld(sx, sy) {
    return {
        x: (sx - GRAPH.offsetX) / GRAPH.zoom,
        y: (sy - GRAPH.offsetY) / GRAPH.zoom,
    };
}

function getCanvasXY(e) {
    const rect = GRAPH.canvas.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
}

function findNodeAt(wx, wy) {
    // Search in reverse (topmost first)
    for (let i = GRAPH.nodes.length - 1; i >= 0; i--) {
        const n = GRAPH.nodes[i];
        if (!GRAPH.filteredNodes.has(n.id)) continue;
        const r = getNodeRadius(n) + 4;
        const dx = n.x - wx, dy = n.y - wy;
        if (dx * dx + dy * dy <= r * r) return n;
    }
    return null;
}

function onGraphMouseDown(e) {
    const { x, y } = getCanvasXY(e);
    const { x: wx, y: wy } = screenToWorld(x, y);
    const node = findNodeAt(wx, wy);

    if (node) {
        GRAPH.dragging = node;
        node.fx = node.x;
        node.fy = node.y;
        GRAPH.canvas.style.cursor = 'grabbing';
        GRAPH.alpha = Math.max(GRAPH.alpha, 0.3); // reheat
    } else {
        GRAPH.panning = true;
        GRAPH.panMoved = false;
        GRAPH.panStart = { x: x - GRAPH.offsetX, y: y - GRAPH.offsetY };
        GRAPH.canvas.style.cursor = 'grabbing';
    }
}

function onGraphMouseMove(e) {
    const { x, y } = getCanvasXY(e);
    const { x: wx, y: wy } = screenToWorld(x, y);

    if (GRAPH.dragging) {
        GRAPH.dragging.fx = wx;
        GRAPH.dragging.fy = wy;
        GRAPH.dragging.x = wx;
        GRAPH.dragging.y = wy;
        GRAPH.alpha = Math.max(GRAPH.alpha, 0.1);
        return;
    }

    if (GRAPH.panning) {
        GRAPH.offsetX = x - GRAPH.panStart.x;
        GRAPH.offsetY = y - GRAPH.panStart.y;
        GRAPH.panMoved = true;
        return;
    }

    // Hover detection
    const node = findNodeAt(wx, wy);
    if (node !== GRAPH.hoveredNode) {
        GRAPH.hoveredNode = node;
        GRAPH.canvas.style.cursor = node ? 'pointer' : 'grab';
    }
}

function onGraphMouseUp(e) {
    if (GRAPH.dragging) {
        // Unpin after drag unless shift held
        if (!e.shiftKey) {
            GRAPH.dragging.fx = null;
            GRAPH.dragging.fy = null;
        }
        GRAPH.dragging = null;
    } else if (!GRAPH.panMoved) {
        // Click (no drag, no pan) — select or deselect
        const { x, y } = getCanvasXY(e);
        const { x: wx, y: wy } = screenToWorld(x, y);
        const node = findNodeAt(wx, wy);
        if (node) {
            selectGraphNode(node);
        } else {
            GRAPH.selectedNode = null;
            hideInfoPanel();
        }
    }

    GRAPH.panning = false;
    GRAPH.panMoved = false;
    GRAPH.canvas.style.cursor = 'grab';
}

function onGraphWheel(e) {
    e.preventDefault();
    const { x, y } = getCanvasXY(e);
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    const newZoom = Math.max(0.1, Math.min(5, GRAPH.zoom * delta));

    // Zoom toward cursor
    GRAPH.offsetX = x - (x - GRAPH.offsetX) * (newZoom / GRAPH.zoom);
    GRAPH.offsetY = y - (y - GRAPH.offsetY) * (newZoom / GRAPH.zoom);
    GRAPH.zoom = newZoom;
}

function onGraphDblClick(e) {
    const { x, y } = getCanvasXY(e);
    const { x: wx, y: wy } = screenToWorld(x, y);
    const node = findNodeAt(wx, wy);
    if (node && node.type === 'subject') {
        // Open subject details
        if (typeof showSubjectDetails === 'function') {
            showSubjectDetails(node.id, node.regulation || '2019');
        }
    }
}

// Touch handlers
let touchStartDist = 0;
let touchStartZoom = 1;

function onGraphTouchStart(e) {
    e.preventDefault();
    if (e.touches.length === 1) {
        const touch = e.touches[0];
        const fakeEvent = { clientX: touch.clientX, clientY: touch.clientY, shiftKey: false };
        onGraphMouseDown(fakeEvent);
    } else if (e.touches.length === 2) {
        // Pinch zoom start
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        touchStartDist = Math.sqrt(dx * dx + dy * dy);
        touchStartZoom = GRAPH.zoom;
    }
}

function onGraphTouchMove(e) {
    e.preventDefault();
    if (e.touches.length === 1) {
        const touch = e.touches[0];
        onGraphMouseMove({ clientX: touch.clientX, clientY: touch.clientY });
    } else if (e.touches.length === 2) {
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        const dist = Math.sqrt(dx * dx + dy * dy);
        GRAPH.zoom = Math.max(0.1, Math.min(5, touchStartZoom * (dist / touchStartDist)));
    }
}

function onGraphTouchEnd(e) {
    onGraphMouseUp({ shiftKey: false, clientX: 0, clientY: 0 });
}

// ─────────────────────────────────────────────────────────────────────────────
// Node Selection & Info Panel
// ─────────────────────────────────────────────────────────────────────────────

function selectGraphNode(node) {
    GRAPH.selectedNode = node;
    const panel = document.getElementById('graph-info-panel');
    const titleEl = document.getElementById('graph-info-title');
    const contentEl = document.getElementById('graph-info-content');
    if (!panel || !titleEl || !contentEl) return;

    const typeBadge = `<span style="display:inline-block;padding:2px 8px;border-radius:9999px;font-size:0.7rem;font-weight:600;color:#fff;background:${GRAPH.colors[node.type]}">${node.type}</span>`;

    titleEl.innerHTML = `${escapeHtml(node.label || node.id)} ${typeBadge}`;

    let html = `<div class="info-row"><span class="info-label">ID</span><span>${escapeHtml(node.id)}</span></div>`;

    if (node.type === 'subject') {
        html += `<div class="info-row"><span class="info-label">Semester</span><span>S${node.semester || '?'}</span></div>`;
        html += `<div class="info-row"><span class="info-label">Branch</span><span>${node.branch || '?'}</span></div>`;
        html += `<div class="info-row"><span class="info-label">Regulation</span><span>${node.regulation || '?'}</span></div>`;
    }
    if (node.type === 'module') {
        html += `<div class="info-row"><span class="info-label">Module #</span><span>${node.number || '?'}</span></div>`;
        html += `<div class="info-row"><span class="info-label">Subject</span><span>${node.subject_code || '?'}</span></div>`;
    }
    if (node.type === 'concept') {
        html += `<div class="info-row"><span class="info-label">Module</span><span>${node.module_id || '?'}</span></div>`;
    }

    // Connected nodes
    const neighbors = GRAPH.adjacency[node.id] || [];
    html += `<div style="margin-top:8px;border-top:1px solid var(--border);padding-top:8px"><span class="info-label">Connections: ${neighbors.length}</span></div>`;

    contentEl.innerHTML = html;
    panel.classList.add('visible');
}

function hideInfoPanel() {
    const panel = document.getElementById('graph-info-panel');
    if (panel) panel.classList.remove('visible');
}

// ─────────────────────────────────────────────────────────────────────────────
// Controls
// ─────────────────────────────────────────────────────────────────────────────

function graphZoomIn() {
    const cx = GRAPH.width / 2, cy = GRAPH.height / 2;
    const newZoom = Math.min(5, GRAPH.zoom * 1.3);
    GRAPH.offsetX = cx - (cx - GRAPH.offsetX) * (newZoom / GRAPH.zoom);
    GRAPH.offsetY = cy - (cy - GRAPH.offsetY) * (newZoom / GRAPH.zoom);
    GRAPH.zoom = newZoom;
}

function graphZoomOut() {
    const cx = GRAPH.width / 2, cy = GRAPH.height / 2;
    const newZoom = Math.max(0.1, GRAPH.zoom * 0.75);
    GRAPH.offsetX = cx - (cx - GRAPH.offsetX) * (newZoom / GRAPH.zoom);
    GRAPH.offsetY = cy - (cy - GRAPH.offsetY) * (newZoom / GRAPH.zoom);
    GRAPH.zoom = newZoom;
}

function graphResetView() {
    if (GRAPH.nodes.length === 0) {
        GRAPH.offsetX = 0;
        GRAPH.offsetY = 0;
        GRAPH.zoom = 1;
        return;
    }
    // Fit all nodes
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    GRAPH.nodes.forEach(n => {
        if (n.x < minX) minX = n.x;
        if (n.y < minY) minY = n.y;
        if (n.x > maxX) maxX = n.x;
        if (n.y > maxY) maxY = n.y;
    });
    const pad = 60;
    const gw = maxX - minX + pad * 2;
    const gh = maxY - minY + pad * 2;
    GRAPH.zoom = Math.min(GRAPH.width / gw, GRAPH.height / gh, 2);
    GRAPH.offsetX = GRAPH.width / 2 - ((minX + maxX) / 2) * GRAPH.zoom;
    GRAPH.offsetY = GRAPH.height / 2 - ((minY + maxY) / 2) * GRAPH.zoom;
}

function toggleGraphLabels() {
    GRAPH.labelsEnabled = !GRAPH.labelsEnabled;
    document.getElementById('graph-toggle-labels')?.classList.toggle('active', GRAPH.labelsEnabled);
}

function toggleGraphPhysics() {
    GRAPH.physicsEnabled = !GRAPH.physicsEnabled;
    document.getElementById('graph-toggle-physics')?.classList.toggle('active', GRAPH.physicsEnabled);
    if (GRAPH.physicsEnabled) {
        GRAPH.alpha = 0.5;
        // Unpin all nodes
        GRAPH.nodes.forEach(n => { n.fx = null; n.fy = null; });
    }
}

function filterGraphNodes(query) {
    query = (query || '').toLowerCase().trim();
    if (!query) {
        GRAPH.filteredNodes = new Set(GRAPH.nodes.map(n => n.id));
        return;
    }
    const matched = new Set();
    GRAPH.nodes.forEach(n => {
        if ((n.label || '').toLowerCase().includes(query) || n.id.toLowerCase().includes(query)) {
            matched.add(n.id);
            // Also show connected nodes
            (GRAPH.adjacency[n.id] || []).forEach(id => matched.add(id));
        }
    });
    GRAPH.filteredNodes = matched;
}

// ─────────────────────────────────────────────────────────────────────────────
// Mini Graph (Dashboard preview)
// ─────────────────────────────────────────────────────────────────────────────

function renderMiniGraph() {
    const miniCanvas = document.getElementById('dashboard-mini-graph');
    if (!miniCanvas || GRAPH.nodes.length === 0) return;

    const ctx = miniCanvas.getContext('2d');
    const rect = miniCanvas.parentElement.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    miniCanvas.width = rect.width * dpr;
    miniCanvas.height = rect.height * dpr;
    miniCanvas.style.width = rect.width + 'px';
    miniCanvas.style.height = rect.height + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const w = rect.width, h = rect.height;
    ctx.fillStyle = GRAPH.colors.bg;
    ctx.fillRect(0, 0, w, h);

    // Fit nodes to mini canvas
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    GRAPH.nodes.forEach(n => {
        if (n.x < minX) minX = n.x;
        if (n.y < minY) minY = n.y;
        if (n.x > maxX) maxX = n.x;
        if (n.y > maxY) maxY = n.y;
    });
    const pad = 30;
    const gw = maxX - minX + pad * 2 || 1;
    const gh = maxY - minY + pad * 2 || 1;
    const scale = Math.min(w / gw, h / gh, 1.5);
    const offX = w / 2 - ((minX + maxX) / 2) * scale;
    const offY = h / 2 - ((minY + maxY) / 2) * scale;

    ctx.save();
    ctx.translate(offX, offY);
    ctx.scale(scale, scale);

    // Edges
    for (const edge of GRAPH.edges) {
        const a = GRAPH.nodeMap[edge.from];
        const b = GRAPH.nodeMap[edge.to];
        if (!a || !b) continue;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.strokeStyle = 'rgba(148,163,184,0.15)';
        ctx.lineWidth = 0.5 / scale;
        ctx.stroke();
    }

    // Nodes
    for (const node of GRAPH.nodes) {
        const r = (GRAPH.nodeRadius[node.type] || 8) * 0.6;
        ctx.beginPath();
        ctx.arc(node.x, node.y, r, 0, Math.PI * 2);
        ctx.fillStyle = getNodeColor(node, 0.8);
        ctx.fill();
    }

    ctx.restore();
}
