"""Tests for post-edit JavaScript validation helpers."""

from ai.validation import format_validation_error, validate_javascript_files


class TestJavaScriptValidation:
    def test_validate_javascript_files_returns_none_for_valid_js(self):
        error = validate_javascript_files({
            'sketch.js': 'function setup() { return 1; }\nconst x = 2;'
        }, language='p5js')

        assert error is None

    def test_validate_javascript_files_reports_syntax_error(self):
        error = validate_javascript_files({
            'sketch.js': "fill(item.bought ? 30, 41, 59 : 30, 41, 59);"
        }, language='p5js')

        assert error is not None
        assert error['filename'] == 'sketch.js'
        assert error['line'] == 1
        assert "SyntaxError:" in error['message']

    def test_format_validation_error_includes_location(self):
        text = format_validation_error({
            'filename': 'sketch.js',
            'line': 111,
            'column': 26,
            'message': "SyntaxError: Unexpected token ','",
        })

        assert text == "sketch.js (line 111, col 26): SyntaxError: Unexpected token ','"
