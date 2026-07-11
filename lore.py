#!/usr/bin/env python3
"""
lore.py - the whole LORE app in one file.
--------------------------------------------------------
LORE - the book your games write. It records them on Windows: smooth video,
clean audio, true HDR handling, clips, and a book for every memory.

How it works:
  * VIDEO  -> ffmpeg captures the watched monitor on the GPU (ddagrab) and a
             hardware encoder (AMD AMF / NVENC / QSV, auto-detected) encodes it.
             ffmpeg does ONLY video, so the pipeline never stalls on audio.
             On an HDR desktop it records a true 10-bit HDR file - ZERO-COPY on
             AMD (surface straight into the encoder), so HDR costs no game FPS.
  * AUDIO  -> Python captures WASAPI loopback of the DEFAULT playback device
             (plus the microphone) with no rerouting and no added latency.
  * At the end of the session the two are muxed into one clean .mp4.

It auto-detects a game going fullscreen ON THE WATCHED SCREEN, records the whole
session, and stops when the game closes. Launchers, browsers and media apps are
never auto-recorded; games on the user's list always are.

FIRST-TIME SETUP (from source; the installer does all this for friends):
    pip install psutil PyAudioWPatch pystray pillow
    (ffmpeg.exe + ffprobe.exe in .\\ffmpeg\\bin, or on PATH)
    python lore.py --settings       # pick folder, audio, quality
    python lore.py --diag-audio     # confirm audio devices are seen
    python lore.py --test 12        # 12s test clip (video+audio)
"""

import argparse
import datetime as _dt
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import wave

# Product version - shown in the window and used to tell releases apart.
# Bump this (and AppVersion in installer.iss) on every release.
APP_VERSION = "1.02"

try:
    import psutil
except ImportError:
    print("Missing dependency. Run:  pip install psutil PyAudioWPatch")
    sys.exit(1)

# pyaudiowpatch is imported lazily inside the audio code so the rest of the
# program (settings, detection) still works even if it's not installed yet.


def _default_output_dir():
    """An always-writable default save folder for a fresh install - a friend's
    PC may not have a D: drive, so use their own Videos folder."""
    if os.name == "nt":
        prof = os.environ.get("USERPROFILE")
        if prof:
            return os.path.join(prof, "Videos", "Game Recordings")
    return os.path.join(os.path.expanduser("~"), "Game Recordings")


# ===========================================================================
#  DEFAULTS  (the settings window writes these into settings.json)
# ===========================================================================
DEFAULTS = {
    "output_dir":        _default_output_dir(),
    "ffmpeg_path":       "ffmpeg",

    # Video / quality
    "framerate":         60,
    "bitrate_mbps":      25,          # VBR target; peaks to 2x. Up to ~11 GB/hr, usually less
    "encoder":           "auto",      # "auto" detects your GPU (AMD/NVIDIA/Intel)
                                      # and picks the best encoder; or force one:
                                      # av1 / hevc / hevc_amf / hevc_nvenc / ...
    "amf_quality":       "balanced",  # "speed" = smoothest, "balanced", "quality"
    "monitor_index":     0,           # 0 = primary screen (default). 1,2,... = capture
                                      # that screen index instead (Screen 2, Screen 3...)
    "safe_capture":      False,        # most-compatible capture path; turn on if the
                                       # encoder fails to start (e.g. some AMD/4K setups)

    # Detection
    "detection_mode":    "auto",      # "auto" (fullscreen games) or "list"
    "poll_interval":     3,

    # Audio (WASAPI - no rerouting, no delay)
    "capture_system":    True,        # loopback of the chosen/default playback device
    "capture_mic":       True,
    "audio_output_device": "",        # which playback device to record ("" = default)
    "mic_name_contains": "",          # which microphone ("" = Windows default input)
    "audio_mode":        "mix",       # "mix" = one track, "separate" = two tracks
    "audio_offset_ms":   0,           # nudge if audio is slightly ahead/behind

    # Replay buffer ("save the last minute" hotkey)
    "segment_seconds":   4,           # internal capture chunk size (don't fuss with this)
    "replay_seconds":    60,          # how much the "save last minute" hotkey grabs

    # HDR. "auto" (recommended): when Windows HDR is on, capture the desktop's
    # FLOAT16 (scRGB) surface zero-copy into an AMD (AMF) encoder, which PQ-encodes
    # it into a true 10-bit HDR10 file at full speed. Every 8/10-bit readback that
    # ddagrab offers was MEASURED to be linear light hard-clipped at 80 nits
    # (colour-patch lab, RX 9070 XT + Windows 11) - i.e. destroyed before any
    # filter could run - which is why 1.16-1.23 HDR looked washed/neon no matter
    # what tone-map ran on top. The float16 surface is the only unclipped source,
    # and AMF is the only encoder here that eats it on the GPU. Non-AMF encoders
    # record plain SDR capture instead (slightly flat, never neon). "off": plain.
    "hdr_mode":          "auto",      # auto | off
    # After an HDR session ends, convert the recording/clips to normal SDR colour in
    # the background (only while nothing is recording - it never costs game FPS).
    # The conversion is anchored to the WINDOWS SDR WHITE LEVEL captured at record
    # time (the "SDR content brightness" slider), which is what makes the result
    # match the screen - a fixed 100/203-nit reference is what blew out 1.21-1.23.
    "sdr_finish":        True,
    "sdr_finish_max_min": 30,         # don't auto-convert recordings longer than this

    # Housekeeping
    "max_storage_gb":    0,           # auto-delete oldest clips above this (0 = off)
    "notify_on_record":  True,        # subtle tray pop when a recording starts
    "quiet_popups":      True,        # hold Lore's own popups while WRITING a recording
    # What the recorder captures: the whole watched screen (proven path) or,
    # experimentally, only the detected game's own window (gdigrab; windowed
    # games without the rest of the desktop - falls back to screen if it fails)
    "capture_scope":     "screen",    # screen | window
    # Popups (Lore' own on-top notifications). Size scales with the watched
    # monitor; style picks the entrance animation (Settings > Replay > Popups).
    "popup_style":       "slide",     # slide | rise | pop | glow | sweep | off
    "popup_size":        "large",     # small | medium | large | huge
    "sfx_volume":        25,          # volume of the app's start/stop/shutter sounds (0-100)

    # Global hotkeys (assignable in Settings). Blank = disabled.
    # ONE key handles recording: it starts a recording when idle and stops &
    # saves it while recording - a single press captures a moment, no clicking.
    "hotkey_record":     "ctrl+alt+f7",     # start when idle / stop & save when recording
    "hotkey_replay":     "ctrl+alt+f9",     # save the last N seconds
    "hotkey_pause":      "ctrl+alt+f10",    # pause / continue the current recording
    "hotkey_clip_discord": "ctrl+alt+f8",   # save a clip AND post it to Discord
    "clip_hotkey_seconds": 60,        # length grabbed by the clip hotkeys (separate control)

    # Share clips to a Discord channel (paste a channel webhook URL). The
    # "Clip + post to Discord" hotkey uploads a small compressed copy; your saved
    # clip stays full quality. The plain "Save clip" hotkey never uploads.
    "discord_webhook":       "",
    "discord_max_mb":        9,        # keep the upload under Discord's free 10 MB cap
    "discord_clip_seconds":  15,       # how much of the clip to post (its last N sec)
    "discord_quality_mbps":  6,        # target quality of the Discord copy
}

# Apps Lore never auto-records when they go full-screen (games are still always
# recorded - the games list and full-screen game detection take priority over this).
# This is the BUILT-IN baseline; you can add your own in ignore.txt (Settings >
# General > "Never auto-record these"). Names are matched on the .exe, lower-case.
IGNORE_PROCESSES = {
    # Lore itself + Windows shell / system surfaces
    "lore.exe", "records.exe", "explorer.exe", "searchhost.exe", "searchapp.exe",
    "shellexperiencehost.exe", "startmenuexperiencehost.exe", "systemsettings.exe",
    "lockapp.exe", "dwm.exe", "applicationframehost.exe", "textinputhost.exe",
    "widgets.exe", "widgetservice.exe",
    # Web browsers
    "chrome.exe", "msedge.exe", "msedgewebview2.exe", "firefox.exe", "opera.exe",
    "opera_gx.exe", "operagx.exe", "brave.exe", "vivaldi.exe", "iexplore.exe",
    # Media / video players
    "vlc.exe", "mpc-hc64.exe", "mpc-hc.exe", "mpc-be64.exe", "mpc-be.exe",
    "wmplayer.exe", "potplayermini64.exe", "potplayermini.exe", "potplayer64.exe",
    "potplayer.exe", "mpv.exe", "kmplayer.exe", "kmplayer64.exe", "smplayer.exe",
    "mpchc.exe", "qbittorrent.exe",
    # Streaming / media-centre apps (all go borderless-fullscreen for playback -
    # Stremio was the reported offender; the rest are the same class)
    "stremio.exe", "plex.exe", "plexhtpc.exe", "plex htpc.exe", "kodi.exe",
    "jellyfinmediaplayer.exe", "jellyfin media player.exe", "netflix.exe",
    "wwahost.exe", "crunchyroll.exe", "appletv.exe", "primevideo.exe",
    "amazon prime video.exe", "disneyplus.exe", "hulu.exe", "youtube.exe",
    # Live wallpapers (their windows cover the whole monitor behind the desktop)
    "wallpaper32.exe", "wallpaper64.exe", "wallpaperengine.exe", "lively.exe",
    "livelywpf.exe", "rainmeter.exe",
    # Game LAUNCHERS + their UI helpers - the storefront/friends/lobby windows are
    # not gameplay (a maximised Steam friends list was being recorded). The actual
    # games they launch are separate processes, so games still record fine.
    "steam.exe", "steamwebhelper.exe", "epicgameslauncher.exe", "epicwebhelper.exe",
    "battle.net.exe", "battlenet.exe", "agent.exe", "galaxyclient.exe",
    "origin.exe", "eadesktop.exe", "ubisoftconnect.exe", "upc.exe",
    "riotclientservices.exe", "riotclientux.exe", "leagueclientux.exe",
    "rockstargameslauncher.exe", "playnite.desktopapp.exe", "playnite.fullscreenapp.exe",
    "xboxapp.exe", "xboxpcapp.exe", "gamingservicesui.exe",
    # Overlay / capture companions that draw full-screen surfaces
    "overwolf.exe", "medal.exe", "curseforge.exe", "gamebar.exe", "gamebarftserver.exe",
    # Chat / calls / streaming
    "discord.exe", "discordptb.exe", "discordcanary.exe", "slack.exe", "teams.exe",
    "ms-teams.exe", "zoom.exe", "webex.exe", "skype.exe", "telegram.exe",
    "whatsapp.exe", "spotify.exe",
    # Office / documents / PDF / notes
    "winword.exe", "excel.exe", "powerpnt.exe", "onenote.exe", "outlook.exe",
    "acrobat.exe", "acrord32.exe", "foxitpdfreader.exe", "foxitreader.exe",
    "sumatrapdf.exe", "nitropdf.exe", "wordpad.exe", "notepad.exe",
    "notepad++.exe", "code.exe", "devenv.exe",
    # Creative / editing suites (fullscreen canvases are not gameplay)
    "photoshop.exe", "illustrator.exe", "indesign.exe", "afterfx.exe",
    "adobe premiere pro.exe", "premiere.exe", "resolve.exe", "blender.exe",
    "figma.exe", "krita.exe", "gimp.exe", "clipstudiopaint.exe", "aseprite.exe",
    # Capture / dev / system tools (don't record our own kind, or admin windows)
    "obs64.exe", "obs32.exe", "pythonw.exe", "python.exe", "ffmpeg.exe",
    "taskmgr.exe", "windowsterminal.exe", "powershell.exe", "cmd.exe",
    "steelseriesgg.exe", "steelseries gg.exe",
    "snippingtool.exe", "screensketch.exe", "screenclippinghost.exe", "screenclip.exe",
}

SETTINGS = dict(DEFAULTS)

# Serialises the few places that read-modify-write SETTINGS / settings.json from
# different threads (UI Save vs the watcher persisting a discovered fix), so a save
# can't lose an update or briefly expose half-written state.
_SETTINGS_LOCK = threading.Lock()

# Encoders that started fine in the quick probe but then died on the real
# capture this session. We skip them and fall back to the next one, so a PC
# whose GPU encoder misbehaves still records (eventually via software).
_BAD_ENCODERS = set()

# When True, capture/encode uses the most compatible path (frames via system
# memory, no forced-keyframe expression). We switch this on automatically if an
# encoder dies on the fast path - fixes e.g. AMD AMF dying at 4K.
_ENC_SAFE = [False]

# HDR fallback for this app run. 0 = the float16 zero-copy HDR path (AMF only);
# 1+ = give up on HDR handling and record plain. The watcher sets this to 1 if
# the HDR path yields zero frames on this machine, so an HDR path that doesn't
# work on some driver can NEVER leave it with no recording at all.
_HDR_LEVEL = [0]

# Last time we toasted a "couldn't start recording" message, so a persistent start
# failure (missing ffmpeg, unwritable folder) tells the user once rather than spamming.
_LAST_START_FAIL_TOAST = [0.0]


# ---------------------------------------------------------------------------
#  Logging (console + lore.log, so auto-start runs are debuggable)
# ---------------------------------------------------------------------------
def _here():
    # When bundled by PyInstaller, files live next to the .exe (the install
    # folder); in dev they live next to this .py. The BUNDLED, read-only files
    # (ffmpeg, lore.ico) are found relative to this.
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _data_dir():
    """User-writable folder for settings, log, games list and lock/IPC files.
    The app itself can live in a read-only place (e.g. C:\\Program Files), so these
    must NOT be written next to the .exe or saving fails with a permission error."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    d = os.path.join(base, "Lore") if base else _here()
    try:
        os.makedirs(d, exist_ok=True)
        return d
    except Exception:
        return _here()


def log(msg):
    line = f"[{_dt.datetime.now():%H:%M:%S}] {msg}"
    try:
        print(line, flush=True)        # no-op in the windowed build (no console)
    except Exception:
        pass
    try:
        with open(os.path.join(_data_dir(), "lore.log"), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
#  Single-instance lock + "show the window" IPC
#  (stops "Start" from launching a second recorder on top of the first, and lets a
#   second launch pop the running instance's window instead of starting a new copy)
# ---------------------------------------------------------------------------
def _lock_path():
    return os.path.join(_data_dir(), "lore.lock")


def _show_flag_path():
    return os.path.join(_data_dir(), "show.flag")


def _watcher_running_pid():
    """PID of a live OTHER Lore instance, or None.

    Critically, we confirm the PID belongs to an ACTUAL Lore process - not just
    that *some* process has that number. After a freeze/crash or a reboot the lock
    file can be left behind pointing at an old PID, and the OS routinely reuses that
    PID for an unrelated program. The old check only asked 'does any process with
    this PID exist?', so a reused PID made Lore think a copy was already running
    and refuse to start (double-click did nothing). Matching the executable fixes
    that, and a stale lock simply gets reclaimed."""
    try:
        with open(_lock_path()) as fh:
            pid = int(fh.read().strip())
    except Exception:
        return None
    if pid == os.getpid():
        return None
    try:
        if not psutil.pid_exists(pid):
            return None
        p = psutil.Process(pid)
        pname = (p.name() or "").lower()
        # Frozen build: the process is Lore.exe. Exact-match on the name -
        # a substring test would false-positive on e.g. explorer.exe ('lore').
        if pname == "lore.exe" or pname.startswith("lore."):
            return pid
        # Running from source: same interpreter (python/pythonw) - only count it if
        # it's actually running our script, otherwise an unrelated python is not us.
        me_name = (psutil.Process(os.getpid()).name() or "").lower()
        if pname == me_name:
            try:
                cl = " ".join(p.cmdline()).lower()
                if "lore.py" in cl:
                    return pid
            except Exception:
                return pid    # can't read its command line; assume same-name is us
        return None           # PID reused by something unrelated -> stale lock
    except Exception:
        return None


def _signal_show():
    """Ask an already-running tray instance to pop its settings window."""
    try:
        open(_show_flag_path(), "w").close()
    except Exception:
        pass


_SINGLETON_MUTEX = None
_MUTEX_NAME = "Lore_SingleInstance_Gate"   # must match installer.iss AppMutex


def _hold_singleton_mutex():
    """Create/hold a named Windows mutex for our whole lifetime AND report whether
    we are the FIRST instance. This is the authoritative, OS-atomic singleton gate:
    the lock file alone has a check-then-write race where two launches fired within
    a few milliseconds (a common double-click) both read 'no lock' and both start,
    ending up with two recorders writing into the same folder. CreateMutexW is
    atomic in the kernel, so exactly one launch wins. The installer declares the
    same name via AppMutex to detect a running copy during an update.

    Returns True if we are the first instance (also True off-Windows, or on any
    error - we never block startup on a mutex hiccup). Idempotent: a second call in
    the SAME process (e.g. tray -> console fallback) returns True."""
    global _SINGLETON_MUTEX
    if os.name != "nt":
        return True
    if _SINGLETON_MUTEX:
        return True                       # already acquired by us this process
    try:
        import ctypes
        ERROR_ALREADY_EXISTS = 183
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        h = k32.CreateMutexW(None, False, _MUTEX_NAME)
        err = ctypes.get_last_error()
        _SINGLETON_MUTEX = h
        if not h:
            return True                   # couldn't create it; don't block on that
        return err != ERROR_ALREADY_EXISTS
    except Exception:
        _SINGLETON_MUTEX = None
        return True


# ---------------------------------------------------------------------------
#  Settings
# ---------------------------------------------------------------------------
def _settings_path():
    return os.path.join(_data_dir(), "settings.json")


def _migrate_legacy_data():
    """One-time: inherit everything Records (LORE's previous incarnation) knew,
    so the tome opens already filled - settings, the games/ignore lists, the
    file-ownership manifest (the storage cap keeps managing old recordings)
    and any pending HDR->SDR conversions. Best-effort, silent, and it never
    overwrites anything LORE has already written."""
    newp = _settings_path()
    if os.path.exists(newp):
        return
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or ""
    candidates = [os.path.join(base, "Records") if base else "", _here()]
    for old in candidates:
        try:
            if not (old and os.path.isfile(os.path.join(old, "settings.json"))):
                continue
            for name in ("settings.json", "games.txt", "ignore.txt",
                         "created_files.json", "finish_queue.json"):
                src = os.path.join(old, name)
                dst = os.path.join(_data_dir(), name)
                if os.path.isfile(src) and not os.path.exists(dst):
                    shutil.copy2(src, dst)
            log(f"Inherited existing setup from {old}")
            return
        except Exception:
            pass


def _migrate_settings_shape():
    """Bring older settings.json shapes up to date in memory (saved back on the
    next Save). Best-effort and silent: never raises, never overwrites a value the
    user has clearly set on the new shape."""
    s = SETTINGS
    # hdr_mode history: checkbox (bool) -> auto|on|off -> auto|tonemap|off ->
    # auto|off (1.24: the live tone-map path is gone - the 8/10-bit sources it
    # read were proven clipped at capture, so it could never look right). Any
    # legacy value that meant "handle HDR" maps to auto; only "off" stays off.
    hm = s.get("hdr_mode")
    if isinstance(hm, bool):
        s["hdr_mode"] = "auto"
    elif isinstance(hm, str):
        if hm.lower() not in ("auto", "off"):
            s["hdr_mode"] = "auto"
    # retired with the live tone-map path (1.24)
    s.pop("hdr_input", None)
    s.pop("hdr_peak_nits", None)
    # Start and Stop used to be two separate hotkeys; they are now one record
    # toggle. If the new key isn't present, inherit the old Start key so nobody's
    # muscle memory breaks.
    if not s.get("hotkey_record"):
        legacy = (s.get("hotkey_start") or "").strip()
        s["hotkey_record"] = legacy or DEFAULTS["hotkey_record"]
    # Drop the retired keys so they don't linger in settings.json.
    s.pop("hotkey_start", None)
    s.pop("hotkey_stop", None)


def _sanitize_settings(d):
    """Coerce/clamp values loaded from settings.json so a corrupt or hand-edited file
    can't feed a bad value (e.g. framerate 0, bitrate -5) straight into ffmpeg. Each
    numeric key falls back to its DEFAULT on a bad type/range; a few small enums fall
    back if not in their allowed set. 'encoder' is deliberately NOT whitelisted - a
    power user may hand-set one the GUI doesn't list, and resolve_encoder already
    validates it by probing. hdr_mode is left for _migrate_settings_shape (it maps a
    legacy boolean)."""
    INT_BOUNDS = {
        "framerate": (1, 1000), "bitrate_mbps": (1, 1000), "monitor_index": (-1, 64),
        "poll_interval": (1, 60), "segment_seconds": (2, 60), "replay_seconds": (1, 3600),
        "audio_offset_ms": (-60000, 60000),
        "max_storage_gb": (0, 1000000), "sfx_volume": (0, 100),
        "clip_hotkey_seconds": (1, 3600), "discord_max_mb": (1, 1000),
        "discord_clip_seconds": (1, 3600), "discord_quality_mbps": (1, 1000),
        "sdr_finish_max_min": (1, 600),
    }
    for k, (lo, hi) in INT_BOUNDS.items():
        try:
            d[k] = max(lo, min(hi, int(d.get(k, DEFAULTS.get(k, lo)))))
        except Exception:
            d[k] = DEFAULTS.get(k, lo)
    ENUMS = {
        "amf_quality": ("speed", "balanced", "quality"),
        "audio_mode": ("mix", "separate"),
        "detection_mode": ("auto", "list"),
        "popup_style": ("slide", "rise", "pop", "glow", "sweep", "off"),
        "popup_size": ("small", "medium", "large", "huge"),
        "capture_scope": ("screen", "window"),
    }
    # (hdr_mode is normalised by _migrate_settings_shape, which also maps legacy values)
    for k, allowed in ENUMS.items():
        v = d.get(k)
        d[k] = v.lower() if (isinstance(v, str) and v.lower() in allowed) else DEFAULTS[k]


def load_settings():
    global SETTINGS
    with _SETTINGS_LOCK:
        _migrate_legacy_data()
        new = dict(DEFAULTS)
        if os.path.isfile(_settings_path()):
            try:
                with open(_settings_path(), encoding="utf-8") as fh:
                    new.update(json.load(fh))
            except Exception as e:
                log(f"Could not read settings.json ({e}); using defaults.")
        _sanitize_settings(new)
        # Single rebind: a concurrent reader (the watcher) never sees a half-built
        # dict that's momentarily back at DEFAULTS.
        SETTINGS = new
        _migrate_settings_shape()
        _resolve_ffmpeg_paths()
        return SETTINGS


def _resolve_ffmpeg_paths():
    """Prefer a bundled ffmpeg (so friends don't install anything). An explicit
    path is respected ONLY while it actually exists: settings inherited from
    Records carry Records' bundled path, and the moment Records is uninstalled
    that path dies - which used to greet every launch with 'can't find its
    video tool' even though LORE ships its own copy right next to the exe.
    A dead explicit path now heals itself: bundled -> old Records installs ->
    PATH, and the fix is persisted so it never has to heal twice."""
    exp = SETTINGS.get("ffmpeg_path", "ffmpeg")
    explicit = exp not in ("ffmpeg", "", None)
    if explicit and os.path.isfile(exp):
        return                        # user's explicit path, alive - respect it
    if explicit:
        log(f"Configured ffmpeg not reachable ({exp}); using another copy this run.")
    cands = [os.path.join(_here(), "ffmpeg", "bin", "ffmpeg.exe")]
    for pf in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
        if pf:
            cands.append(os.path.join(pf, "Lore", "ffmpeg", "bin", "ffmpeg.exe"))
            cands.append(os.path.join(pf, "Records", "ffmpeg", "bin", "ffmpeg.exe"))
    for cand in cands:
        if os.path.isfile(cand):
            # Heal IN MEMORY ONLY. We deliberately never rewrite an explicit
            # ffmpeg_path: a path on a merely-disconnected network/USB drive is
            # indistinguishable from a permanently-dead one, and silently
            # discarding the user's choice would lose it for good. Recording
            # uses this copy for the session; when the drive returns next
            # launch, the user's own path is respected again.
            SETTINGS["ffmpeg_path"] = cand
            return
    if explicit:
        SETTINGS["ffmpeg_path"] = "ffmpeg"     # last hope: PATH (in-memory only)


def _atomic_write_json(path, obj):
    """Write JSON to `path` so a crash or power loss can never leave a truncated,
    unreadable file: write a sibling temp file, flush it to disk, then atomically
    replace the real one. Raises on failure (callers decide how loud to be)."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2)
        fh.flush()
        try:
            os.fsync(fh.fileno())
        except Exception:
            pass
    os.replace(tmp, path)   # atomic on Windows and POSIX


def save_settings(data):
    # Never persist runtime-internal keys (e.g. _encoder_resolved): they're
    # re-derived each launch, and saving a stale one would skip GPU re-detection.
    clean = {k: v for k, v in data.items() if not k.startswith("_")}
    with _SETTINGS_LOCK:
        _atomic_write_json(_settings_path(), clean)


def _persist_setting(key, value):
    """Update a single key in settings.json on disk without disturbing the live
    SETTINGS or other keys. Used by the watcher to remember a discovered fix."""
    try:
        with _SETTINGS_LOCK:
            d = {}
            if os.path.isfile(_settings_path()):
                with open(_settings_path(), encoding="utf-8") as fh:
                    d = json.load(fh)
            d[key] = value
            _atomic_write_json(_settings_path(), d)
            SETTINGS[key] = value
    except Exception:
        pass


# ---------------------------------------------------------------------------
#  Game detection
# ---------------------------------------------------------------------------
def running_process_names():
    names = set()
    for p in psutil.process_iter(["name"]):
        n = p.info.get("name")
        if n:
            names.add(n.lower())
    return names


def load_game_list():
    names = set()
    path = os.path.join(_data_dir(), "games.txt")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#"):
                    if not line.lower().endswith(".exe"):
                        line += ".exe"
                    names.add(line.lower())
    return names


def read_games_lines():
    """Raw game names from games.txt (as the user typed them, no .exe forced)."""
    path = os.path.join(_data_dir(), "games.txt")
    out = []
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#"):
                    out.append(line)
    return out


def write_games_lines(lines):
    path = os.path.join(_data_dir(), "games.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# Games Lore always captures (one name per line, e.g. eldenring).\n")
        for ln in lines:
            ln = ln.strip()
            if ln:
                fh.write(ln + "\n")


def _ignore_path():
    return os.path.join(_data_dir(), "ignore.txt")


def read_ignore_lines():
    """User-added 'never auto-record' names from ignore.txt (as typed)."""
    out = []
    path = _ignore_path()
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#"):
                    out.append(line)
    return out


def write_ignore_lines(lines):
    """Save the user's extra never-record list. The built-in list always applies on
    top of this, so games keep recording even if the user empties this file."""
    with open(_ignore_path(), "w", encoding="utf-8") as fh:
        fh.write("# Extra apps Lore should NEVER auto-record when full-screen\n")
        fh.write("# (one .exe name per line, e.g. photoshop.exe). Games are still\n")
        fh.write("# always recorded - your games list and full-screen game detection\n")
        fh.write("# take priority over this list.\n")
        for ln in lines:
            ln = ln.strip()
            if ln:
                if not ln.lower().endswith(".exe"):
                    ln += ".exe"
                fh.write(ln + "\n")


def load_ignore_list():
    """The effective never-auto-record set: the built-in baseline UNION the user's
    ignore.txt additions. Always lower-case, .exe forced."""
    names = set(IGNORE_PROCESSES)
    for ln in read_ignore_lines():
        ln = ln.strip().lower()
        if ln:
            if not ln.endswith(".exe"):
                ln += ".exe"
            names.add(ln)
    return names


def _window_monitor_rect(hwnd):
    """(left, top, right, bottom) of the monitor the given window is on, or None.
    Lets borderless-fullscreen be detected on ANY screen, not just the primary."""
    if os.name != "nt" or not hwnd:
        return None
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        MONITOR_DEFAULTTONEAREST = 2
        hmon = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        if not hmon:
            return None

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(ctypes.c_void_p(hmon), ctypes.byref(mi)):
            r = mi.rcMonitor
            return (r.left, r.top, r.right, r.bottom)
    except Exception:
        return None
    return None


def _watched_monitor_rect():
    """rcMonitor of the screen Lore is set to record (the monitor_index setting;
    0 = the primary screen). Full-screen DETECTION only fires for windows on this
    monitor - a game or app going fullscreen on any OTHER screen is deliberately
    ignored, because Lore would end up recording the watched screen anyway (the
    'it recorded my second monitor's fullscreen app' complaint). Monitors are ranked
    by display number, the same contract build_video_cmd uses for ddagrab output_idx.
    Returns None when monitors can't be enumerated (then any monitor is accepted)."""
    try:
        mons = _enumerate_active_monitors()
        if not mons:
            return None
        mons.sort(key=lambda m: m["num"])
        idx = min(max(0, _resolve_capture_monitor()), len(mons) - 1)
        return tuple(mons[idx]["rect"])
    except Exception:
        return None


def detect_fullscreen_game():
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        shell32 = ctypes.windll.shell32
        ignore = load_ignore_list()
        watched = _watched_monitor_rect()

        def _name_if_game(hwnd, require_borderless):
            """Process name if hwnd covers its monitor and isn't Lore / an ignored
            app / (when require_borderless) an ordinary titled or owned window. The
            cheap geometry + style checks run BEFORE the psutil lookup so scanning all
            windows stays light."""
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if not pid.value or pid.value == os.getpid():
                return None
            if require_borderless:
                # A borderless-fullscreen game is a caption-less, un-owned, plain
                # top-level window. Excluding WS_CAPTION skips a merely-maximized
                # browser/editor (which also fills its monitor); excluding owned
                # windows skips tool popups; excluding TRANSPARENT / TOOLWINDOW /
                # NOACTIVATE ex-styles skips click-through overlays (crosshairs,
                # OSDs); excluding the shell's Progman/WorkerW skips the desktop and
                # live-wallpaper hosts; and excluding DWM-cloaked windows skips
                # suspended UWP apps that keep an invisible full-screen frame alive.
                try:
                    if user32.GetWindowLongW(hwnd, -16) & 0x00C00000:   # GWL_STYLE & WS_CAPTION
                        return None
                    if user32.GetWindow(hwnd, 4):                       # GW_OWNER
                        return None
                    ex = user32.GetWindowLongW(hwnd, -20)               # GWL_EXSTYLE
                    if ex & (0x00000020 | 0x00000080 | 0x08000000):     # TRANSPARENT|TOOLWINDOW|NOACTIVATE
                        return None
                    buf = ctypes.create_unicode_buffer(64)
                    user32.GetClassNameW(hwnd, buf, 64)
                    if buf.value in ("Progman", "WorkerW", "Shell_TrayWnd"):
                        return None
                    cloaked = ctypes.c_int(0)
                    if ctypes.windll.dwmapi.DwmGetWindowAttribute(
                            hwnd, 14, ctypes.byref(cloaked),
                            ctypes.sizeof(cloaked)) == 0 and cloaked.value:
                        return None                                    # DWMWA_CLOAKED
                except Exception:
                    return None
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            mrect = _window_monitor_rect(hwnd)
            # Only the WATCHED monitor counts: a window filling any other screen is
            # ignored entirely (Lore would be capturing the watched screen anyway).
            if watched is not None:
                if mrect is None or tuple(mrect) != watched:
                    return None
            if mrect:
                mon_w, mon_h = (mrect[2] - mrect[0]), (mrect[3] - mrect[1])
            else:
                mon_w, mon_h = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
            w, h = rect.right - rect.left, rect.bottom - rect.top
            if not (w > 0 and h > 0 and w >= mon_w - 2 and h >= mon_h - 2):
                return None
            try:
                name = psutil.Process(pid.value).name().lower()
            except psutil.Error:
                return None
            return None if name in ignore else name

        # 1) Foreground window: D3D exclusive fullscreen (a global foreground state),
        # or a borderless window covering its monitor. The user focused it, so we don't
        # require it to be caption-less here.
        hwnd = user32.GetForegroundWindow()
        if hwnd:
            fpid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(fpid))
            if fpid.value and fpid.value != os.getpid():
                try:
                    fname = psutil.Process(fpid.value).name().lower()
                except psutil.Error:
                    fname = None
                if fname and fname not in ignore:
                    # D3D exclusive fullscreen - but only if it's happening on the
                    # monitor Lore actually watches/records.
                    on_watched = True
                    if watched is not None:
                        fmr = _window_monitor_rect(hwnd)
                        on_watched = (fmr is not None and tuple(fmr) == watched)
                    if on_watched:
                        state = ctypes.c_int(0)
                        try:
                            shell32.SHQueryUserNotificationState(ctypes.byref(state))
                            if state.value == 3:           # QUNS_RUNNING_D3D_FULL_SCREEN
                                return fname
                        except Exception:
                            pass
            n = _name_if_game(hwnd, require_borderless=False)
            if n:
                return n

        # 2) Nothing in the foreground qualifies: scan top-level windows so a
        # borderless game on the WATCHED monitor is still caught while the user is
        # focused elsewhere (game on the primary, clicked into Discord on screen 2).
        # _name_if_game rejects windows on other monitors, and the caption/owner/
        # ignore guards prevent grabbing a maximized browser or a media player.
        found = []

        @ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
        def _enum(h, _lparam):
            try:
                if user32.IsWindowVisible(h) and not user32.IsIconic(h):
                    nm = _name_if_game(h, require_borderless=True)
                    if nm:
                        found.append(nm)
                        return 0                           # first match: stop enumerating
            except Exception:
                pass
            return 1
        user32.EnumWindows(_enum, 0)
        if found:
            return found[0]
    except Exception:
        return None
    return None


# The tome ships with its own knowledge of games (known_games.txt, bundled
# read-only next to the app): any of these launching starts a recording even
# WINDOWED - no fullscreen needed, nothing for the user to add by hand. The
# user's ignore list always outranks it.
_BUILTIN_GAMES = {"set": None}


def load_builtin_games():
    if _BUILTIN_GAMES["set"] is not None:
        return _BUILTIN_GAMES["set"]
    names = set()
    for base in (_here(), getattr(sys, "_MEIPASS", None)):
        if not base:
            continue
        p = os.path.join(base, "known_games.txt")
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip().lower()
                        if line and not line.startswith("#"):
                            if not line.endswith(".exe"):
                                line += ".exe"
                            names.add(line)
                log(f"Known-games list loaded: {len(names)} titles.")
            except Exception:
                pass
            break
    if not names:
        # Say so ONCE - otherwise a missing/unreadable bundle makes windowed
        # auto-detect silently inert with no clue in the log.
        log("No known_games.txt bundled; windowed games auto-record only "
            "when they're in your own games list.")
    _BUILTIN_GAMES["set"] = names
    return names


def find_active_game():
    # The games.txt list is ALWAYS honored - this catches windowed games like
    # Hearthstone that fullscreen detection would miss.
    listed = load_game_list()
    running = None
    if listed:
        running = running_process_names()
        hit = listed & running
        if hit:
            return sorted(hit)[0]
    if SETTINGS["detection_mode"] == "list":
        return None
    # Auto mode: the built-in known-games list catches windowed games the
    # moment they launch (user's ignore list wins over it)...
    builtin = load_builtin_games()
    if builtin:
        if running is None:
            running = running_process_names()
        hit = (builtin & running) - load_ignore_list()
        if hit:
            return sorted(hit)[0]
    # ...and fullscreen detection catches everything else.
    return detect_fullscreen_game()


# ---------------------------------------------------------------------------
#  WASAPI audio capture (the part ffmpeg can't do)
# ---------------------------------------------------------------------------
class AudioRecorder:
    """Captures system loopback (default playback device) and/or the mic to
    separate WAV files using WASAPI. No rerouting, no added latency."""

    def __init__(self, tmp_dir, tag=""):
        self.tmp_dir = tmp_dir
        self.tag = tag                       # per-run suffix so pause/resume parts don't clash
        self._pa = None
        self._streams = []
        self._threads = []
        self._stop = threading.Event()
        self.system_wav = None
        self.mic_wav = None
        # In-memory rolling buffer of the most recent audio, per stream, so the
        # "save last minute" replay can be muxed without reading the live WAVs.
        self.rings = []          # list of dicts: kind, rate, channels, chunks, bytes, max
        self._ring_lock = threading.Lock()
        # Hold enough audio for the LONGEST clip any feature can ask for - the
        # replay length, the clip-hotkey length (up to 120s) and the Discord clip
        # length - not just the default, or a long clip would get full video but
        # truncated/silent audio.
        self._replay_seconds = max(
            60,
            int(SETTINGS.get("replay_seconds", 60)),
            int(SETTINGS.get("clip_hotkey_seconds", 60)),
            int(SETTINGS.get("discord_clip_seconds", 15)),
        ) + 5

    def _open_capture(self, dev, path, label, kind):
        import pyaudiowpatch as pyaudio
        import queue
        from collections import deque
        channels = max(1, int(dev["maxInputChannels"]))
        rate = int(dev["defaultSampleRate"])
        wf = wave.open(path, "wb")
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # paInt16
        wf.setframerate(rate)

        ring = {"kind": kind, "rate": rate, "channels": channels,
                "chunks": deque(), "bytes": 0,
                "max": rate * channels * 2 * self._replay_seconds,
                "t_first": None, "frames": 0, "push": None, "frame_bytes": channels * 2}
        with self._ring_lock:
            self.rings.append(ring)

        # Bound the writer queue to ~60s of audio so a sustained disk stall can't grow
        # memory without limit (the ring is already bounded; the live-WAV queue was
        # not). Overflow happens only on a slow/full drive and is counted SEPARATELY
        # from WASAPI capture xruns, so the log stays diagnostic.
        qmax = max(256, int(rate * 60 / 4096) + 16)
        q = queue.Queue(maxsize=qmax)
        drops = {"n": 0}
        qdrops = {"n": 0}
        frame_bytes = channels * 2

        def _push(data):
            try:
                q.put_nowait(data)
            except queue.Full:
                qdrops["n"] += 1          # disk can't keep up; cap RAM (rare, catastrophic)
            with self._ring_lock:
                ring["chunks"].append(data)
                ring["bytes"] += len(data)
                while ring["bytes"] > ring["max"] and len(ring["chunks"]) > 1:
                    ring["bytes"] -= len(ring["chunks"].popleft())
        ring["push"] = _push              # signal_stop() uses it to fill the tail

        # Callback mode: WASAPI hands us audio the instant it's ready. The
        # callback only drops the bytes into a queue (fast, non-blocking); a
        # writer thread does the actual disk writing so the audio system is
        # never stalled. `status` is non-zero when WASAPI had data ready but we
        # weren't quick enough to take it - i.e. samples were LOST.
        #
        # SILENCE-GAP FILL: WASAPI *loopback* starves while the render engine is
        # idle (loading screens, menus, quiet moments) - callbacks pause or turn
        # up empty. Left as-is those wall-clock seconds are simply missing from
        # the WAV, so everything after a gap plays EARLY (and the old duration-
        # based sync then over-delayed the whole track: the '4-6 seconds late'
        # bug). Fix: count frames delivered and, on every callback, top the
        # stream up with real silence until it matches the wall clock since the
        # first sample - the WAV timeline then always equals wall time no matter
        # HOW the device starves.
        def callback(in_data, frame_count, time_info, status):
            now = time.time()
            if ring.get("closed"):
                return (None, pyaudio.paComplete)       # tail already sealed by stop
            if status:
                drops["n"] += 1
            nfr = len(in_data) // frame_bytes
            if ring["t_first"] is None:
                if not nfr:
                    return (None, pyaudio.paContinue)   # idle ticks before any audio
                ring["t_first"] = now - nfr / rate      # sync anchor: first REAL sample
                ring["frames"] = 0
            target = int((now - ring["t_first"]) * rate)
            miss = target - ring["frames"] - nfr
            if miss > rate * 0.25:                      # engine starved: true silence
                fill = int(min(miss, rate * 30))
                _push(b"\x00" * (fill * frame_bytes))
                ring["frames"] += fill
            if nfr:
                _push(in_data)
                ring["frames"] += nfr
            return (None, pyaudio.paContinue)

        # A bigger buffer means the callback fires less often, which leaves far
        # more headroom against scheduling jitter while the GPU is busy encoding.
        # That headroom is what keeps the high-rate Sonar stream (8ch @ 96kHz)
        # from dropping samples and sounding robotic.
        stream = self._pa.open(
            format=pyaudio.paInt16, channels=channels, rate=rate,
            input=True, input_device_index=dev["index"],
            frames_per_buffer=4096, stream_callback=callback,
        )
        self._streams.append(stream)

        def writer():
            try:
                while not self._stop.is_set() or not q.empty():
                    try:
                        wf.writeframes(q.get(timeout=0.3))
                    except queue.Empty:
                        continue
            finally:
                try:
                    wf.close()
                except Exception:
                    pass
                if drops["n"]:
                    log(f"Audio WARNING: '{label}' had {drops['n']} capture xrun(s) "
                        f"- if it sounds choppy, this is why.")
                if qdrops["n"]:
                    log(f"Audio WARNING: '{label}' dropped {qdrops['n']} buffer(s) to a "
                        f"disk backlog (slow/full drive); memory was capped to protect the app.")

        t = threading.Thread(target=writer, daemon=True)
        t.start()
        self._threads.append(t)
        log(f"Audio: capturing {label} -> {channels}ch @ {rate}Hz")

    def start(self):
        import pyaudiowpatch as pyaudio
        self._pa = pyaudio.PyAudio()
        wasapi = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)

        if SETTINGS["capture_system"]:
            # Which playback device to listen to: the user's explicit pick from
            # Settings > Audio, or the Windows default. (It was always the default
            # before, which looked random to anyone who switches outputs.)
            out = self._pa.get_device_info_by_index(wasapi["defaultOutputDevice"])
            want = str(SETTINGS.get("audio_output_device", "") or "").strip().lower()
            if want:
                for i in range(self._pa.get_device_count()):
                    d0 = self._pa.get_device_info_by_index(i)
                    if (d0.get("maxOutputChannels", 0) > 0
                            and not d0.get("isLoopbackDevice")
                            and want in str(d0.get("name", "")).lower()):
                        out = d0
                        break
                else:
                    log(f"Audio: chosen output '{want}' not found; using the default.")
            loop = None
            for d in self._pa.get_loopback_device_info_generator():
                if out["name"] in d["name"]:
                    loop = d
                    break
            if loop is None:  # fall back to first loopback device
                gen = self._pa.get_loopback_device_info_generator()
                loop = next(gen, None)
            if loop is not None:
                self.system_wav = os.path.join(
                    self.tmp_dir, f"system{('_' + self.tag) if self.tag else ''}.wav")
                self._open_capture(loop, self.system_wav, f"system ({out['name']})", "system")
            else:
                log("Audio: no WASAPI loopback device found; system sound skipped.")

        if SETTINGS["capture_mic"]:
            mic = self._resolve_mic(wasapi)
            if mic is not None:
                self.mic_wav = os.path.join(
                    self.tmp_dir, f"mic{('_' + self.tag) if self.tag else ''}.wav")
                self._open_capture(mic, self.mic_wav, f"mic ({mic['name']})", "mic")
            else:
                log("Audio: no microphone found; mic skipped.")

    def _resolve_mic(self, wasapi):
        want = SETTINGS["mic_name_contains"].strip().lower()
        if want:
            for i in range(self._pa.get_device_count()):
                d = self._pa.get_device_info_by_index(i)
                if d["maxInputChannels"] > 0 and not d.get("isLoopbackDevice") \
                        and want in d["name"].lower():
                    return d
        try:
            return self._pa.get_device_info_by_index(wasapi["defaultInputDevice"])
        except Exception:
            return None

    def first_sample_wallclock(self, kind):
        """Wall-clock time of this stream's first captured sample ('system'/'mic'),
        or None. The A/V sync anchors on this instead of guessing from durations."""
        with self._ring_lock:
            for r in self.rings:
                if r["kind"] == kind:
                    return r["t_first"]
        return None

    def signal_stop(self):
        """Tell capture threads to stop now (non-blocking), so audio and video
        stop at the same instant. First seals each ring (so a racing callback
        can't double-fill), then tops every stream up with silence to the current
        wall clock in small chunks - a recording that ENDS during a quiet stretch
        would otherwise have its last starved seconds missing from the WAV. The
        tail fill is capped at 2 minutes: beyond that the missing part is
        trailing silence anyway, and a multi-hour zero-buffer would spike RAM."""
        now = time.time()
        for r in list(self.rings):
            try:
                r["closed"] = True
                if r["t_first"] is not None and r["push"]:
                    miss = int((now - r["t_first"]) * r["rate"]) - r["frames"]
                    miss = min(miss, r["rate"] * 120)
                    while miss > 0:                              # 5s pieces
                        n = min(miss, r["rate"] * 5)
                        r["push"](b"\x00" * (n * r["frame_bytes"]))
                        r["frames"] += n
                        miss -= n
            except Exception:
                pass
        self._stop.set()

    def finalize(self):
        """Stop capture, then let writer threads flush the rest to disk."""
        # Stop the callback streams first so they stop filling the queues...
        for s in self._streams:
            try:
                s.stop_stream(); s.close()
            except Exception:
                pass
        # ...then let the writer threads drain whatever's left and close files.
        for t in self._threads:
            t.join(timeout=10)
            if t.is_alive():
                log("Audio: a writer thread is still flushing after 10s (slow/full "
                    "disk); its track may be slightly truncated.")
        if self._pa:
            try:
                self._pa.terminate()
            except Exception:
                pass

    def stop(self):
        self.signal_stop()
        self.finalize()

    def dump_ring(self, out_dir, seconds, trim_tail=0.0):
        """Write the last `seconds` of buffered audio to WAV file(s). Returns
        (system_wav_or_None, mic_wav_or_None, ends) where ends maps
        'system'/'mic' to the WALL-CLOCK time of the written wav's LAST sample.
        That anchor is what lets the clip mux line audio up against the video's
        own wall-clock end instead of guessing - the guess ('trim half a
        segment') left clip audio 1-2s EARLY whenever the open segment was
        young. trim_tail still drops the most-recent N seconds first (the clip's
        video ends in the past; audio buffered beyond it is useless)."""
        sys_path = mic_path = None
        ends = {}
        # Snapshot under the lock with only a shallow ref-copy of each deque (fast),
        # then do the expensive b"".join OUTSIDE the lock so the audio callback isn't
        # blocked appending to the ring while a long clip is assembled (that block was
        # causing capture drops exactly when the user saved a clip). Bytes chunks are
        # immutable, so the joined result is identical to joining under the lock.
        with self._ring_lock:
            snap_refs = [(r["kind"], r["rate"], r["channels"], list(r["chunks"]),
                          r.get("t_first"), r.get("frames", 0))
                         for r in self.rings]
        snapshot = [(kind, rate, channels, b"".join(chunks), t0, frames)
                    for (kind, rate, channels, chunks, t0, frames) in snap_refs]
        for kind, rate, channels, data, t0, frames in snapshot:
            frame = channels * 2                     # bytes per sample frame
            drop = int(rate * channels * 2 * max(0.0, trim_tail))
            drop -= drop % frame
            dropped_sec = 0.0
            if 0 < drop < len(data):
                data = data[:-drop]                  # discard the newest audio
                dropped_sec = drop / float(rate * channels * 2)
            want = int(rate * channels * 2 * seconds)
            tail = data[-want:] if want < len(data) else data
            tail = tail[len(tail) % frame:]          # keep cut on a sample boundary
            path = os.path.join(out_dir, f"{kind}_clip.wav")
            try:
                wf = wave.open(path, "wb")
                wf.setnchannels(channels); wf.setsampwidth(2); wf.setframerate(rate)
                wf.writeframes(tail); wf.close()
            except Exception as e:
                log(f"Replay: could not write {kind} audio ({e})")
                continue
            # Wall-clock of the wav's last sample: ring start + frames delivered
            # (the silence top-up keeps 'frames' tracking wall time), minus what
            # trim_tail actually removed.
            if t0 is not None and frames:
                ends[kind] = t0 + frames / float(rate) - dropped_sec
            if kind == "system":
                sys_path = path
            else:
                mic_path = path
        return sys_path, mic_path, ends


def list_audio_devices():
    """(playback_outputs, microphones) - device-name lists for the Settings
    pickers. WASAPI devices only, loopback mirrors excluded. Safe on failure."""
    outs, mics = [], []
    try:
        import pyaudiowpatch as pyaudio
        pa = pyaudio.PyAudio()
        try:
            was = pa.get_host_api_info_by_type(pyaudio.paWASAPI)["index"]
            for i in range(pa.get_device_count()):
                d = pa.get_device_info_by_index(i)
                if d.get("hostApi") != was or d.get("isLoopbackDevice"):
                    continue
                name = str(d.get("name", "")).strip()
                if not name:
                    continue
                if d.get("maxOutputChannels", 0) > 0 and name not in outs:
                    outs.append(name)
                if d.get("maxInputChannels", 0) > 0 and name not in mics:
                    mics.append(name)
        finally:
            pa.terminate()
    except Exception as e:
        log(f"Audio device scan failed: {e}")
    return outs, mics


def diag_audio():
    load_settings()
    try:
        import pyaudiowpatch as pyaudio
    except ImportError:
        print("PyAudioWPatch not installed. Run:  pip install PyAudioWPatch")
        return
    p = pyaudio.PyAudio()
    wasapi = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    out = p.get_device_info_by_index(wasapi["defaultOutputDevice"])
    inp = p.get_device_info_by_index(wasapi["defaultInputDevice"])
    print(f"\nDefault PLAYBACK (system sound will follow this): {out['name']}")
    print(f"Default MICROPHONE: {inp['name']}\n")
    print("Loopback devices (system capture uses one of these automatically):")
    for d in p.get_loopback_device_info_generator():
        print(f"  - {d['name']}")
    print("\nMicrophones / inputs you can target via 'mic_name_contains':")
    for i in range(p.get_device_count()):
        d = p.get_device_info_by_index(i)
        if d["maxInputChannels"] > 0 and not d.get("isLoopbackDevice"):
            print(f"  - {d['name']}")
    p.terminate()
    print("\nTip: to use your clean HyperX mic, set mic_name_contains to 'HyperX'.")


# ---------------------------------------------------------------------------
#  GPU / encoder auto-detection  (so it runs on AMD, NVIDIA, or Intel)
# ---------------------------------------------------------------------------
def get_screen_size():
    """Primary monitor pixel size (used only to probe the encoder at the real
    resolution - catches e.g. H.264's 4096px-wide hardware limit)."""
    if os.name == "nt":
        try:
            import ctypes
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
            u = ctypes.windll.user32
            w, h = u.GetSystemMetrics(0), u.GetSystemMetrics(1)
            if w and h:
                return int(w), int(h)
        except Exception:
            pass
    return 1920, 1080


def _enumerate_active_monitors():
    r"""All currently-active display monitors, each as a dict:
        device  - the '\\.\DISPLAYn' GDI name
        num     - the trailing integer of that name (Windows' display number)
        rect    - (left, top, right, bottom) in virtual-desktop pixels
        primary - True for the primary monitor
    Returned in no particular order. Windows-only; [] elsewhere or on error."""
    mons = []
    if os.name != "nt":
        return mons
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32

        class MONITORINFOEXW(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD),
                        ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT),
                        ("dwFlags", wintypes.DWORD),
                        ("szDevice", ctypes.c_wchar * 32)]

        MONITORENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.POINTER(wintypes.RECT), ctypes.c_void_p)
        handles = []

        def _cb(hmon, hdc, lprc, lparam):
            handles.append(hmon)
            return 1
        user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(_cb), 0)
        for hmon in handles:
            mi = MONITORINFOEXW()
            mi.cbSize = ctypes.sizeof(MONITORINFOEXW)
            if user32.GetMonitorInfoW(ctypes.c_void_p(hmon), ctypes.byref(mi)):
                dev = mi.szDevice or ""
                digits = "".join(c for c in dev if c.isdigit())
                mons.append({
                    "device": dev,
                    "num": int(digits) if digits else 0,
                    "rect": (mi.rcMonitor.left, mi.rcMonitor.top,
                             mi.rcMonitor.right, mi.rcMonitor.bottom),
                    "work": (mi.rcWork.left, mi.rcWork.top,
                             mi.rcWork.right, mi.rcWork.bottom),
                    "primary": bool(mi.dwFlags & 1),
                })
    except Exception:
        return []
    return mons


def _active_monitor_count():
    """How many monitors the screen-grabber can address (>=1)."""
    return max(1, len(_enumerate_active_monitors()))


def _resolve_capture_monitor():
    """Which screen to capture. Simple and predictable: the monitor_index setting,
    where 0 = primary screen (the default). "Auto"/-1 also means the primary screen.
    No foreground-window guessing - that proved unreliable across mixed multi-monitor
    setups and could silently record the wrong screen."""
    try:
        idx = int(SETTINGS.get("monitor_index", 0))
    except Exception:
        idx = 0
    return idx if idx >= 0 else 0



def _hdr_active():
    """True if ANY active display currently has HDR (advanced colour) switched ON.
    Windows-only, and deliberately CONSERVATIVE: any uncertainty returns False, so
    it can never wrongly tone-map an ordinary SDR desktop. This is what lets Lore
    record correctly when Windows HDR is on even if the app's HDR toggle is off."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        QDC_ONLY_ACTIVE_PATHS = 2

        class LUID(ctypes.Structure):
            _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]

        class SRC(ctypes.Structure):
            _fields_ = [("adapterId", LUID), ("id", wintypes.UINT),
                        ("modeInfoIdx", wintypes.UINT), ("statusFlags", wintypes.UINT)]

        class TGT(ctypes.Structure):
            _fields_ = [("adapterId", LUID), ("id", wintypes.UINT),
                        ("modeInfoIdx", wintypes.UINT), ("outputTechnology", wintypes.UINT),
                        ("rotation", wintypes.UINT), ("scaling", wintypes.UINT),
                        ("refreshNum", wintypes.UINT), ("refreshDen", wintypes.UINT),
                        ("scanline", wintypes.UINT), ("targetAvailable", wintypes.BOOL),
                        ("statusFlags", wintypes.UINT)]

        class PATH(ctypes.Structure):
            _fields_ = [("sourceInfo", SRC), ("targetInfo", TGT), ("flags", wintypes.UINT)]

        class MODE(ctypes.Structure):       # we only need the right size for the buffer
            _fields_ = [("infoType", wintypes.UINT), ("id", wintypes.UINT),
                        ("adapterId", LUID), ("blob", ctypes.c_byte * 64)]

        class HDR(ctypes.Structure):
            _fields_ = [("type", wintypes.UINT), ("size", wintypes.UINT),
                        ("adapterId", LUID), ("id", wintypes.UINT),
                        ("value", wintypes.UINT), ("colorEncoding", wintypes.UINT),
                        ("bitsPerColor", wintypes.UINT)]

        npaths, nmodes = wintypes.UINT(), wintypes.UINT()
        if user32.GetDisplayConfigBufferSizes(QDC_ONLY_ACTIVE_PATHS,
                                              ctypes.byref(npaths), ctypes.byref(nmodes)) != 0:
            return False
        paths = (PATH * npaths.value)()
        modes = (MODE * nmodes.value)()
        if user32.QueryDisplayConfig(QDC_ONLY_ACTIVE_PATHS, ctypes.byref(npaths), paths,
                                     ctypes.byref(nmodes), modes, None) != 0:
            return False
        GET_ADVANCED_COLOR_INFO = 9
        for i in range(npaths.value):
            req = HDR()
            req.type = GET_ADVANCED_COLOR_INFO
            req.size = ctypes.sizeof(HDR)
            req.adapterId = paths[i].targetInfo.adapterId
            req.id = paths[i].targetInfo.id
            if user32.DisplayConfigGetDeviceInfo(ctypes.byref(req)) == 0:
                # bit0 = advancedColorSupported, bit1 = advancedColorEnabled (HDR on)
                if req.value & 0x2:
                    return True
        return False
    except Exception:
        return False


def _sdr_white_nits():
    """The Windows 'SDR content brightness' level in nits - the brightness an HDR
    desktop draws WHITE (255,255,255) at. This is THE anchor for converting an
    HDR recording back to a normal-looking SDR file: convert against a textbook
    reference (100 or 203 nits) instead and everything comes out 1.2-2.4x too
    bright ('mega blown out' - the 1.21-1.23 bug). Returns the LARGEST level
    across active displays (SDR-only displays report the 80-nit floor, the HDR
    display carries the real slider value), or None if the query fails.
    Verified against the dev G95SC: slider 40% -> SDRWhiteLevel 3000 -> 240.0."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        QDC_ONLY_ACTIVE_PATHS = 2

        class LUID(ctypes.Structure):
            _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]

        class SRC(ctypes.Structure):
            _fields_ = [("adapterId", LUID), ("id", wintypes.UINT),
                        ("modeInfoIdx", wintypes.UINT), ("statusFlags", wintypes.UINT)]

        class TGT(ctypes.Structure):
            _fields_ = [("adapterId", LUID), ("id", wintypes.UINT),
                        ("modeInfoIdx", wintypes.UINT), ("outputTechnology", wintypes.UINT),
                        ("rotation", wintypes.UINT), ("scaling", wintypes.UINT),
                        ("refreshNum", wintypes.UINT), ("refreshDen", wintypes.UINT),
                        ("scanline", wintypes.UINT), ("targetAvailable", wintypes.BOOL),
                        ("statusFlags", wintypes.UINT)]

        class PATH(ctypes.Structure):
            _fields_ = [("sourceInfo", SRC), ("targetInfo", TGT), ("flags", wintypes.UINT)]

        class MODE(ctypes.Structure):
            _fields_ = [("infoType", wintypes.UINT), ("id", wintypes.UINT),
                        ("adapterId", LUID), ("blob", ctypes.c_byte * 64)]

        class SDRW(ctypes.Structure):   # DISPLAYCONFIG_SDR_WHITE_LEVEL
            _fields_ = [("type", wintypes.UINT), ("size", wintypes.UINT),
                        ("adapterId", LUID), ("id", wintypes.UINT),
                        ("SDRWhiteLevel", wintypes.ULONG)]

        npaths, nmodes = wintypes.UINT(), wintypes.UINT()
        if user32.GetDisplayConfigBufferSizes(QDC_ONLY_ACTIVE_PATHS,
                                              ctypes.byref(npaths), ctypes.byref(nmodes)) != 0:
            return None
        paths = (PATH * npaths.value)()
        modes = (MODE * nmodes.value)()
        if user32.QueryDisplayConfig(QDC_ONLY_ACTIVE_PATHS, ctypes.byref(npaths), paths,
                                     ctypes.byref(nmodes), modes, None) != 0:
            return None
        GET_SDR_WHITE_LEVEL = 11
        best = None
        for i in range(npaths.value):
            req = SDRW()
            req.type = GET_SDR_WHITE_LEVEL
            req.size = ctypes.sizeof(SDRW)
            req.adapterId = paths[i].targetInfo.adapterId
            req.id = paths[i].targetInfo.id
            if user32.DisplayConfigGetDeviceInfo(ctypes.byref(req)) == 0:
                nits = req.SDRWhiteLevel * 80.0 / 1000.0   # units of 1/1000 of 80 nits
                if nits > 0 and (best is None or nits > best):
                    best = nits
        return best
    except Exception:
        return None


_FILTER_CACHE = {}


def _has_filter(name):
    """Does the bundled ffmpeg have this filter? Probed once per session."""
    v = _FILTER_CACHE.get(name)
    if v is not None:
        return v
    try:
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        r = subprocess.run([SETTINGS["ffmpeg_path"], "-hide_banner", "-h", f"filter={name}"],
                           capture_output=True, text=True, timeout=10, creationflags=flags)
        v = (r.returncode == 0 and "Unknown filter" not in (r.stderr or "")
             and "Unknown filter" not in (r.stdout or ""))
    except Exception:
        v = False
    _FILTER_CACHE[name] = v
    return v


def _hdr_strategy():
    """How this capture should handle an HDR desktop:
      None      - no HDR handling (SDR desktop, or the user turned it off)
      'native'  - capture the float16 (scRGB) desktop surface zero-copy into an
                  AMF encoder, producing a TRUE 10-bit HDR10 (PQ/BT.2020) file.
    Why float16 is not optional: the colour-patch lab proved every other ddagrab
    readback of an HDR desktop (8-bit AND 10-bit) is LINEAR light hard-clipped at
    80 nits by Windows - most of the image is destroyed before any filter can
    touch it. That clipped source is what made 1.16-1.23 HDR washed/neon under
    every tone-map curve tried. Only AMF encoders accept the float16 surface on
    the GPU, so 'native' applies only to them; everything else records plain
    (build_video_cmd handles that), which is flat-ish but never neon.
    Accepts legacy values (bool / 'on' / 'tonemap')."""
    mode = str(SETTINGS.get("hdr_mode", "auto")).strip().lower()
    if mode in ("off", "false", "0", "no"):
        return None
    return "native" if _hdr_active() else None


def _enc_supports_10bit(enc):
    """Can this encoder produce a real 10-bit stream? Native HDR must never be
    attempted on 8-bit-only encoders (h264_nvenc, h264_amf, libx264) - the run
    would just die and burn a retry cycle on every recording."""
    e = (enc or "").lower()
    return ("av1" in e) or ("hevc" in e) or ("265" in e)


def _hdr_native_args(grab, enc_name=""):
    """(filtergraph, extra encoder args, global pre-args) for native HDR capture
    on an AMF encoder - the ONLY encoder family here that accepts the float16
    scRGB desktop surface directly (zero-copy d3d11; measured the same speed
    class as plain capture on the dev RX 9070 XT, and bit-exact PQ against the
    drawn-patch lab: white 255 -> 255, grey 128 -> 129 after finishing).

    The pieces, each load-bearing:
      * output_fmt=16bit    - the float16 surface; the only UNCLIPPED source.
      * -init_hw_device...  - a shared d3d11 device; without it AMF refuses the
                              float16 frames outright ('Invalid argument').
      * -bitdepth 10 / main10 - with 10-bit output AMF PQ-encodes the linear
                              floats at the true scRGB scale (1.0 = 80 nits,
                              verified against PQ maths to within quantisation).
      * the metadata BSF    - AMF stamps the container 'linear/gbr', which is
                              wrong; the BSF writes PQ/BT.2020 into the actual
                              bitstream header, which is what decoders trust."""
    if enc_name.startswith("av1"):
        depth = ["-bitdepth", "10"]
        bsf = ["-bsf:v", "av1_metadata=color_primaries=9:"
               "transfer_characteristics=16:matrix_coefficients=9:color_range=tv"]
    else:                                   # hevc_amf
        depth = ["-profile:v", "main10"]
        bsf = ["-bsf:v", "hevc_metadata=colour_primaries=9:"
               "transfer_characteristics=16:matrix_coefficients=9"]
    pre = ["-init_hw_device", "d3d11va=dd", "-filter_hw_device", "dd"]
    vf = f"{grab}:output_fmt=16bit[v]"
    return vf, depth + bsf, pre


def _hdr_to_sdr_vf(trc, nits=None):
    """The ONE offline HDR->SDR conversion used everywhere (finishing queue,
    Discord copies, thumbnails), so every consumer produces the same colours.
    Validated absolutely against drawn patches on the dev machine: white 255 ->
    255, grey 180 -> 180, grey 128 -> 129, red (255,0,0) -> (252,6,4).

    The recipe (each part fixes a measured failure - don't 'improve' casually):
      * setparams when the container says 'linear' - our own recordings: AMF
        writes real PQ/BT.2020 pixels but mislabels the container; concat-copied
        segments keep that label. Forcing the true interpretation makes the
        chain deterministic even if a decoder ignores the (correct) bitstream
        header that the recording BSF wrote.
      * npl = the Windows SDR white level AT RECORD TIME (the nits argument;
        falls back to querying now, then 240). PQ is absolute: dividing by the
        wrong white is exactly the old 'mega blown out' bug - npl=100 lifted a
        240-nit desktop 2.4x.
      * tonemap=clip:desat=0 - highlights above SDR white clip, exactly like an
        SDR monitor would show them. desat=0 matters: the filter's DEFAULT
        desat=2 bleeds blue into bright yellows/reds (measured +65/255 blue).
      * output transfer iec61966-2-1 (sRGB) - matches how the desktop actually
        displayed the content; the classic bt709 camera curve measured ~+7 too
        bright on every mid grey."""
    n = 240
    try:
        n = int(round(float(nits))) if nits else int(round(_sdr_white_nits() or 240))
    except Exception:
        pass
    n = max(80, min(1000, n))
    pre = ""
    if (trc or "").strip().lower() == "linear":
        pre = ("setparams=color_primaries=bt2020:color_trc=smpte2084:"
               "colorspace=bt2020nc,")
    return (pre + f"zscale=t=linear:npl={n},"
            "tonemap=tonemap=clip:param=1.0:desat=0,"
            "zscale=p=bt709:t=iec61966-2-1:m=bt709:r=tv")


def _is_hdr_trc(trc):
    """Is this transfer tag one of our HDR recordings? 'smpte2084'/'arib-std-b67'
    are real HDR labels; 'linear' is what AMF stamps on the CONTAINER of our
    float16-native recordings (the bitstream itself is PQ - see _hdr_native_args)."""
    return (trc or "").strip().lower() in ("smpte2084", "arib-std-b67", "linear")


def detect_gpu_vendor():
    """Return 'amd' / 'nvidia' / 'intel' / None by asking Windows what display
    adapter is installed. Prefers a discrete GPU when more than one is listed."""
    if os.name != "nt":
        return None
    try:
        flags = subprocess.CREATE_NO_WINDOW
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_VideoController | "
             "Select-Object -ExpandProperty Name"],
            capture_output=True, text=True, timeout=6, creationflags=flags
        ).stdout.lower()
    except Exception:
        out = ""
    if any(k in out for k in ("nvidia", "geforce", "rtx", "gtx")):
        return "nvidia"
    if any(k in out for k in ("radeon", "amd", "rx ")):
        return "amd"
    if any(k in out for k in ("intel", "arc", "iris", "uhd graphics")):
        return "intel"
    return None


def _encoder_works(enc, w, h, fps):
    """True if this encoder actually initialises on this machine. Feeds it a few
    synthetic nv12 frames at the real resolution - the same pixel format the real
    capture delivers - so a pass is representative."""
    if enc in _BAD_ENCODERS:
        return False
    cmd = [SETTINGS["ffmpeg_path"], "-hide_banner", "-loglevel", "error",
           "-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r={fps}",
           "-vf", "format=nv12", "-frames:v", "3", "-c:v", enc, "-f", "null", "-"]
    try:
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        return subprocess.run(cmd, capture_output=True, timeout=40,
                              creationflags=flags).returncode == 0
    except Exception:
        return False


def choose_encoder(vendor, w, h, fps, prefer_av1=True):
    """Pick the best WORKING encoder for this GPU. Tries the vendor's AV1 then
    HEVC hardware encoder, then any other vendor's HEVC (in case detection was
    off), then guarantees a result with software encoding. Encoders that died at
    runtime earlier this session (_BAD_ENCODERS) are skipped."""
    fam = {
        "amd":    ["av1_amf", "hevc_amf"],
        "nvidia": ["av1_nvenc", "hevc_nvenc"],
        "intel":  ["av1_qsv", "hevc_qsv"],
    }.get(vendor, [])
    if not prefer_av1:
        fam = [e for e in fam if not e.startswith("av1")]
    # Cross-vendor fallback. Include the hardware AV1 encoders here too (when AV1 is
    # wanted) so a machine whose GPU vendor couldn't be detected (e.g. PowerShell/WMI
    # locked down) still tries hardware AV1 before dropping to CPU software. The
    # h264 HARDWARE encoders come before software: an older GPU (GTX 6xx-9xx,
    # pre-Skylake Intel) still beats libx264 trying to chase 60fps on the CPU.
    tail = (["av1_amf", "av1_nvenc", "av1_qsv"] if prefer_av1 else []) \
        + ["hevc_amf", "hevc_nvenc", "hevc_qsv",
           "h264_nvenc", "h264_qsv", "h264_amf", "libx265", "libx264"]
    seen, order = set(), []
    for e in fam + tail:
        if e not in seen and e not in _BAD_ENCODERS:
            seen.add(e); order.append(e)
    for enc in order:
        if _encoder_works(enc, w, h, fps):
            return enc
    return "libx264"  # last resort; always present in a full ffmpeg build


def _capture_screen_size():
    """A representative resolution for the encoder probe. The capture target may be a
    secondary monitor LARGER than the primary, so probe at the biggest active monitor
    (and never below the primary) - that keeps the H.264 4096px-wide guard meaningful
    when capturing a 4K/ultrawide secondary. Falls back to the primary on any error."""
    pw, ph = get_screen_size()
    try:
        mons = _enumerate_active_monitors()
        if mons:
            w = max((m["rect"][2] - m["rect"][0]) for m in mons)
            h = max((m["rect"][3] - m["rect"][1]) for m in mons)
            return max(w, pw), max(h, ph)
    except Exception:
        pass
    return pw, ph


def resolve_encoder():
    """Turn the 'encoder' setting (auto / av1 / hevc / explicit) into a concrete
    encoder that works on THIS machine, and cache it for the session."""
    pref = str(SETTINGS.get("encoder", "auto")).lower()
    w, h = _capture_screen_size()
    fps = int(SETTINGS["framerate"])
    if pref in ("auto", "av1", "hevc"):
        vendor = detect_gpu_vendor()
        enc = choose_encoder(vendor, w, h, fps, prefer_av1=(pref != "hevc"))
        log(f"GPU detected: {vendor or 'unknown'} -> encoder '{enc}' @ {w}x{h}/{fps}")
    elif _encoder_works(pref, w, h, fps):
        enc = pref
    else:
        vendor = detect_gpu_vendor()
        enc = choose_encoder(vendor, w, h, fps, True)
        log(f"Encoder '{pref}' didn't work here; falling back to '{enc}'")
    SETTINGS["_encoder_resolved"] = enc
    return enc


def _current_encoder():
    return SETTINGS.get("_encoder_resolved") or resolve_encoder()


def _ffmpeg_ok():
    """Quick one-shot check that the ffmpeg binary actually runs. Lets a missing or
    antivirus-quarantined ffmpeg surface as a plain-language message at startup
    instead of degrading into a permanent, silent 'never records'."""
    try:
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        r = subprocess.run([SETTINGS["ffmpeg_path"], "-version"],
                           capture_output=True, timeout=10, creationflags=flags)
        return r.returncode == 0
    except Exception:
        return False


def encoder_quality_flags(enc, br):
    """Rate-control + quality flags, tuned for QUALITY PER GIGABYTE: peak-constrained
    VBR instead of CBR, so quiet scenes stop burning bits and busy scenes may borrow
    up to 2x the target. Real files come out well under the old CBR sizes at equal
    or better quality. The option NAMES differ per encoder family, so this can't be
    shared - AMF uses -quality, NVENC uses -preset pN, etc."""
    q = SETTINGS["amf_quality"]
    vbr = ["-b:v", f"{br}M", "-maxrate", f"{br * 2}M", "-bufsize", f"{br * 4}M"]
    if enc.endswith("_amf"):
        return ["-rc", "vbr_peak", *vbr, "-quality", q]
    if enc.endswith("_nvenc"):
        preset = {"speed": "p1", "balanced": "p4", "quality": "p7"}.get(q, "p4")
        return ["-rc", "vbr", *vbr, "-preset", preset]
    if enc.endswith("_qsv"):
        preset = {"speed": "veryfast", "balanced": "medium", "quality": "slower"}.get(q, "medium")
        return [*vbr, "-preset", preset]
    # software libx264 / libx265: constant-quality capped at the same peak
    preset = {"speed": "veryfast", "balanced": "medium", "quality": "slow"}.get(q, "medium")
    return ["-crf", "23", "-maxrate", f"{br * 2}M", "-bufsize", f"{br * 4}M",
            "-preset", preset]


# ---------------------------------------------------------------------------
#  ffmpeg: video capture + final mux
# ---------------------------------------------------------------------------
def _game_window_title(pname):
    """Title of the given process's biggest visible top-level window, or None.
    Used by the EXPERIMENTAL window-only capture scope to aim gdigrab."""
    if os.name != "nt" or not pname:
        return None
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        pids = set()
        for pr in psutil.process_iter(["pid", "name"]):
            try:
                if (pr.info.get("name") or "").lower() == pname.lower():
                    pids.add(pr.info["pid"])
            except Exception:
                pass
        if not pids:
            return None
        best = {"area": 0, "title": None}

        @ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
        def _enum(h, _l):
            try:
                if not user32.IsWindowVisible(h) or user32.IsIconic(h):
                    return 1
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
                if pid.value not in pids:
                    return 1
                r = wintypes.RECT()
                user32.GetWindowRect(h, ctypes.byref(r))
                area = max(0, r.right - r.left) * max(0, r.bottom - r.top)
                if area <= best["area"]:
                    return 1
                n = user32.GetWindowTextLengthW(h)
                if n <= 0:
                    return 1
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(h, buf, n + 1)
                if buf.value:
                    best["area"] = area
                    best["title"] = buf.value
            except Exception:
                pass
            return 1
        user32.EnumWindows(_enum, 0)
        return best["title"]
    except Exception:
        return None


def build_video_cmd(out_pattern, start_number=0, monitor_index=None,
                    window_title=None):
    """Capture the screen and encode it, writing the stream as a sequence of
    short MP4 segments (out_pattern like '.../seg_%06d.mp4'). Segments let us
    (a) concat them into the full session file at the end, (b) grab just the
    last minute on demand for the replay hotkey, and (c) continue numbering
    after a pause - all without re-encoding. start_number is where this run's
    segment numbering begins (so a resumed run doesn't overwrite earlier ones).
    monitor_index overrides which screen to grab; None falls back to settings."""
    s = SETTINGS
    enc = _current_encoder()
    br = s["bitrate_mbps"]
    safe = _ENC_SAFE[0]
    mon = monitor_index if monitor_index is not None else s.get("monitor_index", 0)
    try:
        mon = int(mon)
    except Exception:
        mon = 0
    if mon < 0:
        mon = 0   # "Auto" records the primary screen (output 0) - simple and reliable
    # Never ask ddagrab for a screen that doesn't exist (a stale saved index, or a
    # monitor that was unplugged) - clamp to the real screen count so capture still
    # starts on a valid output instead of failing outright.
    mon = min(mon, _active_monitor_count() - 1)
    grab = f"ddagrab=output_idx={mon}:framerate={s['framerate']}"

    hdr_enc_args = []
    hdr_pre_args = []
    strategy = None if (_HDR_LEVEL[0] >= 1 or window_title) else _hdr_strategy()
    if strategy == "native" and not (enc.endswith("_amf") and _enc_supports_10bit(enc)):
        # Only AMF encoders accept the float16 surface (the sole unclipped HDR
        # source - see _hdr_strategy). Everyone else records plain SDR capture:
        # slightly flat on an HDR desktop, but stable and never neon.
        strategy = None
    if strategy == "native":
        # True HDR file: the float16 scRGB surface goes zero-copy into the AMF
        # encoder, which PQ-encodes it (verified bit-exact against PQ maths).
        # The finishing queue converts it to normal SDR right after the session.
        # If the chain yields zero frames, the watcher steps _HDR_LEVEL to plain.
        vf, hdr_enc_args, hdr_pre_args = _hdr_native_args(grab, enc)
        # Give the HDR master a bitrate FLOOR: it lives through one more encode
        # generation (the SDR finishing pass) than a normal recording, so the
        # master must not be the quality bottleneck - the finished file should
        # be bounded by the user's own bitrate. Costs disk only TEMPORARILY:
        # finishing re-encodes at the user's bitrate and replaces this file.
        br = max(int(br), 30)
    elif enc.endswith(("_amf", "_nvenc")) and not safe:
        # AMF and NVENC consume ddagrab's d3d11 frames directly (zero-copy, most
        # efficient). On fragile setups (some 4K AMD combos, hybrid laptops where
        # capture runs on the iGPU and NVENC on the dGPU) this fast path can fail
        # to start - the encoder-died recovery then retries in 'safe' mode below
        # and remembers it, so it self-heals after one lost start, once ever.
        vf = f"{grab}[v]"
    else:
        # NVENC / QSV / software (and AMF in safe mode) take frames in system
        # memory as nv12 - the most compatible path.
        vf = f"{grab},hwdownload,format=bgra,format=nv12[v]"

    seg = max(2, int(s.get("segment_seconds", 4)))
    fps = int(s["framerate"])
    gop = max(1, fps * seg)
    # Force a keyframe on each segment boundary so cuts land on time. Some
    # encoders choke on the expression form, so safe mode relies on -g alone.
    keyframes = [] if safe else ["-force_key_frames", f"expr:gte(t,n_forced*{seg})"]
    # Safe mode also drops encoder-specific tuning (-quality/-preset/-rc), which
    # can be rejected by some driver/ffmpeg combos, for plain CBR.
    rc = (["-b:v", f"{br}M", "-maxrate", f"{br}M", "-bufsize", f"{br * 2}M"]
          if safe else encoder_quality_flags(enc, br))
    tail = [
        "-c:v", enc,
        *rc,
        *hdr_enc_args,                 # 10-bit depth + PQ/BT.2020 bitstream tags
        "-g", str(gop), *keyframes,
        # MP4 segments work for AV1 / HEVC / H.264 alike (MPEG-TS can't carry
        # AV1, which is what AMD GPUs pick by default - that broke saving).
        "-f", "segment", "-segment_time", str(seg),
        "-segment_format", "mp4", "-reset_timestamps", "1",
        "-segment_start_number", str(int(start_number)),
        out_pattern,
    ]
    if window_title:
        # EXPERIMENTAL window-only capture: gdigrab follows the one window by
        # title, so a windowed game records without the rest of the desktop.
        # Plain SDR frames via system memory (no HDR handling here - gdigrab
        # has no access to the float16 surface). If this path yields nothing,
        # the watcher falls back to the proven screen capture mid-session.
        return [
            s["ffmpeg_path"], "-y", "-hide_banner", "-loglevel", "error", "-stats",
            "-f", "gdigrab", "-framerate", str(fps),
            "-i", f"title={window_title}",
            "-vf", "crop=iw-mod(iw\\,2):ih-mod(ih\\,2),format=nv12",
            *tail,
        ]
    return [
        s["ffmpeg_path"], "-y", "-hide_banner", "-loglevel", "error", "-stats",
        *hdr_pre_args,                 # shared d3d11 device (float16 HDR capture only)
        "-filter_complex", vf,
        "-map", "[v]",
        *tail,
    ]


def _work_dir():
    """A SINGLE hidden parent folder for in-progress capture scratch (segments +
    wavs), kept on the same drive as the output so the final assemble is a fast
    local read. One tidy folder instead of a litter of '.tmp_*' folders sitting
    next to the user's finished videos."""
    d = os.path.join(SETTINGS.get("output_dir", "") or _data_dir(), ".lore_cache")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        d = os.path.join(_data_dir(), ".lore_cache")
        os.makedirs(d, exist_ok=True)
    return d


def _salvage_interrupted():
    """A previous run died mid-save (force-kill, crash, power cut). NEVER
    just sweep its remains - they are the user's footage:
      * '<name>.mp4.__assembling__.mp4' whose weld actually FINISHED (it
        probes to a real duration) only missed its final rename - promote it
        into the library.
      * a session folder still holding seg_*.mp4 gets a best-effort re-weld:
        video concat + whatever audio the run captured, muxed from zero.
        (The wall-clock anchors died with the process, so sync is within a
        few hundred ms - imperfect footage beats deleted footage.)
    Anything truly unreadable is parked in .lore_cache\\lost, never deleted.
    Born of a real loss: a 69-minute session was welding when the process
    was killed, and the next boot swept its segments."""
    out = SETTINGS.get("output_dir", "")
    if not out or not os.path.isdir(out):
        return
    ff = SETTINGS.get("ffmpeg_path") or "ffmpeg"
    lost = os.path.join(_work_dir(), "lost")

    def _fresh(path):
        # younger than a minute = something LIVE is writing it, not a corpse
        try:
            return time.time() - os.path.getmtime(path) < 60
        except Exception:
            return True
    # 1) finished-but-unrenamed assemblies. Scan the library root AND every
    #    per-game shelf (<Game>/Videos, <Game>/Clips): real recordings assemble
    #    INSIDE their shelf, so a root-only scan left a completed weld orphaned
    #    forever - the exact bug that stranded a finished session as a stuck
    #    '.__assembling__.mp4' the app never recovered.
    scan_dirs = {out}
    try:
        for _d, _kind in _library_dirs(out):
            scan_dirs.add(_d)
    except Exception:
        pass
    for d in scan_dirs:
        try:
            entries = list(os.listdir(d))
        except Exception:
            continue
        for name in entries:
            if not name.endswith(".__assembling__.mp4"):
                continue
            p = os.path.join(d, name)
            if _fresh(p):
                continue
            final = os.path.join(d, name[:-len(".__assembling__.mp4")])
            try:
                if (_probe_duration(p) or 0) > 1.0 and not os.path.exists(final):
                    os.replace(p, final)
                    _record_made_file(final)
                    log("Recovered an interrupted save: "
                        + os.path.basename(final))
                else:
                    os.makedirs(lost, exist_ok=True)
                    os.replace(p, os.path.join(lost, name))
                    log("An interrupted save could not be read; parked in "
                        ".lore_cache\\lost: " + name)
            except Exception as e:
                log(f"Salvage skipped for {name}: {e}")
    # 2) orphaned session folders with real segments -> best-effort weld
    try:
        cache = _work_dir()
        for name in list(os.listdir(cache)):
            d = os.path.join(cache, name)
            if not os.path.isdir(d) or name == "lost":
                continue
            segs = _list_segments(d)
            if not segs or _fresh(segs[-1]):
                continue
            final = os.path.join(out, name + ".mp4")
            if os.path.exists(final):
                final = os.path.join(out, name + "_recovered.mp4")
            tmp = final + ".__assembling__.mp4"
            try:
                wavs = [os.path.join(d, w) for w in sorted(os.listdir(d))
                        if w.endswith(".wav")
                        and os.path.getsize(os.path.join(d, w)) > 64_000]
                lst = os.path.join(d, "concat.txt")
                with open(lst, "w", encoding="utf-8") as fh:
                    for s in segs:
                        fh.write("file '" + s.replace("'", "'\\''") + "'\n")
                cmd = [ff, "-y", "-hide_banner", "-loglevel", "error",
                       "-f", "concat", "-safe", "0", "-i", lst]
                for w in wavs[:2]:
                    cmd += ["-i", w]
                cmd += ["-map", "0:v", "-c:v", "copy"]
                if wavs:
                    if len(wavs) >= 2:
                        cmd += ["-filter_complex",
                                "[1:a][2:a]amix=inputs=2:duration=longest[a]",
                                "-map", "[a]"]
                    else:
                        cmd += ["-map", "1:a"]
                    cmd += ["-c:a", "aac", "-b:a", "192k"]
                cmd += ["-movflags", "+faststart", tmp]
                flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                r = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.PIPE, creationflags=flags,
                                   timeout=1800)
                if r.returncode == 0 and os.path.isfile(tmp) \
                        and os.path.getsize(tmp) > 100_000:
                    os.replace(tmp, final)
                    _record_made_file(final)
                    log("Recovered an interrupted recording: "
                        + os.path.basename(final))
                    shutil.rmtree(d, ignore_errors=True)
                else:
                    for ln in (r.stderr or b"").decode("utf-8", "ignore") \
                            .splitlines()[-2:]:
                        log("  ffmpeg(salvage): " + ln)
                    os.makedirs(lost, exist_ok=True)
                    os.replace(d, os.path.join(lost, name))
                    log("Couldn't re-weld a leftover session; parked in "
                        ".lore_cache\\lost: " + name)
            except Exception as e:
                log(f"Salvage failed for {name}: {e}")
                try:
                    if os.path.isfile(tmp):
                        os.remove(tmp)
                except Exception:
                    pass
    except Exception:
        pass


def _migrate_library_layout():
    """One-time (and self-healing) shelving: move flat legacy recordings into
    per-game folders - <Game>/Videos and <Game>/Clips - and keep the storage
    manifest, finish queue and cached thumbnails pointing at the moved files.
    Skips anything younger than 3 minutes (it may still be being written)."""
    out = SETTINGS.get("output_dir", "")
    if not out or not os.path.isdir(out):
        return
    remap = {}

    def _shelve(src_dir, kind):
        if not os.path.isdir(src_dir):
            return
        for f in list(os.listdir(src_dir)):
            p = os.path.join(src_dir, f)
            try:
                if (not os.path.isfile(p) or not f.lower().endswith(".mp4")
                        or ".__" in f or f.startswith(".")):
                    continue
                if time.time() - os.path.getmtime(p) < 180:
                    continue
                base = _parse_clip_name(f)
                nd = _game_shelf(base, kind)
                np = os.path.join(nd, f)
                if os.path.abspath(np) == os.path.abspath(p) or os.path.exists(np):
                    continue
                os.rename(p, np)
                remap[os.path.normcase(os.path.abspath(p))] = np
                # thumbnails already live in ONE root cache keyed by the
                # (unique) filename, so a moved recording keeps its thumb -
                # nothing to relocate.
            except Exception as e:
                log(f"shelving skipped {f}: {e}")
    _shelve(out, "session")
    _shelve(os.path.join(out, "Clips"), "clip")
    # SELF-HEAL stale records: if something else moved files onto their
    # shelves (a helper, a hand), manifest/queue entries still pointing at
    # the old flat spots are re-aimed at wherever the file actually lives.
    try:
        with _MANIFEST_LOCK:
            paths, _ = _load_manifest()
            healed = set()
            changed = False
            for p in paths:
                if os.path.isfile(p):
                    healed.add(p)
                    continue
                bn = os.path.basename(p)
                kind = "clip" if ("_clip_" in bn or "_cut_" in bn) else "session"
                cand = os.path.join(_game_shelf(_parse_clip_name(bn), kind,
                                                make=False), bn)
                if os.path.isfile(cand):
                    healed.add(os.path.normcase(os.path.abspath(cand)))
                    changed = True
                else:
                    healed.add(p)
            if changed:
                _save_manifest(healed)
                log("Re-aimed ownership records at the shelved files.")
    except Exception:
        pass
    try:
        q = _load_finish_queue()
        qchanged = False
        for it in q:
            fp = it.get("path", "")
            if fp and not os.path.isfile(fp):
                bn = os.path.basename(fp)
                cand = os.path.join(_game_shelf(_parse_clip_name(bn),
                                                "session", make=False), bn)
                if os.path.isfile(cand):
                    it["path"] = os.path.abspath(cand)
                    qchanged = True
        if qchanged:
            _save_finish_queue(q)
    except Exception:
        pass
    if not remap:
        return
    log(f"Shelved {len(remap)} recordings into per-game folders.")
    # ownership manifest follows the files
    try:
        with _MANIFEST_LOCK:
            paths, _ = _load_manifest()
            changed = False
            for old_p, new_p in remap.items():
                if old_p in paths:
                    paths.discard(old_p)
                    paths.add(os.path.normcase(os.path.abspath(new_p)))
                    changed = True
            if changed:
                _save_manifest(paths)
    except Exception:
        pass
    # pending HDR restorations follow too
    try:
        q = _load_finish_queue()
        changed = False
        for it in q:
            k = os.path.normcase(os.path.abspath(it.get("path", "")))
            if k in remap:
                it["path"] = os.path.abspath(remap[k])
                changed = True
        if changed:
            _save_finish_queue(q)
    except Exception:
        pass


def _sweep_orphan_temp():
    """Tidy TRUE leftovers from previous runs - but salvage runs FIRST, and
    on its OWN thread: a rescue weld can take minutes of ffmpeg, and the
    watcher must never wait on it (a recorder that boots late records
    late). What's swept here synchronously is only empty scratch, legacy
    '.tmp_*' litter and half-written SDR conversions (whose HDR originals
    still exist untouched)."""
    threading.Thread(target=_salvage_interrupted, daemon=True).start()
    removed = 0
    try:
        cache = _work_dir()
        for name in os.listdir(cache):
            if name == "lost":
                continue          # parked salvage evidence - never touch
            p = os.path.join(cache, name)
            if os.path.isdir(p) and not _list_segments(p):
                shutil.rmtree(p, ignore_errors=True)
                removed += 1
    except Exception:
        pass
    # legacy location: '.tmp_<game>_<stamp>' folders directly in the output dir
    try:
        out = SETTINGS.get("output_dir", "")
        if out and os.path.isdir(out):
            for name in os.listdir(out):
                if name.startswith(".tmp_"):
                    p = os.path.join(out, name)
                    if os.path.isdir(p):
                        shutil.rmtree(p, ignore_errors=True)
                        removed += 1
    except Exception:
        pass
    # half-written work temps from a crash/kill: '<name>.mp4.__sdr__.mp4'
    # (conversion) and '<base>_cut_<stamp>.__tmp.mp4' (trim). The temps live on
    # the per-game SHELVES now, not just the flat legacy dirs - sweep every
    # folder a recording can live in (the same single source of truth the
    # scanner uses), and only LORE's own '.__' work names, nothing else.
    # Age-gate 10 minutes so a temp a LIVE worker is writing right now survives.
    try:
        out = SETTINGS.get("output_dir", "")
        dirs = [d for d, _k in _library_dirs(out)] if out else []
        now = time.time()
        for d in dirs:
            if os.path.isdir(d):
                for name in os.listdir(d):
                    if ".__sdr__." in name or ".__tmp" in name:
                        p = os.path.join(d, name)
                        try:
                            if now - os.path.getmtime(p) > 600:
                                os.remove(p)
                                removed += 1
                        except Exception:
                            pass
    except Exception:
        pass
    if removed:
        log(f"Cleaned up {removed} leftover temp folder(s) from a previous run.")


def _list_segments(seg_dir):
    """All finished+current capture segments in order (oldest -> newest)."""
    try:
        names = [f for f in os.listdir(seg_dir)
                 if f.startswith("seg_") and f.endswith(".mp4")]
    except Exception:
        return []
    return [os.path.join(seg_dir, f) for f in sorted(names)]


def _concat_copy(ffmpeg, seg_files, out_path):
    """Concatenate segments into out_path with no re-encode (instant). If the
    join fails - which usually means the final segment was truncated by a crash
    or a force-kill - retry once without that last segment, so a long recording
    is never lost to one bad tail file."""
    if not seg_files:
        return False

    def _run(files):
        list_path = out_path + ".list.txt"
        try:
            with open(list_path, "w", encoding="utf-8") as fh:
                for f in files:
                    p = os.path.abspath(f).replace("\\", "/").replace("'", "'\\''")
                    fh.write(f"file '{p}'\n")
        except Exception:
            return False
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
               "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", out_path]
        try:
            r = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE, creationflags=flags,
                               timeout=1800)
        except Exception as e:
            log(f"Concat error: {e}")
            r = None
        try:
            os.remove(list_path)
        except Exception:
            pass
        return bool(r) and r.returncode == 0 and os.path.isfile(out_path)

    if _run(seg_files):
        return True
    if len(seg_files) > 1:
        log("Concat failed; retrying without the final (likely truncated) segment.")
        return _run(seg_files[:-1])
    return False


def _is_lore_recording(name):
    """Heuristic 'looks unmistakably like a file Lore made', used ONLY to SEED
    the ownership manifest on first run after an upgrade. Lore names its files
    '<base>_YYYYMMDD_HHMMSS.mp4' (and clips '<base>_clip_...'), where <base> is a
    real game/app name. We deliberately REJECT names with no base before the
    date+time (e.g. a stock Android camera clip '20240101_120000.mp4') and common
    phone/camera/screen-recorder prefixes, because those share the date+time
    signature. Day-to-day deletion is driven by the explicit manifest
    (_record_made_file), NOT this heuristic, so a user's own videos sharing the
    folder are never at risk."""
    base = name[:-4] if name.lower().endswith(".mp4") else name
    parts = base.split("_")
    # require at least one base segment BEFORE the date+time, so a bare
    # 'YYYYMMDD_HHMMSS.mp4' camera export (len 2) is rejected outright.
    if not (len(parts) >= 3
            and len(parts[-1]) == 6 and parts[-1].isdigit()
            and len(parts[-2]) == 8 and parts[-2].isdigit()):
        return False
    prefix = "_".join(parts[:-2]).strip().lower()
    if not prefix:
        return False
    # prefixes that collide with the signature but are NOT Lore files
    CAMERA = {"vid", "img", "pxl", "mvimg", "mov", "dsc", "dscn", "dji", "gopro",
              "gx", "burst", "pano", "screenrecording", "screen-recording",
              "screenrec", "rec", "capture", "video", "wp", "signal", "whatsapp"}
    return prefix not in CAMERA


_MANIFEST_LOCK = threading.Lock()


def _manifest_path():
    return os.path.join(_data_dir(), "created_files.json")


def _load_manifest():
    """The set of absolute paths Lore itself created (recordings + clips), plus
    a flag saying whether the manifest existed at all. Returns (set, existed)."""
    p = _manifest_path()
    if not os.path.isfile(p):
        return set(), False
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        return {os.path.normcase(os.path.abspath(x)) for x in data}, True
    except Exception:
        return set(), False


def _save_manifest(paths):
    try:
        _atomic_write_json(_manifest_path(), sorted(paths))
    except Exception:
        pass


def _record_made_file(path):
    """Remember that Lore created this file, so the storage cap can later delete
    it WITHOUT ever touching a user's unrelated videos in the same folder. This is
    the authoritative ownership record; the name heuristic above is only a seed."""
    if not path:
        return
    try:
        with _MANIFEST_LOCK:      # two finalizes/clips can land at the same moment
            paths, _existed = _load_manifest()
            paths.add(os.path.normcase(os.path.abspath(path)))
            _save_manifest(paths)
    except Exception:
        pass


def enforce_storage_cap():
    """If a storage cap is set, delete the oldest Lore-made full recordings in
    the output folder until under the limit. Ownership comes from an explicit
    manifest written whenever Lore saves a file (_record_made_file), so this can
    NEVER delete a user's unrelated videos that merely share the folder - the exact
    promise the old name-pattern check couldn't keep (it collided with phone/camera
    exports like 'VID_20240101_120000.mp4'). On the first run the manifest is seeded
    from existing files whose name unmistakably matches Lore' own signature
    (camera/phone exports excluded). If ownership is unknown, nothing is deleted."""
    cap_gb = SETTINGS.get("max_storage_gb", 0) or 0
    if cap_gb <= 0:
        return
    out = SETTINGS["output_dir"]
    with _MANIFEST_LOCK:
        owned, existed = _load_manifest()
        if not existed:
            # one-time seed from existing, unmistakably-ours files, so the cap keeps
            # managing pre-upgrade recordings without ever matching a camera clip.
            seed = set()
            try:
                for f in os.listdir(out):
                    fp = os.path.join(out, f)
                    if f.lower().endswith(".mp4") and _is_lore_recording(f) \
                            and os.path.isfile(fp):
                        seed.add(os.path.normcase(os.path.abspath(fp)))
            except Exception:
                pass
            owned = seed
            _save_manifest(owned)
    if not owned:
        return     # nothing is known to be ours -> never delete anything (fail-safe)
    # Recordings at the top level AND saved clips in the Clips subfolder both count
    # toward the cap (clips are manifest-owned too - excluding them let the Clips
    # folder grow without bound while the cap starved the main recordings).
    files = []
    for folder, _kind in _library_dirs(out):
        try:
            for f in os.listdir(folder):
                fp = os.path.join(folder, f)
                if f.lower().endswith(".mp4") \
                        and os.path.normcase(os.path.abspath(fp)) in owned \
                        and os.path.isfile(fp):
                    files.append(fp)
        except Exception:
            continue

    def _mtime_safe(p):
        try:
            return os.path.getmtime(p)
        except OSError:
            return 0.0             # vanished mid-scan: sorts first, delete no-ops
    files.sort(key=_mtime_safe)    # oldest first
    try:
        total = sum(os.path.getsize(p) for p in files)
    except Exception:
        return
    cap = cap_gb * (1024 ** 3)
    i = 0
    deleted = set()
    while total > cap and i < len(files):
        p = files[i]
        try:
            sz = os.path.getsize(p)
            os.remove(p)
            total -= sz
            deleted.add(os.path.normcase(os.path.abspath(p)))
            log(f"Storage cap: deleted oldest clip {os.path.basename(p)}")
        except Exception:
            pass
        i += 1
    if deleted:
        with _MANIFEST_LOCK:      # re-read: saves may have added entries meanwhile
            cur, _e = _load_manifest()
            _save_manifest(cur - deleted)


def _probe_duration(path):
    """Return the media duration in seconds via ffprobe, or None."""
    if not path or not os.path.isfile(path):
        return None
    d = os.path.dirname(SETTINGS["ffmpeg_path"])
    name = "ffprobe.exe" if os.name == "nt" else "ffprobe"
    exe = os.path.join(d, name) if d else "ffprobe"
    try:
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        r = subprocess.run(
            [exe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nokey=1", path],
            capture_output=True, text=True, creationflags=flags, timeout=15)
        return float(r.stdout.strip())
    except Exception:
        return None


def build_mux_cmd(video, system_wav, mic_wav, out_final, offset_ms=0, mic_offset_ms=None,
                  video_is_concat=False):
    """offset_ms shifts the system track; mic_offset_ms the mic track (defaults to
    the same). Each stream gets its OWN correction because they start at slightly
    different wall-clock moments. video_is_concat=True treats `video` as a concat
    list file (the segments are read directly - saves writing the multi-GB merged
    intermediate, which doubled save time on hard drives)."""
    s = SETTINGS
    vin = (["-f", "concat", "-safe", "0", "-i", video] if video_is_concat
           else ["-i", video])
    cmd = [s["ffmpeg_path"], "-y", "-hide_banner", "-loglevel", "warning"] + vin

    audio_inputs = []  # (label, path, offset_ms)
    if system_wav and os.path.isfile(system_wav):
        cmd += ["-i", system_wav]
        audio_inputs.append(("System", system_wav, offset_ms))
    if mic_wav and os.path.isfile(mic_wav):
        cmd += ["-i", mic_wav]
        audio_inputs.append(("Mic", mic_wav,
                             offset_ms if mic_offset_ms is None else mic_offset_ms))

    n = len(audio_inputs)
    if n == 0:
        cmd += ["-map", "0:v", "-c:v", "copy", out_final]
        return cmd

    # A/V sync correction, BAKED INTO THE SAMPLES. We used to delay the audio with
    # -itsoffset, but that records the shift as an MP4 edit-list / start-time, which
    # many players silently ignore - so the audio still played early. Prepending real
    # silence (adelay) for a positive offset, or trimming the head (atrim) for a
    # negative one, physically moves the audio and survives every player.
    def _sync(ms):
        off = int(round(ms))
        if off > 0:
            return f",adelay=delays={off}:all=1"        # audio starts late -> pad its head
        if off < 0:
            return (f",atrim=start={(-off) / 1000.0:.3f},"
                    "asetpts=PTS-STARTPTS")             # audio starts early -> trim its head
        return ""

    # Normalize EVERY audio input to clean stereo 48 kHz before doing anything
    # else. Capturing a virtual surround device (e.g. SteelSeries Sonar - Gaming)
    # yields 8ch @ 96kHz; left as-is the file is 7.1/96kHz, which a player has to
    # downmix on the fly - that's the hollow/harsh "tunnel" sound. Resampling to
    # 48k and doing a proper stereo downmix here once makes it play clean
    # everywhere.
    pre = [f"[{i + 1}:a]aresample=48000,aformat=channel_layouts=stereo"
           f"{_sync(audio_inputs[i][2])}[a{i}]" for i in range(n)]

    if n >= 2 and s["audio_mode"] == "mix":
        ins = "".join(f"[a{i}]" for i in range(n))
        graph = ";".join(pre + [f"{ins}amix=inputs={n}:duration=longest:normalize=0[a]"])
        cmd += ["-filter_complex", graph,
                "-map", "0:v", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", out_final]
    else:
        cmd += ["-filter_complex", ";".join(pre), "-map", "0:v"]
        for i in range(n):
            cmd += ["-map", f"[a{i}]"]
        cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k"]
        if n >= 2:
            for i, (label, _p, _o) in enumerate(audio_inputs):
                cmd += [f"-metadata:s:a:{i}", f"title={label}"]
        cmd += [out_final]
    return cmd


# ---------------------------------------------------------------------------
#  SDR finishing - convert native-HDR files to normal SDR AFTER the session
#  (never during gameplay: no live conversion of the float16 source can keep up
#  at high resolutions, so the conversion is done offline instead)
# ---------------------------------------------------------------------------
# 'path'/'t0'/'pct' are read by the dashboard to show a live "Converting..."
# badge (with real percent progress) on the file's card while ffmpeg works.
_FINISHING = {"proc": None, "path": None, "t0": 0.0, "pct": None,
              "busy": False, "aborted": False}

# Live BIND (save-mux) progress, read by state() for the tome's saving card:
# pct from ffmpeg's -progress out_time vs the session's known length, MB/s from
# the growing temp file. Also the instrumentation for "why was that save slow" -
# the completion log line records wall time, size and speed for every bind.
_BINDING = {"name": None, "pct": None, "eta": None, "mbps": None,
            "t0": 0.0, "total": 0.0}
_TRAY_ICON = [None]    # the pystray icon, stashed so the bind loop can whisper
                       # progress into the tooltip without threading ctl through
_FINISH_FAILS = {}     # path -> genuine failure count (interruptions don't count)

# Files the user is actively READING right now (the in-tome player streaming,
# the trim tool cutting). The SDR finisher must not try to replace these:
# Windows os.replace fails while any plain handle is open, and that failure
# used to burn the 3-strike budget for what was really just "you were
# watching it". Refcounted because the player issues overlapping range reads.
_ACTIVE_SOURCES = {}
_ACTIVE_LOCK = threading.Lock()


def _source_busy_add(path):
    ap = os.path.abspath(path)
    with _ACTIVE_LOCK:
        _ACTIVE_SOURCES[ap] = _ACTIVE_SOURCES.get(ap, 0) + 1


def _source_busy_done(path):
    ap = os.path.abspath(path)
    with _ACTIVE_LOCK:
        n = _ACTIVE_SOURCES.get(ap, 0) - 1
        if n <= 0:
            _ACTIVE_SOURCES.pop(ap, None)
        else:
            _ACTIVE_SOURCES[ap] = n


def _source_busy(path):
    with _ACTIVE_LOCK:
        return os.path.abspath(path) in _ACTIVE_SOURCES


def _finish_queue_path():
    return os.path.join(_data_dir(), "finish_queue.json")


# the queue is edited from the worker, the watcher tick, trims, deletes and
# Discord copies - like the manifest, its read-modify-write pairs need a lock
# or two writers interleave and one update is silently lost (RLock: the pairs
# below hold it across their load+save while load/save also take it solo)
_FINISH_Q_LOCK = threading.RLock()


def _load_finish_queue():
    """Queue entries are dicts {'path', 'nits'}: nits = the Windows SDR white
    level when the file was recorded, because the conversion must use the value
    from RECORD time even if the user moves the slider (or turns HDR off) before
    the conversion gets its idle moment. Plain-string entries from 1.23 are
    accepted and upgraded (their nits defaults at convert time)."""
    try:
        with _FINISH_Q_LOCK:
            with open(_finish_queue_path(), encoding="utf-8") as fh:
                raw = json.load(fh)
        out = []
        for it in raw:
            if isinstance(it, str):
                out.append({"path": it, "nits": None})
            elif isinstance(it, dict) and isinstance(it.get("path"), str):
                out.append({"path": it["path"], "nits": it.get("nits")})
        return out
    except Exception:
        return []


def _save_finish_queue(items):
    try:
        with _FINISH_Q_LOCK:
            _atomic_write_json(_finish_queue_path(), items)
        _FINISH_Q_CACHE["t"] = 0.0   # every writer lands here - wake the read cache
    except Exception:
        pass


def _queue_sdr_finish(path):
    """Remember that this recording/clip is HDR and should be converted to SDR
    once nothing is recording. Persisted, so it survives a restart. The current
    SDR white level is captured HERE (seconds after the recording ended) - see
    _load_finish_queue for why it rides along."""
    try:
        if not SETTINGS.get("sdr_finish", True) or not path:
            return
        if not _is_hdr_trc(_probe_color_trc(path)):
            return                     # already SDR
        dur = _probe_duration(path) or 0
        cap_min = int(SETTINGS.get("sdr_finish_max_min", 30) or 30)
        if dur > cap_min * 60:
            log(f"SDR finish skipped ({dur / 60:.0f} min > {cap_min} min cap): "
                + os.path.basename(path))
            return
        # one locked unit: a delete's queue rewrite racing this append used to
        # overwrite the new entry - the file then stayed HDR forever, silently
        with _FINISH_Q_LOCK:
            q = _load_finish_queue()
            ap = os.path.abspath(path)
            if not any(it["path"] == ap for it in q):
                q.append({"path": ap, "nits": _sdr_white_nits() or 240})
                _save_finish_queue(q)
                log("Queued for SDR conversion: " + os.path.basename(path))
    except Exception:
        pass


def _sdr_finish_abort():
    """A recording is starting: stop any in-flight conversion immediately (the
    file stays queued and is retried later). GPU belongs to the game."""
    p = _FINISHING.get("proc")
    if p is not None and p.poll() is None:
        _FINISHING["aborted"] = True
        try:
            p.terminate()
        except Exception:
            pass


_FINISH_Q_CACHE = {"t": 0.0, "q": []}


def _queued_finish_paths():
    """The queue as plain paths, through a small cache. state() polls every
    ~.6s and the badge scans hit this per file - each used to be a fresh file
    read + json parse. 5s is safe: _save_finish_queue zeroes the clock, so a
    real change still shows on the very next tick."""
    now = time.time()
    if now - _FINISH_Q_CACHE["t"] > 5.0:
        _FINISH_Q_CACHE["q"] = ([it["path"] for it in _load_finish_queue()]
                                if SETTINGS.get("sdr_finish", True) else [])
        _FINISH_Q_CACHE["t"] = now
    return _FINISH_Q_CACHE["q"]


def _finish_badge(path):
    """What the dashboard should say on this file's card:
        ('Making standard version - 43%', 'conv')  while ffmpeg works on it
        ('Fine to watch - converts when idle', 'wait')  while it waits its turn
        None                                        for a normal file
    Wording matters here: the recording is a CORRECT HDR file that already
    plays well in modern players - the conversion only makes it a smaller,
    standard video that works everywhere. The badge must not imply the file
    is broken while it waits (that read as 'what is it even converting?').
    The file stays clickable the whole time - conversion writes to a temp name
    and swaps in atomically. Queue reads ride the ~5s
    _queued_finish_paths cache (writes wake it) - the cards poll every second
    and the queue is a file on disk."""
    try:
        ap = os.path.abspath(path)
        if _FINISHING["busy"] and _FINISHING["path"] == ap:
            pct = _FINISHING.get("pct")
            if pct is not None:
                return (f"Restoring true colour — {pct:.0f}%", "conv")
            el = max(0, int(time.time() - (_FINISHING["t0"] or time.time())))
            return (f"Restoring true colour — {el // 60}:{el % 60:02d}", "conv")
        if ap in _queued_finish_paths():
            return ("Fine to watch — restores colour when idle", "wait")
    except Exception:
        pass
    return None


def _sdr_finish_worker(item, ctl=None):
    """Convert one HDR file to SDR in place with the measured-correct chain
    (_hdr_to_sdr_vf at the record-time SDR white level), re-encode with the
    machine's hardware encoder, copy the audio untouched, verify the result,
    then replace ATOMICALLY. The original is never at risk: any failure keeps
    it exactly as it was. A file that genuinely fails 3 times is dropped from
    the queue (with its HDR original intact) rather than retried forever."""
    path = item["path"]
    tmp_out = path + ".__sdr__.mp4"
    ok = False
    aborted = False
    try:
        # RE-CHECK before burning an idle hour: a queue entry can go stale (the
        # file was trim-replaced with an SDR cut while its dequeue was racing
        # another writer). Tone-mapping an already-SDR file crushes its colours.
        trc = _probe_color_trc(path)
        if not _is_hdr_trc(trc):
            ok = True          # nothing to do; the finally-block dequeues it
            return
        dur = _probe_duration(path) or 0
        vf = (_hdr_to_sdr_vf(trc, item.get("nits"))
              + ",format=nv12")
        enc = _current_encoder()
        br = int(SETTINGS.get("bitrate_mbps", 25))
        # Below-normal priority so this HDR->SDR re-encode NEVER starves video
        # playback, the editor or the UI. The conversion is a background nicety;
        # the app must stay responsive while it runs (at normal priority it fought
        # the in-tome player for CPU/GPU/disk, which is what made everything
        # stutter and feel like "saving is still happening").
        flags = ((subprocess.CREATE_NO_WINDOW
                  | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0))
                 if os.name == "nt" else 0)
        _FINISHING["aborted"] = False
        _FINISHING["pct"] = None
        cmd = [SETTINGS["ffmpeg_path"], "-y", "-hide_banner", "-loglevel", "error",
               "-progress", "pipe:1", "-nostats",
               "-i", path, "-vf", vf, "-c:v", enc,
               *encoder_quality_flags(enc, br),
               "-color_primaries", "bt709", "-color_trc", "bt709",
               "-colorspace", "bt709",
               # no +faststart here: it re-writes the ENTIRE multi-GB file at
               # the end (a whole extra disk pass) and only matters for web
               # streaming - local players and Discord's own re-encode don't care.
               "-c:a", "copy", tmp_out]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, creationflags=flags)
        _FINISHING["proc"] = proc
        err_tail = bytearray()

        def _read_err():
            # drain stderr as it comes: a decode-error-spamming source would
            # otherwise fill the 64K pipe and wedge ffmpeg until the watchdog
            # kills it - a stall billed as a strike the file didn't earn
            try:
                for raw_e in proc.stderr:
                    err_tail.extend(raw_e)
                    del err_tail[:-4096]
            except Exception:
                pass
        threading.Thread(target=_read_err, daemon=True).start()

        def _read_progress():
            # ffmpeg -progress emits 'out_time_ms=<microseconds>' lines; against
            # the known duration that's an honest percent for the card badge.
            try:
                for raw in proc.stdout:
                    ln = raw.decode("ascii", "ignore").strip()
                    if ln.startswith("out_time_ms=") and dur > 0:
                        try:
                            done = int(ln.split("=", 1)[1]) / 1_000_000.0
                            _FINISHING["pct"] = max(0, min(99, done / dur * 100))
                        except ValueError:
                            pass
            except Exception:
                pass
        threading.Thread(target=_read_progress, daemon=True).start()
        try:
            proc.wait(timeout=max(600, dur * 6 + 120))
        except subprocess.TimeoutExpired:
            proc.kill()
        aborted = _FINISHING["aborted"]
        if proc.returncode == 0 and os.path.isfile(tmp_out):
            new_dur = _probe_duration(tmp_out) or 0
            if dur <= 0 or abs(new_dur - dur) <= max(2.0, dur * 0.02):
                try:
                    os.replace(tmp_out, path)  # atomic: SDR takes the file's place
                    ok = True
                except PermissionError:
                    # The user is watching or cutting this exact file right
                    # now - that's not a conversion failure, so it must not
                    # burn a strike. Leave the queue entry for the next idle.
                    aborted = True
                    log("SDR conversion finished but the file is in use "
                        "(playing or being cut); will retry later: "
                        + os.path.basename(path))
            if ok:
                log("SDR conversion done: " + os.path.basename(path))
                # Refresh the cached thumbnail: the file's colours just changed.
                try:
                    tp = os.path.join(
                        _thumb_dir(os.path.dirname(path)),
                        os.path.splitext(os.path.basename(path))[0] + ".jpg")
                    if os.path.isfile(tp):
                        os.remove(tp)
                except Exception:
                    pass
                if ctl is not None:
                    try:
                        ctl.notify("Ready to share",
                                   os.path.basename(path) + " is now normal colour.")
                    except Exception:
                        pass
            elif not aborted:
                log(f"SDR conversion length mismatch ({new_dur:.1f}s vs "
                    f"{dur:.1f}s); keeping the HDR original.")
        elif aborted:
            log("SDR conversion paused (recording started); will retry later.")
        else:
            err = bytes(err_tail)
            for ln in err.decode("utf-8", "ignore").strip().splitlines()[-2:]:
                log("  ffmpeg(sdr): " + ln)
            log("SDR conversion attempt failed; keeping the HDR original for now.")
    except Exception as e:
        log(f"SDR conversion error ({e}); keeping the HDR original.")
    finally:
        _FINISHING["proc"] = None
        _FINISHING["path"] = None
        _FINISHING["pct"] = None
        try:
            if os.path.isfile(tmp_out):
                os.remove(tmp_out)
        except Exception:
            pass
        # Success (or a vanished source) leaves the queue. An ABORT keeps the entry
        # for the next idle. A genuine failure counts toward a 3-strike drop, so a
        # machine that can't convert doesn't spin ffmpeg forever. The whole
        # load->filter->save is one locked unit so a trim/delete editing the
        # queue at the same moment can't have its update overwritten.
        with _FINISH_Q_LOCK:
            q = _load_finish_queue()
            ap = os.path.abspath(path)
            if ok or not os.path.isfile(path):
                q = [x for x in q if x["path"] != ap]
                _save_finish_queue(q)
                _FINISH_FAILS.pop(ap, None)
            elif not aborted:
                n = _FINISH_FAILS.get(ap, 0) + 1
                _FINISH_FAILS[ap] = n
                if n >= 3:
                    q = [x for x in q if x["path"] != ap]
                    _save_finish_queue(q)
                    log("SDR conversion given up after 3 attempts (file stays HDR): "
                        + os.path.basename(path))
        _FINISHING["busy"] = False


def _sdr_finish_tick(ctl):
    """Called from the watcher's idle beat: start ONE queued conversion when
    nothing is recording or saving. The moment a game appears, the watcher
    calls _sdr_finish_abort() and the GPU is the game's again."""
    if _FINISHING["busy"] or not SETTINGS.get("sdr_finish", True):
        return
    if ctl.session is not None or ctl.saving > 0:
        return
    # Don't fight interactive playback/editing: if the media server streamed a
    # chunk in the last 20s the user is watching or scrubbing a video - leave the
    # machine to them and resume the conversion once they've stopped.
    if time.time() - _MEDIA.get("last_read", 0) < 20:
        return
    q = _load_finish_queue()
    q = [it for it in q if os.path.isfile(it["path"])]
    if not q:
        return
    _save_finish_queue(q)
    # Never convert a file the user is watching or cutting right now - the
    # final os.replace would fail against their open handle anyway.
    pick = next((it for it in q if not _source_busy(it["path"])), None)
    if pick is None:
        return
    _FINISHING["busy"] = True
    _FINISHING["path"] = pick["path"]     # dashboard badge reads these two
    _FINISHING["t0"] = time.time()
    threading.Thread(target=_sdr_finish_worker, args=(pick, ctl), daemon=True).start()


def _drain_stderr(proc, first_frame, tail):
    """Continuously drain ffmpeg's stderr so its pipe never blocks (which would
    freeze long recordings), and signal as soon as the first frame appears.
    Keeps a rolling tail of ALL stderr (in the `tail` bytearray) so that if the
    encoder dies - even during start-up, before any frame - we can log WHY."""
    try:
        while True:
            chunk = proc.stderr.read1(65536)
            if not chunk:
                break
            if not first_frame.is_set() and b"frame=" in chunk:
                first_frame.set()
            tail += chunk
            if len(tail) > 8000:           # keep only the last ~8 KB
                del tail[:-8000]
    except Exception:
        pass


# ---------------------------------------------------------------------------
#  Recording session
# ---------------------------------------------------------------------------
class Session:
    """One recording. Internally it can span several capture 'runs' (Pause stops
    a run keeping the footage; Continue starts the next run). At the end the runs
    are stitched into a single file with the paused gaps removed. Each run is
    muxed with its own A/V sync, so pause joints stay in sync; a normal one-run
    recording takes the simple proven path."""

    def __init__(self, game_name):
        self.game = game_name
        base = os.path.splitext(game_name)[0]
        try:
            _learn_game_display_name(game_name)
        except Exception:
            pass
        stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        # NOTE: the output_dir is created in start(), not here, so an unwritable /
        # disconnected save folder surfaces inside _safe_start's try (where it can be
        # explained to the user) instead of escaping Session() construction.
        self.base = base
        self.tmp = os.path.join(_work_dir(), f"{base}_{stamp}")
        os.makedirs(self.tmp, exist_ok=True)
        self.seg_pattern = os.path.join(self.tmp, "seg_%06d.mp4")
        self.final = os.path.join(_game_shelf(base, "session", make=False),
                                  f"{base}_{stamp}.mp4")
        self.vproc = None
        self.audio = None
        self.monitor_idx = None        # which screen to capture (resolved at start)
        self.window_title = None       # experimental window-only capture target
        self._first_frame = threading.Event()
        self._err = bytearray()        # rolling tail of the encoder's stderr
        self._replay_lock = threading.Lock()
        self.suspended = False
        self._hdr_used = False          # did the active run use HDR tone-mapping?
        self.runs = []                 # finished runs: {"sys","mic","nseg"}
        self._run_index = 0
        self._seg_start = 0            # next segment number (continues across pauses)
        self._run_vstart = 0          # first segment number of the current run

    # ---- capture run lifecycle --------------------------------------------
    def _start_run(self):
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self._first_frame = threading.Event()
        self._err = bytearray()
        self._run_vstart = self._seg_start
        # Remember whether THIS run is doing HDR capture, so the watcher can tell
        # an HDR path failure (recoverable by falling back to plain) from a dead
        # encoder. Mirror build_video_cmd's guard exactly: float16 HDR runs only
        # on a 10-bit-capable AMF encoder - any other encoder records PLAIN even
        # in auto mode, so it must not be flagged as HDR (wrong toast, wasted
        # ladder step, delayed encoder recovery).
        strat = _hdr_strategy()
        enc_now = _current_encoder()
        if strat == "native" and not (enc_now.endswith("_amf")
                                      and _enc_supports_10bit(enc_now)):
            strat = None
        self._hdr_used = bool(strat and _HDR_LEVEL[0] < 1)
        # AUDIO FIRST: the microphone and system streams open in well under a
        # second, while ffmpeg takes 1-3s to produce its first frame. Starting
        # audio first means the opening seconds of the game are never lost, and
        # the wall-clock sync anchors trim the surplus head off precisely.
        # (The old order started audio ~3s late and relied on a duration guess
        # to compensate - see _assemble for why that broke.)
        self.audio = None
        if SETTINGS["capture_system"] or SETTINGS["capture_mic"]:
            try:
                self.audio = AudioRecorder(self.tmp, tag=f"{self._run_index:02d}")
                self.audio.start()
            except Exception as e:
                log(f"Audio init failed ({e}); recording video only.")
                # Unwind any HALF-started capture (e.g. system opened, mic failed):
                # without this the orphaned stream + writer thread would keep the
                # device busy and grow a WAV in the tmp dir for the whole session.
                try:
                    if self.audio is not None:
                        self.audio.stop()
                except Exception:
                    pass
                self.audio = None
        self.vproc = subprocess.Popen(
            build_video_cmd(self.seg_pattern, start_number=self._seg_start,
                            monitor_index=self.monitor_idx,
                            window_title=self.window_title),
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, creationflags=flags,
        )
        threading.Thread(target=_drain_stderr,
                         args=(self.vproc, self._first_frame, self._err),
                         daemon=True).start()
        self._first_frame.wait(timeout=1.5)

    def err_text(self):
        """The encoder's recent stderr (so a crash can be diagnosed)."""
        try:
            return bytes(self._err).decode("utf-8", "ignore").strip()
        except Exception:
            return ""

    def _stop_run(self):
        """Stop the current capture run cleanly and record what it produced."""
        v_end_wall = None
        if self.audio:
            self.audio.signal_stop()
        if self.vproc and self.vproc.poll() is None:
            try:
                self.vproc.stdin.write(b"q")
                self.vproc.stdin.flush()
                v_end_wall = time.time()   # capture halts ~here; flush adds no PTS
            except Exception:
                pass
        else:
            # Salvage path: the encoder died up to a poll earlier. The newest
            # segment's mtime is when video really ended - anchoring on 'now'
            # would shift the whole audio track early by the detection delay.
            try:
                segs = _list_segments(self.tmp)
                if segs:
                    v_end_wall = os.path.getmtime(segs[-1])
            except Exception:
                pass
        if self.audio:
            self.audio.finalize()
        if self.vproc and self.vproc.poll() is None:
            try:
                self.vproc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                # ffmpeg ignored the graceful 'q'; terminate, and if it STILL
                # hasn't exited shortly after, kill it so a stuck encoder can't
                # wedge the rest of the save.
                try:
                    self.vproc.terminate()
                    self.vproc.wait(timeout=8)
                except Exception:
                    try:
                        self.vproc.kill()
                    except Exception:
                        pass
        if v_end_wall is None:
            v_end_wall = time.time()  # last-resort anchor (no 'q' sent, no segments)
        total = len(_list_segments(self.tmp))
        nseg = max(0, total - self._run_vstart)
        sysw = (self.audio.system_wav if self.audio and self.audio.system_wav
                and os.path.isfile(self.audio.system_wav) else None)
        micw = (self.audio.mic_wav if self.audio and self.audio.mic_wav
                and os.path.isfile(self.audio.mic_wav) else None)
        if nseg > 0 or sysw or micw:
            self.runs.append({
                "sys": sysw, "mic": micw, "nseg": nseg,
                "v_end_wall": v_end_wall,
                "sys_t0": self.audio.first_sample_wallclock("system") if self.audio else None,
                "mic_t0": self.audio.first_sample_wallclock("mic") if self.audio else None,
            })
        self._seg_start = total
        self._run_index += 1
        self.vproc = None
        self.audio = None

    def _abort_run(self):
        """Tear down a run that produced NO usable video (e.g. gdigrab opened
        against a title that vanished before the first frame). Unlike
        _stop_run this records nothing: the stray audio is stopped and
        dropped - audio with no picture would only skew the sync anchors -
        and the WAV tag is retired so the next run opens fresh files instead
        of truncating ones a half-dead writer thread still holds."""
        if self.audio:
            try:
                self.audio.signal_stop()
                self.audio.finalize()
            except Exception:
                pass
        if self.vproc and self.vproc.poll() is None:
            try:
                self.vproc.stdin.write(b"q")
                self.vproc.stdin.flush()
            except Exception:
                pass
            try:
                self.vproc.wait(timeout=8)
            except Exception:
                try:
                    self.vproc.kill()
                except Exception:
                    pass
        self._seg_start = len(_list_segments(self.tmp))
        self._run_index += 1
        self.vproc = None
        self.audio = None

    def start(self):
        # Create the save folder here (not in __init__) so a permission/offline-drive
        # error is caught by _safe_start and shown to the user in plain language.
        os.makedirs(SETTINGS["output_dir"], exist_ok=True)
        os.makedirs(os.path.dirname(self.final), exist_ok=True)
        self.monitor_idx = _resolve_capture_monitor()
        # Experimental window-only scope: aim gdigrab at the game's own window
        # (manual desktop recordings and title-less windows use the screen).
        if (str(SETTINGS.get("capture_scope", "screen")) == "window"
                and self.game and self.game.lower() != "screen"):
            self.window_title = _game_window_title(self.game)
            if self.window_title:
                log(f"Window capture (experimental): '{self.window_title}'")
            else:
                log("Window capture: no window found; recording the screen.")
        log(f"Capturing screen #{self.monitor_idx + 1} (output {self.monitor_idx}).")
        log(f"Detected '{self.game}'. Recording -> {self.final}")
        self._start_run()

    def suspend(self):
        """Pause: stop the current run but keep all footage for Continue."""
        if self.suspended:
            return
        self._stop_run()
        self.suspended = True
        log("Recording paused (footage kept).")

    def resume(self):
        """Continue: start a new run that appends to the same recording."""
        if not self.suspended:
            return
        self.suspended = False
        self._start_run()
        log("Recording resumed.")

    # ---- finalise ---------------------------------------------------------
    def stop(self):
        log("Finalising...")
        if not self.suspended and (self.vproc or self.audio):
            self._stop_run()
        all_segs = _list_segments(self.tmp)
        if not all_segs:
            # None means "there was nothing to save" (e.g. Cancel during warm-up) -
            # callers must NOT show a scary "couldn't save your video" for this.
            log("No video captured; nothing saved.")
            self._cleanup()
            return None

        ok = False
        if len(self.runs) <= 1:
            # Common path: a single uninterrupted run. Concatenate the segments and
            # mux the audio in (see _assemble), writing straight to the final file.
            run = self.runs[0] if self.runs else {}
            ok = self._assemble(all_segs, run.get("sys"), run.get("mic"), self.final,
                                run)
        else:
            # Pauses happened: assemble each run on its own (so each stays in sync),
            # then concatenate the runs into one gap-free file.
            run_finals = []
            start = 0
            for k, run in enumerate(self.runs):
                cnt = run.get("nseg", 0)
                rsegs = all_segs[start:start + cnt]
                start += cnt
                if not rsegs:
                    continue
                rfin = os.path.join(self.tmp, f"_runf{k}.mp4")
                if self._assemble(rsegs, run["sys"], run["mic"], rfin, run):
                    run_finals.append(rfin)
            if len(run_finals) == 1:
                try:
                    os.replace(run_finals[0], self.final)
                    ok = True
                except Exception:
                    ok = False
            elif len(run_finals) > 1:
                tmp_final = self.final + ".__assembling__.mp4"
                if _concat_copy(SETTINGS["ffmpeg_path"], run_finals, tmp_final):
                    # _concat_copy salvages a bad join by DROPPING the last file and
                    # still returns True - which would silently lose the entire final
                    # run of a paused recording. Verify the stitched length first.
                    want = sum((_probe_duration(f) or 0) for f in run_finals)
                    got = _probe_duration(tmp_final) or 0
                    if want <= 0 or got >= want - max(1.0, want * 0.04):
                        try:
                            os.replace(tmp_final, self.final)
                            ok = True
                        except Exception:
                            ok = False
                    else:
                        log(f"Paused-recording stitch dropped footage "
                            f"({got:.0f}s of {want:.0f}s); keeping the raw runs.")
                if not ok:
                    try:                       # never leave a half-file beside the videos
                        if os.path.isfile(tmp_final):
                            os.remove(tmp_final)
                    except Exception:
                        pass

        if ok and os.path.isfile(self.final):
            log(f"Saved: {self.final}")
            _record_made_file(self.final)   # own it before the cap can consider it
            _queue_sdr_finish(self.final)   # HDR file? convert to SDR once idle
            enforce_storage_cap()
            self._cleanup()
            return True
        else:
            log("Merge failed; your raw files are kept in: " + self.tmp)
            return False

    def discard(self):
        """Stop capture and throw the whole recording away - no file saved."""
        log("Discarding current recording.")
        if self.audio:
            try:
                self.audio.signal_stop()
            except Exception:
                pass
        if self.vproc and self.vproc.poll() is None:
            try:
                self.vproc.terminate()
            except Exception:
                pass
            try:
                self.vproc.wait(timeout=10)
            except Exception:
                try:
                    self.vproc.kill()
                except Exception:
                    pass
        if self.audio:
            try:
                self.audio.finalize()
            except Exception:
                pass
        self._cleanup()

    def save_replay(self, seconds=None):
        """Grab roughly the last `seconds` of the live session and save it as a
        standalone clip in the Clips subfolder - the 'save last minute' feature.
        Saves whatever is buffered so far (so it works even seconds into a game).
        Returns the saved path, or None."""
        if seconds is None:
            seconds = SETTINGS.get("replay_seconds", 60)
        if not self._replay_lock.acquire(blocking=False):
            log("Replay: a save is already in progress.")
            return None
        try:
            segs = _list_segments(self.tmp)
            closed = segs[:-1] if len(segs) >= 1 else []   # newest is still open
            if not closed:
                log("Replay: nothing buffered yet - give it a few seconds.")
                return None
            seg = max(2, int(SETTINGS.get("segment_seconds", 4)))
            n = max(1, int(round(seconds / seg)) + 1)
            use = closed[-n:]                              # fewer => shorter clip, still saves
            stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            clip_video = os.path.join(self.tmp, f"clip_{stamp}.mp4")
            if not _concat_copy(SETTINGS["ffmpeg_path"], use, clip_video):
                log("Replay: failed to assemble clip video.")
                return None
            d = _probe_duration(clip_video) or float(seconds)
            sys_wav = mic_wav = None
            ends = {}
            seg = max(2, int(SETTINGS.get("segment_seconds", 4)))
            aud = self.audio          # snapshot: _stop_run nulls self.audio racily
            if aud:
                # Dump MORE audio than the clip needs (the ring runs ~a segment
                # past the video's end and we want spare head too): the anchor
                # below trims the head to the exact frame, and -t cuts the tail
                # at the video's length - aligned at BOTH ends, no guessing.
                sys_wav, mic_wav, ends = aud.dump_ring(self.tmp, d + 2 * seg,
                                                       trim_tail=0.0)
            clips_dir = _game_shelf(self.base, "clip")
            out_final = os.path.join(clips_dir, f"{self.base}_clip_{stamp}.mp4")
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            # WALL-CLOCK sync, same idea as full recordings: the last closed
            # segment's mtime IS the video's end moment (the segment muxer
            # finalises it right then), so video t0 = mtime - duration; each
            # wav's end moment comes from its ring. The old fixed 'trim half a
            # segment' guess was wrong by up to +-2s depending on how young the
            # open segment was - that's the 'clip sound is 1-2s early' bug.
            user_ms = int(SETTINGS.get("audio_offset_ms", 0))
            off_sys = off_mic = user_ms
            lo = -int((2 * seg + 6) * 1000)     # head-trim can legitimately be ~2 segments
            try:
                v_t0 = os.path.getmtime(use[-1]) - d
                def _off(wav, kind):
                    if not wav or kind not in ends:
                        return user_ms
                    adur = _probe_duration(wav)
                    if adur is None:
                        return user_ms
                    o = int(round((ends[kind] - adur - v_t0) * 1000)) + user_ms
                    return max(lo, min(8000, o))
                off_sys = _off(sys_wav, "system")
                off_mic = _off(mic_wav, "mic")
                if sys_wav or mic_wav:
                    log(f"Clip A/V sync: system {off_sys:+d} ms, mic {off_mic:+d} ms")
            except Exception:
                pass
            cmd = build_mux_cmd(clip_video, sys_wav, mic_wav, out_final,
                                off_sys, off_mic)
            cmd = cmd[:-1] + ["-t", f"{d:.3f}", cmd[-1]]   # end audio WITH the video
            try:
                # Bounded so a stuck encoder can't hold the replay lock (and wedge
                # cleanup/quit) indefinitely. A real clip muxes in a few seconds.
                r = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.PIPE, creationflags=flags, timeout=180)
            except subprocess.TimeoutExpired:
                log("Replay: clip mux timed out; skipping this clip.")
                return None
            for p in (clip_video, sys_wav, mic_wav):
                if p and os.path.isfile(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass
            if r.returncode == 0 and os.path.isfile(out_final):
                log(f"Clip saved ({d:.0f}s): {out_final}")
                _record_made_file(out_final)
                _queue_sdr_finish(out_final)   # converted after the game session
                enforce_storage_cap()          # clips count toward the cap too
                return out_final
            log("Replay: final mux failed.")
            err = (r.stderr or b"").decode("utf-8", "ignore").strip().splitlines()
            for line in err[-3:]:
                log("  ffmpeg: " + line)
            return None
        finally:
            self._replay_lock.release()

    def _assemble(self, segs, sys_wav, mic_wav, out, run=None):
        """Turn the captured segments + audio into one finished file. Two proven
        steps: (1) concatenate the segments with no re-encode into a single file -
        this is the codec-safe route that survives every encoder, including AMD's
        hardware AV1 (muxing straight from the segment list can fail to identify a
        hardware-AV1 stream); (2) mux that file with the audio, correcting each
        audio stream's start skew. Written to a temp name and renamed on success so
        the finished recording appears atomically. Returns True; never raises.

        SYNC: each stream's offset comes from WALL-CLOCK anchors - the moment its
        first sample was captured vs the moment the video's first frame was
        captured (video-end wallclock minus video duration). The old way guessed
        the skew from (video length - audio length), which silently included every
        second the loopback device spent idle (WASAPI sends nothing during
        silence) and over-delayed the whole track - the '4-6 seconds late' bug.
        The duration guess remains only as a fallback when anchors are missing."""
        if not segs:
            return False
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        # FAST PATH: mux STRAIGHT from the segment list (concat demuxer input).
        # The old route wrote a multi-GB '_merged.mp4' first and then copied all
        # of it AGAIN into the final - two full disk passes, which is most of
        # why a 10-minute recording took ~2 minutes to save on a hard drive.
        # If the direct route fails on some machine (ancient concat quirks),
        # the proven two-step below still runs - nothing is ever lost.
        list_path = os.path.join(self.tmp, "_final.list.txt")
        merged = None
        try:
            with open(list_path, "w", encoding="utf-8") as fh:
                for f in segs:
                    p = os.path.abspath(f).replace("\\", "/").replace("'", "'\\''")
                    fh.write(f"file '{p}'\n")
        except Exception:
            list_path = None
        video_src, src_is_concat = (list_path, True) if list_path else (None, False)
        if not list_path:
            merged = os.path.join(self.tmp, "_merged.mp4")
            try:
                if os.path.isfile(merged):
                    os.remove(merged)
            except Exception:
                pass
            if not _concat_copy(SETTINGS["ffmpeg_path"], segs, merged):
                return False
            video_src = merged
        # 2. Per-stream A/V offsets from wall-clock anchors.
        user_ms = int(SETTINGS.get("audio_offset_ms", 0))
        off_sys = off_mic = user_ms
        run = run or {}
        if sys_wav or mic_wav:
            # Video t0, wallclock. Preferred: the FIRST segment's own clock -
            # its mtime is the moment the muxer finalised it (= its last frame),
            # so mtime - duration = the first captured frame. One cheap probe,
            # exact per run, and it works without the merged intermediate
            # (ffprobe reports N/A for a concat list's total duration).
            v_t0 = None
            vdur = None
            try:
                d0 = _probe_duration(segs[0])
                if d0 is not None:
                    v_t0 = os.path.getmtime(segs[0]) - d0
            except Exception:
                v_t0 = None
            if v_t0 is None:
                # legacy anchor: video-end wallclock minus total duration
                vdur = _probe_duration(video_src) if not src_is_concat else None
                v_end = run.get("v_end_wall")
                if vdur is not None and v_end is not None:
                    v_t0 = v_end - vdur
            if v_t0 is not None and (run.get("sys_t0") or run.get("mic_t0")):
                if sys_wav and run.get("sys_t0"):
                    off_sys = int(round((run["sys_t0"] - v_t0) * 1000)) + user_ms
                if mic_wav and run.get("mic_t0"):
                    off_mic = int(round((run["mic_t0"] - v_t0) * 1000)) + user_ms
                # A LARGE positive offset is legitimate: a game silent through a
                # long splash/menu means the first loopback sample genuinely
                # arrives that late, and the audio belongs exactly there. Only
                # the negative side (trimming audio head) stays tightly bounded.
                segsec = max(2, int(SETTINGS.get("segment_seconds", 4)))
                hi = max(8000, int((vdur if vdur else len(segs) * segsec) * 1000))
                off_sys = max(-8000, min(hi, off_sys))
                off_mic = max(-8000, min(hi, off_mic))
                log(f"A/V sync: video t0 anchored; system {off_sys:+d} ms, "
                    f"mic {off_mic:+d} ms")
            else:
                # fallback: the legacy duration guess (anchors unavailable).
                # Needs the total video length - probe FIRST + LAST segment and
                # extrapolate the uniform middle. The old way probed EVERY
                # segment: a 30-minute session is ~450 ffprobe SPAWNS, minutes
                # of pure process churn before the mux even started.
                if vdur is None:
                    if src_is_concat:
                        try:
                            dfirst = _probe_duration(segs[0])
                            dlast = _probe_duration(segs[-1]) if len(segs) > 1 else 0
                            if dfirst is not None and dlast is not None:
                                vdur = dfirst * max(1, len(segs) - 1) + dlast
                        except Exception:
                            vdur = None
                    else:
                        vdur = _probe_duration(video_src)
                adur = _probe_duration(sys_wav or mic_wav)
                if vdur is not None and adur is not None:
                    off_sys = off_mic = max(-6000, min(6000,
                        int(round((vdur - adur) * 1000)) + user_ms))
                    log(f"A/V sync (fallback): video {vdur:.2f}s vs audio "
                        f"{adur:.2f}s -> {off_sys:+d} ms")
        # 3. Mux to a temp file, then rename so the final appears atomically.
        tmp_out = out + ".__assembling__.mp4"

        # the session's length for the progress card - cheap: first + last
        # segment, uniform middle extrapolated
        bind_total = 0.0
        try:
            d0 = _probe_duration(segs[0])
            dl = _probe_duration(segs[-1]) if len(segs) > 1 else 0
            if d0 is not None and dl is not None:
                bind_total = d0 * max(1, len(segs) - 1) + dl
        except Exception:
            pass
        _BINDING.update({"name": os.path.basename(out), "pct": None, "eta": None,
                         "mbps": None, "t0": time.time(), "total": bind_total})

        def _mux(src, is_concat):
            cmd = build_mux_cmd(src, sys_wav, mic_wav, tmp_out, off_sys, off_mic,
                                video_is_concat=is_concat)
            # live progress on stdout (out_time_us lines); stderr kept for errors
            cmd[1:1] = ["-progress", "pipe:1", "-nostats"]
            t_start = time.time()
            try:
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, creationflags=flags)
            except Exception as e:
                log(f"Mux failed to start ({e}); raw footage kept in the cache.")
                return False
            err_tail = []

            def _drain_err():
                try:
                    for ln in iter(p.stderr.readline, b""):
                        err_tail.append(ln)
                        if len(err_tail) > 8:
                            err_tail.pop(0)
                except Exception:
                    pass
            threading.Thread(target=_drain_err, daemon=True).start()
            last_size_t = t_start
            last_size = 0
            try:
                for ln in iter(p.stdout.readline, b""):
                    if time.time() - t_start > 1800:
                        p.kill()
                        log("Mux exceeded 30 minutes; killed. Raw footage kept in the cache.")
                        return False
                    s_ln = ln.decode("utf-8", "ignore").strip()
                    if s_ln.startswith("out_time_us=") or s_ln.startswith("out_time_ms="):
                        try:
                            done_s = int(s_ln.split("=")[1]) / 1e6
                            if bind_total > 1:
                                pct = max(0, min(99, int(done_s / bind_total * 100)))
                                if pct != _BINDING["pct"] and _TRAY_ICON[0] is not None:
                                    # the tray answers "how far along?" without opening the tome
                                    try:
                                        _TRAY_ICON[0].title = f"Lore - binding {pct}%"
                                    except Exception:
                                        pass
                                _BINDING["pct"] = pct
                                spent = time.time() - _BINDING["t0"]
                                if pct >= 3:
                                    _BINDING["eta"] = max(0, int(spent * (100 - pct) / pct))
                        except Exception:
                            pass
                        now = time.time()
                        if now - last_size_t >= 1.5:
                            try:
                                sz = os.path.getsize(tmp_out) if os.path.isfile(tmp_out) else 0
                                _BINDING["mbps"] = max(0.0, (sz - last_size) / 1e6
                                                       / max(0.2, now - last_size_t))
                                last_size, last_size_t = sz, now
                            except Exception:
                                pass
                p.wait(timeout=60)
            except Exception as e:
                try:
                    p.kill()
                except Exception:
                    pass
                log(f"Mux failed/stalled ({e}); raw footage kept in the cache.")
                return False
            good = (p.returncode == 0 and os.path.isfile(tmp_out)
                    and os.path.getsize(tmp_out) > 0)
            if good:
                # the honest ledger: every bind states its wall time and speed,
                # so a slow save is a MEASURED fact with a size attached
                try:
                    secs = max(0.1, time.time() - t_start)
                    gb = os.path.getsize(tmp_out) / 1e9
                    log(f"Bound {os.path.basename(out)}: {gb:.2f} GB in "
                        f"{secs:.0f}s ({gb * 1000 / secs:.0f} MB/s)")
                except Exception:
                    pass
            else:
                err = b"".join(err_tail).decode("utf-8", "ignore").strip().splitlines()
                for line in err[-4:]:
                    log("  ffmpeg: " + line)
            return good

        ok = _mux(video_src, src_is_concat)
        if not ok and src_is_concat:
            # Direct route rejected on this machine: fall back to the proven
            # two-step (write merged, then mux from it).
            log("Direct save failed; using the two-step route.")
            merged = os.path.join(self.tmp, "_merged.mp4")
            if _concat_copy(SETTINGS["ffmpeg_path"], segs, merged):
                ok = _mux(merged, False)
        for p in (list_path, merged):
            if p:
                try:
                    if os.path.isfile(p):
                        os.remove(p)
                except Exception:
                    pass
        if ok:
            # Atomic finalise. A transient handle - antivirus scanning the fresh
            # file, the search indexer - can make os.replace fail; retry before
            # giving up, and if it STILL won't budge never delete the finished
            # weld. Leave it as an orphaned '.__assembling__.mp4' so
            # _salvage_interrupted promotes it next boot. Losing a good recording
            # to a 200ms lock is the worst possible outcome.
            for _attempt in range(25):
                try:
                    os.replace(tmp_out, out)
                    return True
                except Exception as e:
                    if _attempt >= 24:
                        log(f"Could not finalise file: {e}; kept "
                            f"{os.path.basename(tmp_out)} for recovery on restart.")
                        return False
                    time.sleep(0.4)
        try:
            if os.path.isfile(tmp_out):
                os.remove(tmp_out)
        except Exception:
            pass
        return False

    def _cleanup(self):
        # Remove the whole temp folder (segments, wavs, concatenated video). Take
        # the replay lock first so we never delete the scratch dir out from under a
        # 'save last minute' clip that's still being assembled.
        got = False
        try:
            got = self._replay_lock.acquire(timeout=120)
        except Exception:
            got = False
        try:
            if got:
                shutil.rmtree(self.tmp, ignore_errors=True)
            else:
                # A 'save clip' is still using this scratch dir - don't delete it out
                # from under the clip. The next-launch orphan sweep clears it safely.
                log("Cleanup deferred: a clip is still saving; the next launch will sweep it.")
        except Exception:
            pass
        finally:
            if got:
                try:
                    self._replay_lock.release()
                except Exception:
                    pass


# ---------------------------------------------------------------------------
#  Watch loop
# ---------------------------------------------------------------------------
class _Ctl:
    """Shared control state between the tray UI and the watcher thread."""
    def __init__(self):
        self.quit = threading.Event()
        self.watching = threading.Event()
        self.watching.set()
        self.stop_now = threading.Event()     # "stop this recording but keep watching"
        self.force_record = threading.Event()  # manual "record now" (even with no game)
        self.lock = threading.Lock()
        self.session = None
        self.suppressed_game = None            # game we manually stopped; don't re-grab
        self.status = "starting"
        self.icon = None
        self.icon_idle = None
        self.icon_rec = None
        self.ui_enqueue = None     # set by the tray app: run a fn on the UI thread
        self.ui_root = None        # the hidden Tk root, parent for popups
        self.rec_t0 = None         # time the current recording started (live timer)
        self.wake = threading.Event()    # poke the watch loop to react to a click NOW
        self.muted_until = 0.0     # briefly silence the loop's sound after a click sound
        self.skip_loop_on = False  # consume-once: the click already played the start beep
        self.skip_loop_off = False # consume-once: the click already played the stop beep
        self.optimistic = None     # show this state instantly on click until reality catches up
        self.optimistic_t = 0.0
        self._dash_refresh = None  # dashboard registers a fn to repaint its state instantly
        self.saving = 0            # number of recordings finalising in the background

    def click_feedback(self, sound, optimistic, secs=4.0):
        """Instant feedback when the user presses a control: play the sound now,
        silence the loop's (delayed) duplicate, show the new state immediately, and
        poke the loop so the real action happens with minimal lag."""
        import time as _t
        try:
            _play_sound(sound)
        except Exception:
            pass
        # The loop's matching beep can land seconds later (after ffmpeg warms up),
        # so a short time-mute isn't enough - flag it to be skipped exactly once.
        if sound == "on":
            self.skip_loop_on = True
        elif sound == "off":
            self.skip_loop_off = True
        self.muted_until = _t.time() + 1.2
        self.optimistic = optimistic
        self.optimistic_t = _t.time() + secs
        self.wake.set()
        if self._dash_refresh:
            try:
                if self.ui_enqueue:
                    self.ui_enqueue(self._dash_refresh)
                else:
                    self._dash_refresh()
            except Exception:
                pass

    def eff_status(self):
        """Real status, except briefly overridden by an optimistic one right after a
        click so the UI feels instant. The live timer still uses rec_t0 (never faked)."""
        import time as _t
        opt = self.optimistic
        if opt:
            rec = ("recording", "paused", "starting")
            if _t.time() > self.optimistic_t or (self.status in rec) == (opt in rec):
                self.optimistic = None
            else:
                return opt
        return self.status

    def set_status(self, s):
        if s == self.status:
            return          # no change: skip the tray icon/menu churn every poll
        if s == "recording":
            if self.rec_t0 is None:
                import time as _t
                self.rec_t0 = _t.time()
        elif s in ("watching", "stopped", "idle", "saving"):
            self.rec_t0 = None     # paused keeps the clock; stop/idle/saving resets it
        self.status = s
        ic = self.icon
        if ic is not None:
            try:
                ic.title = f"Lore - {s}"
                img = self.icon_rec if (s == "recording" and self.icon_rec) else self.icon_idle
                if img is not None:
                    ic.icon = img
                ic.update_menu()
            except Exception:
                pass

    def notify(self, title, message, force=False):
        # Every action's notification is shown as Lore' own on-top popup, so it
        # is visible during a fullscreen game (Windows hides its own there).
        self.toast(title, message, force)

    def toast(self, title, sub, force=False):
        """Show Lore's own on-top popup. Unlike a Windows notification, this is
        visible over a fullscreen game (where Windows hides notifications via Focus
        Assist). Safe no-op when there's no UI thread (e.g. console mode).
        While a recording is WRITING, automatic mid-write chatter (clip
        saved, conversion ready, storage notes) is held by default (the
        quiet_popups setting) - a card sliding over the game mid-fight was
        exactly the wrong moment; the chimes still speak. LIFECYCLE moments
        pass `force=True` and ALWAYS show: recording started/stopped,
        paused/resumed - the user was explicit that "Now recording" must
        appear every time, tome open or not."""
        if not force and SETTINGS.get("quiet_popups", True) and self.status == "recording":
            log(f"(whisper held while writing) {title} - {sub}")
            return
        fn = self.ui_enqueue
        root = self.ui_root
        if fn is None or root is None:
            return
        try:
            fn(lambda: _show_toast(root, title, sub))
        except Exception:
            pass


def _tray_font(size):
    from PIL import ImageFont
    for name in ("segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "ariblk.ttf",
                 "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None


# ---------------------------------------------------------------------------
#  Sound effects (synthesized once to temp WAVs - reliable winsound playback)
# ---------------------------------------------------------------------------
_SOUND_RATE = 44100
_SOUND_FILES = {}


def _env_exp(n, attack_ms, decay_tau):
    """A smooth volume envelope: quick fade-in, then an exponential fade-out.
    Exponential decay (not linear) is what makes a tone sound 'real' not 'beep'."""
    import math
    a = max(1, int(_SOUND_RATE * attack_ms / 1000))
    out = []
    for i in range(n):
        if i < a:
            out.append(i / a)
        else:
            out.append(math.exp(-(i - a) / max(1.0, n * decay_tau)))
    return out


def _tone(freq, ms, harmonics=(1.0, 0.22, 0.07), detune_cents=5.0,
          attack_ms=4.0, decay_tau=0.30, vol=0.7):
    """A warm musical tone: the fundamental plus a couple of soft harmonics, with
    two very slightly detuned voices layered for warmth, and an exponential
    decay. Returns a list of floats (combined/normalised later)."""
    import math
    n = int(_SOUND_RATE * ms / 1000)
    env = _env_exp(n, attack_ms, decay_tau)
    det = 2 ** (detune_cents / 1200.0)        # a few cents sharp = chorus warmth
    hsum = sum(harmonics) or 1.0
    out = []
    for i in range(n):
        t = i / _SOUND_RATE
        s = 0.0
        for k, amp in enumerate(harmonics, start=1):
            s += amp * 0.5 * (math.sin(2 * math.pi * freq * k * t)
                              + math.sin(2 * math.pi * freq * k * det * t))
        out.append(s * vol * env[i] / hsum)
    return out


def _overlay(a, b, offset_ms=0, gain_b=1.0):
    """Lay sound b over sound a, starting offset_ms in (so notes can overlap and
    ring into each other instead of playing as separate beeps)."""
    off = int(_SOUND_RATE * offset_ms / 1000)
    out = list(a)
    if len(out) < off + len(b):
        out += [0.0] * (off + len(b) - len(out))
    for i, v in enumerate(b):
        out[off + i] += v * gain_b
    return out


def _to_i16(samples, peak=0.82):
    """Normalise a float buffer to a comfortable peak and convert to int16."""
    m = max(1e-6, max((abs(s) for s in samples), default=0.0))
    g = peak / m
    return [int(max(-1.0, min(1.0, s * g)) * 32767) for s in samples]


def _silence(ms):
    return [0.0] * int(_SOUND_RATE * ms / 1000)


def _shutter_burst(ms, tau, vol, low_mix=0.0, low_f=180):
    """A short filtered-noise transient with optional low 'body' resonance -
    the building block of a mechanical camera click. Returns floats."""
    import math
    import random
    n = int(_SOUND_RATE * ms / 1000)
    out = []
    prev = 0.0
    for i in range(n):
        env = math.exp(-i / max(1.0, n * tau))
        white = random.uniform(-1, 1)
        prev = prev * 0.55 + white * 0.45        # light low-pass: a "click" not a "tss"
        s = prev * vol * env
        if low_mix:
            s += math.sin(2 * math.pi * low_f * (i / _SOUND_RATE)) * vol * low_mix * env
        out.append(s)
    return out


def _sound_samples(kind):
    if kind == "on":
        # confident rising two-note (E6 -> B6, a perfect fifth), warm + overlapped
        a = _tone(1318.5, 150, decay_tau=0.30, vol=0.55)
        b = _tone(1975.5, 200, decay_tau=0.34, vol=0.72)
        return _to_i16(_overlay(a, b, offset_ms=62, gain_b=1.0))
    if kind == "off":
        # gentle falling two-note (G5 -> C5), softer and a touch longer
        a = _tone(784.0, 165, decay_tau=0.36, vol=0.50)
        b = _tone(523.3, 240, decay_tau=0.46, vol=0.62)
        return _to_i16(_overlay(a, b, offset_ms=74, gain_b=0.92))
    if kind == "shutter":
        # DSLR "k-chnk": crisp mirror-up snap, short gap, fuller shutter-close
        # with low body, plus a faint metallic ring on the tail.
        snap = _shutter_burst(7, 0.18, 1.0, low_mix=0.22, low_f=240)
        close = _shutter_burst(13, 0.26, 0.85, low_mix=0.48, low_f=160)
        ring = _tone(2300, 70, harmonics=(1.0, 0.0, 0.0), detune_cents=0,
                     attack_ms=1, decay_tau=0.10, vol=0.10)
        seq = snap + _silence(30) + close
        seq = _overlay(seq, ring, offset_ms=(len(snap) * 1000 // _SOUND_RATE) + 8)
        return _to_i16(seq)
    return []


_SFX_VER = "3"   # bump when a sound changes so stale cached files are rebuilt


def _sound_path(kind):
    """Render a sound to a temp WAV once per volume level; return its path."""
    vol = SETTINGS.get("sfx_volume", DEFAULTS["sfx_volume"])
    try:
        vol = max(0, min(100, int(vol)))
    except Exception:
        vol = DEFAULTS["sfx_volume"]
    key = f"{kind}:{vol}"
    p = _SOUND_FILES.get(key)
    if p and os.path.isfile(p):
        return p
    try:
        import wave as _wave
        import array
        import tempfile
        d = os.path.join(tempfile.gettempdir(), "lore_sfx")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, f"{kind}_v{_SFX_VER}_{vol}.wav")
        samples = _sound_samples(kind)
        if not samples:
            return None
        g = vol / 100.0
        samples = [int(s * g) for s in samples]
        w = _wave.open(p, "wb")
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(_SOUND_RATE)
        w.writeframes(array.array("h", samples).tobytes())
        w.close()
        _SOUND_FILES[key] = p
        return p
    except Exception as e:
        log(f"Sound build failed ({e})")
        return None


def _play_sound(kind):
    """Play a short effect (non-blocking). Windows only; silent elsewhere."""
    if os.name != "nt":
        return
    if int(SETTINGS.get("sfx_volume", DEFAULTS["sfx_volume"]) or 0) <= 0:
        return                                   # muted
    try:
        import winsound
    except Exception:
        return
    p = _sound_path(kind)
    if not p:
        return
    try:
        winsound.PlaySound(p, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception:
        pass


# ---------------------------------------------------------------------------
#  Autostart (login) shortcut - togglable from Settings
# ---------------------------------------------------------------------------
def _autostart_path():
    base = os.environ.get("APPDATA")
    if not base:
        return None
    return os.path.join(base, "Microsoft", "Windows", "Start Menu",
                        "Programs", "Startup", "Lore.lnk")


def _is_autostart_enabled():
    p = _autostart_path()
    return bool(p and os.path.isfile(p))


def _set_autostart(enabled):
    p = _autostart_path()
    if not p:
        return
    if enabled:
        if getattr(sys, "frozen", False):
            target = sys.executable          # the installed Lore.exe
            args = "--hidden"
            workdir = os.path.dirname(target)
        else:
            # Running from source: point at pythonw.exe + the script path. Targeting
            # the bare interpreter (as before) made the login shortcut launch Python
            # with no script, so Lore never started.
            exe_dir = os.path.dirname(sys.executable)
            pyw = os.path.join(exe_dir, "pythonw.exe")
            target = pyw if os.path.isfile(pyw) else sys.executable
            script = os.path.abspath(__file__)
            args = f'"{script}" --hidden'
            workdir = os.path.dirname(script)

        def _q(s):                           # escape ' for a PowerShell single-quoted literal
            return str(s).replace("'", "''")
        ps = ("$ws=New-Object -ComObject WScript.Shell;"
              f"$l=$ws.CreateShortcut('{_q(p)}');"
              f"$l.TargetPath='{_q(target)}';"
              f"$l.Arguments='{_q(args)}';"
              f"$l.WorkingDirectory='{_q(workdir)}';"
              "$l.Save()")
        try:
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           creationflags=flags, timeout=15)
        except Exception as e:
            log(f"Could not enable autostart: {e}")
    else:
        try:
            if os.path.isfile(p):
                os.remove(p)
        except Exception as e:
            log(f"Could not disable autostart: {e}")


# ---------------------------------------------------------------------------
#  Global hotkeys (Win32 RegisterHotKey - no dependency, no admin)
# ---------------------------------------------------------------------------
def _parse_hotkey(spec):
    """'ctrl+alt+f9' -> (modifiers, vk) for RegisterHotKey, or None."""
    if not spec:
        return None
    MODS = {"ctrl": 0x0002, "control": 0x0002, "alt": 0x0001, "shift": 0x0004,
            "win": 0x0008, "super": 0x0008, "cmd": 0x0008}
    SPECIAL = {"space": 0x20, "enter": 0x0D, "return": 0x0D, "esc": 0x1B,
               "escape": 0x1B, "tab": 0x09, "home": 0x24, "end": 0x23,
               "insert": 0x2D, "delete": 0x2E, "del": 0x2E, "pageup": 0x21,
               "pagedown": 0x22, "up": 0x26, "down": 0x28, "left": 0x25,
               "right": 0x27, "printscreen": 0x2C, "prtsc": 0x2C}
    mods, vk = 0, None
    for part in spec.lower().replace(" ", "").split("+"):
        if not part:
            continue
        if part in MODS:
            mods |= MODS[part]
        elif len(part) == 1 and part.isalnum():
            vk = ord(part.upper())
        elif part.startswith("f") and part[1:].isdigit() and 1 <= int(part[1:]) <= 24:
            vk = 0x6F + int(part[1:])        # F1 = 0x70
        elif part in SPECIAL:
            vk = SPECIAL[part]
        else:
            return None
    if vk is None:
        return None
    return (mods | 0x4000, vk)                # MOD_NOREPEAT


def _hotkey_listener(ctl, actions, stop_when=None):
    """actions: list of (spec, callable). Registers global hotkeys and runs a
    Win32 message loop in this thread, firing callables on press. stop_when
    (optional callable) makes the loop return early - the shell uses it to
    re-register combos the moment the user inscribes new ones."""
    if os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    registered = {}
    failed = []
    idn = 1
    for spec, fn in actions:
        parsed = _parse_hotkey(spec)
        if not parsed:
            if spec:
                log(f"Hotkey '{spec}' not understood; skipped.")
                failed.append(spec)
            continue
        mods, vk = parsed
        if user32.RegisterHotKey(None, idn, mods, vk):
            registered[idn] = (spec, fn)
            log(f"Hotkey registered: {spec}")
            idn += 1
        else:
            log(f"Hotkey '{spec}' couldn't be registered (already used by another app?).")
            failed.append(spec)
    # If a combo couldn't be claimed, tell the user once (after the window has had a
    # moment to come up) - so a conflict (e.g. AMD/NVIDIA overlay owning the key)
    # shows up clearly instead of looking like the hotkey is simply broken.
    if failed:
        def _warn_failed():
            time.sleep(2.5)
            try:
                ctl.notify("A hotkey is in use",
                           ", ".join(failed) + " couldn't be registered - another app may "
                           "own it. Pick a different combo in Settings \u203a Hotkeys.")
            except Exception:
                pass
        threading.Thread(target=_warn_failed, daemon=True).start()
    if not registered:
        return
    msg = wintypes.MSG()
    try:
        while not ctl.quit.is_set() and not (stop_when and stop_when()):
            if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):   # PM_REMOVE
                if msg.message == 0x0312:                              # WM_HOTKEY
                    entry = registered.get(msg.wParam)
                    if entry:
                        spec, fn = entry
                        log(f"Hotkey pressed: {spec}")
                        try:
                            fn()
                        except Exception as e:
                            log(f"Hotkey action error: {e}")
            else:
                time.sleep(0.03)
    finally:
        for hid in registered:
            try:
                user32.UnregisterHotKey(None, hid)
            except Exception:
                pass


def _discord_target_dims(iw, ih, v_kbps, fps=60.0):
    """Output size for the Discord copy: scale by AREA so the bitrate budget is
    actually enough per pixel (>= ~0.045 bits/px/frame - below that H.264 turns to
    mush). The old cap ('height <= 1080') let a 5120x1440 ultrawide through at
    3840x1080 = 4.1 Mpx on a ~3.7 Mbps budget = 0.015 bpp = the 'quality is so
    bad' complaint. Keeps aspect, never upscales, rounds to even."""
    try:
        iw, ih = int(iw), int(ih)
        if iw <= 0 or ih <= 0:
            return None
        budget_px = max(320 * 180, int(v_kbps * 1000 / (fps * 0.045)))
        max_px = min(budget_px, 1920 * 1080)          # never bigger than ~2 Mpx
        if iw * ih <= max_px:
            return None                               # small enough already
        s = (max_px / (iw * ih)) ** 0.5
        w = max(2, int(iw * s / 2) * 2)
        h = max(2, int(ih * s / 2) * 2)
        return (w, h)
    except Exception:
        return None


def _probe_dims(path):
    """(width, height) of the first video stream, or None."""
    try:
        d = os.path.dirname(SETTINGS["ffmpeg_path"])
        probe = os.path.join(d, "ffprobe.exe" if os.name == "nt" else "ffprobe") if d else "ffprobe"
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        r = subprocess.run([probe, "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=width,height", "-of", "csv=p=0", path],
                           capture_output=True, text=True, timeout=15, creationflags=flags)
        w, h = (r.stdout or "").strip().split(",")[:2]
        return int(w), int(h)
    except Exception:
        return None


def _compress_for_discord(clip_path, max_mb, length_s=0, quality_mbps=0):
    """Make a small, GOOD-looking copy of a clip for Discord. Optionally trims to
    the LAST `length_s` seconds, aims for `quality_mbps`, never exceeds `max_mb`.
    Quality levers (all offline - the game is long gone by now): the frame is
    scaled so the bitrate is sufficient PER PIXEL (area-based, ultrawide-aware),
    x264 runs on its 'medium' preset (near-slow quality, half the wait before
    the upload), and HDR sources get the measured-correct SDR conversion so
    embeds look right. Returns the temp file path, or None. Original is kept."""
    dur = _probe_duration(clip_path)
    if not dur or dur <= 0:
        return None
    import tempfile
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    out = os.path.join(tempfile.gettempdir(),
                       "lore_share_" + os.path.basename(clip_path))
    trim = []
    use_dur = dur
    if length_s and 0 < length_s < dur:
        trim = ["-ss", f"{max(0, dur - length_s):.3f}"]   # seek to the last N sec
        use_dur = length_s
    audio_kbps = 96
    # Video-bitrate budget that fits under max_mb (95% headroom for container + AAC).
    cap_kbps = int(max_mb * 1024 * 1024 * 8 * 0.95 / use_dur / 1000) - audio_kbps
    if cap_kbps < 200:
        # Even the minimum quality can't fit this length under the size limit. Say so
        # plainly rather than encode an over-size file and blame the webhook later.
        log(f"Discord: {use_dur:.0f}s can't fit under {max_mb} MB "
            f"(budget {cap_kbps} kbps). Lower the clip seconds or raise the limit.")
        return None
    want_kbps = int(quality_mbps * 1000) if quality_mbps else cap_kbps
    v_kbps = max(200, min(want_kbps, cap_kbps))
    # Area-based downscale sized to the budget (see _discord_target_dims).
    dims = _probe_dims(clip_path)
    tgt = _discord_target_dims(dims[0], dims[1], v_kbps) if dims else None
    vf = f"scale={tgt[0]}:{tgt[1]}" if tgt else "scale=-2:'min(1080,ih)'"
    # HDR recordings get the SAME measured-correct SDR conversion as the finishing
    # queue - a shared recipe, so the Discord copy can never look different from
    # the finished file (npl=100+hable here is what 'mega blew out' 1.21-1.23).
    trc = _probe_color_trc(clip_path)
    if _is_hdr_trc(trc):
        vf += "," + _hdr_to_sdr_vf(trc)

    def _encode(vbk):
        # preset medium: within ~5% of slow's quality at these bitrates, but the
        # upload starts about twice as soon after the hotkey ('clip is slightly
        # delayed' feedback - most of that wait was this encode).
        cmd = [SETTINGS["ffmpeg_path"], "-y", "-hide_banner", "-loglevel", "error",
               *trim, "-i", clip_path, "-vf", vf,
               "-c:v", "libx264", "-preset", "medium", "-b:v", f"{vbk}k",
               "-maxrate", f"{int(vbk * 1.35)}k", "-bufsize", f"{int(vbk * 2)}k",
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", f"{audio_kbps}k",
               "-movflags", "+faststart", out]
        try:
            rr = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                creationflags=flags, timeout=600)
        except subprocess.TimeoutExpired:
            log("Discord: compression timed out; upload skipped.")
            return None
        if rr.returncode != 0 or not os.path.isfile(out):
            err = (rr.stderr or b"").decode("utf-8", "ignore").strip().splitlines()
            for ln in err[-2:]:
                log("  ffmpeg(share): " + ln)
            return None
        return os.path.getsize(out) / (1024 * 1024)

    size_mb = _encode(v_kbps)
    if size_mb is None:
        return None
    # ABR can overshoot on short, high-motion clips. If the copy came out over the
    # limit, re-encode ONCE at a bitrate scaled to the achieved size; if it still
    # won't fit, give up honestly instead of uploading something Discord rejects.
    if size_mb > max_mb:
        v2 = max(150, int(v_kbps * (max_mb / size_mb) * 0.9))
        log(f"Discord copy {size_mb:.1f} MB > {max_mb} MB; retrying at {v2} kbps.")
        size_mb = _encode(v2)
        if size_mb is None or size_mb > max_mb:
            log("Discord: couldn't get the clip under the size limit.")
            try:
                if os.path.isfile(out):
                    os.remove(out)
            except Exception:
                pass
            return None
        v_kbps = v2
    log(f"Discord copy: {size_mb:.1f} MB, {use_dur:.0f}s at {v_kbps} kbps")
    return out


def _post_to_discord(file_path, content=""):
    """Upload a file to a Discord webhook (multipart). Returns True on success."""
    url = SETTINGS.get("discord_webhook", "").strip()
    if not url:
        return False
    # Only ever POST a clip to an actual Discord webhook address - guards against a
    # mistyped/pasted URL quietly sending your video somewhere else.
    try:
        from urllib.parse import urlparse
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        host = ""
    if not (host in ("discord.com", "discordapp.com")
            or host.endswith(".discord.com") or host.endswith(".discordapp.com")):
        log("Discord upload skipped: the webhook URL isn't a discord.com address.")
        return False
    import urllib.request
    import uuid
    import json
    boundary = "----records" + uuid.uuid4().hex
    crlf = b"\r\n"
    fname = os.path.basename(file_path)
    try:
        with open(file_path, "rb") as f:
            filedata = f.read()
    except Exception:
        return False
    buf = bytearray()
    payload = json.dumps({"content": content[:1900]} if content else {})
    buf += b"--" + boundary.encode() + crlf
    buf += b'Content-Disposition: form-data; name="payload_json"' + crlf
    buf += b"Content-Type: application/json" + crlf + crlf
    buf += payload.encode() + crlf
    buf += b"--" + boundary.encode() + crlf
    buf += ('Content-Disposition: form-data; name="files[0]"; filename="%s"' % fname).encode() + crlf
    buf += b"Content-Type: video/mp4" + crlf + crlf
    buf += filedata + crlf
    buf += b"--" + boundary.encode() + b"--" + crlf
    req = urllib.request.Request(url, data=bytes(buf), method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
    req.add_header("User-Agent", "Lore/1.0")
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return 200 <= resp.getcode() < 300
    except Exception as e:
        log(f"Discord upload failed: {e}")
        return False


def _maybe_post_discord(ctl, clip_path):
    """Compress the clip and post it to Discord (best-effort). Only the dedicated
    'Clip + post to Discord' hotkey calls this; the plain 'Save clip' hotkey never
    uploads."""
    if not SETTINGS.get("discord_webhook", "").strip():
        ctl.notify("Discord", "No webhook set - add one in Sharing settings.")
        return
    if not clip_path or not os.path.isfile(clip_path):
        return
    ctl.notify("Discord", "Posting clip...")
    small = _compress_for_discord(
        clip_path,
        int(SETTINGS.get("discord_max_mb", 9) or 9),
        length_s=int(SETTINGS.get("discord_clip_seconds", 0) or 0),
        quality_mbps=int(SETTINGS.get("discord_quality_mbps", 0) or 0),
    )
    if not small:
        ctl.notify("Discord", "Couldn't fit the clip under the size limit - "
                   "lower the seconds or raise the limit in Sharing.")
        return
    ok = _post_to_discord(small, content=f"\U0001F3AE New clip: {os.path.basename(clip_path)}")
    try:
        os.remove(small)
    except Exception:
        pass
    ctl.notify("Discord \u2713", "Clip posted." if ok else "Upload failed - check the webhook URL.")


def _trigger_replay(ctl, seconds=None, force_discord=False):
    _play_sound("shutter")
    with ctl.lock:
        sess = ctl.session
    if sess is None or getattr(sess, "suspended", False):
        log("Replay: no active recording right now.")
        ctl.notify("Lore", "Not recording right now - nothing to clip.")
        return
    secs = seconds or int(SETTINGS.get("clip_hotkey_seconds", SETTINGS.get("replay_seconds", 60)) or 60)
    ctl.notify("Clip", f"Saving the last ~{secs}s...")

    def work():
        # a clip binds on a worker thread too - wear the same honest card the
        # session bind wears (and make quit wait for it) unless a session bind
        # already owns the card and the counter
        fresh = getattr(ctl, "saving", 0) <= 0
        if fresh:
            with ctl.lock:
                ctl.saving += 1
            _BINDING.update({"name": f"last {secs}s clip", "pct": None,
                             "eta": None, "mbps": None,
                             "t0": time.time(), "total": 0.0})
        try:
            path = sess.save_replay(secs)
        finally:
            if fresh:
                with ctl.lock:
                    ctl.saving -= 1
        if path:
            ctl.notify("Clip captured \u2713", os.path.basename(path))
            # Only the dedicated "Clip + post to Discord" hotkey ever uploads; the
            # plain "Save clip" hotkey is always local-only.
            if force_discord:
                _maybe_post_discord(ctl, path)
        else:
            ctl.notify("Lore", "Couldn't save the clip - give it a few more seconds.")
    threading.Thread(target=work, daemon=True).start()


def _interruptible_sleep(ctl, secs):
    # Wakes early when the user clicks something (ctl.wake), so a button press is
    # acted on within milliseconds instead of waiting out the poll interval.
    end = time.time() + secs
    while time.time() < end:
        if ctl.quit.is_set():
            return
        if getattr(ctl, "wake", None) and ctl.wake.wait(timeout=min(0.25, max(0.0, end - time.time()))):
            ctl.wake.clear()
            return


def _loop_sound(ctl, kind):
    """Play a start/stop sound from the watch loop, unless a click already played it
    (the click's sound is the instant one the user hears). A click sets a consume-once
    flag because the loop's matching beep can land seconds later, after the warm-up."""
    if kind == "on" and getattr(ctl, "skip_loop_on", False):
        ctl.skip_loop_on = False
        return
    if kind == "off" and getattr(ctl, "skip_loop_off", False):
        ctl.skip_loop_off = False
        return
    if time.time() >= getattr(ctl, "muted_until", 0.0):
        _play_sound(kind)


def _finalize_async(ctl, session):
    """Save (concat + mux) a finished recording in the BACKGROUND so the watch loop
    and the UI never freeze while a long file is written - a 50-minute capture can
    take minutes to mux. Shows 'saving' while it runs and returns to 'watching' when
    every pending save is done and nothing new is recording."""
    if session is None:
        return
    with ctl.lock:
        ctl.saving += 1
    ctl.set_status("saving")

    def work():
        ok = False
        try:
            ok = session.stop()      # True saved / False merge failed / None nothing
        except Exception as e:
            log(f"Finalise failed: {e}")
            ok = False
        try:
            # Report the REAL outcome. The watcher only fires a present-tense
            # "Saving your video..." earlier, so the user is never told a recording
            # is safe when the merge actually failed and the footage is only in the
            # hidden cache. A cancelled warm-up (nothing captured) stays quiet.
            if ok:
                ctl.notify("Saved ✓", os.path.basename(getattr(session, "final", "") or ""))
            elif ok is False:
                ctl.notify("Couldn't save your video",
                           "Your raw footage was kept - see lore.log for the folder.")
        except Exception:
            pass
        with ctl.lock:
            ctl.saving -= 1
            idle = ctl.saving <= 0 and ctl.session is None
        if idle and ctl.status == "saving":
            ctl.set_status("watching")
        # the bind is over - never leave the tooltip frozen at 99%
        ic = ctl.icon
        if ic is not None:
            try:
                ic.title = f"Lore - {ctl.status}"
            except Exception:
                pass
    threading.Thread(target=work, daemon=True).start()


def _safe_start(session, ctl):
    """Start a recording, swallowing and logging any error. A single failed
    start must never escape the watch loop - that loop has no except clause, so
    one uncaught error there would silently kill ALL future recording until the
    app is restarted. Returns True if the recording actually started."""
    try:
        session.start()
        return True
    except Exception as e:
        import traceback
        log(f"Couldn't start recording: {e}")
        log(traceback.format_exc())
        # Tell the user in plain language WHY (throttled so a transient hiccup doesn't
        # spam toasts). FileNotFoundError = ffmpeg missing/blocked; OSError/Permission
        # from makedirs = the save folder is unwritable or the drive is gone.
        if isinstance(e, FileNotFoundError):
            msg = ("Lore can't find its video tool (ffmpeg) - your antivirus may "
                   "have removed it. Reinstalling Lore fixes this.")
        elif isinstance(e, OSError):
            msg = (f"Lore can't write to your save folder:\n"
                   f"{SETTINGS.get('output_dir', '')}\n"
                   "Pick another folder in Settings, or reconnect the drive.")
        else:
            msg = "Couldn't start the recording - see lore.log for details."
        if time.time() - _LAST_START_FAIL_TOAST[0] > 30:
            _LAST_START_FAIL_TOAST[0] = time.time()
            try:
                ctl.notify("Lore can't start recording", msg)
            except Exception:
                pass
        try:
            session.discard()
        except Exception:
            pass
        with ctl.lock:
            ctl.session = None
        ctl.set_status("watching")
        return False


def _watch_core(ctl):
    """Detection + record loop, driven by ctl events. Used by the tray app
    and by the legacy console mode."""
    load_settings()
    _ENC_SAFE[0] = bool(SETTINGS.get("safe_capture", False))
    _migrate_library_layout() # shelve any flat legacy recordings first
    _sweep_orphan_temp()      # clear scratch left by a crash/force-kill last time
    resolve_encoder()
    gb_hr = SETTINGS["bitrate_mbps"] / 8 * 3600 / 1024
    log(f"Watching ({SETTINGS['detection_mode']}). {SETTINGS['framerate']}fps "
        f"{SETTINGS['bitrate_mbps']}Mbps VBR (~{gb_hr:.0f} GB/hr max) "
        f"{SETTINGS['_encoder_resolved']}/{SETTINGS['amf_quality']}. "
        f"Output: {SETTINGS['output_dir']}")
    parts = []
    if SETTINGS["capture_system"]:
        parts.append("system (default device)")
    if SETTINGS["capture_mic"]:
        parts.append("mic" + (f" [{SETTINGS['mic_name_contains']}]"
                              if SETTINGS["mic_name_contains"] else ""))
    log("Audio: " + (" + ".join(parts) if parts else "none") +
        (f"  [{SETTINGS['audio_mode']}]" if len(parts) == 2 else ""))

    if not _ffmpeg_ok():
        log("ffmpeg health check failed: the video tool did not run.")
        ctl.notify("Lore can't find its video tool",
                   "ffmpeg is missing or was blocked by antivirus. Reinstall Lore.")

    session = None
    current = None
    manual = False          # True while this recording was started by hand
    enc_fails = 0           # consecutive encoder-died restarts (to stop looping)
    start_fails = 0         # consecutive start failures (spawn / output-folder errors)
    gone = 0                # consecutive polls the game looked closed (debounce)
    safe_persisted = False  # have we saved a discovered safe-capture mode yet
    try:
        while not ctl.quit.is_set():
          try:
            # STOP & SAVE: works whether actively recording or paused.
            if ctl.stop_now.is_set():
                ctl.stop_now.clear()
                ctl.force_record.clear()
                if session:
                    _loop_sound(ctl, "off")
                    ctl.notify("Recording stopped", "Saving your video...", force=True)
                    ctl.suppressed_game = current
                    with ctl.lock:
                        ctl.session = None
                    _finalize_async(ctl, session)   # save in the background; UI stays live
                    session = current = None
                    manual = False
                # Stopping always returns to watching - otherwise a stop pressed while
                # paused would leave the app paused (and not detecting the next game).
                ctl.watching.set()

            # PAUSE: suspend the current recording (keep footage); Continue resumes it.
            if not ctl.watching.is_set():
                if session and not session.suspended:
                    _loop_sound(ctl, "off")
                    ctl.notify("Paused", "Recording paused - footage kept.", force=True)
                    session.suspend()
                    ctl.set_status("paused")
                elif session and session.suspended:
                    ctl.set_status("paused")
                else:
                    # Nothing is recording - 'pause' has no meaning here, so don't show
                    # a misleading PAUSED state; just keep watching for the next game.
                    ctl.watching.set()
                _interruptible_sleep(ctl, 0.4)
                continue

            # Just un-paused with a suspended recording: continue it, or - if the
            # game closed while paused - finalise what we already captured.
            if session and session.suspended:
                game_gone = current is not None and current not in running_process_names()
                if not game_gone:
                    try:
                        session.resume()
                    except Exception as e:
                        # leave the dead-video state to the health check below
                        log(f"Couldn't resume recording: {e}")
                    _loop_sound(ctl, "on")
                    ctl.notify("Recording resumed", current or "Screen", force=True)
                    ctl.set_status("recording")
                else:
                    _loop_sound(ctl, "off")
                    ctl.notify("Saving your video…", current or "Screen", force=True)
                    ctl.force_record.clear()
                    with ctl.lock:
                        ctl.session = None
                    _finalize_async(ctl, session)
                    session = current = None
                    manual = False

            if session is None:
                if ctl.saving <= 0:
                    ctl.set_status("watching")   # but keep showing 'saving' while a save runs
                g = find_active_game()
                # Forget the suppression as soon as the game we manually stopped is no
                # longer the active full-screen app (you minimised it, alt-tabbed away,
                # or closed it) - so RE-maximising it starts a fresh recording. This is
                # far more reliable than waiting for the process to exit: media apps
                # like Stremio keep a background process alive, which used to leave
                # them suppressed forever and never recording again.
                if ctl.suppressed_game and ctl.suppressed_game != g:
                    ctl.suppressed_game = None
                auto = bool(g) and g != ctl.suppressed_game and not ctl.force_record.is_set()
                if not g and not ctl.force_record.is_set():
                    _sdr_finish_tick(ctl)      # truly idle: chip away at HDR->SDR queue
                if auto:
                    _sdr_finish_abort()        # game first - the GPU is theirs now
                    session = Session(g)
                    ctl.set_status("starting")     # honest "warming up" while ffmpeg spins up
                    if not _safe_start(session, ctl):
                        session = None
                        start_fails += 1
                        if start_fails >= 4:
                            # stop hammering one game that won't start (the user was
                            # already told why by _safe_start); re-arms if they alt-tab.
                            start_fails = 0
                            ctl.suppressed_game = g
                        _interruptible_sleep(ctl, 1.0)
                        continue
                    current = g
                    manual = False
                    start_fails = 0
                    with ctl.lock:
                        ctl.session = session
                    ctl.set_status("recording")
                    if enc_fails == 0:          # stay quiet while hunting an encoder
                        _loop_sound(ctl, "on")
                        if SETTINGS.get("notify_on_record", True):
                            # the user asked for this one ALWAYS: recording
                            # beginning is news, whatever else is happening
                            ctl.notify("Now recording", g, force=True)
                elif ctl.force_record.is_set():
                    # Manual record: capture the screen now. If a game is already
                    # fullscreen, attach to it; otherwise record the desktop and
                    # attach to the next game that goes fullscreen.
                    gg = detect_fullscreen_game()
                    name = gg or "Screen"
                    ctl.suppressed_game = None
                    _sdr_finish_abort()        # manual record also outranks conversions
                    session = Session(name)
                    ctl.set_status("starting")     # honest "warming up" while ffmpeg spins up
                    if not _safe_start(session, ctl):
                        session = None
                        start_fails += 1
                        if start_fails >= 4:
                            # manual record keeps failing; stop retrying so it doesn't
                            # churn ffmpeg forever (the user was told why by _safe_start).
                            start_fails = 0
                            ctl.force_record.clear()
                        _interruptible_sleep(ctl, 1.0)
                        continue
                    current = gg
                    manual = True
                    start_fails = 0
                    with ctl.lock:
                        ctl.session = session
                    ctl.set_status("recording")
                    if enc_fails == 0:
                        _loop_sound(ctl, "on")
                        if SETTINGS.get("notify_on_record", True):
                            # manual start = the user just pressed the sigil
                            ctl.notify("Now recording", name, force=True)
            elif session.suspended:
                pass   # paused; wait for Continue or Stop (handled above)
            else:
                # 'not session.vproc' matters: a failed RESUME leaves vproc=None with
                # suspended=False - that dead-video state must enter recovery too,
                # or audio records to nowhere until the user notices.
                if not session.vproc or session.vproc.poll() is not None:
                    # Window-capture death FIRST - and it owns EVERY death of
                    # a gdigrab run. The capture lives and dies with the
                    # game's HWND: quitting the game, toggling windowed <->
                    # borderless, or a resolution switch destroys the window
                    # and ffmpeg exits mid-run. None of that is the GPU
                    # encoder's fault, so none of it may reach the encoder
                    # ladder below (which would blacklist a healthy encoder
                    # and persist safe mode over a closed window).
                    if getattr(session, "window_title", None):
                        err = session.err_text()
                        for ln in err.splitlines()[-3:]:
                            if ln.strip():
                                log("  ffmpeg: " + ln.strip())
                        had_frames = (len(_list_segments(session.tmp))
                                      > getattr(session, "_run_vstart", 0))
                        if had_frames:
                            session._stop_run()    # keep the footage; anchors on last segment
                        else:
                            session._abort_run()   # nothing usable; drop the stray audio too
                        game_alive = (current is not None
                                      and current in running_process_names())
                        if not game_alive:
                            # The window died because the game closed - just
                            # the normal end of a session, saved as ever.
                            _loop_sound(ctl, "off")
                            ctl.force_record.clear()
                            with ctl.lock:
                                ctl.session = None
                            if _list_segments(session.tmp):
                                ctl.notify("Saving your video…",
                                           current or "Screen", force=True)
                                _finalize_async(ctl, session)
                            else:
                                session.discard()
                            session = current = None
                            manual = False
                            gone = 0
                        else:
                            # Game still running: its window was recreated
                            # (resolution/borderless switch) or renamed after
                            # loading. Re-aim ONCE at the fresh window; after
                            # that, the proven screen capture for good -
                            # footage over purity.
                            title = None
                            if not getattr(session, "_win_retry", False):
                                session._win_retry = True
                                title = _game_window_title(current)
                            if title:
                                session.window_title = title
                                log("Window capture: the window changed; "
                                    f"re-aiming at '{title}'.")
                            else:
                                session.window_title = None
                                log("Window capture ended; recording the "
                                    "whole screen for the rest of this session.")
                            try:
                                session._start_run()
                            except Exception as e:
                                log(f"Capture restart failed: {e}")
                        _interruptible_sleep(ctl, 0.5)
                        continue
                    # HDR-specific failure NEXT: if this run was handling HDR and
                    # produced no frames, that's the HDR path failing on this
                    # machine - NOT a bad encoder. Fall back to plain capture and
                    # re-record right away, so HDR can never leave you with no
                    # recording at all.
                    if (getattr(session, "_hdr_used", False) and _HDR_LEVEL[0] < 1
                            and len(_list_segments(session.tmp))
                                <= getattr(session, "_run_vstart", 0)):
                        err = session.err_text()
                        for ln in err.splitlines()[-4:]:
                            if ln.strip():
                                log("  ffmpeg: " + ln.strip())
                        # There is exactly ONE HDR path now (float16 zero-copy on
                        # AMF); if it can't produce frames on this driver, plain
                        # capture is the only alternative - no half-steps to try.
                        _HDR_LEVEL[0] = 1
                        log("HDR capture produced no frames here; recording "
                            "continues with plain capture.")
                        ctl.notify("Lore", "HDR isn't working on this PC - "
                                   "recording without it.")
                        # A multi-run session (pause/resume) may hold GOOD segments
                        # from earlier runs - salvage them; only a truly empty
                        # session is discarded. (Unconditional discard here deleted
                        # pre-pause footage when a resumed HDR run died at start.)
                        if _list_segments(session.tmp):
                            with ctl.lock:
                                ctl.session = None
                            _finalize_async(ctl, session)
                        else:
                            session.discard()
                            with ctl.lock:
                                ctl.session = None
                        session = None
                        # Not an encoder fault - don't count it; retry next poll.
                        if ctl.saving <= 0:
                            ctl.set_status("watching")
                        _interruptible_sleep(ctl, 0.3)
                        continue
                    # Disk full? A full output drive kills ffmpeg exactly like a bad
                    # encoder does - check before blaming (and needlessly blacklisting)
                    # the GPU, and tell the user the real, fixable cause.
                    try:
                        free = shutil.disk_usage(SETTINGS["output_dir"]).free
                    except Exception:
                        free = None
                    if free is not None and free < (1 << 30):     # under ~1 GB
                        log(f"Output drive nearly full ({free / 1e9:.1f} GB free); stopping.")
                        ctl.notify("Your drive is almost full",
                                   "Recording stopped - free up space to record again.")
                        if len(_list_segments(session.tmp)) >= 2:
                            with ctl.lock:
                                ctl.session = None
                            _finalize_async(ctl, session)         # salvage what exists
                        else:
                            session.discard()
                            with ctl.lock:
                                ctl.session = None
                        ctl.suppressed_game = current             # don't re-record into a full disk
                        ctl.force_record.clear()
                        session = current = None
                        manual = False
                        if ctl.saving <= 0:
                            ctl.set_status("watching")
                        _interruptible_sleep(ctl, 1.0)
                        continue
                    # The encoder died mid-capture. Log WHY, then recover: first
                    # retry the SAME encoder on the most-compatible path ('safe'
                    # mode); if that also fails, blacklist it and try the next.
                    err = session.err_text()
                    dead = SETTINGS.get("_encoder_resolved")
                    for ln in err.splitlines()[-4:]:
                        if ln.strip():
                            log("  ffmpeg: " + ln.strip())
                    if not _ENC_SAFE[0]:
                        _ENC_SAFE[0] = True
                        log(f"Encoder '{dead}' exited early; retrying in compatible mode.")
                    else:
                        if dead:
                            _BAD_ENCODERS.add(dead)
                        SETTINGS["_encoder_resolved"] = None
                        _ENC_SAFE[0] = False
                        log(f"Encoder '{dead}' still failed; switching to another encoder.")
                    # If essentially nothing was captured (encoder died at start),
                    # throw it away rather than leaving a broken stub + temp folder.
                    # If it ran long enough to have real footage, salvage it.
                    if len(_list_segments(session.tmp)) >= 2:
                        with ctl.lock:
                            ctl.session = None
                        _finalize_async(ctl, session)   # salvage in background
                    else:
                        session.discard()     # nothing worth keeping; cleans up temp
                        with ctl.lock:
                            ctl.session = None
                    keep_game = current
                    session = None
                    enc_fails += 1
                    if enc_fails >= 8:
                        log("Several encoders failed here; pausing auto-record for this game.")
                        ctl.notify("Lore", "Couldn't find a working video encoder - check the log.")
                        ctl.suppressed_game = keep_game
                        ctl.force_record.clear()   # also stop manual retries
                        current = None
                        manual = False
                        enc_fails = 0
                    if ctl.saving <= 0:
                        ctl.set_status("watching")
                    # leave force_record/current so it re-records the same game next poll
                elif manual and current is None:
                    # Pure desktop recording - attach to a game if one appears,
                    # but never stop just because no game is running.
                    gone = 0
                    gg = detect_fullscreen_game()
                    if gg:
                        current = gg
                        log(f"Attached recording to '{gg}'.")
                elif current is not None and current not in running_process_names():
                    # Debounce: a single missed poll (alt-tab, brief hitch) shouldn't
                    # end the recording - only stop once the game is really gone.
                    gone += 1
                    if gone >= 2:
                        gone = 0
                        enc_fails = 0
                        _loop_sound(ctl, "off")
                        # the game just closed - nothing left for a card to cover
                        ctl.notify("Saving your video…", current or "Screen", force=True)
                        ctl.force_record.clear()
                        with ctl.lock:
                            ctl.session = None
                        _finalize_async(ctl, session)
                        session = current = None
                        manual = False
                else:
                    gone = 0
                    enc_fails = 0   # healthy: encoder alive and the game is running
                    if _ENC_SAFE[0] and not safe_persisted and not SETTINGS.get("safe_capture"):
                        # compatible mode was auto-discovered and is working - remember
                        # it so future launches skip the failed fast-path attempt.
                        _persist_setting("safe_capture", True)
                        safe_persisted = True
                        log("Saved compatibility capture mode for next time.")
            _interruptible_sleep(ctl, SETTINGS["poll_interval"])
          except Exception as _loop_err:
            # A single unexpected error (a transient Windows/psutil hiccup, etc.)
            # must NEVER kill the watcher - otherwise the tray icon stays but
            # nothing records for the rest of the session. Log it and keep going.
            log(f"Watcher hit an unexpected error; recovering: {_loop_err}")
            _interruptible_sleep(ctl, 1.0)
    finally:
        _sdr_finish_abort()       # never leave an orphan converter running after quit
        if session:
            session.stop()        # finish the active recording (synchronous on quit)
        with ctl.lock:
            ctl.session = None
        # Wait for any background saves still finalising so quitting never drops one.
        deadline = time.time() + 590
        while ctl.saving > 0 and time.time() < deadline:
            time.sleep(0.2)
        ctl.set_status("stopped")
        log("Recorder stopped.")


def _release_lock():
    # Only delete the lock file if it still holds OUR pid, so a quitting instance can
    # never clobber a lock that another running instance legitimately owns. A garbled
    # or other-pid lock is left alone (a genuinely stale one is reclaimed on the next
    # launch by _watcher_running_pid). Flag files are transient IPC, always cleared.
    try:
        with open(_lock_path()) as fh:
            ours = fh.read().strip() == str(os.getpid())
    except Exception:
        ours = False
    if ours:
        try:
            os.remove(_lock_path())
        except Exception:
            pass
    try:
        os.remove(_show_flag_path())
    except Exception:
        pass


def _claim_lock():
    """Return True if we became the single running instance."""
    other = _watcher_running_pid()
    if other:
        log(f"Lore is already running (PID {other}). Closing this one.")
        return False
    try:
        with open(_lock_path(), "w") as fh:
            fh.write(str(os.getpid()))
    except Exception:
        pass
    try:
        if os.path.exists(_show_flag_path()):
            os.remove(_show_flag_path())
    except Exception:
        pass
    return True


def watch_loop():
    """Legacy console watcher (no tray icon). Ctrl+C to quit."""
    if not _hold_singleton_mutex() or not _claim_lock():
        return
    log("Idle. Launch a game to start. Ctrl+C to quit.")
    ctl = _Ctl()
    t = threading.Thread(target=_watch_core, args=(ctl,), daemon=True)
    t.start()
    try:
        while t.is_alive():
            t.join(0.3)
    except KeyboardInterrupt:
        ctl.quit.set()
        t.join()
    finally:
        _release_lock()


# ---------------------------------------------------------------------------
#  Test mode
# ---------------------------------------------------------------------------
def test_clip(seconds):
    load_settings()
    resolve_encoder()
    log(f"Test recording for {seconds}s (play some audio + talk into your mic)...")
    s = Session("Test.exe")
    s.start()
    time.sleep(seconds)
    s.stop()


def hdr_probe():
    """Diagnose HDR capture on THIS machine: is Windows HDR on, what is the SDR
    white level, does the float16 zero-copy HDR path produce frames with this
    GPU/driver, and does the offline SDR conversion chain run."""
    load_settings()
    ff = SETTINGS["ffmpeg_path"]
    mon = _resolve_capture_monitor()
    fps = int(SETTINGS.get("framerate", 60))
    print("\n=== Lore HDR diagnostic ===")
    print(f"ffmpeg: {ff}")
    print(f"Windows HDR currently ON: {_hdr_active()}")
    print(f"Windows SDR white level: {_sdr_white_nits() or '(query failed)'} nits")
    enc = resolve_encoder()
    print(f"Encoder: {enc}")
    mons = _enumerate_active_monitors()
    mons.sort(key=lambda m: m["num"])
    print(f"Active monitors: {len(mons)}")
    for rank, m in enumerate(mons):
        w = m["rect"][2] - m["rect"][0]
        h = m["rect"][3] - m["rect"][1]
        tag = " (primary)" if m["primary"] else ""
        print(f"  capture index {rank}: DISPLAY{m['num']} {w}x{h}{tag}")
    print(f"Capturing screen index {mon} (Screen {mon + 1}).")
    if os.name != "nt":
        print("\n(Not on Windows - ddagrab capture can't be tested here.)")
        return

    flags = subprocess.CREATE_NO_WINDOW
    import tempfile
    grab = f"ddagrab=output_idx={mon}:framerate={fps}"

    if not (enc.endswith("_amf") and _enc_supports_10bit(enc)):
        print("\nThis encoder can't take the float16 HDR surface (AMD/AMF only) - "
              "on an HDR desktop Lore records plain capture here.")
        return

    print("\n[1] Float16 zero-copy HDR capture (~1s):")
    out = os.path.join(tempfile.gettempdir(), "lore_hdr_probe.mp4")
    vf, enc_args, pre = _hdr_native_args(grab, enc)
    n = 0
    try:
        r = subprocess.run([ff, "-y", "-hide_banner", "-loglevel", "error", *pre,
                            "-filter_complex", vf, "-map", "[v]", "-t", "1",
                            "-c:v", enc, "-b:v", "10M", *enc_args, out],
                           capture_output=True, text=True, timeout=40,
                           creationflags=flags)
        d = os.path.dirname(ff)
        probe = os.path.join(d, "ffprobe.exe") if d else "ffprobe"
        pr = subprocess.run([probe, "-v", "error", "-count_frames",
                             "-select_streams", "v:0", "-show_entries",
                             "stream=nb_read_frames", "-of",
                             "default=nw=1:nokey=1", out],
                            capture_output=True, text=True, creationflags=flags)
        n = int((pr.stdout or "0").strip() or "0")
        if n <= 0:
            for ln in (r.stderr or "").strip().splitlines()[-3:]:
                print("   ffmpeg: " + ln)
    except Exception as e:
        print(f"   probe failed: {e}")
    print(f"   frames produced: {n}" + ("  <- HDR capture works" if n > 0 else
                                        "  <- would fall back to plain capture"))

    if n > 0:
        print("\n[2] Offline SDR conversion of that file:")
        out2 = os.path.join(tempfile.gettempdir(), "lore_hdr_probe_sdr.mp4")
        vf2 = _hdr_to_sdr_vf(_probe_color_trc(out)) + ",format=nv12"
        try:
            r = subprocess.run([ff, "-y", "-hide_banner", "-loglevel", "error",
                                "-i", out, "-vf", vf2, "-c:v", "libx264",
                                "-preset", "ultrafast", out2],
                               capture_output=True, text=True, timeout=60,
                               creationflags=flags)
            okc = r.returncode == 0 and os.path.isfile(out2) and os.path.getsize(out2)
            print("   conversion: " + ("OK" if okc else "FAILED"))
            if not okc:
                for ln in (r.stderr or "").strip().splitlines()[-3:]:
                    print("   ffmpeg: " + ln)
        except Exception as e:
            print(f"   conversion failed: {e}")
        try:
            os.remove(out2)
        except Exception:
            pass
    try:
        os.remove(out)
    except Exception:
        pass


# ---------------------------------------------------------------------------
#  LORE - the tome
# ===========================================================================
#  Everything below is the shell the machinery above lives inside: a frameless
#  WebView2 window holding one hand-crafted HTML tome (ui.html), the over-game
#  popups (PIL-rendered, visible over fullscreen games), the tray presence and
#  the JS<->Python bridge. The recorder itself neither knows nor cares that the
#  buttons are now made of wax and parchment - it sees the same ctl calls the
#  old shell made.
# ===========================================================================

# The tome's small fixed palette for the PIL-rendered pieces (tray icon, over-
# game popup card). Physical light is candle-gold; magic is arcane cyan.
LORE_INK = "#120D08"          # deep warm ink (card ground)
LORE_INK_EDGE = "#3B2F1D"     # hairline around the card
LORE_TILE = "#1D1610"         # the seal's parchment tile
LORE_GOLD = "#E8B563"         # candle-gold (accent bar, ring, countdown)
LORE_GOLD_HI = "#F6D398"      # bright gold
LORE_EMBER = "#E4552F"        # recording ember
LORE_ARCANE = "#7FD6E8"       # arcane cyan (magic touches only)
LORE_IVORY = "#F1E6CF"        # title ink
LORE_FADED = "#A8946E"        # sub ink


def _hex_rgba(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def _hex_rgb(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _vgrad(w, h, top_hex, bot_hex):
    """A vertical gradient image, w x h, from top colour to bottom colour."""
    from PIL import Image
    t = _hex_rgb(top_hex)
    b = _hex_rgb(bot_hex)
    col = Image.new("RGB", (1, max(1, h)))
    px = col.load()
    H = max(1, h - 1)
    for y in range(h):
        f = y / H
        px[0, y] = (int(t[0] + (b[0] - t[0]) * f),
                    int(t[1] + (b[1] - t[1]) * f),
                    int(t[2] + (b[2] - t[2]) * f))
    return col.resize((max(1, w), max(1, h)))


# ---------------------------------------------------------------------------
#  The mark - an ornate leather grimoire with gold hardware and a serif "L".
#  Used for the tray icon (with a red ember when recording), the popup seal,
#  and it matches lore.ico so every face of LORE wears one identity. No halo,
#  no rune ring - he called those "a glowing round thing" and "a symbol that
#  doesnt make sense", and he was right. Drawn 4x and downsized so it stays
#  crisp at 16px in the tray; tiny sizes drop the fiddly hardware.
# ---------------------------------------------------------------------------
def _mark_serif_font(px):
    """A bookish serif for the cover monogram - Georgia/Garamond/Times all
    ship with Windows, so one of these always lands."""
    from PIL import ImageFont
    for name in ("garabd.ttf", "gara.ttf", "georgiab.ttf", "georgia.ttf",
                 "timesbd.ttf", "times.ttf"):
        try:
            return ImageFont.truetype("C:/Windows/Fonts/" + name, px)
        except Exception:
            continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def _mark_gold(w, h):
    """Gold with a bright band near the top, so the hardware reads as
    polished metal instead of flat paint."""
    from PIL import Image
    hi = _hex_rgb(LORE_GOLD_HI)
    mid = _hex_rgb(LORE_GOLD)
    lo = (156, 112, 48)
    col = Image.new("RGB", (1, max(1, h)))
    px = col.load()
    H = max(1, h - 1)
    for y in range(h):
        f = y / H
        if f < 0.28:
            g = f / 0.28
            c = tuple(int(hi[i] + (mid[i] - hi[i]) * g) for i in range(3))
        else:
            g = (f - 0.28) / 0.72
            c = tuple(int(mid[i] + (lo[i] - mid[i]) * g * 0.8) for i in range(3))
        px[0, y] = c
    return col.resize((max(1, w), max(1, h)))


def _tome_mark(P, recording=False):
    from PIL import Image, ImageDraw, ImageFilter
    detail_full = P >= 32          # the tray's 16-24px drops the fiddly bits
    S = P * 4
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    LEATHER_T = (109, 66, 34)
    LEATHER_B = (44, 24, 12)
    SPINE_D = (35, 20, 10)
    PAGES = (235, 219, 185)
    PAGES_D = (196, 176, 138)
    GOLD_LO = (156, 112, 48)

    # geometry: cover slab, spine at left, page block peeking out at right
    x0, y0, x1, y1 = S * 0.10, S * 0.06, S * 0.90, S * 0.94
    rad = S * 0.055
    d = ImageDraw.Draw(img)

    # page block first, so the cover overlaps it
    pb_x0 = x1 - S * 0.050
    d.rounded_rectangle([pb_x0, y0 + S * 0.030, x1 + S * 0.012, y1 - S * 0.012],
                        radius=rad * 0.4, fill=PAGES)
    if detail_full:
        for i in range(3):
            lx = pb_x0 + S * (0.014 + i * 0.014)
            d.line([lx, y0 + S * 0.045, lx, y1 - S * 0.028], fill=PAGES_D,
                   width=max(2, S // 400))

    # leather: a vertical gradient through the cover mask + a soft top sheen
    cover_x1 = x1 - S * 0.028
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([x0, y0, cover_x1, y1], radius=rad, fill=255)
    leather = _vgrad(S, S, "#6D4222", "#2C180C")
    sheen = Image.new("L", (S, S), 0)
    ImageDraw.Draw(sheen).ellipse([x0 - S * 0.1, y0 - S * 0.28,
                                   cover_x1 + S * 0.1, y0 + S * 0.42], fill=46)
    sheen = sheen.filter(ImageFilter.GaussianBlur(S * 0.05))
    leather = Image.composite(Image.new("RGB", (S, S), (150, 96, 52)), leather, sheen)
    if detail_full:   # grain, so the cover doesn't read flat
        noise = Image.effect_noise((S, S), 22).convert("L")
        leather = Image.composite(leather.point(lambda v: min(255, v + 12)), leather,
                                  noise.point(lambda v: 24 if v > 128 else 0))
    img.paste(leather, (0, 0), mask)

    # depth: a soft inner vignette + a crisp dark edge
    vg = Image.new("L", (S, S), 0)
    ImageDraw.Draw(vg).rounded_rectangle([x0, y0, cover_x1, y1], radius=rad,
                                         outline=255, width=int(S * 0.045))
    vg = vg.filter(ImageFilter.GaussianBlur(S * 0.02))
    dark_v = Image.new("RGBA", (S, S), (14, 8, 4, 255))
    img.paste(dark_v, (0, 0),
              Image.composite(vg, Image.new("L", (S, S), 0), mask).point(lambda v: v * 55 // 100))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x0, y0, cover_x1, y1], radius=rad,
                        outline=(22, 12, 6, 255), width=max(3, int(S * 0.008)))

    # spine: darker band with two gold hinge straps
    sp_w = S * 0.085
    sp = Image.new("L", (S, S), 0)
    ImageDraw.Draw(sp).rounded_rectangle([x0, y0, x0 + sp_w * 2, y1], radius=rad, fill=255)
    ImageDraw.Draw(sp).rectangle([x0 + sp_w, y0, S, S], fill=0)
    img.paste(Image.new("RGBA", (S, S), SPINE_D + (255,)), (0, 0),
              Image.eval(sp, lambda v: v * 60 // 100))
    if detail_full:
        for fy in (0.16, 0.84):
            yy = y0 + (y1 - y0) * fy
            d.rectangle([x0 + S * 0.008, yy - S * 0.010, x0 + sp_w, yy + S * 0.010],
                        fill=GOLD_LO + (220,))
            d.rectangle([x0 + S * 0.008, yy - S * 0.010, x0 + sp_w, yy - S * 0.002],
                        fill=_hex_rgb(LORE_GOLD) + (235,))

    # the gold rim inset - the same signature as the app's cover
    rim_in = S * 0.052
    gx0, gy0 = x0 + sp_w + S * 0.020, y0 + rim_in
    gx1, gy1 = cover_x1 - rim_in, y1 - rim_in
    gold_layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gm = Image.new("L", (S, S), 0)
    gd = ImageDraw.Draw(gm)
    w_out = max(3, int(S * (0.012 if detail_full else 0.020)))
    gd.rounded_rectangle([gx0, gy0, gx1, gy1], radius=rad * 0.6, outline=255, width=w_out)
    if detail_full:
        pad = S * 0.020
        gd.rounded_rectangle([gx0 + pad, gy0 + pad, gx1 - pad, gy1 - pad],
                             radius=rad * 0.5, outline=255, width=max(2, int(S * 0.005)))
    gold_layer.paste(_mark_gold(S, S).convert("RGBA"), (0, 0), gm)
    img.alpha_composite(gold_layer)

    if detail_full:
        # gold corner caps with a rivet each - proper grimoire hardware
        cap = S * 0.104
        cap_layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        cm = Image.new("L", (S, S), 0)
        cd = ImageDraw.Draw(cm)
        corners = [(gx0, gy0, 1, 1), (gx1, gy0, -1, 1), (gx0, gy1, 1, -1), (gx1, gy1, -1, -1)]
        for cx, cy, sx, sy in corners:
            cd.polygon([(cx - sx * S * 0.012, cy - sy * S * 0.012),
                        (cx + sx * cap, cy - sy * S * 0.012),
                        (cx - sx * S * 0.012, cy + sy * cap)], fill=255)
        cap_layer.paste(_mark_gold(S, S).convert("RGBA"), (0, 0), cm)
        img.alpha_composite(cap_layer)
        d = ImageDraw.Draw(img)
        for cx, cy, sx, sy in corners:
            d.line([(cx + sx * cap, cy - sy * S * 0.012),
                    (cx - sx * S * 0.012, cy + sy * cap)],
                   fill=GOLD_LO + (255,), width=max(2, int(S * 0.005)))
            rv = S * 0.011
            rvx, rvy = cx + sx * cap * 0.30, cy + sy * cap * 0.30
            d.ellipse([rvx - rv, rvy - rv, rvx + rv, rvy + rv], fill=GOLD_LO + (255,))

        # the clasp: a gold strap from the page edge onto the cover
        cy = (y0 + y1) / 2
        strap_w, strap_h = S * 0.070, S * 0.058
        sxx = cover_x1 - strap_w * 0.62
        clm = Image.new("L", (S, S), 0)
        ImageDraw.Draw(clm).rounded_rectangle(
            [sxx, cy - strap_h / 2, x1 + S * 0.012, cy + strap_h / 2],
            radius=strap_h * 0.32, fill=255)
        clasp_layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        clasp_layer.paste(_mark_gold(S, S).convert("RGBA"), (0, 0), clm)
        img.alpha_composite(clasp_layer)
        d.rounded_rectangle([sxx, cy - strap_h / 2, x1 + S * 0.012, cy + strap_h / 2],
                            radius=strap_h * 0.32, outline=GOLD_LO + (255,),
                            width=max(2, int(S * 0.005)))
        pv = S * 0.012
        d.ellipse([sxx + strap_w * 0.30 - pv, cy - pv,
                   sxx + strap_w * 0.30 + pv, cy + pv], fill=(60, 36, 16, 255))

    # the monogram: a bookish gold "L", bevelled with a dark drop
    ccx, ccy = (gx0 + gx1) / 2, (gy0 + gy1) / 2
    font = _mark_serif_font(int(S * (0.38 if detail_full else 0.48)))
    if font is not None:
        bb = d.textbbox((0, 0), "L", font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        tx, ty = ccx - tw / 2 - bb[0], ccy - th / 2 - bb[1]
        lm = Image.new("L", (S, S), 0)
        ImageDraw.Draw(lm).text((tx, ty), "L", font=font, fill=255)
        img.paste(Image.new("RGBA", (S, S), (24, 13, 6, 235)),
                  (int(S * 0.006), int(S * 0.008)), lm)
        gl = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        gl.paste(_mark_gold(S, S).convert("RGBA"), (0, 0), lm)
        img.alpha_composite(gl)

    if recording:
        # the ember: a wax-seal red dot in the corner, unmissable at 16px
        rr = S * 0.105
        ex, ey = S - rr - S * 0.015, S - rr - S * 0.015
        d = ImageDraw.Draw(img)
        d.ellipse([ex - rr, ey - rr, ex + rr, ey + rr],
                  fill=_hex_rgb(LORE_EMBER) + (255,),
                  outline=(255, 236, 210, 255), width=max(3, int(S * 0.012)))

    return img.resize((P, P), Image.LANCZOS)


def _make_tray_images():
    """Two tray icons: the tome at rest, and the tome with a red ember."""
    try:
        idle = _tome_mark(256, recording=False).resize((64, 64))
        rec = _tome_mark(256, recording=True).resize((64, 64))
        return idle, rec
    except Exception:
        try:
            from PIL import Image, ImageDraw
            base = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            ImageDraw.Draw(base).ellipse([5, 5, 58, 58], fill=_hex_rgba(LORE_GOLD, 255))
            return base, base
        except Exception:
            return None, None


# ---------------------------------------------------------------------------
#  Library - the tome's table of contents. Folder-derived (like the old
#  dashboard strips) so it is always in sync with what's on disk: nothing to
#  index, nothing to lose. Videos are grouped by the game name baked into the
#  filename; chapters are ordered by how many videos each game holds.
# ---------------------------------------------------------------------------
def _parse_clip_name(fname):
    """Turn 'RocketLeague_20260616_142233.mp4' into a readable 'RocketLeague'.
    '_clip' (hotkey clips) and '_cut' (pieces bound in the player) are part of
    the file's role, not the game's name - both fold into the game's chapter."""
    import re
    base = os.path.splitext(os.path.basename(fname))[0]
    m = re.match(r"^(.*?)(?:_clip|_cut|_edit)?_(\d{8})_(\d{6})$", base)
    name = (m.group(1) if m else base).replace("_", " ").strip()
    return name or "Recording"


# Pretty titles for exe stems that concatenate their words - the filename is
# the only truth we have, so well-known games get their real names and the
# rest get sensible splitting. Keys are lower-case with spaces stripped.
_GAME_NAMES = {
    "eldenring": "Elden Ring", "eldenringnightreign": "Elden Ring Nightreign",
    "33immortals": "33 Immortals",
    "rocketleague": "Rocket League", "hearthstone": "Hearthstone",
    "trackmania": "Trackmania", "trackmania2020": "Trackmania",
    "witcher3": "The Witcher 3", "thewitcher3": "The Witcher 3",
    "hades": "Hades", "hades2": "Hades II", "hadesii": "Hades II",
    "stardewvalley": "Stardew Valley", "screen": "Desktop", "desktop": "Desktop",
    "cyberpunk2077": "Cyberpunk 2077", "eldenscrolls": "Elder Scrolls",
    "baldursgate3": "Baldur's Gate 3", "bg3": "Baldur's Gate 3",
    "corepunk": "Corepunk", "soulframe": "Soulframe", "warframe": "Warframe",
    "overwatch": "Overwatch", "valorant": "Valorant", "helldivers2": "Helldivers 2",
    "eafc24": "EA FC 24", "eafc25": "EA FC 25", "fortnite": "Fortnite",
    "minecraft": "Minecraft", "terraria": "Terraria", "factorio": "Factorio",
    "satisfactory": "Satisfactory", "pathofexile": "Path of Exile",
    "pathofexile2": "Path of Exile 2", "poe2": "Path of Exile 2",
    "diablo4": "Diablo IV", "diabloiv": "Diablo IV",
    "monsterhunterwilds": "Monster Hunter Wilds", "nioh2": "Nioh 2",
    "sekiro": "Sekiro", "darksouls3": "Dark Souls III", "armoredcore6": "Armored Core VI",
    "immortalsofaveum": "Immortals of Aveum", "backroomslostrunners": "Backrooms Lost Runners",
    "theawakenerfo": "The Awakener", "theawakener": "The Awakener",
    "visionquench": "Vision Quench", "penguinhotel": "Mecha Chameleon",
    "steamwebhelper": "Steam", "corepunkclient": "Corepunk",
    # ---- name fixes + folder merges (words stuck together / duplicate folders) ----
    "hearthstoneheroesofwarcraft": "Hearthstone",   # merge the 286-video folder into Hearthstone
    "liesofp": "Lies of P",
    "drovaforsakenkin": "Drova",
    "guiltyassock": "Guilty as Sock",
    "lostinrandomtheeternaldie": "Lost in Random: The Eternal Die",
    "tcgcardshopsimulator": "TCG Card Shop Simulator",
    "swordartonlinefractureddaydream": "Sword Art Online: Fractured Daydream",
    "swordartonlinelastrecollection": "Sword Art Online: Last Recollection",
    "repo": "R.E.P.O", "r.e.p.o": "R.E.P.O",         # the two R.E.P.O folders are one game
    # ---- spacing/casing fixes from the full name review (CamelCase can't split glued lowercase words) ----
    "ageofwonders4": "Age of Wonders 4",
    "ageofdarknessfinalstand": "Age of Darkness: Final Stand",
    "asterigoscurseofthestars": "Asterigos: Curse of the Stars",
    "awayout": "A Way Out",
    "ballxpit": "BALL x PIT",
    "doomthedarkages": "DOOM: The Dark Ages",
    "dontscreamtogether": "Don't Scream Together",
    "dungeonsofsundaria": "Dungeons of Sundaria",
    "hellisus": "Hell is Us",
    "lordsofthefallen(2023)": "Lords of the Fallen (2023)",
    "nierautomata": "NieR: Automata",
    "riskofrain2": "Risk of Rain 2",
    "runescapedragonwilds": "RuneScape: Dragonwilds",
    "seaofthieves": "Sea of Thieves",
    "shapeofdreams": "Shape of Dreams",
    "taintedgrailthefallofavalon": "Tainted Grail: The Fall of Avalon",
    "theelderscrollsivoblivionremastered": "The Elder Scrolls IV: Oblivion Remastered",
    "vrising": "V Rising",
    "warhammer40000spacemarine2": "Warhammer 40,000: Space Marine 2",
    "starwarsbattlefrontii": "Star Wars Battlefront II",
    "granbluefantasyrelink": "Granblue Fantasy: Relink",
    "thronebreakerthewitchertales": "Thronebreaker: The Witcher Tales",
}


_USER_GAME_NAMES = None   # lazy cache: {current-title.lower(): user's new title}
_AUTO_GAME_NAMES = None   # lazy cache: {normalised exe/title key: {name, source, confidence, ...}}
_RELEARN_PENDING = set()  # stems with a steam re-learn timer already ticking - one shot, never a chain


def _user_names_path():
    return os.path.join(_data_dir(), "user_game_names.json")


def _auto_names_path():
    return os.path.join(_data_dir(), "auto_game_names.json")


def _load_user_game_names():
    global _USER_GAME_NAMES
    if _USER_GAME_NAMES is not None:
        return _USER_GAME_NAMES
    d = {}
    try:
        with open(_user_names_path(), encoding="utf-8") as fh:
            raw = json.load(fh)
        if isinstance(raw, dict):
            d = {str(k).strip().lower(): str(v).strip()
                 for k, v in raw.items() if str(v).strip()}
    except Exception:
        d = {}
    _USER_GAME_NAMES = d
    return d


def _save_user_game_names(d):
    global _USER_GAME_NAMES
    _USER_GAME_NAMES = d
    try:
        _atomic_write_json(_user_names_path(), d)
    except Exception:
        pass


def _load_auto_game_names():
    global _AUTO_GAME_NAMES
    if _AUTO_GAME_NAMES is not None:
        return _AUTO_GAME_NAMES
    d = {}
    try:
        with open(_auto_names_path(), encoding="utf-8") as fh:
            raw = json.load(fh)
        if isinstance(raw, dict):
            # self-heal: an older learner could persist engine internals
            # (TAGame et al.) - drop them on load so the filename-derived
            # title takes over again and the next launch re-learns properly
            junk = {"tagame", "ue4game", "ue5game", "unrealwindow", "cryengine",
                    "unityplayer", "godot engine", "gameapp",
                    "bootstrappackagedgame", "d3d11", "dx11", "main"}
            healed = False
            for k, v in raw.items():
                kk = _norm_game_key(k)
                if not kk:
                    continue
                nm = v if isinstance(v, str) else str((v or {}).get("name", ""))
                if nm.strip().lower() in junk:
                    healed = True
                    continue
                if isinstance(v, str):
                    d[kk] = {"name": v, "source": "legacy", "confidence": 50}
                elif isinstance(v, dict) and str(v.get("name", "")).strip():
                    d[kk] = v
            if healed:
                try:
                    _atomic_write_json(_auto_names_path(), d)
                    log("Purged engine-junk game titles from the learned names.")
                except Exception:
                    pass
    except Exception:
        d = {}
    _AUTO_GAME_NAMES = d
    return d


def _save_auto_game_names(d):
    global _AUTO_GAME_NAMES
    _AUTO_GAME_NAMES = d
    try:
        _atomic_write_json(_auto_names_path(), d)
    except Exception:
        pass


def _norm_game_key(s):
    import re
    return re.sub(r"[^a-z0-9]+", "", str(s or "").lower())


def _auto_name_for_raw(raw):
    """Automatic exe/title/appmanifest alias for an old or future recording.
    This is what makes a newly discovered real title apply to all existing files
    without renaming or moving them."""
    try:
        auto = _load_auto_game_names()
        keys = {_norm_game_key(raw), _norm_game_key(os.path.splitext(str(raw))[0])}
        for k in keys:
            it = auto.get(k)
            if isinstance(it, dict) and str(it.get("name", "")).strip():
                return str(it["name"]).strip()
            if isinstance(it, str) and it.strip():
                return it.strip()
    except Exception:
        pass
    return None


def _clean_game_display_title(title, raw_base=""):
    """Turn a taskbar/window title or metadata string into a stable game title,
    rejecting scene names, device/API suffixes and obvious launcher junk."""
    import re
    s = str(title or "").replace("™", "").replace("®", "").replace("©", "")
    s = re.sub(r"[\r\n\t]+", " ", s).strip(" -_|—–")
    if not s or len(s) < 3 or len(s) > 96:
        return None
    if re.search(r"[A-Za-z]:\\|/|https?://", s):
        return None
    # Drop pure technical tags but keep real subtitles such as ': Wings of Ruin'.
    s = re.sub(r"\s*[\[(](?:dx\s*1[12]|directx\s*1[12]|vulkan|opengl|win64|x64|shipping|64-bit|steam|epic)[\])]\s*", " ", s, flags=re.I)
    s = re.sub(r"\s+[-–—]\s+(?:dx\s*1[12]|directx\s*1[12]|vulkan|opengl|win64|x64|shipping|steam|epic)$", "", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip(" -_|—–")
    low = s.lower()
    bad_exact = {"unity", "unreal engine", "game", "launcher", "bootstrapper",
                 "loading", "not responding", "application", "windows",
                 # engine INTERNALS that leak through EXE version metadata -
                 # Rocket League's FileDescription is literally "TAGame"
                 "tagame", "ue4game", "ue5game", "unrealwindow", "cryengine",
                 "unityplayer", "godot engine", "gameapp",
                 "bootstrappackagedgame", "d3d11", "dx11", "main"}
    # only the ENGINE's splash strings are junk - a bare "unreal " prefix
    # used to eat the actual Unreal Tournament titles
    if low in bad_exact or low.endswith(" launcher") or low.startswith(("unreal engine", "unreal editor")):
        return None
    # NOTE: a name that merely EQUALS the exe stem is kept - it is the CORRECT
    # title and must be able to OUTRANK engine junk. (Rejecting it here once
    # left "TAGame" as the only exe-version candidate, which then won.) The
    # learner skips STORING a pointless same-as-stem alias instead.
    if raw_base and _norm_game_key(s) in {"", "win64shipping", "shipping"}:
        return None
    # Avoid volatile titles that are probably just level/server/editor state.
    if re.search(r"\b(level|map|server|lobby|match|profile|settings|options)\b", low) and len(s.split()) <= 3:
        return None
    return s


def _game_exe_path(pname):
    try:
        for pr in psutil.process_iter(["pid", "name", "exe"]):
            if (pr.info.get("name") or "").lower() == str(pname or "").lower():
                ex = pr.info.get("exe") or ""
                if ex and os.path.isfile(ex):
                    return ex
    except Exception:
        pass
    return None


def _file_version_strings(exe_path):
    """ProductName/FileDescription from the EXE version resource, no internet."""
    if os.name != "nt" or not exe_path or not os.path.isfile(exe_path):
        return []
    try:
        import ctypes
        from ctypes import wintypes
        ver = ctypes.windll.version
        size = ver.GetFileVersionInfoSizeW(exe_path, None)
        if not size:
            return []
        buf = ctypes.create_string_buffer(size)
        if not ver.GetFileVersionInfoW(exe_path, 0, size, buf):
            return []
        trans_ptr = ctypes.c_void_p()
        trans_len = wintypes.UINT()
        langs = [(0x0409, 0x04B0)]
        if ver.VerQueryValueW(buf, "\\VarFileInfo\\Translation",
                              ctypes.byref(trans_ptr), ctypes.byref(trans_len)) and trans_len.value >= 4:
            arr = (ctypes.c_ushort * (trans_len.value // 2)).from_address(trans_ptr.value)
            langs = [(arr[i], arr[i + 1]) for i in range(0, min(len(arr) - 1, 8), 2)]
        out = []
        for lang, cp in langs:
            for key in ("ProductName", "FileDescription", "InternalName"):
                ptr = ctypes.c_void_p(); ln = wintypes.UINT()
                sub = f"\\StringFileInfo\\{lang:04x}{cp:04x}\\{key}"
                if ver.VerQueryValueW(buf, sub, ctypes.byref(ptr), ctypes.byref(ln)) and ptr.value:
                    txt = ctypes.wstring_at(ptr.value, max(0, ln.value - 1)).strip()
                    if txt and txt not in out:
                        out.append(txt)
        return out
    except Exception:
        return []


def _steam_name_for_exe(exe_path):
    """Steam appmanifest DisplayName by matching steamapps/common/<installdir>."""
    if not exe_path:
        return None
    try:
        import glob, re
        p = os.path.abspath(exe_path)
        parts = p.split(os.sep)
        steamapps = None
        installdir = None
        for i, part in enumerate(parts):
            if part.lower() == "steamapps":
                steamapps = os.sep.join(parts[:i + 1])
                if i + 2 < len(parts) and parts[i + 1].lower() == "common":
                    installdir = parts[i + 2]
                break
        if not steamapps or not installdir:
            return None
        for mf in glob.glob(os.path.join(steamapps, "appmanifest_*.acf")):
            try:
                txt = open(mf, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            mdir = re.search(r'"installdir"\s+"([^"]+)"', txt, re.I)
            mname = re.search(r'"name"\s+"([^"]+)"', txt, re.I)
            if mdir and mname and mdir.group(1).strip().lower() == installdir.lower():
                return mname.group(1).strip()
    except Exception:
        pass
    return None


def _registry_name_for_exe(exe_path):
    """Installed-app DisplayName by matching Uninstall InstallLocation/DisplayIcon."""
    if os.name != "nt" or not exe_path:
        return None
    try:
        import winreg, re
        p = os.path.normcase(os.path.abspath(exe_path))
        roots = [(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
                 (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
                 (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall")]
        for root, sub in roots:
            try:
                key = winreg.OpenKey(root, sub)
            except OSError:
                continue
            with key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        sk = winreg.OpenKey(key, winreg.EnumKey(key, i))
                    except OSError:
                        continue
                    with sk:
                        def q(name):
                            try: return str(winreg.QueryValueEx(sk, name)[0]).strip()
                            except Exception: return ""
                        name = q("DisplayName")
                        if not name:
                            continue
                        loc = q("InstallLocation")
                        icon = q("DisplayIcon")
                        icon = re.sub(r'^"|",?\d*$|,\d+$', "", icon).strip('"')
                        hit = False
                        for cand in (loc, icon):
                            if not cand:
                                continue
                            c = os.path.normcase(os.path.abspath(os.path.expandvars(cand)))
                            if c and (p == c or p.startswith(c.rstrip(os.sep) + os.sep)):
                                hit = True; break
                        if hit:
                            return name
    except Exception:
        pass
    return None


def _folder_name_for_exe(exe_path):
    if not exe_path:
        return None
    try:
        skip = {"binaries", "win64", "win32", "x64", "x86", "shipping", "retail",
                "content", "engine", "bin"}
        d = os.path.dirname(os.path.abspath(exe_path))
        for _ in range(5):
            name = os.path.basename(d)
            if name and name.lower() not in skip:
                return name
            nd = os.path.dirname(d)
            if nd == d:
                break
            d = nd
    except Exception:
        pass
    return None


def _learn_game_display_name(pname, retry=True):
    """Discover and persist the best no-internet display name for a running game.
    Priority: taskbar/window title -> Steam manifest -> registry -> EXE metadata -> folder.
    The alias key is the raw EXE stem, so old recordings and future recordings both
    show the corrected title without renaming files."""
    try:
        raw_base = os.path.splitext(os.path.basename(str(pname or "")))[0]
        if not raw_base or raw_base.lower() in ("screen", "desktop", "test"):
            return None
        exe = _game_exe_path(pname)
        candidates = []
        title = _game_window_title(pname)
        ct = _clean_game_display_title(title, raw_base)
        if ct:
            candidates.append((95, "window-title", ct))
        sn = _clean_game_display_title(_steam_name_for_exe(exe), raw_base)
        if sn:
            candidates.append((94, "steam-manifest", sn))
        rn = _clean_game_display_title(_registry_name_for_exe(exe), raw_base)
        if rn:
            candidates.append((86, "registry", rn))
        for txt in _file_version_strings(exe):
            vn = _clean_game_display_title(txt, raw_base)
            if vn:
                candidates.append((78, "exe-version", vn))
        fn = _clean_game_display_title(_folder_name_for_exe(exe), raw_base)
        if fn:
            candidates.append((62, "install-folder", fn))
        if not candidates:
            return None
        score, source, name = sorted(candidates, key=lambda x: (-x[0], -len(x[2])))[0]
        # a Steam miss at record start is usually Steam rewriting the manifest
        # at that exact second (LastPlayed) - re-learn ONCE shortly after, when
        # the acf is whole again. gated on steam actually MISSING: window-title
        # outranks steam 95>94, so testing the winner's source was true on
        # every run and chained a 20s full-rescan timer all session long.
        # sits ABOVE the same-as-stem return so a stem-titled winner can't
        # swallow the retry; one-shot (retry flag + pending set) so parallel
        # record starts can't stack timers either.
        if retry and sn is None and exe and "steamapps" in exe.lower() \
                and raw_base not in _RELEARN_PENDING:
            try:
                _RELEARN_PENDING.add(raw_base)
                def _relearn(p=pname, b=raw_base):
                    _RELEARN_PENDING.discard(b)
                    _learn_game_display_name(p, retry=False)
                threading.Timer(20.0, _relearn).start()
            except Exception:
                _RELEARN_PENDING.discard(raw_base)
        if _norm_game_key(name) == _norm_game_key(raw_base):
            # the winner just confirms the filename-derived title: nothing worth
            # persisting, and crucially nothing WRONG got stored either
            return name
        auto = dict(_load_auto_game_names())
        keys = {_norm_game_key(raw_base), _norm_game_key(pname)}
        if exe:
            keys.add(_norm_game_key(os.path.splitext(os.path.basename(exe))[0]))
        changed = False
        for k in {x for x in keys if x}:
            old = auto.get(k, {}) if isinstance(auto.get(k), dict) else {}
            old_score = int(old.get("confidence", 0) or 0)
            old_name = str(old.get("name", "")).strip()
            if not old_name or score >= old_score - 3:
                auto[k] = {"name": name, "source": source, "confidence": score,
                           "exe": exe or "", "window_title": title or "", "seen": time.time()}
                changed = True
        if changed:
            _save_auto_game_names(auto)
            if _norm_game_key(name) != _norm_game_key(raw_base):
                log(f"Game title learned: {raw_base} -> {name} ({source})")
        return name
    except Exception as e:
        log(f"Game title learn failed: {e}")
        return None


def _apply_user_name(name):
    """A user rename overrides the computed title AND every future recording of
    that game (same exe -> same computed title -> same override). Resolves a
    short A->B->C chain so repeated renames still land on the latest name."""
    try:
        ov = _load_user_game_names()
        if not ov:
            return name
        cur, seen = name, set()
        for _ in range(6):
            k = cur.strip().lower()
            if k in ov and ov[k] and ov[k] != cur and k not in seen:
                seen.add(k)
                cur = ov[k]
            else:
                break
        return cur
    except Exception:
        return name


def _display_name(raw):
    """Best-effort pretty title for a chapter heading: known games get their
    real names; the rest get their engine's build suffix stripped, then
    CamelCase / letter-digit splitting and title-casing. The filename is the
    only truth we have, so this is cosmetic and never fails."""
    import re
    try:
        s = str(raw)
        # strip Unreal/Unity/GDK shipping-build tails: 'Foo-Win64-Shipping',
        # 'Foo-WinGDK-Shipping', 'FooClient-Win64-Test', 'Foo-Shipping', etc.
        s = re.sub(r"[-_\s]*(Win(?:64|32|GDK|Client)?|Shipping|Client|Server|Test|"
                   r"Final|Development|Cmd|EGS|Steam)+([-_\s].*)?$", "", s,
                   flags=re.IGNORECASE).strip(" -_") or str(raw)
        # strip a leaked capture-date that got glued onto the name, e.g.
        # 'Game_20251216' or 'Game 20251216 143022' - a bare run of 8 digits is
        # never part of a real title, so it can only be a stray timestamp that
        # otherwise spawns a phantom one-off "game" split from its real folder.
        s2 = re.sub(r"[\s_\-]+\d{8}(?:[\s_\-]+\d{6})?$", "", s).strip(" -_")
        if s2:
            s = s2
        key = re.sub(r"[\s_\-]+", "", s).lower()
        auto = _auto_name_for_raw(s)
        if auto:
            return _apply_user_name(auto)
        if key in _GAME_NAMES:
            return _apply_user_name(_GAME_NAMES[key])
        s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", s)
        s = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", s).strip()
        if s.islower():
            s = s.title()
        return _apply_user_name(s or str(raw))
    except Exception:
        return str(raw)


def _safe_folder(name):
    """A filesystem-safe folder name for a game's shelf on the disk."""
    bad = set('<>:"/|?*') | {chr(92)}
    sname = "".join(c for c in str(name) if c not in bad)
    sname = sname.strip().rstrip(".")
    return sname or "Unsorted"


def _game_shelf(base, kind, make=True):
    """Where a recording belongs now: output_dir/<Game>/Videos for full
    sessions, output_dir/<Game>/Clips for clips - one tidy shelf per game
    (the user's library-organisation ask)."""
    d = os.path.join(SETTINGS.get("output_dir", ""),
                     _safe_folder(_display_name(base)),
                     "Videos" if kind == "session" else "Clips")
    if make:
        os.makedirs(d, exist_ok=True)
    return d


def _library_dirs(out):
    """Every folder a recording can live in, as (dir, kind) pairs: the
    per-game shelves (<Game>/Videos + <Game>/Clips) AND the flat legacy
    spots. ONE source of truth so the scanner, the change-signature and the
    storage cap all look in exactly the same places (they drifted apart when
    shelves arrived, which hid new recordings and starved the cap)."""
    pairs = []
    try:
        for name in os.listdir(out):
            d = os.path.join(out, name)
            if (not os.path.isdir(d) or name.startswith(".")
                    or name in ("Clips", "Old")):
                continue
            pairs.append((os.path.join(d, "Videos"), "session"))
            pairs.append((os.path.join(d, "Clips"), "clip"))
    except Exception:
        pass
    pairs.append((out, "session"))
    pairs.append((os.path.join(out, "Clips"), "clip"))
    return pairs


def _thumb_dir(out):
    # ALL thumbnails live in ONE cache at the recordings-folder root, keyed by
    # the (unique) filename - never a per-shelf dir, or the generator and the
    # readers look in different places. Survives a reinstall.
    return os.path.join(SETTINGS.get("output_dir", "") or out, ".lore_thumbs")


def _probe_color_trc(path):
    """The video stream's transfer characteristic ('smpte2084' for PQ/HDR10,
    'arib-std-b67' for HLG, '' when unknown/SDR)."""
    try:
        d = os.path.dirname(SETTINGS["ffmpeg_path"])
        probe = os.path.join(d, "ffprobe.exe" if os.name == "nt" else "ffprobe") if d else "ffprobe"
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        r = subprocess.run([probe, "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=color_transfer", "-of",
                            "default=nw=1:nokey=1", path],
                           capture_output=True, text=True, timeout=15, creationflags=flags)
        return (r.stdout or "").strip().lower()
    except Exception:
        return ""


def _ensure_thumb(video_path, tdir):
    """Return a cached JPG thumbnail for a video, generating it with ffmpeg the
    first time. The frame is normally taken from the MIDDLE of the clip (the
    start is often a black loading screen), and HDR recordings go through the
    same measured-correct SDR conversion as the finishing queue, so previews
    match the finished file. Some recordings go dark partway (screen idled,
    game left on a menu) and are black from the middle to the end, so the grab
    walks a ladder of seek points toward the start and keeps the best frame it
    finds. Every attempt renders to a temp file with its own timeout - a killed
    ffmpeg used to leave a 0-byte JPG at the real name, which the cache then
    trusted forever (the eternal broken-image glyph). If Records (LORE's
    previous incarnation) already made a thumbnail for this exact video, it is
    adopted instead of re-rendered."""
    try:
        name = os.path.splitext(os.path.basename(video_path))[0] + ".jpg"
        tp = os.path.join(tdir, name)
        # a cached thumb only counts if it has BYTES: a 0-byte file is the
        # corpse of a killed ffmpeg, not a picture. regenerate those.
        if (os.path.isfile(tp) and os.path.getsize(tp) > 0
                and os.path.getmtime(tp) >= os.path.getmtime(video_path)):
            return tp
        os.makedirs(tdir, exist_ok=True)
        # adopt a Records-era thumbnail when it's still current (and non-empty)
        try:
            legacy = os.path.join(os.path.dirname(tdir), ".records_thumbs", name)
            if (os.path.isfile(legacy) and os.path.getsize(legacy) > 0
                    and os.path.getmtime(legacy) >= os.path.getmtime(video_path)):
                shutil.copy2(legacy, tp)
                return tp
        except Exception:
            pass
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        dur = _probe_duration(video_path) or 0
        trc = _probe_color_trc(video_path)
        # -2 keeps the height EVEN: zscale/zimg refuses odd 4:2:0 dimensions
        # (that silent refusal is why HDR files once had black thumbnails).
        vf = "scale=480:-2"
        if _is_hdr_trc(trc):
            vf += "," + _hdr_to_sdr_vf(trc)
        # seek ladder: middle first (healthy files keep their familiar thumb),
        # then earlier and earlier - a recording whose screen went dark only
        # has real pixels in its opening seconds. probe failed -> 3s, not
        # frame 0 (a black loading screen).
        if dur > 0.5:
            ladder = [dur * 0.5, dur * 0.25, dur * 0.1, min(30.0, dur * 0.5), 0.0]
        else:
            ladder = [3.0, 0.0]
        seen, attempts = set(), []
        for ss in ladder:
            key = round(ss, 1)
            if key not in seen:
                seen.add(key)
                attempts.append(ss)
        # temp name UNIQUE per invocation: thumb() and a thumbs() batch provably
        # overlap on the same uncached video (the turn preload races the landing
        # render), and two ffmpegs sharing one .part name corrupt each other
        tmp = tp + f".part.{os.getpid()}.{threading.get_ident()}.jpg"
        best, last_err = 0, b""
        try:
            for ss in attempts:
                try:
                    r = subprocess.run([SETTINGS["ffmpeg_path"], "-y", "-ss", f"{ss:.2f}",
                                        "-i", video_path, "-frames:v", "1", "-vf", vf,
                                        "-q:v", "5", "-update", "1", tmp],
                                       capture_output=True, timeout=20, creationflags=flags)
                    last_err = r.stderr or b""
                except subprocess.TimeoutExpired:
                    continue    # one slow seek must not doom the rest of the ladder
                try:
                    sz = os.path.getsize(tmp) if os.path.isfile(tmp) else 0
                except OSError:
                    sz = 0
                if sz > best:
                    best = sz
                    os.replace(tmp, tp)   # atomic: readers never see a torn JPG
                if best >= 2000:
                    break   # flat black compresses to ~600 bytes; a real frame doesn't
        finally:
            try:
                if os.path.isfile(tmp):
                    os.remove(tmp)    # even when os.replace threw mid-ladder
            except OSError:
                pass
        if best <= 0:
            for ln in last_err.decode("utf-8", "ignore").splitlines()[-2:]:
                log("  ffmpeg(thumb): " + ln)
        return tp if (os.path.isfile(tp) and os.path.getsize(tp) > 0) else None
    except Exception:
        return None


# Duration cache: ffprobe is ~50ms per file, so durations are probed lazily
# (only for the page being looked at) and remembered against the file's mtime,
# in memory and in a sidecar next to the thumbnails so restarts stay instant.
_DUR_CACHE = {}
_DUR_LOCK = threading.Lock()
_DUR_LOADED = [False]


def _dur_sidecar():
    return os.path.join(_thumb_dir(SETTINGS.get("output_dir", "") or _data_dir()),
                        "durations.json")


def _dur_load_once():
    if _DUR_LOADED[0]:
        return
    _DUR_LOADED[0] = True
    try:
        with open(_dur_sidecar(), encoding="utf-8") as fh:
            data = json.load(fh)
        with _DUR_LOCK:
            for k, v in data.items():
                if isinstance(v, list) and len(v) == 2:
                    _DUR_CACHE[k] = (float(v[0]), float(v[1]))
    except Exception:
        pass


def _dur_save():
    try:
        with _DUR_LOCK:
            data = {k: [v[0], v[1]] for k, v in _DUR_CACHE.items()}
        os.makedirs(os.path.dirname(_dur_sidecar()), exist_ok=True)
        _atomic_write_json(_dur_sidecar(), data)
    except Exception:
        pass


def _video_duration(path):
    """Cached duration in seconds (None while unknown)."""
    _dur_load_once()
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return None
    key = os.path.normcase(os.path.abspath(path))
    with _DUR_LOCK:
        hit = _DUR_CACHE.get(key)
        if hit and abs(hit[0] - mt) < 2:
            return hit[1]
    d = _probe_duration(path)
    if d is not None:
        with _DUR_LOCK:
            _DUR_CACHE[key] = (mt, float(d))
    return d


def _scan_dir_mp4s(directory, kind):
    """All finished .mp4s in one folder (work-in-progress '.__' temps skipped,
    same rule the old dashboard lived by). os.scandir, because the signature
    poll walks every shelf every 2s: the old isfile+getsize+stat trio paid
    three syscalls per file, while scandir's entries carry the stat data for
    free on Windows."""
    items = []
    try:
        with os.scandir(directory) as it:
            for e in it:
                f = e.name
                if f.startswith(".") or not f.lower().endswith(".mp4"):
                    continue
                if ".__" in f:
                    continue
                try:
                    if not e.is_file():
                        continue
                    st = e.stat()
                except Exception:
                    continue
                if st.st_size < 100_000:
                    continue
                items.append({"path": e.path, "file": f, "kind": kind,
                              "mtime": st.st_mtime, "size": st.st_size})
    except Exception:
        pass
    return items


def scan_library():
    """The whole book: every recording and clip on disk, grouped into chapters
    by game, ordered by how many videos each chapter holds (most first, ties
    broken by whoever was played most recently)."""
    out = SETTINGS.get("output_dir", "")
    vids = []
    for d, kind in _library_dirs(out):
        vids += _scan_dir_mp4s(d, kind)
    groups = {}
    for v in vids:
        raw = _parse_clip_name(v["file"])
        disp = _display_name(raw)
        # Group by DISPLAY name (lowercased), NOT the raw filename, so name-map
        # aliases actually MERGE into one chapter: Trackmania + Trackmania 2020,
        # Diablo 4 + Diablo IV, the two R.E.P.O folders, Desktop + The Desk,
        # Hearthstone + Hearthstone Heroes of Warcraft, etc.
        key = disp.lower()
        g = groups.setdefault(key, {"key": key, "name": disp,
                                    "display": disp,
                                    "sessions": [], "clips": []})
        badge = _finish_badge(v["path"])
        dur = None                       # duration from the CACHE only - never probe
        try:                             # here, or scan_library would ffprobe the whole
            _dur_load_once()             # library and hang the first load
            _dk = os.path.normcase(os.path.abspath(v["path"]))
            with _DUR_LOCK:
                _dh = _DUR_CACHE.get(_dk)
            if _dh and abs(_dh[0] - v["mtime"]) < 2:
                dur = _dh[1]
        except Exception:
            dur = None
        item = {"path": v["path"], "mtime": v["mtime"], "size": v["size"],
                "kind": v["kind"],
                "dur": (round(dur, 1) if dur is not None else None),
                "badge": ({"text": badge[0], "phase": badge[1]} if badge else None)}
        (g["sessions"] if v["kind"] == "session" else g["clips"]).append(item)
    for g in groups.values():
        g["sessions"].sort(key=lambda x: x["mtime"], reverse=True)
        g["clips"].sort(key=lambda x: x["mtime"], reverse=True)
        g["count"] = len(g["sessions"]) + len(g["clips"])
        g["latest"] = max([x["mtime"] for x in g["sessions"] + g["clips"]] or [0])
    ordered = sorted(groups.values(), key=lambda g: (-g["count"], -g["latest"]))
    return {"games": ordered, "out_dir": out}


def _library_signature():
    """Cheap change fingerprint: paths + mtimes + each file's finishing phase.
    The UI polls this and only re-reads the library when it moves - the same
    signature idea that stopped the old dashboard flashing."""
    out = SETTINGS.get("output_dir", "")
    sig = []
    for d, kind in _library_dirs(out):
        for v in _scan_dir_mp4s(d, kind):
            b = _finish_badge(v["path"])
            sig.append(f"{v['file']}|{int(v['mtime'])}|{v['size']}|{b[1] if b else ''}")
    sig.sort()
    import hashlib
    return hashlib.md5("\n".join(sig).encode("utf-8", "ignore")).hexdigest()


# ---------------------------------------------------------------------------
#  Popups v3 - LORE's own on-top notifications. Same battle-tested frame: one
#  FIXED window whose pre-rendered PIL frames are swapped (window-move
#  animation silently fails on some machines - never move a popup window).
#  Size scales with the watched monitor; entrance style is the user's pick.
#  Only the card art changed: warm ink, a candle-gold bar, the tome's seal.
# ---------------------------------------------------------------------------
_POPUP_STYLES = [("slide", "Slide in"), ("rise", "Float up"), ("pop", "Pop"),
                 ("glow", "Glow"), ("sweep", "Light sweep"), ("off", "Instant")]


def _popup_key(label):
    for k, lbl in _POPUP_STYLES:
        if lbl == label:
            return k
    return "slide"


def _toast_metrics():
    """Popup size scaled to the WATCHED monitor's work area (a fixed 432px card
    reads as a speck on a 5120px ultrawide). Width by the Size setting."""
    wa = _watched_monitor_workarea()
    ww = (wa[2] - wa[0]) if wa else 1920
    frac = {"small": 0.13, "medium": 0.17, "large": 0.21, "huge": 0.26}.get(
        str(SETTINGS.get("popup_size", "large")).lower(), 0.21)
    W = max(380, min(1500, int(ww * frac)))
    return W, max(88, int(W * 0.215))


def _pil_font(px, bold=True):
    from PIL import ImageFont
    # Book-ish faces first (Palatino ships with Windows), then the safe stack.
    names = (("palab.ttf", "constb.ttf", "georgiab.ttf", "segoeuib.ttf", "arialbd.ttf") if bold
             else ("pala.ttf", "constan.ttf", "georgia.ttf", "segoeui.ttf", "arial.ttf"))
    for n in names:
        try:
            return ImageFont.truetype(n, px)
        except Exception:
            continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def _seal_glyph(px):
    """The mark that stamps every popup - the SAME closed-tome art as the app
    icon and the tray, so every face of LORE wears one identity."""
    return _tome_mark(px)


def _toast_card_rgba(W, H, title, sub, glow_amt=0.0, sweep_x=None):
    """One fully-baked popup card on TRANSPARENT ground: deep warm-ink card,
    hairline edge, a rounded candle-gold bar down the left, the seal on a soft
    tile, two clean lines of book type. glow_amt adds an ember halo (the
    'Glow' style); sweep_x places a soft light band ('Light sweep')."""
    from PIL import Image, ImageDraw, ImageFilter
    face = LORE_INK
    edge = LORE_INK_EDGE
    tile = LORE_TILE
    ar, ag, ab = _hex_rgb(LORE_GOLD)
    R = max(12, int(H * 0.17))
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([1, 1, W - 2, H - 2], radius=R, fill=255)
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle([1, 1, W - 2, H - 2], radius=R,
                                           fill=_hex_rgb(face) + (255,))
    out = Image.alpha_composite(out, card)
    # 'Glow' pulses a golden rim INSIDE the card silhouette. It must never
    # paint outside the rounded shape: the popup window uses a binary colour
    # key, so any anti-aliased halo pixel outside the card would render as an
    # opaque dark fleck over the game (the v1 'squared corners' flash).
    ga = max(0.0, min(1.8, glow_amt))
    if ga > 0.02:
        er, eg, eb = _hex_rgb(LORE_GOLD)
        halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(halo).rounded_rectangle([2, 2, W - 3, H - 3], radius=R,
                                               outline=(er, eg, eb,
                                                        int(165 * min(1.0, ga))),
                                               width=max(3, H // 18))
        halo = halo.filter(ImageFilter.GaussianBlur(max(3, H / 16)))
        halo = Image.composite(halo, Image.new("RGBA", (W, H), (0, 0, 0, 0)), mask)
        out = Image.alpha_composite(out, halo)
    if sweep_x is not None:
        band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        bwid = int(H * 0.8)
        ImageDraw.Draw(band).polygon(
            [(sweep_x, 0), (sweep_x + bwid, 0),
             (sweep_x + bwid - int(H * 0.5), H), (sweep_x - int(H * 0.5), H)],
            fill=(255, 236, 200, 44))
        band = band.filter(ImageFilter.GaussianBlur(max(3, H / 18)))
        band = Image.composite(band, Image.new("RGBA", (W, H), (0, 0, 0, 0)), mask)
        out = Image.alpha_composite(out, band)
    d = ImageDraw.Draw(out)
    d.rounded_rectangle([1, 1, W - 2, H - 2], radius=R,
                        outline=_hex_rgb(edge) + (255,), width=1)
    bar_w = max(5, H // 16)
    bar = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(bar).rounded_rectangle(
        [int(H * 0.16), int(H * 0.16), int(H * 0.16) + bar_w, H - int(H * 0.16)],
        radius=bar_w // 2, fill=(ar, ag, ab, 255))
    out = Image.alpha_composite(out, bar)
    ts = int(H * 0.60)
    tx0 = int(H * 0.30)
    ty0 = (H - ts) // 2
    tile_im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(tile_im).rounded_rectangle([tx0, ty0, tx0 + ts, ty0 + ts],
                                              radius=int(ts * 0.28),
                                              fill=_hex_rgb(tile) + (255,))
    out = Image.alpha_composite(out, tile_im)
    bs = int(ts * 0.72)
    try:
        out.alpha_composite(_seal_glyph(bs), (tx0 + (ts - bs) // 2, ty0 + (ts - bs) // 2))
    except Exception:
        pass
    txx = tx0 + ts + int(H * 0.22)
    maxw = W - txx - int(H * 0.32)
    ft = _pil_font(int(H * 0.225), bold=True)
    fs = _pil_font(int(H * 0.155), bold=False)
    d = ImageDraw.Draw(out)

    def fit(txt, f):
        txt = (txt or "").strip()
        if not f:
            return txt
        trimmed = False
        while txt and d.textlength(txt + "…", font=f) > maxw:
            txt = txt[:-1]
            trimmed = True
        return (txt + "…") if trimmed else txt

    if ft:
        # Palatino draws U+2713 as a fleuron, not a check - strip it from the
        # text and draw a proper little gold check after the title instead.
        t_txt = (title or "").strip()
        had_check = "✓" in t_txt
        t_txt = fit(t_txt.replace("✓", "").strip(), ft)
        d.text((txx, int(H * 0.315)), t_txt, font=ft,
               fill=_hex_rgb(LORE_IVORY) + (255,), anchor="lm")
        if had_check:
            cw = d.textlength(t_txt, font=ft)
            cx0 = txx + cw + int(H * 0.10)
            cy0 = int(H * 0.315)
            k = H * 0.085
            d.line([(cx0, cy0), (cx0 + k * 0.7, cy0 + k * 0.7),
                    (cx0 + k * 1.8, cy0 - k * 0.9)],
                   fill=_hex_rgb(LORE_GOLD_HI) + (255,),
                   width=max(2, int(H * 0.035)), joint="curve")
    if fs and sub:
        d.text((txx, int(H * 0.660)), fit(sub, fs), font=fs,
               fill=_hex_rgb(LORE_FADED) + (255,), anchor="lm")
    return out


def _toast_flat(card_rgba, key_rgb, scale=1.0, dx=0, dy=0):
    """Flatten a card frame onto the colorkey ground - optionally scaled about
    the centre ('Pop') or offset ('Slide in'/'Float up' reveal the card THROUGH
    the fixed window like a mask; the window itself never moves)."""
    from PIL import Image
    W, H = card_rgba.size
    base = Image.new("RGB", (W, H), key_rgb)
    if abs(scale - 1.0) >= 0.005:
        sw, sh = max(2, int(W * scale)), max(2, int(H * scale))
        scaled = card_rgba.resize((sw, sh), Image.LANCZOS)
        base.paste(scaled, ((W - sw) // 2 + int(dx), (H - sh) // 2 + int(dy)), scaled)
    else:
        base.paste(card_rgba, (int(dx), int(dy)), card_rgba)
    return base


def _watched_monitor_workarea():
    """Work area of the monitor LORE is set to RECORD. Pop-ups are pinned
    there - where the game is - instead of wandering onto another screen.
    Returns None to fall back to the primary work area."""
    try:
        mons = _enumerate_active_monitors()
        if not mons:
            return None
        mons.sort(key=lambda m: m["num"])
        idx = min(max(0, _resolve_capture_monitor()), len(mons) - 1)
        return tuple(mons[idx].get("work") or mons[idx]["rect"])
    except Exception:
        return None


def _screen_workarea(top):
    """Work-area rect of the PRIMARY monitor, excluding the taskbar."""
    sw, sh = top.winfo_screenwidth(), top.winfo_screenheight()
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            r = wintypes.RECT()
            if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0):
                return (r.left, r.top, r.right, r.bottom)
        except Exception:
            pass
    return (0, 0, sw, sh)


def _show_toast(root, title, sub):
    """LORE's own on-top popup, bottom-right of the WATCHED monitor - visible
    over fullscreen games (Windows hides its own popups there). Click to
    dismiss. Only one shows at a time; UI-pump thread only."""
    import tkinter as tk
    try:
        style = str(SETTINGS.get("popup_style", "slide")).lower()
        prev = getattr(root, "_active_toast", None)
        if prev is not None:
            try:
                if prev.winfo_exists():
                    prev.destroy()
            except Exception:
                pass
        top = tk.Toplevel(root)
        root._active_toast = top
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        KEY = "#0a0c10"
        transparent = False
        try:
            top.wm_attributes("-transparentcolor", KEY)
            transparent = True
        except Exception:
            pass
        top.configure(bg=KEY)
        W, H = _toast_metrics()
        key_rgb = _hex_rgb(KEY if transparent else LORE_INK)
        cv = tk.Canvas(top, width=W, height=H, bg=KEY, highlightthickness=0, bd=0)
        cv.pack()

        def _dismiss(_e=None):
            try:
                if top.winfo_exists():
                    top.destroy()
            except Exception:
                pass
        cv.bind("<Button-1>", _dismiss)

        from PIL import ImageTk
        card = _toast_card_rgba(W, H, title, sub)
        frames = []

        def show_img(pil):
            img = ImageTk.PhotoImage(pil)
            frames.append(img)
            cv.delete("all")
            cv.create_image(0, 0, image=img, anchor="nw")

        # PRE-RENDER the whole entrance before the window is ever mapped, and
        # position the window before Tk realises it. v1 (and Records before it)
        # mapped a fully-settled card at (0,0) first, THEN moved it and started
        # animating - which read as a flash in the wrong corner followed by the
        # animation restarting from zero. Now the first pixel anyone sees is
        # the first frame of the entrance, already in the right place.
        def eased(n, ease):
            return [ease(i / (n - 1)) for i in range(n)]
        e_out = lambda t: 1 - (1 - t) ** 3
        settled_img = _toast_flat(card, key_rgb)
        if style == "slide":
            seq = [_toast_flat(card, key_rgb, dx=int((1 - e) * W * 0.55))
                   for e in eased(11, e_out)]
            frame_ms = 16
        elif style == "rise":
            seq = [_toast_flat(card, key_rgb, dy=int((1 - e) * H * 1.0))
                   for e in eased(10, e_out)]
            frame_ms = 16
        elif style == "pop":
            seq = [_toast_flat(card, key_rgb, s)
                   for s in (0.86, 0.93, 0.99, 1.035, 1.05, 1.02, 1.0)]
            frame_ms = 22
        elif style == "glow":
            lo = _toast_card_rgba(W, H, title, sub, glow_amt=0.6)
            hi = _toast_card_rgba(W, H, title, sub, glow_amt=1.6)
            from PIL import Image
            seq = [_toast_flat(Image.blend(lo, hi, a), key_rgb)
                   for a in (0.0, 0.45, 0.9, 1.0, 0.7, 0.4, 0.15)] + [settled_img]
            frame_ms = 34
        elif style == "sweep":
            xs = [int(-H * 0.9 + (W + H * 1.8) * i / 8.0) for i in range(9)]
            seq = [_toast_flat(_toast_card_rgba(W, H, title, sub, sweep_x=x), key_rgb)
                   for x in xs] + [settled_img]
            frame_ms = 28
        else:                                        # 'off' - instant
            seq = [settled_img]
            frame_ms = 0

        wl, wt, wr, wb = _watched_monitor_workarea() or _screen_workarea(top)
        m = max(18, int(H * 0.28))
        fx, fy = max(wl, wr - W - m), max(wt, wb - H - m)
        top.geometry(f"{W}x{H}+{fx}+{fy}")
        show_img(seq[0])
        top.update_idletasks()

        # Keep re-asserting topmost for the popup's whole life (a focused window
        # keeps re-winning the z-order otherwise), with NOACTIVATE so it never
        # steals focus from the game.
        def _raise_toast():
            if not top.winfo_exists():
                return
            try:
                top.attributes("-topmost", True)
                top.lift()
                if os.name == "nt":
                    import ctypes
                    GA_ROOT = 2
                    hwnd = ctypes.windll.user32.GetAncestor(top.winfo_id(), GA_ROOT)
                    ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0,
                                                      0x0001 | 0x0002 | 0x0010)
            except Exception:
                pass
            top.after(250, _raise_toast)
        _raise_toast()

        def fade_out(a):
            if not top.winfo_exists():
                return
            try:
                top.attributes("-alpha", max(0.0, a))
            except Exception:
                pass
            if a > 0.06:
                top.after(16, lambda: fade_out(a - 0.12))
            else:
                try:
                    top.destroy()
                except Exception:
                    pass

        HOLD = 6000
        try:
            top.attributes("-alpha", 0.985)
        except Exception:
            pass

        def settle():
            # rest, then leave with a clean fade. (The old draining countdown
            # line read as "the popup vanished and left a weird shrinking
            # line" - decorative, confusing, gone.)
            if not top.winfo_exists():
                return
            top.after(HOLD, lambda: fade_out(0.985))

        # play the pre-rendered entrance (frame 0 is already on screen)
        rest = list(seq[1:])
        if not rest:
            settle()
        else:
            def step():
                if not top.winfo_exists():
                    return
                if rest:
                    show_img(rest.pop(0))
                    top.after(frame_ms, step)
                else:
                    settle()
            top.after(frame_ms, step)
    except Exception as e:
        log(f"toast failed: {e}")


# ---------------------------------------------------------------------------
#  UI pump - a hidden Tk root on its own thread. It exists ONLY to draw the
#  over-game popups and to notice a second launch's show.flag; every Tk call
#  stays on this one thread (marshalled through ctl.ui_enqueue), which is the
#  same contract the old shell kept on the main thread.
# ---------------------------------------------------------------------------
def _start_ui_pump(ctl, on_show_request):
    def run():
        try:
            import queue
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
        except Exception as e:
            log(f"UI pump unavailable ({e}); popups disabled.")
            return
        cmds = queue.Queue()
        ctl.ui_enqueue = cmds.put
        ctl.ui_root = root

        def pump():
            try:
                if os.path.exists(_show_flag_path()):
                    os.remove(_show_flag_path())
                    try:
                        on_show_request()
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                while True:
                    fn = cmds.get_nowait()
                    try:
                        fn()
                    except Exception as e:
                        log(f"UI action error: {e}")
            except queue.Empty:
                pass
            # The pump outlives ctl.quit ON PURPOSE: quitting while a save is
            # still binding shows "Finishing your recording" / "Saved" popups,
            # and killing the Tk root on quit.set() destroyed them unseen.
            # _UI_QUIT is set only after the watcher has fully drained - and
            # even then we linger ~2.4s so a "Saved" popup enqueued in the
            # same instant (the save's last act) gets its moment on screen.
            if _UI_QUIT.is_set():
                if not hasattr(root, "_quit_t0"):
                    root._quit_t0 = time.time()
                if time.time() - root._quit_t0 > 2.4:
                    try:
                        root.destroy()
                    except Exception:
                        pass
                    return
            root.after(120, pump)
        root.after(120, pump)
        try:
            root.mainloop()
        except Exception:
            pass
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t


# ---------------------------------------------------------------------------
#  The scrying stream - WebView2 refuses file:// media outright ("Media load
#  rejected by URL safety check", measured), so watching a memory inside the
#  tome goes through a tiny localhost server instead. Loopback-only, a fresh
#  random token per launch, only files inside the library are ever served,
#  and Range requests are honoured so the timeline can seek.
# ---------------------------------------------------------------------------
_MEDIA = {"port": None, "token": None, "srv": None}


def _media_safe_path(p):
    try:
        out = os.path.abspath(SETTINGS.get("output_dir", ""))
        ap = os.path.abspath(p)
        if os.path.commonpath([out, ap]) == out and os.path.isfile(ap):
            return ap
    except Exception:
        pass
    return None


def _start_media_server():
    import http.server
    import socketserver
    import secrets
    import base64
    from urllib.parse import urlparse, parse_qs
    if _MEDIA["srv"] is not None:
        return
    token = secrets.token_urlsafe(16)

    class _H(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def do_GET(self):
            try:
                q = parse_qs(urlparse(self.path).query)
                if q.get("t", [""])[0] != token:
                    self.send_error(403)
                    return
                raw = q.get("p", [""])[0]
                path = base64.urlsafe_b64decode(raw.encode("ascii")).decode("utf-8")
                path = _media_safe_path(path)
                if not path:
                    self.send_error(404)
                    return
                size = os.path.getsize(path)
                rng = self.headers.get("Range")
                start, end = 0, size - 1
                if rng:
                    import re as _re
                    m = _re.match(r"bytes=(\d*)-(\d*)", rng)
                    if m:
                        if m.group(1):
                            start = int(m.group(1))
                            if m.group(2):
                                end = min(int(m.group(2)), size - 1)
                        elif m.group(2):          # suffix range: last N bytes
                            start = max(0, size - int(m.group(2)))
                    if start > end or start >= size:
                        self.send_response(416)
                        self.send_header("Content-Range", f"bytes */{size}")
                        self.send_header("Content-Length", "0")   # keep-alive safe
                        self.end_headers()
                        return
                    self.send_response(206)
                    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                else:
                    self.send_response(200)
                length = end - start + 1
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Content-Length", str(length))
                self.send_header("Accept-Ranges", "bytes")
                # Let the browser CACHE the ranges it fetches. With no-store it
                # threw everything away and re-downloaded on every seek - that was
                # the "skip and it buffers" lag. stream_url carries the file mtime,
                # so an edited/re-encoded file gets a fresh URL and can't serve a
                # stale cache.
                self.send_header("Cache-Control", "private, max-age=86400")
                self.end_headers()
                _MEDIA["last_read"] = time.time()   # user is watching -> defer SDR conversions
                _source_busy_add(path)
                try:
                    with open(path, "rb") as fh:
                        fh.seek(start)
                        remaining = length
                        while remaining > 0:
                            chunk = fh.read(min(131072, remaining))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            remaining -= len(chunk)
                finally:
                    _source_busy_done(path)
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                pass                       # the player seeked/closed; normal
            except Exception:
                try:
                    self.send_error(500)
                except Exception:
                    pass

    class _Srv(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    try:
        srv = _Srv(("127.0.0.1", 0), _H)
    except Exception as e:
        log(f"Scrying stream unavailable ({e}); videos open externally.")
        return
    _MEDIA["srv"] = srv
    _MEDIA["port"] = srv.server_address[1]
    _MEDIA["token"] = token
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    log(f"Scrying stream ready on 127.0.0.1:{_MEDIA['port']}")


def _stop_media_server():
    srv = _MEDIA.get("srv")
    if srv is not None:
        try:
            srv.shutdown()
        except Exception:
            pass
        _MEDIA["srv"] = None


# ---------------------------------------------------------------------------
#  The bridge - every method here is callable from the tome's JavaScript as
#  window.pywebview.api.<name>(...). They run on pywebview worker threads, so
#  they only do what the old tray/menu handlers did: poke ctl events, read
#  SETTINGS, spawn worker threads. Nothing here touches Tk directly.
# ---------------------------------------------------------------------------
class _JsApi:
    def __init__(self, ctl):
        self._ctl = ctl
        self._win = None          # set once the window exists
        self._quitting = [False]
        self._hdr_cache = {"t": 0.0, "v": False}
        self._hide_toasted = [False]
        self._reveal_ok = True    # False when started --hidden (tray only)
        self._settled = False     # True once first_paint fired OR the user hid
                                  # the tome - either way the reveal watchdog
                                  # must never pop the window open on its own
        self._drag_live = [False]   # a cursor-follow move loop is running
        self._fs_prev = None        # Win32 true-fullscreen restore state
        self._disk_cache = {"t": 0.0, "v": None}   # free-space, 5s pulse

    # ---------------- state ----------------
    def state(self):
        ctl = self._ctl
        s = ctl.eff_status()
        sess = getattr(ctl, "session", None)
        game = ""
        if sess is not None:
            game = _display_name(os.path.splitext(getattr(sess, "game", "") or "")[0])
        t0 = getattr(ctl, "rec_t0", None)
        elapsed = int(max(0, time.time() - t0)) if (t0 and s in ("recording", "paused")) else 0
        conv = None
        if _FINISHING.get("busy") and _FINISHING.get("path"):
            conv = {"name": os.path.basename(_FINISHING["path"]),
                    "pct": _FINISHING.get("pct")}
        binding = None
        if getattr(ctl, "saving", 0) > 0 and _BINDING.get("name"):
            binding = {"name": _BINDING["name"], "pct": _BINDING.get("pct"),
                       "eta": _BINDING.get("eta"), "mbps": _BINDING.get("mbps")}
        now = time.time()
        if now - self._hdr_cache["t"] > 5:
            self._hdr_cache = {"t": now, "v": _hdr_active()}
        free_gb = None
        try:
            # one syscall, but every ~.6s for a number that crawls (and nothing
            # in the tome reads it yet) - same 5s pulse as _hdr_cache above
            if now - self._disk_cache["t"] > 5:
                self._disk_cache = {"t": now, "v": shutil.disk_usage(
                    SETTINGS.get("output_dir", ".")).free / 1e9}
            free_gb = self._disk_cache["v"]
        except Exception:
            pass
        size_mb = None
        if sess is not None and not getattr(sess, "suspended", False):
            try:
                size_mb = sum(os.path.getsize(p) for p in _list_segments(sess.tmp)) / 1e6
            except Exception:
                pass
        return {"status": s, "game": game, "elapsed": elapsed,
                "saving": getattr(ctl, "saving", 0) > 0,
                "binding": binding,
                "converting": conv,
                "queued": len(_queued_finish_paths()),
                "encoder": _friendly_codec(SETTINGS.get("_encoder_resolved")),
                "fps": SETTINGS.get("framerate", 60),
                "hdr": self._hdr_cache["v"],
                "free_gb": free_gb, "size_mb": size_mb,
                "webhook": bool(SETTINGS.get("discord_webhook", "").strip()),
                "version": APP_VERSION}

    def signature(self):
        return _library_signature()

    def library(self):
        return scan_library()

    def thumb(self, path):
        """Base64 data-URL thumbnail for one video (generated on first ask).
        Data-URLs keep the tome origin-clean - no file:// fetch rules apply."""
        p = self._safe_path(path)
        if not p:
            return None
        tp = _ensure_thumb(p, _thumb_dir(SETTINGS.get("output_dir", "")))
        if not tp:
            return None
        try:
            import base64
            with open(tp, "rb") as fh:
                return "data:image/jpeg;base64," + base64.b64encode(fh.read()).decode("ascii")
        except Exception:
            return None

    def thumbs(self, paths):
        """Base64 thumbnails for a WHOLE page in one call. The per-thumb RPC
        round-trip (one JS<->Python hop each) was the 'wheel spins for a second'
        when opening a game - a page of 6 clips meant 6 serialized hops. The UI
        preloads a spread's thumbs with this before it lands, so they're already
        cached when the cards render."""
        import base64
        out = {}
        tdir = _thumb_dir(SETTINGS.get("output_dir", ""))
        for path in (paths or [])[:60]:
            p = self._safe_path(path)
            if not p:
                continue
            try:
                tp = _ensure_thumb(p, tdir)
                if tp:
                    with open(tp, "rb") as fh:
                        out[path] = ("data:image/jpeg;base64,"
                                     + base64.b64encode(fh.read()).decode("ascii"))
            except Exception:
                pass
        return out

    def meta(self, paths):
        """Durations for the videos on the open page (cached probes)."""
        out = {}
        for path in (paths or [])[:40]:
            p = self._safe_path(path)
            if p:
                d = _video_duration(p)
                if d is not None:
                    out[path] = round(d, 1)
        _dur_save()
        return out

    # ---------------- recording actions ----------------
    def record_toggle(self):
        ctl = self._ctl
        s = ctl.eff_status()
        if s in ("recording", "paused", "starting"):
            ctl.click_feedback("off", "watching")
            ctl.stop_now.set()
        else:
            ctl.click_feedback("on", "starting", secs=12.0)
            ctl.watching.set()
            ctl.force_record.set()
        return True

    def pause_toggle(self):
        ctl = self._ctl
        if ctl.eff_status() not in ("recording", "paused"):
            return False
        if ctl.watching.is_set():
            ctl.click_feedback("off", "paused")
            ctl.watching.clear()
        else:
            ctl.click_feedback("on", "recording")
            ctl.watching.set()
        return True

    def clip(self, seconds=None):
        _trigger_replay(self._ctl, seconds)
        return True

    def clip_discord(self):
        _trigger_replay(self._ctl, force_discord=True)
        return True

    # ---------------- files ----------------
    def _safe_path(self, path):
        """Only ever touch files inside the library (recordings folder). The
        bridge is local, but a habit of checking costs nothing."""
        try:
            out = os.path.abspath(SETTINGS.get("output_dir", ""))
            p = os.path.abspath(str(path))
            if os.path.commonpath([out, p]) == out and os.path.isfile(p):
                return p
        except Exception:
            pass
        return None

    def open_video(self, path):
        p = self._safe_path(path)
        if p:
            try:
                os.startfile(p)
                return True
            except Exception as e:
                log(f"open file failed: {e}")
        return False

    def reveal(self, path):
        p = self._safe_path(path)
        if p:
            try:
                flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                subprocess.Popen(["explorer", "/select,", p], creationflags=flags)
                return True
            except Exception as e:
                log(f"reveal failed: {e}")
        return False

    def open_folder(self, kind="recordings"):
        out = SETTINGS.get("output_dir", "")
        p = os.path.join(out, "Clips") if kind == "clips" else out
        try:
            os.makedirs(p, exist_ok=True)
            os.startfile(p)
            return True
        except Exception as e:
            log(f"open folder failed: {e}")
            return False

    def delete_video(self, path):
        """Burn a memory reliably: validate the path, release/avoid in-use
        files, retry transient Windows locks, then forget manifest/queue/thumb/
        duration cache entries. Missing files count as success so the UI can
        refresh instead of looking stuck."""
        try:
            out = os.path.abspath(SETTINGS.get("output_dir", ""))
            p = os.path.abspath(str(path or ""))
            if not out or os.path.commonpath([out, p]) != out:
                return {"ok": False, "why": "bad-path"}
        except Exception:
            return {"ok": False, "why": "bad-path"}
        ap = os.path.normcase(os.path.abspath(p))

        def _forget():
            try:
                with _MANIFEST_LOCK:
                    owned, existed = _load_manifest()
                    if existed and ap in owned:
                        owned.discard(ap)
                        _save_manifest(owned)
            except Exception:
                pass
            try:
                # locked pair: unlocked, this rewrite could erase an entry a
                # finishing clip appended between our load and our save
                with _FINISH_Q_LOCK:
                    q = [it for it in _load_finish_queue()
                         if os.path.normcase(os.path.abspath(it.get("path", ""))) != ap]
                    _save_finish_queue(q)
            except Exception:
                pass
            try:
                tp = os.path.join(_thumb_dir(SETTINGS.get("output_dir", "")),
                                  os.path.splitext(os.path.basename(p))[0] + ".jpg")
                if os.path.isfile(tp):
                    os.remove(tp)
            except Exception:
                pass
            try:
                _dur_load_once()
                with _DUR_LOCK:
                    _DUR_CACHE.pop(ap, None)
                _dur_save()
            except Exception:
                pass
            try:
                # Keep the shelf tidy after the last clip/session is burned.
                for d in (os.path.dirname(p), os.path.dirname(os.path.dirname(p))):
                    if d and os.path.isdir(d) and not os.listdir(d):
                        os.rmdir(d)
            except Exception:
                pass

        if _FINISHING.get("busy") and os.path.normcase(os.path.abspath(_FINISHING.get("path") or "")) == ap:
            return {"ok": False, "why": "converting"}

        if _source_busy(p):
            for _ in range(12):
                time.sleep(0.15)
                if not _source_busy(p):
                    break
            else:
                return {"ok": False, "why": "playing"}

        if not os.path.exists(p):
            _forget()
            return {"ok": True, "why": "gone"}

        last = None
        for _ in range(20):
            try:
                os.remove(p)
                _forget()
                log(f"Burned from the library: {os.path.basename(p)}")
                return {"ok": True}
            except FileNotFoundError:
                _forget()
                return {"ok": True, "why": "gone"}
            except PermissionError as e:
                last = e
                time.sleep(0.25)
            except OSError as e:
                last = e
                time.sleep(0.25)
        log(f"delete failed: {last}")
        return {"ok": False, "why": "locked", "detail": str(last or "")}

    def post_discord(self, path):
        """Send any saved video to the Discord webhook (compressed copy, the
        original stays untouched) - the same pipeline as the clip hotkey."""
        p = self._safe_path(path)
        if not p:
            return False
        ctl = self._ctl

        def work():
            _maybe_post_discord(ctl, p)
        threading.Thread(target=work, daemon=True).start()
        return True

    # ---------------- settings ----------------
    def get_settings(self):
        clean = {k: v for k, v in SETTINGS.items() if not k.startswith("_")}
        outs, mics = list_audio_devices()
        return {"settings": clean,
                "games": read_games_lines(),
                "ignore": read_ignore_lines(),
                "devices": {"outputs": outs, "mics": mics},
                "monitors": _active_monitor_count(),
                "autostart": _is_autostart_enabled(),
                "popup_styles": _POPUP_STYLES,
                "version": APP_VERSION}

    def set_settings(self, patch):
        """Merge a partial settings dict, sanitize with the same rules a loaded
        settings.json gets, persist, reload. 'autostart' rides along as a
        pseudo-key. Returns the applied settings."""
        try:
            patch = dict(patch or {})
        except Exception:
            return self.get_settings()
        autostart = patch.pop("autostart", None)
        allowed = set(DEFAULTS.keys())
        HK_KEYS = ("hotkey_record", "hotkey_replay", "hotkey_pause", "hotkey_clip_discord")
        hk_before = tuple(str(SETTINGS.get(k, "") or "") for k in HK_KEYS)
        # Snapshot->merge->write under the settings lock: a concurrent
        # _persist_setting (the watcher remembering safe_capture) must never
        # be reverted by a stale snapshot.
        try:
            with _SETTINGS_LOCK:
                data = {k: v for k, v in SETTINGS.items() if not k.startswith("_")}
                for k, v in patch.items():
                    if k in allowed:
                        data[k] = v
                _sanitize_settings(data)
                hm = str(data.get("hdr_mode", "auto")).lower()
                data["hdr_mode"] = hm if hm in ("auto", "off") else "auto"
                try:
                    data["output_dir"] = str(data.get("output_dir") or "").strip() or DEFAULTS["output_dir"]
                except Exception:
                    data["output_dir"] = DEFAULTS["output_dir"]
                for hk in ("hotkey_record", "hotkey_replay", "hotkey_pause", "hotkey_clip_discord",
                           "discord_webhook", "mic_name_contains", "audio_output_device"):
                    data[hk] = str(data.get(hk) or "").strip()
                _atomic_write_json(_settings_path(), data)
            load_settings()
        except Exception as e:
            log(f"Could not save settings: {e}")
        # A changed sigil takes hold IMMEDIATELY: bump the generation and the
        # hotkey service re-registers with the fresh combos within ~30 ms.
        if tuple(str(SETTINGS.get(k, "") or "") for k in HK_KEYS) != hk_before:
            _HK_GEN[0] += 1
        if autostart is not None:
            try:
                if bool(autostart) != _is_autostart_enabled():
                    _set_autostart(bool(autostart))
            except Exception as e:
                log(f"Autostart toggle failed: {e}")
        return self.get_settings()

    def set_games(self, lines):
        try:
            write_games_lines([str(x) for x in (lines or [])])
        except Exception as e:
            log(f"Could not save games list: {e}")
        return read_games_lines()

    def set_ignore(self, lines):
        try:
            write_ignore_lines([str(x) for x in (lines or [])])
        except Exception as e:
            log(f"Could not save ignore list: {e}")
        return read_ignore_lines()

    def audio_devices(self):
        outs, mics = list_audio_devices()
        return {"outputs": outs, "mics": mics}

    def test_sound(self, volume=None):
        if volume is not None:
            try:
                SETTINGS["sfx_volume"] = max(0, min(100, int(volume)))
            except Exception:
                pass
        _play_sound("shutter")
        return True

    def preview_popup(self, style=None, size=None):
        if style in [k for k, _l in _POPUP_STYLES]:
            SETTINGS["popup_style"] = style
        if size in ("small", "medium", "large", "huge"):
            SETTINGS["popup_size"] = size
        log(f"Popup preview: {SETTINGS['popup_style']} / {SETTINGS['popup_size']}")
        # force: the user just pressed "preview" - it must show even mid-write
        self._ctl.toast("LORE", "Whispers will look like this.", force=True)
        return True

    def browse_folder(self):
        try:
            import webview
            if self._win is not None:
                res = self._win.create_file_dialog(webview.FOLDER_DIALOG)
                if res:
                    return os.path.normpath(res[0] if isinstance(res, (list, tuple)) else res)
        except Exception as e:
            log(f"browse failed: {e}")
        return None

    # ---------------- window ----------------
    def stream_url(self, path):
        """A tokened loopback URL the tome's <video> can actually play
        (WebView2 rejects file:// media outright)."""
        p = self._safe_path(path)
        if not p or not _MEDIA.get("port"):
            return None
        import base64
        b = base64.urlsafe_b64encode(p.encode("utf-8")).decode("ascii")
        try:
            m = int(os.path.getmtime(p))
        except Exception:
            m = 0
        # &m = the file's mtime: a cache-buster so a re-encoded/edited file (new
        # mtime) is fetched fresh instead of served from the browser's cache.
        return f"http://127.0.0.1:{_MEDIA['port']}/v?t={_MEDIA['token']}&p={b}&m={m}"

    def set_shape(self, shapes):
        """v1.2.4: the book fills the WHOLE window now (the cut-away-wings
        experiment produced white artefacts on real boots and is retired),
        so any window region is simply CLEARED. Kept for page compat."""
        try:
            import ctypes
            h = _lore_hwnd()
            if h:
                ctypes.windll.user32.SetWindowRgn(h, None, True)
            return True
        except Exception:
            return False

    def begin_drag(self):
        """Move the window by the leather. The old WM_NCLBUTTONDOWN/HTCAPTION
        trick silently did NOTHING in production: ReleaseCapture() from the
        bridge thread can't release the WebView2 child's mouse capture
        (capture is per-thread), so the OS move loop never saw the mouse.
        LORE runs its own mover instead: a thread follows the physical cursor
        while the button is held (GetCursorPos + SetWindowPos, all physical
        px - no DPI math) and on release applies the edge snaps by hand:
        top = maximize, left/right screen edge = half-screen."""
        h = _lore_hwnd()
        if not h:
            return False
        if self._drag_live[0]:
            return True
        self._drag_live[0] = True
        threading.Thread(target=_drag_loop, args=(self._drag_live, h),
                         daemon=True).start()
        return True

    def toggle_maximize(self):
        h = _lore_hwnd()
        if not h:
            return False
        try:
            import ctypes
            u = ctypes.windll.user32
            if u.IsZoomed(h):
                u.ShowWindow(h, 9)      # SW_RESTORE
            else:
                _fit_maximize_bounds()  # maximize must spare the taskbar
                u.ShowWindow(h, 3)      # SW_MAXIMIZE
            return bool(u.IsZoomed(h))
        except Exception:
            return False

    def window_state(self):
        h = _lore_hwnd()
        try:
            import ctypes
            return {"maximized": bool(h and ctypes.windll.user32.IsZoomed(h))}
        except Exception:
            return {"maximized": False}

    def toggle_fullscreen(self):
        """TRUE OS fullscreen: cover the WHOLE monitor rectangle INCLUDING the
        Windows taskbar. Raw Win32 SetWindowLong/SetWindowPos on this
        WinForms-hosted window was silently clobbered - WinForms owns the
        Form's border/state/bounds and re-imposes them (and a maximized form's
        MaximizedBounds pins it to the taskbar-sparing work area), so the popup
        + monitor-rect never actually covered the taskbar. Drive the WinForms
        Form itself instead: strip its border, pin it TopMost, and set Bounds to
        the monitor's FULL rectangle (Screen.FromHandle(...).Bounds, NOT
        WorkingArea). All Form mutation is marshalled onto the GUI thread via
        Invoke; Screen.FromHandle keeps it correct on multi-monitor."""
        if os.name != "nt":
            return False
        try:
            import webview.platforms.winforms as _wf
            from System import Action
            from System.Windows.Forms import (Screen, FormBorderStyle,
                                              FormWindowState)
            # `None` is a Python keyword - reach the enum member by name.
            _FBS_NONE = getattr(FormBorderStyle, "None")

            form = None
            for f in list(getattr(_wf.BrowserView, "instances", {}).values()):
                form = f
                break
            if form is None:
                return False

            def _enter():
                if self._fs_prev is None:   # NEVER recapture mid-transition: a re-run after a throw would save TopMost=True as the "previous" state and the exit could not undo it
                    self._fs_prev = {"border": form.FormBorderStyle,
                                     "state": form.WindowState,
                                     "bounds": form.Bounds,      # value-type copy
                                     "topmost": form.TopMost}
                # A maximized form won't move to an arbitrary Bounds - normalize
                # first, then take the FULL monitor rect (covers the taskbar).
                if form.WindowState != FormWindowState.Normal:
                    form.WindowState = FormWindowState.Normal
                b = Screen.FromHandle(form.Handle).Bounds
                form.FormBorderStyle = _FBS_NONE
                form.TopMost = True
                form.Bounds = b

            def _exit():
                prev = self._fs_prev
                self._fs_prev = None
                if prev is None:
                    return
                form.TopMost = bool(prev["topmost"])
                form.FormBorderStyle = prev["border"]
                if prev["state"] == FormWindowState.Maximized:
                    try:
                        _fit_maximize_bounds()   # re-spare the taskbar
                    except Exception:
                        pass
                    form.WindowState = FormWindowState.Maximized
                else:
                    form.WindowState = FormWindowState.Normal
                    form.Bounds = prev["bounds"]

            entering = self._fs_prev is None
            action = Action(_enter if entering else _exit)
            try:
                if form.InvokeRequired:
                    form.Invoke(action)
                else:
                    action()
            except Exception as ex:
                # a delegate that THREW mid-mutation must not be blindly re-run:
                # re-running _enter would clobber _fs_prev with half-transition
                # state (TopMost captured as True) and the exit could never undo
                # it. Report failure; the UI resets its flag on False.
                log(f"toggle_fullscreen delegate failed: {ex}")
                return False
            return entering
        except Exception as e:
            log(f"toggle_fullscreen failed: {e}")
            return False

    def rename_game(self, old, new):
        """Rename a game's title (e.g. one that was mis-detected). Stored as a
        user override in user_game_names.json, so EVERY recording of that game -
        past and future - shows the new name without touching a single file.
        Reversible by editing that JSON."""
        try:
            old = str(old or "").strip()
            new = str(new or "").strip()
            if not old or not new or old == new:
                return {"ok": False}
            ov = dict(_load_user_game_names())
            ov[old.lower()] = new
            for k, v in list(ov.items()):      # collapse a chain pointing at the old name
                if str(v).strip().lower() == old.lower():
                    ov[k] = new
            _save_user_game_names(ov)
            return {"ok": True, "name": new}
        except Exception as e:
            log(f"rename_game failed: {e}")
            return {"ok": False}

    def first_paint(self):
        """The tome calls this once its silhouette is applied and the first
        spread is rendered - only then is the window shown, so no rectangular
        flash of un-shaped leather ever appears."""
        self._settled = True      # the tome is up; the watchdog stands down
        try:
            if self._reveal_ok and self._win is not None:
                self._win.show()
                _fit_maximize_bounds()   # so Aero snap-to-top spares the taskbar
        except Exception:
            pass
        return True

    def trim_video(self, path, start, end, to_discord=False, replace=False):
        """Cut [start, end] seconds out of a memory. Normally the cut becomes
        a NEW clip on the game's shelf (the original untouched); with
        replace=True the trimmed piece TAKES THE ORIGINAL'S PLACE - same
        file, now holding just that section. HDR masters go through the same
        measured colour restoration either way.
        NOTE: the shipped tome drives edit_video exclusively - no UI caller
        reaches this method today. A trim-behaviour fix belongs in edit_video;
        this stays for compatibility only."""
        p = self._safe_path(path)
        try:
            start = max(0.0, float(start))
            end = float(end)
        except Exception:
            return {"ok": False, "why": "bad range"}
        if not p or end - start < 0.25:
            return {"ok": False, "why": "bad range"}
        ctl = self._ctl
        stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        raw = _parse_clip_name(os.path.basename(p))
        base = raw.replace(" ", "")
        clips_dir = os.path.dirname(p) if replace else _game_shelf(raw, "clip")
        out = p if replace else os.path.join(clips_dir, f"{base}_cut_{stamp}.mp4")
        # Encode into a '.__' work name and os.replace on success - the same
        # appear-complete-or-not-at-all rule every other producer follows
        # (the library scanner skips '.__' names, so a half-written cut can
        # never show up as a broken card or survive a crash under its final name).
        tmp = os.path.join(clips_dir, f"{base}_cut_{stamp}.__tmp.mp4")

        def work():
            _TRIM_BUSY[0] += 1
            _source_busy_add(p)     # hold the SDR finisher off our source
            # replace REWRITES the original, so an SDR conversion of that same
            # file already in flight must be stopped - otherwise it lands its
            # full-length version on top of the trim moments later.
            if replace:
                try:
                    if os.path.abspath(_FINISHING.get("path") or "") == os.path.abspath(p):
                        _sdr_finish_abort()
                        for _w in range(50):
                            if not _FINISHING.get("busy"):
                                break
                            time.sleep(0.1)
                    q = [x for x in _load_finish_queue()
                         if os.path.abspath(x.get("path", "")) != os.path.abspath(p)]
                    _save_finish_queue(q)
                except Exception:
                    pass
            try:
                os.makedirs(clips_dir, exist_ok=True)
                dur = end - start
                enc = _current_encoder()
                br = int(SETTINGS.get("bitrate_mbps", 25))
                vf = "format=nv12"
                trc = _probe_color_trc(p)
                if _is_hdr_trc(trc):
                    # PQ is absolute: tone-map with the SDR white level from
                    # RECORD time (the finish queue keeps it) - today's
                    # slider position may differ and would shift brightness.
                    nits = None
                    try:
                        ap = os.path.abspath(p)
                        for it in _load_finish_queue():
                            if os.path.abspath(it.get("path", "")) == ap:
                                nits = it.get("nits")
                                break
                    except Exception:
                        pass
                    vf = _hdr_to_sdr_vf(trc, nits) + ",format=nv12"
                flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                cmd = [SETTINGS["ffmpeg_path"], "-y", "-hide_banner",
                       "-loglevel", "error",
                       "-ss", f"{start:.3f}", "-i", p, "-t", f"{dur:.3f}",
                       "-vf", vf, "-c:v", enc,
                       *encoder_quality_flags(enc, br),
                       "-c:a", "aac", "-b:a", "192k", tmp]
                r = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.PIPE, creationflags=flags,
                                   timeout=max(300, dur * 8 + 120))
                if r.returncode == 0 and os.path.isfile(tmp) \
                        and os.path.getsize(tmp) > 10_000:
                    if replace:
                        # the player may still hold the source open - retry
                        # briefly; the tome releases it within a moment
                        for _try in range(25):
                            try:
                                os.replace(tmp, out)
                                break
                            except PermissionError:
                                time.sleep(0.2)
                        else:
                            raise PermissionError("original still in use")
                        # the file is SDR now - drop any pending restoration
                        try:
                            ap = os.path.abspath(out)
                            q = [x for x in _load_finish_queue()
                                 if os.path.abspath(x.get("path", "")) != ap]
                            _save_finish_queue(q)
                        except Exception:
                            pass
                        # its face changed: refresh the cached thumbnail
                        try:
                            tp = os.path.join(
                                _thumb_dir(os.path.dirname(out)),
                                os.path.splitext(os.path.basename(out))[0] + ".jpg")
                            if os.path.isfile(tp):
                                os.remove(tp)
                        except Exception:
                            pass
                        log(f"Trimmed in place ({dur:.1f}s): {out}")
                        ctl.notify("Trimmed ✓",
                                   os.path.basename(out) + " now holds just that piece.")
                    else:
                        os.replace(tmp, out)
                        _record_made_file(out)
                        enforce_storage_cap()
                        log(f"Cut saved ({dur:.1f}s): {out}")
                        ctl.notify("Cut saved ✓", os.path.basename(out))
                    if to_discord:
                        _maybe_post_discord(ctl, out)
                else:
                    for ln in (r.stderr or b"").decode("utf-8", "ignore").splitlines()[-2:]:
                        log("  ffmpeg(cut): " + ln)
                    log("Cut failed; nothing was changed.")
                    ctl.notify("Lore", "Couldn't save that cut - see lore.log.")
            except Exception as e:
                log(f"Cut error: {e}")
                try:
                    ctl.notify("Lore", ("Couldn't replace the original - it was "
                                        "still open. Try again in a moment.")
                               if replace else
                               "Couldn't save that cut - see lore.log.")
                except Exception:
                    pass
            finally:
                try:
                    if os.path.isfile(tmp) and os.path.abspath(tmp) != os.path.abspath(out):
                        os.remove(tmp)
                except Exception:
                    pass
                _source_busy_done(p)
                _TRIM_BUSY[0] -= 1
        threading.Thread(target=work, daemon=True).start()
        return {"ok": True, "name": os.path.basename(out)}

    def edit_video(self, path, segments, replace=False, to_discord=False):
        """The multi-part editor. `segments` is the list of [start,end] seconds to
        KEEP, in order (the UI turns a keep/remove choice into this list). Each
        piece is re-encoded to the user's current bitrate/encoder, the pieces are
        stitched, and the result is saved as a NEW clip - or, with replace=True,
        TAKES THE ORIGINAL'S PLACE. Progress is polled via edit_status(); a Cancel
        (edit_cancel) stops it cleanly. Nothing touches the original until every
        piece has encoded and stitched into a verified temp file."""
        if not _EDIT_JOB.get("done", True):
            return {"ok": False, "why": "an edit is already running"}
        p = self._safe_path(path)
        if not p:
            return {"ok": False, "why": "bad path"}
        segs = []
        try:
            for pair in segments or []:
                s = max(0.0, float(pair[0])); e = float(pair[1])
                if e - s >= 0.20:
                    segs.append([s, e])
        except Exception:
            return {"ok": False, "why": "bad segments"}
        if not segs:
            return {"ok": False, "why": "nothing to keep"}
        segs.sort(key=lambda x: x[0])
        merged = [segs[0]]
        for s, e in segs[1:]:
            if s <= merged[-1][1] + 0.05:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        segs = merged
        total = sum(e - s for s, e in segs)
        if total < 0.25:
            return {"ok": False, "why": "too short"}

        ctl = self._ctl
        stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        raw = _parse_clip_name(os.path.basename(p))
        base = raw.replace(" ", "")
        out_dir = os.path.dirname(p) if replace else _game_shelf(raw, "clip")
        out = p if replace else os.path.join(out_dir, f"{base}_edit_{stamp}.mp4")
        job_id = f"edit_{stamp}"
        _EDIT_JOB.update({"id": job_id, "pct": 0, "phase": "starting",
                          "done": False, "ok": False, "why": "", "cancel": False,
                          "name": os.path.basename(out)})

        def work():
            _TRIM_BUSY[0] += 1
            _source_busy_add(p)
            parts = []
            tmp_final = None
            try:
                if replace:
                    try:
                        if os.path.abspath(_FINISHING.get("path") or "") == os.path.abspath(p):
                            _sdr_finish_abort()
                            for _w in range(50):
                                if not _FINISHING.get("busy"):
                                    break
                                time.sleep(0.1)
                        q = [x for x in _load_finish_queue()
                             if os.path.abspath(x.get("path", "")) != os.path.abspath(p)]
                        _save_finish_queue(q)
                    except Exception:
                        pass
                os.makedirs(out_dir, exist_ok=True)
                enc = _current_encoder()
                br = int(SETTINGS.get("bitrate_mbps", 25))
                vf0 = "format=nv12"
                trc = _probe_color_trc(p)
                if _is_hdr_trc(trc):
                    nits = None
                    try:
                        ap = os.path.abspath(p)
                        for it in _load_finish_queue():
                            if os.path.abspath(it.get("path", "")) == ap:
                                nits = it.get("nits")
                                break
                    except Exception:
                        pass
                    vf0 = _hdr_to_sdr_vf(trc, nits) + ",format=nv12"
                flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                done_dur = 0.0
                for i, (s, e) in enumerate(segs):
                    if _EDIT_JOB["cancel"]:
                        raise _EditCancelled()
                    seg_dur = e - s
                    part = os.path.join(out_dir, f"{base}_edit_{stamp}.part{i}.__tmp.mp4")
                    parts.append(part)
                    _EDIT_JOB["phase"] = (f"cutting piece {i + 1} of {len(segs)}"
                                          if len(segs) > 1 else "cutting")
                    cmd = [SETTINGS["ffmpeg_path"], "-y", "-hide_banner",
                           "-loglevel", "error",
                           "-ss", f"{s:.3f}", "-i", p, "-t", f"{seg_dur:.3f}",
                           "-vf", vf0, "-c:v", enc,
                           *encoder_quality_flags(enc, br),
                           "-c:a", "aac", "-b:a", "192k",
                           "-progress", "pipe:1", "-nostats", part]
                    pr = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                          stderr=subprocess.DEVNULL,
                                          creationflags=flags, text=True, bufsize=1)
                    for line in pr.stdout:
                        if _EDIT_JOB["cancel"]:
                            try:
                                pr.kill()
                                pr.wait(timeout=5)   # release the handle before cleanup
                            except Exception:
                                pass
                            raise _EditCancelled()
                        if line.startswith("out_time_us="):
                            try:
                                us = int(line.split("=", 1)[1])
                                cur = done_dur + min(seg_dur, us / 1_000_000.0)
                                _EDIT_JOB["pct"] = int(max(0, min(92, cur / total * 92)))
                            except Exception:
                                pass
                    pr.wait()
                    if pr.returncode != 0 or not (os.path.isfile(part)
                                                  and os.path.getsize(part) > 10_000):
                        raise RuntimeError(f"piece {i + 1} failed to encode")
                    done_dur += seg_dur
                if _EDIT_JOB["cancel"]:
                    raise _EditCancelled()
                # stitch the pieces (or promote the single piece)
                tmp_final = os.path.join(out_dir, f"{base}_edit_{stamp}.__tmp.mp4")
                _EDIT_JOB["phase"] = "stitching" if len(parts) > 1 else "finishing"
                _EDIT_JOB["pct"] = 94
                if len(parts) == 1:
                    os.replace(parts[0], tmp_final)
                    parts = []
                elif not _concat_copy(SETTINGS["ffmpeg_path"], parts, tmp_final):
                    raise RuntimeError("stitch failed")
                if not (os.path.isfile(tmp_final) and os.path.getsize(tmp_final) > 10_000):
                    raise RuntimeError("empty result")
                # _concat_copy salvages a bad join by DROPPING THE LAST segment and
                # still returns True - for an editor that would silently lose a kept
                # piece (and, on replace, overwrite the original with it). Verify the
                # stitched duration actually holds all the kept time.
                if len(segs) > 1:
                    try:
                        ffp = os.path.join(os.path.dirname(SETTINGS["ffmpeg_path"]), "ffprobe.exe")
                        if not os.path.isfile(ffp):
                            ffp = "ffprobe"
                        rp = subprocess.run([ffp, "-v", "error", "-show_entries",
                                             "format=duration", "-of", "csv=p=0", tmp_final],
                                            capture_output=True, text=True,
                                            creationflags=flags, timeout=60)
                        got = float((rp.stdout or "").strip() or 0)
                    except Exception:
                        got = 0.0
                    if got and abs(got - total) > max(1.0, total * 0.04):
                        raise RuntimeError(f"stitch incomplete: {got:.1f}s of {total:.1f}s")
                # last exit before the commit: a Cancel during the stitch must
                # still win - past os.replace the original is gone for good
                if _EDIT_JOB["cancel"]:
                    raise _EditCancelled()
                _EDIT_JOB["phase"] = "saving"
                _EDIT_JOB["pct"] = 97
                if replace:
                    for _try in range(25):
                        try:
                            os.replace(tmp_final, out)
                            break
                        except PermissionError:
                            time.sleep(0.2)
                    else:
                        raise PermissionError("original still in use")
                else:
                    os.replace(tmp_final, out)
                # the result is now IN PLACE - the save has committed (irreversibly,
                # for replace). Mark success BEFORE any side-effect so a failure in
                # thumb/notify/discord/cap can never flip a committed save to "failed".
                _EDIT_JOB.update({"pct": 100, "phase": "done", "ok": True, "done": True})
                try:
                    if replace:
                        ap = os.path.abspath(out)
                        q = [x for x in _load_finish_queue()
                             if os.path.abspath(x.get("path", "")) != ap]
                        _save_finish_queue(q)
                        tp = os.path.join(
                            _thumb_dir(os.path.dirname(out)),
                            os.path.splitext(os.path.basename(out))[0] + ".jpg")
                        if os.path.isfile(tp):
                            os.remove(tp)
                        log(f"Edited in place ({total:.1f}s, {len(segs)} piece(s)): {out}")
                        ctl.notify("Saved ✓", os.path.basename(out) + " now holds your edit.")
                    else:
                        _record_made_file(out)
                        enforce_storage_cap()
                        log(f"Edit saved ({total:.1f}s, {len(segs)} piece(s)): {out}")
                        ctl.notify("Edit saved ✓", os.path.basename(out))
                    if to_discord:
                        _maybe_post_discord(ctl, out)
                except Exception as _tail:
                    log(f"Edit saved; a post-save step failed: {_tail}")
            except _EditCancelled:
                _EDIT_JOB.update({"phase": "cancelled", "ok": False,
                                  "done": True, "why": "cancelled"})
                log("Edit cancelled by the reader.")
            except Exception as ex:
                _EDIT_JOB.update({"phase": "failed", "ok": False,
                                  "done": True, "why": str(ex)})
                log(f"Edit error: {ex}")
                try:
                    ctl.notify("Lore", "Couldn't save that edit - see lore.log.")
                except Exception:
                    pass
            finally:
                for pp in parts:
                    try:
                        if os.path.isfile(pp):
                            os.remove(pp)
                    except Exception:
                        pass
                try:
                    if tmp_final and os.path.isfile(tmp_final) \
                            and os.path.abspath(tmp_final) != os.path.abspath(out):
                        os.remove(tmp_final)
                except Exception:
                    pass
                _source_busy_done(p)
                _TRIM_BUSY[0] -= 1

        threading.Thread(target=work, daemon=True).start()
        return {"ok": True, "id": job_id}

    def edit_status(self):
        """Live progress for the editor overlay: pct 0-100, a human phase, and
        the terminal done/ok/why once it finishes."""
        j = _EDIT_JOB
        return {"id": j.get("id"), "pct": j.get("pct", 0),
                "phase": j.get("phase", ""), "done": j.get("done", True),
                "ok": j.get("ok", False), "why": j.get("why", ""),
                "name": j.get("name", "")}

    def edit_cancel(self):
        """Ask the running edit to stop; the worker kills ffmpeg and cleans up."""
        _EDIT_JOB["cancel"] = True
        return {"ok": True}

    def resize_to(self, w, h):
        """The brass grip on the cover corner drives the real window. Clamped
        to sane book sizes; the boot size is fixed by _tome_window_size (his
        call), so nothing is remembered across launches."""
        try:
            try:
                import ctypes
                _h = _lore_hwnd()
                if _h and ctypes.windll.user32.IsZoomed(_h):
                    ctypes.windll.user32.ShowWindow(_h, 9)   # SW_RESTORE: a maximized form ignores resize() (only its hidden restore-size changes), so un-maximize first or the grip looks dead
            except Exception:
                pass
            aw, ah = _work_area_size()
            w = max(860, min(int(aw), int(w)))
            h = max(645, min(int(ah), int(h)))
            if self._win is not None:
                self._win.resize(w, h)
            # no persist: _tome_window_size fixes every boot at 1152x648 on
            # purpose, so saving window_size was a write nothing ever read
            # back - and each save was a locked read+fsync'd rewrite of
            # settings.json on a disk ffmpeg may be hammering.
            return True
        except Exception as e:
            log(f"resize failed: {e}")
            return False

    def hide(self):
        self._settled = True      # dismissed on purpose; watchdog stands down
        try:
            if self._win is not None:
                # The book CLOSES as it rests, so the next opening always
                # begins with the cover swinging open. The reset runs on its
                # OWN thread: hide() is called from the window's closing
                # event (the UI thread), and a synchronous evaluate_js there
                # deadlocks - the JS result can only be delivered by the very
                # thread that would be waiting for it. That deadlock was
                # v1.2.2's frozen tome.
                w = self._win

                def _rest():
                    try:
                        w.evaluate_js("window.tomeRest&&tomeRest()")
                    except Exception:
                        pass
                threading.Thread(target=_rest, daemon=True).start()
                self._win.hide()
                if not self._hide_toasted[0]:
                    self._hide_toasted[0] = True
                    self._ctl.toast("The tome rests in the tray",
                                    "LORE keeps watch - games still record themselves.")
            return True
        except Exception:
            return False

    def minimize(self):
        try:
            if self._win is not None:
                self._win.minimize()
            return True
        except Exception:
            return False

    def quit(self):
        _request_quit(self._ctl, self, self._win)
        return True

    def log_js(self, msg):
        # no UI caller today - kept as a debugging hook (evaluate_js can reach it)
        log(f"tome: {str(msg)[:400]}")
        return True


def _friendly_codec(enc):
    e = (enc or "").lower()
    if "av1" in e:
        return "AV1"
    if "hevc" in e or "265" in e:
        return "HEVC"
    if "264" in e or "avc" in e:
        return "H.264"
    return (enc or "auto").upper()[:6]


# ---------------------------------------------------------------------------
#  Quit - mirrors the old shell's care: never vanish while a recording is
#  still being saved. The window closes when every pending save is flushed.
#  _UI_QUIT ends the popup pump (kept alive past ctl.quit so the quit-time
#  popups are actually seen); _HK_GEN re-registers hotkeys when it changes.
# ---------------------------------------------------------------------------
_QUIT_STATE = {"requested": False}
_UI_QUIT = threading.Event()
_HK_GEN = [0]
_TRIM_BUSY = [0]        # cuts currently binding (quit waits for them)
# the multi-part editor's single live job (progress polled by the UI via edit_status)
_EDIT_JOB = {"id": None, "pct": 0, "phase": "", "done": True, "ok": False,
             "why": "", "cancel": False, "name": ""}


class _EditCancelled(Exception):
    """raised inside the editor worker when the user hits Cancel mid-encode"""
    pass


def _request_quit(ctl, api, win):
    if _QUIT_STATE["requested"]:
        return
    _QUIT_STATE["requested"] = True
    api._quitting[0] = True

    def work():
        busy = ctl.saving > 0 or ctl.session is not None or _TRIM_BUSY[0] > 0
        if busy:
            try:
                ctl.set_status("saving")
                ctl.notify("Finishing your recording", "LORE will close once it's saved.")
            except Exception:
                pass
        ctl.quit.set()
        t = _WATCH_THREAD.get("t")
        if t is not None:
            try:
                t.join(timeout=600)
            except Exception:
                pass
        # A cut still binding? Wait for it too - abandoning the worker at
        # quit would leave its ffmpeg to die at logoff mid-encode.
        deadline = time.time() + 300
        while _TRIM_BUSY[0] > 0 and time.time() < deadline:
            time.sleep(0.2)
        _UI_QUIT.set()          # every save is flushed; the popups may rest now
        try:
            # read the window at destroy time, not call time: a quit clicked
            # in the boot gap (tray is up before the window exists) must still
            # close the tome once it appears.
            target = api._win if api is not None else win
            if target is not None:
                target.destroy()
        except Exception:
            pass
    threading.Thread(target=work, daemon=True).start()


_WATCH_THREAD = {"t": None}


# ---------------------------------------------------------------------------
#  Tray - LORE's quiet presence when the tome is closed. Same controls the
#  old shell offered; the tome opens on double-click.
# ---------------------------------------------------------------------------
def _start_tray(ctl, api, show_cb):
    try:
        import pystray
        from pystray import MenuItem as Item, Menu
    except Exception as e:
        log(f"Tray libraries unavailable ({e}); running without a tray icon.")
        return None

    idle_img, rec_img = _make_tray_images()
    ctl.icon_idle, ctl.icon_rec = idle_img, (rec_img or idle_img)

    recording = lambda *_: ctl.status == "recording"
    has_rec = lambda *_: ctl.status in ("recording", "paused")
    not_recording = lambda *_: ctl.status not in ("recording", "paused")

    def toggle_label(*_):
        if not ctl.watching.is_set():
            return "Continue recording"
        return "Pause recording" if ctl.status == "recording" else "Pause watching"

    def on_open(icon=None, item=None):
        show_cb()

    def on_start(icon=None, item=None):
        ctl.click_feedback("on", "starting", secs=12.0)
        ctl.watching.set()
        ctl.force_record.set()

    def on_stop(icon=None, item=None):
        ctl.click_feedback("off", "watching")
        ctl.stop_now.set()

    def on_toggle(icon=None, item=None):
        api.pause_toggle()

    def on_folder(icon=None, item=None):
        api.open_folder("recordings")

    def on_quit(icon=None, item=None):
        _request_quit(ctl, api, api._win)

    clip_menu = Menu(
        Item("Last 15 seconds", lambda i, it: _trigger_replay(ctl, 15)),
        Item("Last 30 seconds", lambda i, it: _trigger_replay(ctl, 30)),
        Item("Last 60 seconds", lambda i, it: _trigger_replay(ctl, 60)),
        Item(lambda *_: f"Last {SETTINGS.get('clip_hotkey_seconds', 60)}s (default)",
             lambda i, it: _trigger_replay(ctl)),
    )
    menu = Menu(
        Item(lambda *_: f"LORE - {ctl.status}", None, enabled=False),
        Menu.SEPARATOR,
        Item("Start recording", on_start, enabled=not_recording),
        Item(toggle_label, on_toggle, enabled=has_rec),
        Item("Stop & save recording", on_stop, enabled=has_rec),
        Menu.SEPARATOR,
        Item("Save a clip", clip_menu, enabled=recording),
        Item("Open recordings folder", on_folder),
        Item("Open the tome", on_open, default=True),
        Menu.SEPARATOR,
        Item("Quit LORE", on_quit),
    )
    icon = pystray.Icon("LORE", icon=idle_img, title="LORE - starting", menu=menu)
    ctl.icon = icon
    _TRAY_ICON[0] = icon
    try:
        icon.run_detached()
    except Exception:
        threading.Thread(target=icon.run, daemon=True).start()
    return icon


# ---------------------------------------------------------------------------
#  The tome window
# ---------------------------------------------------------------------------
def _ui_html_path():
    """ui.html lives next to lore.py in dev, inside the bundle when frozen."""
    for base in (_here(), getattr(sys, "_MEIPASS", None)):
        if base:
            p = os.path.join(base, "ui.html")
            if os.path.isfile(p):
                return p
    return None


def _work_area_size():
    """Primary work area in LOGICAL pixels (what pywebview sizes windows in).
    SPI_GETWORKAREA answers in physical pixels because the process is
    DPI-aware, so divide by the system scale - clamping logical sizes against
    the physical area let the book grow ~25% past a 125%-scaled screen."""
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        w = h = None
        hwnd = _lore_hwnd()
        if hwnd:
            # The monitor the book is actually ON - clamping to the primary
            # locked resizing on any larger secondary screen.
            class _MI(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.DWORD),
                            ("rcMonitor", wintypes.RECT),
                            ("rcWork", wintypes.RECT),
                            ("dwFlags", wintypes.DWORD)]
            mon = u.MonitorFromWindow(hwnd, 2)      # MONITOR_DEFAULTTONEAREST
            mi = _MI()
            mi.cbSize = ctypes.sizeof(_MI)
            if mon and u.GetMonitorInfoW(mon, ctypes.byref(mi)):
                w = mi.rcWork.right - mi.rcWork.left
                h = mi.rcWork.bottom - mi.rcWork.top
        if w is None:
            r = wintypes.RECT()
            if u.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0):
                w, h = r.right - r.left, r.bottom - r.top
        if w is not None:
            try:
                scale = (u.GetDpiForWindow(hwnd) if hwnd
                         else u.GetDpiForSystem()) / 96.0
                if scale > 0:
                    w, h = int(w / scale), int(h / scale)
            except Exception:
                pass
            return w, h
    except Exception:
        pass
    return 1920, 1040


def _tome_window_size():
    """The book ALWAYS opens at the same size:
    16:9 and about nine inches of book - the user's explicit ask, replacing
    remembered sizes (the grip still resizes freely within a session)."""
    aw, ah = _work_area_size()
    w, h = 1152, 648                      # 16:9, a compact volume (his call)
    if w > aw:
        w = aw
        h = int(w * 9 / 16)
    if h > ah:
        h = ah
        w = int(h * 16 / 9)
    return w, h


# ---------------------------------------------------------------------------
#  The silhouette - SetWindowRgn shapes the top-level window to the book (and
#  its protruding bookmark ribbons), so everything outside the shape IS the
#  desktop: visible, clickable, real. Probed on this stack: WebView2 renders
#  cleanly inside a region and the cut-away is genuinely transparent (unlike
#  alpha/colorkey, which DirectComposition defeats). The tome's JS reports its
#  silhouette; Python turns it into a Win32 region in physical pixels.
# ---------------------------------------------------------------------------
_HWND = {"h": None}


def _paint_it_black():
    """Blacken every native surface that could flash before the tome paints.
    pywebview only sets WebView2's DefaultBackgroundColor AFTER CoreWebView2
    finishes initialising - the WinForms control face is WHITE until then,
    and a window shown from the tray on a busy PC wears that white for whole
    seconds. Setting the control's BackColor (and the form's) covers the
    pre-init face; DefaultBackgroundColor covers everything after."""
    try:
        import webview.platforms.winforms as _wf
        from System.Drawing import Color
        for form in list(getattr(_wf.BrowserView, "instances", {}).values()):
            try:
                form.BackColor = Color.FromArgb(36, 22, 16)   # #241610 leather, not black -> no black seam at the resize edge (still not white pre-init)
                for c in form.Controls:
                    try:
                        c.BackColor = Color.FromArgb(36, 22, 16)   # #241610 leather, matches the cover -> exposed resize strip is leather, not black
                    except Exception:
                        pass
            except Exception:
                pass
        return True
    except Exception:
        return False


def _drag_loop(live, h):
    """Follow the held mouse with the window (the tome's drag). Runs on its
    own thread at ~240Hz; everything is physical pixels so no DPI scaling is
    needed. Ends when the button lifts, then applies the edge snaps."""
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    moved = False
    try:
        pt0 = wintypes.POINT()
        u.GetCursorPos(ctypes.byref(pt0))
        rc = wintypes.RECT()
        u.GetWindowRect(h, ctypes.byref(rc))
        left, top = rc.left, rc.top
        while u.GetAsyncKeyState(0x01) & 0x8000:      # VK_LBUTTON held
            pt = wintypes.POINT()
            u.GetCursorPos(ctypes.byref(pt))
            dx, dy = pt.x - pt0.x, pt.y - pt0.y
            if not moved and abs(dx) < 3 and abs(dy) < 3:
                time.sleep(0.004)
                continue                               # a click, not (yet) a drag
            if not moved and u.IsZoomed(h):
                # Dragging a maximized book un-maximizes it first (like any
                # window) and re-grips it under the cursor proportionally.
                fx = (pt0.x - rc.left) / max(1, rc.right - rc.left)
                u.ShowWindow(h, 9)                     # SW_RESTORE
                u.GetWindowRect(h, ctypes.byref(rc))
                w = rc.right - rc.left
                left = int(pt0.x - fx * w)
                # NO max(0,...) clamp: virtual-desktop y is NEGATIVE on a monitor
                # arranged above the primary, and clamping to 0 teleported the
                # restored book a full screen below the cursor for the whole drag
                top = pt0.y - 18
            moved = True
            u.SetWindowPos(h, 0, left + dx, top + dy, 0, 0,
                           0x0001 | 0x0004 | 0x0010)   # NOSIZE|NOZORDER|NOACTIVATE
            time.sleep(0.004)
        if moved:
            _drag_snap(h)
    except Exception as e:
        log(f"drag ended oddly: {e}")
    finally:
        live[0] = False


def _drag_snap(h):
    """Hand-made Aero: released at the top edge = maximize; released hard
    against a side edge = that half of the screen."""
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32

    class _MI(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
    pt = wintypes.POINT()
    u.GetCursorPos(ctypes.byref(pt))
    mon = u.MonitorFromPoint(pt, 2)                    # MONITOR_DEFAULTTONEAREST
    mi = _MI()
    mi.cbSize = ctypes.sizeof(_MI)
    if not (mon and u.GetMonitorInfoW(mon, ctypes.byref(mi))):
        return
    wa = mi.rcWork
    if pt.y <= wa.top + 4:
        _fit_maximize_bounds()
        u.ShowWindow(h, 3)                             # SW_MAXIMIZE
    elif pt.x <= wa.left + 4:
        u.SetWindowPos(h, 0, wa.left, wa.top,
                       (wa.right - wa.left) // 2, wa.bottom - wa.top,
                       0x0004 | 0x0010)                # NOZORDER|NOACTIVATE
    elif pt.x >= wa.right - 5:
        w = (wa.right - wa.left) // 2
        u.SetWindowPos(h, 0, wa.right - w, wa.top, w, wa.bottom - wa.top,
                       0x0004 | 0x0010)


def _fit_maximize_bounds():
    """A borderless WinForms window maximizes over the TASKBAR by default (no
    caption = Windows doesn't clamp it to the work area), which would bury the
    centred Win11 icons under the book's apron. Pin the form's MaximizedBounds
    to the work area of the monitor the book is on - this governs the ▢
    button, the rim double-press AND Aero snap-to-top. Only ever called while
    the window is NOT maximized (then the setter just stores the rectangle).
    The rectangle is MONITOR-RELATIVE, not absolute: WinForms copies
    MaximizedBounds.X/Y straight into MINMAXINFO.ptMaxPosition, and Windows
    reads that as an offset from the origin of whichever monitor hosts the
    maximize. Absolute work-area coords doubled the offset on a second
    monitor and the maximized book sailed clean off the desktop - the
    primary's origin is (0,0), which is the only reason it ever looked
    correct there. Marshalled onto the GUI thread so the monitor is read and
    the rectangle stored right before the zoom, wherever the book sits."""
    try:
        h = _lore_hwnd()
        if not h:
            return False
        import webview.platforms.winforms as _wf
        from System import Action, IntPtr
        from System.Drawing import Rectangle
        from System.Windows.Forms import Screen
        for form in list(getattr(_wf.BrowserView, "instances", {}).values()):
            if hasattr(form, "MaximizedBounds"):
                def _pin(form=form):
                    # ptMaxPosition is an offset from the HOST monitor's
                    # origin, not a desktop coordinate - subtract the
                    # monitor's own corner or monitor 2 gets it twice.
                    scr = Screen.FromHandle(IntPtr(h))
                    wa, mon = scr.WorkingArea, scr.Bounds
                    form.MaximizedBounds = Rectangle(
                        wa.X - mon.X, wa.Y - mon.Y, wa.Width, wa.Height)
                act = Action(_pin)
                try:
                    if form.InvokeRequired:
                        form.Invoke(act)
                    else:
                        act()
                except Exception:
                    _pin()   # no handle yet - a plain store is still just a store
                return True
    except Exception:
        pass
    return False


_ENUM_PROC = None      # keep the callback alive for the process lifetime


def _lore_hwnd():
    """The tome's top-level HWND - found by title AND OWNING PID, so a
    foreign window that happens to be called 'LORE' can never be shaped,
    dragged or maximized by mistake."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        h = _HWND.get("h")
        if h and u.IsWindow(h):
            return h
        me = os.getpid()
        found = []
        global _ENUM_PROC
        if _ENUM_PROC is None:
            _ENUM_PROC = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HWND,
                                            wintypes.LPARAM)

        def _cb(hw, _):
            try:
                pid = wintypes.DWORD()
                u.GetWindowThreadProcessId(hw, ctypes.byref(pid))
                if pid.value == me:
                    buf = ctypes.create_unicode_buffer(16)
                    u.GetWindowTextW(hw, buf, 16)
                    if buf.value == "LORE":
                        found.append(hw)
                        return 0
            except Exception:
                pass
            return 1
        u.EnumWindows(_ENUM_PROC(_cb), 0)
        h = found[0] if found else None
        _HWND["h"] = h
        return h
    except Exception:
        return None


def _round_window_corners(title=None):
    """Ask DWM for native rounded corners on the frameless window (Windows 11;
    silently a no-op on Windows 10). This is what keeps the book from having
    hard black corner pixels - the OS clips and anti-aliases the window
    itself, shadow included. Resolves OUR window via the pid-checked
    _lore_hwnd - a title-only FindWindow could round some other window
    named 'Lore' (an Explorer folder, say) and leave the tome square."""
    if os.name != "nt":
        return
    try:
        import ctypes
        hwnd = _lore_hwnd()
        if hwnd:
            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            DWMWCP_ROUND = 2
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(ctypes.c_int(DWMWCP_ROUND)), 4)
    except Exception:
        pass


def lore_app(show_window=True):
    """The whole app: singleton gate, watcher, hotkeys, tray, popups, and one
    frameless window holding the tome. Closing the window rests it in the
    tray; the recorder keeps watching.

    ORDER MATTERS: the RECORDER comes up first and the window last, so a slow
    or broken GUI (WebView2 hiccup, missing ui.html, sluggish first boot under
    a running game) can never delay or cost a recording. The breadcrumb log
    lines exist because a heavily-loaded PC can take minutes over the encoder
    probes - without them a slow start is indistinguishable from a hang."""
    if not _hold_singleton_mutex() or not _claim_lock():
        _signal_show()   # another copy is running: ask it to open its tome
        return
    load_settings()
    _hide_console()
    log(f"LORE v{APP_VERSION} is waking; the recorder starts first, "
        "then the tome opens.")

    # An unpainted WebView2 is WHITE by default - on a slow boot that was a
    # white flash before the book appeared. The runtime honours this env var
    # for its default background; with it, "not painted yet" is just black
    # inside the (black-brushed) window and the reveal stays invisible.
    os.environ.setdefault("WEBVIEW2_DEFAULT_BACKGROUND_COLOR", "FF241610")

    ctl = _Ctl()
    api = _JsApi(ctl)
    # --hidden starts tray-only; set the flag NOW, before the pump and tray
    # exist. show_tome flips it True on a tray-open, and nothing may ever
    # demote it back - a click landing in the boot gap must still count.
    api._reveal_ok = show_window
    _start_media_server()

    _show_pending = [False]   # an open request that beat the window's creation

    def show_tome():
        try:
            api._reveal_ok = True
            if api._win is None:
                # tray click / second launch landed in the boot gap - the
                # window isn't built yet, so remember the ask instead of
                # dropping it (first_paint reveals once the tome is up)
                _show_pending[0] = True
                return
            if api._win is not None:
                _paint_it_black()      # no white face, even pre-init
                # Arm the wake veil BEFORE the window is visible: tomeWake sets
                # a full-opacity leather overlay synchronously (no frame ticks
                # needed while hidden), so the first visible frame is calm
                # leather that then fades into the book - the tray-open no
                # longer POPS. Quick and bounded: one try, then show regardless
                # (the retry thread below still wakes a slow-booting browser).
                woke = False
                try:
                    api._win.evaluate_js("window.tomeWake&&tomeWake()")
                    woke = True
                except Exception:
                    pass
                api._win.show()
                # Only un-MINIMIZE. A blanket restore() also un-maximized a
                # maximized tome every time it came back from the tray (or
                # when the exe was double-launched while already open).
                try:
                    import ctypes
                    h = _lore_hwnd()
                    if h and ctypes.windll.user32.IsIconic(h):
                        api._win.restore()
                    elif h:
                        ctypes.windll.user32.SetForegroundWindow(h)
                except Exception:
                    pass
                # If the pre-show wake failed (hidden autostart: the browser may
                # still be initialising and evaluate_js raises), retry on a
                # thread so the geometry-reconcile inside tomeWake still runs.
                if not woke:
                    w = api._win

                    def _wake():
                        for _ in range(20):
                            try:
                                w.evaluate_js("window.tomeWake&&tomeWake()")
                                return
                            except Exception:
                                time.sleep(0.5)
                    threading.Thread(target=_wake, daemon=True).start()
        except Exception:
            pass

    _start_ui_pump(ctl, show_tome)

    t = threading.Thread(target=_watch_core, args=(ctl,), daemon=True)
    _WATCH_THREAD["t"] = t
    t.start()

    def _hotkey_service():
        # Register the current combos; when the user inscribes new ones,
        # set_settings bumps _HK_GEN, the listener returns (unregistering),
        # and this loop registers the fresh set - no restart needed.
        while not ctl.quit.is_set():
            gen = _HK_GEN[0]
            actions = [
                (SETTINGS.get("hotkey_record", ""), lambda: api.record_toggle()),
                (SETTINGS.get("hotkey_replay", ""), lambda: _trigger_replay(ctl)),
                (SETTINGS.get("hotkey_clip_discord", ""),
                 lambda: _trigger_replay(ctl, force_discord=True)),
                (SETTINGS.get("hotkey_pause", ""), lambda: api.pause_toggle()),
            ]
            _hotkey_listener(ctl, actions,
                             stop_when=lambda: _HK_GEN[0] != gen)
            # The listener only returns early when the combos changed - or when
            # nothing could be registered (all blank / owned by another app).
            # In the second case idle here until the user inscribes new ones,
            # so we never hammer RegisterHotKey or repeat the conflict warning.
            while not ctl.quit.is_set() and _HK_GEN[0] == gen:
                time.sleep(0.5)
            time.sleep(0.1)
    threading.Thread(target=_hotkey_service, daemon=True).start()

    icon = _start_tray(ctl, api, show_tome)

    def _headless_vigil():
        """No window, but the watch continues - recording, hotkeys, popups
        and the tray all live without the tome."""
        try:
            while not ctl.quit.is_set():
                time.sleep(0.5)
        except KeyboardInterrupt:
            ctl.quit.set()

    try:
        import webview
    except Exception as e:
        log(f"WebView unavailable ({e}); LORE keeps watching from the tray.")
        webview = None

    html = _ui_html_path()
    if webview is None or not html:
        if not html:
            log("ui.html is missing next to the app; LORE keeps watching from the tray.")
        _headless_vigil()
        try:
            if icon is not None:
                icon.stop()
        except Exception:
            pass
        try:
            t.join(timeout=600)
        except Exception:
            pass
        _UI_QUIT.set()
        _release_lock()
        return

    if _QUIT_STATE["requested"]:
        # Quit was chosen from the tray during the boot gap - don't open a
        # window that would linger dead over the desktop.
        try:
            t.join(timeout=600)
        except Exception:
            pass
        _UI_QUIT.set()
        try:
            if icon is not None:
                icon.stop()   # or the dead icon haunts the tray and its thread outlives the quit
        except Exception:
            pass
        _release_lock()
        return

    w, h = _tome_window_size()
    api._reveal_ok = show_window or _show_pending[0]
    window = webview.create_window(
        "LORE", url=html, js_api=api,
        width=w, height=h, min_size=(860, 645),
        frameless=True, easy_drag=False,
        # LEATHER pre-paint background: the intro card IS textured leather, so the
        # first frame before HTML paints must be that same leather - otherwise the
        # start staged dark-brown -> light-brown -> leather. Now it reads as leather
        # immediately, and the textured cover + logo paint on top.
        background_color="#241610",
        # EVERY launch begins hidden: the tome shows itself via first_paint()
        # only once the leather/walnut JPEGs have decoded and two frames have
        # rendered - so the first visible frame is the finished cover, never
        # the flat-brown pre-paint colour. The JS side carries a ~4s hard
        # ceiling and calls first_paint even on error, and the 20s
        # _reveal_watchdog below still rescues a tome whose JS died outright -
        # nobody gets stranded in the tray.
        hidden=True,
        text_select=False,
    )
    api._win = window

    if show_window:
        def _reveal_watchdog():
            # Only rescues a tome whose JS never reached first_paint (broken
            # WebView2, script error). Once the window has shown - or the
            # user already sent it to the tray - it must never fire. Twenty
            # seconds, not six: a gaming-loaded PC can take that long to
            # spin WebView2 up, and revealing early = an unpainted window.
            time.sleep(20.0)
            try:
                if (api._reveal_ok and not api._settled
                        and api._win is not None):
                    api._win.show()
            except Exception:
                pass
        threading.Thread(target=_reveal_watchdog, daemon=True).start()

    def on_closing():
        # X rests the tome in the tray - unless a real quit is in flight.
        if _QUIT_STATE["requested"]:
            return True
        api.hide()
        return False
    try:
        window.events.closing += on_closing
    except Exception:
        pass

    log("Recorder is up; opening the tome window…")

    def _after_gui_up():
        # Runs once the GUI loop owns the form: blacken the native faces so
        # nothing can flash white before (or between) the tome's paints, and
        # give the full-window book its native rounded corners.
        for _ in range(50):
            if _paint_it_black():
                break
            time.sleep(0.1)
        # The native HWND arrives a beat after the form exists - wait for it,
        # or the corner-rounding and size enforcement silently miss.
        for _ in range(100):
            if _lore_hwnd():
                break
            time.sleep(0.1)
        _round_window_corners()
        # Enforce the boot geometry EXACTLY (pywebview's frameless sizing
        # lands a few px off): a true 4:3 book, every launch the same.
        try:
            import ctypes
            h = _lore_hwnd()
            if h:
                u = ctypes.windll.user32
                scale = (u.GetDpiForWindow(h) or 96) / 96.0
                lw, lh = _tome_window_size()
                u.SetWindowPos(h, 0, 0, 0, int(lw * scale), int(lh * scale),
                               0x0002 | 0x0004 | 0x0010)  # NOMOVE|NOZORDER|NOACTIVATE
        except Exception:
            pass
    try:
        webview.start(_after_gui_up, gui="edgechromium", debug=False)
    except Exception as e:
        log(f"The tome could not open ({e}); LORE keeps watching from the tray.")
        _headless_vigil()
    finally:
        ctl.quit.set()
        try:
            if icon is not None:
                icon.stop()
        except Exception:
            pass
        try:
            t.join(timeout=600)   # never drop an in-progress save on quit
        except Exception:
            pass
        _UI_QUIT.set()            # saves flushed - the popup pump may close
        _stop_media_server()
        _release_lock()



def _hide_console():
    """Hide our own console window. No-op in the windowed build (no console)."""
    if os.name == "nt":
        try:
            import ctypes
            wnd = ctypes.windll.kernel32.GetConsoleWindow()
            if wnd:
                ctypes.windll.user32.ShowWindow(wnd, 0)  # SW_HIDE
        except Exception:
            pass


def _alloc_console():
    """Summon a console window on demand (the windowed exe has none by
    default). Used only by debug commands like --detect/--test/--console so
    their text output is visible. Normal/tray launches never call this."""
    if os.name != "nt":
        return
    try:
        import ctypes
        k = ctypes.windll.kernel32
        if not k.AttachConsole(-1):     # attach to launching cmd if any...
            k.AllocConsole()            # ...otherwise open a fresh console
        sys.stdout = open("CONOUT$", "w", buffering=1)
        sys.stderr = open("CONOUT$", "w", buffering=1)
        try:
            sys.stdin = open("CONIN$", "r")
        except Exception:
            pass
        try:
            k.SetConsoleTitleW("LORE")
        except Exception:
            pass
    except Exception:
        pass


def _pause_console():
    try:
        input("\nPress Enter to close...")
    except Exception:
        pass


def main():
    # The named mutex (installer-detection + atomic singleton gate) is acquired by
    # the long-running recorder modes (lore_app / watch_loop), not the transient
    # diagnostic commands - so a quick --detect can't block the recorder.
    ap = argparse.ArgumentParser(description="Auto-record games (WASAPI audio).")
    ap.add_argument("--settings", action="store_true", help="Open settings window.")
    ap.add_argument("--diag-audio", action="store_true", help="List WASAPI audio devices.")
    ap.add_argument("--detect", action="store_true", help="Show detected GPU + chosen encoder.")
    ap.add_argument("--test", type=int, metavar="SECONDS", help="Record a test clip now.")
    ap.add_argument("--print-cmd", action="store_true", help="Print the video ffmpeg command.")
    ap.add_argument("--hdr-probe", action="store_true", help="Diagnose HDR capture on this PC.")
    ap.add_argument("--hidden", action="store_true", help="Start the tray app with no window (autostart).")
    ap.add_argument("--console", action="store_true", help="Run the watcher in a console (no tray).")
    args = ap.parse_args()

    if args.settings:
        lore_app(show_window=True)
    elif args.diag_audio:
        _alloc_console()
        diag_audio()
    elif args.detect:
        _alloc_console()
        load_settings()
        enc = resolve_encoder()
        print(f"\nChosen encoder: {enc}")
        print("If this says libx264/libx265, no GPU encoder worked and it will "
              "use the CPU (slower). Send me this output.")
        _pause_console()
    elif args.test is not None:
        _alloc_console()
        test_clip(args.test)
        _pause_console()
    elif args.print_cmd:
        _alloc_console()
        load_settings()
        resolve_encoder()
        print(" ".join(f'"{c}"' if " " in c else c
                        for c in build_video_cmd(os.path.join(SETTINGS["output_dir"], "video.mp4"))))
        _pause_console()
    elif args.hdr_probe:
        _alloc_console()
        hdr_probe()
        _pause_console()
    elif args.console:
        _alloc_console()
        watch_loop()
    elif args.hidden:
        lore_app(show_window=False)
    else:
        lore_app(show_window=True)


if __name__ == "__main__":
    main()
