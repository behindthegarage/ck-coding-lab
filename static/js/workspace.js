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
let pendingUpload = null;

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

    container.scrollTop = container.scrollHeight;
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

    const data = await apiRequest(`/projects/${projectId}/chat`, {
        method: 'POST',
        body: { message: messageContent, model: 'kimi-k2.5' }
    });

    thinking.classList.add('hidden');
    sendBtn.disabled = false;

    if (data && data.success) {
        if (data.response.code) {
            currentCode = data.response.code;
            updateCodeDisplay();

            switchToTab('preview');
            runPreview();
        }

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

// Handle file upload
function handleFileUpload(file) {
    if (!file) return;
    
    const maxSize = 5 * 1024 * 1024; // 5MB limit
    if (file.size > maxSize) {
        alert('File too large. Max size is 5MB.');
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
    } else if (file.type === 'text/plain' || file.name.match(/\.(js|html|css|txt|json)$/)) {
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
        alert('Unsupported file type. Please upload images, text files, or code files.');
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
    const container = document.getElementById('preview-container');
    
    if (!container) {
        console.error("runPreview: preview-container element not found!");
        return;
    }
    
    if (!currentCode) {
        container.innerHTML = '<p class="preview-placeholder">Your project preview will appear here.</p>';
        return;
    }
    
    const language = (project && project.language) ? project.language : 'p5js';
    
    sandboxRunner = new SandboxRunner('preview-container');
    sandboxRunner.run(currentCode, language);
}

// Parse assistant message for display
function parseAssistantMessage(content) {
    const result = {
        explanation: '',
        code: '',
        suggestions: []
    };

    const codeMatch = content.match(/```(?:javascript|js|html)?\s*\n([\s\S]*?)\n```/);
    if (codeMatch) {
        result.code = codeMatch[1].trim();
    }

    const beforeCode = content.split(/```/)[0].trim();
    result.explanation = beforeCode;

    const afterCode = content.split(/```/).slice(-1)[0].trim();
    if (afterCode) {
        const lines = afterCode.split('\n').filter(l => l.trim().startsWith('-') || l.trim().startsWith('•'));
        result.suggestions = lines.map(l => l.replace(/^[-•]\s*/, '').trim()).filter(l => l);
    }

    return result;
}

// Switch to a different tab
function switchToTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.tab === tabName) {
            btn.classList.add('active');
        }
    });

    document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.classList.remove('active');
        if (pane.id === `${tabName}-tab`) {
            pane.classList.add('active');
        }
    });
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

    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.dataset.tab;
            switchToTab(tabName);
            
            // Auto-focus preview when switching to preview tab
            if (tabName === 'preview' && sandboxRunner) {
                sandboxRunner.focus();
            }
        });
    });

    // Chat input
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');

    sendBtn.addEventListener('click', () => {
        const message = chatInput.value.trim();
        if (message || pendingUpload) {
            sendMessage(message || 'Please help with the uploaded file.');
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

    // File upload
    const uploadInput = document.getElementById('chat-upload');
    if (uploadInput) {
        uploadInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleFileUpload(e.target.files[0]);
            }
        });
    }

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
                currentCode = editor.value;
                display.textContent = currentCode || '// Your code will appear here...';
                display.classList.remove('hidden');
                editor.classList.add('hidden');
            }
        });
    }

    // Run button - focus now waits for iframe to load via sandboxRunner.focus()
    const runBtn = document.getElementById('run-btn');
    if (runBtn) {
        runBtn.addEventListener('click', () => {
            runPreview();
            sandboxRunner.focus();
        });
    }
    
    // Fullscreen button
    const fullscreenBtn = document.getElementById('fullscreen-btn');
    if (fullscreenBtn) {
        fullscreenBtn.addEventListener('click', () => {
            const previewContainer = document.getElementById('preview-container');
            if (previewContainer) {
                if (previewContainer.requestFullscreen) {
                    previewContainer.requestFullscreen();
                } else if (previewContainer.webkitRequestFullscreen) {
                    previewContainer.webkitRequestFullscreen();
                } else if (previewContainer.msRequestFullscreen) {
                    previewContainer.msRequestFullscreen();
                }
            }
            if (sandboxRunner) {
                sandboxRunner.focus();
            }
        });
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
