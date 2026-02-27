// sandbox.js - Secure client-side code execution

class SandboxRunner {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.iframe = null;
        this.config = {
            maxExecutionTime: 5000,  // Default 5s for simple sketches
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
            this.config.maxExecutionTime = 15000;  // 15 seconds for WEBGL
            console.log("SandboxRunner: WEBGL detected, using 15s timeout");
        } else {
            this.config.maxExecutionTime = 5000;  // 5 seconds for normal sketches
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
        
        // Listen for messages from iframe (errors AND success)
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
        const isWebGL = this.config.isWebGL;
        
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
            max-width: 90%;
        }
        #success-display {
            color: #10b981;
            padding: 10px;
            font-family: monospace;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div id="error-display"></div>
    <script>
        // Track if we've successfully rendered
        let firstFrameRendered = false;
        let frameCount = 0;
        const maxFrames = 100000;
        
        // Error handling with better messages
        window.onerror = function(msg, url, line, col, error) {
            console.error('Sketch error:', msg, 'at line', line);
            let errorMsg = 'Error: ' + msg;
            if (line && line > 0) {
                errorMsg += '\\nLine: ' + line;
            }
            document.getElementById('error-display').textContent = errorMsg;
            parent.postMessage({type: 'error', message: msg, line: line}, '*');
            return true;
        };
        
        // Catch unhandled promise rejections
        window.onunhandledrejection = function(event) {
            console.error('Unhandled promise rejection:', event.reason);
            parent.postMessage({type: 'error', message: 'Promise error: ' + event.reason}, '*');
        };
        
        // Override p5.js setup to track successful initialization
        const originalSetup = window.setup;
        window.setup = function() {
            try {
                if (originalSetup) originalSetup();
                // Notify parent that setup completed
                parent.postMessage({type: 'setupComplete'}, '*');
            } catch (e) {
                console.error('Setup error:', e);
                document.getElementById('error-display').textContent = 'Setup Error: ' + e.message;
                parent.postMessage({type: 'error', message: 'Setup error: ' + e.message}, '*');
            }
        };
        
        // Override p5.js draw to add frame limit and track first frame
        const originalDraw = window.draw;
        window.draw = function() {
            frameCount++;
            
            // Notify parent on first successful frame
            if (!firstFrameRendered) {
                firstFrameRendered = true;
                parent.postMessage({type: 'firstFrame'}, '*');
            }
            
            if (frameCount > maxFrames) {
                noLoop();
                console.warn('Sketch stopped: frame limit reached');
                document.getElementById('error-display').textContent = 
                    'Sketch stopped: too many frames (possible infinite loop)';
                parent.postMessage({type: 'error', message: 'Frame limit reached'}, '*');
                return;
            }
            
            try {
                if (originalDraw) originalDraw();
            } catch (e) {
                console.error('Draw error:', e);
                document.getElementById('error-display').textContent = 'Draw Error: ' + e.message;
                parent.postMessage({type: 'error', message: 'Draw error: ' + e.message}, '*');
            }
        };
        
        // Block dangerous globals
        window.eval = function() { throw new Error('eval is disabled'); };
        window.Function = function() { throw new Error('Function constructor is disabled'); };
        
        // User code
        try {
            ${escapedCode}
        } catch (e) {
            console.error('Code error:', e);
            document.getElementById('error-display').textContent = 'Code Error: ' + e.message;
            parent.postMessage({type: 'error', message: 'Code error: ' + e.message}, '*');
        }
        
        // Auto-focus canvas for keyboard input
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
        if (!event.data) return;
        
        if (event.data.type === 'error') {
            console.error('Sandbox error:', event.data.message);
            // Don't stop on errors - let the sketch continue if possible
        } else if (event.data.type === 'firstFrame') {
            // Clear timeout on successful first frame
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
