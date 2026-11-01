"""Runs in its own Python (set up by natural.py), never inside Anki.

Loads the Kokoro neural voice once, then reads JSON commands on stdin:
  {"cmd": "speak", "id": 3, "text": "...", "voice": "af_heart", "speed": 1.0, "volume": 0.9,
   "device": "MacBook Air Speakers"}
  {"cmd": "stop"}
and answers with JSON events on stdout: ready, started, done, error.

Text is split into sentences; the next sentence is made while the current
one plays, so long backs start talking right away.
"""

import json
import os
import queue
import re
import sys
import threading
import traceback

import numpy as np

_out_lock = threading.Lock()


def emit(**event):
    with _out_lock:
        sys.stdout.write(json.dumps(event) + "\n")
        sys.stdout.flush()


def split_sentences(text):
    parts = re.split(r"(?<=[.!?;:])\s+", text.strip())
    out = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # keep very short bits with their neighbour so the voice doesn't stutter
        if out and (len(part) < 12 or len(out[-1]) < 12):
            out[-1] += " " + part
        else:
            out.append(part)
    return out


WORD_RE = re.compile(r"([^\W\d_][^\W\d_']*(?:'[^\W\d_]+)*)")
LEXICON = {}


def load_lexicon():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lexicon.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return
    LEXICON.update({k.lower(): v for k, v in data.items() if not k.startswith("_")})
    extra = os.environ.get("CARD_READ_ALOUD_LEXICON")
    if extra and os.path.exists(extra):
        try:
            with open(extra, encoding="utf-8") as f:
                LEXICON.update({k.lower(): v for k, v in json.load(f).items() if v})
        except (OSError, ValueError):
            pass


def lookup(word):
    w = word.lower()
    if not w or not w[0].isalpha():
        return None
    if w in LEXICON:
        return LEXICON[w]
    # plurals: kinases, carboxylases, cephalosporins...
    if w.endswith("es") and w[:-1] in LEXICON and w[:-1].endswith(("se", "ce", "ze")):
        return LEXICON[w[:-1]] + "ᵻz"
    if w.endswith("s") and w[:-1] in LEXICON:
        base = LEXICON[w[:-1]]
        return base + ("s" if base[-1:] in "ptkfθ" else "z")
    return None


# Letter names for spelled abbreviations ("D N A", "C E A"). eSpeak reads a
# lone "A" in the middle of a sentence as the word "a", so we say them here.
LETTER_IPA = {
    "A": "eɪ", "B": "biː", "C": "siː", "D": "diː", "E": "iː", "F": "ɛf",
    "G": "dʒiː", "H": "eɪtʃ", "I": "aɪ", "J": "dʒeɪ", "K": "keɪ", "L": "ɛl",
    "M": "ɛm", "N": "ɛn", "O": "oʊ", "P": "piː", "Q": "kjuː", "R": "ɑːɹ",
    "S": "ɛs", "T": "tiː", "U": "juː", "V": "viː", "W": "dʌbəljuː", "X": "ɛks",
    "Y": "waɪ", "Z": "ziː",
}
# runs of two or more capital letters ("D N A"), or a capital A after a word
# ("vitamin A", "group A strep"); a sentence-initial "A" stays the article
LETTERS_RE = re.compile(r"(?<![\w'])[A-Z](?:\u00a0[A-Z])+s?(?![\w'])|(?<=[\w,)] )A(?![\w'])")


def _stress(ipa, mark):
    m = re.search(r"[aeiouæɑɐɔəɚɛɜɪʊʌᵻ]", ipa)
    return ipa[:m.start()] + mark + ipa[m.start():] if m else mark + ipa


def spell(letters):
    # "U\u00a0T\u00a0Is" (UTIs) ends with a plural s
    plural = letters.endswith("s")
    names = [LETTER_IPA[c] for c in letters.rstrip("s").split("\u00a0")]
    out = " ".join([_stress(n, "ˌ") for n in names[:-1]] + [_stress(names[-1], "ˈ")])
    return out + ("z" if plural else "")


# Combining forms. Joined words like "neoantigen" or "oncofetal" are read in
# their parts ("neo antigen"), which is how they're said. Without this eSpeak
# guesses from the spelling and runs the parts together ("nee-oh-AN-tie-gen").
PREFIXES = {
    "neo": "nˌiːoʊ", "onco": "ˌɑːŋkoʊ", "auto": "ˌɔːɾoʊ", "allo": "ˌæloʊ",
    "iso": "ˌaɪsoʊ", "pro": "pɹˌoʊ", "pre": "pɹˌiː", "post": "pˌoʊst",
    "re": "ɹˌiː", "co": "kˌoʊ", "anti": "ˌænti", "pseudo": "sˌuːdoʊ",
    "hyper": "hˌaɪpɚ", "hypo": "hˌaɪpoʊ", "intra": "ˌɪntɹə", "inter": "ˌɪntɚ",
    "micro": "mˌaɪkɹoʊ", "macro": "mˌækɹoʊ", "endo": "ˌɛndoʊ", "exo": "ˌɛksoʊ",
    "epi": "ˌɛpɪ", "peri": "pˌɛɹi", "para": "pˌæɹə", "super": "sˌuːpɚ",
    "sub": "sˌʌb", "non": "nˌɑːn", "poly": "pˌɑːli", "oligo": "ˌɑːlɪɡoʊ",
    "pan": "pˌæn", "thrombo": "θɹˌɑːmboʊ", "immuno": "ˌɪmjʊnoʊ",
    "cardio": "kˌɑːɹdioʊ", "hepato": "hˌɛpətoʊ", "spleno": "splˌiːnoʊ",
    "glomerulo": "ɡloʊmˌɛɹjʊloʊ", "nephro": "nˌɛfɹoʊ", "neuro": "nˌʊɹoʊ",
    "gastro": "ɡˌæstɹoʊ", "entero": "ˌɛntəɹoʊ", "osteo": "ˌɑːstioʊ",
    "myo": "mˌaɪoʊ", "hemo": "hˌiːmoʊ", "angio": "ˌændʒioʊ", "vaso": "vˌeɪzoʊ",
    "broncho": "bɹˌɑːŋkoʊ", "pneumo": "nˌuːmoʊ", "chemo": "kˌiːmoʊ",
    "radio": "ɹˌeɪdioʊ", "lympho": "lˌɪmfoʊ", "leuko": "lˌuːkoʊ",
    "erythro": "ɪɹˌɪθɹoʊ", "cyto": "sˌaɪɾoʊ", "histo": "hˌɪstoʊ",
    "patho": "pˌæθoʊ", "physio": "fˌɪzioʊ", "uro": "jˌʊɹoʊ", "dys": "dˌɪs",
    "mono": "mˌɑːnoʊ", "multi": "mˌʌlti", "semi": "sˌɛmi", "ultra": "ˌʌltɹə",
    "trans": "tɹˌænz", "retro": "ɹˌɛtɹoʊ", "extra": "ˌɛkstɹə", "infra": "ˌɪnfɹə",
    "supra": "sˌuːpɹə", "meta": "mˌɛɾə", "bio": "bˌaɪoʊ", "glyco": "ɡlˌaɪkoʊ",
    "lipo": "lˌɪpoʊ", "phospho": "fˌɑːsfoʊ", "pharmaco": "fˌɑːɹməkoʊ",
    "tachy": "tˌæki", "brady": "bɹˌædi", "hetero": "hˌɛɾəɹoʊ", "homo": "hˌoʊmoʊ",
    "xeno": "zˌɛnoʊ", "ortho": "ˌɔːɹθoʊ", "photo": "fˌoʊɾoʊ",
    "chondro": "kˌɑːndɹoʊ", "fibro": "fˌaɪbɹoʊ", "adeno": "ˌædənoʊ",
    "carcino": "kˌɑːɹsɪnoʊ", "hemi": "hˌɛmi", "dermato": "dˌɜːmətoʊ",
    "derm": "dˌɜːm", "cholangio": "koʊlˌændʒioʊ", "chole": "kˌoʊli",
    "pancreatico": "pˌæŋkɹiˌæɾɪkoʊ", "duodeno": "dˌuːədˌiːnoʊ",
    "thyro": "θˌaɪɹoʊ", "adreno": "ədɹˌiːnoʊ", "cortico": "kˌɔːɹɾɪkoʊ",
    "gluco": "ɡlˌuːkoʊ", "keto": "kˌiːɾoʊ", "mega": "mˌɛɡə", "pyelo": "pˌaɪəloʊ",
    "salpingo": "sælpˌɪŋɡoʊ", "oophoro": "oʊˌɑːfəɹoʊ", "hystero": "hˌɪstəɹoʊ",
    "encephalo": "ɛnsˌɛfəloʊ", "meningo": "mənˌɪŋɡoʊ", "myelo": "mˌaɪəloʊ",
    "arterio": "ɑːɹtˌɪɹioʊ", "athero": "ˌæθəɹoʊ", "veno": "vˌiːnoʊ",
    "lymphangio": "lɪmfˌændʒioʊ", "rhabdo": "ɹˌæbdoʊ", "leiomyo": "lˌaɪoʊmˌaɪoʊ",
    "hemato": "hˌiːmətoʊ", "sero": "sˌɪɹoʊ", "toxo": "tˌɑːksoʊ",
}
_PREFIX_ORDER = sorted(PREFIXES, key=len, reverse=True)
# endings that aren't words on their own but finish a joined word
# ("spleno" + "megaly", "angio" + "pathic")
ENDINGS = {
    "megaly": "mˈɛɡəli", "pathic": "pˈæθɪk", "genic": "dʒˈɛnɪk",
    "genesis": "dʒˈɛnəsɪs", "viridae": "vˈɪɹɪdiː",
}
VOWELS = "aeiouy"
COMMON = set()  # everyday words: never split ("present" is not pre + sent)
KNOWN = set()  # real words a part may be ("antigen", "fetal", "embolism")
_compound_cache = {}


def load_words():
    here = os.path.dirname(os.path.abspath(__file__))
    for name, target in (("words_common.txt", COMMON), ("words_known.txt", KNOWN)):
        try:
            with open(os.path.join(here, name), encoding="utf-8") as f:
                target.update(line.strip() for line in f if line.strip())
        except OSError:
            pass


def _is_part(word):
    return word in COMMON or word in KNOWN or word in ENDINGS or lookup(word) is not None


def _inflected_common(w):
    # "antigens" is "antigen" + s, not "anti" + "gens"
    for end, add in (("s", ""), ("es", ""), ("ed", ""), ("ed", "e"), ("ing", ""), ("ing", "e"), ("ly", ""), ("al", "")):
        if w.endswith(end) and (w[: -len(end)] + add) in COMMON:
            return True
    return False


def split_compound(word, depth=0):
    """'neoantigen' -> ['neo', 'antigen']; None if it isn't a joined word."""
    w = word.lower()
    if depth == 0 and (len(w) < 7 or w in COMMON or w in LEXICON or _inflected_common(w)):
        return None
    for p in _PREFIX_ORDER:
        rest = w[len(p):]
        if not w.startswith(p) or len(rest) < 5:
            continue
        # short prefixes only split before a vowel ("pre-eclampsia", "re-uptake"),
        # so "protease" and "prostatic" stay whole
        if len(p) <= 3 and rest[0] not in VOWELS and depth == 0:
            continue
        if _is_part(rest):
            return [p, rest]
        if depth < 2:
            more = split_compound(rest, depth + 1)
            if more:
                return [p] + more
    return None


def compound(word, phonemize):
    """IPA for a joined word, or None. phonemize(text) gives eSpeak's IPA."""
    w = word.lower()
    if w in _compound_cache:
        return _compound_cache[w]
    parts = split_compound(w)
    ipa = None
    if not parts and len(w) > 8 and w.endswith(("iasis", "iases")) and w not in COMMON:
        # candidiasis, cholelithiasis, schistosomiasis: "-EYE-a-sis"
        stem = phonemize(w[:-5]).strip().replace("ˈ", "ˌ")
        if stem:
            ipa = stem + ("ˈaɪəsɪs" if w.endswith("sis") else "ˈaɪəsiːz")
    elif not parts and len(w) > 9 and w.endswith("viridae") and w not in COMMON:
        # virus families: picornaviridae, "-VEER-ih-dee"
        stem = phonemize(w[:-7]).strip().replace("ˈ", "ˌ")
        if stem:
            ipa = stem + "vˈɪɹɪdiː"
    elif parts:
        *prefixes, last = parts
        tail = ENDINGS.get(last) or lookup(last) or phonemize(last).strip()
        if tail:
            ipa = "".join(PREFIXES[p] for p in prefixes) + tail
    _compound_cache[w] = ipa
    return ipa


class Speaker:
    def __init__(self, kokoro, player):
        self.kokoro = kokoro
        self.player = player
        self.generation = 0
        self.lock = threading.Lock()
        self.jobs = queue.Queue()
        self.chunks = queue.Queue(maxsize=3)
        threading.Thread(target=self._synth_loop, daemon=True).start()
        threading.Thread(target=self._play_loop, daemon=True).start()

    def style(self, spec):
        """'af_heart' or a blend like 'af_heart:0.6+af_nicole:0.4'."""
        total = None
        weight_sum = 0.0
        for piece in str(spec or "af_heart").split("+"):
            name, _, weight = piece.strip().partition(":")
            w = float(weight) if weight else 1.0
            vec = self.kokoro.get_voice_style(name.strip()) * w
            total = vec if total is None else total + vec
            weight_sum += w
        return total / (weight_sum or 1.0)

    def phonemize(self, text, lang):
        """Phonemes for a sentence, using our lexicon for words the
        pronunciation rules get wrong (drug, bug and enzyme names)."""
        pieces = []
        plain = []

        def flush():
            chunk = "".join(plain).replace("\u00a0", " ").strip()
            plain.clear()
            if chunk:
                ph = self.kokoro.tokenizer.phonemize(chunk, lang)
                if ph.strip():
                    pieces.append(ph.strip())

        def espeak(word):
            return self.kokoro.tokenizer.phonemize(word, lang)

        def words(segment):
            for token in WORD_RE.split(segment):
                ipa = lookup(token)
                if not ipa and token[:1].isalpha():
                    ipa = compound(token, espeak)
                if ipa:
                    flush()
                    pieces.append(ipa)
                else:
                    plain.append(token)

        pos = 0
        for m in LETTERS_RE.finditer(text):
            words(text[pos:m.start()])
            flush()
            pieces.append(spell(m.group(0)))
            pos = m.end()
        words(text[pos:])
        flush()
        out = " ".join(pieces)
        return re.sub(r"\s+([,.;:!?])", r"\1", out)

    @staticmethod
    def lang_for(spec):
        first = str(spec or "a").strip()[:1].lower()
        return "en-gb" if first == "b" else "en-us"

    def speak(self, job):
        with self.lock:
            gen = self.generation
        self.jobs.put((gen, job))

    def stop(self):
        with self.lock:
            self.generation += 1
        self._drain(self.jobs)
        self._drain(self.chunks)
        self.player.stop()

    @staticmethod
    def _drain(q):
        try:
            while True:
                q.get_nowait()
        except queue.Empty:
            pass

    def _current(self, gen):
        with self.lock:
            return gen == self.generation

    def _synth_loop(self):
        while True:
            gen, job = self.jobs.get()
            if not self._current(gen):
                continue
            job_id = job.get("id")
            try:
                voice = job.get("voice") or "af_heart"
                style = self.style(voice)
                lang = self.lang_for(voice)
                speed = min(2.0, max(0.5, float(job.get("speed", 1.0))))
                volume = min(1.0, max(0.05, float(job.get("volume", 1.0))))
                first = True
                for sentence in split_sentences(job.get("text") or ""):
                    if not self._current(gen):
                        break
                    phonemes = self.phonemize(sentence, lang)
                    if not phonemes.strip():
                        continue
                    audio, rate = self.kokoro.create(
                        phonemes, voice=style, speed=speed, lang=lang, is_phonemes=True
                    )
                    audio = np.asarray(audio, dtype=np.float32) * volume
                    self._put(gen, ("audio", job_id, audio, rate, first, job.get("device")))
                    first = False
            except Exception as e:
                emit(event="error", id=job_id, message=f"{type(e).__name__}: {e}")
            self._put(gen, ("end", job_id, None, 0, False, None))

    def _put(self, gen, item):
        while self._current(gen):
            try:
                self.chunks.put((gen, item), timeout=0.1)
                return
            except queue.Full:
                continue

    def _play_loop(self):
        while True:
            gen, (kind, job_id, audio, rate, first, device) = self.chunks.get()
            if not self._current(gen):
                continue
            if kind == "end":
                emit(event="done", id=job_id)
                continue
            if first:
                emit(event="started", id=job_id)
            # short silence so sentences don't run together
            gap = np.zeros(int(rate * 0.12), dtype=np.float32)
            self.player.play(np.concatenate([audio, gap]), rate, lambda: self._current(gen), device)


class SoundDevicePlayer:
    def __init__(self):
        import sounddevice as sd

        self.sd = sd

    def _device(self, name):
        """The output device with this name, or None for the system default
        (also when it has been unplugged)."""
        if not name:
            return None
        try:
            for i, dev in enumerate(self.sd.query_devices()):
                if dev["name"] == name and dev["max_output_channels"] > 0:
                    return i
        except Exception:
            pass
        return None

    def play(self, audio, rate, still_wanted, device=None):
        try:
            self.sd.play(audio, rate, device=self._device(device))
        except Exception:
            # the chosen device can't play this; fall back to the default
            self.sd.play(audio, rate)
        if still_wanted():
            self.sd.wait()
        else:
            self.sd.stop()

    def stop(self):
        self.sd.stop()


class WavFilePlayer:
    """For testing without speakers: writes each sentence to a folder."""

    def __init__(self, folder):
        self.folder = folder
        self.n = 0

    def play(self, audio, rate, still_wanted, device=None):
        import wave

        self.n += 1
        pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
        with wave.open(os.path.join(self.folder, f"{self.n:03d}.wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(pcm.tobytes())

    def stop(self):
        pass


def espeak_config():
    """eSpeak (which turns words into sounds for Kokoro) can't open its data
    folder when the path has a space in it, and Anki's add-on folder on a Mac
    is under "Application Support". So we keep a copy at a path without one."""
    import shutil
    import tempfile

    import espeakng_loader
    from kokoro_onnx.config import EspeakConfig

    source = espeakng_loader.get_data_path()
    if " " not in source:
        return None
    stamp = f"{os.path.getsize(os.path.join(source, 'phontab'))}-{len(os.listdir(source))}"
    bases = [
        os.path.join(os.path.expanduser("~"), ".cache", "card_read_aloud"),
        os.path.join(tempfile.gettempdir(), "card_read_aloud"),
        "/tmp/card_read_aloud",
    ]
    for base in bases:
        if " " in base:
            continue
        target = os.path.join(base, "espeak-ng-data")
        marker = os.path.join(base, "espeak-ng-data.stamp")
        try:
            with open(marker, encoding="utf-8") as f:
                if f.read() == stamp and os.path.exists(os.path.join(target, "phontab")):
                    return EspeakConfig(data_path=target)
        except OSError:
            pass
        try:
            os.makedirs(base, exist_ok=True)
            tmp = target + f".tmp{os.getpid()}"
            shutil.rmtree(tmp, ignore_errors=True)
            shutil.copytree(source, tmp)
            shutil.rmtree(target, ignore_errors=True)
            os.replace(tmp, target)
            with open(marker, "w", encoding="utf-8") as f:
                f.write(stamp)
            return EspeakConfig(data_path=target)
        except OSError as e:
            print(f"couldn't copy espeak data to {base}: {e}", file=sys.stderr)
    raise RuntimeError("no folder without spaces for the pronunciation data")


def main():
    model_path, voices_path = sys.argv[1], sys.argv[2]
    try:
        from kokoro_onnx import Kokoro

        kokoro = Kokoro(model_path, voices_path, espeak_config=espeak_config())
        wav_dir = os.environ.get("CARD_READ_ALOUD_WAV_DIR")
        player = WavFilePlayer(wav_dir) if wav_dir else SoundDevicePlayer()
        # first inference is slow, so do it before anyone is waiting
        kokoro.create("Ready.", voice=kokoro.get_voice_style("af_heart"), speed=1.0, lang="en-us")
    except Exception:
        emit(event="fatal", message=traceback.format_exc())
        return 1
    load_lexicon()
    load_words()
    speaker = Speaker(kokoro, player)
    emit(event="ready", voices=sorted(kokoro.get_voices()))
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        cmd = msg.get("cmd")
        if cmd == "speak":
            speaker.stop()
            speaker.speak(msg)
        elif cmd == "stop":
            speaker.stop()
        elif cmd == "quit":
            break
    speaker.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
