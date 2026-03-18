// workspace-preview.js - Preview helpers extracted from workspace.js

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
    const container = document.getElementById('preview-container');

    if (!container) {
        console.error('runPreview: preview-container element not found!');
        return;
    }

    const language = (project && project.language) ? project.language : 'p5js';

    if (language === 'python') {
        container.innerHTML = '<p class="preview-placeholder">Python code runs on your computer. Copy the code and run it locally with Python installed.</p>';
        return;
    }

    sandboxRunner = new SandboxRunner('preview-container');

    const hasIndexHtml = projectFiles.some(f => f.filename === 'index.html');

    if (hasIndexHtml) {
        try {
            const response = await apiRequest(`/projects/${projectId}/preview-bundle`);
            if (response && response.success && response.files) {
                const bundledHtml = buildPreviewBundle(response.files);
                sandboxRunner.runHTML(bundledHtml);
                return;
            }
        } catch (e) {
            console.error('Error loading preview bundle:', e);
        }
    }

    if (!currentCode || !currentCode.trim()) {
        container.innerHTML = '<p class="preview-placeholder">Your project preview will appear here.</p>';
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
