"""Exercise the actual Whisper audio decoder and bundled VAD, without model downloads."""
import subprocess
import wave

import numpy as np
import pytest
from faster_whisper.audio import decode_audio
from faster_whisper.vad import VadOptions, get_speech_timestamps


@pytest.mark.parametrize('extension', ['wav', 'mp3'])
def test_real_whisper_audio_decoder(tmp_path, extension):
    rate = 48000
    samples = (np.sin(2 * np.pi * 440 * np.arange(rate) / rate) * 12000).astype('<i2')
    original = tmp_path / 'tone.wav'
    with wave.open(str(original), 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(samples.tobytes())
    source = original
    if extension == 'mp3':
        source = tmp_path / 'tone.mp3'
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(original),
                        '-b:a', '192k', str(source)], check=True, capture_output=True)
    decoded = decode_audio(str(source), sampling_rate=16000)
    assert decoded.dtype == np.float32
    assert abs(len(decoded) - 16000) < 100
    assert np.isfinite(decoded).all()
    assert np.sqrt(np.mean(decoded ** 2)) > 0.1


def test_actual_bundled_vad_handles_silence():
    silence = np.zeros(32000, dtype=np.float32)
    assert get_speech_timestamps(silence, VadOptions(min_silence_duration_ms=700)) == []
