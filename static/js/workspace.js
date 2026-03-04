// workspace.js - Main workspace with sidebar, file management, and agentic workflow

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
    if (currentCode && project.language !== 'python') {
        runPreview();
    }
}

// Load file tree in sidebar
function loadFileTree() {
    const container = document.getElementById('file-tree');
    
    if (projectFiles.length === 0) {
        container.innerHTML = '<div class="file-loading">No files yet</div>';
        return;
    }
    
    container.innerHTML = '';
    
    projectFiles.forEach(file => {
        const fileEl = document.createElement('div');
        fileEl.className = 'file-item';
        fileEl.dataset.fileId = file.id;
        fileEl.dataset.filename = file.filename;
        
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
            <span class="file-icon">${icon}</span>
            <span class="file-name">${escapeHtml(file.filename)}</span>
            ${badge ? `<span class="file-badge">${badge}</span>` : ''}
        `;
        
        fileEl.addEventListener('click', () => viewFile(file.id, file.filename));
        
        container.appendChild(fileEl);
    });
}

// View a file's contents
async function viewFile(fileId, filename) {
    currentFileId = fileId;
    
    // Update active state in sidebar
    document.querySelectorAll('.file-item').forEach(el => {
        el.classList.remove('active');
        if (el.dataset.fileId == fileId) {
            el.classList.add('active');
        }
    });
    
    // Show file view tab
    document.getElementById('fileview-tab-btn').style.display = 'inline-block';
    document.getElementById('fileview-tab-btn').textContent = `📄 ${filename}`;
    
    // Update file view content
    document.getElementById('fileview-filename').textContent = filename;
    document.getElementById('fileview-display').textContent = 'Loading...';
    
    // Switch to file view tab
    switchToTab('fileview');
    
    // Fetch file content
    const data = await apiRequest(`/files/${fileId}`);
    
    if (data && data.success) {
        document.getElementById('fileview-display').textContent = data.file.content || '// File is empty';
    } else {
        document.getElementById('fileview-display').textContent = 'Error loading file';
    }
}

// Close file view
function closeFileView() {
    document.getElementById('fileview-tab-btn').style.display = 'none';
    document.querySelectorAll('.file-item').forEach(el => el.classList.remove('active'));
    switchToTab('chat');
    currentFileId = null;
}

// Update UI based on project type (p5js, html, or python)
function updateProjectTypeUI(language) {
    const badge = document.getElementById('project-type-badge');
    const codeLabel = document.getElementById('code-type-label');
    const previewTabBtn = document.getElementById('preview-tab-btn');
    const quickActions = document.getElementById('quick-actions');
    const welcome = document.querySelector('.chat-welcome');
    
    if (language === 'html') {
        if (badge) {
            badge.textContent = '🌐 HTML';
            badge.className = 'project-badge badge-html';
        }
        if (codeLabel) {
            codeLabel.textContent = 'HTML/CSS/JS (read-only)';
        }
        if (previewTabBtn) {
            previewTabBtn.style.display = 'inline-block';
        }
    } else if (language === 'python') {
        if (badge) {
            badge.textContent = '🐍 Python';
            badge.className = 'project-badge badge-python';
        }
        if (codeLabel) {
            codeLabel.textContent = 'Python (read-only)';
        }
        // Hide preview tab for Python projects
        if (previewTabBtn) {
            previewTabBtn.style.display = 'none';
        }
        // Update welcome message for Python
        if (welcome) {
            welcome.innerHTML = `<p>👋 Welcome to your Python project!</p>
                <p>I'm Hari — your coding partner. I read and write files to track our work.</p>
                <p class="example">Try: "Make a script that generates random passwords" or "Check todo.md and let's plan"</p>`;
        }
        // Update quick actions for Python
        if (quickActions) {
            quickActions.innerHTML = `<button class="quick-btn" data-prompt="Add error handling">🛡️ Add Error Handling</button>
                <button class="quick-btn" data-prompt="Add comments explaining the code">💬 Add Comments</button>
                <button class="quick-btn" data-prompt="Fix any bugs">🐛 Fix Bugs</button>
                <button class="quick-btn" data-prompt="Explain how this works">❓ Explain</button>`;
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
        if (codeLabel) {
            codeLabel.textContent = 'JavaScript (read-only)';
        }
        if (previewTabBtn) {
            previewTabBtn.style.display = 'inline-block';
        }
        // Update welcome message for agentic workflow
        if (welcome) {
            welcome.innerHTML = `<p>👋 Welcome to your coding project!</p>
                <p>I'm Hari — your coding partner. I read and write files to track our work.</p>
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
            const toolCallsHtml = renderToolCalls(parsed.toolCalls);
            
            messageDiv.innerHTML = `
                <div class="message-bubble">
                    <div class="explanation">${formatText(parsed.explanation)}</div>
                    ${toolCallsHtml}
                    ${parsed.suggestions.length > 0 ? `
                        <div class="suggestions">
                            <p><strong>Ideas to try:</strong></p>
                            <ul>${parsed.suggestions.map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ul>
                        </div>
                    ` : ''}
                </div>
                <div class="message-meta">Hari · ${msg.model || 'kimi'} · ${formatTime(msg.created_at)}</div>
            `;
        }

        container.appendChild(messageDiv);
    });

    container.scrollTop = container.scrollHeight;
}

// Render tool calls in a message
function renderToolCalls(toolCalls) {
    if (!toolCalls || toolCalls.length === 0) return '';
    
    let html = '<div class="tool-calls-list">';
    html += '<p style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.25rem;">Files:</p>';
    
    toolCalls.forEach(tc => {
        const toolName = tc.tool || tc.name;
        const filename = tc.input?.filename || tc.input?.name || '';
        const action = tc.result?.action || 'executed';
        const success = tc.result?.success !== false;
        
        html += `
            <div class="tool-call-item ${success ? 'success' : ''}">
                <span class="tool-icon">${success ? '✓' : '✗'}</span>
                <span class="tool-name">${toolName}</span>
                <span>${filename} → ${action}</span>
            </div>
        `;
    });
    
    html += '</div>';
    return html;
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
        body: { 
            message: messageContent, 
            model: 'kimi-k2.5',
            enable_tools: true
        }
    });

    thinking.classList.add('hidden');
    sendBtn.disabled = false;

    if (data && data.success) {
        if (data.response.code) {
            currentCode = data.response.code;
            updateCodeDisplay();

            // Only auto-switch to preview for runnable languages
            if (project.language !== 'python') {
                switchToTab('preview');
                runPreview();
            }
        }
        
        // Refresh file tree if tools were used
        if (data.response.tool_calls && data.response.tool_calls.length > 0) {
            refreshFileTree();
        }

        const assistantMsg = document.createElement('div');
        assistantMsg.className = 'message assistant';
        const suggestions = data.response.suggestions || [];
        const toolCallsHtml = renderToolCalls(data.response.tool_calls);
        
        assistantMsg.innerHTML = `
            <div class="message-bubble">
                <div class="explanation">${formatText(data.response.explanation)}</div>
                ${toolCallsHtml}
                ${suggestions.length > 0 ? `
                    <div class="suggestions">
                        <p><strong>Ideas to try:</strong></p>
                        <ul>${suggestions.map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ul>
                    </div>
                ` : ''}
            </div>
            <div class="message-meta">Hari · ${data.response.model || 'kimi'} · ${formatTime(new Date().toISOString())}</div>
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
    
    // Don't try to preview Python in browser
    if (language === 'python') {
        container.innerHTML = '<p class="preview-placeholder">Python code runs on your computer. Copy the code and run it locally with Python installed.</p>';
        return;
    }
    
    sandboxRunner = new SandboxRunner('preview-container');
    sandboxRunner.run(currentCode, language);
}

// Parse assistant message for display
function parseAssistantMessage(content) {
    const result = {
        explanation: '',
        code: '',
        suggestions: [],
        toolCalls: []
    };

    // Extract tool calls section if present
    const toolSectionMatch = content.match(/---\s*\n\*\*Tool Calls:\*\*\s*\n([\s\S]*?)$/);
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
        // Remove tool section from content for other parsing
        content = content.substring(0, content.indexOf('---\n\n**Tool Calls:**'));
    }

    const codeMatch = content.match(/```(?:javascript|js|html|python|py)?\s*\n([\s\S]*?)\n```/);
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
        });
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

    // Fullscreen button
    document.getElementById('fullscreen-btn').addEventListener('click', () => {
        const preview = document.getElementById('preview-container');
        if (preview.requestFullscreen) {
            preview.requestFullscreen();
        }
    });

    // Save version button
    document.getElementById('save-version-btn').addEventListener('click', async () => {
        const description = prompt('Version description (optional):');
        if (description === null) return;

        const data = await apiRequest(`/projects/${projectId}/versions`, {
            method: 'POST',
            body: { description }
        });

        if (data && data.success) {
            alert('Version saved!');
        } else {
            alert('Failed to save version');
        }
    });

    // Logout button
    document.getElementById('logout-btn').addEventListener('click', () => {
        logout();
        window.location.href = '/lab/login';
    });

    // Edit mode toggle
    document.getElementById('edit-mode').addEventListener('change', (e) => {
        const display = document.getElementById('code-display');
        const editor = document.getElementById('code-editor');

        if (e.target.checked) {
            display.classList.add('hidden');
            editor.classList.remove('hidden');
        } else {
            display.classList.remove('hidden');
            editor.classList.add('hidden');
        }
    });

    // File upload
    document.getElementById('chat-upload').addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            handleFileUpload(file);
        }
    });
    
    // File view close button
    document.getElementById('fileview-close').addEventListener('click', closeFileView);
    
    // New file button (placeholder for future)
    document.getElementById('new-file-btn').addEventListener('click', () => {
        const filename = prompt('Enter filename (e.g., helper.js, styles.css):');
        if (filename && filename.trim()) {
            // For now, just show a message - actual file creation would need backend support
            alert(`To create ${filename.trim()}, ask me to write it for you!\n\nTry: "Create a file called ${filename.trim()} with [what you want in it]"`);
        }
    });
});
