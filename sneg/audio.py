"""Original procedural soundscapes, generated locally. No network or audio assets."""
from array import array
import math
from pathlib import Path
import random
import wave

RATE = 22050

def synthesize(path: Path, kind: str, seconds=12):
    rng = random.Random(24)
    samples = array('h')
    notes = [523.25,659.25,783.99,1046.5,880,783.99,659.25,587.33]
    low = 0.
    crackle = 0.
    for i in range(int(RATE*seconds)):
        t = i/RATE
        noise = rng.uniform(-1,1)
        low = low*.985 + noise*.015
        if kind == 'bells':
            phase = t % 1.5
            n = notes[int(t/1.5) % len(notes)]
            value = sum(math.sin(2*math.pi*n*k*phase)*math.exp(-phase*(2.8+k*.4))/k**1.7 for k in (1,2,3,5))*.22
            value *= min(1,phase/.008)
        elif kind == 'fire':
            if rng.random() < .0007:
                crackle = rng.uniform(.25,.7)
            crackle *= .975
            value = low*.9 + noise*crackle
        else:
            value = low*(1.2+.5*math.sin(t*.9))
        fade = min(1,t/.15,(seconds-t)/.2)
        samples.append(int(max(-1,min(1,value*fade))*32767))
    if __import__('sys').byteorder != 'little':
        samples.byteswap()
    path.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(path),'wb') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(RATE); f.writeframes(samples.tobytes())

class Soundscape:
    def __init__(self):
        from PySide6.QtMultimedia import QSoundEffect
        from PySide6.QtCore import QStandardPaths
        self.effect = QSoundEffect()
        self.effect.setLoopCount(QSoundEffect.Infinite.value)
        self.effect.setVolume(.25)
        self.cache = Path(QStandardPaths.writableLocation(QStandardPaths.CacheLocation))
        self.kind = 'off'
        self.paused = False

    def select(self, kind):
        from PySide6.QtCore import QUrl
        self.effect.stop()
        self.kind = kind
        if kind == 'off': return
        path = self.cache/f'{kind}-v1.wav'
        if not path.exists(): synthesize(path,kind)
        self.effect.setSource(QUrl.fromLocalFile(str(path)))
        if not self.paused: self.effect.play()

    def pause(self, paused):
        self.paused = paused
        if paused: self.effect.stop()
        elif self.kind != 'off': self.effect.play()
