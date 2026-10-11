import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, kind TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 filename TEXT NOT NULL, audio_path TEXT NOT NULL, duration REAL NOT NULL,
 status TEXT NOT NULL DEFAULT 'uploaded', progress REAL NOT NULL DEFAULT 0,
 message TEXT NOT NULL DEFAULT '', reference TEXT NOT NULL DEFAULT '',
 terms TEXT NOT NULL DEFAULT '', speakers TEXT NOT NULL DEFAULT '{}',
 next_chunk INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '',
 diarization_status TEXT NOT NULL DEFAULT 'not_started',
 peaks TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS segments (
 id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 start REAL NOT NULL, end REAL NOT NULL, original_text TEXT NOT NULL, text TEXT NOT NULL,
 speaker TEXT NOT NULL DEFAULT 'speaker_1', reviewed INTEGER NOT NULL DEFAULT 0,
 flags TEXT NOT NULL DEFAULT '[]', version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS segment_order ON segments(project_id, start);
CREATE TABLE IF NOT EXISTS revisions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, segment_id INTEGER NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
 text TEXT NOT NULL, speaker TEXT NOT NULL, reviewed INTEGER NOT NULL,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS drafts (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 kind TEXT NOT NULL, status TEXT NOT NULL, content TEXT NOT NULL DEFAULT '[]',
 error TEXT NOT NULL DEFAULT '', reviewed_only INTEGER NOT NULL DEFAULT 1,
 input_snapshot TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


class Database:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / 'archive.sqlite3'
        with self.connect() as db:
            db.executescript(SCHEMA)
            db.execute("UPDATE projects SET status='paused', message='앱이 종료되어 작업이 멈췄습니다. 이어서 처리할 수 있습니다.' WHERE status IN ('queued','converting','transcribing','diarizing','canceling')")
            db.execute("UPDATE drafts SET status='error', error='앱 종료로 생성이 중단되었습니다. 다시 생성해 주세요.' WHERE status IN ('queued','running')")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA journal_mode=WAL')
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def project(self, project_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()
        return dict(row) if row else None

    def update_project(self, project_id, **fields):
        allowed = {'status','progress','message','next_chunk','error','peaks','diarization_status'}
        assert set(fields) <= allowed
        with self.connect() as db:
            db.execute('UPDATE projects SET ' + ','.join(f'{key}=?' for key in fields) + ' WHERE id=?', (*fields.values(), project_id))

    def settings(self):
        defaults = {
            'whisper_model': str(self.root.parent / 'models' / 'whisper-large-v3'),
            'device': 'cuda', 'compute_type': 'float16',
            'ollama_model': 'qwen3:8b',
            'diarization_model': '',
        }
        with self.connect() as db:
            defaults.update({r['key']: json.loads(r['value']) for r in db.execute('SELECT * FROM settings')})
        return defaults

    def segments(self, project_id):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM segments WHERE project_id=? ORDER BY start,id', (project_id,))]
