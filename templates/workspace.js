// workspace.js - Main workspace with chat, code, and preview tabs

// Redirect if not logged in
if (!isLoggedIn()) {
    window.location.href = '/lab/login';
}

// Get project ID from URL
const projectId = window.location.pathname.split('/').pop();

// State
let project = null;
let conversations = [];
let currentCode = '';
let sandboxRunner = null;

// Load project data
async function loadProject() {
    const data = await apiRequest(`/projects/${projectId}`);

    if (!data) return;

    project = data.project;
    conversations = data.conversations || [];
    currentCode = project.current_code || '';

    // Update UI
    document.getElementById('project-name').textContent = project.name;
    updateCodeDisplay();

    // Load conversation history
    loadConversations();

    // Run initial preview if there's code
    if (currentCode) {
        runPreview();
    }
}

// Load conversation messages
function loadConversations() {
    const container = document.getElementById('chat-messages');

    if (conversations.length === 0) {
        return; // Keep welcome message
    }

    container.innerHTML = '';

    conversations.forEach(msg => {
        if (msg.role === 'system') return; // Skip system messages

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${msg.role}`;

        if (msg.role === 'user') {
            messageDiv.innerHTML = `
                <div class="message-bubble">${escapeHtml(msg.content)}</div>
                <div class="message-meta">You</div>
            `;
        } else {
            // Assistant message - parse for code and suggestions
            const parsed = parseAssistantMessage(msg.content);
            messageDiv.innerHTML = `
                <div class="message-bubble">
                    <p>${escapeHtml(parsed.explanation)}</p>
                    ${parsed.code ? `<pre><code class="language-javascript">${escapeHtml(parsed.code.substring(0, 200))}${parsed.code.length > 200 ? '...' : ''}</code></pre>` : ''}
                    ${parsed.suggestions.length > 0 ? `
                        <div class="suggestions">
                            <p><strong>Ideas:</strong></p>
                            <ul>${parsed.suggestions.map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ul>
                        </div>
                    ` : ''}
                </div>
                <div class="message-meta">AI · ${msg.model || 'unknown'} · ${formatTime(msg.created_at)}</div>
            `;
        }

        container.appendChild(messageDiv);
    });

    // Scroll to bottom
    container.scrollTop = container.scrollHeight;
}

// Send message to AI
async function sendMessage(message) {
    const input = document.getElementById('chat-input');
    const thinking = document.getElementById('thinking-indicator');
    const sendBtn = document.getElementById('send-btn');

    // Clear input and show thinking
    input.value = '';
    thinking.classList.remove('hidden');
    sendBtn.disabled = true;

    // Add user message to UI immediately
    const container = document.getElementById('chat-messages');
    const userMsg = document.createElement('div');
    userMsg.className = 'message user';
    userMsg.innerHTML = `
        <div class="message-bubble">${escapeHtml(message)}</div>
        <div class="message-meta">You</div>
    `;
    container.appendChild(userMsg);
    container.scrollTop = container.scrollHeight;

    // Remove welcome message if present
    const welcome = container.querySelector('.chat-welcome');
    if (welcome) welcome.remove();

    // Call API
    const data = await apiRequest(`/projects/${projectId}/chat`, {
        method: 'POST',
        body: { message, model: 'kimi-k2.5' }
    });

    // Hide thinking
    thinking.classList.add('hidden');
    sendBtn.disabled = false;

    if (data && data.success) {
        // Update code
        if (data.response.code) {
            currentCode = data.response.code;
            updateCodeDisplay();

            // Auto-switch to preview tab
            switchToTab('preview');
            runPreview();
        }

        // Add assistant message to UI
        const assistantMsg = document.createElement('div');
        assistantMsg.className = 'message assistant';
        const suggestions = data.response.suggestions || [];
        assistantMsg.innerHTML = `
            <div class="message-bubble">
                <p>${escapeHtml(data.response.explanation || '')}</p>
                ${data.response.code ? `<pre><code class="language-javascript">${escapeHtml(data.response.code.substring(0, 200))}${data.response.code.length > 200 ? '...' : ''}</code></pre>` : ''}
                ${suggestions.length > 0 ? `
                    <div class="suggestions">
                        <p><strong>Ideas:</strong></p>
                        <ul>${suggestions.map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ul>
                    </div>
                ` : ''}
            </div>
            <div class="message-meta">AI · ${data.response.model || 'kimi'} · ${formatTime(new Date().toISOString())}</div>
        `;
        container.appendChild(assistantMsg);
        container.scrollTop = container.scrollHeight;
    } else {
        // Show error
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
}

// Update code display in code tab
function updateCodeDisplay() {
    const display = document.getElementById('code-display');
    const editor = document.getElementById('code-editor');

    display.textContent = currentCode || '// Your code will appear here...';
    editor.value = currentCode;
}

// Run code in preview
function runPreview() {
    console.log("runPreview called, code length:", currentCode ? currentCode.length : 0);
    const container = document.getElementById('preview-container');
    
    if (!currentCode) {
        container.innerHTML = '<p class="preview-placeholder">Your project preview will appear here.</p>';
        return;
    }
    
    // Initialize sandbox if needed
    if (!sandboxRunner) {
        sandboxRunner = new SandboxRunner('preview-container');
    }
    
    // Validate code first (optional - could also call server)
    sandboxRunner.run(currentCode);
}

// Parse assistant message for display
function parseAssistantMessage(content) {
    const result = {
        explanation: '',
        code: '',
        suggestions: []
    };

    // Extract code block
    const codeMatch = content.match(/```(?:javascript|js)?\s*\n([\s\S]*?)\n```/);
    if (codeMatch) {
        result.code = codeMatch[1].trim();
    }

    // Get text before code block as explanation
    const beforeCode = content.split(/```/)[0].trim();
    result.explanation = beforeCode;

    // Extract suggestions (bullet points after code)
    const afterCode = content.split(/```[\s\S]*?```/)[1] || '';
    const suggestionMatch = afterCode.match(/(?:[-*•]\s*(.+?)(?:\n|$))/g);
    if (suggestionMatch) {
        result.suggestions = suggestionMatch.map(s => s.replace(/^[-*•]\s*/, '').trim());
    }

    return result;
}

// Tab switching
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('tab-btn')) {
        const tab = e.target.dataset.tab;
        switchToTab(tab);
    }
});

// Helper: Switch to a specific tab
function switchToTab(tabName) {
    // Update active tab button
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });

    // Update active tab pane
    document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.classList.toggle('active', pane.id === `${tabName}-tab`);
    });
}

// Helper: Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Helper: Format time
function formatTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit'
    });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Load project data
    loadProject();

    // Chat input
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');

    sendBtn.addEventListener('click', () => {
        const message = chatInput.value.trim();
        if (message) {
            sendMessage(message);
        }
    });

    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendBtn.click();
        }
    });

    // Quick action buttons
    document.querySelectorAll('.quick-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const prompt = btn.dataset.prompt;
            sendMessage(prompt);
        });
    });

    // Code edit toggle
    const editToggle = document.getElementById('edit-mode');
    if (editToggle) {
        editToggle.addEventListener('change', () => {
            const display = document.getElementById('code-display');
            const editor = document.getElementById('code-editor');

            if (editToggle.checked) {
                display.classList.add('hidden');
                editor.classList.remove('hidden');
            } else {
                // Save changes
                currentCode = editor.value;
                display.textContent = currentCode || '// Your code will appear here...';
                display.classList.remove('hidden');
                editor.classList.add('hidden');
            }
        });
    }

    // Run button
    const runBtn = document.getElementById('run-btn');
    if (runBtn) {
        runBtn.addEventListener('click', runPreview);
    }

    // Save version button
    const saveVersionBtn = document.getElementById('save-version-btn');
    if (saveVersionBtn) {
        saveVersionBtn.addEventListener('click', async () => {
            const data = await apiRequest(`/projects/${projectId}/versions`, {
                method: 'POST',
                body: { description: 'Manual save' }
            });

            if (data?.success) {
                saveVersionBtn.textContent = 'Saved!';
                setTimeout(() => {
                    saveVersionBtn.textContent = 'Save Version';
                }, 2000);
            }
        });
    }
});