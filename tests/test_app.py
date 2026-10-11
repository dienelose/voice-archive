import io
import json
import sqlite3
import subprocess
import sys
import threading
import types
import wave
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database import Database
from app.main import create_app, extract_terms
from app.worker import Worker, assign_speakers, snapshot

HEADERS = {'X-Voice-Archive': '1'}


def audio_bytes(seconds=2):
    output = io.BytesIO()
    with wave.open(output, 'wb') as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(16000)
        file.writeframes(b'\0\0' * (16000 * seconds))
    return output.getvalue()


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / 'data', start_worker=False)
    with TestClient(app, headers=HEADERS) as client:
        yield client


def upload(client, **data):
    response = client.post('/api/projects', files={'file': ('회의.wav', audio_bytes(), 'audio/wav')},
                           data={'title': '주민과의 대화', **data})
    assert response.status_code == 201, response.text
    return response.json()


def seed_segment(client, project, text='사업 예산은 13억 원입니다.'):
    with client.app.state.db.connect() as db:
        row = db.execute('INSERT INTO segments(project_id,start,end,original_text,text) VALUES(?,?,?,?,?)',
                         (project['id'], 0, 1.7, text, text))
        return row.lastrowid


def test_real_wav_upload_range_and_reference(client):
    project = upload(client, reference='[8. 음성인식용 압축 용어 목록]\n도시재생, 김시장')
    assert project['terms'] == '도시재생, 김시장'
    assert project['duration'] == 2
    assert 'audio_path' not in project
    response = client.get(f"/api/projects/{project['id']}/audio", headers={'Range': 'bytes=0-43'})
    assert response.status_code == 206
    assert response.content[:4] == b'RIFF'
    assert len(response.content) == 44


def test_invalid_audio_is_rejected_and_removed(client):
    response = client.post('/api/projects', files={'file': ('fake.mp3', b'not audio', 'audio/mpeg')})
    assert response.status_code == 422
    assert client.get('/api/projects').json() == []
    assert list((client.app.state.db.root / 'recordings').iterdir()) == []


def test_same_origin_and_host_restrictions(client):
    assert client.post('/api/projects', headers={'x-voice-archive': ''}).status_code == 403
    assert client.post('/api/projects', headers={'origin': 'https://malicious.example'}).status_code == 403
    assert client.get('/api/settings', headers={'host': 'malicious.example'}).status_code == 403
    assert client.get('/').headers['content-security-policy'].find("frame-ancestors 'none'") >= 0


def test_edit_history_optimistic_lock_and_original_export(client):
    project = upload(client)
    identifier = seed_segment(client, project)
    body = {'text': '사업 예산은 30억 원입니다.', 'speaker': 'speaker_1', 'reviewed': True, 'version': 1}
    assert client.patch(f'/api/segments/{identifier}', json=body).json()['version'] == 2
    assert client.patch(f'/api/segments/{identifier}', json=body).status_code == 409
    detail = client.get(f"/api/projects/{project['id']}").json()
    assert detail['segments'][0]['original_text'] == '사업 예산은 13억 원입니다.'
    assert detail['segments'][0]['text'] == body['text']
    history = client.get(f'/api/segments/{identifier}/history').json()
    assert len(history) == 1 and history[0]['text'] == '사업 예산은 13억 원입니다.'
    export = client.get(f"/api/projects/{project['id']}/export?mode=original")
    assert '13억' in export.text and '30억' not in export.text
    export = client.get(f"/api/projects/{project['id']}/export?mode=reviewed")
    assert '30억' in export.text


def test_korean_pdf_contains_embedded_font(client):
    project = upload(client)
    seed_segment(client, project, '<확인> 시장님 주요 발언 & 예산 13억 원')
    response = client.get(f"/api/projects/{project['id']}/export?format=pdf")
    assert response.status_code == 200
    assert response.content.startswith(b'%PDF')
    assert b'/FontFile2' in response.content
    assert b'/ToUnicode' in response.content


def test_backup_and_delete_preserve_other_projects(client):
    first, second = upload(client), upload(client, title='다른 녹음')
    seed_segment(client, first)
    backup = client.get('/api/backup')
    assert backup.status_code == 200
    with zipfile.ZipFile(io.BytesIO(backup.content)) as archive:
        assert 'data/archive.sqlite3' in archive.namelist()
        assert len([name for name in archive.namelist() if '/original.' in name]) == 2
    assert client.delete(f"/api/projects/{first['id']}").status_code == 200
    assert client.get(f"/api/projects/{first['id']}").status_code == 404
    assert client.get(f"/api/projects/{second['id']}/audio").status_code == 200


def test_busy_protects_reference_and_deletion(client):
    project = upload(client)
    client.app.state.db.update_project(project['id'], status='transcribing')
    assert client.patch(f"/api/projects/{project['id']}", json={'reference': '새 자료'}).status_code == 409
    assert client.delete(f"/api/projects/{project['id']}").status_code == 409
    assert client.get('/api/backup').status_code == 409


def test_stale_draft_cannot_be_exported(client):
    project = upload(client)
    seed_segment(client, project)
    database = client.app.state.db
    snap = snapshot(database.project(project['id']), database.segments(project['id']))
    with database.connect() as db:
        db.execute('INSERT INTO drafts(id,project_id,kind,status,input_snapshot) VALUES(?,?,?,?,?)',
                   ('draft', project['id'], 'summary', 'completed', snap))
    assert client.get(f"/api/projects/{project['id']}/export?draft=draft").status_code == 200
    client.patch(f"/api/projects/{project['id']}", json={'reference': '새 참고정보'})
    assert client.get(f"/api/projects/{project['id']}").json()['drafts'][0]['stale'] is True
    assert client.get(f"/api/projects/{project['id']}/export?draft=draft").status_code == 409


def test_restart_marks_interrupted_work_and_preserves_checkpoint(tmp_path):
    database = Database(tmp_path)
    with database.connect() as db:
        db.execute("INSERT INTO projects(id,title,kind,filename,audio_path,duration,status,next_chunk) VALUES('p','t','회의','a.wav','a.wav',700,'transcribing',2)")
    restored = Database(tmp_path)
    assert restored.project('p')['status'] == 'paused'
    assert restored.project('p')['next_chunk'] == 2


def test_term_extraction_does_not_use_entire_reference():
    assert extract_terms('긴 배경 설명과 예정 발언') == ''
    assert extract_terms('[8. 음성인식용 압축 용어 목록]\n자료에 없음') == ''
    assert len(extract_terms('[8. 음성인식용 압축 용어 목록]\n' + '가,'*500)) <= 400


def test_speaker_assignment_preserves_human_edits():
    segments = [{'id':1,'start':0,'end':4,'reviewed':0,'version':1},
                {'id':2,'start':4,'end':8,'reviewed':1,'version':1},
                {'id':3,'start':8,'end':12,'reviewed':0,'version':2}]
    assert assign_speakers(segments, [(0, 3, 'A'), (3, 12, 'B')]) == [('A', 1)]


def make_worker(database):
    worker = Worker.__new__(Worker)
    worker.db = database
    worker.lock = threading.RLock()
    worker.canceled = set()
    worker.stopping = threading.Event()
    return worker


def test_transcription_checkpoint_retries_without_duplicates(client, monkeypatch, tmp_path):
    """Fake inference tests orchestration, not speech accuracy; conversion is real FFmpeg."""
    import sys
    import app.worker as module
    project = upload(client)
    database = client.app.state.db
    model_dir = tmp_path / 'model'
    model_dir.mkdir()
    (model_dir / 'model.bin').write_bytes(b'test fixture, not a real model')
    with database.connect() as db:
        db.execute('INSERT INTO settings VALUES(?,?)', ('whisper_model', json.dumps(str(model_dir))))
    monkeypatch.setattr(module, 'CHUNK_SECONDS', 1)
    monkeypatch.setattr(module, 'OVERLAP_SECONDS', 0)
    calls = []

    class FakeModel:
        def __init__(self, *args, **kwargs):
            assert kwargs['local_files_only'] is True

        def transcribe(self, path, **kwargs):
            calls.append(path)
            if len(calls) == 2:
                raise RuntimeError('simulated interruption')
            word = types.SimpleNamespace(word=' 테스트', start=0.1, end=0.8)
            result = types.SimpleNamespace(words=[word], avg_logprob=-0.2, no_speech_prob=0,
                                           compression_ratio=1, text='테스트', start=.1, end=.8)
            return iter([result]), None

    monkeypatch.setitem(sys.modules, 'faster_whisper', types.SimpleNamespace(WhisperModel=FakeModel))
    worker = make_worker(database)
    with pytest.raises(RuntimeError, match='simulated'):
        worker.transcribe(project['id'])
    assert database.project(project['id'])['next_chunk'] == 1
    assert len(database.segments(project['id'])) == 1
    worker.transcribe(project['id'])
    assert database.project(project['id'])['status'] == 'completed'
    assert len(database.segments(project['id'])) == 2
    assert database.segments(project['id'])[1]['start'] == 1.1


def test_generated_sources_must_exist_in_input(client, monkeypatch):
    project = upload(client)
    identifier = seed_segment(client, project)
    database = client.app.state.db
    with database.connect() as db:
        db.execute('UPDATE segments SET reviewed=1 WHERE id=?', (identifier,))
        db.execute("INSERT INTO drafts(id,project_id,kind,status,reviewed_only) VALUES('bad',?,'summary','queued',1)", (project['id'],))
    worker = make_worker(database)
    monkeypatch.setattr(worker, 'ask_local_model', lambda *args: [{'heading':'제목','body':'생성 내용','segment_ids':[9999]}])
    with pytest.raises(RuntimeError, match='유효하지 않은 원문'):
        worker.generate('bad', {})
    with database.connect() as db:
        assert db.execute("SELECT content FROM drafts WHERE id='bad'").fetchone()[0] == '[]'


def test_missing_model_is_actionable_and_no_job_is_queued(tmp_path):
    with TestClient(create_app(tmp_path), headers=HEADERS) as client:
        project = upload(client)
        result = client.post(f"/api/projects/{project['id']}/transcribe")
        assert result.status_code == 422
        assert '모델' in result.json()['detail']
        assert client.get(f"/api/projects/{project['id']}").json()['status'] == 'uploaded'


def test_generated_draft_uses_reviewed_text_and_separate_reference(client, monkeypatch):
    project = upload(client, reference='[사전 자료] 예산은 예정 금액입니다.')
    identifier = seed_segment(client, project, '검토한 발언: 13억입니다.')
    seed_segment(client, project, '미검토 발언은 전달하면 안 됩니다.')
    database = client.app.state.db
    with database.connect() as db:
        db.execute('UPDATE segments SET reviewed=1 WHERE id=?', (identifier,))
        db.execute("INSERT INTO drafts(id,project_id,kind,status,reviewed_only) VALUES('good',?,'summary','queued',1)", (project['id'],))
    worker = make_worker(database)

    def local_response(model, system, text):
        assert '실제 발언 아님' in text
        assert '미검토 발언은' not in text
        assert '13억' in text
        return [{'heading':'예산 관련 발언','body':'13억이라고 설명했다.','segment_ids':[identifier]}]

    monkeypatch.setattr(worker, 'ask_local_model', local_response)
    worker.generate('good', {})
    result = client.get(f"/api/projects/{project['id']}").json()['drafts'][0]
    assert result['status'] == 'completed'
    assert result['stale'] is False
    assert result['content'][0]['segment_ids'] == [identifier]


def test_cpu_float16_and_empty_names_are_rejected(client):
    settings = client.get('/api/settings').json()
    settings['device'] = 'cpu'
    assert client.put('/api/settings', json=settings).status_code == 422
    project = upload(client)
    assert client.patch(f"/api/projects/{project['id']}", json={'speakers': {'speaker_1': ' '}}).status_code == 422


def test_windows_launcher_survives_distribution_zip():
    root = Path(__file__).resolve().parents[1]
    launcher = (root / 'start.bat').read_bytes()
    assert launcher.isascii()
    assert b'\n' not in launcher.replace(b'\r\n', b'')
    assert b'chcp' not in launcher
    assert b'if not exist ".venv\\Scripts\\python.exe" goto missing_python\r\n' in launcher
    assert b'".venv\\Scripts\\python.exe" "scripts\\run.py"\r\n' in launcher
    subprocess.run([sys.executable, str(root / 'scripts' / 'package.py')], cwd=root, check=True, capture_output=True)
    with zipfile.ZipFile(root / 'dist' / 'voice-archive-windows.zip') as archive:
        assert archive.read('voice-archive/start.bat') == launcher
        assert 'voice-archive/.gitattributes' in archive.namelist()


def test_transcription_runtime_imports_in_fresh_process():
    """Windows CT2 imports pkg_resources even when the Linux wheel does not."""
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, '-c',
         'import pkg_resources; from app.worker import bootstrap_cuda; bootstrap_cuda(); '
         'from faster_whisper import WhisperModel; print("Whisper OK")'],
        cwd=root, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert 'Whisper OK' in result.stdout
