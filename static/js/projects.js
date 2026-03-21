// projects.js - Project gallery + teacher/admin oversight tools

if (!isLoggedIn()) {
    window.location.href = '/lab/login';
}

let projects = [];
let projectSummary = {};
let selectedLanguage = 'p5js';
let currentScope = 'mine';
let projectActionState = null;

const RECENT_PROJECTS_KEY = 'ckcl-recent-projects';
const RECENT_PROJECT_LIMIT = 12;
const RECENT_ACTIVITY_WINDOW_MS = 1000 * 60 * 60 * 24 * 7;

const STARTER_PRESETS = {
    p5js: {
        icon: '🎮',
        language: 'p5js',
        title: 'Make a game',
        name: 'Color Splash Game',
        description: 'A playful sketch where moving the mouse creates colorful shapes and surprises.'
    },
    html: {
        icon: '🌐',
        language: 'html',
        title: 'Build a web page',
        name: 'My Awesome Web Page',
        description: 'A bright page with a button, a message, and room for your own style.'
    },
    python: {
        icon: '🐍',
        language: 'python',
        title: 'Start a Python story',
        name: 'Hero Story Generator',
        description: 'A simple Python script that prints a tiny story you can remix with your own ideas.'
    }
};

const STARTER_PREVIEW = {
    p5js: {
        title: 'p5.js starter ready',
        file: 'sketch.js',
        message: 'You will land in a runnable drawing sketch so you can tweak colors, text, and shapes right away.',
        steps: [
            'Run the sketch and move the mouse.',
            'Change one color, number, or message.',
            'Add your own rule for clicks or key presses.'
        ]
    },
    html: {
        title: 'HTML starter ready',
        file: 'index.html',
        message: 'You will start with a real web page that already has a button and a little bit of style.',
        steps: [
            'Open the preview and click the button.',
            'Rewrite the title or message.',
            'Add a new section, image, or color theme.'
        ]
    },
    python: {
        title: 'Python starter ready',
        file: 'main.py',
        message: 'You will get a friendly script with printed output so you can begin changing the story immediately.',
        steps: [
            'Run the program once.',
            'Rename the hero or mission.',
            'Add one more print() line with your own idea.'
        ]
    }
};

const user = getCurrentUser() || {};
const isAdmin = user.role === 'admin';
if (isAdmin) {
    currentScope = 'all';
    const adminLink = document.getElementById('admin-link');
    if (adminLink) adminLink.classList.remove('hidden');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

function getLanguageIcon(lang) {
    return {
        p5js: '🎨',
        html: '🌐',
        python: '🐍',
        undecided: '💡'
    }[lang] || '💡';
}

function getLanguageBadgeClass(lang) {
    return {
        p5js: 'p5js',
        html: 'html',
        python: 'python',
        undecided: 'undecided'
    }[lang] || 'undecided';
}

function getLanguageLabel(lang) {
    return {
        p5js: 'p5.js',
        html: 'HTML/CSS/JS',
        python: 'Python',
        undecided: 'Starter project'
    }[lang] || 'Starter project';
}

function parseDate(value) {
    if (!value) return null;
    const parsed = new Date(String(value).replace(' ', 'T'));
    return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function getTimeAgo(dateString) {
    const date = parseDate(dateString);
    if (!date) return 'unknown time';

    const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
    const intervals = {
        year: 31536000,
        month: 2592000,
        week: 604800,
        day: 86400,
        hour: 3600,
        minute: 60
    };

    for (const [unit, secondsInUnit] of Object.entries(intervals)) {
        const interval = Math.floor(seconds / secondsInUnit);
        if (interval >= 1) {
            return interval === 1 ? `1 ${unit} ago` : `${interval} ${unit}s ago`;
        }
    }

    return 'just now';
}

function formatAbsoluteDate(dateString) {
    const date = parseDate(dateString);
    if (!date) return 'Unknown time';

    return date.toLocaleString([], {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit'
    });
}

function getRecentProjectIds() {
    try {
        const parsed = JSON.parse(localStorage.getItem(RECENT_PROJECTS_KEY) || '[]');
        return Array.isArray(parsed) ? parsed.map((value) => Number(value)).filter(Boolean) : [];
    } catch (error) {
        return [];
    }
}

function rememberRecentProject(projectId) {
    const id = Number(projectId);
    if (!id) return;

    const recent = getRecentProjectIds().filter((value) => value !== id);
    recent.unshift(id);
    localStorage.setItem(RECENT_PROJECTS_KEY, JSON.stringify(recent.slice(0, RECENT_PROJECT_LIMIT)));
}

function projectMatchesRecentActivity(project) {
    const latest = parseDate(project.latest_activity_at || project.updated_at);
    if (!latest) return false;
    return (Date.now() - latest.getTime()) <= RECENT_ACTIVITY_WINDOW_MS;
}

function getRecentProjectRank(projectId) {
    const recent = getRecentProjectIds();
    const rank = recent.indexOf(Number(projectId));
    return rank === -1 ? Number.POSITIVE_INFINITY : rank;
}

function isRecentlyOpened(projectId) {
    return getRecentProjectRank(projectId) !== Number.POSITIVE_INFINITY;
}

function getProjectOpenUrl(projectId, options = {}) {
    const url = new URL(`/lab/project/${projectId}`, window.location.origin);
    if (options.modal) {
        url.searchParams.set('modal', options.modal);
    }
    return `${url.pathname}${url.search}`;
}

function openProject(projectId, options = {}) {
    rememberRecentProject(projectId);
    window.location.href = getProjectOpenUrl(projectId, options);
}

function setSelectedLanguage(language) {
    selectedLanguage = language || 'p5js';
    document.querySelectorAll('.lang-option').forEach((button) => {
        button.classList.toggle('active', button.dataset.lang === selectedLanguage);
    });
    renderStarterPreview();
}

function renderStarterPreview() {
    const preview = STARTER_PREVIEW[selectedLanguage] || STARTER_PREVIEW.p5js;
    const container = document.getElementById('starter-preview');

    if (!container) return;

    container.innerHTML = `
        <h3>${preview.title}</h3>
        <p>${preview.message}</p>
        <span class="starter-chip">Starter file: ${preview.file}</span>
        <ul>
            ${preview.steps.map((step) => `<li>${escapeHtml(step)}</li>`).join('')}
        </ul>
    `;
}

function applyStarterPreset(presetKey, overwriteText = true) {
    const preset = STARTER_PRESETS[presetKey];
    if (!preset) return;

    const nameInput = document.getElementById('project-name');
    const descInput = document.getElementById('project-desc');

    setSelectedLanguage(preset.language);

    if (overwriteText || !nameInput.value.trim()) {
        nameInput.value = preset.name;
    }

    if (overwriteText || !descInput.value.trim()) {
        descInput.value = preset.description;
    }
}

function openNewProjectModal(presetKey = null) {
    const modal = document.getElementById('new-project-modal');
    if (!modal) return;

    modal.classList.remove('hidden');
    const errorDiv = document.getElementById('project-error');
    errorDiv.classList.remove('show');
    errorDiv.textContent = '';

    const createBtn = document.getElementById('create-project');
    createBtn.disabled = false;
    createBtn.textContent = 'Start Building';

    if (presetKey) {
        applyStarterPreset(presetKey, true);
    } else {
        renderStarterPreview();
    }

    const nameInput = document.getElementById('project-name');
    nameInput.focus();
    nameInput.select();
}

function closeNewProjectModal(resetText = true) {
    const modal = document.getElementById('new-project-modal');
    if (!modal) return;

    modal.classList.add('hidden');
    const errorDiv = document.getElementById('project-error');
    errorDiv.classList.remove('show');
    errorDiv.textContent = '';

    if (resetText) {
        document.getElementById('project-name').value = '';
        document.getElementById('project-desc').value = '';
    }

    setSelectedLanguage('p5js');
}

function showBanner(message, type = 'info') {
    const banner = document.getElementById('projects-banner');
    if (!banner) return;

    if (!message) {
        banner.textContent = '';
        banner.className = 'projects-banner';
        return;
    }

    banner.textContent = message;
    banner.className = `projects-banner show ${type}`;
}

function renderProjectsError(container, message = 'Could not load your projects right now.') {
    container.innerHTML = `
        <section class="empty-state">
            <div class="empty-state-icon">⚠️</div>
            <h3>We couldn't load your projects</h3>
            <p>${escapeHtml(message)}</p>
            <div class="project-actions-primary" style="justify-content:center; margin-top: 1.25rem;">
                <button id="retry-projects-load" class="btn-gradient" type="button">Try again</button>
                <button id="projects-open-new" class="btn-secondary" type="button">Start a new project instead</button>
            </div>
        </section>
    `;

    const retryButton = document.getElementById('retry-projects-load');
    if (retryButton) {
        retryButton.addEventListener('click', () => loadProjects());
    }

    const newProjectButton = document.getElementById('projects-open-new');
    if (newProjectButton) {
        newProjectButton.addEventListener('click', () => openNewProjectModal());
    }
}

function renderEmptyState(container) {
    const starterCards = Object.entries(STARTER_PRESETS).map(([key, preset]) => `
        <button class="starter-card" type="button" data-starter="${key}">
            <span class="starter-card-icon">${preset.icon}</span>
            <h4>${preset.title}</h4>
            <p>${preset.description}</p>
            <small>Starts with ${STARTER_PREVIEW[preset.language].file}</small>
        </button>
    `).join('');

    container.innerHTML = `
        <section class="empty-state">
            <div class="empty-state-icon">🚀</div>
            <h3>Start your first project</h3>
            <p>Pick a starter below, open it, and make one tiny change right away.</p>
            <div class="quick-start-grid">
                ${starterCards}
            </div>
            <div class="project-actions-primary" style="justify-content:center;">
                <button id="empty-state-new-project" class="btn-gradient" type="button">+ Start from my own idea</button>
                <button id="empty-state-try-game" class="btn-secondary" type="button">Use the game starter</button>
            </div>
        </section>
    `;

    container.querySelectorAll('[data-starter]').forEach((button) => {
        button.addEventListener('click', () => openNewProjectModal(button.dataset.starter));
    });

    const ownIdeaButton = document.getElementById('empty-state-new-project');
    if (ownIdeaButton) {
        ownIdeaButton.addEventListener('click', () => openNewProjectModal());
    }

    const gameButton = document.getElementById('empty-state-try-game');
    if (gameButton) {
        gameButton.addEventListener('click', () => openNewProjectModal('p5js'));
    }
}

function renderSummaryCards(filteredProjects) {
    const summaryContainer = document.getElementById('oversight-summary');
    if (!summaryContainer) return;

    const allProjects = projects || [];
    const allActive = allProjects.filter((project) => !project.is_archived);
    const visible = filteredProjects || [];
    const recentlyOpened = allProjects.filter((project) => isRecentlyOpened(project.id));
    const needsAttention = allProjects.filter((project) => project.needs_attention);

    summaryContainer.innerHTML = `
        <article class="summary-card">
            <span class="summary-label">Visible now</span>
            <strong class="summary-value">${visible.length}</strong>
            <span class="summary-note">${allProjects.length} total loaded in this scope</span>
        </article>
        <article class="summary-card">
            <span class="summary-label">Active projects</span>
            <strong class="summary-value">${allActive.length}</strong>
            <span class="summary-note">${projectSummary.archived_projects || 0} archived and safely out of the way</span>
        </article>
        <article class="summary-card">
            <span class="summary-label">Needs attention</span>
            <strong class="summary-value">${needsAttention.length}</strong>
            <span class="summary-note">Stale projects without backup checkpoints or runnable code</span>
        </article>
        <article class="summary-card">
            <span class="summary-label">Recently opened</span>
            <strong class="summary-value">${recentlyOpened.length}</strong>
            <span class="summary-note">Local shortcuts for getting back to what mattered last</span>
        </article>
    `;
}

function getOwnerOptions() {
    const owners = Array.from(new Set((projects || []).map((project) => project.owner_username).filter(Boolean))).sort();
    return ['all', ...owners];
}

function syncOwnerFilterOptions() {
    const ownerFilter = document.getElementById('owner-filter');
    if (!ownerFilter) return;

    const currentValue = ownerFilter.value || 'all';
    ownerFilter.innerHTML = getOwnerOptions().map((owner) => {
        if (owner === 'all') {
            return '<option value="all">All owners</option>';
        }
        return `<option value="${escapeHtml(owner)}">${escapeHtml(owner)}</option>`;
    }).join('');

    ownerFilter.value = getOwnerOptions().includes(currentValue) ? currentValue : 'all';
}

function getProjectSearchText(project) {
    const reviewText = (project.latest_review?.items || []).map((item) => `${item.filename} ${item.summary}`).join(' ');
    return [
        project.name,
        project.description,
        project.owner_username,
        getLanguageLabel(project.language),
        project.latest_user_message_preview,
        project.latest_assistant_preview,
        project.latest_review?.headline,
        reviewText,
        (project.attention_reasons || []).join(' ')
    ].join(' ').toLowerCase();
}

function getQuickFilterValue() {
    const activeChip = document.querySelector('.quick-filter-chip.active');
    return activeChip ? activeChip.dataset.quickFilter : 'all';
}

function getFilteredProjects() {
    const searchQuery = (document.getElementById('project-search')?.value || '').trim().toLowerCase();
    const ownerFilter = document.getElementById('owner-filter')?.value || 'all';
    const languageFilter = document.getElementById('language-filter')?.value || 'all';
    const statusFilter = document.getElementById('status-filter')?.value || 'active';
    const quickFilter = getQuickFilterValue();
    const sortFilter = document.getElementById('sort-filter')?.value || 'recent-activity';
    const recentProjectIds = getRecentProjectIds();

    let filtered = [...projects];

    if (statusFilter === 'active') {
        filtered = filtered.filter((project) => !project.is_archived);
    } else if (statusFilter === 'attention') {
        filtered = filtered.filter((project) => project.needs_attention && !project.is_archived);
    } else if (statusFilter === 'archived') {
        filtered = filtered.filter((project) => project.is_archived);
    }

    if (ownerFilter !== 'all') {
        filtered = filtered.filter((project) => project.owner_username === ownerFilter);
    }

    if (languageFilter !== 'all') {
        filtered = filtered.filter((project) => project.language === languageFilter);
    }

    if (searchQuery) {
        filtered = filtered.filter((project) => getProjectSearchText(project).includes(searchQuery));
    }

    if (quickFilter === 'recent-opened') {
        filtered = filtered.filter((project) => recentProjectIds.includes(Number(project.id)));
    } else if (quickFilter === 'recent-activity') {
        filtered = filtered.filter((project) => projectMatchesRecentActivity(project));
    } else if (quickFilter === 'needs-attention') {
        filtered = filtered.filter((project) => project.needs_attention && !project.is_archived);
    } else if (quickFilter === 'no-save') {
        filtered = filtered.filter((project) => Number(project.version_count || 0) === 0 && !project.is_archived);
    } else if (quickFilter === 'archived') {
        filtered = filtered.filter((project) => project.is_archived);
    }

    filtered.sort((a, b) => {
        if (sortFilter === 'recent-opened') {
            return getRecentProjectRank(a.id) - getRecentProjectRank(b.id)
                || String(a.name || '').localeCompare(String(b.name || ''));
        }

        if (sortFilter === 'needs-attention') {
            return Number(Boolean(b.needs_attention)) - Number(Boolean(a.needs_attention))
                || String(b.latest_activity_at || '').localeCompare(String(a.latest_activity_at || ''));
        }

        if (sortFilter === 'most-files') {
            return Number(b.file_count || 0) - Number(a.file_count || 0)
                || String(b.latest_activity_at || '').localeCompare(String(a.latest_activity_at || ''));
        }

        if (sortFilter === 'most-versions') {
            return Number(b.version_count || 0) - Number(a.version_count || 0)
                || String(b.latest_activity_at || '').localeCompare(String(a.latest_activity_at || ''));
        }

        if (sortFilter === 'name') {
            return String(a.name || '').localeCompare(String(b.name || ''));
        }

        return String(b.latest_activity_at || '').localeCompare(String(a.latest_activity_at || ''));
    });

    return filtered;
}

function buildProjectCard(project) {
    const langClass = getLanguageBadgeClass(project.language);
    const langIcon = getLanguageIcon(project.language);
    const statusBadge = project.is_archived
        ? '<span class="status-badge archived">Archived</span>'
        : project.needs_attention
            ? '<span class="status-badge attention">Needs attention</span>'
            : '<span class="status-badge active">Ready</span>';
    const recentActivityBadge = projectMatchesRecentActivity(project)
        ? '<span class="status-badge recent">Recent activity</span>'
        : '';
    const ownerLine = isAdmin ? `<div class="project-owner">Owner: <strong>${escapeHtml(project.owner_username || 'unknown')}</strong></div>` : '';
    const description = escapeHtml(project.description || 'No description yet.');
    const latestPrompt = project.latest_user_message_preview
        ? `
            <div class="project-activity-line">
                <strong>Latest prompt</strong>
                <span>${escapeHtml(project.latest_user_message_preview)}</span>
            </div>
        `
        : '';
    const latestReview = project.latest_review?.headline
        ? `
            <div class="project-activity-line">
                <strong>Latest review</strong>
                <span>${escapeHtml(project.latest_review.headline)}</span>
            </div>
        `
        : '';
    const attentionList = (project.attention_reasons || []).length
        ? `<ul class="project-attention-list">${project.attention_reasons.map((reason) => `<li>${escapeHtml(reason)}</li>`).join('')}</ul>`
        : '';
    const recentlyOpened = isRecentlyOpened(project.id)
        ? '<span class="meta-chip">Recently opened</span>'
        : '';
    const archiveLabel = project.is_archived ? 'Restore from archive' : 'Archive';

    return `
        <article class="project-card ${project.is_archived ? 'archived' : ''}" data-project-id="${project.id}">
            <div class="project-card-header">
                <div class="project-icon ${langClass}">${langIcon}</div>
                <div class="project-title-group">
                    <div class="project-title-row">
                        <h3>${escapeHtml(project.name)}</h3>
                        <span class="lang-badge ${langClass}">${escapeHtml(getLanguageLabel(project.language))}</span>
                    </div>
                    ${ownerLine}
                    <div class="project-meta-line">Last active ${escapeHtml(getTimeAgo(project.latest_activity_at || project.updated_at))} • Updated ${escapeHtml(formatAbsoluteDate(project.updated_at))}</div>
                </div>
            </div>

            <div class="chip-row">
                ${statusBadge}
                ${recentActivityBadge}
                ${recentlyOpened}
            </div>

            <p class="project-description">${description}</p>

            <div class="project-stats-row">
                <span class="meta-chip">${Number(project.file_count || 0)} files</span>
                <span class="meta-chip">${Number(project.version_count || 0)} save ${Number(project.version_count || 0) === 1 ? 'point' : 'points'}</span>
                <span class="meta-chip">${Number(project.conversation_count || 0)} chat ${Number(project.conversation_count || 0) === 1 ? 'message' : 'messages'}</span>
            </div>

            <div class="project-activity-box">
                ${latestPrompt || latestReview ? `${latestPrompt}${latestReview}` : `
                    <div class="project-activity-line">
                        <strong>Latest activity</strong>
                        <span>No chat review yet. Open the project to explore or create a save point.</span>
                    </div>
                `}
                ${attentionList}
            </div>

            <div class="project-actions-primary">
                <button class="btn-open" type="button" data-action="open" data-project-id="${project.id}">🚀 Open workspace</button>
                <button class="btn-secondary" type="button" data-action="versions" data-project-id="${project.id}">🕘 Save points</button>
            </div>

            <details class="project-tools">
                <summary>Recovery & cleanup tools <span class="project-tools-copy">Duplicate, archive, or reset with a safety net.</span></summary>
                <div class="project-tools-body">
                    <p class="project-tools-note">Duplicate keeps a safe copy. Archive hides finished or messy projects without deleting them. Reset restores starter files and makes an automatic recovery point first.</p>
                    <div class="project-tools-actions">
                        <button class="btn-secondary" type="button" data-action="duplicate" data-project-id="${project.id}">Duplicate</button>
                        <button class="btn-secondary" type="button" data-action="archive" data-project-id="${project.id}">${archiveLabel}</button>
                        <button class="btn-danger" type="button" data-action="reset" data-project-id="${project.id}">Reset to starter</button>
                    </div>
                </div>
            </details>
        </article>
    `;
}

function updateResultsMeta(filteredProjects) {
    const meta = document.getElementById('projects-results-meta');
    if (!meta) return;

    const activeScopeLabel = currentScope === 'all' ? 'all visible projects' : 'your projects';
    meta.textContent = `Showing ${filteredProjects.length} of ${projects.length} loaded in ${activeScopeLabel}.`;
}

function renderFilteredEmptyState(container) {
    container.innerHTML = `
        <section class="empty-state">
            <div class="empty-state-icon">🧭</div>
            <h3>No projects match these filters</h3>
            <p>Try clearing one filter, switching scope, or opening the archived view.</p>
            <div class="project-actions-primary" style="justify-content:center; margin-top: 1.25rem;">
                <button id="clear-project-filters" class="btn-secondary" type="button">Clear filters</button>
            </div>
        </section>
    `;

    const clearButton = document.getElementById('clear-project-filters');
    if (clearButton) {
        clearButton.addEventListener('click', () => resetFilters());
    }
}

function renderProjectsList() {
    const container = document.getElementById('projects-list');
    if (!container) return;

    if (!projects.length) {
        renderSummaryCards([]);
        updateResultsMeta([]);
        renderEmptyState(container);
        return;
    }

    const filteredProjects = getFilteredProjects();
    renderSummaryCards(filteredProjects);
    updateResultsMeta(filteredProjects);

    if (!filteredProjects.length) {
        renderFilteredEmptyState(container);
        return;
    }

    container.innerHTML = filteredProjects.map(buildProjectCard).join('');

    container.querySelectorAll('[data-action="open"]').forEach((button) => {
        button.addEventListener('click', (event) => {
            event.stopPropagation();
            openProject(button.dataset.projectId);
        });
    });

    container.querySelectorAll('[data-action="versions"]').forEach((button) => {
        button.addEventListener('click', (event) => {
            event.stopPropagation();
            openProject(button.dataset.projectId, { modal: 'versions' });
        });
    });

    container.querySelectorAll('[data-action="duplicate"]').forEach((button) => {
        button.addEventListener('click', async (event) => {
            event.stopPropagation();
            const project = projects.find((item) => Number(item.id) === Number(button.dataset.projectId));
            if (project) await duplicateProject(project);
        });
    });

    container.querySelectorAll('[data-action="archive"]').forEach((button) => {
        button.addEventListener('click', async (event) => {
            event.stopPropagation();
            const project = projects.find((item) => Number(item.id) === Number(button.dataset.projectId));
            if (project) await toggleProjectArchive(project);
        });
    });

    container.querySelectorAll('[data-action="reset"]').forEach((button) => {
        button.addEventListener('click', async (event) => {
            event.stopPropagation();
            const project = projects.find((item) => Number(item.id) === Number(button.dataset.projectId));
            if (project) await resetProjectToStarter(project);
        });
    });
}

function resetFilters() {
    const search = document.getElementById('project-search');
    const owner = document.getElementById('owner-filter');
    const language = document.getElementById('language-filter');
    const status = document.getElementById('status-filter');
    const sort = document.getElementById('sort-filter');

    if (search) search.value = '';
    if (owner) owner.value = 'all';
    if (language) language.value = 'all';
    if (status) status.value = 'active';
    if (sort) sort.value = 'recent-activity';

    document.querySelectorAll('.quick-filter-chip').forEach((chip) => {
        chip.classList.toggle('active', chip.dataset.quickFilter === 'all');
    });

    renderProjectsList();
}

async function loadProjects() {
    const container = document.getElementById('projects-list');
    if (!container) return;

    container.innerHTML = `
        <section class="loading-state">
            <div class="spinner"></div>
            <p>Loading your projects...</p>
        </section>
    `;

    let data;
    try {
        data = await apiRequest(`/projects${isAdmin ? `?scope=${encodeURIComponent(currentScope)}` : ''}`);
    } catch (error) {
        renderProjectsError(container, 'Network error. Please check your connection and try again.');
        return;
    }

    if (!data) {
        renderProjectsError(container, 'Your session may have expired. Please sign in again.');
        return;
    }

    if (!data.success) {
        renderProjectsError(container, data.error || 'The projects list could not be loaded.');
        return;
    }

    projects = data.projects || [];
    projectSummary = data.summary || {};
    syncOwnerFilterOptions();
    renderProjectsList();
}

async function createProject() {
    const nameInput = document.getElementById('project-name');
    const descInput = document.getElementById('project-desc');
    const errorDiv = document.getElementById('project-error');
    const createBtn = document.getElementById('create-project');

    const name = nameInput.value.trim();
    const description = descInput.value.trim();

    if (!name) {
        errorDiv.textContent = 'Please give your project a name.';
        errorDiv.classList.add('show');
        nameInput.focus();
        return;
    }

    errorDiv.classList.remove('show');
    errorDiv.textContent = '';
    createBtn.disabled = true;
    createBtn.textContent = 'Creating...';

    try {
        const data = await apiRequest('/projects', {
            method: 'POST',
            body: { name, description, language: selectedLanguage }
        });

        if (data && data.success) {
            openProject(data.project.id);
            return;
        }

        errorDiv.textContent = data?.error || 'Failed to create project. Please try again.';
        errorDiv.classList.add('show');
    } catch (error) {
        errorDiv.textContent = 'Network error. Please try again.';
        errorDiv.classList.add('show');
    } finally {
        createBtn.disabled = false;
        createBtn.textContent = 'Start Building';
    }
}

function openProjectActionModal(config) {
    const modal = document.getElementById('project-action-modal');
    const title = document.getElementById('project-action-title');
    const message = document.getElementById('project-action-message');
    const inputWrap = document.getElementById('project-action-input-wrap');
    const inputLabel = document.getElementById('project-action-input-label');
    const input = document.getElementById('project-action-input');
    const error = document.getElementById('project-action-error');
    const confirm = document.getElementById('project-action-confirm');

    if (!modal || !title || !message || !inputWrap || !inputLabel || !input || !error || !confirm) {
        return Promise.resolve({ confirmed: false, value: '' });
    }

    title.textContent = config.title || 'Project action';
    message.textContent = config.message || '';
    confirm.textContent = config.confirmLabel || 'Confirm';
    confirm.className = config.confirmClass || 'btn-gradient';
    inputWrap.classList.toggle('hidden', !config.needsInput);
    inputLabel.textContent = config.inputLabel || 'Name';
    input.value = config.initialValue || '';
    input.placeholder = config.placeholder || '';
    error.classList.remove('show');
    error.textContent = '';
    modal.classList.remove('hidden');

    return new Promise((resolve) => {
        projectActionState = {
            resolve,
            validate: config.validate || (() => ''),
            needsInput: Boolean(config.needsInput)
        };

        if (projectActionState.needsInput) {
            setTimeout(() => {
                input.focus();
                input.select();
            }, 0);
        } else {
            setTimeout(() => confirm.focus(), 0);
        }
    });
}

function closeProjectActionModal(result = { confirmed: false, value: '' }) {
    const modal = document.getElementById('project-action-modal');
    const input = document.getElementById('project-action-input');
    const error = document.getElementById('project-action-error');

    if (modal) modal.classList.add('hidden');
    if (input) input.value = '';
    if (error) {
        error.classList.remove('show');
        error.textContent = '';
    }

    if (projectActionState?.resolve) {
        projectActionState.resolve(result);
    }
    projectActionState = null;
}

function submitProjectActionModal() {
    if (!projectActionState) return;

    const input = document.getElementById('project-action-input');
    const error = document.getElementById('project-action-error');
    const value = input ? input.value.trim() : '';
    const validationError = projectActionState.validate(value);

    if (validationError) {
        error.textContent = validationError;
        error.classList.add('show');
        return;
    }

    closeProjectActionModal({ confirmed: true, value });
}

async function duplicateProject(project) {
    const action = await openProjectActionModal({
        title: 'Duplicate project',
        message: `Create a safe copy of "${project.name}" so you can experiment or recover without touching the original right away.`,
        confirmLabel: 'Duplicate project',
        confirmClass: 'btn-gradient',
        needsInput: true,
        inputLabel: 'Copy name',
        initialValue: `${project.name} Copy`,
        placeholder: 'Project copy name',
        validate: (value) => value ? '' : 'Please name the copy.'
    });

    if (!action.confirmed) return;

    const data = await apiRequest(`/projects/${project.id}/duplicate`, {
        method: 'POST',
        body: { name: action.value }
    });

    if (!data || !data.success) {
        showBanner(data?.error || 'Could not duplicate that project.', 'error');
        return;
    }

    showBanner(`Duplicated "${project.name}" as "${data.project.name}".`, 'success');
    await loadProjects();
}

async function toggleProjectArchive(project) {
    const archiving = !project.is_archived;
    const action = await openProjectActionModal({
        title: archiving ? 'Archive project' : 'Restore archived project',
        message: archiving
            ? `Archive "${project.name}"? It will stay safe, including files and save points, but it will stop cluttering the active list.`
            : `Restore "${project.name}" to the active list?`,
        confirmLabel: archiving ? 'Archive project' : 'Restore project',
        confirmClass: archiving ? 'btn-secondary' : 'btn-gradient',
        needsInput: false
    });

    if (!action.confirmed) return;

    const data = await apiRequest(`/projects/${project.id}/archive`, {
        method: 'POST',
        body: { archived: archiving }
    });

    if (!data || !data.success) {
        showBanner(data?.error || 'Could not update archive status.', 'error');
        return;
    }

    showBanner(
        archiving
            ? `Archived "${project.name}". You can bring it back any time.`
            : `Restored "${project.name}" to the active list.`,
        'success'
    );
    await loadProjects();
}

async function resetProjectToStarter(project) {
    const action = await openProjectActionModal({
        title: 'Reset project to starter files',
        message: `Reset "${project.name}" back to its starter files? A hidden recovery save point will be created first so the current work can still be restored later from Save points.`,
        confirmLabel: 'Create recovery point and reset',
        confirmClass: 'btn-danger',
        needsInput: false
    });

    if (!action.confirmed) return;

    const data = await apiRequest(`/projects/${project.id}/reset`, {
        method: 'POST'
    });

    if (!data || !data.success) {
        showBanner(data?.error || 'Could not reset that project.', 'error');
        return;
    }

    const recoveryNote = data.recovery_version_id
        ? ' A recovery point was saved first.'
        : '';
    showBanner(`Reset "${project.name}" to starter files.${recoveryNote}`, 'success');
    await loadProjects();
}

function wireControls() {
    document.getElementById('project-search')?.addEventListener('input', () => renderProjectsList());
    document.getElementById('owner-filter')?.addEventListener('change', () => renderProjectsList());
    document.getElementById('language-filter')?.addEventListener('change', () => renderProjectsList());
    document.getElementById('status-filter')?.addEventListener('change', () => renderProjectsList());
    document.getElementById('sort-filter')?.addEventListener('change', () => renderProjectsList());

    const scopeFilter = document.getElementById('scope-filter');
    if (scopeFilter) {
        scopeFilter.value = currentScope;
        scopeFilter.addEventListener('change', async () => {
            currentScope = scopeFilter.value || 'mine';
            await loadProjects();
        });
    }

    document.querySelectorAll('.quick-filter-chip').forEach((chip) => {
        chip.addEventListener('click', () => {
            document.querySelectorAll('.quick-filter-chip').forEach((button) => {
                button.classList.toggle('active', button === chip);
            });

            const quickFilter = chip.dataset.quickFilter;
            const status = document.getElementById('status-filter');
            if (status && quickFilter === 'archived') {
                status.value = 'archived';
            } else if (status && quickFilter === 'needs-attention') {
                status.value = 'attention';
            } else if (status && quickFilter === 'all') {
                status.value = 'active';
            }
            renderProjectsList();
        });
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const currentUser = getCurrentUser();
    const usernameDisplay = document.getElementById('username-display');
    if (usernameDisplay && currentUser) {
        usernameDisplay.textContent = currentUser.username;
    }

    if (isAdmin) {
        document.getElementById('scope-filter-wrap')?.classList.remove('hidden');
        document.getElementById('owner-filter-wrap')?.classList.remove('hidden');
    }

    const modal = document.getElementById('new-project-modal');
    const newProjectButton = document.getElementById('new-project-btn');
    const cancelButton = document.getElementById('cancel-project');
    const createButton = document.getElementById('create-project');
    const projectNameInput = document.getElementById('project-name');
    const actionModal = document.getElementById('project-action-modal');

    renderStarterPreview();
    wireControls();
    loadProjects();

    newProjectButton?.addEventListener('click', () => openNewProjectModal());
    cancelButton?.addEventListener('click', () => closeNewProjectModal(true));

    modal?.addEventListener('click', (event) => {
        if (event.target === modal) {
            closeNewProjectModal(true);
        }
    });

    document.querySelectorAll('.lang-option').forEach((button) => {
        button.addEventListener('click', () => setSelectedLanguage(button.dataset.lang));
    });

    document.querySelectorAll('.starter-idea').forEach((button) => {
        button.addEventListener('click', () => applyStarterPreset(button.dataset.template, true));
    });

    createButton?.addEventListener('click', createProject);

    projectNameInput?.addEventListener('keypress', (event) => {
        if (event.key === 'Enter') {
            createProject();
        }
    });

    document.getElementById('project-action-cancel')?.addEventListener('click', () => closeProjectActionModal());
    document.getElementById('project-action-confirm')?.addEventListener('click', submitProjectActionModal);
    document.getElementById('project-action-input')?.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            submitProjectActionModal();
        }
    });

    actionModal?.addEventListener('click', (event) => {
        if (event.target === actionModal) {
            closeProjectActionModal();
        }
    });
});
