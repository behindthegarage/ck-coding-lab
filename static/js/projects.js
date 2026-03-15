// projects.js - Project gallery functionality

// Redirect if not logged in
if (!isLoggedIn()) {
    window.location.href = '/lab/login';
}

let projects = [];
let selectedLanguage = 'p5js';

// Show admin link if user is admin
const user = getCurrentUser();
if (user && user.role === "admin") {
    const adminLink = document.getElementById("admin-link");
    if (adminLink) adminLink.classList.remove("hidden");
}

// Load projects from API
async function loadProjects() {
    const container = document.getElementById('projects-list');
    container.innerHTML = `
        <div class="loading-state">
            <div class="spinner"></div>
            <p>Loading your projects...</p>
        </div>
    `;

    const data = await apiRequest('/projects');

    if (!data) return;

    projects = data.projects || [];

    if (projects.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📁</div>
                <h3>No projects yet!</h3>
                <p>Click "New Project" to get started on something awesome.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = projects.map(project => {
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
                    <button class="btn-open" data-id="${project.id}">
                        🚀 Open
                    </button>
                    <button class="btn-menu" data-id="${project.id}">
                        ⋮
                    </button>
                </div>
            </div>
        `;
    }).join('');

    // Add click handlers for Open buttons
    document.querySelectorAll('.btn-open').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const projectId = btn.dataset.id;
            window.location.href = `/lab/project/${projectId}`;
        });
    });

    // Add click handlers for cards (click anywhere to open)
    document.querySelectorAll('.project-card').forEach(card => {
        card.addEventListener('click', (e) => {
            // Don't navigate if clicking buttons
            if (e.target.closest('.btn-open') || e.target.closest('.btn-menu')) {
                return;
            }
            const projectId = card.dataset.id;
            window.location.href = `/lab/project/${projectId}`;
        });
    });

    // Menu button handlers (placeholder for future functionality)
    document.querySelectorAll('.btn-menu').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const projectId = btn.dataset.id;
            showProjectMenu(projectId);
        });
    });
}

// Get language icon
function getLanguageIcon(lang) {
    const icons = {
        'p5js': '🎨',
        'html': '🌐',
        'python': '🐍',
        'undecided': '💡'
    };
    return icons[lang] || icons['undecided'];
}

// Get language badge class
function getLanguageBadgeClass(lang) {
    const classes = {
        'p5js': 'p5js',
        'html': 'html',
        'python': 'python',
        'undecided': 'html'
    };
    return classes[lang] || 'html';
}

// Get time ago string
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

// Show project menu (placeholder)
function showProjectMenu(projectId) {
    // Future: Show dropdown menu with options like:
    // - Rename
    // - Duplicate
    // - Delete
    // - Share
    console.log('Menu clicked for project:', projectId);
}

// Create new project
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

    createBtn.disabled = true;
    createBtn.textContent = 'Creating...';

    const data = await apiRequest('/projects', {
        method: 'POST',
        body: { name, description, language: selectedLanguage }
    });

    if (data && data.success) {
        window.location.href = `/lab/project/${data.project.id}`;
    } else {
        errorDiv.textContent = data?.error || 'Failed to create project. Please try again.';
        errorDiv.classList.add('show');
        createBtn.disabled = false;
        createBtn.textContent = 'Start Building';
    }
}

// Helper: Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Show admin link if user is admin
    const user = getCurrentUser();
    if (user && user.role === "admin") {
        const adminLink = document.getElementById("admin-link");
        if (adminLink) adminLink.classList.remove("hidden");
    }

    // Display username
    const usernameDisplay = document.getElementById('username-display');
    if (usernameDisplay && user) {
        usernameDisplay.textContent = user.username;
    }

    // Load projects
    loadProjects();

    // New project modal
    const modal = document.getElementById('new-project-modal');
    const newBtn = document.getElementById('new-project-btn');
    const cancelBtn = document.getElementById('cancel-project');
    const createBtn = document.getElementById('create-project');

    newBtn.addEventListener('click', () => {
        modal.classList.remove('hidden');
        document.getElementById('project-name').focus();
    });

    cancelBtn.addEventListener('click', () => {
        modal.classList.add('hidden');
        document.getElementById('project-name').value = '';
        document.getElementById('project-desc').value = '';
        document.getElementById('project-error').textContent = '';
        document.getElementById('project-error').classList.remove('show');
        selectedLanguage = 'p5js';
        document.querySelectorAll('.lang-option').forEach(b => {
            b.classList.toggle('active', b.dataset.lang === 'p5js');
        });
    });

    // Close modal on backdrop click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            cancelBtn.click();
        }
    });

    // Language picker
    document.querySelectorAll('.lang-option').forEach(btn => {
        btn.addEventListener('click', () => {
            selectedLanguage = btn.dataset.lang;
            document.querySelectorAll('.lang-option').forEach(b => {
                b.classList.remove('active');
            });
            btn.classList.add('active');
        });
    });

    createBtn.addEventListener('click', createProject);

    // Allow Enter in name field to create
    document.getElementById('project-name').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            createProject();
        }
    });
});
