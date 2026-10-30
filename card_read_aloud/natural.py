"""The natural voice: Kokoro, an open-source neural text-to-speech model.

Kokoro needs numpy and onnxruntime, which Anki's own Python doesn't have, so
we give it a private Python of its own under user_files/natural_voice/ (made
with uv, the installer Anki itself uses) and talk to it over a pipe. Nothing
here touches Anki's Python or the rest of the computer; deleting that folder
removes it all.
"""

import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import traceback
import zipfile

from aqt import mw

ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
HELPER = os.path.join(ADDON_DIR, "natural_voice", "kokoro_helper.py")
DATA_DIR = os.path.join(ADDON_DIR, "user_files", "natural_voice")
ENV_DIR = os.path.join(DATA_DIR, "env")
MODEL_DIR = os.path.join(DATA_DIR, "model")
LOG_PATH = os.path.join(DATA_DIR, "log.txt")
MARKER = os.path.join(DATA_DIR, "installed.json")

PYTHON_VERSION = "3.12"
PACKAGES = ["kokoro-onnx==0.6.1", "sounddevice>=0.5"]
RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
MIRROR = "https://huggingface.co/fastrtc/kokoro-onnx/resolve/main/"
MODEL_FILES = [
    # (file, urls, smallest believable size)
    ("kokoro-v1.0.onnx", [RELEASE + "kokoro-v1.0.onnx", MIRROR + "kokoro-v1.0.onnx"], 200_000_000),
    ("voices-v1.0.bin", [RELEASE + "voices-v1.0.bin", MIRROR + "voices-v1.0.bin"], 10_000_000),
]
DOWNLOAD_SIZE_TEXT = "about 500 MB"

# Gentle-sounding picks first. A "+" blends two voices.
VOICES = [
    ("af_heart", "Heart: warm and natural (US)"),
    ("af_heart:0.6+af_nicole:0.4", "Heart + Nicole: extra gentle (US)"),
    ("af_nicole", "Nicole: soft, almost a whisper (US)"),
    ("af_bella", "Bella: bright and friendly (US)"),
    ("af_sarah", "Sarah: calm (US)"),
    ("af_aoede", "Aoede: light (US)"),
    ("bf_emma", "Emma: gentle (UK)"),
    ("bf_isabella", "Isabella: clear (UK)"),
    ("am_michael", "Michael: calm male (US)"),
    ("am_fenrir", "Fenrir: deeper male (US)"),
    ("bm_george", "George: male (UK)"),
    ("bm_fable", "Fable: storyteller male (UK)"),
]


def log(msg):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg.rstrip() + "\n")
    except Exception:
        pass


def env_python():
    if sys.platform == "win32":
        return os.path.join(ENV_DIR, "Scripts", "python.exe")
    return os.path.join(ENV_DIR, "bin", "python")


def is_installed():
    return os.path.exists(MARKER) and os.path.exists(env_python()) and all(
        os.path.exists(os.path.join(MODEL_DIR, name)) for name, _, _ in MODEL_FILES
    )


def _use_data_dir(path):
    global DATA_DIR, ENV_DIR, MODEL_DIR, LOG_PATH, MARKER
    DATA_DIR = path
    ENV_DIR = os.path.join(DATA_DIR, "env")
    MODEL_DIR = os.path.join(DATA_DIR, "model")
    LOG_PATH = os.path.join(DATA_DIR, "log.txt")
    MARKER = os.path.join(DATA_DIR, "installed.json")


def _borrow_voice():
    """If this copy of the add-on has no voice yet but another copy does (one
    from AnkiWeb and one installed from a file), use that one instead of
    downloading 500 MB again. Nothing is moved, so both copies keep working."""
    if is_installed():
        return
    own = DATA_DIR
    parent = os.path.dirname(ADDON_DIR)
    try:
        siblings = sorted(os.listdir(parent))
    except OSError:
        return
    for name in siblings:
        other = os.path.join(parent, name)
        if other == ADDON_DIR or not os.path.exists(os.path.join(other, "natural_voice", "kokoro_helper.py")):
            continue
        _use_data_dir(os.path.join(other, "user_files", "natural_voice"))
        if is_installed():
            return
    _use_data_dir(own)


def _clean_env():
    env = dict(os.environ)
    for key in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "PYTHONSTARTUP", "UV_PROJECT_ENVIRONMENT"):
        env.pop(key, None)
    env["UV_CACHE_DIR"] = os.path.join(DATA_DIR, "uv-cache")
    env["UV_PYTHON_INSTALL_DIR"] = os.path.join(DATA_DIR, "python")
    env["PYTHONIOENCODING"] = "utf-8"
    return env


# ---------------------------------------------------------------- install

class Install:
    """One background install; the settings window watches it."""

    def __init__(self):
        self.running = False
        self.status = ""
        self.error = None
        self.listeners = []
        self.on_installed = None

    def _set(self, status):
        self.status = status
        log(status)
        for fn in list(self.listeners):
            mw.taskman.run_on_main(lambda fn=fn: fn())

    def start(self):
        if self.running:
            return
        self.running = True
        self.error = None
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            os.makedirs(MODEL_DIR, exist_ok=True)
            uv = self._find_uv()
            self._set("Setting up a private Python for the voice…")
            self._uv(uv, ["venv", "--allow-existing", "--python", PYTHON_VERSION, ENV_DIR])
            self._set("Installing the voice engine…")
            self._uv(uv, ["pip", "install", "--python", env_python(), *PACKAGES])
            for name, urls, min_size in MODEL_FILES:
                self._download_any(name, urls, min_size)
            with open(MARKER, "w", encoding="utf-8") as f:
                json.dump({"packages": PACKAGES, "python": PYTHON_VERSION, "time": time.time()}, f)
            self._set("Natural voice installed.")
            if self.on_installed:
                mw.taskman.run_on_main(self.on_installed)
        except Exception as e:
            self.error = str(e) or type(e).__name__
            log(traceback.format_exc())
            self._set(f"Install failed: {self.error}")
        finally:
            self.running = False
            self._set(self.status)

    def _uv(self, uv, args):
        proc = subprocess.run(
            [uv, *args], env=_clean_env(), capture_output=True, text=True, timeout=1800
        )
        log(f"uv {' '.join(args)}\n{proc.stdout[-4000:]}\n{proc.stderr[-4000:]}")
        if proc.returncode != 0:
            last = (proc.stderr or proc.stdout).strip().splitlines()
            raise RuntimeError(last[-1] if last else f"uv exited with {proc.returncode}")

    def _find_uv(self):
        own = os.path.join(DATA_DIR, "uv.exe" if sys.platform == "win32" else "uv")
        if os.path.exists(own):
            return own
        exe_dirs = [os.path.dirname(sys.executable)]
        launcher = os.environ.get("ANKI_LAUNCHER")
        if launcher:
            exe_dirs.insert(0, os.path.dirname(launcher))
        candidates = [os.path.join(d, "uv") for d in exe_dirs] + [
            "/Applications/Anki.app/Contents/MacOS/uv",
            os.path.expanduser("~/.local/bin/uv"),
            "/opt/homebrew/bin/uv",
            "/usr/local/bin/uv",
        ]
        found = shutil.which("uv")
        if found:
            candidates.append(found)
        for path in candidates:
            if path and os.path.isfile(path) and os.access(path, os.X_OK):
                log(f"using uv at {path}")
                return path
        self._set("Downloading the installer (uv)…")
        return self._download_uv(own)

    def _download_uv(self, dest):
        import requests

        machine = platform.machine().lower()
        arm = machine in ("arm64", "aarch64")
        if sys.platform == "darwin":
            tag = "macosx_11_0_arm64" if arm else "macosx_10_12_x86_64"
        elif sys.platform == "win32":
            tag = "win_arm64" if arm else "win_amd64"
        else:
            tag = "manylinux_2_17_aarch64" if arm else "manylinux_2_17_x86_64"
        info = requests.get("https://pypi.org/pypi/uv/json", timeout=30).json()
        wheel = next(
            (u for u in info["urls"] if u["filename"].endswith(".whl") and tag in u["filename"]),
            None,
        )
        if not wheel:
            raise RuntimeError(f"no uv download for this computer ({tag})")
        tmp = dest + ".whl"
        self._fetch(wheel["url"], tmp, "the installer")
        exe = "uv.exe" if sys.platform == "win32" else "uv"
        with zipfile.ZipFile(tmp) as z:
            member = next(n for n in z.namelist() if n.endswith("/scripts/" + exe))
            with z.open(member) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)
        os.remove(tmp)
        os.chmod(dest, 0o755)
        return dest

    def _download_any(self, name, urls, min_size):
        dest = os.path.join(MODEL_DIR, name)
        if os.path.exists(dest) and os.path.getsize(dest) >= min_size:
            return
        errors = []
        for url in urls:
            try:
                self._fetch(url, dest, name)
                if os.path.getsize(dest) < min_size:
                    raise RuntimeError("download was too small")
                return
            except Exception as e:
                errors.append(f"{url}: {e}")
                log(f"download failed {url}: {e}")
        raise RuntimeError(f"couldn't download {name}")

    def _fetch(self, url, dest, label):
        import requests

        part = dest + ".part"
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length") or 0)
            done = 0
            last = 0.0
            with open(part, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
                    done += len(chunk)
                    if time.time() - last > 0.5:
                        last = time.time()
                        pct = f" {done * 100 // total}%" if total else ""
                        self._set(f"Downloading {label}…{pct} ({done >> 20} MB)")
        os.replace(part, dest)


installer = Install()


def remove():
    stop_helper()
    shutil.rmtree(DATA_DIR, ignore_errors=True)


_borrow_voice()


# ---------------------------------------------------------------- the helper process

class Helper:
    def __init__(self):
        self.proc = None
        self.ready = False
        self.broken = None
        self.pending = None
        self.speaking = None
        self.next_id = 0
        self.on_failed = None

    def start(self):
        if self.proc and self.proc.poll() is None:
            return
        self.ready = False
        self.broken = None
        model = os.path.join(MODEL_DIR, MODEL_FILES[0][0])
        voices = os.path.join(MODEL_DIR, MODEL_FILES[1][0])
        os.makedirs(DATA_DIR, exist_ok=True)
        err = open(os.path.join(DATA_DIR, "helper_errors.txt"), "w", encoding="utf-8")
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = 0x08000000  # no console window
        self.proc = subprocess.Popen(
            [env_python(), "-I", HELPER, model, voices],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=err,
            env=_clean_env(),
            text=True,
            encoding="utf-8",
            bufsize=1,
            **kwargs,
        )
        log("helper started")
        threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()

    def _read(self, proc):
        for line in proc.stdout:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            mw.taskman.run_on_main(lambda e=event, p=proc: self._event(e, p))
        mw.taskman.run_on_main(lambda p=proc: self._exited(p))

    def _event(self, event, proc):
        if proc is not self.proc:
            return
        kind = event.get("event")
        if kind == "ready":
            self.ready = True
            log("helper ready")
            if self.pending:
                msg, self.pending = self.pending, None
                self._send(msg)
        elif kind == "started":
            pass
        elif kind == "done":
            if self.speaking == event.get("id"):
                self.speaking = None
        elif kind in ("error", "fatal"):
            log(f"helper {kind}: {event.get('message')}")
            if kind == "fatal":
                self._fail(event.get("message") or "the voice couldn't start")
            elif self.speaking == event.get("id"):
                self.speaking = None

    def _exited(self, proc):
        if proc is not self.proc:
            return
        code = proc.poll()
        log(f"helper exited ({code})")
        self.proc = None
        self.speaking = None
        if (not self.ready or self.pending) and not self.broken:
            detail = ""
            try:
                with open(os.path.join(DATA_DIR, "helper_errors.txt"), encoding="utf-8") as f:
                    lines = [l.strip() for l in f.read().splitlines() if l.strip()]
                if lines:
                    detail = ": " + lines[-1][:300]
                    log("helper stderr:\n" + "\n".join(lines[-40:]))
            except OSError:
                pass
            self._fail(f"the voice stopped unexpectedly (code {code}){detail}")
        self.ready = False

    def _fail(self, reason):
        self.broken = reason.strip().splitlines()[-1] if reason.strip() else "unknown error"
        pending, self.pending = self.pending, None
        self.speaking = None
        if self.on_failed:
            self.on_failed(self.broken, pending["text"] if pending else None)

    def _send(self, msg):
        try:
            self.proc.stdin.write(json.dumps(msg) + "\n")
            self.proc.stdin.flush()
        except Exception as e:
            log(f"send failed: {e}")
            return False
        if msg.get("cmd") == "speak":
            self.speaking = msg["id"]
        return True

    def speak(self, text, voice, speed, volume):
        self.next_id += 1
        msg = {"cmd": "speak", "id": self.next_id, "text": text, "voice": voice,
               "speed": speed, "volume": volume}
        self.start()
        if self.ready:
            self._send(msg)
        else:
            self.pending = msg
            self.speaking = msg["id"]
        return self.next_id

    def stop(self):
        self.pending = None
        self.speaking = None
        if self.proc and self.proc.poll() is None and self.ready:
            self._send({"cmd": "stop"})

    def is_speaking(self):
        return self.speaking is not None

    def shutdown(self):
        proc, self.proc = self.proc, None
        self.ready = False
        if proc and proc.poll() is None:
            try:
                proc.stdin.write(json.dumps({"cmd": "quit"}) + "\n")
                proc.stdin.flush()
                proc.wait(timeout=2)
            except Exception:
                proc.kill()


helper = Helper()


def stop_helper():
    helper.shutdown()
