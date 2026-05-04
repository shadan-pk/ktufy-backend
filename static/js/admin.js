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

            // Trigger change callback
            if (this.onchangeFn && typeof window[this.onchangeFn] === 'function') {
                window[this.onchangeFn]();
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
            data.knowledge_graph?.total_concepts ?? data.knowledge_graph?.total_topics ?? 0;
        document.getElementById('stat-embeddings').textContent =
            data.embeddings?.total_chunks ?? data.embeddings?.total_embeddings ?? 0;

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

let selectedFile = null;

function initUploadZone() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    if (!dropZone || !fileInput) return;

    dropZone.addEventListener('click', () => fileInput.click());

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
        const files = e.dataTransfer.files;
        if (files.length > 0 && files[0].type === 'application/pdf') {
            selectedFile = files[0];
            document.getElementById('selected-file').textContent = `Selected: ${files[0].name}`;
        } else {
            showToast('Please select a PDF file', 'warning');
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            selectedFile = e.target.files[0];
            document.getElementById('selected-file').textContent = `Selected: ${selectedFile.name}`;
        }
    });
}

function initUploadForm() {
    const form = document.getElementById('upload-form');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        if (!selectedFile) {
            showToast('Please select a PDF file', 'warning');
            return;
        }

        const branch = document.getElementById('upload-branch').value;
        const semester = document.getElementById('upload-semester').value;
        const regulation = document.getElementById('upload-regulation').value;

        if (!branch || !semester) {
            showToast('Please select branch and semester', 'warning');
            return;
        }

        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('branch', branch);
        formData.append('semester', semester);
        formData.append('regulation', regulation);

        const uploadBtn = document.getElementById('upload-btn');
        uploadBtn.querySelector('.spinner').style.display = 'inline-block';
        uploadBtn.querySelector('.btn-text').style.display = 'none';
        uploadBtn.disabled = true;

        try {
            const response = await fetch(`${API_BASE_V2}/upload`, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (response.ok) {
                showToast('File uploaded! Processing started...', 'success');
                document.getElementById('upload-progress').style.display = 'block';

                // Start polling for progress (fast: every 800ms)
                pollJobProgress(data.id);

                selectedFile = null;
                document.getElementById('selected-file').textContent = '';
                document.getElementById('file-input').value = '';
            } else {
                showToast(data.detail || 'Upload failed', 'danger');
            }

        } catch (error) {
            console.error('Upload error:', error);
            showToast('Upload failed: ' + error.message, 'danger');
        } finally {
            uploadBtn.querySelector('.spinner').style.display = 'none';
            uploadBtn.querySelector('.btn-text').style.display = '';
            uploadBtn.disabled = false;
        }
    });
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

    if (subjects.length === 0) {
        grid.innerHTML = '<div class="text-center text-muted" style="grid-column:1/-1;padding:2rem">No subjects found. Upload a syllabus or add subjects manually.</div>';
        return;
    }

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

    if (typeof lucide !== 'undefined') lucide.createIcons();
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

            const data = await response.json();

            if (data.results.length === 0) {
                document.getElementById('search-results').innerHTML =
                    '<div class="text-center text-muted" style="padding:2rem"><p>No results found</p></div>';
                return;
            }

            document.getElementById('search-results').innerHTML = `
                <div class="flex items-center justify-between mb-sm">
                    <span class="text-sm text-muted">${data.total_results} results found in ${data.search_time_ms.toFixed(0)}ms</span>
                </div>
                ${data.results.map((r, i) => `
                    <div class="card" style="margin-bottom:0.75rem">
                        <div class="card-body compact">
                            <div class="flex items-start justify-between" style="margin-bottom:0.5rem">
                                <div>
                                    <span class="badge badge-info" style="margin-right:0.5rem">${r.subject_code}</span>
                                    <span class="text-sm text-muted">${r.subject_name}</span>
                                </div>
                                <span class="badge badge-success">${(r.similarity_score * 100).toFixed(1)}% match</span>
                            </div>
                            <p style="font-size:0.875rem;margin-bottom:0.375rem">${r.content}</p>
                            <span class="text-xs text-muted">
                                ${r.module_name ? `Module: ${r.module_name}` : ''}
                                ${r.topic_name ? `| Topic: ${r.topic_name}` : ''}
                            </span>
                        </div>
                    </div>
                `).join('')}
            `;

        } catch (error) {
            document.getElementById('search-results').innerHTML =
                `<div class="alert alert-danger">Search failed: ${error.message}</div>`;
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
    initUploadForm();
    initSearchForm();

    // Load dashboard
    loadDashboard();
});
