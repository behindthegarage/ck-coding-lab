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
    }
    
    /**
     * Run code in isolated iframe sandbox
     * @param {string} code - The code to run
     * @param {string} language - 'p5js' or 'html'
     */
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
        
        // Check if HTML mode or code looks like HTML (after trimming whitespace)
        const trimmedCode = code.trim();
        const firstChar = trimmedCode.charCodeAt(0);
        const firstFewChars = trimmedCode.substring(0, 10).split('').map(c => c.charCodeAt(0));
        const looksLikeHTML = trimmedCode.startsWith('<') || trimmedCode.startsWith('<!');
        console.log("SandboxRunner: first 100 chars:", JSON.stringify(trimmedCode.substring(0, 100)));
        console.log("SandboxRunner: first char code:", firstChar, "char:", trimmedCode[0]);
        console.log("SandboxRunner: first 10 char codes:", firstFewChars);
        console.log("SandboxRunner: looksLikeHTML:", looksLikeHTML, "language:", language);
        console.log("SandboxRunner: condition check - language===html:", language === 'html', "|| looksLikeHTML:", looksLikeHTML);
        
        if (language === 'html' || looksLikeHTML) {
            console.log("SandboxRunner: rendering as HTML");
            this.runHTML(code);
        } else {
            console.log("SandboxRunner: rendering as p5.js");
            this.runP5JS(code);
        }
    }
    
    /**
     * Run HTML code directly
     */
    runHTML(htmlCode) {
        // Create sandbox iframe
        this.iframe = document.createElement('iframe');
        this.iframe.style.width = '100%';
        this.iframe.style.height = '100%';
        this.iframe.style.border = 'none';
        this.iframe.sandbox = 'allow-scripts allow-same-origin';
        
        console.log("SandboxRunner: clearing container for HTML...");
        this.container.innerHTML = '';
        this.container.appendChild(this.iframe);
        
        // NO timeout for HTML mode - it's a full page, not a p5.js sketch
        // HTML pages may have intentional continuous animation/game loops
        
        // Load HTML content
        console.log("SandboxRunner: setting iframe srcdoc for HTML...");
        this.iframe.srcdoc = htmlCode;
        console.log("SandboxRunner: HTML iframe srcdoc set");
        
        // Auto-focus for keyboard input
        this.iframe.onload = () => {
            console.log("SandboxRunner: HTML iframe loaded, focusing...");
            this.iframe.focus();
            try {
                this.iframe.contentWindow.focus();
            } catch (e) {
                // Cross-origin restrictions may prevent this
            }
        };
    }
    
    /**
     * Run p5.js code
     */
    runP5JS(userCode) {
        // Build HTML with protections
        const html = this.buildP5SandboxHTML(userCode);
        
        // Create sandbox iframe
        this.iframe = document.createElement('iframe');
        this.iframe.style.width = '100%';
        this.iframe.style.height = '100%';
        this.iframe.style.border = 'none';
        this.iframe.sandbox = 'allow-scripts allow-same-origin';
        
        console.log("SandboxRunner: clearing container...");
        this.container.innerHTML = '';
        this.container.appendChild(this.iframe);
        console.log("SandboxRunner: iframe appended to container");
        
        // Set timeout for infinite loop protection
        this.config.timeoutId = setTimeout(() => {
            this.stop('Execution timeout (infinite loop protection)');
        }, this.config.maxExecutionTime);
        
        // Load content
        console.log("SandboxRunner: setting iframe srcdoc...");
        this.iframe.srcdoc = html;
        console.log("SandboxRunner: iframe srcdoc set");
        
        // Auto-focus for keyboard input
        this.iframe.onload = () => {
            console.log("SandboxRunner: p5.js iframe loaded, focusing...");
            this.focus();
        };
        
        // Listen for errors from iframe
        window.addEventListener('message', this.handleMessage.bind(this));
    }
    
    /**
     * Build sandbox HTML for p5.js with protections
     */
    buildP5SandboxHTML(userCode) {
        // Escape user code to prevent breaking out of the script tag
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
        // Error handling
        window.onerror = function(msg, url, line, col, error) {
            console.error('Sketch error:', msg, 'at line', line);
            document.getElementById('error-display').textContent = 
                'Error: ' + msg + '\\nLine: ' + line;
            parent.postMessage({type: 'error', message: msg, line: line}, '*');
            return true;
        };
        
        // Frame limit protection
        let frameCount = 0;
        const maxFrames = ${this.config.maxFrames};
        
        // Override p5.js draw to add frame limit
        const originalDraw = window.draw;
        window.draw = function() {
            frameCount++;
            if (frameCount > maxFrames) {
                noLoop();
                console.warn('Sketch stopped: frame limit reached');
                document.getElementById('error-display').textContent = 
                    'Sketch stopped: too many frames (possible infinite loop)';
                return;
            }
            if (originalDraw) originalDraw();
        };
        
        // Block dangerous globals
        window.eval = function() { throw new Error('eval is disabled'); };
        window.Function = function() { throw new Error('Function constructor is disabled'); };
        
        // User code
        try {
            ${escapedCode}
        } catch (e) {
            console.error('Code error:', e);
            document.getElementById('error-display').textContent = 
                'Error: ' + e.message;
        }
    </script>
</body>
</html>`;
    }
    
    /**
     * Handle messages from iframe
     */
    handleMessage(event) {
        if (event.data && event.data.type === 'error') {
            console.error('Sandbox error:', event.data.message);
            // Could bubble up to UI here
        }
    }
    
    /**
     * Stop execution and cleanup
     */
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
                <p style="font-size: 0.875rem; color: #94a3b8;">Try simplifying your code or check for infinite loops.</p>
            </div>`;
        }
        
        window.removeEventListener('message', this.handleMessage.bind(this));
    }
    
    /**
     * Focus the iframe for keyboard input
     */
    focus() {
        if (this.iframe) {
            console.log("SandboxRunner: focusing iframe...");
            this.iframe.focus();
            try {
                this.iframe.contentWindow.focus();
                // Also try to focus the canvas if it exists (for p5.js games)
                const canvas = this.iframe.contentDocument?.querySelector('canvas');
                if (canvas) {
                    canvas.focus();
                    canvas.click(); // Some games need a click to capture input
                }
            } catch (e) {
                // Cross-origin restrictions may prevent this
                console.log("SandboxRunner: cross-origin focus prevented");
            }
        }
    }
    
    /**
     * Cleanup resources
     */
    cleanup() {
        this.stop();
    }
}

// Export for use in workspace.js
window.SandboxRunner = SandboxRunner;
