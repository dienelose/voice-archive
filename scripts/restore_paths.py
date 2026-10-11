"""Run with the app stopped after restoring a backup to a different directory."""
import os
import sqlite3
from pathlib import Path

root = Path(os.environ.get('VOICE_ARCHIVE_DATA', Path(__file__).resolve().parents[1] / 'data')).resolve()
if not (root / 'archive.sqlite3').exists():
    raise SystemExit('No database found. Restore the data folder first.')
with sqlite3.connect(root / 'archive.sqlite3') as db:
    rows = db.execute('SELECT id, audio_path FROM projects').fetchall()
    updates = []
    for identifier, old in rows:
        candidates = list((root / 'recordings' / identifier).glob('original.*'))
        if len(candidates) != 1:
            raise SystemExit(f'Missing or ambiguous original audio: {identifier}; no paths were changed.')
        updates.append((str(candidates[0]), identifier))
    db.executemany('UPDATE projects SET audio_path=? WHERE id=?', updates)
print(f'Updated {len(updates)} audio paths. Check model paths in app settings after starting.')
