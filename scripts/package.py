"""Build a source bundle without recordings, secrets, models or virtual environments."""
import hashlib
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
destination = root / 'dist'
destination.mkdir(exist_ok=True)
archive_path = destination / 'voice-archive-windows.zip'
files = [root / name for name in ['README.md', 'VALIDATION.md', 'start.bat', '.gitignore', '.gitattributes']]
files += list(root.glob('requirements*.txt'))
for directory in ['app', 'scripts', 'tests']:
    files += [p for p in (root / directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(files):
        archive.write(path, str(Path('voice-archive') / path.relative_to(root)))
with zipfile.ZipFile(archive_path) as archive:
    assert archive.testzip() is None
checksum = hashlib.sha256(archive_path.read_bytes()).hexdigest()
(destination / 'SHA256SUMS.txt').write_text(f'{checksum}  {archive_path.name}\n', encoding='utf-8')
print(f'{archive_path} ({archive_path.stat().st_size:,} bytes)')
