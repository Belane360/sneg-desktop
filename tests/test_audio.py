import wave
import pytest
from sneg.audio import synthesize

@pytest.mark.parametrize('kind',['bells','fire','wind'])
def test_original_audio_is_valid_pcm(tmp_path,kind):
    path=tmp_path/f'{kind}.wav';synthesize(path,kind,seconds=.2)
    with wave.open(str(path),'rb') as sound:
        assert sound.getnchannels()==1
        assert sound.getframerate()==22050
        assert sound.getnframes()==4410
        assert any(sound.readframes(4410))
