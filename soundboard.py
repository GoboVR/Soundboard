"""
Voice Chat Soundboard
----------------------
A free, unlimited soundboard that routes sound effects through VB-Audio CABLE
so they can be heard by others in Discord / games / voice chat.

NEW: "Mic + SFX Passthrough" mode. When enabled, the app continuously
relays your real microphone into CABLE Input and mixes sound effects on top
of it in real time. That means you can talk normally AND fire sfx at the
same time, with no separate mixer app (like VoiceMeeter) required. Sound
effects also always play back locally so you can hear them yourself.

Setup:
    1. Install VB-Audio CABLE:  https://vb-audio.com/Cable/
    2. In Discord / your game's voice settings, set your microphone /
       input device to "CABLE Output (VB-Audio Virtual Cable)".
    3. In this app:
         - "Sfx / Passthrough Output" -> "CABLE Input (VB-Audio Virtual Cable)"
         - "Mic Input" -> your real physical microphone
         - "Play locally on" -> your real speakers/headset
         - check "Enable Mic + SFX Passthrough"
       Now talk normally - it goes: your mic -> this app -> CABLE Input ->
       CABLE Output -> Discord. Click any sound button and it gets mixed in
       on top, and also played to your local speakers so you hear it too.

Install dependencies:
    pip install -r requirements.txt

    (pydub is only needed as a fallback for formats soundfile can't read,
     e.g. some mp3s - it requires ffmpeg installed and on PATH.)
    (keyboard is only needed for global hotkeys - may require running as
     Administrator on Windows to work while a game has focus.)
"""

import json
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

import numpy as np
import sounddevice as sd

try:
    import soundfile as sf
except ImportError:
    sf = None

try:
    from pydub import AudioSegment
except ImportError:
    AudioSegment = None

try:
    import keyboard as kb
except ImportError:
    kb = None


def _app_dir():
    """Folder the config file lives in. When frozen by PyInstaller (onefile),
    __file__ points at a temporary extraction folder that gets wiped on
    exit, so use the .exe's own folder instead in that case."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def safe_log(msg):
    """print() can raise if this is a --windowed exe with no console
    attached (sys.stdout is None) - swallow that instead of crashing."""
    try:
        if sys.stdout is not None:
            print(msg)
    except Exception:
        pass


CONFIG_PATH = os.path.join(_app_dir(), "soundboard_config.json")

MIX_SAMPLERATE = 48000  # fixed rate used for the live mic+sfx mixer
MIX_BLOCKSIZE = 1024
MIX_CHANNELS = 2


class Sound:
    def __init__(self, name, path, hotkey=None):
        self.name = name
        self.path = path
        self.hotkey = hotkey  # e.g. "ctrl+alt+1" or None


# ---------------------------------------------------------------- audio I/O
def load_audio(path):
    """Return (numpy_array float32 shape (frames, channels), samplerate)."""
    if sf is not None:
        try:
            data, samplerate = sf.read(path, dtype="float32", always_2d=True)
            return data, samplerate
        except Exception:
            pass  # fall through to pydub

    if AudioSegment is not None:
        seg = AudioSegment.from_file(path)
        samples = np.array(seg.get_array_of_samples()).astype(np.float32)
        samples /= float(1 << (8 * seg.sample_width - 1))
        if seg.channels > 1:
            samples = samples.reshape((-1, seg.channels))
        else:
            samples = samples.reshape((-1, 1))
        return samples, seg.frame_rate

    raise RuntimeError(
        "Could not load '{}'. Install 'soundfile' (wav/flac/ogg) or "
        "'pydub' + ffmpeg (mp3 and others).".format(path)
    )


def resample(data, orig_sr, target_sr):
    if orig_sr == target_sr or data.shape[0] == 0:
        return data
    n_frames = data.shape[0]
    duration = n_frames / float(orig_sr)
    new_n = max(1, int(round(duration * target_sr)))
    old_idx = np.linspace(0, n_frames - 1, n_frames)
    new_idx = np.linspace(0, n_frames - 1, new_n)
    out = np.zeros((new_n, data.shape[1]), dtype=np.float32)
    for ch in range(data.shape[1]):
        out[:, ch] = np.interp(new_idx, old_idx, data[:, ch])
    return out


def match_channels(data, target_channels):
    cur = data.shape[1]
    if cur == target_channels:
        return data
    if cur == 1 and target_channels > 1:
        return np.repeat(data, target_channels, axis=1)
    if cur > target_channels:
        return data[:, :target_channels]
    pad = np.zeros((data.shape[0], target_channels - cur), dtype=np.float32)
    return np.concatenate([data, pad], axis=1)


def prepare_for_stream(data, orig_sr, target_sr, target_channels):
    data = resample(data, orig_sr, target_sr)
    data = match_channels(data, target_channels)
    return np.ascontiguousarray(data, dtype=np.float32)


def _play_on_device(data, samplerate, device_idx):
    """Fire-and-forget playback of a numpy buffer on a specific device -
    used for the local monitor copy, independent of everything else."""
    stream = sd.OutputStream(samplerate=samplerate, device=device_idx, channels=data.shape[1])
    stream.start()

    def _writer():
        try:
            stream.write(data)
        finally:
            stream.stop()
            stream.close()

    threading.Thread(target=_writer, daemon=True).start()


# ---------------------------------------------------------------- mixer
class MicSfxMixer:
    """Continuously relays a mic input device to an output device (CABLE
    Input), mixing in sound effects live so both are heard together."""

    def __init__(self, samplerate=MIX_SAMPLERATE, blocksize=MIX_BLOCKSIZE, channels=MIX_CHANNELS):
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.channels = channels
        self.input_stream = None
        self.output_stream = None
        self._mic_queue = queue.Queue(maxsize=50)
        self._active_lock = threading.Lock()
        self._active_sfx = []  # list of [data(np.ndarray), position(int)]
        self.running = False

    def start(self, mic_device, out_device):
        self.stop()
        self._mic_queue = queue.Queue(maxsize=50)
        self._active_sfx = []
        self.input_stream = sd.InputStream(
            device=mic_device, channels=self.channels, samplerate=self.samplerate,
            blocksize=self.blocksize, dtype="float32", callback=self._input_cb,
        )
        self.output_stream = sd.OutputStream(
            device=out_device, channels=self.channels, samplerate=self.samplerate,
            blocksize=self.blocksize, dtype="float32", callback=self._output_cb,
        )
        self.input_stream.start()
        self.output_stream.start()
        self.running = True

    def stop(self):
        for s in (self.input_stream, self.output_stream):
            if s is not None:
                try:
                    s.stop()
                    s.close()
                except Exception:
                    pass
        self.input_stream = None
        self.output_stream = None
        self.running = False
        with self._active_lock:
            self._active_sfx = []

    def add_sfx(self, raw_data, orig_sr):
        data = prepare_for_stream(raw_data, orig_sr, self.samplerate, self.channels)
        with self._active_lock:
            self._active_sfx.append([data, 0])

    def clear_sfx(self):
        with self._active_lock:
            self._active_sfx = []

    def _input_cb(self, indata, frames, time_info, status):
        try:
            self._mic_queue.put_nowait(indata.copy())
        except queue.Full:
            pass

    def _output_cb(self, outdata, frames, time_info, status):
        try:
            mic_chunk = self._mic_queue.get_nowait()
            if mic_chunk.shape[0] < frames:
                pad = np.zeros((frames - mic_chunk.shape[0], self.channels), dtype=np.float32)
                mic_chunk = np.concatenate([mic_chunk, pad], axis=0)
            elif mic_chunk.shape[0] > frames:
                mic_chunk = mic_chunk[:frames]
        except queue.Empty:
            mic_chunk = np.zeros((frames, self.channels), dtype=np.float32)

        mix = mic_chunk.copy()

        with self._active_lock:
            still_active = []
            for item in self._active_sfx:
                data, pos = item
                remaining = data.shape[0] - pos
                take = min(remaining, frames)
                if take > 0:
                    mix[:take] += data[pos:pos + take]
                pos += take
                if pos < data.shape[0]:
                    item[1] = pos
                    still_active.append(item)
            self._active_sfx = still_active

        np.clip(mix, -1.0, 1.0, out=mix)
        outdata[:] = mix


# ---------------------------------------------------------------- app
class SoundboardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Voice Chat Soundboard")
        self.root.geometry("950x680")
        self.root.minsize(650, 420)

        self.sounds = []
        self.volume = tk.DoubleVar(value=1.0)
        self.play_locally = tk.BooleanVar(value=True)
        self.passthrough_enabled = tk.BooleanVar(value=False)

        self.mixer = MicSfxMixer()

        self._build_ui()
        self._load_config()

    # ---------------------------------------------------------- UI setup
    def _build_ui(self):
        top = tk.Frame(self.root, padx=10, pady=10)
        top.pack(fill=tk.X)

        tk.Label(top, text="Sfx / Passthrough Output (set to CABLE Input):").grid(row=0, column=0, sticky="w")
        self.out_device_var = tk.StringVar()
        self.out_device_menu = tk.OptionMenu(top, self.out_device_var, "")
        self.out_device_menu.config(width=38)
        self.out_device_menu.grid(row=0, column=1, sticky="w", padx=5)

        tk.Label(top, text="Mic Input (your real microphone):").grid(row=1, column=0, sticky="w")
        self.mic_device_var = tk.StringVar()
        self.mic_device_menu = tk.OptionMenu(top, self.mic_device_var, "")
        self.mic_device_menu.config(width=38)
        self.mic_device_menu.grid(row=1, column=1, sticky="w", padx=5)

        tk.Label(top, text="Play locally on:").grid(row=2, column=0, sticky="w")
        self.local_device_var = tk.StringVar()
        self.local_device_menu = tk.OptionMenu(top, self.local_device_var, "")
        self.local_device_menu.config(width=38)
        self.local_device_menu.grid(row=2, column=1, sticky="w", padx=5)

        tk.Checkbutton(top, text="Play sfx locally too", variable=self.play_locally).grid(
            row=2, column=2, sticky="w", padx=10
        )

        tk.Button(top, text="Refresh Devices", command=self._refresh_devices).grid(row=0, column=2, padx=10, sticky="w")

        self.passthrough_check = tk.Checkbutton(
            top, text="Enable Mic + SFX Passthrough (talk and play sfx together)",
            variable=self.passthrough_enabled, command=self._toggle_passthrough,
            font=("TkDefaultFont", 9, "bold"),
        )
        self.passthrough_check.grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))

        self.status_label = tk.Label(top, text="Passthrough: OFF - sounds will play alone (mic not relayed)", fg="#a60")
        self.status_label.grid(row=4, column=0, columnspan=3, sticky="w")

        hotkey_note = "Panic stop: Escape key (app focused)"
        if kb is not None:
            hotkey_note += " or Ctrl+Alt+P (works globally)"
        tk.Label(top, text=hotkey_note, fg="#888").grid(row=5, column=0, columnspan=3, sticky="w")

        tk.Label(top, text="Volume").grid(row=0, column=3, padx=(20, 0))
        tk.Scale(top, from_=0, to=2, resolution=0.05, orient=tk.HORIZONTAL,
                 variable=self.volume, length=140).grid(row=0, column=4)

        tk.Button(top, text="Stop All Sfx", fg="white", bg="#b33", command=self.stop_all).grid(
            row=1, column=3, columnspan=2, sticky="ew", padx=(20, 0)
        )

        tk.Button(top, text="PANIC - Kill Passthrough", fg="white", bg="#900",
                  font=("TkDefaultFont", 9, "bold"), command=self.panic_stop).grid(
            row=2, column=3, columnspan=2, sticky="ew", padx=(20, 0), pady=(4, 0)
        )

        # Add / search row
        add_row = tk.Frame(self.root, padx=10)
        add_row.pack(fill=tk.X)
        tk.Button(add_row, text="+ Add Sound", command=self.add_sound).pack(side=tk.LEFT)
        tk.Button(add_row, text="+ Add Whole Folder", command=self.add_folder).pack(side=tk.LEFT, padx=5)

        tk.Label(add_row, text="Search:").pack(side=tk.LEFT, padx=(20, 2))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._refresh_buttons())
        tk.Entry(add_row, textvariable=self.search_var, width=25).pack(side=tk.LEFT)

        if kb is None:
            tk.Label(add_row, text="(install 'keyboard' package to enable global hotkeys)",
                     fg="#888").pack(side=tk.RIGHT)

        # Scrollable button grid
        container = tk.Frame(self.root)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.button_frame = tk.Frame(self.canvas)

        self.button_frame.bind(
            "<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.create_window((0, 0), window=self.button_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

        self._refresh_devices()

        # Escape key (while app is focused) and, if available, a global
        # hotkey (works even while a game/Discord has focus) both trigger
        # an instant panic stop - useful for killing a feedback loop fast.
        self.root.bind_all("<Escape>", lambda e: self.panic_stop())
        if kb is not None:
            try:
                kb.add_hotkey("ctrl+alt+p", self.panic_stop)
            except Exception:
                pass

    # ---------------------------------------------------------- devices
    def _refresh_devices(self):
        devices = sd.query_devices()
        out_names = [f"{i}: {d['name']}" for i, d in enumerate(devices) if d["max_output_channels"] > 0]
        in_names = [f"{i}: {d['name']}" for i, d in enumerate(devices) if d["max_input_channels"] > 0]

        def fill_menu(menu_widget, var, names, prefer_substring=None):
            menu = menu_widget["menu"]
            menu.delete(0, "end")
            for n in names:
                menu.add_command(label=n, command=lambda v=n: var.set(v))
            if not var.get() or var.get() not in names:
                chosen = None
                if prefer_substring:
                    for n in names:
                        if prefer_substring.lower() in n.lower():
                            chosen = n
                            break
                var.set(chosen or (names[0] if names else ""))

        fill_menu(self.out_device_menu, self.out_device_var, out_names, prefer_substring="CABLE Input")
        fill_menu(self.mic_device_menu, self.mic_device_var, in_names, prefer_substring=None)
        fill_menu(self.local_device_menu, self.local_device_var, out_names, prefer_substring=None)

    @staticmethod
    def _device_index(device_str):
        if not device_str:
            return None
        return int(device_str.split(":")[0])

    # ---------------------------------------------------------- passthrough
    def _toggle_passthrough(self):
        if self.passthrough_enabled.get():
            mic_idx = self._device_index(self.mic_device_var.get())
            out_idx = self._device_index(self.out_device_var.get())
            if mic_idx is None or out_idx is None:
                messagebox.showwarning("Missing device", "Pick a mic input and an sfx output device first.")
                self.passthrough_enabled.set(False)
                return
            try:
                self.mixer.start(mic_idx, out_idx)
            except Exception as e:
                messagebox.showerror(
                    "Passthrough Error",
                    f"Could not start mic passthrough: {e}\n\n"
                    "Tip: open Windows Sound settings, click your mic and CABLE Input's "
                    "'Properties' -> 'Advanced', and set both to the same sample rate "
                    f"(e.g. 48000 Hz), then try again.",
                )
                self.passthrough_enabled.set(False)
                return
            self.status_label.config(
                text="Passthrough: ON - your mic is live on the sfx output device, sounds mix in on top",
                fg="#080",
            )
        else:
            self.mixer.stop()
            self.status_label.config(text="Passthrough: OFF - sounds will play alone (mic not relayed)", fg="#a60")

    # ---------------------------------------------------------- sound mgmt
    def add_sound(self):
        paths = filedialog.askopenfilenames(
            filetypes=[("Audio Files", "*.wav *.mp3 *.ogg *.flac *.m4a"), ("All files", "*.*")]
        )
        for path in paths:
            default_name = os.path.splitext(os.path.basename(path))[0]
            name = simpledialog.askstring("Sound Name", f"Name for '{default_name}':", initialvalue=default_name)
            if not name:
                continue
            self._register_sound(Sound(name, path))
        self._save_config()
        self._refresh_buttons()

    def add_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        exts = (".wav", ".mp3", ".ogg", ".flac", ".m4a")
        count = 0
        for fname in sorted(os.listdir(folder)):
            if fname.lower().endswith(exts):
                path = os.path.join(folder, fname)
                name = os.path.splitext(fname)[0]
                self._register_sound(Sound(name, path))
                count += 1
        self._save_config()
        self._refresh_buttons()
        messagebox.showinfo("Added", f"Added {count} sounds from folder.")

    def _register_sound(self, sound):
        self.sounds.append(sound)
        if sound.hotkey and kb is not None:
            self._bind_hotkey(sound)

    def remove_sound(self, sound):
        if sound.hotkey and kb is not None:
            try:
                kb.remove_hotkey(sound.hotkey)
            except KeyError:
                pass
        self.sounds.remove(sound)
        self._save_config()
        self._refresh_buttons()

    def set_hotkey(self, sound):
        if kb is None:
            messagebox.showwarning("Unavailable", "Install the 'keyboard' package to use hotkeys.")
            return
        hk = simpledialog.askstring(
            "Set Hotkey", "Enter a hotkey combo (e.g. ctrl+alt+1), or leave blank to clear:",
            initialvalue=sound.hotkey or "",
        )
        if sound.hotkey:
            try:
                kb.remove_hotkey(sound.hotkey)
            except KeyError:
                pass
        sound.hotkey = hk.strip() if hk else None
        if sound.hotkey:
            self._bind_hotkey(sound)
        self._save_config()
        self._refresh_buttons()

    def _bind_hotkey(self, sound):
        try:
            kb.add_hotkey(sound.hotkey, lambda s=sound: self.play_sound(s))
        except Exception as e:
            messagebox.showerror("Hotkey Error", f"Could not bind '{sound.hotkey}': {e}")
            sound.hotkey = None

    # ---------------------------------------------------------- buttons
    def _refresh_buttons(self):
        for w in self.button_frame.winfo_children():
            w.destroy()

        query = self.search_var.get().lower().strip()
        visible = [s for s in self.sounds if query in s.name.lower()] if query else self.sounds

        cols = 4
        for idx, snd in enumerate(visible):
            row, col = divmod(idx, cols)
            frame = tk.Frame(self.button_frame, bd=1, relief=tk.RAISED, padx=3, pady=3)
            frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

            label = snd.name if not snd.hotkey else f"{snd.name}\n[{snd.hotkey}]"
            btn = tk.Button(frame, text=label, width=16, height=3,
                             command=lambda s=snd: self.play_sound(s))
            btn.pack(side=tk.TOP)

            sub = tk.Frame(frame)
            sub.pack(side=tk.TOP, fill=tk.X)
            tk.Button(sub, text="Hotkey", command=lambda s=snd: self.set_hotkey(s)).pack(side=tk.LEFT, expand=True, fill=tk.X)
            tk.Button(sub, text="Remove", fg="red", command=lambda s=snd: self.remove_sound(s)).pack(side=tk.LEFT, expand=True, fill=tk.X)

    # ---------------------------------------------------------- playback
    def play_sound(self, sound):
        threading.Thread(target=self._play_thread, args=(sound,), daemon=True).start()

    def _play_thread(self, sound):
        try:
            data, samplerate = load_audio(sound.path)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Playback Error", str(e)))
            return

        vol = self.volume.get()
        if vol != 1.0:
            data = np.clip(data * vol, -1.0, 1.0)

        if self.mixer.running:
            # Mic + sfx are both live on the output device via the mixer.
            self.mixer.add_sfx(data, samplerate)
        else:
            # No passthrough - just send the sfx alone to the output device.
            out_idx = self._device_index(self.out_device_var.get())
            try:
                sd.play(data, samplerate, device=out_idx, blocking=False)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Playback Error", f"Output device: {e}"))
                return

        if self.play_locally.get():
            local_idx = self._device_index(self.local_device_var.get())
            out_idx = self._device_index(self.out_device_var.get())
            if local_idx is not None and local_idx != out_idx:
                try:
                    _play_on_device(data, samplerate, local_idx)
                except Exception:
                    pass

    def stop_all(self):
        sd.stop()
        self.mixer.clear_sfx()

    def panic_stop(self):
        """Immediately kill mic passthrough (e.g. feedback loop / echo) and
        stop all sfx. Safe to call from any thread."""
        def _do_it():
            self.passthrough_enabled.set(False)
            self.mixer.stop()
            sd.stop()
            self.status_label.config(
                text="Passthrough: OFF (panic stop) - re-enable when ready", fg="#900"
            )
        if threading.current_thread() is threading.main_thread():
            _do_it()
        else:
            self.root.after(0, _do_it)

    # ---------------------------------------------------------- persistence
    def _save_config(self):
        data = {
            "sounds": [{"name": s.name, "path": s.path, "hotkey": s.hotkey} for s in self.sounds],
            "out_device": self.out_device_var.get(),
            "mic_device": self.mic_device_var.get(),
            "local_device": self.local_device_var.get(),
            "play_locally": self.play_locally.get(),
            "volume": self.volume.get(),
        }
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            safe_log(f"Could not save config: {e}")

    def _load_config(self):
        if not os.path.exists(CONFIG_PATH):
            return
        try:
            with open(CONFIG_PATH) as f:
                data = json.load(f)
        except Exception as e:
            safe_log(f"Could not load config: {e}")
            return

        for s in data.get("sounds", []):
            if os.path.exists(s["path"]):
                self._register_sound(Sound(s["name"], s["path"], s.get("hotkey")))

        if data.get("out_device"):
            self.out_device_var.set(data["out_device"])
        if data.get("mic_device"):
            self.mic_device_var.set(data["mic_device"])
        if data.get("local_device"):
            self.local_device_var.set(data["local_device"])
        self.play_locally.set(data.get("play_locally", True))
        self.volume.set(data.get("volume", 1.0))

        self._refresh_buttons()


def main():
    root = tk.Tk()
    app = SoundboardApp(root)

    def on_close():
        app._save_config()
        app.mixer.stop()
        if kb is not None:
            try:
                kb.unhook_all_hotkeys()
            except Exception:
                pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
