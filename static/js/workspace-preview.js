// workspace-preview.js - Preview helpers extracted from workspace.js

const PREVIEW_DEBUG_MAX_ENTRIES = 40;

let previewDebugEntries = [];
let previewDebugExpanded = false;
let previewDebugStatus = 'Watching runtime errors and console.error.';
let previewDebugInitialized = false;

function getPreviewDebugElements() {
    return {
        panel: document.getElementById('preview-debug-panel'),
        toggle: document.getElementById('preview-debug-toggle'),
        summary: document.getElementById('preview-debug-summary'),
        count: document.getElementById('preview-debug-count'),
        body: document.getElementById('preview-debug-body'),
        list: document.getElementById('preview-debug-list'),
        clear: document.getElementById('preview-debug-clear')
    };
}

function previewEscapeHtml(text) {
    if (typeof escapeHtml === 'function') {
        return escapeHtml(text);
    }

    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function initPreviewDebugPane() {
    if (previewDebugInitialized) {
        return;
    }

    const elements = getPreviewDebugElements();
    if (!elements.panel || !elements.toggle || !elements.body || !elements.list || !elements.clear) {
        return;
    }

    elements.toggle.addEventListener('click', () => {
        setPreviewDebugExpanded(!previewDebugExpanded);
    });

    elements.clear.addEventListener('click', (event) => {
        event.stopPropagation();
        clearPreviewDebugEntries();
    });

    previewDebugInitialized = true;
    renderPreviewDebugPane();
}

function setPreviewDebugExpanded(expanded) {
    previewDebugExpanded = !!expanded;
    renderPreviewDebugPane();
}

function clearPreviewDebugEntries() {
    previewDebugEntries = [];
    previewDebugStatus = 'Watching runtime errors and console.error.';
    previewDebugExpanded = false;
    renderPreviewDebugPane();
}

function resetPreviewDebugPane(statusMessage = 'Watching runtime errors and console.error.') {
    previewDebugEntries = [];
    previewDebugStatus = statusMessage;
    previewDebugExpanded = false;
    renderPreviewDebugPane();
}

function normalizePreviewDebugEntry(entry = {}) {
    const rawMessage = entry.message === undefined || entry.message === null
        ? ''
        : String(entry.message).trim();

    if (!rawMessage) {
        return null;
    }

    const level = entry.level === 'warn'
        ? 'warn'
        : (entry.level === 'info' ? 'info' : 'error');

    const contextParts = [];
    if (entry.filename) {
        const locationBits = [];
        if (entry.lineno) locationBits.push(`line ${entry.lineno}`);
        if (entry.colno) locationBits.push(`col ${entry.colno}`);
        contextParts.push(`${entry.filename}${locationBits.length ? ` (${locationBits.join(', ')})` : ''}`);
    } else if (entry.line) {
        contextParts.push(`line ${entry.line}`);
    }

    if (entry.context) {
        contextParts.push(String(entry.context).trim());
    }

    if (entry.stack) {
        contextParts.push(String(entry.stack).trim());
    }

    return {
        level,
        source: entry.source || 'preview',
        message: rawMessage,
        context: contextParts.filter(Boolean).join('\n'),
        timestamp: entry.timestamp || Date.now(),
        repeatCount: entry.repeatCount || 1
    };
}

function appendPreviewDebugEntry(entry) {
    const normalized = normalizePreviewDebugEntry(entry);
    if (!normalized) {
        return;
    }

    const latest = previewDebugEntries[0];
    if (
        latest &&
        latest.level === normalized.level &&
        latest.source === normalized.source &&
        latest.message === normalized.message &&
        latest.context === normalized.context
    ) {
        latest.repeatCount += 1;
        latest.timestamp = normalized.timestamp;
    } else {
        previewDebugEntries.unshift(normalized);
        if (previewDebugEntries.length > PREVIEW_DEBUG_MAX_ENTRIES) {
            previewDebugEntries.length = PREVIEW_DEBUG_MAX_ENTRIES;
        }
    }

    if (normalized.level === 'error') {
        previewDebugExpanded = true;
    }

    renderPreviewDebugPane();
}

function getPreviewDebugSummary() {
    if (previewDebugEntries.length === 0) {
        return previewDebugStatus;
    }

    const errorCount = previewDebugEntries.filter(entry => entry.level === 'error').length;
    const warnCount = previewDebugEntries.filter(entry => entry.level === 'warn').length;

    const parts = [];
    if (errorCount) {
        parts.push(`${errorCount} error${errorCount === 1 ? '' : 's'}`);
    }
    if (warnCount) {
        parts.push(`${warnCount} warning${warnCount === 1 ? '' : 's'}`);
    }

    return parts.join(' • ') || `${previewDebugEntries.length} preview event${previewDebugEntries.length === 1 ? '' : 's'}`;
}

function getPreviewDebugCount() {
    return previewDebugEntries.filter(entry => entry.level === 'error' || entry.level === 'warn').length;
}

function formatPreviewDebugTime(timestamp) {
    return new Date(timestamp).toLocaleTimeString([], {
        hour: 'numeric',
        minute: '2-digit',
        second: '2-digit'
    });
}

function titleCasePreviewLevel(level) {
    if (!level) return 'Preview';
    return level.charAt(0).toUpperCase() + level.slice(1);
}

function renderPreviewDebugPane() {
    const elements = getPreviewDebugElements();
    if (!elements.panel || !elements.summary || !elements.count || !elements.body || !elements.list || !elements.toggle) {
        return;
    }

    const summary = getPreviewDebugSummary();
    const count = getPreviewDebugCount();
    const hasErrors = previewDebugEntries.some(entry => entry.level === 'error');
    const hasWarnings = previewDebugEntries.some(entry => entry.level === 'warn');

    elements.summary.textContent = summary;
    elements.count.textContent = String(count);
    elements.count.classList.toggle('hidden', count === 0);
    elements.body.classList.toggle('hidden', !previewDebugExpanded);
    elements.toggle.setAttribute('aria-expanded', previewDebugExpanded ? 'true' : 'false');
    elements.panel.classList.toggle('has-errors', hasErrors);
    elements.panel.classList.toggle('has-warnings', hasWarnings);

    if (previewDebugEntries.length === 0) {
        elements.list.innerHTML = `<div class="preview-debug-empty">${previewEscapeHtml(previewDebugStatus)}</div>`;
        return;
    }

    elements.list.innerHTML = previewDebugEntries.map(entry => `
        <article class="preview-debug-entry level-${previewEscapeHtml(entry.level)}">
            <div class="preview-debug-entry-meta">
                <div class="preview-debug-entry-badges">
                    <span class="preview-debug-entry-source">${previewEscapeHtml(entry.source)}</span>
                    <span>${previewEscapeHtml(titleCasePreviewLevel(entry.level))}</span>
                    ${entry.repeatCount > 1 ? `<span class="preview-debug-entry-repeat">×${entry.repeatCount}</span>` : ''}
                </div>
                <span class="preview-debug-entry-time">${previewEscapeHtml(formatPreviewDebugTime(entry.timestamp))}</span>
            </div>
            <div class="preview-debug-message">${previewEscapeHtml(entry.message)}</div>
            ${entry.context ? `<div class="preview-debug-context">${previewEscapeHtml(entry.context)}</div>` : ''}
        </article>
    `).join('');
}

function handlePreviewSandboxEvent(event = {}) {
    if (!event || !event.message) {
        return;
    }

    const sourceLabels = {
        console: event.level === 'warn' ? 'console.warn' : 'console.error',
        runtime: 'runtime',
        promise: 'promise',
        preview: 'preview',
        p5: 'p5'
    };

    appendPreviewDebugEntry({
        level: event.level || 'error',
        source: sourceLabels[event.source] || event.source || 'preview',
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
        line: event.line,
        context: event.context,
        stack: event.stack,
        timestamp: event.timestamp
    });
}

function togglePreview() {
    const preview = document.getElementById('preview-pane');
    const showBtn = document.getElementById('show-preview-btn');

    previewCollapsed = !previewCollapsed;

    if (isMobile) {
        if (previewCollapsed) {
            preview.classList.remove('open');
            showBtn.classList.remove('hidden');
        } else {
            preview.classList.add('open');
            showBtn.classList.add('hidden');
        }
    } else {
        preview.classList.toggle('collapsed', previewCollapsed);
    }

    localStorage.setItem('previewCollapsed', previewCollapsed);
}

function updateCodeDisplay() {
    // Code display removed from UI, but keep state updated
    // for preview functionality
}

async function runPreview() {
    initPreviewDebugPane();
    resetPreviewDebugPane();

    const container = document.getElementById('preview-container');

    if (!container) {
        console.error('runPreview: preview-container element not found!');
        appendPreviewDebugEntry({
            level: 'error',
            source: 'preview',
            message: 'Preview area was not found, so the project could not run.'
        });
        return;
    }

    const language = (project && project.language) ? project.language : 'p5js';

    if (language === 'python') {
        container.innerHTML = '<p class="preview-placeholder">Python code runs on your computer. Copy the code and run it locally with Python installed.</p>';
        resetPreviewDebugPane('Python previews run locally, so browser debug signals are unavailable here.');
        return;
    }

    sandboxRunner = new SandboxRunner('preview-container', {
        onEvent: handlePreviewSandboxEvent
    });

    const hasIndexHtml = projectFiles.some(f => f.filename === 'index.html');

    if (hasIndexHtml) {
        try {
            const response = await apiRequest(`/projects/${projectId}/preview-bundle`);
            if (response && response.success && response.files) {
                const bundledHtml = buildPreviewBundle(response.files);
                sandboxRunner.runHTML(bundledHtml);
                return;
            }

            appendPreviewDebugEntry({
                level: 'error',
                source: 'preview',
                message: 'The preview bundle did not return usable files.'
            });
        } catch (error) {
            console.error('Error loading preview bundle:', error);
            appendPreviewDebugEntry({
                level: 'error',
                source: 'preview',
                message: `Could not load preview files: ${error.message || 'Unknown error'}`
            });
        }
    }

    if (!currentCode || !currentCode.trim()) {
        container.innerHTML = '<p class="preview-placeholder">Your project preview will appear here.</p>';
        resetPreviewDebugPane('No code to preview yet. When the preview runs, runtime errors and console.error will show up here.');
        return;
    }

    sandboxRunner.run(currentCode, language);
}

function buildPreviewBundle(files) {
    let indexHtml = files['index.html'] || '';

    const cssFiles = Object.keys(files).filter(f => f.endsWith('.css'));
    let cssInjection = '';
    cssFiles.forEach(filename => {
        const cssContent = files[filename] || '';
        cssInjection += `\n<style data-file="${filename}">\n${cssContent}\n</style>\n`;
    });

    if (indexHtml.includes('</head>')) {
        indexHtml = indexHtml.replace('</head>', `${cssInjection}</head>`);
    } else if (indexHtml.includes('<head>')) {
        indexHtml = indexHtml.replace('<head>', `<head>${cssInjection}`);
    } else if (indexHtml.includes('<html>')) {
        indexHtml = indexHtml.replace('<html>', `<html><head>${cssInjection}</head>`);
    } else {
        indexHtml = `<head>${cssInjection}</head>\n${indexHtml}`;
    }

    const jsFiles = Object.keys(files).filter(f => f.endsWith('.js'));

    jsFiles.forEach(filename => {
        const jsContent = files[filename] || '';
        const scriptRegex = new RegExp(`<script[^>]*src=["']${filename}["'][^>]*>\\s*</script>`, 'gi');
        const inlineScript = `<script data-file="${filename}">\n${jsContent}\n</script>`;
        indexHtml = indexHtml.replace(scriptRegex, inlineScript);
    });

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
