// workspace-versions.js - Version history helpers extracted from workspace.js

window.__ckclVersions = window.__ckclVersions || [];

function getWorkspaceVersions() {
    return window.__ckclVersions || [];
}

function setWorkspaceVersions(nextVersions) {
    window.__ckclVersions = nextVersions || [];
    return window.__ckclVersions;
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

    const versions = getWorkspaceVersions();
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
            const version = getWorkspaceVersions().find(item => item.id === versionId);
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
        setWorkspaceVersions([]);
        container.innerHTML = '<div class="file-loading">Could not load saved versions.</div>';
        return;
    }

    setWorkspaceVersions(data.versions || []);
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

async function saveProjectVersion() {
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
}
