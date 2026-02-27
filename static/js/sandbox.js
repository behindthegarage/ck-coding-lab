// sandbox.js - Secure client-side code execution

class SandboxRunner {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.iframe = null;
        this.config = {
            maxExecutionTime: 5000,
            maxFrames: 100000,
            timeoutId: null,
            isWebGL: false
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
        
        // Detect WEBGL mode for longer timeout
        this.config.isWebGL = code.includes('WEBGL') || code.includes('webgl');
        if (this.config.isWebGL) {
            this.config.maxExecutionTime = 15000;
            console.log("SandboxRunner: WEBGL detected, using 15s timeout");
        } else {
            this.config.maxExecutionTime = 5000;
        }
        
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
            console.log("SandboxRunner: HTML iframe loaded");
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
        
        // Set timeout for infinite loop protection
        this.config.timeoutId = setTimeout(() => {
            this.stop('Execution timeout (infinite loop protection). Try refreshing or simplifying your code.');
        }, this.config.maxExecutionTime);
        
        this.iframe.srcdoc = html;
        
        this.iframe.onload = () => {
            console.log("SandboxRunner: p5.js iframe loaded");
            this.loaded = true;
            this._runOnLoadCallbacks();
            this._doFocus();
        };
        
        this._messageHandler = this.handleMessage.bind(this);
        window.addEventListener('message', this._messageHandler);
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
        // Escape user code to prevent breaking out of the script tag
        const escapedCode = userCode.replace(/<\/script>/gi, '<\\/script>');
        
        return `<!DOCTYPE html>
<html>
<head>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/p5.js/1.9.0/p5.min.js"><\/script>
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
            max-width: 90%;
        }
    </style>
</head>
<body>
    <div id="error-display"></div>
    <script>
        // Wrap everything in try-catch for better error reporting
        try {
            // Track if we've successfully rendered
            let firstFrameRendered = false;
            let frameCount = 0;
            const maxFrames = 100000;
            
            // Store original setup and draw
            let userSetup = null;
            let userDraw = null;
            
            // Override setup to catch errors
            Object.defineProperty(window, 'setup', {
                get: function() { return userSetup; },
                set: function(fn) { 
                    userSetup = function() {
                        try {
                            fn();
                            parent.postMessage({type: 'setupComplete'}, '*');
                        } catch (e) {
                            console.error('Setup error:', e);
                            showError('Setup Error: ' + e.message);
                            parent.postMessage({type: 'error', message: 'Setup: ' + e.message}, '*');
                        }
                    };
                }
            });
            
            // Override draw to add frame limit and error handling
            Object.defineProperty(window, 'draw', {
                get: function() { return userDraw; },
                set: function(fn) { 
                    userDraw = function() {
                        frameCount++;
                        if (!firstFrameRendered) {
                            firstFrameRendered = true;
                            parent.postMessage({type: 'firstFrame'}, '*');
                        }
                        if (frameCount > maxFrames) {
                            noLoop();
                            showError('Stopped: too many frames (possible infinite loop)');
                            parent.postMessage({type: 'error', message: 'Frame limit reached'}, '*');
                            return;
                        }
                        try {
                            fn();
                        } catch (e) {
                            console.error('Draw error:', e);
                            showError('Draw Error (line ~' + frameCount + '): ' + e.message);
                            parent.postMessage({type: 'error', message: 'Draw: ' + e.message}, '*');
                        }
                    };
                }
            });
            
            function showError(msg) {
                const el = document.getElementById('error-display');
                if (el) el.textContent = msg;
            }
            
            // Global error handler
            window.onerror = function(msg, url, line, col, error) {
                console.error('Global error:', msg, 'at', line);
                showError('Error: ' + msg + (line ? ' (line ' + line + ')' : ''));
                parent.postMessage({type: 'error', message: String(msg), line: line}, '*');
                return true;
            };
            
            // Block dangerous functions
            window.eval = function() { throw new Error('eval is disabled'); };
            window.Function = function() { throw new Error('Function constructor is disabled'); };
            
            // User code
            ${escapedCode}
            
        } catch (e) {
            console.error('Code loading error:', e);
            document.getElementById('error-display').textContent = 'Error loading code: ' + e.message;
            parent.postMessage({type: 'error', message: 'Load: ' + e.message}, '*');
        }
        
        // Auto-focus
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(function() {
                const canvas = document.querySelector('canvas');
                if (canvas) { canvas.focus(); canvas.click(); }
                document.body.focus();
            }, 100);
        });
    <\/script>
</body>
</html>`;
    }
    
    handleMessage(event) {
        if (!event.data) return;
        
        if (event.data.type === 'error') {
            console.error('Sandbox error:', event.data.message);
        } else if (event.data.type === 'firstFrame') {
            console.log('SandboxRunner: First frame rendered, clearing timeout');
            if (this.config.timeoutId) {
                clearTimeout(this.config.timeoutId);
                this.config.timeoutId = null;
            }
        } else if (event.data.type === 'setupComplete') {
            console.log('SandboxRunner: Setup completed');
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
                <p style="font-size: 0.875rem; color: #94a3b8;">Try refreshing the preview or simplifying your code.</p>
            </div>`;
        }
        
        if (this._messageHandler) {
            window.removeEventListener('message', this._messageHandler);
        }
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
