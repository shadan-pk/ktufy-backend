// KTUfy Admin Dashboard JavaScript — Shadcn-inspired UI
// All API endpoints remain unchanged from previous version.

const API_BASE_V1 = '/api/v1/admin';
const API_BASE_V2 = '/api/v2/admin';
const API_BASE = API_BASE_V1; // legacy base for graph.js

let activeUsersIntervalId = null;

// ═══════════════════════════════════════════════════════════════════════════════
// Custom Select Dropdown Component
// Replaces native <select> with styled Shadcn-like dropdown
// ═══════════════════════════════════════════════════════════════════════════════

class CustomSelect {
    constructor(wrapper) {
        this.wrapper = wrapper;
        this.wrapper._customSelect = this; // Store instance for programmatic access
        this.nativeSelect = wrapper.querySelector('select');
        if (!this.nativeSelect) return;

        this.onchangeFn = wrapper.dataset.onchange || null;
        this.options = Array.from(this.nativeSelect.options);
        this.isOpen = false;

        this.build();
        this.bindEvents();
    }

    build() {
        // Create trigger button
        this.trigger = document.createElement('button');
        this.trigger.type = 'button';
        this.trigger.className = 'custom-select-trigger';

        const selected = this.options.find(o => o.selected) || this.options[0];
        const isPlaceholder = !selected.value;

        this.trigger.innerHTML = `
            <span class="trigger-text ${isPlaceholder ? 'placeholder' : ''}">${selected.text}</span>
            <svg class="chevron" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>
        `;

        // Create dropdown list
        this.dropdown = document.createElement('div');
        this.dropdown.className = 'custom-select-dropdown';

        this.options.forEach(opt => {
            const item = document.createElement('div');
            item.className = `custom-select-option${opt.selected ? ' selected' : ''}`;
            item.dataset.value = opt.value;
            item.innerHTML = `
                <svg class="check-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
                <span>${opt.text}</span>
            `;
            this.dropdown.appendChild(item);
        });

        // Insert into DOM
        this.wrapper.appendChild(this.trigger);
        this.wrapper.appendChild(this.dropdown);
    }

    bindEvents() {
        // Toggle dropdown
        this.trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            // Close all other open selects first
            document.querySelectorAll('.custom-select.open').forEach(other => {
                if (other !== this.wrapper) other.classList.remove('open');
            });
            this.isOpen = !this.isOpen;
            this.wrapper.classList.toggle('open', this.isOpen);
        });

        // Option click
        this.dropdown.addEventListener('click', (e) => {
            const option = e.target.closest('.custom-select-option');
            if (!option) return;

            const value = option.dataset.value;
            const text = option.querySelector('span').textContent;

            // Update native select
            this.nativeSelect.value = value;

            // Update UI
            const triggerText = this.trigger.querySelector('.trigger-text');
            triggerText.textContent = text;
            triggerText.classList.toggle('placeholder', !value);

            // Update selected state
            this.dropdown.querySelectorAll('.custom-select-option').forEach(o => o.classList.remove('selected'));
            option.classList.add('selected');

            // Close dropdown
            this.isOpen = false;
            this.wrapper.classList.remove('open');

            // Trigger native change event
            this.nativeSelect.dispatchEvent(new Event('change', { bubbles: true }));

            // Trigger change callback
            if (this.onchangeFn && typeof window[this.onchangeFn] === 'function') {
                window[this.onchangeFn](this.nativeSelect.value);
            }
        });
    }

    // Programmatic value set
    setValue(value) {
        this.nativeSelect.value = value;
        const opt = this.options.find(o => o.value === value);
        if (opt) {
            const triggerText = this.trigger.querySelector('.trigger-text');
            triggerText.textContent = opt.text;
            triggerText.classList.toggle('placeholder', !value);
            this.dropdown.querySelectorAll('.custom-select-option').forEach(o => {
                o.classList.toggle('selected', o.dataset.value === value);
            });
            
            // Trigger native change event
            this.nativeSelect.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }
}

// Close all dropdowns on outside click
document.addEventListener('click', () => {
    document.querySelectorAll('.custom-select.open').forEach(s => s.classList.remove('open'));
});

// Init all custom selects
function initCustomSelects(scope = document) {
    scope.querySelectorAll('.custom-select').forEach(wrapper => {
        // Skip already-initialized
        if (wrapper.querySelector('.custom-select-trigger')) return;
        new CustomSelect(wrapper);
    });
}


// ═══════════════════════════════════════════════════════════════════════════════
// Modal Helpers (replaces Bootstrap Modal)
// ═══════════════════════════════════════════════════════════════════════════════

function openModal(id) {
    const overlay = document.getElementById(id);
    if (overlay) {
        overlay.classList.add('open');
        overlay.addEventListener('click', function handler(e) {
            if (e.target === overlay) {
                closeModal(id);
                overlay.removeEventListener('click', handler);
            }
        });
        // Init any custom selects inside modal
        initCustomSelects(overlay);
    }
}

function closeModal(id) {
    const overlay = document.getElementById(id);
    if (overlay) overlay.classList.remove('open');
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.open').forEach(m => m.classList.remove('open'));
        document.querySelectorAll('.custom-select.open').forEach(s => s.classList.remove('open'));
    }
});

// ═══════════════════════════════════════════════════════════════════════════════
// Page Navigation
// ═══════════════════════════════════════════════════════════════════════════════

function showSection(sectionName) {
    // Hide all sections
    document.querySelectorAll('.content-section').forEach(section => {
        section.classList.remove('active');
    });

    // Show selected section
    const target = document.getElementById(`${sectionName}-section`);
    if (target) target.classList.add('active');

    // Update nav links
    document.querySelectorAll('.sidebar-nav .nav-item').forEach(link => {
        link.classList.remove('active');
        if (link.dataset.section === sectionName) {
            link.classList.add('active');
        }
    });

    // Load section data
    switch(sectionName) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'upload':
            loadUploadedFiles();
            break;
        case 'curriculum':
            loadCurriculumMappings();
            setupCurriculumFileInput();
            break;
        case 'subjects':
            loadSubjects();
            break;
        case 'graph':
            loadGraphData();
            break;
        case 'jobs':
            loadJobs();
            break;
    }

    // Stop dashboard-only pollers when leaving the dashboard
    if (sectionName !== 'dashboard' && activeUsersIntervalId) {
        clearInterval(activeUsersIntervalId);
        activeUsersIntervalId = null;
    }

    // Re-render Lucide icons for dynamically injected content
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

// ═══════════════════════════════════════════════════════════════════════════════
// Dashboard
// ═══════════════════════════════════════════════════════════════════════════════

async function loadDashboard() {
    await loadSystemStatus();
    await refreshStats();
    await loadActiveUsers();

    // Load graph data for mini preview
    if (typeof loadGraphData === 'function' && GRAPH.nodes.length === 0) {
        loadGraphData();
    } else if (typeof renderMiniGraph === 'function') {
        renderMiniGraph();
    }

    if (activeUsersIntervalId) {
        clearInterval(activeUsersIntervalId);
    }
    activeUsersIntervalId = setInterval(loadActiveUsers, 10000);
}

async function loadActiveUsers() {
    const listEl = document.getElementById('active-users-list');
    const metaEl = document.getElementById('active-users-meta');
    if (!listEl || !metaEl) return;

    try {
        const response = await fetch(`${API_BASE_V1}/active-users?window_minutes=10`);
        const data = await response.json();

        const users = data.users || [];
        metaEl.textContent = `${users.length} active (last ${data.window_minutes || 10} min)`;

        if (users.length === 0) {
            listEl.innerHTML = '<div class="list-item"><span class="text-muted text-sm">No active users</span></div>';
            return;
        }

        const now = new Date();
        listEl.innerHTML = users.map(u => {
            const label = u.email || u.user_id;
            const lastSeen = u.last_seen ? new Date(u.last_seen) : null;
            const secondsAgo = lastSeen ? Math.max(0, Math.floor((now - lastSeen) / 1000)) : null;

            let agoText = 'just now';
            if (secondsAgo !== null) {
                if (secondsAgo < 60) agoText = `${secondsAgo}s ago`;
                else if (secondsAgo < 3600) agoText = `${Math.floor(secondsAgo / 60)}m ago`;
                else agoText = `${Math.floor(secondsAgo / 3600)}h ago`;
            }

            return `
                <div class="list-item">
                    <div>
                        <div class="list-item-label">${escapeHtml(label)}</div>
                        <div class="list-item-sub">${escapeHtml(u.role || 'authenticated')}</div>
                    </div>
                    <span class="list-item-right">${agoText}</span>
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('Error loading active users:', error);
        metaEl.textContent = 'Failed to load';
        listEl.innerHTML = '<div class="list-item"><span class="text-muted text-sm">Failed to load</span></div>';
    }
}

function escapeHtml(value) {
    return String(value || '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

async function loadSystemStatus() {
    try {
        const response = await fetch(`${API_BASE_V2}/status`);
        const data = await response.json();

        const components = data.components;

        document.getElementById('neo4j-status').className =
            `status-dot ${components.neo4j ? 'online' : 'offline'}`;
        document.getElementById('embedding-status').className =
            `status-dot ${components.embedding_model ? 'online' : 'offline'}`;
        document.getElementById('llm-status').className =
            `status-dot ${components.llm_extractor ? 'online' : 'offline'}`;

    } catch (error) {
        console.error('Error loading status:', error);
    }
}

async function refreshStats() {
    try {
        const response = await fetch(`${API_BASE_V2}/stats`);
        const data = await response.json();

        document.getElementById('stat-subjects').textContent =
            data.knowledge_graph?.total_subjects || 0;
        document.getElementById('stat-modules').textContent =
            data.knowledge_graph?.total_modules || 0;
        document.getElementById('stat-topics').textContent =
            (data.knowledge_graph && (data.knowledge_graph.total_concepts || data.knowledge_graph.total_topics)) || 0;
        document.getElementById('stat-embeddings').textContent =
            (data.embeddings && (data.embeddings.total_chunks || data.embeddings.total_embeddings)) || 0;

        const branches = data.knowledge_graph?.branches || [];
        document.getElementById('branches-list').innerHTML = branches.length > 0
            ? branches.map(b => `<span class="badge badge-info" style="margin-right:4px">${b}</span>`).join('')
            : '<span class="text-muted text-sm">No data yet</span>';

        const semesters = data.knowledge_graph?.semesters || [];
        document.getElementById('semesters-list').innerHTML = semesters.length > 0
            ? semesters.map(s => `<span class="badge badge-success" style="margin-right:4px">S${s}</span>`).join('')
            : '<span class="text-muted text-sm">No data yet</span>';

        const regulations = data.knowledge_graph?.regulations || [];
        document.getElementById('regulations-list').innerHTML = regulations.length > 0
            ? regulations.map(r => `<span class="badge badge-default" style="margin-right:4px">${r}</span>`).join('')
            : '<span class="text-muted text-sm">No data yet</span>';

        showToast('Statistics refreshed', 'success');

    } catch (error) {
        console.error('Error loading stats:', error);
        showToast('Error loading statistics', 'danger');
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// File Upload
// ═══════════════════════════════════════════════════════════════════════════════

// ═══════════════════════════════════════════════════════════════════════════════
// Batch File Upload
// ═══════════════════════════════════════════════════════════════════════════════

let batchFiles = [];

function initUploadZone() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    if (!dropZone || !fileInput) return;

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        handleFilesSelected(e.dataTransfer.files);
    });

    fileInput.addEventListener('change', (e) => {
        handleFilesSelected(e.target.files);
    });
}

function handleFilesSelected(fileList) {
    const files = Array.from(fileList).filter(f => f.type === 'application/pdf');
    
    if (files.length === 0) {
        showToast('Please select valid PDF files', 'warning');
        return;
    }

    files.forEach(file => {
        // Add to batch with default metadata
        const fileObj = {
            file: file,
            id: Math.random().toString(36).substr(2, 9),
            branch: '',
            semester: '',
            regulation: '2019',
            analyzing: false
        };
        batchFiles.push(fileObj);
        
        // Start auto-analysis for each file
        analyzeBatchFile(fileObj);
    });

    renderBatchTable();
}

async function analyzeBatchFile(fileObj) {
    fileObj.analyzing = true;
    updateBatchRow(fileObj);

    const formData = new FormData();
    formData.append('file', fileObj.file);

    try {
        const response = await fetch(`${API_BASE_V2}/analyze-pdf`, {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const data = await response.json();
            if (data.branch) fileObj.branch = data.branch.toUpperCase();
            if (data.regulation) fileObj.regulation = data.regulation;
            fileObj.analyzing = false;
            updateBatchRow(fileObj);
        }
    } catch (error) {
        console.error('Error analyzing metadata:', error);
        fileObj.analyzing = false;
        updateBatchRow(fileObj);
    }
}

function renderBatchTable() {
    const container = document.getElementById('batch-config-container');
    const list = document.getElementById('batch-files-list');
    const countText = document.getElementById('selected-files-count');
    
    if (batchFiles.length === 0) {
        container.style.display = 'none';
        countText.textContent = 'No files selected';
        return;
    }

    container.style.display = 'block';
    countText.textContent = `${batchFiles.length} file(s) ready for configuration`;
    list.innerHTML = '';

    batchFiles.forEach((f, index) => {
        const row = document.createElement('tr');
        row.id = `batch-row-${f.id}`;
        row.innerHTML = getBatchRowHtml(f, index);
        list.appendChild(row);
    });

    initCustomSelects(list);
    updateBatchSummary();
}

function getBatchRowHtml(f, index) {
    return `
        <td>
            <div class="flex items-center gap-sm">
                ${f.analyzing ? '<span class="spinner"></span>' : '<i data-lucide="file-text" class="text-muted" style="width:16px"></i>'}
                <span class="font-medium text-sm truncate" style="max-width:250px" title="${f.file.name}">${f.file.name}</span>
            </div>
        </td>
        <td>
            <div class="custom-select" data-id="branch-${f.id}">
                <select onchange="updateBatchData('${f.id}', 'branch', this)">
                    <option value="">Select Branch</option>
                    <option value="CSE" ${f.branch === 'CSE' ? 'selected' : ''}>CSE</option>
                    <option value="ECE" ${f.branch === 'ECE' ? 'selected' : ''}>ECE</option>
                    <option value="EEE" ${f.branch === 'EEE' ? 'selected' : ''}>EEE</option>
                    <option value="ME" ${f.branch === 'ME' ? 'selected' : ''}>ME</option>
                    <option value="CE" ${f.branch === 'CE' ? 'selected' : ''}>CE</option>
                    <option value="IT" ${f.branch === 'IT' ? 'selected' : ''}>IT</option>
                    <option value="AI" ${f.branch === 'AI' ? 'selected' : ''}>AI</option>
                    <option value="DS" ${f.branch === 'DS' ? 'selected' : ''}>DS</option>
                </select>
            </div>
        </td>
        <td>
            <div class="custom-select" data-id="semester-${f.id}">
                <select onchange="updateBatchData('${f.id}', 'semester', this)">
                    <option value="">Select Sem</option>
                    <option value="1" ${f.semester === '1' ? 'selected' : ''}>S1</option>
                    <option value="2" ${f.semester === '2' ? 'selected' : ''}>S2</option>
                    <option value="3" ${f.semester === '3' ? 'selected' : ''}>S3</option>
                    <option value="4" ${f.semester === '4' ? 'selected' : ''}>S4</option>
                    <option value="5" ${f.semester === '5' ? 'selected' : ''}>S5</option>
                    <option value="6" ${f.semester === '6' ? 'selected' : ''}>S6</option>
                    <option value="7" ${f.semester === '7' ? 'selected' : ''}>S7</option>
                    <option value="8" ${f.semester === '8' ? 'selected' : ''}>S8</option>
                </select>
            </div>
        </td>
        <td>
            <div class="custom-select" data-id="regulation-${f.id}">
                <select onchange="updateBatchData('${f.id}', 'regulation', this)">
                    <option value="2019" ${f.regulation === '2019' ? 'selected' : ''}>2019</option>
                    <option value="2024" ${f.regulation === '2024' ? 'selected' : ''}>2024</option>
                    <option value="2028" ${f.regulation === '2028' ? 'selected' : ''}>2028</option>
                </select>
            </div>
        </td>
        <td>
            <button class="btn btn-ghost btn-sm text-danger" onclick="removeFromBatch('${f.id}')"><i data-lucide="x"></i></button>
        </td>
    `;
}

function updateBatchRow(fileObj) {
    const row = document.getElementById(`batch-row-${fileObj.id}`);
    if (!row) return;
    
    // We need to preserve the selections if they were manually changed
    // But for auto-detection, we update the whole row
    const index = batchFiles.findIndex(f => f.id === fileObj.id);
    row.innerHTML = getBatchRowHtml(fileObj, index);
    
    // Re-init lucide icons and custom selects for this row
    lucide.createIcons({ scope: row });
    initCustomSelects(row);
}

function updateBatchData(id, field, element) {
    const fileObj = batchFiles.find(f => f.id === id);
    if (!fileObj) return;
    
    // The element might be the wrapper or the native select
    const select = element.querySelector('select') || element;
    fileObj[field] = select.value;
    updateBatchSummary();
}

function applyToAll(field) {
    if (batchFiles.length < 2) return;
    
    const firstVal = batchFiles[0][field];
    if (!firstVal && field !== 'regulation') {
        showToast(`Please select a ${field} for the first file first`, 'warning');
        return;
    }

    batchFiles.forEach((f, i) => {
        if (i === 0) return;
        f[field] = firstVal;
        
        // Update the UI for this field
        const wrapper = document.querySelector(`[data-id="${field}-${f.id}"]`);
        if (wrapper && wrapper._customSelect) {
            wrapper._customSelect.setValue(firstVal);
        }
    });
    
    showToast(`Applied ${firstVal} to all ${batchFiles.length} files`, 'success');
    updateBatchSummary();
}

function removeFromBatch(id) {
    batchFiles = batchFiles.filter(f => f.id !== id);
    renderBatchTable();
}

function clearBatch() {
    batchFiles = [];
    renderBatchTable();
}

function updateBatchSummary() {
    const info = document.getElementById('batch-total-info');
    if (!info) return;
    
    const total = batchFiles.length;
    const ready = batchFiles.filter(f => f.branch && f.semester).length;
    
    info.textContent = `${ready}/${total} files configured`;
}

async function processBatch() {
    const unconfigured = batchFiles.filter(f => !f.branch || !f.semester);
    if (unconfigured.length > 0) {
        showToast(`Please configure Branch and Semester for all ${unconfigured.length} files`, 'warning');
        return;
    }

    const btn = document.getElementById('process-batch-btn');
    const spinner = btn.querySelector('.spinner');
    const text = btn.querySelector('.btn-text');
    
    btn.disabled = true;
    spinner.style.display = 'inline-block';
    text.textContent = 'Processing Batch...';

    let successCount = 0;
    let failCount = 0;

    for (const f of batchFiles) {
        const formData = new FormData();
        formData.append('file', f.file);
        formData.append('branch', f.branch);
        formData.append('semester', f.semester);
        formData.append('regulation', f.regulation);

        try {
            const response = await fetch(`${API_BASE_V2}/upload`, {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                successCount++;
            } else {
                failCount++;
            }
        } catch (error) {
            failCount++;
        }
    }

    btn.disabled = false;
    spinner.style.display = 'none';
    text.innerHTML = '<i data-lucide="play"></i> Start Batch Processing';
    lucide.createIcons({ scope: btn });

    if (successCount > 0) {
        showToast(`Successfully queued ${successCount} files for processing`, 'success');
        clearBatch();
        loadUploadedFiles();
        loadJobs();
    }
    
    if (failCount > 0) {
        showToast(`Failed to upload ${failCount} files`, 'danger');
    }
}


async function pollJobProgress(jobId) {
    const progressBar = document.getElementById('progress-bar');
    const progressStatus = document.getElementById('progress-status');
    const progressPercent = document.getElementById('progress-percent');
    const progressDetail = document.getElementById('progress-detail');

    // ── Smooth animated progress ──────────────────────────────────────
    // The bar animates smoothly on the frontend. When the API reports
    // completion, the bar accelerates to 100% over ~1.5s before showing
    // the success toast.

    let displayPercent = 0;
    let realProgress = 0;
    let completing = false;   // API said done; animation is filling to 100%
    let isFailed = false;
    let lastMessage = 'Initializing...';
    let animFrameId = null;
    let lastTimestamp = null;

    const stages = [
        { at: 0,  msg: 'Uploading file...' },
        { at: 10, msg: 'Extracting text from PDF...' },
        { at: 25, msg: 'Analyzing with AI...' },
        { at: 45, msg: 'Building knowledge graph...' },
        { at: 60, msg: 'Storing to database...' },
        { at: 75, msg: 'Generating embeddings...' },
        { at: 88, msg: 'Finalizing...' },
    ];

    function getStageMessage(pct) {
        let msg = stages[0].msg;
        for (const s of stages) {
            if (pct >= s.at) msg = s.msg;
        }
        return msg;
    }

    function animate(timestamp) {
        if (isFailed) return;

        if (!lastTimestamp) lastTimestamp = timestamp;
        const dt = (timestamp - lastTimestamp) / 1000;
        lastTimestamp = timestamp;

        if (completing) {
            // Fast fill to 100% — takes ~1.5s total regardless of where we are
            const remaining = 100 - displayPercent;
            const speed = Math.max(remaining * 1.2, 8); // exponential ease-out
            displayPercent = Math.min(100, displayPercent + speed * dt);
        } else {
            // Normal animation: advances quickly at first, slows toward 92%
            const ceiling = 92;
            if (displayPercent < ceiling) {
                let speed;
                if (realProgress > displayPercent) {
                    speed = 20; // catch up to real value fast
                } else if (displayPercent < 30) {
                    speed = 6;
                } else if (displayPercent < 55) {
                    speed = 3.5;
                } else if (displayPercent < 75) {
                    speed = 2;
                } else if (displayPercent < 85) {
                    speed = 0.8;
                } else {
                    speed = 0.3;
                }
                displayPercent = Math.min(ceiling, displayPercent + speed * dt);
            }
        }

        // Update DOM
        const rounded = Math.round(displayPercent);
        progressBar.style.width = `${rounded}%`;
        progressPercent.textContent = `${rounded}%`;
        progressStatus.textContent = completing
            ? 'Almost done...'
            : (lastMessage !== 'Initializing...' ? lastMessage : getStageMessage(rounded));

        // When completing animation reaches 100%, fire the success
        if (completing && displayPercent >= 99.5) {
            progressBar.style.width = '100%';
            progressPercent.textContent = '100%';
            progressStatus.textContent = 'Completed!';
            if (progressDetail) progressDetail.textContent = '';
            showToast('Processing completed successfully!', 'success');
            setTimeout(() => {
                document.getElementById('upload-progress').style.display = 'none';
                progressBar.style.width = '0%';
            }, 2000);
            loadUploadedFiles();
            refreshStats();
            return; // stop animation
        }

        animFrameId = requestAnimationFrame(animate);
    }

    // Remove any leftover classes, start clean
    progressBar.className = 'progress-bar-fill';
    progressBar.style.width = '0%';
    animFrameId = requestAnimationFrame(animate);

    // Poll the API separately
    let consecutiveErrors = 0;
    const MAX_ERRORS = 5;

    const poll = async () => {
        if (completing || isFailed) return;

        try {
            const response = await fetch(`${API_BASE_V2}/jobs/${jobId}`);

            // Stop immediately on 404 — job was lost or never created
            if (response.status === 404) {
                isFailed = true;
                cancelAnimationFrame(animFrameId);
                showToast('Job not found. The server may have restarted. Please try uploading again.', 'danger');
                document.getElementById('upload-progress').style.display = 'none';
                return;
            }

            // Stop on repeated server errors
            if (!response.ok) {
                consecutiveErrors++;
                if (consecutiveErrors >= MAX_ERRORS) {
                    isFailed = true;
                    cancelAnimationFrame(animFrameId);
                    showToast(`Server error (${response.status}). Processing may have failed.`, 'danger');
                    document.getElementById('upload-progress').style.display = 'none';
                    return;
                }
                setTimeout(poll, 2000);
                return;
            }

            consecutiveErrors = 0; // reset on success
            const data = await response.json();

            realProgress = data.progress || 0;
            if (data.message) lastMessage = data.message;

            if (data.status === 'completed') {
                // Don't snap — let the animation fill to 100% smoothly
                completing = true;
                return;
            }

            if (data.status === 'failed') {
                isFailed = true;
                cancelAnimationFrame(animFrameId);
                showToast('Processing failed: ' + data.message, 'danger');
                document.getElementById('upload-progress').style.display = 'none';
                return;
            }

            setTimeout(poll, 500);
        } catch (error) {
            console.error('Polling error:', error);
            consecutiveErrors++;
            if (consecutiveErrors >= MAX_ERRORS) {
                isFailed = true;
                cancelAnimationFrame(animFrameId);
                showToast('Lost connection to server. Please refresh and check job status.', 'danger');
                document.getElementById('upload-progress').style.display = 'none';
                return;
            }
            setTimeout(poll, 1500);
        }
    };

    poll();
}


async function loadUploadedFiles() {
    try {
        const response = await fetch(`${API_BASE_V1}/files`);
        const data = await response.json();

        const tbody = document.getElementById('files-table');

        if (data.files.length === 0) {
            tbody.innerHTML = '<tr><td class="td-empty" colspan="6">No files uploaded yet</td></tr>';
            return;
        }

        tbody.innerHTML = data.files.map(file => `
            <tr>
                <td>${file.filename}</td>
                <td><span class="badge badge-info">${file.branch}</span></td>
                <td>S${file.semester}</td>
                <td>${formatFileSize(file.size_bytes)}</td>
                <td>${formatDate(file.uploaded_at)}</td>
                <td>
                    <button class="btn btn-ghost btn-sm" onclick="deleteFile('${file.filename}')" style="color:hsl(0 62.8% 60%)">
                        <i data-lucide="trash-2" style="width:14px;height:14px"></i>
                    </button>
                </td>
            </tr>
        `).join('');

        if (typeof lucide !== 'undefined') lucide.createIcons();

    } catch (error) {
        console.error('Error loading files:', error);
    }
}

async function deleteFile(filename) {
    if (!confirm(`Delete file "${filename}"?`)) return;

    try {
        const response = await fetch(`${API_BASE_V1}/files/${filename}`, { method: 'DELETE' });
        if (response.ok) {
            showToast('File deleted', 'success');
            loadUploadedFiles();
        } else {
            showToast('Failed to delete file', 'danger');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'danger');
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Subjects
// ═══════════════════════════════════════════════════════════════════════════════

let allSubjects = [];
let subjectsViewMode = 'grid'; // 'grid' or 'list'

async function loadSubjects() {
    try {
        const branch = document.getElementById('filter-branch').value;
        const semester = document.getElementById('filter-semester').value;
        const regulation = document.getElementById('filter-regulation').value;

        let url = `${API_BASE_V2}/subjects?`;
        if (branch) url += `branch=${branch}&`;
        if (semester) url += `semester=${semester}&`;
        if (regulation) url += `regulation=${regulation}`;

        const response = await fetch(url);
        const data = await response.json();

        allSubjects = data.subjects || [];
        renderSubjects(allSubjects);

    } catch (error) {
        console.error('Error loading subjects:', error);
        document.getElementById('subjects-grid').innerHTML =
            '<div class="text-center text-danger" style="grid-column:1/-1;padding:2rem">Error loading subjects</div>';
    }
}

function renderSubjects(subjects) {
    const grid = document.getElementById('subjects-grid');
    const listCard = document.getElementById('subjects-list-card');
    const listBody = document.getElementById('subjects-list');

    if (subjects.length === 0) {
        const emptyMsg = '<div class="text-center text-muted" style="grid-column:1/-1;padding:2rem">No subjects found. Upload a syllabus or add subjects manually.</div>';
        if (subjectsViewMode === 'grid') {
            grid.innerHTML = emptyMsg;
            grid.style.display = 'grid';
            listCard.style.display = 'none';
        } else {
            listBody.innerHTML = '<tr><td colspan="5" class="td-empty">No subjects found</td></tr>';
            grid.style.display = 'none';
            listCard.style.display = 'block';
        }
        return;
    }

    if (subjectsViewMode === 'grid') {
        grid.style.display = 'grid';
        listCard.style.display = 'none';
        grid.innerHTML = subjects.map(subject => `
            <div class="card subject-card" onclick="showSubjectDetails('${subject.code}', '${subject.regulation || '2019'}')">
                <div class="card-body">
                    <div class="flex items-start justify-between" style="margin-bottom:0.5rem">
                        <span class="badge badge-info">${subject.code}</span>
                        <div class="flex gap-xs">
                            <span class="badge badge-muted">${subject.regulation || '2019'}</span>
                            <span class="badge badge-default">${subject.module_count || 0} modules</span>
                        </div>
                    </div>
                    <h5 style="font-size:0.9375rem;margin-bottom:0.25rem">${subject.name}</h5>
                    <div class="subject-meta">
                        <span><i data-lucide="graduation-cap" style="width:14px;height:14px"></i> S${subject.semester}</span>
                        <span><i data-lucide="building-2" style="width:14px;height:14px"></i> ${subject.branch}</span>
                        <span><i data-lucide="star" style="width:14px;height:14px"></i> ${subject.credits} credits</span>
                    </div>
                </div>
            </div>
        `).join('');
    } else {
        grid.style.display = 'none';
        listCard.style.display = 'block';
        listBody.innerHTML = subjects.map(subject => `
            <tr>
                <td class="font-medium"><code>${subject.code}</code></td>
                <td>
                    <div class="font-medium">${subject.name}</div>
                    <div class="text-xs text-muted-foreground">${subject.category || 'PCC'}</div>
                </td>
                <td>
                    <div class="flex gap-xs">
                        <span class="badge badge-outline">${subject.regulation || '2019'}</span>
                        <span class="badge badge-muted">${subject.module_count || 0} modules</span>
                    </div>
                </td>
                <td>
                    <div class="text-sm">S${subject.semester} • ${subject.branch}</div>
                    <div class="text-xs text-muted-foreground">${subject.credits} Credits</div>
                </td>
                <td>
                    <div class="flex gap-sm">
                        <button class="btn btn-ghost btn-sm" onclick="showSubjectDetails('${subject.code}', '${subject.regulation || '2019'}')" title="View Details">
                            <i data-lucide="eye"></i>
                        </button>
                        <button class="btn btn-ghost btn-sm text-danger" onclick="deleteSubject('${subject.code}', '${subject.regulation || '2019'}')" title="Delete">
                            <i data-lucide="trash-2"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');
    }

    if (typeof lucide !== 'undefined') lucide.createIcons();
}

function toggleSubjectsView(mode) {
    subjectsViewMode = mode;
    
    // Update button states
    document.getElementById('view-grid-btn').classList.toggle('active', mode === 'grid');
    document.getElementById('view-list-btn').classList.toggle('active', mode === 'list');
    
    // Re-filter and render
    filterSubjects();
}

async function bulkDeleteSubjects() {
    const branch = document.getElementById('filter-branch').value;
    const semester = document.getElementById('filter-semester').value;
    const regulation = document.getElementById('filter-regulation').value || '2019';

    if (!semester && !branch) {
        showToast('Please select at least a Semester or Branch to bulk delete.', 'warning');
        return;
    }

    const filterText = (semester ? `S${semester} ` : '') + (branch ? `${branch} ` : '') + `(${regulation} scheme)`;
    
    if (!confirm(`⚠️ WARNING: This will delete ALL ${filterText} subjects and their data from the Knowledge Graph and database.\n\nAre you sure you want to proceed?`)) {
        return;
    }

    const confirmCode = prompt(`Type "DELETE ALL" to confirm deleting ${filterText} subjects:`);
    if (confirmCode !== 'DELETE ALL') {
        showToast('Bulk delete cancelled', 'info');
        return;
    }

    try {
        let url = `${API_BASE_V2}/subjects/bulk?regulation=${regulation}`;
        if (semester) url += `&semester=${semester}`;
        if (branch) url += `&branch=${branch}`;

        showToast('Processing bulk deletion...', 'info');
        
        const response = await fetch(url, { method: 'DELETE' });
        const data = await response.json();

        if (response.ok) {
            showToast(data.message, 'success');
            loadSubjects();
            refreshStats();
        } else {
            showToast(data.detail || 'Bulk delete failed', 'danger');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'danger');
    }
}

function filterSubjects() {
    const search = document.getElementById('search-subject').value.toLowerCase();
    const filtered = allSubjects.filter(s =>
        s.name.toLowerCase().includes(search) ||
        s.code.toLowerCase().includes(search)
    );
    renderSubjects(filtered);
}

async function showSubjectDetails(code, regulation = '2019') {
    openModal('subjectDetailsModal');
    document.getElementById('subject-detail-title').textContent = `Subject: ${code} (${regulation} Scheme)`;
    document.getElementById('subject-detail-content').innerHTML = '<div class="text-center" style="padding:2rem"><div class="spinner spinner-lg"></div></div>';

    try {
        const response = await fetch(`${API_BASE_V2}/subjects/${code}?regulation=${regulation}`);
        const subject = await response.json();

        let modulesHtml = '';
        if (subject.modules && subject.modules.length > 0) {
            modulesHtml = subject.modules.map(m => `
                <div class="card" style="margin-bottom:0.75rem">
                    <div class="card-header">
                        <h6>Module ${m.number}: ${m.name}</h6>
                        <span class="text-xs text-muted">${m.hours || 0} hours</span>
                    </div>
                    <div class="card-body compact">
                        ${(() => { const items = m.topics || m.concepts || []; return items.length > 0
                            ? `<ul style="margin:0;padding-left:1.25rem;list-style:disc">${items.map(t => `
                                <li style="margin-bottom:0.375rem">
                                    <strong>${t.name}</strong>
                                    ${t.description ? `<br><span class="text-sm text-muted">${t.description}</span>` : ''}
                                    ${t.keywords && t.keywords.length > 0
                                        ? `<br><span>${t.keywords.map(k => `<span class="badge badge-muted" style="margin-right:3px;margin-top:2px">${k}</span>`).join('')}</span>`
                                        : ''}
                                </li>
                            `).join('')}</ul>`
                            : '<p class="text-sm text-muted">No topics added</p>'; })()}
                    </div>
                </div>
            `).join('');
        } else {
            modulesHtml = '<p class="text-muted">No modules found</p>';
        }

        document.getElementById('subject-detail-content').innerHTML = `
            <div class="grid-2 gap-md" style="grid-template-columns: 280px 1fr">
                <div class="card">
                    <div class="card-body">
                        <h6 class="text-muted" style="margin-bottom:0.75rem">Subject Info</h6>
                        <div style="font-size:0.875rem">
                            <p style="margin-bottom:0.375rem"><strong>Code:</strong> ${subject.code}</p>
                            <p style="margin-bottom:0.375rem"><strong>Name:</strong> ${subject.name}</p>
                            <p style="margin-bottom:0.375rem"><strong>Credits:</strong> ${subject.credits}</p>
                            <p style="margin-bottom:0.375rem"><strong>Semester:</strong> S${subject.semester}</p>
                            <p style="margin-bottom:0.375rem"><strong>Branch:</strong> ${subject.branch}</p>
                            <p style="margin-bottom:0.375rem"><strong>Regulation:</strong> ${subject.regulation || '2019'}</p>
                            <p><strong>Category:</strong> ${subject.category || 'N/A'}</p>
                        </div>
                        <div class="separator"></div>
                        <button class="btn btn-destructive btn-sm w-full" onclick="deleteSubject('${subject.code}', '${subject.regulation || '2019'}')">
                            <i data-lucide="trash-2" style="width:14px;height:14px"></i> Delete Subject
                        </button>
                    </div>
                </div>
                <div>
                    <h6 class="text-muted" style="margin-bottom:0.75rem">Modules & Topics</h6>
                    ${modulesHtml}
                </div>
            </div>
        `;

        if (typeof lucide !== 'undefined') lucide.createIcons();

    } catch (error) {
        document.getElementById('subject-detail-content').innerHTML =
            `<div class="alert alert-danger">Error loading subject: ${error.message}</div>`;
    }
}

async function addSubject() {
    const subject = {
        code: document.getElementById('subject-code').value,
        name: document.getElementById('subject-name').value,
        credits: parseInt(document.getElementById('subject-credits').value),
        semester: parseInt(document.getElementById('subject-semester').value),
        branch: document.getElementById('subject-branch').value,
        regulation: document.getElementById('subject-regulation').value,
        category: document.getElementById('subject-category').value,
        modules: [],
        textbooks: [],
        objectives: []
    };

    try {
        const response = await fetch(`${API_BASE_V1}/subjects`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(subject)
        });

        if (response.ok) {
            showToast('Subject added successfully!', 'success');
            closeModal('addSubjectModal');
            document.getElementById('add-subject-form').reset();
            loadSubjects();
            refreshStats();
        } else {
            const error = await response.json();
            showToast(error.detail || 'Failed to add subject', 'danger');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'danger');
    }
}

async function deleteSubject(code, regulation = '2019') {
    if (!confirm(`Delete subject "${code}" (${regulation} scheme) and all its modules/topics?`)) return;

    try {
        const response = await fetch(`${API_BASE_V2}/subjects/${code}?regulation=${regulation}`, { method: 'DELETE' });
        if (response.ok) {
            showToast('Subject deleted', 'success');
            closeModal('subjectDetailsModal');
            loadSubjects();
            refreshStats();
        } else {
            showToast('Failed to delete subject', 'danger');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'danger');
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Search
// ═══════════════════════════════════════════════════════════════════════════════

function initSearchForm() {
    const form = document.getElementById('search-form');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const query = document.getElementById('search-query').value;
        const limit = document.getElementById('search-limit').value;
        const branch = document.getElementById('search-branch').value;
        const semester = document.getElementById('search-semester').value;
        const subjectCode = document.getElementById('search-subject-code').value;

        document.getElementById('search-results').innerHTML =
            '<div class="text-center" style="padding:2rem"><div class="spinner spinner-lg"></div><p class="text-muted" style="margin-top:0.75rem">Searching...</p></div>';

        try {
            const response = await fetch(`${API_BASE_V2}/search`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: query,
                    limit: parseInt(limit),
                    branch: branch || null,
                    semester: semester ? parseInt(semester) : null,
                    subject_code: subjectCode || null
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: response.statusText }));
                throw new Error(errorData.detail || 'Search request failed');
            }

            const data = await response.json();

            if (data.total_results === 0) {
                document.getElementById('search-results').innerHTML =
                    '<div class="text-center text-muted" style="padding:2rem"><p>No results found in the syllabus knowledge base.</p></div>';
                return;
            }

            let html = `
                <div class="flex items-center justify-between mb-sm">
                    <span class="text-sm text-muted">Found ${data.total_results} matches in ${data.search_time_ms.toFixed(0)}ms (Route: ${data.routing.type})</span>
                </div>
            `;

            // KG Results
            if (data.kg_results && data.kg_results.length > 0) {
                html += `
                    <div class="mb-sm">
                        <h6 class="text-xs uppercase tracking-wider text-muted-foreground mb-sm">Knowledge Graph Concepts</h6>
                        <div class="grid-2 gap-sm">
                            ${data.kg_results.map(c => `
                                <div class="card" style="border-left: 3px solid #f59e0b">
                                    <div class="card-body compact">
                                        <div class="flex items-center justify-between">
                                            <span class="font-medium text-sm">${escapeHtml(c.name || c.id)}</span>
                                            <span class="badge badge-info">${c.subject_code || 'Syllabus'}</span>
                                        </div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                `;
            }

            // Vector Results
            if (data.vector_results && data.vector_results.length > 0) {
                html += `
                    <h6 class="text-xs uppercase tracking-wider text-muted-foreground mb-sm">Semantic Content Chunks</h6>
                    ${data.vector_results.map(r => `
                        <div class="card" style="margin-bottom:0.75rem; border-left: 3px solid #6366f1">
                            <div class="card-body compact">
                                <div class="flex items-start justify-between" style="margin-bottom:0.5rem">
                                    <div>
                                        <span class="badge badge-outline" style="margin-right:0.5rem">${r.subject_code}</span>
                                        <span class="text-sm font-medium">${r.subject_name || ''}</span>
                                    </div>
                                    <span class="badge ${r.similarity > 0.8 ? 'badge-success' : 'badge-default'}">
                                        ${(r.similarity * 100).toFixed(1)}% match
                                    </span>
                                </div>
                                <p style="font-size:0.875rem; color: var(--foreground); line-height: 1.5; margin-bottom: 0.5rem">
                                    ${escapeHtml(r.content)}
                                </p>
                                <div class="flex items-center gap-sm">
                                    <span class="text-xs text-muted-foreground">Type: ${r.chunk_type || 'content'}</span>
                                    <span class="text-xs text-muted-foreground">|</span>
                                    <span class="text-xs text-muted-foreground">Branch: ${r.branch}</span>
                                    <span class="text-xs text-muted-foreground">|</span>
                                    <span class="text-xs text-muted-foreground">Sem: S${r.semester}</span>
                                </div>
                            </div>
                        </div>
                    `).join('')}
                `;
            }

            document.getElementById('search-results').innerHTML = html;

        } catch (error) {
            console.error('Search error:', error);
            document.getElementById('search-results').innerHTML =
                `<div class="card" style="border: 1px solid var(--destructive)"><div class="card-body text-destructive">Search failed: ${error.message}</div></div>`;
        }
    });
}

// ═══════════════════════════════════════════════════════════════════════════════
// Jobs
// ═══════════════════════════════════════════════════════════════════════════════

async function loadJobs() {
    try {
        const response = await fetch(`${API_BASE_V2}/jobs`);
        const data = await response.json();

        const tbody = document.getElementById('jobs-table');

        if (data.jobs.length === 0) {
            tbody.innerHTML = '<tr><td class="td-empty" colspan="7">No processing jobs yet</td></tr>';
            return;
        }

        tbody.innerHTML = data.jobs.map(job => `
            <tr>
                <td><code>${job.job_id.slice(0, 8)}...</code></td>
                <td>${job.filename}</td>
                <td>${job.branch}</td>
                <td>S${job.semester}</td>
                <td>
                    <span class="badge ${getStatusBadgeClass(job.status)}">${job.status}</span>
                </td>
                <td>
                    <div class="flex items-center gap-sm">
                        <div class="progress-bar-wrap" style="width:80px">
                            <div class="progress-bar-fill${job.status === 'processing' && job.progress === 0 ? ' indeterminate' : ''}" style="width:${job.progress}%"></div>
                        </div>
                        <span class="text-xs text-muted">${job.progress}%</span>
                    </div>
                </td>
                <td class="text-sm">${job.started_at ? formatDate(job.started_at) : '-'}</td>
            </tr>
        `).join('');

    } catch (error) {
        console.error('Error loading jobs:', error);
    }
}

async function stopAllJobs() {
    if (!confirm('Stop all active processing jobs? This will clear the background queue.')) return;

    try {
        const response = await fetch(`${API_BASE_V2}/jobs/stop-all`, { method: 'POST' });
        const data = await response.json();

        if (response.ok) {
            showToast(data.message, 'success');
            loadJobs();
            loadUploadedFiles();
        } else {
            showToast(data.detail || 'Failed to stop jobs', 'danger');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'danger');
    }
}

function getStatusBadgeClass(status) {
    switch(status) {
        case 'completed': return 'badge-success';
        case 'processing': return 'badge-info';
        case 'failed': return 'badge-danger';
        default: return 'badge-muted';
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Settings / Actions
// ═══════════════════════════════════════════════════════════════════════════════

async function setupNeo4j() {
    try {
        const response = await fetch(`${API_BASE_V2}/neo4j/setup`, { method: 'POST' });
        const data = await response.json();

        if (response.ok) {
            showToast('Neo4j setup completed!', 'success');
        } else {
            showToast(data.detail || 'Setup failed', 'danger');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'danger');
    }
}

async function confirmClearData() {
    if (!confirm('⚠️ WARNING: This will delete ALL data from the knowledge graph and embeddings. This action cannot be undone!\n\nAre you sure?')) {
        return;
    }

    if (!confirm('Are you REALLY sure? Type "DELETE" in the next prompt to confirm.')) {
        return;
    }

    const confirmation = prompt('Type DELETE to confirm:');
    if (confirmation !== 'DELETE') {
        showToast('Deletion cancelled', 'info');
        return;
    }

    try {
        const response = await fetch(`${API_BASE_V2}/data/clear?confirm=true`, { method: 'DELETE' });
        if (response.ok) {
            showToast('All data cleared', 'warning');
            refreshStats();
        } else {
            showToast('Failed to clear data', 'danger');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'danger');
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Utilities
// ═══════════════════════════════════════════════════════════════════════════════

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const id = 'toast-' + Date.now();

    const html = `
        <div id="${id}" class="toast toast-${type}">
            <span>${message}</span>
            <button class="toast-close" onclick="document.getElementById('${id}').remove()">
                <i data-lucide="x" style="width:14px;height:14px"></i>
            </button>
        </div>
    `;

    container.insertAdjacentHTML('beforeend', html);

    if (typeof lucide !== 'undefined') lucide.createIcons();

    setTimeout(() => {
        const toast = document.getElementById(id);
        if (toast) toast.remove();
    }, 4000);
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// ═══════════════════════════════════════════════════════════════════════════════
// Initialize
// ═══════════════════════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    // Initialize custom dropdowns
    initCustomSelects();

    // Bind upload + search forms
    initUploadZone();
    initSearchForm();

    // Load dashboard
    loadDashboard();
});
