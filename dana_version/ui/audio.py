"""Thin wrapper around pygame.mixer for music and sound effects. Missing
files or no audio device are silently ignored so the game, acceptance
suite and smoke tests still run headless (SDL_AUDIODRIVER=dummy)."""

from pathlib import Path

import pygame

from data import config

SOUND_DIR = Path(__file__).resolve().parent.parent.parent / "Sound effects"

SFX_FILES = {
    "hit": "hit.mp3",
    "skill": "skill.mp3",
    "block": "block_shield.mp3",
    "flee": "flee.mp3",
}
MUSIC_FILES = {
    "overworld": "Background music loop.mp3",
    "battle": "Battle music.mp3",
}

_enabled = False
_sfx = {}
_current_music = None


def init():
    """Call once after pygame.init(). Safe to call even with no audio device."""
    global _enabled
    try:
        pygame.mixer.init()
        _enabled = True
    except pygame.error as e:
        print(f"[audio] mixer unavailable, sound disabled: {e}")
        _enabled = False
        return
    for name, filename in SFX_FILES.items():
        path = SOUND_DIR / filename
        try:
            _sfx[name] = pygame.mixer.Sound(str(path))
        except (pygame.error, FileNotFoundError) as e:
            print(f"[audio] couldn't load {filename}: {e}")


def play(name):
    """Fire-and-forget sound effect by logical name (see SFX_FILES)."""
    sound = _sfx.get(name)
    if sound is None:
        return
    sound.set_volume(config.SFX_VOLUME)
    sound.play()


def play_music(name, loop=-1):
    """Switch the looping music track by logical name (see MUSIC_FILES).
    No-ops if that track is already playing."""
    global _current_music
    if not _enabled or _current_music == name:
        return
    filename = MUSIC_FILES.get(name)
    if filename is None:
        return
    try:
        pygame.mixer.music.load(str(SOUND_DIR / filename))
        pygame.mixer.music.set_volume(config.MUSIC_VOLUME)
        pygame.mixer.music.play(loop)
        _current_music = name
    except (pygame.error, FileNotFoundError) as e:
        print(f"[audio] couldn't play music {filename}: {e}")


def stop_music():
    global _current_music
    if _enabled:
        pygame.mixer.music.stop()
    _current_music = None
