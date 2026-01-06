// KTUfy Admin Dashboard JavaScript

const API_BASE = '/api/v1/admin';

// ═══════════════════════════════════════════════════════════════════════════════
// Page Navigation
// ═══════════════════════════════════════════════════════════════════════════════

function showSection(sectionName) {
    // Hide all sections
    document.querySelectorAll('.content-section').forEach(section => {
        section.style.display = 'none';
    });
    
    // Show selected section
    document.getElementById(`${sectionName}-section`).style.display = 'block';
    
    // Update nav links
    document.querySelectorAll('.sidebar .nav-link').forEach(link => {
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
        case 'jobs':
            loadJobs();
            break;
    }
}

// Initialize navigation
document.querySelectorAll('.sidebar .nav-link').forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        showSection(link.dataset.section);
    });
});

// ═══════════════════════════════════════════════════════════════════════════════
// Dashboard
// ═══════════════════════════════════════════════════════════════════════════════

async function loadDashboard() {
    await loadSystemStatus();
    await refreshStats();
}

async function loadSystemStatus() {
    try {
        const response = await fetch(`${API_BASE}/status`);
        const data = await response.json();
        
        const components = data.components;
        
        // Update status dots
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
        const response = await fetch(`${API_BASE}/stats`);
        const data = await response.json();
        
        // Update stat cards
        document.getElementById('stat-subjects').textContent = 
            data.knowledge_graph?.total_subjects || 0;
        document.getElementById('stat-modules').textContent = 
            data.knowledge_graph?.total_modules || 0;
        document.getElementById('stat-topics').textContent = 
            data.knowledge_graph?.total_topics || 0;
        document.getElementById('stat-embeddings').textContent = 
            data.embeddings?.total_embeddings || 0;
        
        // Update branches list
        const branches = data.knowledge_graph?.branches || [];
        document.getElementById('branches-list').innerHTML = branches.length > 0
            ? branches.map(b => `<span class="badge bg-primary me-1">${b}</span>`).join('')
            : '<span class="text-secondary">No data yet</span>';
        
        // Update semesters list
        const semesters = data.knowledge_graph?.semesters || [];
        document.getElementById('semesters-list').innerHTML = semesters.length > 0
            ? semesters.map(s => `<span class="badge bg-success me-1">S${s}</span>`).join('')
            : '<span class="text-secondary">No data yet</span>';
        
        // Update regulations list
        const regulations = data.knowledge_graph?.regulations || [];
        document.getElementById('regulations-list').innerHTML = regulations.length > 0
            ? regulations.map(r => `<span class="badge bg-info me-1">${r}</span>`).join('')
            : '<span class="text-secondary">No data yet</span>';
            
        showToast('Statistics refreshed', 'success');
        
    } catch (error) {
        console.error('Error loading stats:', error);
        showToast('Error loading statistics', 'danger');
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// File Upload
// ═══════════════════════════════════════════════════════════════════════════════

const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
let selectedFile = null;

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

document.getElementById('upload-form').addEventListener('submit', async (e) => {
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
    uploadBtn.classList.add('loading');
    uploadBtn.disabled = true;
    
    try {
        const response = await fetch(`${API_BASE}/upload`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast('File uploaded! Processing started...', 'success');
            document.getElementById('upload-progress').style.display = 'block';
            
            // Start polling for progress
            pollJobProgress(data.id);
            
            // Reset form
            selectedFile = null;
            document.getElementById('selected-file').textContent = '';
            fileInput.value = '';
            
        } else {
            showToast(data.detail || 'Upload failed', 'danger');
        }
        
    } catch (error) {
        console.error('Upload error:', error);
        showToast('Upload failed: ' + error.message, 'danger');
    } finally {
        uploadBtn.classList.remove('loading');
        uploadBtn.disabled = false;
    }
});

async function pollJobProgress(jobId) {
    const progressBar = document.getElementById('progress-bar');
    const progressStatus = document.getElementById('progress-status');
    const progressPercent = document.getElementById('progress-percent');
    
    const poll = async () => {
        try {
            const response = await fetch(`${API_BASE}/jobs/${jobId}`);
            const data = await response.json();
            
            progressBar.style.width = `${data.progress}%`;
            progressPercent.textContent = `${data.progress}%`;
            progressStatus.textContent = data.message;
            
            if (data.status === 'completed') {
                showToast('Processing completed successfully!', 'success');
                document.getElementById('upload-progress').style.display = 'none';
                loadUploadedFiles();
                refreshStats();
            } else if (data.status === 'failed') {
                showToast('Processing failed: ' + data.message, 'danger');
                document.getElementById('upload-progress').style.display = 'none';
            } else {
                setTimeout(poll, 2000);
            }
        } catch (error) {
            console.error('Polling error:', error);
        }
    };
    
    poll();
}

async function loadUploadedFiles() {
    try {
        const response = await fetch(`${API_BASE}/files`);
        const data = await response.json();
        
        const tbody = document.getElementById('files-table');
        
        if (data.files.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-secondary">No files uploaded yet</td></tr>';
            return;
        }
        
        tbody.innerHTML = data.files.map(file => `
            <tr>
                <td>${file.filename}</td>
                <td><span class="badge bg-primary">${file.branch}</span></td>
                <td>S${file.semester}</td>
                <td>${formatFileSize(file.size_bytes)}</td>
                <td>${formatDate(file.uploaded_at)}</td>
                <td>
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteFile('${file.filename}')">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            </tr>
        `).join('');
        
    } catch (error) {
        console.error('Error loading files:', error);
    }
}

async function deleteFile(filename) {
    if (!confirm(`Delete file "${filename}"?`)) return;
    
    try {
        const response = await fetch(`${API_BASE}/files/${filename}`, { method: 'DELETE' });
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
        
        let url = `${API_BASE}/subjects?`;
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
            '<div class="col-12 text-center text-danger">Error loading subjects</div>';
    }
}

function renderSubjects(subjects) {
    const grid = document.getElementById('subjects-grid');
    
    if (subjects.length === 0) {
        grid.innerHTML = '<div class="col-12 text-center text-secondary">No subjects found. Upload a syllabus or add subjects manually.</div>';
        return;
    }
    
    grid.innerHTML = subjects.map(subject => `
        <div class="col-md-4">
            <div class="card subject-card h-100" onclick="showSubjectDetails('${subject.code}', '${subject.regulation || '2019'}')">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <span class="badge bg-primary">${subject.code}</span>
                        <div>
                            <span class="badge bg-secondary me-1">${subject.regulation || '2019'}</span>
                            <span class="module-badge">${subject.module_count || 0} modules</span>
                        </div>
                    </div>
                    <h5 class="card-title">${subject.name}</h5>
                    <div class="text-secondary small">
                        <span class="me-3"><i class="bi bi-mortarboard me-1"></i> S${subject.semester}</span>
                        <span class="me-3"><i class="bi bi-building me-1"></i> ${subject.branch}</span>
                        <span><i class="bi bi-star me-1"></i> ${subject.credits} credits</span>
                    </div>
                </div>
            </div>
        </div>
    `).join('');
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
    const modal = new bootstrap.Modal(document.getElementById('subjectDetailsModal'));
    document.getElementById('subject-detail-title').textContent = `Subject: ${code} (${regulation} Scheme)`;
    document.getElementById('subject-detail-content').innerHTML = 'Loading...';
    modal.show();
    
    try {
        const response = await fetch(`${API_BASE}/subjects/${code}?regulation=${regulation}`);
        const subject = await response.json();
        
        let modulesHtml = '';
        if (subject.modules && subject.modules.length > 0) {
            modulesHtml = subject.modules.map(m => `
                <div class="card mb-3">
                    <div class="card-header">
                        <h6 class="mb-0">Module ${m.number}: ${m.name}</h6>
                        <small class="text-secondary">${m.hours || 0} hours</small>
                    </div>
                    <div class="card-body">
                        ${m.topics && m.topics.length > 0 
                            ? `<ul class="mb-0">${m.topics.map(t => `
                                <li>
                                    <strong>${t.name}</strong>
                                    ${t.description ? `<br><small class="text-secondary">${t.description}</small>` : ''}
                                    ${t.keywords && t.keywords.length > 0 
                                        ? `<br><small>${t.keywords.map(k => `<span class="badge bg-secondary me-1">${k}</span>`).join('')}</small>` 
                                        : ''}
                                </li>
                            `).join('')}</ul>`
                            : '<p class="text-secondary mb-0">No topics added</p>'
                        }
                    </div>
                </div>
            `).join('');
        } else {
            modulesHtml = '<p class="text-secondary">No modules found</p>';
        }
        
        document.getElementById('subject-detail-content').innerHTML = `
            <div class="row">
                <div class="col-md-4">
                    <div class="card">
                        <div class="card-body">
                            <h6 class="text-secondary">Subject Info</h6>
                            <p><strong>Code:</strong> ${subject.code}</p>
                            <p><strong>Name:</strong> ${subject.name}</p>
                            <p><strong>Credits:</strong> ${subject.credits}</p>
                            <p><strong>Semester:</strong> S${subject.semester}</p>
                            <p><strong>Branch:</strong> ${subject.branch}</p>
                            <p><strong>Regulation:</strong> ${subject.regulation || '2019'}</p>
                            <p><strong>Category:</strong> ${subject.category || 'N/A'}</p>
                            
                            <hr>
                            <button class="btn btn-sm btn-outline-danger w-100" onclick="deleteSubject('${subject.code}', '${subject.regulation || '2019'}')">
                                <i class="bi bi-trash me-2"></i> Delete Subject
                            </button>
                        </div>
                    </div>
                </div>
                <div class="col-md-8">
                    <h6 class="text-secondary mb-3">Modules & Topics</h6>
                    ${modulesHtml}
                </div>
            </div>
        `;
        
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
        const response = await fetch(`${API_BASE}/subjects`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(subject)
        });
        
        if (response.ok) {
            showToast('Subject added successfully!', 'success');
            bootstrap.Modal.getInstance(document.getElementById('addSubjectModal')).hide();
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
        const response = await fetch(`${API_BASE}/subjects/${code}?regulation=${regulation}`, { method: 'DELETE' });
        if (response.ok) {
            showToast('Subject deleted', 'success');
            bootstrap.Modal.getInstance(document.getElementById('subjectDetailsModal')).hide();
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

document.getElementById('search-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const query = document.getElementById('search-query').value;
    const limit = document.getElementById('search-limit').value;
    const branch = document.getElementById('search-branch').value;
    const semester = document.getElementById('search-semester').value;
    const subjectCode = document.getElementById('search-subject-code').value;
    
    document.getElementById('search-results').innerHTML = 
        '<div class="text-center"><div class="spinner-border text-primary"></div><p class="mt-2">Searching...</p></div>';
    
    try {
        const response = await fetch(`${API_BASE}/search`, {
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
                '<div class="text-center text-secondary"><i class="bi bi-search display-4 d-block mb-3"></i>No results found</div>';
            return;
        }
        
        document.getElementById('search-results').innerHTML = `
            <div class="d-flex justify-content-between align-items-center mb-3">
                <span class="text-secondary">${data.total_results} results found in ${data.search_time_ms.toFixed(0)}ms</span>
            </div>
            ${data.results.map((r, i) => `
                <div class="card mb-3">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start mb-2">
                            <div>
                                <span class="badge bg-primary me-2">${r.subject_code}</span>
                                <span class="text-secondary">${r.subject_name}</span>
                            </div>
                            <span class="badge bg-success">${(r.similarity_score * 100).toFixed(1)}% match</span>
                        </div>
                        <p class="mb-2">${r.content}</p>
                        <small class="text-secondary">
                            ${r.module_name ? `Module: ${r.module_name}` : ''} 
                            ${r.topic_name ? `| Topic: ${r.topic_name}` : ''}
                        </small>
                    </div>
                </div>
            `).join('')}
        `;
        
    } catch (error) {
        document.getElementById('search-results').innerHTML = 
            `<div class="alert alert-danger">Search failed: ${error.message}</div>`;
    }
});

// ═══════════════════════════════════════════════════════════════════════════════
// Jobs
// ═══════════════════════════════════════════════════════════════════════════════

async function loadJobs() {
    try {
        const response = await fetch(`${API_BASE}/jobs`);
        const data = await response.json();
        
        const tbody = document.getElementById('jobs-table');
        
        if (data.jobs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-secondary">No processing jobs yet</td></tr>';
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
                    <div class="progress" style="width: 100px; height: 6px;">
                        <div class="progress-bar" style="width: ${job.progress}%"></div>
                    </div>
                    <small>${job.progress}%</small>
                </td>
                <td>${job.started_at ? formatDate(job.started_at) : '-'}</td>
            </tr>
        `).join('');
        
    } catch (error) {
        console.error('Error loading jobs:', error);
    }
}

function getStatusBadgeClass(status) {
    switch(status) {
        case 'completed': return 'bg-success';
        case 'processing': return 'bg-primary';
        case 'failed': return 'bg-danger';
        default: return 'bg-secondary';
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Settings / Actions
// ═══════════════════════════════════════════════════════════════════════════════

async function setupNeo4j() {
    try {
        const response = await fetch(`${API_BASE}/neo4j/setup`, { method: 'POST' });
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
        const response = await fetch(`${API_BASE}/data/clear?confirm=true`, { method: 'DELETE' });
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
    
    const bgClass = {
        success: 'bg-success',
        danger: 'bg-danger',
        warning: 'bg-warning',
        info: 'bg-info'
    }[type] || 'bg-info';
    
    const html = `
        <div id="${id}" class="toast show ${bgClass} text-white" role="alert">
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;
    
    container.insertAdjacentHTML('beforeend', html);
    
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
    loadDashboard();
});
