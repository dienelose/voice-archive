"""Explicit online installation; inference itself loads only this local folder."""
import argparse
from pathlib import Path


def main():
    from huggingface_hub import snapshot_download
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, default=Path(__file__).resolve().parents[1] / 'models' / 'whisper-large-v3')
    parser.add_argument('--revision', default='main', help='Optional audited Hugging Face commit hash')
    args = parser.parse_args()
    snapshot_download(repo_id='Systran/faster-whisper-large-v3', revision=args.revision,
                      local_dir=args.directory, allow_patterns=['*.json', '*.bin', '*.txt'])
    print(f'Model installed: {args.directory.resolve()}')


if __name__ == '__main__':
    main()
