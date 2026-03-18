import json

from projects.state import (
    build_project_state,
    choose_primary_code_file,
    materialize_version_files,
    restore_version_snapshot,
    sync_current_code_cache,
)


class TestProjectState:
    def _create_project(self, db_connection, language='p5js', current_code=''):
        db_connection.execute(
            "INSERT INTO users (username, pin_hash) VALUES (?, ?)",
            ('state_user', 'hash')
        )
        user_id = db_connection.lastrowid
        db_connection.execute(
            '''
            INSERT INTO projects (user_id, name, description, current_code, language)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (user_id, 'State Project', 'desc', current_code, language)
        )
        return db_connection.lastrowid

    def test_choose_primary_code_file_prefers_language_entrypoint(self):
        files = {
            'main.js': 'console.log(1);',
            'index.html': '<html></html>',
            'styles.css': 'body {}',
        }

        assert choose_primary_code_file('html', files) == 'index.html'
        assert choose_primary_code_file('p5js', files) == 'main.js'

    def test_build_project_state_prefers_project_files_over_stale_current_code(self, db_connection):
        project_id = self._create_project(
            db_connection,
            language='html',
            current_code='stale current_code'
        )
        db_connection.execute(
            '''
            INSERT INTO project_files (project_id, filename, content)
            VALUES (?, ?, ?)
            ''',
            (project_id, 'index.html', '<h1>real source of truth</h1>')
        )

        state = build_project_state(
            db_connection,
            project_id,
            'html',
            fallback_current_code='stale current_code'
        )

        assert state['primary_file'] == 'index.html'
        assert state['current_code'] == '<h1>real source of truth</h1>'

    def test_build_project_state_synthesizes_primary_file_for_legacy_code(self, db_connection):
        project_id = self._create_project(
            db_connection,
            language='python',
            current_code='print("hello")'
        )

        state = build_project_state(
            db_connection,
            project_id,
            'python',
            fallback_current_code='print("hello")',
            synthesize_primary_file=True
        )

        assert state['primary_file'] == 'main.py'
        assert state['snapshot_files']['main.py'] == 'print("hello")'

    def test_sync_current_code_cache_updates_project_from_primary_file(self, db_connection):
        project_id = self._create_project(
            db_connection,
            language='p5js',
            current_code='old code'
        )
        db_connection.execute(
            '''
            INSERT INTO project_files (project_id, filename, content)
            VALUES (?, ?, ?)
            ''',
            (project_id, 'sketch.js', 'function draw() { ellipse(1, 2, 3, 4); }')
        )

        state = sync_current_code_cache(
            db_connection,
            project_id,
            'p5js',
            fallback_current_code='old code',
            touch_project=False
        )

        db_connection.execute('SELECT current_code FROM projects WHERE id = ?', (project_id,))
        row = db_connection.fetchone()

        assert 'ellipse' in state['current_code']
        assert row['current_code'] == state['current_code']

    def test_materialize_version_files_prefers_snapshot_over_stale_code(self):
        files, entry_filename = materialize_version_files(
            'html',
            code='stale legacy blob',
            files_snapshot=json.dumps({
                'index.html': '<html><body>fresh</body></html>',
                'main.js': 'console.log("fresh")',
            }),
            entry_filename='index.html'
        )

        assert entry_filename == 'index.html'
        assert files == {
            'index.html': '<html><body>fresh</body></html>',
            'main.js': 'console.log("fresh")',
        }

    def test_restore_version_snapshot_replaces_files_and_heals_current_code(self, db_connection):
        project_id = self._create_project(
            db_connection,
            language='p5js',
            current_code='stale current code'
        )
        db_connection.execute(
            '''
            INSERT INTO project_files (project_id, filename, content)
            VALUES (?, ?, ?)
            ''',
            (project_id, 'main.js', 'console.log("old")')
        )
        db_connection.execute(
            '''
            INSERT INTO project_files (project_id, filename, content)
            VALUES (?, ?, ?)
            ''',
            (project_id, 'notes.md', 'old notes')
        )

        state = restore_version_snapshot(
            db_connection,
            project_id,
            'p5js',
            code='function draw() { background(0); }',
            files_snapshot=None,
            entry_filename=None,
        )

        db_connection.execute(
            'SELECT filename, content FROM project_files WHERE project_id = ? ORDER BY filename',
            (project_id,)
        )
        files = {row['filename']: row['content'] for row in db_connection.fetchall()}
        db_connection.execute('SELECT current_code FROM projects WHERE id = ?', (project_id,))
        row = db_connection.fetchone()

        assert files == {'sketch.js': 'function draw() { background(0); }'}
        assert state['restored_entry_filename'] == 'sketch.js'
        assert row['current_code'] == 'function draw() { background(0); }'
