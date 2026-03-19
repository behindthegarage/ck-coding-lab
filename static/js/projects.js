// projects.js - Project gallery functionality

if (!isLoggedIn()) {
    window.location.href = '/lab/login';
}

let projects = [];
let selectedLanguage = 'p5js';

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

const user = getCurrentUser();
if (user && user.role === 'admin') {
    const adminLink = document.getElementById('admin-link');
    if (adminLink) adminLink.classList.remove('hidden');
}

function getLanguageIcon(lang) {
    const icons = {
        p5js: '🎨',
        html: '🌐',
        python: '🐍',
        undecided: '💡'
    };
    return icons[lang] || icons.undecided;
}

function getLanguageBadgeClass(lang) {
    const classes = {
        p5js: 'p5js',
        html: 'html',
        python: 'python',
        undecided: 'html'
    };
    return classes[lang] || 'html';
}

function getTimeAgo(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);

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

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showProjectMenu(projectId) {
    console.log('Menu clicked for project:', projectId);
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
    document.getElementById('project-error').classList.remove('show');
    document.getElementById('project-error').textContent = '';

    const createBtn = document.getElementById('create-project');
    if (createBtn) {
        createBtn.disabled = false;
        createBtn.textContent = 'Start Building';
    }

    if (presetKey) {
        applyStarterPreset(presetKey, true);
    } else {
        renderStarterPreview();
    }

    document.getElementById('project-name').focus();
    document.getElementById('project-name').select();
}

function closeNewProjectModal(resetText = true) {
    const modal = document.getElementById('new-project-modal');
    if (!modal) return;

    modal.classList.add('hidden');
    document.getElementById('project-error').classList.remove('show');
    document.getElementById('project-error').textContent = '';

    if (resetText) {
        document.getElementById('project-name').value = '';
        document.getElementById('project-desc').value = '';
    }

    setSelectedLanguage('p5js');
}

function renderProjectsError(container, message = 'Could not load your projects right now.') {
    container.innerHTML = `
        <section class="empty-state">
            <div class="empty-state-hero">
                <div class="empty-state-icon">⚠️</div>
                <h3>We couldn't load your projects</h3>
                <p>${escapeHtml(message)}</p>
            </div>
            <div class="empty-state-actions">
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
            <div class="empty-state-hero">
                <div class="empty-state-icon">🚀</div>
                <h3>Start your first project</h3>
                <p>Pick a starter below, open it, and make one tiny change right away.</p>
            </div>
            <div class="quick-start-grid">
                ${starterCards}
            </div>
            <div class="empty-state-actions">
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

async function loadProjects() {
    const container = document.getElementById('projects-list');
    container.innerHTML = `
        <div class="loading-state">
            <div class="spinner"></div>
            <p>Loading your projects...</p>
        </div>
    `;

    let data;
    try {
        data = await apiRequest('/projects');
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

    if (projects.length === 0) {
        renderEmptyState(container);
        return;
    }

    container.innerHTML = projects.map((project) => {
        const langIcon = getLanguageIcon(project.language);
        const langBadgeClass = getLanguageBadgeClass(project.language);
        const desc = project.description || 'No description';
        const timeAgo = getTimeAgo(project.updated_at);

        return `
            <div class="project-card" data-id="${project.id}">
                <div class="project-card-header">
                    <div class="project-icon ${langBadgeClass}">${langIcon}</div>
                    <div class="project-title-group">
                        <h3>${escapeHtml(project.name)}</h3>
                        <div class="project-meta">Updated ${timeAgo}</div>
                    </div>
                    <span class="lang-badge ${langBadgeClass}">${project.language || 'p5js'}</span>
                </div>
                <div class="project-body">
                    <p class="project-description">${escapeHtml(desc)}</p>
                </div>
                <div class="project-actions">
                    <button class="btn-open" data-id="${project.id}">🚀 Open</button>
                    <button class="btn-menu" data-id="${project.id}">⋮</button>
                </div>
            </div>
        `;
    }).join('');

    document.querySelectorAll('.btn-open').forEach((button) => {
        button.addEventListener('click', (event) => {
            event.stopPropagation();
            window.location.href = `/lab/project/${button.dataset.id}`;
        });
    });

    document.querySelectorAll('.project-card').forEach((card) => {
        card.addEventListener('click', (event) => {
            if (event.target.closest('.btn-open') || event.target.closest('.btn-menu')) {
                return;
            }
            window.location.href = `/lab/project/${card.dataset.id}`;
        });
    });

    document.querySelectorAll('.btn-menu').forEach((button) => {
        button.addEventListener('click', (event) => {
            event.stopPropagation();
            showProjectMenu(button.dataset.id);
        });
    });
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
            window.location.href = `/lab/project/${data.project.id}`;
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

document.addEventListener('DOMContentLoaded', () => {
    const currentUser = getCurrentUser();
    if (currentUser && currentUser.role === 'admin') {
        const adminLink = document.getElementById('admin-link');
        if (adminLink) adminLink.classList.remove('hidden');
    }

    const usernameDisplay = document.getElementById('username-display');
    if (usernameDisplay && currentUser) {
        usernameDisplay.textContent = currentUser.username;
    }

    const modal = document.getElementById('new-project-modal');
    const newProjectButton = document.getElementById('new-project-btn');
    const cancelButton = document.getElementById('cancel-project');
    const createButton = document.getElementById('create-project');
    const projectNameInput = document.getElementById('project-name');

    renderStarterPreview();
    loadProjects();

    newProjectButton.addEventListener('click', () => openNewProjectModal());
    cancelButton.addEventListener('click', () => closeNewProjectModal(true));

    modal.addEventListener('click', (event) => {
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

    createButton.addEventListener('click', createProject);

    projectNameInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter') {
            createProject();
        }
    });
});
