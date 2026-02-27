// sandbox.js - Secure client-side code execution

class SandboxRunner {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.iframe = null;
        this.config = {
            maxExecutionTime: 5000,
            maxFrames: 100000,
            timeoutId: null
        };
        this.loaded = false;
        this.onLoadCallbacks = [];
    }
    
    run(code, language = 'p5js') {
        console.log("SandboxRunner.run() called with code length:", code ? code.length : 0, "language:", language);
        this.cleanup();
        
        if (!this.container) {
            console.error("SandboxRunner: container element not found!");
            return;
        }
        
        if (!code || !code.trim()) {
            console.log("SandboxRunner: no code provided, showing placeholder");
            this.container.innerHTML = '<p class="preview-placeholder">Your project preview will appear here.</p>';
            return;
        }
        
        const trimmedCode = code.trim();
        const looksLikeHTML = trimmedCode.startsWith('<') || trimmedCode.startsWith('<!');
        
        if (language === 'html' || looksLikeHTML) {
            this.runHTML(code);
        } else {
            this.runP5JS(code);
        }
    }
    
    runHTML(htmlCode) {
        this.loaded = false;
        this.onLoadCallbacks = [];
        
        this.iframe = document.createElement('iframe');
        this.iframe.style.width = '100%';
        this.iframe.style.height = '100%';
        this.iframe.style.border = 'none';
        this.iframe.sandbox = 'allow-scripts allow-same-origin';
        
        this.container.innerHTML = '';
        this.container.appendChild(this.iframe);
        
        this.iframe.srcdoc = htmlCode;
        
        this.iframe.onload = () => {
            this.loaded = true;
            this._runOnLoadCallbacks();
            this._doFocus();
        };
    }
    
    runP5JS(userCode) {
        this.loaded = false;
        this.onLoadCallbacks = [];
        
        const html = this.buildP5SandboxHTML(userCode);
        
        this.iframe = document.createElement('iframe');
        this.iframe.style.width = '100%';
        this.iframe.style.height = '100%';
        this.iframe.style.border = 'none';
        this.iframe.sandbox = 'allow-scripts allow-same-origin';
        
        this.container.innerHTML = '';
        this.container.appendChild(this.iframe);
        
        this.config.timeoutId = setTimeout(() => {
            this.stop('Execution timeout (infinite loop protection)');
        }, this.config.maxExecutionTime);
        
        this.iframe.srcdoc = html;
        
        this.iframe.onload = () => {
            this.loaded = true;
            this._runOnLoadCallbacks();
            this._doFocus();
        };
        
        window.addEventListener('message', this.handleMessage.bind(this));
    }
    
    _doFocus() {
        if (!this.iframe) return;
        
        this.iframe.focus();
        try {
            this.iframe.contentWindow.focus();
            const doc = this.iframe.contentDocument;
            if (doc) {
                if (doc.body) {
                    doc.body.focus();
                    doc.body.click();
                }
                const canvas = doc.querySelector('canvas');
                if (canvas) {
                    canvas.focus();
                    canvas.click();
                }
            }
        } catch (e) {
            console.log("SandboxRunner: focus error:", e.message);
        }
    }
    
    _runOnLoadCallbacks() {
        while (this.onLoadCallbacks.length > 0) {
            const cb = this.onLoadCallbacks.shift();
            try { cb(); } catch (e) { console.error("OnLoad callback error:", e); }
        }
    }
    
    onReady(callback) {
        if (this.loaded) {
            try { callback(); } catch (e) { console.error("OnReady callback error:", e); }
        } else {
            this.onLoadCallbacks.push(callback);
        }
    }
    
    buildP5SandboxHTML(userCode) {
        const escapedCode = userCode.replace(/<\/script>/gi, '<\\/script>');
        
        return `<!DOCTYPE html>
<html>
<head>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/p5.js/1.9.0/p5.min.js"></script>
    <style>
        body { 
            margin: 0; 
            padding: 0; 
            overflow: hidden; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            min-height: 100vh; 
            background: #0f172a; 
        }
        canvas { display: block; }
        #error-display {
            color: #ef4444;
            padding: 20px;
            font-family: monospace;
            white-space: pre-wrap;
        }
    </style>
</head>
<body>
    <div id="error-display"></div>
    <script>
        window.onerror = function(msg, url, line, col, error) {
            console.error('Sketch error:', msg, 'at line', line);
            document.getElementById('error-display').textContent = 
                'Error: ' + msg + '\\nLine: ' + line;
            parent.postMessage({type: 'error', message: msg, line: line}, '*');
            return true;
        };
        
        let frameCount = 0;
        const maxFrames = 100000;
        
        const originalDraw = window.draw;
        window.draw = function() {
            frameCount++;
            if (frameCount > maxFrames) {
                noLoop();
                console.warn('Sketch stopped: frame limit reached');
                document.getElementById('error-display').textContent = 
                    'Sketch stopped: too many frames';
                return;
            }
            if (originalDraw) originalDraw();
        };
        
        window.eval = function() { throw new Error('eval is disabled'); };
        window.Function = function() { throw new Error('Function constructor is disabled'); };
        
        try {
            ${escapedCode}
        } catch (e) {
            console.error('Code error:', e);
            document.getElementById('error-display').textContent = 
                'Error: ' + e.message;
        }
        
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(function() {
                const canvas = document.querySelector('canvas');
                if (canvas) {
                    canvas.focus();
                    canvas.click();
                }
                document.body.focus();
            }, 100);
        });
    </script>
</body>
</html>`;
    }
    
    handleMessage(event) {
        if (event.data && event.data.type === 'error') {
            console.error('Sandbox error:', event.data.message);
        }
    }
    
    stop(reason) {
        if (this.config.timeoutId) {
            clearTimeout(this.config.timeoutId);
            this.config.timeoutId = null;
        }
        
        if (this.iframe) {
            this.iframe.remove();
            this.iframe = null;
        }
        
        if (reason) {
            this.container.innerHTML = `<div style="color: #ef4444; padding: 20px;">
                <p>⚠️ ${reason}</p>
                <p style="font-size: 0.875rem; color: #94a3b8;">Try simplifying your code.</p>
            </div>`;
        }
        
        window.removeEventListener('message', this.handleMessage.bind(this));
    }
    
    focus() {
        if (this.loaded) {
            this._doFocus();
        } else {
            this.onReady(() => this._doFocus());
        }
    }
    
    cleanup() {
        this.stop();
    }
}

window.SandboxRunner = SandboxRunner;
