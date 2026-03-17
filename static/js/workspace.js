// workspace.js - Three-pane layout with collapsible panels
// Version 34 - Three-pane workspace layout

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

// View a file's contents (now opens in modal instead of tab)
async function viewFile(fileId, filename) {
    currentFileId = fileId;
    
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
    const modalContent = document.getElementById('modal-file-content');
    
    modalFilename.textContent = filename;
    modalContent.textContent = 'Loading...';
    modal.classList.remove('hidden');
    
    // Fetch file content
    const data = await apiRequest(`/files/${fileId}`);
    
    if (data && data.success) {
        modalContent.textContent = data.file.content || '// File is empty';
    } else {
        modalContent.textContent = 'Error loading file';
    }
}

// Close file modal
function closeFileModal() {
    document.getElementById('file-modal').classList.add('hidden');
    document.querySelectorAll('.file-item').forEach(el => el.classList.remove('active'));
    currentFileId = null;
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

    // File upload
    document.getElementById('chat-upload').addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            handleFileUpload(file);
        }
    });
    
    // Modal close button
    document.getElementById('modal-close').addEventListener('click', closeFileModal);
    
    // Close modal when clicking outside
    document.getElementById('file-modal').addEventListener('click', (e) => {
        if (e.target === document.getElementById('file-modal')) {
            closeFileModal();
        }
    });
    
    // New file button
    document.getElementById('new-file-btn').addEventListener('click', () => {
        const filename = prompt('Enter filename (e.g., helper.js, styles.css):');
        if (filename && filename.trim()) {
            alert(`To create ${filename.trim()}, ask me to write it for you!\n\nTry: "Create a file called ${filename.trim()} with [what you want in it]"`);
        }
    });
});
