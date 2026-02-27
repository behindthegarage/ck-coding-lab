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
        canvas { 
            display: block; 
            box-shadow: 0 0 20px rgba(99, 102, 241, 0.3);
        }
        #error-display {
            color: #ef4444;
            padding: 20px;
            font-family: monospace;
            white-space: pre-wrap;
            max-width: 90%;
            font-size: 14px;
        }
        #debug-info {
            position: fixed;
            top: 10px;
            left: 10px;
            color: #10b981;
            font-family: monospace;
            font-size: 12px;
            background: rgba(0,0,0,0.7);
            padding: 10px;
            border-radius: 4px;
            z-index: 1000;
            max-width: 300px;
        }
    </style>
</head>
<body>
    <div id="error-display"></div>
    <div id="debug-info">Initializing...</div>
    <script>
        // Debug logging
        let debugInfo = document.getElementById('debug-info');
        function log(msg) {
            console.log(msg);
            if (debugInfo) debugInfo.textContent += '\\n' + msg;
        }
        
        // Global error handler
        window.onerror = function(msg, url, line, col, error) {
            console.error('Sketch error:', msg, 'at line', line);
            log('ERROR: ' + msg + (line ? ' (line ' + line + ')' : ''));
            const el = document.getElementById('error-display');
            if (el) el.textContent = 'Error: ' + msg + (line ? ' (line ' + line + ')' : '');
            parent.postMessage({type: 'error', message: String(msg), line: line}, '*');
            return true;
        };
        
        // Block dangerous functions
        window.eval = function() { throw new Error('eval is disabled'); };
        window.Function = function() { throw new Error('Function constructor is disabled'); };
        
        // Wait for p5.js to be ready, then load user code
        if (typeof p5 !== 'undefined') {
            // p5.js already loaded, wait a tick for it to init
            setTimeout(initSketch, 10);
        } else {
            // Wait for p5.js to load
            window.addEventListener('load', function() {
                setTimeout(initSketch, 100);
            });
        }
        
        function initSketch() {
            log('p5.js ready, loading user code...');
            
            try {
                // Load user code - functions will be defined on window
                ${escapedCode}
                
                log('User code executed');
                
                // Now wrap the functions
                wrapFunctions();
                
                // Start p5.js manually if functions exist
                if (typeof window.setup === 'function') {
                    log('Starting p5.js...');
                    new p5();
                } else {
                    log('No setup() found');
                }
            } catch (e) {
                console.error('Error:', e);
                log('ERROR: ' + e.message);
                document.getElementById('error-display').textContent = 'Error: ' + e.message;
                parent.postMessage({type: 'error', message: e.message}, '*');
            }
        }
        
        function wrapFunctions() {
            log('Checking for functions...');
            
            // Wrap setup if it exists
            if (typeof window.setup === 'function' && !window.setup.__wrapped) {
                const originalSetup = window.setup;
                window.setup = function() {
                    try {
                        log('setup() starting...');
                        originalSetup();
                        log('setup() done');
                        parent.postMessage({type: 'setupComplete'}, '*');
                    } catch (e) {
                        console.error('Setup error:', e);
                        log('Setup ERROR: ' + e.message);
                        document.getElementById('error-display').textContent = 'Setup Error: ' + e.message;
                        parent.postMessage({type: 'error', message: 'Setup: ' + e.message}, '*');
                    }
                };
                window.setup.__wrapped = true;
                log('setup() wrapped');
            }
            
            // Wrap draw if it exists
            if (typeof window.draw === 'function' && !window.draw.__wrapped) {
                const originalDraw = window.draw;
                let frameCount = 0;
                const maxFrames = 100000;
                let firstFrame = true;
                
                window.draw = function() {
                    frameCount++;
                    
                    if (firstFrame) {
                        firstFrame = false;
                        log('First frame!');
                        parent.postMessage({type: 'firstFrame'}, '*');
                    }
                    
                    if (frameCount > maxFrames) {
                        noLoop();
                        log('Stopped: frame limit');
                        document.getElementById('error-display').textContent = 'Stopped: too many frames';
                        parent.postMessage({type: 'error', message: 'Frame limit reached'}, '*');
                        return;
                    }
                    
                    try {
                        originalDraw();
                    } catch (e) {
                        console.error('Draw error:', e);
                        log('Draw ERROR: ' + e.message);
                        document.getElementById('error-display').textContent = 'Draw Error: ' + e.message;
                        parent.postMessage({type: 'error', message: 'Draw: ' + e.message}, '*');
                    }
                };
                window.draw.__wrapped = true;
                log('draw() wrapped');
            }
        }
        
        log('Waiting for p5.js...');
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
