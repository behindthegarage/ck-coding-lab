// workspace.js - Three-pane layout with collapsible panels
// Version 41 - Three-pane workspace layout

// Redirect if not logged in
if (!isLoggedIn()) {
    window.location.href = '/lab/login';
}

// Get project ID from URL
const projectId = window.location.pathname.split('/').pop();

// State
let project = null;
let conversations = [];
let projectFiles = [];
let currentCode = '';
let sandboxRunner = null;
let pendingUpload = null;
let currentFileId = null;
let currentFileOriginalContent = '';
let fileModalSaving = false;
let fileActionDialogState = null;
let workspaceToastTimer = null;
let versions = [];
let fileSearchQuery = '';
let activeFileMenuId = null;
let sidebarCollapsed = false;
let previewCollapsed = false;
let isMobile = window.innerWidth < 768;
let isTablet = window.innerWidth >= 768 && window.innerWidth < 1024;

// Load project data
async function loadProject() {
    const data = await apiRequest(`/projects/${projectId}`);

    if (!data) return;

    project = data.project;
    conversations = data.conversations || [];
    projectFiles = data.files || [];
    currentCode = project.current_code || '';

    // Update UI
    document.getElementById('project-name').textContent = project.name;
    
    // Update project type badge and labels
    updateProjectTypeUI(project.language);
    
    // Load file tree
    loadFileTree();
    
    updateCodeDisplay();

    // Load conversation history
    loadConversations();

    // Run initial preview if there's code (and not Python)
    if (project.language !== 'python') {
        runPreview();
    }
}

function updateFileSearchUI() {
    const input = document.getElementById('file-search-input');
    const clearBtn = document.getElementById('file-search-clear');
    if (!input || !clearBtn) return;

    input.value = fileSearchQuery;
    clearBtn.classList.toggle('hidden', !fileSearchQuery);
}

function getFilteredProjectFiles() {
    const query = fileSearchQuery.trim().toLowerCase();
    if (!query) return projectFiles;
    return projectFiles.filter(file => (file.filename || '').toLowerCase().includes(query));
}

function getProjectFileById(fileId) {
    return projectFiles.find(file => String(file.id) === String(fileId)) || null;
}

function closeAllFileMenus() {
    activeFileMenuId = null;
    document.querySelectorAll('.file-item').forEach(el => el.classList.remove('menu-open'));
}

function toggleFileMenu(fileId) {
    activeFileMenuId = String(activeFileMenuId) === String(fileId) ? null : String(fileId);
    document.querySelectorAll('.file-item').forEach(el => {
        el.classList.toggle('menu-open', String(el.dataset.fileId) === String(activeFileMenuId));
    });
}

async function renameProjectFileById(fileId) {
    const file = getProjectFileById(fileId);
    if (!file) return;

    if (String(currentFileId) === String(fileId)) {
        await renameCurrentFile();
        return;
    }

    const action = await showFileActionDialog({
        title: 'Rename file',
        message: `Choose a new name for ${file.filename}.`,
        confirmLabel: 'Rename file',
        confirmClass: 'btn-primary',
        initialValue: file.filename,
        inputLabel: 'New filename',
        placeholder: file.filename,
        needsInput: true,
        validate: (value) => {
            if (value === file.filename) return '';
            return validateFilenameInput(value, { existingId: fileId });
        }
    });

    if (!action.confirmed || action.value === file.filename) return;

    const data = await apiRequest(`/files/${fileId}/rename`, {
        method: 'PUT',
        body: { filename: action.value }
    });

    if (!data || !data.success) {
        showWorkspaceToast(data?.error || 'Failed to rename file.', 'error', 4200);
        return;
    }

    await refreshWorkspaceAfterFileSave();
    showWorkspaceToast(`Renamed to ${data.file.filename}.`, 'success');
}

async function deleteProjectFileById(fileId) {
    const file = getProjectFileById(fileId);
    if (!file) return;

    if (String(currentFileId) === String(fileId)) {
        await deleteCurrentFile();
        return;
    }

    const action = await showFileActionDialog({
        title: 'Delete file',
        message: `Delete ${file.filename}? If you saved a version first, you can restore it later from Version History.`,
        confirmLabel: 'Delete file',
        confirmClass: 'btn-small file-modal-danger',
        needsInput: false
    });

    if (!action.confirmed) return;

    const data = await apiRequest(`/files/${fileId}`, {
        method: 'DELETE'
    });

    if (!data || !data.success) {
        showWorkspaceToast(data?.error || 'Failed to delete file.', 'error', 4200);
        return;
    }

    await refreshWorkspaceAfterFileSave();
    showWorkspaceToast(`Deleted ${file.filename}.`, 'success');
}

async function handleFileMenuAction(action, fileId) {
    closeAllFileMenus();

    if (action === 'open') {
        const file = getProjectFileById(fileId);
        if (file) {
            await viewFile(file.id, file.filename);
        }
        return;
    }

    if (action === 'rename') {
        await renameProjectFileById(fileId);
        return;
    }

    if (action === 'delete') {
        await deleteProjectFileById(fileId);
    }
}

// Load file tree in sidebar
function loadFileTree() {
    const container = document.getElementById('file-tree');
    const filteredFiles = getFilteredProjectFiles();
    updateFileSearchUI();
    
    if (projectFiles.length === 0) {
        container.innerHTML = '<div class="file-loading">No files yet</div>';
        return;
    }

    if (filteredFiles.length === 0) {
        const safeQuery = escapeHtml(fileSearchQuery.trim());
        container.innerHTML = `<div class="file-loading">No files match “${safeQuery}”.</div>`;
        return;
    }
    
    container.innerHTML = '';
    
    filteredFiles.forEach(file => {
        const fileEl = document.createElement('div');
        fileEl.className = 'file-item';
        fileEl.dataset.fileId = file.id;
        fileEl.dataset.filename = file.filename;

        if (String(currentFileId) === String(file.id)) {
            fileEl.classList.add('active');
        }
        if (String(activeFileMenuId) === String(file.id)) {
            fileEl.classList.add('menu-open');
        }
        
        // Determine icon and badge
        let icon = '📄';
        let badge = '';
        
        if (file.filename.endsWith('.md')) {
            icon = '📝';
            if (['design.md', 'architecture.md', 'todo.md', 'notes.md'].includes(file.filename)) {
                icon = '📋';
            }
        } else if (file.filename.endsWith('.js')) {
            icon = '📜';
            badge = 'JS';
            fileEl.classList.add('code-file');
        } else if (file.filename.endsWith('.py')) {
            icon = '🐍';
            badge = 'PY';
            fileEl.classList.add('code-file');
        } else if (file.filename.endsWith('.html')) {
            icon = '🌐';
            badge = 'HTML';
            fileEl.classList.add('code-file');
        } else if (file.filename.endsWith('.css')) {
            icon = '🎨';
            badge = 'CSS';
            fileEl.classList.add('code-file');
        }
        
        fileEl.innerHTML = `
            <div class="file-item-main">
                <span class="file-icon">${icon}</span>
                <span class="file-name">${escapeHtml(file.filename)}</span>
                ${badge ? `<span class="file-badge">${badge}</span>` : ''}
            </div>
            <div class="file-item-actions">
                <button class="file-menu-toggle" type="button" aria-label="File actions">⋯</button>
                <div class="file-action-menu">
                    <button class="file-action-menu-item" type="button" data-file-action="open">Open</button>
                    <button class="file-action-menu-item" type="button" data-file-action="rename">Rename</button>
                    <button class="file-action-menu-item danger" type="button" data-file-action="delete">Delete</button>
                </div>
            </div>
        `;

        fileEl.querySelector('.file-item-main').addEventListener('click', async () => {
            closeAllFileMenus();
            await viewFile(file.id, file.filename);
        });

        fileEl.querySelector('.file-menu-toggle').addEventListener('click', (event) => {
            event.stopPropagation();
            toggleFileMenu(file.id);
        });

        fileEl.querySelectorAll('.file-action-menu-item').forEach((button) => {
            button.addEventListener('click', async (event) => {
                event.stopPropagation();
                await handleFileMenuAction(button.dataset.fileAction, file.id);
            });
        });
        
        container.appendChild(fileEl);
    });
}

function setFileSearchQuery(value = '') {
    fileSearchQuery = value.trimStart();
    activeFileMenuId = null;
    loadFileTree();
}

function setFileModalStatus(message = '', type = 'info') {
    const status = document.getElementById('file-modal-status');
    if (!status) return;

    if (!message) {
        status.textContent = '';
        status.className = 'file-modal-status hidden';
        return;
    }

    status.textContent = message;
    status.className = `file-modal-status ${type}`;
}

function isFileModalDirty() {
    const editor = document.getElementById('modal-file-editor');
    if (!editor || currentFileId === null) return false;
    return editor.value !== currentFileOriginalContent;
}

function getCurrentFileRecord() {
    return projectFiles.find(file => String(file.id) === String(currentFileId)) || null;
}

function validateFilenameInput(filename, { existingId = null } = {}) {
    const value = (filename || '').trim();

    if (!value) {
        return 'Filename is required.';
    }

    if (value.includes('/') || value.includes('\\') || value.includes('..')) {
        return 'Filename cannot include folders or ..';
    }

    if (projectFiles.some(file => String(file.id) !== String(existingId) && file.filename === value)) {
        return `A file named ${value} already exists.`;
    }

    return '';
}

function closeFileActionDialog(result = { confirmed: false, value: '' }) {
    const modal = document.getElementById('file-action-modal');
    const error = document.getElementById('file-action-error');
    const inputGroup = document.getElementById('file-action-input-group');
    const input = document.getElementById('file-action-input');
    const resolver = fileActionDialogState?.resolve;

    fileActionDialogState = null;
    modal.classList.add('hidden');
    error.textContent = '';
    error.classList.add('hidden');
    inputGroup.classList.add('hidden');
    input.value = '';

    if (resolver) {
        resolver(result);
    }
}

function submitFileActionDialog() {
    if (!fileActionDialogState) return;

    const error = document.getElementById('file-action-error');
    const input = document.getElementById('file-action-input');
    const needsInput = fileActionDialogState.needsInput;
    const value = needsInput ? input.value.trim() : '';

    error.textContent = '';
    error.classList.add('hidden');

    if (needsInput && typeof fileActionDialogState.validate === 'function') {
        const validationError = fileActionDialogState.validate(value);
        if (validationError) {
            error.textContent = validationError;
            error.classList.remove('hidden');
            input.focus();
            input.select();
            return;
        }
    }

    closeFileActionDialog({ confirmed: true, value });
}

function showWorkspaceToast(message, type = 'info', durationMs = 3200) {
    const toast = document.getElementById('workspace-toast');
    if (!toast || !message) return;

    if (workspaceToastTimer) {
        clearTimeout(workspaceToastTimer);
    }

    toast.textContent = message;
    toast.className = `workspace-toast ${type}`;

    workspaceToastTimer = setTimeout(() => {
        toast.textContent = '';
        toast.className = 'workspace-toast hidden';
        workspaceToastTimer = null;
    }, durationMs);
}

function showFileActionDialog({
    title,
    message,
    confirmLabel = 'Confirm',
    confirmClass = 'btn-primary',
    initialValue = '',
    inputLabel = 'Filename',
    placeholder = '',
    needsInput = false,
    validate = null
}) {
    if (fileActionDialogState) {
        closeFileActionDialog();
    }

    const modal = document.getElementById('file-action-modal');
    const titleEl = document.getElementById('file-action-title');
    const messageEl = document.getElementById('file-action-message');
    const inputGroup = document.getElementById('file-action-input-group');
    const inputLabelEl = document.getElementById('file-action-input-label');
    const inputEl = document.getElementById('file-action-input');
    const confirmBtn = document.getElementById('file-action-confirm');
    const error = document.getElementById('file-action-error');

    titleEl.textContent = title || 'File action';
    messageEl.textContent = message || '';
    inputLabelEl.textContent = inputLabel;
    inputEl.value = initialValue;
    inputEl.placeholder = placeholder;
    confirmBtn.textContent = confirmLabel;
    confirmBtn.className = confirmClass;
    error.textContent = '';
    error.classList.add('hidden');

    if (needsInput) {
        inputGroup.classList.remove('hidden');
    } else {
        inputGroup.classList.add('hidden');
    }

    modal.classList.remove('hidden');

    return new Promise(resolve => {
        fileActionDialogState = {
            resolve,
            needsInput,
            validate
        };

        if (needsInput) {
            setTimeout(() => {
                inputEl.focus();
                inputEl.select();
            }, 0);
        } else {
            setTimeout(() => confirmBtn.focus(), 0);
        }
    });
}

function showWorkspaceToast(message, type = 'info', durationMs = 3200) {
    const toast = document.getElementById('workspace-toast');
    if (!toast) return;

    if (workspaceToastTimer) {
        clearTimeout(workspaceToastTimer);
    }

    toast.textContent = message;
    toast.className = `workspace-toast ${type}`;

    workspaceToastTimer = setTimeout(() => {
        toast.textContent = '';
        toast.className = 'workspace-toast hidden';
        workspaceToastTimer = null;
    }, durationMs);
}

function updateFileModalSaveState() {
    const saveBtn = document.getElementById('file-modal-save');
    const renameBtn = document.getElementById('file-modal-rename');
    const deleteBtn = document.getElementById('file-modal-delete');
    const editor = document.getElementById('modal-file-editor');
    if (!saveBtn || !renameBtn || !deleteBtn || !editor) return;

    const dirty = isFileModalDirty();
    const hasFile = currentFileId !== null;
    saveBtn.disabled = fileModalSaving || !hasFile || !dirty;
    renameBtn.disabled = fileModalSaving || !hasFile;
    deleteBtn.disabled = fileModalSaving || !hasFile;
    saveBtn.textContent = fileModalSaving ? 'Saving...' : 'Save';
    editor.disabled = fileModalSaving || !hasFile;
}

async function confirmDiscardFileModalChanges(message = 'Discard unsaved changes?') {
    if (!isFileModalDirty()) return true;

    const action = await showFileActionDialog({
        title: 'Discard unsaved changes',
        message,
        confirmLabel: 'Discard changes',
        confirmClass: 'btn-small file-modal-danger',
        needsInput: false
    });

    return action.confirmed;
}

async function refreshWorkspaceAfterFileSave() {
    const data = await apiRequest(`/projects/${projectId}`);
    if (!data || !data.success) return;

    project = data.project;
    projectFiles = data.files || [];
    currentCode = project.current_code || '';
    activeFileMenuId = null;

    loadFileTree();
    updateCodeDisplay();

    if (project.language !== 'python') {
        runPreview();
    }
}

// View a file's contents (opens in editable modal)
async function viewFile(fileId, filename) {
    const fileModal = document.getElementById('file-modal');
    if (currentFileId !== null && fileModal && !fileModal.classList.contains('hidden')) {
        const canDiscard = await confirmDiscardFileModalChanges('Open a different file and discard your unsaved changes?');
        if (!canDiscard) {
            return;
        }
    }

    currentFileId = fileId;
    currentFileOriginalContent = 'Loading...';

    // Update active state in sidebar
    document.querySelectorAll('.file-item').forEach(el => {
        el.classList.remove('active');
        if (el.dataset.fileId == fileId) {
            el.classList.add('active');
        }
    });

    // Show modal
    const modal = document.getElementById('file-modal');
    const modalFilename = document.getElementById('modal-filename');
    const modalEditor = document.getElementById('modal-file-editor');

    modalFilename.textContent = filename;
    modalEditor.value = 'Loading...';
    modal.classList.remove('hidden');
    setFileModalStatus('Loading file...', 'info');
    updateFileModalSaveState();

    // Fetch file content
    const data = await apiRequest(`/files/${fileId}`);

    if (data && data.success) {
        currentFileOriginalContent = data.file.content || '';
        modalEditor.value = currentFileOriginalContent;
        setFileModalStatus('', 'info');
        updateFileModalSaveState();
        modalEditor.focus();
        modalEditor.setSelectionRange(0, 0);
    } else {
        modalEditor.value = '';
        currentFileOriginalContent = '';
        setFileModalStatus(data?.error || 'Error loading file.', 'error');
        updateFileModalSaveState();
    }
}

async function saveCurrentFile() {
    if (currentFileId === null || fileModalSaving) return;

    const editor = document.getElementById('modal-file-editor');
    if (!editor) return;

    const content = editor.value;
    if (content === currentFileOriginalContent) {
        setFileModalStatus('No changes to save.', 'info');
        updateFileModalSaveState();
        return;
    }

    fileModalSaving = true;
    setFileModalStatus('Saving changes...', 'info');
    updateFileModalSaveState();

    try {
        const data = await apiRequest(`/files/${currentFileId}`, {
            method: 'PUT',
            body: { content }
        });

        if (!data || !data.success) {
            setFileModalStatus(data?.error || 'Failed to save file.', 'error');
            return;
        }

        currentFileOriginalContent = data.file.content || '';
        editor.value = currentFileOriginalContent;
        setFileModalStatus('Saved.', 'success');
        await refreshWorkspaceAfterFileSave();
    } catch (error) {
        console.error('Error saving file:', error);
        setFileModalStatus(error.message || 'Failed to save file.', 'error');
    } finally {
        fileModalSaving = false;
        updateFileModalSaveState();
    }
}

async function renameCurrentFile() {
    if (currentFileId === null || fileModalSaving) return;

    const file = getCurrentFileRecord();
    if (!file) return;

    if (!(await confirmDiscardFileModalChanges('Rename this file and discard your unsaved changes?'))) {
        return;
    }

    const action = await showFileActionDialog({
        title: 'Rename file',
        message: `Choose a new name for ${file.filename}.`,
        confirmLabel: 'Rename file',
        confirmClass: 'btn-primary',
        initialValue: file.filename,
        inputLabel: 'New filename',
        placeholder: file.filename,
        needsInput: true,
        validate: (value) => {
            if (value === file.filename) return '';
            return validateFilenameInput(value, { existingId: currentFileId });
        }
    });

    if (!action.confirmed) return;

    const nextFilename = action.value;
    if (nextFilename === file.filename) {
        return;
    }

    fileModalSaving = true;
    setFileModalStatus('Renaming file...', 'info');
    updateFileModalSaveState();

    try {
        const data = await apiRequest(`/files/${currentFileId}/rename`, {
            method: 'PUT',
            body: { filename: nextFilename }
        });

        if (!data || !data.success) {
            setFileModalStatus(data?.error || 'Failed to rename file.', 'error');
            return;
        }

        document.getElementById('modal-filename').textContent = data.file.filename;
        currentFileOriginalContent = data.file.content || '';
        document.getElementById('modal-file-editor').value = currentFileOriginalContent;
        await refreshWorkspaceAfterFileSave();
        setFileModalStatus(`Renamed to ${data.file.filename}.`, 'success');
    } catch (error) {
        console.error('Error renaming file:', error);
        setFileModalStatus(error.message || 'Failed to rename file.', 'error');
    } finally {
        fileModalSaving = false;
        updateFileModalSaveState();
    }
}

async function deleteCurrentFile() {
    if (currentFileId === null || fileModalSaving) return;

    const file = getCurrentFileRecord();
    if (!file) return;

    if (!(await confirmDiscardFileModalChanges('Delete this file and discard your unsaved changes?'))) {
        return;
    }

    const action = await showFileActionDialog({
        title: 'Delete file',
        message: `Delete ${file.filename}? If you saved a version first, you can restore it later from Version History.`,
        confirmLabel: 'Delete file',
        confirmClass: 'btn-small file-modal-danger',
        needsInput: false
    });

    if (!action.confirmed) return;

    fileModalSaving = true;
    setFileModalStatus('Deleting file...', 'info');
    updateFileModalSaveState();

    try {
        const data = await apiRequest(`/files/${currentFileId}`, {
            method: 'DELETE'
        });

        if (!data || !data.success) {
            setFileModalStatus(data?.error || 'Failed to delete file.', 'error');
            return;
        }

        await closeFileModal(true);
        await refreshWorkspaceAfterFileSave();
    } catch (error) {
        console.error('Error deleting file:', error);
        setFileModalStatus(error.message || 'Failed to delete file.', 'error');
    } finally {
        fileModalSaving = false;
        updateFileModalSaveState();
    }
}

// Close file modal
async function closeFileModal(force = false) {
    if (!force) {
        const canDiscard = await confirmDiscardFileModalChanges();
        if (!canDiscard) {
            return false;
        }
    }

    document.getElementById('file-modal').classList.add('hidden');
    document.querySelectorAll('.file-item').forEach(el => el.classList.remove('active'));
    document.getElementById('modal-file-editor').value = '';
    setFileModalStatus('', 'info');
    currentFileId = null;
    currentFileOriginalContent = '';
    fileModalSaving = false;
    updateFileModalSaveState();
    return true;
}

function openVersionsModal() {
    document.getElementById('versions-modal').classList.remove('hidden');
    setVersionsStatus('');
    loadVersions();
}

function closeVersionsModal() {
    document.getElementById('versions-modal').classList.add('hidden');
}

function setVersionsStatus(message = '', type = 'info') {
    const status = document.getElementById('versions-status');
    if (!status) return;

    if (!message) {
        status.textContent = '';
        status.className = 'versions-status hidden';
        return;
    }

    status.textContent = message;
    status.className = `versions-status ${type}`;
}

function formatVersionTimestamp(timestamp) {
    if (!timestamp) return 'Unknown time';

    const date = new Date(timestamp.replace(' ', 'T'));
    if (Number.isNaN(date.getTime())) {
        return timestamp;
    }

    return date.toLocaleString([], {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit'
    });
}

function getVersionDescription(version) {
    const description = (version.description || '').trim();
    return description || 'Manual save';
}

function renderVersionsList() {
    const container = document.getElementById('versions-list');
    if (!container) return;

    if (versions.length === 0) {
        container.innerHTML = '<div class="file-loading">No saved versions yet.</div>';
        return;
    }

    container.innerHTML = versions.map(version => {
        const hasSnapshot = Number(version.has_files_snapshot) === 1;
        const entryFile = version.entry_filename ? `<span class="version-chip">${escapeHtml(version.entry_filename)}</span>` : '';
        const snapshotType = `<span class="version-chip">${hasSnapshot ? 'Multi-file snapshot' : 'Single-file save'}</span>`;

        return `
            <div class="version-item">
                <div class="version-item-main">
                    <div class="version-item-top">
                        <strong>${escapeHtml(getVersionDescription(version))}</strong>
                        <span class="version-date">${escapeHtml(formatVersionTimestamp(version.created_at))}</span>
                    </div>
                    <div class="version-meta">
                        ${snapshotType}
                        ${entryFile}
                    </div>
                </div>
                <button class="btn-small restore-version-btn" data-version-id="${version.id}">Restore</button>
            </div>
        `;
    }).join('');

    container.querySelectorAll('.restore-version-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const versionId = Number(btn.dataset.versionId);
            const version = versions.find(item => item.id === versionId);
            await restoreVersion(version, btn);
        });
    });
}

async function loadVersions() {
    const container = document.getElementById('versions-list');
    if (!container) return;

    container.innerHTML = '<div class="file-loading">Loading versions...</div>';

    const data = await apiRequest(`/projects/${projectId}/versions`);
    if (!data || !data.success) {
        versions = [];
        container.innerHTML = '<div class="file-loading">Could not load saved versions.</div>';
        return;
    }

    versions = data.versions || [];
    renderVersionsList();
}

async function restoreVersion(version, buttonEl) {
    if (!version) return;

    const description = getVersionDescription(version);
    const action = await showFileActionDialog({
        title: 'Restore saved version',
        message: `Restore "${description}" from ${formatVersionTimestamp(version.created_at)}? This will replace the project's current files with that saved version.`,
        confirmLabel: 'Restore version',
        confirmClass: 'btn-primary',
        needsInput: false
    });
    if (!action.confirmed) return;

    const originalLabel = buttonEl ? buttonEl.textContent : '';
    if (buttonEl) {
        buttonEl.disabled = true;
        buttonEl.textContent = 'Restoring...';
    }

    setVersionsStatus('Restoring version...', 'info');

    try {
        const data = await apiRequest(`/projects/${projectId}/versions/${version.id}/restore`, {
            method: 'POST'
        });

        if (!data || !data.success) {
            setVersionsStatus(data?.error || 'Failed to restore that version.', 'error');
            return;
        }

        await closeFileModal(true);
        await loadProject();
        await loadVersions();
        setVersionsStatus(`Restored "${description}".`, 'success');
        showWorkspaceToast(`Restored "${description}".`, 'success');
    } catch (error) {
        console.error('Error restoring version:', error);
        const message = error.message || 'Failed to restore that version.';
        setVersionsStatus(message, 'error');
        showWorkspaceToast(message, 'error', 4200);
    } finally {
        if (buttonEl) {
            buttonEl.disabled = false;
            buttonEl.textContent = originalLabel || 'Restore';
        }
    }
}

// Toggle sidebar
function toggleSidebar() {
    const sidebar = document.getElementById('project-sidebar');
    const workspace = document.getElementById('workspace-container');
    
    sidebarCollapsed = !sidebarCollapsed;
    
    if (isMobile || isTablet) {
        // On mobile/tablet, use slide-in overlay
        if (sidebarCollapsed) {
            sidebar.classList.remove('open');
            workspace.classList.remove('sidebar-open');
        } else {
            sidebar.classList.add('open');
            workspace.classList.add('sidebar-open');
        }
    } else {
        // On desktop, collapse/expand
        sidebar.classList.toggle('collapsed', sidebarCollapsed);
    }
    
    // Save preference
    localStorage.setItem('sidebarCollapsed', sidebarCollapsed);
}

// Toggle preview panel
function togglePreview() {
    const preview = document.getElementById('preview-pane');
    const showBtn = document.getElementById('show-preview-btn');
    
    previewCollapsed = !previewCollapsed;
    
    if (isMobile) {
        // On mobile, use slide-in from right
        if (previewCollapsed) {
            preview.classList.remove('open');
            showBtn.classList.remove('hidden');
        } else {
            preview.classList.add('open');
            showBtn.classList.add('hidden');
        }
    } else {
        // On desktop, collapse/expand
        preview.classList.toggle('collapsed', previewCollapsed);
    }
    
    // Save preference
    localStorage.setItem('previewCollapsed', previewCollapsed);
}

// Handle window resize for responsive layout
function handleResize() {
    const newIsMobile = window.innerWidth < 768;
    const newIsTablet = window.innerWidth >= 768 && window.innerWidth < 1024;
    
    // Reset classes when crossing breakpoints
    if (newIsMobile !== isMobile || newIsTablet !== isTablet) {
        const sidebar = document.getElementById('project-sidebar');
        const preview = document.getElementById('preview-pane');
        const workspace = document.getElementById('workspace-container');
        const showPreviewBtn = document.getElementById('show-preview-btn');
        
        // Reset sidebar
        sidebar.classList.remove('open', 'collapsed');
        workspace.classList.remove('sidebar-open');
        
        // Reset preview
        preview.classList.remove('open');
        
        if (newIsMobile) {
            // Mobile: start with preview hidden
            previewCollapsed = true;
            showPreviewBtn.classList.remove('hidden');
        } else if (newIsTablet) {
            // Tablet: no sidebar visible by default
            sidebarCollapsed = true;
            previewCollapsed = false;
            showPreviewBtn.classList.add('hidden');
        } else {
            // Desktop: use saved preferences
            sidebarCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
            previewCollapsed = localStorage.getItem('previewCollapsed') === 'true';
            sidebar.classList.toggle('collapsed', sidebarCollapsed);
            preview.classList.toggle('collapsed', previewCollapsed);
            showPreviewBtn.classList.add('hidden');
        }
    }
    
    isMobile = newIsMobile;
    isTablet = newIsTablet;
}

// Update UI based on project type (p5js, html, or python)
function updateProjectTypeUI(language) {
    const badge = document.getElementById('project-type-badge');
    const welcome = document.querySelector('.chat-welcome');
    const previewPane = document.getElementById('preview-pane');
    
    if (language === 'html') {
        if (badge) {
            badge.textContent = '🌐 HTML';
            badge.className = 'project-badge badge-html';
        }
    } else if (language === 'python') {
        if (badge) {
            badge.textContent = '🐍 Python';
            badge.className = 'project-badge badge-python';
        }
        // Hide preview pane for Python projects
        if (previewPane) {
            previewPane.style.display = 'none';
            // Adjust grid to two columns
            document.querySelector('.workspace-three-pane').style.gridTemplateColumns = '200px 1fr';
        }
        // Update welcome message for Python
        if (welcome) {
            welcome.innerHTML = `<p>👋 Welcome to your Python project!</p>
                <p>I'm Hari — your coding partner. I read and write files to track our work.</p>
                <p class="example">Try: "Make a script that generates random passwords" or "Check todo.md and let's plan"</p>`;
        }
        // Update quick actions for Python
        const quickActions = document.querySelector('.quick-actions');
        if (quickActions) {
            quickActions.innerHTML = `
                <button class="quick-btn" data-prompt="Add error handling">🛡️ Add Error Handling</button>
                <button class="quick-btn" data-prompt="Add comments explaining the code">💬 Add Comments</button>
                <button class="quick-btn" data-prompt="Fix any bugs">🐛 Fix Bugs</button>
                <button class="quick-btn" data-prompt="Explain how this works">❓ Explain</button>
            `;
            // Re-attach event listeners
            quickActions.querySelectorAll('.quick-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    const prompt = btn.dataset.prompt;
                    sendMessage(prompt);
                });
            });
        }
    } else {
        // Default to p5js
        if (badge) {
            badge.textContent = '🎨 p5.js';
            badge.className = 'project-badge badge-p5js';
        }
        // Update welcome message for agentic workflow
        if (welcome) {
            welcome.innerHTML = `<p>👋 Welcome to your coding project!</p>
                <p>I'm Hari — your coding partner. I read and write files to keep track of our work.</p>
                <p class="example">Try: "Make a game where a ball bounces" or "Check todo.md and let's plan"</p>`;
        }
    }
}

// Format text with proper line breaks and basic markdown
function formatText(text) {
    if (!text) return '';
    
    // Escape HTML first
    let formatted = escapeHtml(text);
    
    // Convert line breaks to <br> and <p> tags
    const paragraphs = formatted.split(/\n\n+/);
    return paragraphs.map(p => {
        // Handle single line breaks within paragraphs
        const lines = p.split(/\n/);
        const withBreaks = lines.join('<br>');
        return `<p>${withBreaks}</p>`;
    }).join('');
}

// Load conversation messages
function loadConversations() {
    const container = document.getElementById('chat-messages');

    if (conversations.length === 0) {
        return;
    }

    container.innerHTML = '';

    conversations.forEach(msg => {
        if (msg.role === 'system') return;

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${msg.role}`;

        if (msg.role === 'user') {
            messageDiv.innerHTML = `
                <div class="message-bubble">${escapeHtml(msg.content)}</div>
                <div class="message-meta">You</div>
            `;
        } else {
            const parsed = parseAssistantMessage(msg.content);
            messageDiv.innerHTML = renderAssistantBubble(parsed, msg.model || 'kimi', msg.created_at);
        }

        container.appendChild(messageDiv);
    });

    container.scrollTop = container.scrollHeight;
}

// Render tool calls in a message
function renderToolCalls(toolCalls) {
    if (!toolCalls || toolCalls.length === 0) return '';

    let html = '<div class="tool-calls-list">';
    html += '<p style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.25rem;">Tools used:</p>';

    toolCalls.forEach(tc => {
        const toolName = tc.tool || tc.name || 'tool';
        const filename = tc.input?.filename || tc.input?.name || '';
        const action = tc.result?.action || 'executed';
        const success = tc.result?.success !== false;
        const detail = filename ? `${escapeHtml(filename)} → ${escapeHtml(action)}` : escapeHtml(action);

        html += `
            <div class="tool-call-item ${success ? 'success' : ''}">
                <span class="tool-icon">${success ? '✓' : '✗'}</span>
                <span class="tool-name">${escapeHtml(toolName)}</span>
                <span>${detail}</span>
            </div>
        `;
    });

    html += '</div>';
    return html;
}

function renderChangedFiles(changedFiles) {
    if (!changedFiles || changedFiles.length === 0) return '';

    let html = '<div class="tool-calls-list">';
    html += '<p style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.25rem;">What changed:</p>';

    changedFiles.forEach(file => {
        const action = (file.action || 'updated').replace(/_/g, ' ');
        const actionLabel = action.charAt(0).toUpperCase() + action.slice(1);
        html += `
            <div class="tool-call-item success">
                <span class="tool-icon">✓</span>
                <span>${escapeHtml(actionLabel)}</span>
                <span class="tool-name">${escapeHtml(file.filename || 'file')}</span>
            </div>
        `;
    });

    html += '</div>';
    return html;
}

function renderPrimaryFile(primaryFile) {
    if (!primaryFile) return '';

    return `
        <div class="entry-file-card">
            <p class="entry-file-label">Start here:</p>
            <div class="entry-file-chip">${escapeHtml(primaryFile)}</div>
        </div>
    `;
}

function renderAssistantBubble(data, model, timestamp) {
    const explanationHtml = data.explanation ? `<div class="explanation">${formatText(data.explanation)}</div>` : '';
    const changedFilesHtml = renderChangedFiles(data.changedFiles || []);
    const primaryFileHtml = renderPrimaryFile(data.primaryFile);
    const toolCallsHtml = renderToolCalls(data.toolCalls || []);
    const suggestions = data.suggestions || [];

    return `
        <div class="message-bubble">
            ${explanationHtml}
            ${changedFilesHtml}
            ${primaryFileHtml}
            ${toolCallsHtml}
            ${suggestions.length > 0 ? `
                <div class="suggestions">
                    <p><strong>Ideas to try:</strong></p>
                    <ul>${suggestions.map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ul>
                </div>
            ` : ''}
        </div>
        <div class="message-meta">Hari · ${model || 'kimi'} · ${formatTime(timestamp)}</div>
    `;
}

// Send message to AI
async function sendMessage(message) {
    const input = document.getElementById('chat-input');
    const thinking = document.getElementById('thinking-indicator');
    const sendBtn = document.getElementById('send-btn');

    input.value = '';
    thinking.classList.remove('hidden');
    sendBtn.disabled = true;

    // Build message content
    let messageContent = message;
    if (pendingUpload) {
        messageContent = `[Uploaded: ${pendingUpload.name}]\n\n${message}`;
        if (pendingUpload.type === 'text') {
            messageContent += `\n\nFile contents:\n\`\`\`\n${pendingUpload.content}\n\`\`\``;
        } else if (pendingUpload.type === 'image') {
            messageContent += `\n\n[Image attached: ${pendingUpload.name}]`;
        }
        pendingUpload = null;
        document.getElementById('upload-preview').classList.add('hidden');
        document.getElementById('upload-preview').textContent = '';
    }

    const container = document.getElementById('chat-messages');
    const userMsg = document.createElement('div');
    userMsg.className = 'message user';
    userMsg.innerHTML = `
        <div class="message-bubble">${escapeHtml(messageContent)}</div>
        <div class="message-meta">You</div>
    `;
    container.appendChild(userMsg);
    container.scrollTop = container.scrollHeight;

    const welcome = container.querySelector('.chat-welcome');
    if (welcome) welcome.remove();

    try {
        const data = await apiRequest(`/projects/${projectId}/chat`, {
            timeout: 120000,
            method: 'POST',
            body: { 
                message: messageContent, 
                model: 'kimi-k2.5',
                enable_tools: true
            }
        });

        if (data && data.success) {
            const changedFiles = data.response.changed_files || data.response.created_files || [];
            const hasFileChanges = changedFiles.length > 0;
            const hasToolCalls = data.response.tool_calls && data.response.tool_calls.length > 0;

            if (hasFileChanges || hasToolCalls) {
                await refreshFileTree();
            }

            if (data.response.code) {
                currentCode = data.response.code;
                updateCodeDisplay();

                // Only auto-show preview for runnable languages
                if (project.language !== 'python') {
                    // If preview is collapsed on desktop, expand it
                    if (!isMobile && previewCollapsed) {
                        togglePreview();
                    }
                    runPreview();
                }
            } else if (hasFileChanges) {
                // If files were created or updated, run preview
                if (project.language !== 'python') {
                    if (!isMobile && previewCollapsed) {
                        togglePreview();
                    }
                    runPreview();
                }
            }

            const assistantMsg = document.createElement('div');
            assistantMsg.className = 'message assistant';
            assistantMsg.innerHTML = renderAssistantBubble({
                explanation: data.response.explanation,
                suggestions: data.response.suggestions || [],
                toolCalls: data.response.tool_calls || [],
                changedFiles,
                primaryFile: data.response.primary_file || ''
            }, data.response.model || 'kimi', new Date().toISOString());
            container.appendChild(assistantMsg);
            container.scrollTop = container.scrollHeight;
        } else {
            const errorMsg = document.createElement('div');
            errorMsg.className = 'message assistant';
            errorMsg.innerHTML = `
                <div class="message-bubble" style="border-color: #ef4444;">
                    <p>❌ Something went wrong. Please try again.</p>
                    <p style="color: #94a3b8; font-size: 0.875rem;">${escapeHtml(data?.error || 'Unknown error')}</p>
                </div>
            `;
            container.appendChild(errorMsg);
            container.scrollTop = container.scrollHeight;
        }
    } catch (error) {
        console.error('Error in sendMessage:', error);
        const errorMsg = document.createElement('div');
        errorMsg.className = 'message assistant';
        errorMsg.innerHTML = `
            <div class="message-bubble" style="border-color: #ef4444;">
                <p>❌ Network error or unexpected problem.</p>
                <p style="color: #94a3b8; font-size: 0.875rem;">${escapeHtml(error.message || 'Please try again.')}</p>
            </div>
        `;
        container.appendChild(errorMsg);
        container.scrollTop = container.scrollHeight;
    } finally {
        thinking.classList.add('hidden');
        sendBtn.disabled = false;
    }
}

// Refresh file tree after tool calls
async function refreshFileTree() {
    const data = await apiRequest(`/projects/${projectId}`);
    if (data && data.files) {
        projectFiles = data.files;
        loadFileTree();
    }
}

// Handle file upload
function handleFileUpload(file) {
    if (!file) return;
    
    const maxSize = 5 * 1024 * 1024; // 5MB limit
    if (file.size > maxSize) {
        showWorkspaceToast('File too large. Max size is 5MB.', 'error', 4200);
        return;
    }
    
    const preview = document.getElementById('upload-preview');
    
    if (file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = (e) => {
            pendingUpload = {
                name: file.name,
                type: 'image',
                content: e.target.result // base64
            };
            preview.textContent = `📷 ${file.name}`;
            preview.classList.remove('hidden');
        };
        reader.readAsDataURL(file);
    } else if (file.type === 'text/plain' || file.name.match(/\.(js|html|css|txt|json|py)$/)) {
        const reader = new FileReader();
        reader.onload = (e) => {
            pendingUpload = {
                name: file.name,
                type: 'text',
                content: e.target.result
            };
            preview.textContent = `📄 ${file.name}`;
            preview.classList.remove('hidden');
        };
        reader.readAsText(file);
    } else {
        showWorkspaceToast('Unsupported file type. Please upload images, text files, or code files.', 'error', 4200);
    }
}

async function createNewFile() {
    const action = await showFileActionDialog({
        title: 'Create new file',
        message: 'Add a new file to this project. You can start with something like helper.js, styles.css, or level2.html.',
        confirmLabel: 'Create file',
        confirmClass: 'btn-primary',
        initialValue: '',
        inputLabel: 'Filename',
        placeholder: 'helper.js',
        needsInput: true,
        validate: (value) => validateFilenameInput(value)
    });

    if (!action.confirmed) return;

    const filename = action.value;
    const data = await apiRequest(`/projects/${projectId}/files`, {
        method: 'POST',
        body: { filename, content: '' }
    });

    if (!data || !data.success) {
        showWorkspaceToast(data?.error || 'Failed to create file.', 'error');
        return;
    }

    await refreshWorkspaceAfterFileSave();
    await viewFile(data.file.id, data.file.filename);
    setFileModalStatus('New file created. Start typing.', 'info');
}

// Update code display (kept for internal state)
function updateCodeDisplay() {
    // Code display removed from UI, but keep state updated
    // for preview functionality
}

// Run code in preview
async function runPreview() {
    const container = document.getElementById('preview-container');
    
    if (!container) {
        console.error("runPreview: preview-container element not found!");
        return;
    }
    
    const language = (project && project.language) ? project.language : 'p5js';
    
    // Don't try to preview Python in browser
    if (language === 'python') {
        container.innerHTML = '<p class="preview-placeholder">Python code runs on your computer. Copy the code and run it locally with Python installed.</p>';
        return;
    }
    
    sandboxRunner = new SandboxRunner('preview-container');
    
    // Check if this is a multi-file project with index.html
    const hasIndexHtml = projectFiles.some(f => f.filename === 'index.html');
    
    if (hasIndexHtml) {
        // Multi-file project: fetch all files and build preview bundle
        console.log("Multi-file project detected - fetching preview bundle");
        try {
            const response = await apiRequest(`/projects/${projectId}/preview-bundle`);
            if (response && response.success && response.files) {
                const bundledHtml = buildPreviewBundle(response.files);
                sandboxRunner.runHTML(bundledHtml);
                return;
            }
        } catch (e) {
            console.error("Error loading preview bundle:", e);
        }
    }
    
    // Single-file fallback: use currentCode
    if (!currentCode || !currentCode.trim()) {
        container.innerHTML = '<p class="preview-placeholder">Your project preview will appear here.</p>';
        return;
    }
    
    sandboxRunner.run(currentCode, language);
}

// Build preview bundle from project files
function buildPreviewBundle(files) {
    // Get the index.html content
    let indexHtml = files['index.html'] || '';
    
    // Inject CSS files into the head (as inline styles)
    const cssFiles = Object.keys(files).filter(f => f.endsWith('.css'));
    let cssInjection = '';
    cssFiles.forEach(filename => {
        const cssContent = files[filename] || '';
        cssInjection += `\n<style data-file="${filename}">\n${cssContent}\n</style>\n`;
    });
    
    // Inject CSS before </head> or after <head>
    if (indexHtml.includes('</head>')) {
        indexHtml = indexHtml.replace('</head>', `${cssInjection}</head>`);
    } else if (indexHtml.includes('<head>')) {
        indexHtml = indexHtml.replace('<head>', `<head>${cssInjection}`);
    } else if (indexHtml.includes('<html>')) {
        indexHtml = indexHtml.replace('<html>', `<html><head>${cssInjection}</head>`);
    } else {
        indexHtml = `<head>${cssInjection}</head>\n${indexHtml}`;
    }
    
    // Replace script src references with inline content
    const jsFiles = Object.keys(files).filter(f => f.endsWith('.js'));
    
    jsFiles.forEach(filename => {
        const jsContent = files[filename] || '';
        const scriptRegex = new RegExp(`<script[^>]*src=["']${filename}["'][^>]*>\s*</script>`, 'gi');
        const inlineScript = `<script data-file="${filename}">\n${jsContent}\n</script>`;
        indexHtml = indexHtml.replace(scriptRegex, inlineScript);
    });
    
    // Inject any remaining JS files that weren't referenced via src
    let jsInjection = '';
    jsFiles.forEach(filename => {
        if (!indexHtml.includes(`data-file="${filename}"`)) {
            const jsContent = files[filename] || '';
            jsInjection += `\n<script data-file="${filename}">\n${jsContent}\n</script>\n`;
        }
    });
    
    if (indexHtml.includes('</body>')) {
        indexHtml = indexHtml.replace('</body>', `${jsInjection}</body>`);
    } else if (indexHtml.includes('</html>')) {
        indexHtml = indexHtml.replace('</html>', `${jsInjection}</html>`);
    } else {
        indexHtml += jsInjection;
    }
    
    return indexHtml;
}

// Parse assistant message for display
function parseAssistantMessage(content) {
    const result = {
        explanation: '',
        code: '',
        suggestions: [],
        toolCalls: [],
        changedFiles: [],
        primaryFile: ''
    };

    if (!content) {
        return result;
    }

    const normalized = content.replace(/\r\n/g, '\n').trim();
    const headingRegex = /^##\s+(.+)$/gm;
    const matches = [...normalized.matchAll(headingRegex)];

    if (matches.length > 0) {
        result.explanation = normalized.slice(0, matches[0].index).trim();

        const sections = {};
        matches.forEach((match, index) => {
            const sectionName = match[1].trim().toLowerCase();
            const start = match.index + match[0].length;
            const end = index + 1 < matches.length ? matches[index + 1].index : normalized.length;
            sections[sectionName] = normalized.slice(start, end).trim();
        });

        const parseBullets = (sectionText) => {
            if (!sectionText) return [];
            return sectionText
                .split('\n')
                .map(line => line.trim())
                .filter(line => /^[-*•]/.test(line))
                .map(line => line.replace(/^[-*•]\s*/, '').trim())
                .filter(Boolean);
        };

        parseBullets(sections['what changed']).forEach(item => {
            const fileMatch = item.match(/^([A-Za-z ]+?)\s+`([^`]+)`$/);
            if (fileMatch) {
                result.changedFiles.push({
                    action: fileMatch[1].trim().toLowerCase(),
                    filename: fileMatch[2].trim()
                });
            }
        });

        parseBullets(sections['start here']).forEach(item => {
            const entryMatch = item.match(/(?:entry file|start with|main file):\s*`?([^`]+)`?/i)
                || item.match(/`([^`]+)`/);
            if (!result.primaryFile && entryMatch) {
                result.primaryFile = (entryMatch[1] || '').trim();
            }
        });

        parseBullets(sections['tools used']).forEach(item => {
            let toolMatch = item.match(/^`([^`]+)` on `([^`]+)`\s*→\s*(.+)$/);
            if (toolMatch) {
                result.toolCalls.push({
                    tool: toolMatch[1],
                    input: { filename: toolMatch[2] },
                    result: { action: toolMatch[3] }
                });
                return;
            }

            toolMatch = item.match(/^`([^`]+)` on `([^`]+)`$/);
            if (toolMatch) {
                result.toolCalls.push({
                    tool: toolMatch[1],
                    input: { filename: toolMatch[2] },
                    result: { action: 'executed' }
                });
                return;
            }

            const oldStyleMatch = item.match(/^`([^`]+)`:\s*([^→]+)\s*→\s*(.+)$/);
            if (oldStyleMatch) {
                result.toolCalls.push({
                    tool: oldStyleMatch[1],
                    input: { filename: oldStyleMatch[2].trim() },
                    result: { action: oldStyleMatch[3].trim() }
                });
            }
        });

        result.suggestions = parseBullets(sections['next ideas'] || sections['next steps'] || sections['suggestions']);

        return result;
    }

    // Backward-compatible fallback for older stored messages.
    const toolSectionMatch = normalized.match(/---\s*\n\*\*Tool Calls:\*\*\s*\n([\s\S]*?)$/);
    let fallbackContent = normalized;
    if (toolSectionMatch) {
        const toolSection = toolSectionMatch[1];
        const toolLines = toolSection.split('\n').filter(l => l.trim().startsWith('-'));
        toolLines.forEach(line => {
            const match = line.match(/- `([^`]+)`:\s*([^→]+)\s*→\s*(.+)/);
            if (match) {
                result.toolCalls.push({
                    tool: match[1],
                    input: { filename: match[2].trim() },
                    result: { action: match[3].trim() }
                });
            }
        });
        fallbackContent = normalized.substring(0, normalized.indexOf('---\n\n**Tool Calls:**'));
    }

    const codeMatch = fallbackContent.match(/```(?:javascript|js|html|python|py)?\s*\n([\s\S]*?)\n```/);
    if (codeMatch) {
        result.code = codeMatch[1].trim();
    }

    result.explanation = fallbackContent.split(/```/)[0].trim();

    const afterCode = fallbackContent.split(/```/).slice(-1)[0].trim();
    if (afterCode) {
        const lines = afterCode.split('\n').filter(l => l.trim().startsWith('-') || l.trim().startsWith('•'));
        result.suggestions = lines.map(l => l.replace(/^[-•]\s*/, '').trim()).filter(l => l);
    }

    return result;
}

// Escape HTML for display
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Format timestamp
function formatTime(timestamp) {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadProject();
    
    // Initialize responsive state
    handleResize();
    
    // Listen for window resize
    window.addEventListener('resize', handleResize);

    // Sidebar toggle
    document.getElementById('sidebar-toggle').addEventListener('click', toggleSidebar);

    // File search
    document.getElementById('file-search-input').addEventListener('input', (e) => {
        setFileSearchQuery(e.target.value);
    });
    document.getElementById('file-search-input').addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            e.preventDefault();
            setFileSearchQuery('');
            e.target.blur();
        }
    });
    document.getElementById('file-search-clear').addEventListener('click', () => {
        setFileSearchQuery('');
        document.getElementById('file-search-input').focus();
    });

    // Preview toggle (desktop) / close (mobile)
    document.getElementById('preview-toggle').addEventListener('click', togglePreview);

    // Show preview button (mobile only)
    document.getElementById('show-preview-btn').addEventListener('click', () => {
        previewCollapsed = false;
        document.getElementById('preview-pane').classList.add('open');
        document.getElementById('show-preview-btn').classList.add('hidden');
    });

    // Click outside sidebar to close (mobile/tablet overlay)
    document.getElementById('workspace-container').addEventListener('click', (e) => {
        if (e.target === document.getElementById('workspace-container') && 
            document.getElementById('workspace-container').classList.contains('sidebar-open')) {
            toggleSidebar();
        }
    });

    document.addEventListener('click', (e) => {
        if (!e.target.closest('.file-item-actions')) {
            closeAllFileMenus();
        }
    });

    // Send button
    document.getElementById('send-btn').addEventListener('click', () => {
        const input = document.getElementById('chat-input');
        const message = input.value.trim();
        if (message) {
            sendMessage(message);
        }
    });

    // Enter to send (Shift+Enter for new line)
    document.getElementById('chat-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            const message = e.target.value.trim();
            if (message) {
                sendMessage(message);
            }
        }
    });

    // Quick action buttons
    document.querySelectorAll('.quick-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const prompt = btn.dataset.prompt;
            sendMessage(prompt);
        });
    });

    // Run button
    document.getElementById('run-btn').addEventListener('click', runPreview);
    
    // Refresh preview button
    document.getElementById('refresh-preview-btn').addEventListener('click', runPreview);

    // Fullscreen button
    document.getElementById('fullscreen-btn').addEventListener('click', () => {
        const preview = document.getElementById('preview-container');
        if (preview.requestFullscreen) {
            preview.requestFullscreen();
        }
    });

    // Version history button
    document.getElementById('version-history-btn').addEventListener('click', openVersionsModal);

    // Save version button
    document.getElementById('save-version-btn').addEventListener('click', async () => {
        const action = await showFileActionDialog({
            title: 'Save version',
            message: 'Save the current project state so you can restore it later. A short description helps future-you.',
            confirmLabel: 'Save version',
            confirmClass: 'btn-primary',
            initialValue: '',
            inputLabel: 'Version description (optional)',
            placeholder: 'Before adding enemies',
            needsInput: true,
            validate: () => ''
        });
        if (!action.confirmed) return;

        const data = await apiRequest(`/projects/${projectId}/versions`, {
            method: 'POST',
            body: { description: action.value }
        });

        if (data && data.success) {
            if (!document.getElementById('versions-modal').classList.contains('hidden')) {
                await loadVersions();
                setVersionsStatus('Saved a new version.', 'success');
            }
            showWorkspaceToast('Version saved.', 'success');
        } else {
            const errorMessage = data?.error || 'Failed to save version';
            if (!document.getElementById('versions-modal').classList.contains('hidden')) {
                setVersionsStatus(errorMessage, 'error');
            }
            showWorkspaceToast(errorMessage, 'error', 4200);
        }
    });

    // Logout button
    document.getElementById('logout-btn').addEventListener('click', () => {
        logout();
        window.location.href = '/lab/login';
    });

    // File upload
    document.getElementById('chat-upload').addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            handleFileUpload(file);
        }
    });
    
    // File modal controls
    document.getElementById('modal-close').addEventListener('click', async () => await closeFileModal());
    document.getElementById('file-modal-cancel').addEventListener('click', async () => await closeFileModal());
    document.getElementById('file-modal-rename').addEventListener('click', renameCurrentFile);
    document.getElementById('file-modal-delete').addEventListener('click', deleteCurrentFile);
    document.getElementById('file-modal-save').addEventListener('click', saveCurrentFile);
    document.getElementById('modal-file-editor').addEventListener('input', () => {
        setFileModalStatus(isFileModalDirty() ? 'Unsaved changes.' : '', 'info');
        updateFileModalSaveState();
    });
    document.getElementById('modal-file-editor').addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
            e.preventDefault();
            saveCurrentFile();
        }
    });

    document.getElementById('versions-modal-close').addEventListener('click', closeVersionsModal);

    // File action modal controls
    document.getElementById('file-action-close').addEventListener('click', () => closeFileActionDialog());
    document.getElementById('file-action-cancel').addEventListener('click', () => closeFileActionDialog());
    document.getElementById('file-action-confirm').addEventListener('click', submitFileActionDialog);
    document.getElementById('file-action-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            submitFileActionDialog();
        }
    });
    
    // Close modals when clicking outside
    document.getElementById('file-modal').addEventListener('click', async (e) => {
        if (e.target === document.getElementById('file-modal')) {
            await closeFileModal();
        }
    });
    document.getElementById('file-action-modal').addEventListener('click', (e) => {
        if (e.target === document.getElementById('file-action-modal')) {
            closeFileActionDialog();
        }
    });
    document.getElementById('versions-modal').addEventListener('click', (e) => {
        if (e.target === document.getElementById('versions-modal')) {
            closeVersionsModal();
        }
    });

    document.addEventListener('keydown', async (e) => {
        if (e.key === 'Escape') {
            if (!document.getElementById('file-action-modal').classList.contains('hidden')) {
                closeFileActionDialog();
                return;
            }
            if (activeFileMenuId !== null) {
                closeAllFileMenus();
                return;
            }
            if (!document.getElementById('file-modal').classList.contains('hidden')) {
                await closeFileModal();
            }
        }
    });

    updateFileModalSaveState();
    
    // New file button
    document.getElementById('new-file-btn').addEventListener('click', createNewFile);
});
