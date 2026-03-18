// sandbox.js - Secure client-side code execution
// Preview iframes must keep an opaque origin so user code cannot read
// CK Coding Lab auth/session state from the parent app.

const PREVIEW_SANDBOX_PERMISSIONS = 'allow-scripts';
const PREVIEW_LOAD_TIMEOUT_MS = 4000;

class SandboxRunner {
    constructor(containerId, options = {}) {
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
        this.eventSink = typeof options.onEvent === 'function' ? options.onEvent : null;
        this._messageHandler = null;
        this._loadTimeoutId = null;
    }

    setEventSink(onEvent) {
        this.eventSink = typeof onEvent === 'function' ? onEvent : null;
    }

    reportEvent(event = {}) {
        if (typeof this.eventSink !== 'function') {
            return;
        }

        try {
            this.eventSink({
                timestamp: Date.now(),
                ...event
            });
        } catch (error) {
            console.error('SandboxRunner event handler failed:', error);
        }
    }

    run(code, language = 'p5js') {
        console.log('SandboxRunner.run() called with code length:', code ? code.length : 0, 'language:', language);
        this.cleanup();

        if (!this.container) {
            console.error('SandboxRunner: container element not found!');
            this.reportEvent({
                type: 'load-failure',
                level: 'error',
                source: 'preview',
                message: 'Preview container was not found.'
            });
            return;
        }

        if (!code || !code.trim()) {
            console.log('SandboxRunner: no code provided, showing placeholder');
            this.container.innerHTML = '<p class="preview-placeholder">Your project preview will appear here.</p>';
            return;
        }

        const trimmedCode = code.trim();
        const looksLikeHTML = trimmedCode.startsWith('<') || trimmedCode.startsWith('<!');

        // Detect WEBGL mode for longer timeout
        this.config.isWebGL = code.includes('WEBGL') || code.includes('webgl');
        if (this.config.isWebGL) {
            this.config.maxExecutionTime = 15000;
            console.log('SandboxRunner: WEBGL detected, using 15s timeout');
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
        this._attachMessageHandler();
        this._scheduleLoadTimeout('Preview did not finish loading.');

        this.iframe = document.createElement('iframe');
        this.iframe.style.width = '100%';
        this.iframe.style.height = '100%';
        this.iframe.style.border = 'none';
        this.iframe.sandbox = PREVIEW_SANDBOX_PERMISSIONS;

        this.container.innerHTML = '';
        this.container.appendChild(this.iframe);

        this.iframe.srcdoc = this.instrumentHTML(htmlCode);

        this.iframe.onload = () => {
            console.log('SandboxRunner: HTML iframe loaded');
            this._clearLoadTimeout();
            this.loaded = true;
            this._runOnLoadCallbacks();
            this._doFocus();
        };
    }

    runP5JS(userCode) {
        this.loaded = false;
        this.onLoadCallbacks = [];

        const html = this.buildP5SandboxHTML(userCode);
        this._attachMessageHandler();
        this._scheduleLoadTimeout('Preview did not finish loading.');

        this.iframe = document.createElement('iframe');
        this.iframe.style.width = '100%';
        this.iframe.style.height = '100%';
        this.iframe.style.border = 'none';
        this.iframe.sandbox = PREVIEW_SANDBOX_PERMISSIONS;

        this.container.innerHTML = '';
        this.container.appendChild(this.iframe);

        // Set timeout for infinite loop protection
        this.config.timeoutId = setTimeout(() => {
            this.stop('Execution timeout (infinite loop protection). Try refreshing or simplifying your code.');
        }, this.config.maxExecutionTime);

        this.iframe.srcdoc = html;

        this.iframe.onload = () => {
            console.log('SandboxRunner: p5.js iframe loaded');
            this._clearLoadTimeout();
            this.loaded = true;
            this._runOnLoadCallbacks();
            this._doFocus();
        };
    }

    _attachMessageHandler() {
        if (this._messageHandler) {
            window.removeEventListener('message', this._messageHandler);
        }
        this._messageHandler = this.handleMessage.bind(this);
        window.addEventListener('message', this._messageHandler);
    }

    _scheduleLoadTimeout(message) {
        this._clearLoadTimeout();
        this._loadTimeoutId = setTimeout(() => {
            if (!this.loaded) {
                this.reportEvent({
                    type: 'load-failure',
                    level: 'error',
                    source: 'preview',
                    message
                });
            }
        }, PREVIEW_LOAD_TIMEOUT_MS);
    }

    _clearLoadTimeout() {
        if (this._loadTimeoutId) {
            clearTimeout(this._loadTimeoutId);
            this._loadTimeoutId = null;
        }
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
            console.log('SandboxRunner: focus error:', e.message);
        }
    }

    _runOnLoadCallbacks() {
        while (this.onLoadCallbacks.length > 0) {
            const cb = this.onLoadCallbacks.shift();
            try {
                cb();
            } catch (e) {
                console.error('OnLoad callback error:', e);
            }
        }
    }

    onReady(callback) {
        if (this.loaded) {
            try {
                callback();
            } catch (e) {
                console.error('OnReady callback error:', e);
            }
        } else {
            this.onLoadCallbacks.push(callback);
        }
    }

    buildPreviewBridgeScript() {
        return `<script>
(function() {
    const serialize = (value) => {
        try {
            if (value instanceof Error) {
                return value.stack || value.message || String(value);
            }
            if (typeof value === 'string') {
                return value;
            }
            const jsonValue = JSON.stringify(value);
            if (typeof jsonValue === 'string') {
                return jsonValue;
            }
            return String(value);
        } catch (error) {
            try {
                return String(value);
            } catch (stringError) {
                return '[unserializable value]';
            }
        }
    };

    const post = (payload) => {
        try {
            parent.postMessage(Object.assign({ __ckPreview: true, timestamp: Date.now() }, payload), '*');
        } catch (error) {
            // Ignore postMessage failures inside the preview sandbox.
        }
    };

    window.__CKPreviewBridge = { post, serialize };

    const wrapConsole = (level) => {
        const original = console[level];
        if (typeof original !== 'function') {
            return;
        }

        console[level] = function(...args) {
            if (level === 'error' || level === 'warn') {
                post({
                    type: 'console',
                    level,
                    source: 'console',
                    message: args.map(serialize).join(' ')
                });
            }
            return original.apply(this, args);
        };
    };

    wrapConsole('error');
    wrapConsole('warn');

    window.addEventListener('error', function(event) {
        post({
            type: 'runtime-error',
            level: 'error',
            source: 'runtime',
            message: event.message || serialize(event.error) || 'Unknown runtime error',
            filename: event.filename || '',
            lineno: event.lineno || 0,
            colno: event.colno || 0,
            stack: event.error && event.error.stack ? event.error.stack : ''
        });
    });

    window.addEventListener('unhandledrejection', function(event) {
        const reason = event.reason;
        post({
            type: 'unhandledrejection',
            level: 'error',
            source: 'promise',
            message: serialize(reason),
            stack: reason && reason.stack ? reason.stack : ''
        });
    });
})();
<\/script>`;
    }

    instrumentHTML(htmlCode) {
        const bridgeScript = this.buildPreviewBridgeScript();
        const source = htmlCode || '';

        if (/<head[\s>]/i.test(source)) {
            return source.replace(/<head([^>]*)>/i, `<head$1>${bridgeScript}`);
        }

        if (/<body[\s>]/i.test(source)) {
            return source.replace(/<body([^>]*)>/i, `<body$1>${bridgeScript}`);
        }

        if (/<html[\s>]/i.test(source)) {
            return source.replace(/<html([^>]*)>/i, `<html$1><head>${bridgeScript}</head>`);
        }

        return `<!DOCTYPE html><html><head>${bridgeScript}</head><body>${source}</body></html>`;
    }

    buildP5SandboxHTML(userCode) {
        // Escape user code to prevent breaking out of the script tag
        const escapedCode = userCode.replace(/<\/script>/gi, '<\\/script>');
        const previewBridgeScript = this.buildPreviewBridgeScript();

        return `<!DOCTYPE html>
<html>
<head>
    ${previewBridgeScript}
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
    </style>
</head>
<body>
    <div id="error-display"></div>
    <script>
        const sendPreviewEvent = (payload) => {
            if (window.__CKPreviewBridge && typeof window.__CKPreviewBridge.post === 'function') {
                window.__CKPreviewBridge.post(payload);
            } else {
                parent.postMessage(payload, '*');
            }
        };

        // Global error handler
        window.onerror = function(msg, url, line, col, error) {
            console.error('Sketch error:', msg, 'at line', line);
            const el = document.getElementById('error-display');
            if (el) el.textContent = 'Error: ' + msg + (line ? ' (line ' + line + ')' : '');
            sendPreviewEvent({
                type: 'runtime-error',
                level: 'error',
                source: 'p5',
                message: String(msg),
                filename: url || '',
                lineno: line || 0,
                colno: col || 0,
                stack: error && error.stack ? error.stack : ''
            });
            return true;
        };

        // Block dangerous functions
        window.eval = function() { throw new Error('eval is disabled'); };
        window.Function = function() { throw new Error('Function constructor is disabled'); };

        // Store original functions before user code defines them
        let _userSetup = null;
        let _userDraw = null;

        // Override global function definitions to capture them
        const originalDefineProperty = Object.defineProperty;
        Object.defineProperty = function(obj, prop, desc) {
            if (obj === window && (prop === 'setup' || prop === 'draw')) {
                console.log('Capturing', prop, 'definition');
                if (prop === 'setup') _userSetup = desc.value || desc.get;
                if (prop === 'draw') _userDraw = desc.value || desc.get;
            }
            return originalDefineProperty.apply(this, arguments);
        };

        // Load user code in global scope - NO IIFE!
        try {
            ${escapedCode}
        } catch (e) {
            console.error('Code loading error:', e);
            document.getElementById('error-display').textContent = 'Error loading code: ' + e.message;
            sendPreviewEvent({
                type: 'runtime-error',
                level: 'error',
                source: 'p5',
                message: 'Load: ' + e.message,
                stack: e && e.stack ? e.stack : ''
            });
        }

        // Restore defineProperty
        Object.defineProperty = originalDefineProperty;

        // Also check for directly assigned functions
        if (typeof setup === 'function' && !_userSetup) {
            _userSetup = setup;
        }
        if (typeof draw === 'function' && !_userDraw) {
            _userDraw = draw;
        }

        // Now wrap and assign the functions
        if (_userSetup) {
            console.log('Wrapping setup...');
            window.setup = function() {
                try {
                    _userSetup.apply(this, arguments);
                    sendPreviewEvent({type: 'setupComplete'});
                } catch (e) {
                    console.error('Setup error:', e);
                    document.getElementById('error-display').textContent = 'Setup Error: ' + e.message;
                    sendPreviewEvent({
                        type: 'runtime-error',
                        level: 'error',
                        source: 'p5',
                        message: 'Setup: ' + e.message,
                        stack: e && e.stack ? e.stack : ''
                    });
                }
            };
        }

        if (_userDraw) {
            console.log('Wrapping draw...');
            let frameCount = 0;
            const maxFrames = 100000;
            let firstFrame = true;

            window.draw = function() {
                frameCount++;

                if (firstFrame) {
                    firstFrame = false;
                    sendPreviewEvent({type: 'firstFrame'});
                }

                if (frameCount > maxFrames) {
                    noLoop();
                    document.getElementById('error-display').textContent = 'Stopped: too many frames';
                    sendPreviewEvent({
                        type: 'runtime-error',
                        level: 'error',
                        source: 'p5',
                        message: 'Frame limit reached'
                    });
                    return;
                }

                try {
                    _userDraw.apply(this, arguments);
                } catch (e) {
                    console.error('Draw error:', e);
                    document.getElementById('error-display').textContent = 'Draw Error: ' + e.message;
                    sendPreviewEvent({
                        type: 'runtime-error',
                        level: 'error',
                        source: 'p5',
                        message: 'Draw: ' + e.message,
                        stack: e && e.stack ? e.stack : ''
                    });
                }
            };
        }

        console.log('Sandbox initialized, setup:', typeof setup, 'draw:', typeof draw);
    <\/script>
</body>
</html>`;
    }

    handleMessage(event) {
        if (!event.data || !this.iframe || event.source !== this.iframe.contentWindow) {
            return;
        }

        const payload = event.data && event.data.__ckPreview ? event.data : event.data;

        if (payload.type === 'console' && (payload.level === 'error' || payload.level === 'warn')) {
            this.reportEvent(payload);
        } else if (payload.type === 'runtime-error' || payload.type === 'unhandledrejection' || payload.type === 'load-failure') {
            this.reportEvent(payload);
        } else if (payload.type === 'error') {
            this.reportEvent({
                type: 'runtime-error',
                level: 'error',
                source: 'p5',
                message: payload.message,
                line: payload.line
            });
        } else if (payload.type === 'firstFrame') {
            console.log('SandboxRunner: First frame rendered, clearing timeout');
            if (this.config.timeoutId) {
                clearTimeout(this.config.timeoutId);
                this.config.timeoutId = null;
            }
        } else if (payload.type === 'setupComplete') {
            console.log('SandboxRunner: Setup completed');
        }
    }

    stop(reason) {
        if (this.config.timeoutId) {
            clearTimeout(this.config.timeoutId);
            this.config.timeoutId = null;
        }

        this._clearLoadTimeout();

        if (this.iframe) {
            this.iframe.remove();
            this.iframe = null;
        }

        if (reason) {
            this.reportEvent({
                type: 'runtime-error',
                level: 'error',
                source: 'preview',
                message: reason
            });

            this.container.innerHTML = `<div style="color: #ef4444; padding: 20px;">
                <p>⚠️ ${reason}</p>
                <p style="font-size: 0.875rem; color: #94a3b8;">Try refreshing the preview or simplifying your code.</p>
            </div>`;
        }

        if (this._messageHandler) {
            window.removeEventListener('message', this._messageHandler);
            this._messageHandler = null;
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
