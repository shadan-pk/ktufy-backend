// ═══════════════════════════════════════════════════════════════════════════════
// Curriculum Extraction — Admin Panel Functions
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Setup curriculum file input drag-drop and change listeners
 */
function setupCurriculumFileInput() {
    const dropZone = document.getElementById('curriculum-drop-zone');
    const fileInput = document.getElementById('curriculum-file-input');
    const fileNameDisplay = document.getElementById('curriculum-file-name');
    const extractBtn = document.getElementById('extract-curriculum-btn');

    if (!dropZone || !fileInput) return;

    // File input change
    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            fileNameDisplay.textContent = file.name;
            extractBtn.disabled = false;
        }
    });

    // Drag over
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.style.opacity = '0.7';
        dropZone.style.borderColor = 'var(--info)';
    });

    // Drag leave
    dropZone.addEventListener('dragleave', () => {
        dropZone.style.opacity = '1';
        dropZone.style.borderColor = 'var(--border)';
    });

    // Drop
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.style.opacity = '1';
        dropZone.style.borderColor = 'var(--border)';

        const files = e.dataTransfer.files;
        if (files.length > 0 && files[0].name.endsWith('.pdf')) {
            fileInput.files = files;
            fileNameDisplay.textContent = files[0].name;
            extractBtn.disabled = false;
        } else {
            showToast('Please drop a PDF file', 'danger');
        }
    });
}

/**
 * Extract curriculum mappings from uploaded PDF
 */
async function extractCurriculum() {
    const fileInput = document.getElementById('curriculum-file-input');
    const branch = document.getElementById('curriculum-branch')?.value;
    const regulation = document.getElementById('curriculum-regulation')?.value || '2019';
    const extractBtn = document.getElementById('extract-curriculum-btn');
    const resultContainer = document.getElementById('curriculum-result-container');
    const resultContent = document.getElementById('curriculum-result-content');

    if (!fileInput.files[0]) {
        showToast('Please select a PDF file', 'warning');
        return;
    }

    if (!branch) {
        showToast('Please select a branch', 'warning');
        return;
    }

    // Show loading state
    const spinnerEl = extractBtn.querySelector('.spinner');
    const btnText = extractBtn.querySelector('.btn-text');
    spinnerEl.style.display = 'inline-block';
    extractBtn.disabled = true;

    try {
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('branch', branch);
        formData.append('regulation', regulation);

        showToast('Extracting curriculum mappings...', 'info');

        const response = await fetch(`${API_BASE_V2}/extract-curriculum`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP ${response.status}`);
        }

        const data = await response.json();

        // Display result
        resultContent.innerHTML = `
            <div class="alert alert-success" style="margin-bottom: 1rem;">
                <div style="display: flex; gap: 0.75rem;">
                    <i data-lucide="check-circle" style="width: 20px; height: 20px; flex-shrink: 0; color: var(--success);"></i>
                    <div>
                        <div style="font-weight: 600; margin-bottom: 0.25rem;">Extraction Successful</div>
                        <div style="font-size: 0.875rem; color: var(--muted-foreground);">
                            ${data.message}
                        </div>
                    </div>
                </div>
            </div>
            <div class="grid-2 gap-md">
                <div class="card">
                    <div class="card-body">
                        <div style="font-size: 0.875rem; color: var(--muted-foreground); margin-bottom: 0.5rem;">Mappings Extracted</div>
                        <div style="font-size: 1.875rem; font-weight: 700;">${data.mappings_extracted}</div>
                    </div>
                </div>
                <div class="card">
                    <div class="card-body">
                        <div style="font-size: 0.875rem; color: var(--muted-foreground); margin-bottom: 0.5rem;">Inserted to Database</div>
                        <div style="font-size: 1.875rem; font-weight: 700;">${data.mappings_inserted}</div>
                    </div>
                </div>
            </div>
            <div class="text-sm text-muted" style="margin-top: 1rem;">
                Branch: <strong>${escapeHtml(data.branch)}</strong> | 
                Regulation: <strong>${escapeHtml(data.regulation)}</strong> | 
                Extracted: <strong>${new Date(data.timestamp).toLocaleString()}</strong>
            </div>
        `;

        resultContainer.style.display = 'block';

        // Re-render lucide icons
        if (typeof lucide !== 'undefined') lucide.createIcons();

        showToast(`Successfully extracted and stored ${data.mappings_extracted} mappings`, 'success');

        // Refresh mappings table
        await loadCurriculumMappings();

        // Reset form
        fileInput.value = '';
        document.getElementById('curriculum-file-name').textContent = 'No file selected';

    } catch (error) {
        console.error('Error extracting curriculum:', error);
        resultContent.innerHTML = `
            <div class="alert alert-danger">
                <div style="display: flex; gap: 0.75rem;">
                    <i data-lucide="alert-circle" style="width: 20px; height: 20px; flex-shrink: 0; color: var(--destructive);"></i>
                    <div>
                        <div style="font-weight: 600; margin-bottom: 0.25rem;">Extraction Failed</div>
                        <div style="font-size: 0.875rem; color: var(--muted-foreground);">
                            ${escapeHtml(error.message)}
                        </div>
                    </div>
                </div>
            </div>
        `;
        resultContainer.style.display = 'block';

        if (typeof lucide !== 'undefined') lucide.createIcons();

        showToast(`Error: ${error.message}`, 'danger');
    } finally {
        spinnerEl.style.display = 'none';
        extractBtn.disabled = false;
    }
}

/**
 * Load and display curriculum elective mappings from database
 */
async function loadCurriculumMappings(branch = null, regulation = null) {
    const table = document.getElementById('curriculum-mappings-table');
    if (!table) return;

    table.innerHTML = '<tr><td class="td-empty" colspan="7">Loading mappings...</td></tr>';

    try {
        let url = `${API_BASE_V2}/curriculum-mappings`;
        const params = new URLSearchParams();

        if (branch) params.append('branch', branch);
        if (regulation) params.append('regulation', regulation);

        if (params.toString()) {
            url += '?' + params.toString();
        }

        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        if (data.total === 0) {
            table.innerHTML = '<tr><td class="td-empty" colspan="7">No curriculum mappings found. Extract a curriculum PDF first.</td></tr>';
            return;
        }

        table.innerHTML = (data.mappings || []).map(mapping => `
            <tr>
                <td><strong>${escapeHtml(mapping.subject_code || '')}</strong></td>
                <td>${escapeHtml(mapping.subject_name || '-')}</td>
                <td><span class="badge" style="background: ${getProgramElectiveColor(mapping.program_elective)}">${escapeHtml(mapping.program_elective || 'N/A')}</span></td>
                <td>${mapping.semester || '-'}</td>
                <td>${mapping.credits || '-'}</td>
                <td>${escapeHtml(mapping.branch || '-')}</td>
                <td>${escapeHtml(mapping.regulation || '-')}</td>
            </tr>
        `).join('');

    } catch (error) {
        console.error('Error loading curriculum mappings:', error);
        table.innerHTML = `<tr><td class="td-empty" colspan="7">Error loading mappings: ${escapeHtml(error.message)}</td></tr>`;
    }
}

/**
 * Get color for program_elective badge
 */
function getProgramElectiveColor(programElective) {
    const colors = {
        'PEC1': '#3b82f6',  // blue
        'PEC2': '#8b5cf6',  // purple
        'PEC3': '#ec4899',  // pink
        'PEC4': '#f97316',  // orange
        'PEC5': '#06b6d4',  // cyan
        'PCC': '#10b981',   // green
        'OEC': '#6366f1'    // indigo
    };
    return colors[programElective] || '#6b7280';  // gray fallback
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Setup custom selects for curriculum section if they exist
    const curriculumSelects = document.querySelectorAll('.custom-select[data-id^="curriculum-"]');
    if (curriculumSelects.length > 0) {
        new CustomSelect(document.querySelector('.custom-select[data-id="curriculum-branch"]'));
        new CustomSelect(document.querySelector('.custom-select[data-id="curriculum-regulation"]'));
    }
});
