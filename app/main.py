import asyncio
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import tempfile
import uuid
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from .database import Database
from .exports import build_pdf, export_lines
from .worker import BUSY, Worker, probe_audio, snapshot

STATIC = Path(__file__).parent / 'static'
MAX_UPLOAD = 4 * 1024**3


class ProjectPatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=160)
    reference: str | None = Field(None, max_length=100000)
    terms: str | None = Field(None, max_length=400)
    speakers: dict[str, str] | None = None


class SegmentPatch(BaseModel):
    text: str = Field(min_length=1, max_length=12000)
    speaker: str = Field(min_length=1, max_length=80)
    reviewed: bool
    version: int = Field(ge=1)


class SettingsPatch(BaseModel):
    whisper_model: str = Field(min_length=1, max_length=1000)
    device: Literal['cuda', 'cpu']
    compute_type: Literal['float16', 'float32', 'int8']
    ollama_model: str = Field(min_length=1, max_length=100)
    diarization_model: str = Field(default='', max_length=1000)


class DraftRequest(BaseModel):
    kind: Literal['summary', 'mayor', 'article', 'report', 'polished']
    reviewed_only: bool = True
    speaker: str | None = Field(None, max_length=80)


def extract_terms(reference):
    match = re.search(r'\[8\.\s*음성인식용 압축 용어 목록\]\s*([^\[]*)', reference)
    if not match:
        return ''
    value = match.group(1).strip().strip('`').strip().lstrip('- ').strip()
    if '자료에 없음' in value:
        return ''
    # A short, explicitly editable hint; never feed the entire reference into ASR.
    return ', '.join(t.strip() for t in re.split('[,\n]', value) if t.strip())[:400]


def create_app(data_dir=None, start_worker=True):
    root = Path(data_dir or os.environ.get('VOICE_ARCHIVE_DATA', Path(__file__).resolve().parent.parent / 'data')).resolve()

    @asynccontextmanager
    async def lifespan(app):
        app.state.db = Database(root)
        app.state.worker = Worker(app.state.db) if start_worker else None
        yield
        if app.state.worker:
            app.state.worker.close()

    app = FastAPI(title='목소리 기록실', lifespan=lifespan, docs_url=None, redoc_url=None)

    @app.middleware('http')
    async def local_only(request: Request, call_next):
        host = request.url.hostname
        if host not in {'127.0.0.1', 'localhost', '::1', 'testserver'}:
            return JSONResponse({'detail': '이 앱은 로컬 PC에서만 접속할 수 있습니다.'}, 403)
        if request.method in {'POST', 'PATCH', 'DELETE', 'PUT'}:
            origin = request.headers.get('origin')
            if origin and urlparse(origin).netloc != request.headers.get('host'):
                return JSONResponse({'detail': '다른 사이트에서의 요청은 허용하지 않습니다.'}, 403)
            if request.headers.get('x-voice-archive') != '1':
                return JSONResponse({'detail': '앱 화면에서 요청해 주세요.'}, 403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'"
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    def db():
        return app.state.db

    def project_or_404(identifier):
        project = db().project(identifier)
        if not project:
            raise HTTPException(404, '녹음을 찾을 수 없습니다.')
        return project

    def public_project(project):
        result = {k: v for k, v in project.items() if k != 'audio_path'}
        result['speakers'] = json.loads(result['speakers'])
        result['peaks'] = json.loads(result['peaks'])
        return result

    def worker():
        if not app.state.worker:
            raise HTTPException(503, '작업 처리기가 실행되지 않았습니다.')
        return app.state.worker

    @app.get('/api/projects')
    def projects():
        with db().connect() as conn:
            rows = conn.execute('''SELECT p.*, COUNT(s.id) AS segment_count, COALESCE(SUM(s.reviewed),0) AS reviewed_count
                                   FROM projects p LEFT JOIN segments s ON p.id=s.project_id
                                   GROUP BY p.id ORDER BY p.created_at DESC''').fetchall()
        return [public_project(dict(row)) for row in rows]

    @app.post('/api/projects', status_code=201)
    async def upload(file: UploadFile = File(), title: str = Form(''), kind: str = Form('타운홀 미팅'),
                     reference: str = Form('')):
        if kind not in {'타운홀 미팅', '회의', '현장 발언'}:
            raise HTTPException(422, '지원하지 않는 녹음 유형입니다.')
        if len(title) > 160 or len(reference) > 100000:
            raise HTTPException(422, '제목 또는 참고정보가 너무 깁니다.')
        filename = (file.filename or 'audio').replace('\\', '/').split('/')[-1]
        extension = Path(filename).suffix.lower()
        if extension not in {'.wav', '.mp3', '.m4a', '.flac', '.ogg', '.mp4'}:
            raise HTTPException(422, 'WAV, MP3, M4A, FLAC, OGG, MP4 파일을 지원합니다.')
        identifier = str(uuid.uuid4())
        folder = root / 'recordings' / identifier
        folder.mkdir(parents=True)
        path = folder / ('original' + extension)
        try:
            size = 0
            with path.open('wb') as output:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_UPLOAD:
                        raise HTTPException(413, '파일 한 개는 최대 4GB까지 지원합니다.')
                    output.write(chunk)
            try:
                duration = await asyncio.to_thread(probe_audio, path)
            except (ValueError, RuntimeError) as exc:
                raise HTTPException(422, str(exc)) from exc
            with db().connect() as conn:
                conn.execute('INSERT INTO projects(id,title,kind,filename,audio_path,duration,reference,terms) VALUES(?,?,?,?,?,?,?,?)',
                             (identifier, title.strip() or Path(filename).stem, kind, filename, str(path), duration, reference, extract_terms(reference)))
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        finally:
            await file.close()
        return public_project(project_or_404(identifier))

    @app.get('/api/projects/{identifier}')
    def detail(identifier: str):
        project = project_or_404(identifier)
        result = public_project(project)
        result['segments'] = [{**s, 'flags': json.loads(s['flags'])} for s in db().segments(identifier)]
        with db().connect() as conn:
            drafts = [dict(r) for r in conn.execute('SELECT * FROM drafts WHERE project_id=? ORDER BY created_at DESC', (identifier,))]
        current = snapshot(project, result['segments'])
        for draft in drafts:
            draft['content'] = json.loads(draft['content'])
            draft['stale'] = bool(draft['input_snapshot'] and draft['input_snapshot'] != current)
            del draft['input_snapshot']
        result['drafts'] = drafts
        return result

    @app.patch('/api/projects/{identifier}')
    def edit_project(identifier: str, payload: ProjectPatch):
        project = project_or_404(identifier)
        fields = payload.model_dump(exclude_none=True)
        if project['status'] in BUSY and ('terms' in fields or 'reference' in fields):
            raise HTTPException(409, '인식 작업을 일시 중지한 뒤 참고정보를 수정해 주세요.')
        if 'title' in fields:
            fields['title'] = fields['title'].strip()
            if not fields['title']:
                raise HTTPException(422, '제목을 입력해 주세요.')
        if 'speakers' in fields:
            if len(fields['speakers']) > 100 or any(not k or len(k) > 80 or not v.strip() or len(v) > 80 for k, v in fields['speakers'].items()):
                raise HTTPException(422, '화자 이름은 1~80자로 입력해 주세요.')
            fields['speakers'] = json.dumps(fields['speakers'], ensure_ascii=False)
        if fields:
            with db().connect() as conn:
                conn.execute('UPDATE projects SET ' + ','.join(f'{k}=?' for k in fields) + ' WHERE id=?', (*fields.values(), identifier))
        return public_project(project_or_404(identifier))

    @app.delete('/api/projects/{identifier}')
    def delete_project(identifier: str):
        project = project_or_404(identifier)
        with db().connect() as conn:
            active = conn.execute("SELECT 1 FROM drafts WHERE project_id=? AND status IN ('queued','running')", (identifier,)).fetchone()
            if project['status'] in BUSY or active:
                raise HTTPException(409, '진행 중인 작업이 끝난 뒤 삭제해 주세요.')
            conn.execute('DELETE FROM projects WHERE id=?', (identifier,))
        shutil.rmtree(root / 'recordings' / identifier, ignore_errors=True)
        return {'ok': True}

    @app.get('/api/projects/{identifier}/audio')
    def audio(identifier: str):
        project = project_or_404(identifier)
        return FileResponse(project['audio_path'])

    @app.post('/api/projects/{identifier}/transcribe')
    def transcribe(identifier: str):
        w = worker()
        with w.lock:
            project = project_or_404(identifier)
            if project['status'] in BUSY:
                raise HTTPException(409, '이미 처리 중입니다.')
            if project['status'] == 'completed':
                raise HTTPException(409, '완료된 녹취입니다. 다시 분석하려면 새 녹음으로 추가해 주세요.')
            settings = db().settings()
            if not (Path(settings['whisper_model']).expanduser() / 'model.bin').is_file():
                raise HTTPException(422, 'Whisper 모델이 없습니다. 설정에서 설치 안내와 모델 경로를 확인해 주세요.')
            db().update_project(identifier, status='queued', error='', message='처리 순서를 기다리고 있습니다.')
            w.submit('transcribe', identifier)
        return {'status': 'queued'}

    @app.post('/api/projects/{identifier}/pause')
    def pause(identifier: str):
        project = project_or_404(identifier)
        if project['status'] not in BUSY:
            raise HTTPException(409, '진행 중인 인식 작업이 없습니다.')
        worker().cancel(identifier)
        db().update_project(identifier, status='canceling', message='현재 구간을 저장한 뒤 일시 중지합니다.')
        return {'ok': True}

    @app.patch('/api/segments/{identifier}')
    def edit_segment(identifier: int, payload: SegmentPatch):
        with db().connect() as conn:
            row = conn.execute('SELECT * FROM segments WHERE id=?', (identifier,)).fetchone()
            if not row:
                raise HTTPException(404, '발언을 찾을 수 없습니다.')
            if payload.version != row['version']:
                raise HTTPException(409, '다른 화면에서 수정되었습니다. 새로고침 후 다시 수정해 주세요.')
            conn.execute('INSERT INTO revisions(segment_id,text,speaker,reviewed) VALUES(?,?,?,?)',
                         (identifier, row['text'], row['speaker'], row['reviewed']))
            conn.execute('UPDATE segments SET text=?,speaker=?,reviewed=?,version=version+1 WHERE id=?',
                         (payload.text, payload.speaker, payload.reviewed, identifier))
        return {'version': payload.version + 1}

    @app.get('/api/segments/{identifier}/history')
    def history(identifier: int):
        with db().connect() as conn:
            return [dict(r) for r in conn.execute('SELECT * FROM revisions WHERE segment_id=? ORDER BY id DESC', (identifier,))]

    @app.post('/api/projects/{identifier}/drafts', status_code=202)
    def generate(identifier: str, payload: DraftRequest):
        project = project_or_404(identifier)
        if project['status'] != 'completed':
            raise HTTPException(409, '음성인식을 완료한 뒤 생성할 수 있습니다.')
        w = worker()
        with w.lock:
            with db().connect() as conn:
                if conn.execute("SELECT 1 FROM drafts WHERE project_id=? AND status IN ('queued','running')", (identifier,)).fetchone():
                    raise HTTPException(409, '이 녹음의 초안을 이미 생성하고 있습니다.')
                segments = db().segments(identifier)
                chosen = [s for s in segments if not payload.reviewed_only or s['reviewed']]
                if not chosen:
                    raise HTTPException(422, '먼저 발언을 검토 완료로 표시해 주세요.')
                if payload.kind == 'mayor' and not any(s['speaker'] == payload.speaker for s in chosen):
                    raise HTTPException(422, '시장님 화자를 지정하고 해당 발언을 검토 완료로 표시해 주세요.')
                draft_id = str(uuid.uuid4())
                conn.execute('INSERT INTO drafts(id,project_id,kind,status,reviewed_only) VALUES(?,?,?,?,?)',
                             (draft_id, identifier, payload.kind, 'queued', payload.reviewed_only))
            w.submit('draft', draft_id, payload.model_dump())
        return {'id': draft_id}

    @app.get('/api/projects/{identifier}/export')
    def export(identifier: str, format: Literal['txt', 'pdf'] = 'txt',
               mode: Literal['original', 'edited', 'reviewed'] = 'edited', draft: str | None = None):
        project = project_or_404(identifier)
        selected = None
        if draft:
            with db().connect() as conn:
                row = conn.execute("SELECT * FROM drafts WHERE id=? AND project_id=? AND status='completed'", (draft, identifier)).fetchone()
                if not row:
                    raise HTTPException(404, '완료된 초안을 찾을 수 없습니다.')
                selected = dict(row)
            if selected['input_snapshot'] != snapshot(project, db().segments(identifier)):
                raise HTTPException(409, '녹취 또는 참고정보가 바뀐 이전 초안입니다. 다시 생성한 뒤 내보내 주세요.')
        lines = export_lines(project, db().segments(identifier), mode, selected)
        if format == 'txt':
            return Response('\n'.join(lines), media_type='text/plain; charset=utf-8',
                            headers={'Content-Disposition': 'attachment; filename="transcript.txt"'})
        fd, name = tempfile.mkstemp(suffix='.pdf')
        os.close(fd)
        path = Path(name)
        try:
            build_pdf(path, lines)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return FileResponse(path, media_type='application/pdf', filename='transcript.pdf',
                            background=BackgroundTask(path.unlink, missing_ok=True))

    @app.get('/api/settings')
    def settings():
        return db().settings()

    @app.put('/api/settings')
    def save_settings(payload: SettingsPatch):
        if payload.device == 'cpu' and payload.compute_type == 'float16':
            raise HTTPException(422, 'CPU에서는 float32 또는 int8을 선택해 주세요.')
        with db().connect() as conn:
            active = conn.execute("SELECT 1 FROM projects WHERE status IN ('queued','converting','transcribing','diarizing','canceling')").fetchone()
            active_draft = conn.execute("SELECT 1 FROM drafts WHERE status IN ('queued','running')").fetchone()
            if active or active_draft:
                raise HTTPException(409, '처리 중인 작업을 마친 뒤 설정을 바꿔 주세요.')
            for key, value in payload.model_dump().items():
                conn.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, json.dumps(value)))
        return db().settings()

    @app.get('/api/health')
    async def health():
        settings = db().settings()
        ollama_models, ollama_online = [], False
        try:
            async with httpx.AsyncClient(timeout=2, trust_env=False) as client:
                response = await client.get('http://127.0.0.1:11434/api/tags')
                response.raise_for_status()
                ollama_models = [m['name'] for m in response.json().get('models', [])]
                ollama_online = True
        except (httpx.HTTPError, ValueError, KeyError):
            pass
        return {'ffmpeg': bool(shutil.which('ffmpeg') and shutil.which('ffprobe')),
                'whisper_package': importlib.util.find_spec('faster_whisper') is not None,
                'whisper_model': (Path(settings['whisper_model']).expanduser() / 'model.bin').is_file(),
                'ollama_online': ollama_online, 'ollama_models': ollama_models,
                'selected_ollama_model': settings['ollama_model'],
                'diarization_configured': bool(settings['diarization_model']), 'data_dir': str(root)}

    @app.get('/api/reference-prompt')
    def reference_prompt():
        return {'text': (Path(__file__).parent / 'reference_prompt.txt').read_text(encoding='utf-8')}

    @app.get('/api/backup')
    def backup():
        with db().connect() as conn:
            if conn.execute("SELECT 1 FROM projects WHERE status IN ('queued','converting','transcribing','diarizing','canceling')").fetchone():
                raise HTTPException(409, '인식 작업이 멈춘 뒤 백업해 주세요.')
        folder = Path(tempfile.mkdtemp(prefix='voice-archive-backup-'))
        try:
            copy_path = folder / 'archive.sqlite3'
            with sqlite3.connect(db().path) as source, sqlite3.connect(copy_path) as target:
                source.backup(target)
            zip_path = folder / 'voice-archive-backup.zip'
            with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(copy_path, 'data/archive.sqlite3')
                for path in (root / 'recordings').glob('*/original.*'):
                    archive.write(path, str(Path('data') / path.relative_to(root)))
                archive.writestr('RESTORE.txt', '앱을 종료한 뒤 data 폴더를 복원하세요. 다른 경로로 복원했다면 python scripts/restore_paths.py 를 실행하세요. 모델은 별도 설치 대상입니다.')
        except Exception:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        return FileResponse(zip_path, filename='voice-archive-backup.zip', background=BackgroundTask(shutil.rmtree, folder))

    app.mount('/static', StaticFiles(directory=STATIC), name='static')

    @app.get('/')
    def index():
        return FileResponse(STATIC / 'index.html')

    return app


app = create_app()
