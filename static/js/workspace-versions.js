// workspace-versions.js - Version history helpers extracted from workspace.js

window.__ckclVersions = window.__ckclVersions || [];

const RECOVERY_VERSION_PREFIX = '__ckcl_recovery__:';

function isRecoveryVersion(versionOrDescription) {
    if (typeof versionOrDescription === 'object' && versionOrDescription) {
        if (versionOrDescription.checkpoint_kind) {
            return versionOrDescription.checkpoint_kind === 'recovery';
        }
        if (versionOrDescription?.is_recovery === true) {
            return true;
        }
    }

    const description = typeof versionOrDescription === 'string'
        ? versionOrDescription
        : versionOrDescription?.description;
    return (description || '').startsWith(RECOVERY_VERSION_PREFIX);
}

function getRecoveryVersionReason(versionOrDescription) {
    if (typeof versionOrDescription === 'object' && versionOrDescription) {
        if (versionOrDescription.checkpoint_detail) {
            return versionOrDescription.checkpoint_detail;
        }
        if (versionOrDescription.recovery_reason) {
            return versionOrDescription.recovery_reason;
        }
    }

    const description = typeof versionOrDescription === 'string'
        ? versionOrDescription
        : versionOrDescription?.description;

    if (!isRecoveryVersion(description)) {
        return '';
    }

    return (description || '').slice(RECOVERY_VERSION_PREFIX.length).trim() || 'Saved automatically to protect your work.';
}

function getWorkspaceVersions() {
    return window.__ckclVersions || [];
}

function getVisibleWorkspaceVersions() {
    return getWorkspaceVersions();
}

function getManualWorkspaceVersions() {
    return getWorkspaceVersions().filter(version => !isRecoveryVersion(version));
}

function getRecoveryWorkspaceVersions() {
    return getWorkspaceVersions().filter(version => isRecoveryVersion(version));
}

function setWorkspaceVersions(nextVersions) {
    window.__ckclVersions = nextVersions || [];
    return window.__ckclVersions;
}

function getCurrentSavedVersion() {
    return getManualWorkspaceVersions().find(version => version.matches_live_state) || null;
}

function getCurrentRecoveryVersion() {
    return getRecoveryWorkspaceVersions().find(version => version.matches_live_state) || null;
}

function getCurrentVersionMatch() {
    return getWorkspaceVersions().find(version => version.matches_live_state) || null;
}

function hasAnyRunnableProjectState() {
    return Boolean((currentCode || '').trim()) || (Array.isArray(projectFiles) && projectFiles.length > 0);
}

function getDirtyVersioningFile() {
    if (typeof isFileModalDirty !== 'function' || !isFileModalDirty()) {
        return null;
    }

    if (typeof getCurrentFileRecord === 'function') {
        return getCurrentFileRecord();
    }

    return null;
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

function formatRelativeVersionTime(timestamp) {
    if (!timestamp) return 'Unknown age';

    const date = new Date(timestamp.replace(' ', 'T'));
    if (Number.isNaN(date.getTime())) {
        return 'Unknown age';
    }

    const diffMs = Date.now() - date.getTime();
    const diffMinutes = Math.max(0, Math.round(diffMs / 60000));

    if (diffMinutes < 1) return 'Just now';
    if (diffMinutes < 60) return `${diffMinutes}m ago`;

    const diffHours = Math.round(diffMinutes / 60);
    if (diffHours < 24) return `${diffHours}h ago`;

    const diffDays = Math.round(diffHours / 24);
    if (diffDays < 7) return `${diffDays}d ago`;

    return formatVersionTimestamp(timestamp);
}

function formatVersionSize(size) {
    const bytes = Number(size || 0);
    if (!bytes) return 'No code';
    if (bytes < 1024) return `${bytes} chars`;
    return `${(bytes / 1024).toFixed(bytes >= 10 * 1024 ? 0 : 1)} KB`;
}

function formatFileCount(version) {
    const count = Number(version.file_count || 0);
    if (count === 1) return '1 file';
    return `${count} files`;
}

function getVersionDescription(version) {
    const displayDescription = (version?.display_description || '').trim();
    if (displayDescription) {
        return displayDescription;
    }

    if (isRecoveryVersion(version)) {
        return 'Automatic checkpoint';
    }

    const description = (version.description || '').trim();
    return description || 'Manual save';
}

function getVersionDetail(version) {
    if (!isRecoveryVersion(version)) {
        return '';
    }

    return getRecoveryVersionReason(version);
}

function getVersionTypeLabel(version) {
    return isRecoveryVersion(version) ? 'Automatic checkpoint' : 'Manual save';
}

function bindVersionsSummaryFocusButton() {
    const focusBtn = document.getElementById('versions-summary-focus-file');
    if (!focusBtn) return;

    focusBtn.addEventListener('click', () => {
        closeVersionsModal();
        const editor = document.getElementById('modal-file-editor');
        if (editor) editor.focus();
    });
}

function bindVersionsSummarySaveButton(options = {}) {
    const saveBtn = document.getElementById('versions-summary-save-current');
    if (!saveBtn) return;

    saveBtn.addEventListener('click', async () => {
        await saveProjectVersion({
            initialValue: options.initialValue || 'Before restoring older work',
            message: options.message || 'Save the current project state first so you can safely jump back after restoring an older version.'
        });
    });
}

function renderVersionsSummary() {
    const container = document.getElementById('versions-summary');
    if (!container) return;

    const dirtyFile = getDirtyVersioningFile();
    const currentSavedVersion = getCurrentSavedVersion();
    const currentRecoveryVersion = getCurrentRecoveryVersion();
    const manualVersions = getManualWorkspaceVersions();
    const recoveryVersions = getRecoveryWorkspaceVersions();
    const hasProjectState = hasAnyRunnableProjectState();

    if (dirtyFile) {
        container.className = 'versions-summary warning';
        container.innerHTML = `
            <div class="versions-summary-copy">
                <strong>${escapeHtml(dirtyFile.filename)}</strong> has unsaved edits.
                <span>Save that file first so any version you save or restore reflects your latest work.</span>
            </div>
            <button id="versions-summary-focus-file" class="btn-small" type="button">Back to file</button>
        `;
        bindVersionsSummaryFocusButton();
        return;
    }

    if (currentSavedVersion) {
        container.className = 'versions-summary success';
        container.innerHTML = `
            <div class="versions-summary-copy">
                <strong>Current project is already saved.</strong>
                <span>It matches <strong>${escapeHtml(getVersionDescription(currentSavedVersion))}</strong> from ${escapeHtml(formatVersionTimestamp(currentSavedVersion.created_at))}.</span>
            </div>
        `;
        return;
    }

    if (currentRecoveryVersion) {
        container.className = 'versions-summary info';
        container.innerHTML = `
            <div class="versions-summary-copy">
                <strong>Current project matches an automatic recovery checkpoint.</strong>
                <span>You're protected by <strong>${escapeHtml(getVersionDescription(currentRecoveryVersion))}</strong> from ${escapeHtml(formatVersionTimestamp(currentRecoveryVersion.created_at))}. Save a manual version too if this is a milestone you want to keep on purpose.</span>
            </div>
            <button id="versions-summary-save-current" class="btn-small" type="button">Save current state</button>
        `;
        bindVersionsSummarySaveButton({
            initialValue: 'Named save after recovery checkpoint',
            message: 'Automatic recovery checkpoints help in a pinch, but a named save point is better when you want to keep this moment on purpose.'
        });
        return;
    }

    if (manualVersions.length === 0 && recoveryVersions.length > 0) {
        container.className = 'versions-summary info';
        container.innerHTML = `
            <div class="versions-summary-copy">
                <strong>No manual save points yet.</strong>
                <span>Automatic recovery checkpoints are available below, so you still have a safety net. Save a named version when you want a milestone that's easier to recognize later.</span>
            </div>
            <button id="versions-summary-save-current" class="btn-small" type="button">Save current state</button>
        `;
        bindVersionsSummarySaveButton({
            initialValue: 'Named save after recovery checkpoint',
            message: 'You already have automatic recovery checkpoints below. Create a manual save too if you want an easy-to-find milestone with your own label.'
        });
        return;
    }

    if (hasProjectState) {
        container.className = 'versions-summary warning';
        container.innerHTML = `
            <div class="versions-summary-copy">
                <strong>Current project is not saved in version history yet.</strong>
                <span>Save now before restoring an older version or deleting files you might want back.</span>
            </div>
            <button id="versions-summary-save-current" class="btn-small" type="button">Save current state</button>
        `;

        bindVersionsSummarySaveButton();
        return;
    }

    container.className = 'versions-summary info';
    container.innerHTML = `
        <div class="versions-summary-copy">
            <strong>No code is loaded right now.</strong>
            <span>When you save versions, they will show up here with restore details.</span>
        </div>
    `;
}

function renderVersionItem(version, { latestLabel = '' } = {}) {
    const hasSnapshot = Number(version.has_files_snapshot) === 1;
    const isCurrent = Boolean(version.matches_live_state);
    const description = getVersionDescription(version);
    const detail = getVersionDetail(version);
    const badges = [
        getVersionTypeLabel(version),
        hasSnapshot ? 'Multi-file snapshot' : 'Single-file save',
        formatFileCount(version),
        formatVersionSize(version.code_size),
    ];

    if (version.entry_filename) {
        badges.push(version.entry_filename);
    }

    const statusBadges = [
        isCurrent ? '<span class="version-chip current">Current project</span>' : '',
        latestLabel ? `<span class="version-chip neutral">${escapeHtml(latestLabel)}</span>` : '',
    ].filter(Boolean).join('');

    return `
        <div class="version-item${isCurrent ? ' is-current' : ''}">
            <div class="version-item-main">
                <div class="version-item-top">
                    <div class="version-title-wrap">
                        <strong>${escapeHtml(description)}</strong>
                        ${detail ? `<div class="version-detail">${escapeHtml(detail)}</div>` : ''}
                        <div class="version-state-badges">${statusBadges}</div>
                    </div>
                    <div class="version-date-wrap">
                        <span class="version-date-relative">${escapeHtml(formatRelativeVersionTime(version.created_at))}</span>
                        <span class="version-date">${escapeHtml(formatVersionTimestamp(version.created_at))}</span>
                    </div>
                </div>
                <div class="version-meta">
                    ${badges.map(badge => `<span class="version-chip">${escapeHtml(badge)}</span>`).join('')}
                </div>
            </div>
            <button class="btn-small restore-version-btn" data-version-id="${version.id}">${isCurrent ? 'Restore again' : 'Restore'}</button>
        </div>
    `;
}

function renderVersionsSection(title, subtitle, versions, { latestLabel = '', emptyMessage = '' } = {}) {
    return `
        <div class="versions-section">
            <div class="versions-section-header">
                <div>
                    <h4>${escapeHtml(title)}</h4>
                    <p>${escapeHtml(subtitle)}</p>
                </div>
                <span class="version-chip">${versions.length}</span>
            </div>
            <div class="versions-section-list">
                ${versions.length > 0
                    ? versions.map((version, index) => renderVersionItem(version, {
                        latestLabel: index === 0 ? latestLabel : ''
                    })).join('')
                    : `<div class="file-loading">${escapeHtml(emptyMessage)}</div>`}
            </div>
        </div>
    `;
}

function renderVersionsList() {
    const container = document.getElementById('versions-list');
    if (!container) return;

    renderVersionsSummary();

    const versions = getWorkspaceVersions();
    if (versions.length === 0) {
        container.innerHTML = '<div class="file-loading">No saved versions or recovery checkpoints yet.</div>';
        return;
    }

    const manualVersions = getManualWorkspaceVersions();
    const recoveryVersions = getRecoveryWorkspaceVersions();

    container.innerHTML = [
        renderVersionsSection(
            'Save points',
            'Named milestones you created on purpose.',
            manualVersions,
            {
                latestLabel: 'Latest save',
                emptyMessage: 'No manual save points yet.'
            }
        ),
        renderVersionsSection(
            'Recovery checkpoints',
            'Safety nets the system created before risky changes or after AI updates.',
            recoveryVersions,
            {
                latestLabel: 'Latest recovery',
                emptyMessage: 'No recovery checkpoints yet.'
            }
        )
    ].join('');

    container.querySelectorAll('.restore-version-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const versionId = Number(btn.dataset.versionId);
            const version = getWorkspaceVersions().find(item => item.id === versionId);
            await restoreVersion(version, btn);
        });
    });
}

async function createRecoveryVersion(reason = 'Before risky workspace action') {
    const description = `${RECOVERY_VERSION_PREFIX}${reason}`;
    const data = await apiRequest(`/projects/${projectId}/versions`, {
        method: 'POST',
        body: { description }
    });

    if (!data || !data.success) {
        return {
            success: false,
            error: data?.error || 'Failed to save a recovery point.'
        };
    }

    return {
        success: true,
        versionId: data.version_id,
    };
}

async function undoWorkspaceRecovery(versionId, label = 'your previous project state') {
    if (!versionId) {
        showWorkspaceToast('No recovery point is available for that undo.', 'error', 4200);
        return;
    }

    const data = await apiRequest(`/projects/${projectId}/versions/${versionId}/restore`, {
        method: 'POST'
    });

    if (!data || !data.success) {
        showWorkspaceToast(data?.error || 'Failed to undo that change.', 'error', 4200);
        return;
    }

    await closeFileModal(true);
    suppressAssistantChangeBadgesForNextConversationRender();
    await loadProject();
    await loadVersions();
    showWorkspaceToast(`Restored ${label}.`, 'success');
}

async function loadVersions() {
    const container = document.getElementById('versions-list');
    if (!container) return;

    const summary = document.getElementById('versions-summary');
    if (summary) {
        summary.className = 'versions-summary info';
        summary.innerHTML = '<div class="versions-summary-copy"><strong>Loading saved versions...</strong></div>';
    }
    container.innerHTML = '<div class="file-loading">Loading versions...</div>';

    const data = await apiRequest(`/projects/${projectId}/versions`);
    if (!data || !data.success) {
        setWorkspaceVersions([]);
        renderVersionsSummary();
        container.innerHTML = '<div class="file-loading">Could not load saved versions.</div>';
        return;
    }

    setWorkspaceVersions(data.versions || []);
    renderVersionsList();

    if (data.created_baseline_recovery) {
        setVersionsStatus('Added an automatic checkpoint so this older project has a safe place to come back to.', 'info');
    }
}

async function restoreVersion(version, buttonEl) {
    if (!version) return;

    const dirtyFile = getDirtyVersioningFile();
    if (dirtyFile) {
        const message = `Save ${dirtyFile.filename} before restoring an older version so you do not lose those edits.`;
        setVersionsStatus(message, 'error');
        showWorkspaceToast(message, 'error', 4200);
        renderVersionsSummary();
        return;
    }

    const description = getVersionDescription(version);
    const versionLabel = isRecoveryVersion(version) ? 'recovery checkpoint' : 'saved version';
    const currentSavedVersion = getCurrentSavedVersion();
    const currentVersionMatch = getCurrentVersionMatch();
    const needsSaveCue = !currentSavedVersion && currentVersionMatch !== version && !version.matches_live_state && hasAnyRunnableProjectState();
    const detailParts = [
        getVersionTypeLabel(version),
        formatFileCount(version),
        version.entry_filename || 'Unknown entry file',
        Number(version.has_files_snapshot) === 1 ? 'multi-file snapshot' : 'single-file save'
    ];
    const warning = needsSaveCue
        ? 'Tip: your current project is not saved as a named save point yet. Save it first if you might want to come back.'
        : '';

    const action = await showFileActionDialog({
        title: isRecoveryVersion(version) ? 'Restore recovery checkpoint' : 'Restore saved version',
        message: `Restore "${description}" from ${formatVersionTimestamp(version.created_at)}? This will replace the project's current files with that ${versionLabel}. (${detailParts.join(' • ')})${warning ? ` ${warning}` : ''}`,
        confirmLabel: needsSaveCue ? 'Restore without saving' : 'Restore version',
        confirmClass: 'btn-primary',
        needsInput: false
    });
    if (!action.confirmed) return;

    const originalLabel = buttonEl ? buttonEl.textContent : '';
    if (buttonEl) {
        buttonEl.disabled = true;
        buttonEl.textContent = 'Restoring...';
    }

    setVersionsStatus('Saving a recovery point...', 'info');

    let recoveryVersionId = null;

    try {
        if (!version.matches_live_state && hasAnyRunnableProjectState()) {
            const recovery = await createRecoveryVersion(`Before restoring ${description}`);
            if (!recovery.success) {
                const isNoCodeProject = (recovery.error || '').toLowerCase().includes('no code to save');
                if (!isNoCodeProject) {
                    const message = `Couldn't create a safety net, so the restore was canceled. ${recovery.error}`;
                    setVersionsStatus(message, 'error');
                    showWorkspaceToast(message, 'error', 5200);
                    return;
                }
            } else {
                recoveryVersionId = recovery.versionId;
            }
        }

        setVersionsStatus('Restoring version...', 'info');

        const data = await apiRequest(`/projects/${projectId}/versions/${version.id}/restore`, {
            method: 'POST'
        });

        if (!data || !data.success) {
            setVersionsStatus(data?.error || 'Failed to restore that version.', 'error');
            return;
        }

        await closeFileModal(true);
        suppressAssistantChangeBadgesForNextConversationRender();
        await loadProject();
        await loadVersions();
        setVersionsStatus(`Restored "${description}".`, 'success');

        if (recoveryVersionId) {
            showWorkspaceToast(`Restored "${description}".`, 'success', 9000, {
                actionLabel: 'Undo',
                closeOnAction: false,
                onAction: async () => {
                    await undoWorkspaceRecovery(recoveryVersionId, 'the project from right before restore');
                }
            });
        } else {
            showWorkspaceToast(`Restored "${description}".`, 'success');
        }
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

async function saveProjectVersion(options = {}) {
    const dirtyFile = getDirtyVersioningFile();
    if (dirtyFile) {
        const message = `Save ${dirtyFile.filename} before creating a version so the snapshot includes your latest edits.`;
        if (!document.getElementById('versions-modal').classList.contains('hidden')) {
            setVersionsStatus(message, 'error');
            renderVersionsSummary();
        }
        showWorkspaceToast(message, 'error', 4200);
        return;
    }

    const action = await showFileActionDialog({
        title: options.title || 'Save version',
        message: options.message || 'Save the current project state so you can restore it later. A short description helps future-you.',
        confirmLabel: options.confirmLabel || 'Save version',
        confirmClass: 'btn-primary',
        initialValue: options.initialValue || '',
        inputLabel: 'Version description (optional)',
        placeholder: options.placeholder || 'Before adding enemies',
        needsInput: true,
        validate: () => ''
    });
    if (!action.confirmed) return;

    let data;
    try {
        data = await apiRequest(`/projects/${projectId}/versions`, {
            method: 'POST',
            body: { description: action.value }
        });
    } catch (error) {
        const errorMessage = error.message || 'Failed to save version. Please try again.';
        if (!document.getElementById('versions-modal').classList.contains('hidden')) {
            setVersionsStatus(errorMessage, 'error');
        }
        showWorkspaceToast(errorMessage, 'error', 4200);
        return;
    }

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
