# Voice Chat Soundboard

A free soundboard with **no limit on the number of sound effects and no
ads**. It routes sfx through VB-Audio CABLE so your friends/game voice chat
can hear them, and can now relay your real microphone at the same time so
you can talk and fire sound effects together.

## 1. Install VB-Audio CABLE

Download and install it from https://vb-audio.com/Cable/ (free). This creates
two virtual audio devices: **CABLE Input** and **CABLE Output**. Restart your
PC after installing if prompted.

## 2. Point your voice chat app at the cable

In Discord (or your game's voice settings), set your **Input Device /
Microphone** to `CABLE Output (VB-Audio Virtual Cable)`.

## 3. Install Python dependencies

```
pip install -r requirements.txt
```

- `sounddevice` + `numpy`: core audio playback and the live mixer
- `soundfile`: reads wav/flac/ogg natively
- `pydub`: fallback loader for mp3/m4a/etc — **requires ffmpeg** installed
  and on your PATH (https://ffmpeg.org/download.html). If you only use .wav
  files you can skip installing ffmpeg.
- `keyboard`: optional, enables global hotkeys so you can fire sounds while
  tabbed into your game. On Windows this may require running as
  Administrator for hotkeys to register while another app is focused.

## 4. Run it

```
python soundboard.py
```

### Talk AND play sfx at the same time (recommended setup)

This is the new bit. In the app:

1. **Sfx / Passthrough Output** -> `CABLE Input (VB-Audio Virtual Cable)`
2. **Mic Input** -> your real physical microphone
3. **Play locally on** -> your real speakers/headset (so you hear the sfx too)
4. Check **"Enable Mic + SFX Passthrough"**

With that on, the app continuously relays your real mic into CABLE Input.
Discord (listening to CABLE Output) hears your normal voice the whole time.
Whenever you click a sound button, it gets mixed on top of your mic in real
time — so people in chat hear *you + the sfx* together — and it also plays
out loud on your own speakers so you can hear it.

You do **not** need VoiceMeeter or any other mixer app for this — the
soundboard does the mixing itself.

If you'd rather not relay your mic through the app (e.g. you only want sfx,
or you want to use a dedicated mixer like VoiceMeeter for more advanced
routing), just leave "Enable Mic + SFX Passthrough" unchecked — the app will
fall back to sending sfx alone to the output device.

### Other controls

- **+ Add Sound**: pick one or more audio files and give each a name.
- **+ Add Whole Folder**: bulk-import every audio file in a folder — no cap
  on how many you can add.
- **Hotkey** button on each sound: assign a global key combo like
  `ctrl+alt+1` so you can trigger it without alt-tabbing.
- **Search box**: filters the grid once you have a lot of sounds.
- **Stop All Sfx**: stops any currently playing/queued sfx (mic passthrough,
  if enabled, keeps running).

Everything you add is saved automatically to `soundboard_config.json` next to
the script, so your board and device choices persist between sessions.

## 5. (Optional) Turn it into a standalone .exe

If you don't want to deal with Python every time (handy if you're tethered
into VR and just want to double-click something), you can package it into a
single .exe with PyInstaller. This has to be done **on a Windows machine**
(PyInstaller doesn't cross-compile from other OSes):

1. Make sure `soundboard.py`, `requirements.txt`, and `build_exe.bat` are all
   in the same folder.
2. Double-click `build_exe.bat` (or run it from a terminal). It installs
   dependencies + PyInstaller and builds the exe for you.
3. When it finishes, grab `dist\VoiceChatSoundboard.exe` — that's a single
   self-contained file, no Python install needed to run it. Copy it wherever
   you like (e.g. next to your VR launcher shortcuts).

Notes:
- `soundboard_config.json` will be created next to the .exe itself and saves
  your sound list/settings between launches.
- If you want global hotkeys to work while a game/VR app has focus, right
  click the exe -> "Run as administrator" (Windows restricts global hotkeys
  for unelevated apps in some cases).
- Antivirus / SmartScreen sometimes flags freshly-built PyInstaller exes as
  unrecognized (not malicious, just unsigned/uncommon) — you may need to
  click "More info -> Run anyway" the first time.

## Troubleshooting

- **No sound in Discord**: double check Discord's input device is
  `CABLE Output`, and the app's "Sfx / Passthrough Output" is `CABLE Input`.
- **"Could not start mic passthrough" error**: this usually means your mic
  and CABLE Input aren't running at the same sample rate. Open Windows Sound
  settings -> your mic's Properties -> Advanced, and CABLE Input's
  Properties -> Advanced, and set both to the same rate (48000 Hz is a safe
  choice), then try again.
- **Choppy/glitchy audio during passthrough**: try closing other audio-heavy
  apps, or lower background CPU load — the live mixer needs to keep up in
  real time.
- **mp3 files won't load**: install ffmpeg and make sure it's on PATH, or
  convert the file to `.wav`.
- **Hotkeys don't fire while in-game**: try running your terminal/IDE as
  Administrator (Windows requires elevated privileges for some games to
  receive global hotkeys through other apps).
