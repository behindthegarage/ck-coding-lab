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
    container.innerHTML = '<div class="loading">Loading your projects...</div>';

    const data = await apiRequest('/projects');

    if (!data) return;

    projects = data.projects || [];

    if (projects.length === 0) {
        container.innerHTML = `
            <div class="loading">
                <p>No projects yet!</p>
                <p>Click "New Project" to get started.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = projects.map(project => `
        <div class="project-card" data-id="${project.id}">
            <div class="project-card-header">
                <h3>${escapeHtml(project.name)}</h3>
                <span class="lang-badge">${project.language === 'html' ? '🌐 HTML' : '🎨 p5.js'}</span>
            </div>
            <p>${escapeHtml(project.description || 'No description')}</p>
            <div class="meta">
                <span>Created: ${formatDate(project.created_at)}</span>
                <span>Updated: ${formatDate(project.updated_at)}</span>
            </div>
        </div>
    `).join('');

    // Add click handlers
    document.querySelectorAll('.project-card').forEach(card => {
        card.addEventListener('click', () => {
            const projectId = card.dataset.id;
            window.location.href = `/lab/project/${projectId}`;
        });
    });
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
        errorDiv.textContent = 'Project name is required.';
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
        errorDiv.textContent = data?.error || 'Failed to create project.';
        createBtn.disabled = false;
        createBtn.textContent = 'Create';
    }
}

// Helper: Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Helper: Format date
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
    });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Show admin link if user is admin
    const user = getCurrentUser();
    if (user && user.role === "admin") {
        const adminLink = document.getElementById("admin-link");
        if (adminLink) adminLink.classList.remove("hidden");
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
        selectedLanguage = 'p5js';
        document.querySelectorAll('.lang-pick').forEach(b => {
            b.classList.toggle('active', b.dataset.lang === 'p5js');
        });
    });

    // Language picker
    document.querySelectorAll('.lang-pick').forEach(btn => {
        btn.addEventListener('click', () => {
            selectedLanguage = btn.dataset.lang;
            document.querySelectorAll('.lang-pick').forEach(b => {
                b.classList.toggle('active', b === btn);
            });
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