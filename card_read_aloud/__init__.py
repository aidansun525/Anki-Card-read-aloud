# Card Read Aloud: reads the review card out loud, either with Kokoro, an
# open-source neural voice (natural.py), or with Anki's own text-to-speech
# (the macOS / Windows system voices).
#
# The page script (web/reader.js) walks the card as shown, skipping hidden
# hint fields, images and buttons, and sends the text back here. We then
# speak it once the card's own sounds have finished, and stop it when you
# flip, answer or leave the review screen.

import json
import os
import re
import time

from anki.sound import TTSTag
from aqt import gui_hooks, mw
from aqt.qt import QAction, QMenu, QTimer
from aqt.reviewer import Reviewer
from aqt.sound import av_player
from aqt.utils import tooltip

from . import medspeak, natural

ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE = __name__

DEFAULTS = {
    "auto_read_front": True,
    "auto_read_back": True,
    "cloze_back": "answers",
    "read_extra": False,
    "blank_word": "blank",
    "engine": "system",
    "natural_voice": "af_heart",
    "natural_speed": 0.95,
    "natural_volume": 0.9,
    "output_device": "",
    "voice": "",
    "voice_lang": "en_US",
    "speed": 1.0,
    "wait_for_card_audio": True,
    "skip_cards_with_tts": True,
    "say_symbols": True,
    "medical_terms": True,
    "max_chars": 1500,
    "shortcut": "t",
    "replacements": {},
}

SYMBOLS = [
    ("→", " leads to "), ("⟶", " leads to "), ("➔", " leads to "),
    ("⇒", " leads to "), ("->", " leads to "), ("←", " from "),
    ("↔", " to and from "), ("↑", " increased "), ("⇧", " increased "),
    ("↓", " decreased "), ("⇩", " decreased "),
    ("≥", " greater than or equal to "), (">=", " greater than or equal to "),
    ("≤", " less than or equal to "), ("<=", " less than or equal to "),
    (">", " greater than "), ("<", " less than "), ("≈", " about "),
    ("~", " about "), ("±", " plus or minus "), ("+/-", " plus or minus "),
    ("°", " degrees "), ("×", " times "), ("&", " and "),
    ("∴", " therefore "), ("Δ", " change in "),
]

# The token for the side we last asked the page to read, so a late reply
# from a card you've already moved past is ignored.
_token = 0
_wanted = None


def get_config():
    cfg = dict(DEFAULTS)
    cfg.update(mw.addonManager.getConfig(MODULE) or {})
    return cfg


def save_config(cfg):
    mw.addonManager.writeConfig(MODULE, cfg)
    _sync_menu(cfg)
    _refresh_shortcuts()


# ---------------------------------------------------------------- text clean-up

def clean_text(text, cfg):
    text = text.replace(" ", " ").replace("​", "")
    # [sound:...] tags that weren't turned into buttons, and bare links
    text = re.sub(r"\[sound:[^\]]*\]", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    for src, dst in (cfg.get("replacements") or {}).items():
        if not src:
            continue
        if src[0].isalnum() and src[-1].isalnum():
            text = re.sub(r"(?<![\w])" + re.escape(src) + r"(?![\w])", " " + dst + " ", text)
        else:
            text = text.replace(src, " " + dst + " ")
    if cfg.get("medical_terms", True):
        text = medspeak.apply(text)
    if cfg.get("say_symbols", True):
        for src, dst in SYMBOLS:
            text = text.replace(src, dst)
    # each line becomes its own short sentence so lists get a pause
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"[ \t\r\f\v]+", " ", line).strip(" ,;")
        if not line:
            continue
        if not re.search(r"[.!?:;,]$", line):
            line += "."
        lines.append(line)
    text = " ".join(lines)
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    text = re.sub(r"([.,;:!?]){2,}", r"\1", text)
    try:
        limit = int(cfg.get("max_chars", 1500))
    except (TypeError, ValueError):
        limit = 1500
    if limit > 0 and len(text) > limit:
        cut = text[:limit]
        end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
        text = cut[: end + 1] if end > limit // 2 else cut
    return text.strip()


# ---------------------------------------------------------------- speaking

def make_tag(text, cfg):
    try:
        speed = min(2.0, max(0.5, float(cfg.get("speed", 1.0))))
    except (TypeError, ValueError):
        speed = 1.0
    voice = (cfg.get("voice") or "").strip()
    lang = (cfg.get("voice_lang") or "en_US").strip() or "en_US"
    return TTSTag(
        # no-break spaces only matter to the natural voice
        field_text=text.replace("\u00a0", " "),
        lang=lang,
        voices=[voice] if voice else [],
        speed=speed,
        other_args=[],
    )


def have_voice(tag):
    return any(p.rank_for_tag(tag) is not None for p in av_player.players)


def _num(value, default, lo, hi):
    try:
        return min(hi, max(lo, float(value)))
    except (TypeError, ValueError):
        return default


def use_natural(cfg):
    return cfg.get("engine") == "natural" and natural.is_installed() and not natural.helper.broken


_waiting = None


def _speak_natural(text, cfg, interrupt):
    """Kokoro plays outside Anki's audio queue, so wait for card sounds here."""
    global _waiting
    _waiting = None
    if interrupt:
        av_player.stop_and_clear_queue()
    natural.helper.stop()
    job = object()
    _waiting = job
    started = time.time()

    def go():
        global _waiting
        if _waiting is not job:
            return
        busy = av_player.current_player is not None or not av_player.queue_is_empty()
        if busy and cfg.get("wait_for_card_audio", True) and time.time() - started < 120:
            QTimer.singleShot(100, go)
            return
        _waiting = None
        natural.helper.speak(
            text,
            cfg.get("natural_voice") or "af_heart",
            _num(cfg.get("natural_speed"), 0.95, 0.5, 2.0),
            _num(cfg.get("natural_volume"), 0.9, 0.05, 1.0),
            cfg.get("output_device") or "",
        )

    go()
    return True


def _natural_failed(reason, text=None):
    tooltip(f"Card Read Aloud: the natural voice couldn't start ({reason}). Using the built-in voice for now.")
    if text:
        cfg = get_config()
        cfg["engine"] = "system"
        speak(text, cfg)


def _natural_installed():
    cfg = get_config()
    cfg["engine"] = "natural"
    save_config(cfg)
    natural.helper.broken = None
    natural.helper.start()
    tooltip("Card Read Aloud: the natural voice is ready.")


def speak(text, cfg=None, interrupt=False):
    cfg = cfg or get_config()
    text = clean_text(text, cfg)
    if not text:
        return False
    if use_natural(cfg):
        return _speak_natural(text, cfg, interrupt)
    tag = make_tag(text, cfg)
    if not have_voice(tag):
        tooltip("Card Read Aloud: no text-to-speech voice was found on this computer.")
        return False
    if interrupt or not cfg.get("wait_for_card_audio", True):
        av_player.play_tags([tag])
    else:
        av_player.append_tags([tag])
    return True


def is_reading():
    from aqt.tts import TTSPlayer

    if _waiting is not None or natural.helper.is_speaking():
        return True
    return isinstance(av_player.current_player, TTSPlayer)


def stop_natural():
    global _waiting
    _waiting = None
    natural.helper.stop()


def stop():
    stop_natural()
    av_player.stop_and_clear_queue()


# ---------------------------------------------------------------- reviewer

def _reviewer():
    if mw.state == "review" and getattr(mw, "reviewer", None) and mw.reviewer.web:
        return mw.reviewer
    return None


def _card_has_tts(card, side):
    try:
        tags = card.question_av_tags() if side == "q" else card.answer_av_tags()
    except Exception:
        return False
    return any(isinstance(t, TTSTag) for t in tags)


def request(side, interrupt=False):
    """Ask the review page for the text of the side that's showing."""
    global _token, _wanted
    reviewer = _reviewer()
    if not reviewer:
        return
    cfg = get_config()
    _token += 1
    _wanted = (_token, side, interrupt)
    opts = {
        "blank": cfg.get("blank_word") or "blank",
        "clozeBack": cfg.get("cloze_back", "answers"),
        "readExtra": bool(cfg.get("read_extra", False)),
    }
    # _queueAction runs after Anki has finished putting the card on screen
    reviewer.web.eval(
        "(window._queueAction || function (f) { f(); })(function () {"
        f" window.cardReadAloud && window.cardReadAloud({json.dumps(side)}, {_token}, {json.dumps(opts)});"
        " });"
    )


def on_show_question(card):
    stop_natural()
    cfg = get_config()
    if not cfg.get("auto_read_front", True):
        return
    if cfg.get("skip_cards_with_tts", True) and _card_has_tts(card, "q"):
        return
    request("q")


def on_show_answer(card):
    stop_natural()
    cfg = get_config()
    if not cfg.get("auto_read_back", True):
        return
    if cfg.get("skip_cards_with_tts", True) and _card_has_tts(card, "a"):
        return
    request("a")


def read_now():
    """The shortcut: stop if we're talking, otherwise read the current side."""
    if is_reading():
        stop()
        return
    reviewer = _reviewer()
    if not reviewer:
        tooltip("Card Read Aloud works while you review.")
        return
    request("a" if reviewer.state == "answer" else "q", interrupt=True)


def on_js_message(handled, message, context):
    if not (isinstance(message, str) and message.startswith("readaloud:")):
        return handled
    if not isinstance(context, Reviewer):
        return (True, None)
    try:
        data = json.loads(message[len("readaloud:"):])
    except ValueError:
        return (True, None)
    wanted = _wanted
    if not wanted or data.get("token") != wanted[0] or data.get("side") != wanted[1]:
        return (True, None)
    reviewer = _reviewer()
    current = "a" if reviewer and reviewer.state == "answer" else "q"
    if current != wanted[1]:
        return (True, None)
    speak(str(data.get("text") or ""), interrupt=wanted[2])
    return (True, None)


def inject(web_content, context):
    if not isinstance(context, Reviewer):
        return
    with open(os.path.join(ADDON_DIR, "web", "reader.js"), encoding="utf-8") as f:
        web_content.head += f"<script>{f.read()}</script>"


def on_shortcuts(state, shortcuts):
    if state != "review":
        return
    key = (get_config().get("shortcut") or "").strip()
    if key:
        # replace any earlier binding for the same key
        shortcuts[:] = [s for s in shortcuts if str(s[0]).lower() != key.lower()]
        shortcuts.append((key, read_now))


def on_state_change(new_state, old_state):
    if old_state == "review" and new_state != "review" and is_reading():
        stop()


def _other_copies():
    """Other enabled copies of this add-on, e.g. one from AnkiWeb and one
    installed from a file. Each would read every card, so you'd hear it twice."""
    am = mw.addonManager
    found = []
    for module in am.allAddons():
        if module == MODULE or not am.isEnabled(module):
            continue
        if os.path.exists(os.path.join(am.addonsFolder(module), "natural_voice", "kokoro_helper.py")):
            found.append(module)
    return found


def _offer_to_disable_copies():
    from aqt.utils import askUser

    others = _other_copies()
    if not others:
        return
    names = ", ".join(f'"{m}"' for m in others)
    if askUser(
        "Card Read Aloud is installed more than once, so each card is read more than once.\n\n"
        f"Turn off the extra copy ({names})? This keeps the one in \"{MODULE}\", "
        "including your settings and the natural voice. Anki will need a restart.",
        title="Card Read Aloud",
    ):
        am = mw.addonManager
        # keep your settings: if this copy was never set up, take the other's
        if (am.getConfig(MODULE) or {}) == (am.addonConfigDefaults(MODULE) or {}):
            for module in others:
                theirs = am.getConfig(module)
                if theirs and theirs != (am.addonConfigDefaults(module) or {}):
                    save_config({**get_config(), **theirs})
                    break
        for module in others:
            am.toggleEnabled(module, enable=False)
        tooltip("Card Read Aloud: the extra copy is off. Restart Anki to finish.", period=6000)


def on_profile_open():
    QTimer.singleShot(1500, _offer_to_disable_copies)
    # load the natural voice in the background so the first card isn't slow
    if use_natural(get_config()):
        try:
            natural.helper.start()
        except Exception as e:
            natural.log(f"helper start failed: {e}")


def _refresh_shortcuts():
    if mw.state == "review":
        try:
            mw.setStateShortcuts(mw.reviewer._shortcutKeys())
        except Exception:
            pass


# ---------------------------------------------------------------- Tools menu

_actions = {}


def _toggle(key):
    cfg = get_config()
    cfg[key] = not cfg.get(key, True)
    save_config(cfg)


def _sync_menu(cfg=None):
    cfg = cfg or get_config()
    for key, action in _actions.items():
        action.setChecked(bool(cfg.get(key, True)))


def open_settings():
    from .settings import SettingsDialog

    SettingsDialog(mw).exec()


def build_menu():
    menu = QMenu("Card Read Aloud", mw)
    for key, label in (
        ("auto_read_front", "Read the front automatically"),
        ("auto_read_back", "Read the back automatically"),
    ):
        action = QAction(label, mw)
        action.setCheckable(True)
        action.triggered.connect(lambda _checked=False, k=key: _toggle(k))
        menu.addAction(action)
        _actions[key] = action
    menu.addSeparator()
    read = QAction("Read this side now / stop", mw)
    read.triggered.connect(lambda _checked=False: read_now())
    menu.addAction(read)
    stop_action = QAction("Stop reading", mw)
    stop_action.triggered.connect(lambda _checked=False: stop())
    menu.addAction(stop_action)
    menu.addSeparator()
    settings = QAction("Settings…", mw)
    settings.triggered.connect(lambda _checked=False: open_settings())
    menu.addAction(settings)
    mw.form.menuTools.addMenu(menu)
    _sync_menu()


def setup():
    build_menu()
    mw.addonManager.setConfigAction(MODULE, open_settings)
    gui_hooks.webview_will_set_content.append(inject)
    gui_hooks.webview_did_receive_js_message.append(on_js_message)
    gui_hooks.reviewer_did_show_question.append(on_show_question)
    gui_hooks.reviewer_did_show_answer.append(on_show_answer)
    gui_hooks.state_shortcuts_will_change.append(on_shortcuts)
    gui_hooks.state_will_change.append(on_state_change)
    gui_hooks.profile_did_open.append(on_profile_open)
    gui_hooks.profile_will_close.append(natural.stop_helper)
    natural.helper.on_failed = _natural_failed
    natural.installer.on_installed = _natural_installed


# If another copy of this add-on already loaded, stay quiet: only one copy
# may read, and that copy offers to turn the others off.
if getattr(mw, "_card_read_aloud_module", None) is None:
    mw._card_read_aloud_module = MODULE
    setup()
