"""Exercise the actual Whisper audio decoder and bundled VAD, without model downloads."""
import subprocess
import logging
import types
import wave

import numpy as np
import pytest
from faster_whisper.audio import decode_audio
from faster_whisper.vad import VadOptions, get_speech_timestamps
from faster_whisper import WhisperModel
from app.worker import pcm_to_float32


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


def test_whisper_array_input_bypasses_broken_pyav(monkeypatch):
    """Run Whisper's real input/VAD path; stop before inference requiring weights."""
    import av

    def broken_open(*args, **kwargs):
        raise TypeError("open() got an unexpected keyword argument 'metadata_errors'")

    monkeypatch.setattr(av, 'open', broken_open)

    class ReachedFeatureExtraction(Exception):
        pass

    class FeatureBoundary:
        sampling_rate = 16000

        def __call__(self, audio, **kwargs):
            assert isinstance(audio, np.ndarray) and audio.dtype == np.float32
            raise ReachedFeatureExtraction

    runtime = types.SimpleNamespace(feature_extractor=FeatureBoundary(), logger=logging.getLogger('runtime-test'))
    audio = pcm_to_float32(b'\0\0' * 32000)
    with pytest.raises(ReachedFeatureExtraction):
        WhisperModel.transcribe(runtime, audio, language='ko', vad_filter=True)


def test_pcm_conversion_preserves_polarity_and_amplitude():
    pcm = np.array([-32768, -16384, 0, 16384, 32767], dtype='<i2')
    result = pcm_to_float32(pcm.tobytes())
    np.testing.assert_allclose(result, [-1, -.5, 0, .5, 32767 / 32768], atol=1e-7)
    assert result.dtype == np.float32
