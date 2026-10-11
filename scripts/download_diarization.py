"""Optional model installation after accepting the model terms and local HF login."""
from pathlib import Path
from huggingface_hub import snapshot_download

destination = Path(__file__).resolve().parents[1] / 'models' / 'speaker-diarization-community-1'
snapshot_download(repo_id='pyannote/speaker-diarization-community-1', local_dir=destination, token=True)
print(f'Local diarization model: {destination}')
