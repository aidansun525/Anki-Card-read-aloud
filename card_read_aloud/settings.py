"""Tools > Card Read Aloud > Settings: voice, speed, what gets read."""

from aqt import mw
from aqt.qt import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    Qt,
    QVBoxLayout,
)
from aqt.utils import tooltip

from . import get_config, natural, save_config, speak

SAMPLE = "Staphylococcus aureus is catalase positive and coagulase positive."


def _voices():
    try:
        from aqt.tts import all_tts_voices

        voices = all_tts_voices()
    except Exception:
        voices = []
    # English first, then the rest, each alphabetical
    return sorted(voices, key=lambda v: (not v.lang.startswith("en"), v.lang, v.name))


def _voice_label(voice):
    name = voice.name
    if name.startswith("Apple_"):
        name = name[len("Apple_"):]
    elif name.startswith("Microsoft_"):
        name = name[len("Microsoft_"):]
    return f"{name.replace('_', ' ')} ({voice.lang})"


def _replacements_to_text(rep):
    return "\n".join(f"{k} = {v}" for k, v in (rep or {}).items())


def _text_to_replacements(text):
    rep = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip():
            rep[k.strip()] = v.strip()
    return rep


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent or mw)
        self.setWindowTitle("Card Read Aloud")
        self.cfg = get_config()
        cfg = self.cfg

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.front = QCheckBox("Read the front when it appears")
        self.front.setChecked(bool(cfg["auto_read_front"]))
        self.back = QCheckBox("Read the back when it appears")
        self.back.setChecked(bool(cfg["auto_read_back"]))
        form.addRow(self.front)
        form.addRow(self.back)

        self.cloze = QComboBox()
        self.cloze.addItem("Just the hidden words", "answers")
        self.cloze.addItem("The whole sentence", "sentence")
        self.cloze.setCurrentIndex(1 if cfg["cloze_back"] == "sentence" else 0)
        form.addRow("Cloze back reads:", self.cloze)

        self.extra = QCheckBox("Also read the Extra field on the back")
        self.extra.setChecked(bool(cfg["read_extra"]))
        form.addRow(self.extra)

        self.blank = QLineEdit(cfg.get("blank_word") or "blank")
        form.addRow("Say for a hidden cloze:", self.blank)

        self.engine = QComboBox()
        self.engine.addItem("Natural voice (Kokoro, open source)", "natural")
        self.engine.addItem("Computer's built-in voice", "system")
        self.engine.setCurrentIndex(0 if cfg.get("engine") == "natural" else 1)
        self.engine.currentIndexChanged.connect(self.update_engine)
        test = QPushButton("Test")
        test.clicked.connect(self.test_voice)
        row = QHBoxLayout()
        row.addWidget(self.engine, 1)
        row.addWidget(test)
        form.addRow("Voice engine:", row)

        self.natural_voice = QComboBox()
        self.natural_voice.setEditable(False)
        for key, label in natural.VOICES:
            self.natural_voice.addItem(label, key)
        current = cfg.get("natural_voice") or "af_heart"
        idx = self.natural_voice.findData(current)
        if idx < 0:
            self.natural_voice.addItem(current, current)
            idx = self.natural_voice.count() - 1
        self.natural_voice.setCurrentIndex(idx)
        form.addRow("Natural voice:", self.natural_voice)

        self.natural_speed = QDoubleSpinBox()
        self.natural_speed.setRange(0.5, 2.0)
        self.natural_speed.setSingleStep(0.05)
        self.natural_speed.setSuffix("\u00d7")
        self.natural_speed.setValue(float(cfg.get("natural_speed", 0.95)))
        form.addRow("Natural speed:", self.natural_speed)

        self.natural_volume = QSlider(Qt.Orientation.Horizontal)
        self.natural_volume.setRange(5, 100)
        self.natural_volume.setValue(int(float(cfg.get("natural_volume", 0.9)) * 100))
        form.addRow("Natural volume:", self.natural_volume)

        self.install_status = QLabel()
        self.install_status.setWordWrap(True)
        self.install_button = QPushButton()
        self.install_button.clicked.connect(self.install_or_remove)
        row = QHBoxLayout()
        row.addWidget(self.install_status, 1)
        row.addWidget(self.install_button)
        form.addRow(row)
        natural.installer.listeners.append(self.update_install)
        self.finished.connect(lambda _r: self._unlisten())

        self.voice = QComboBox()
        self.voice.addItem("System default English voice", ("", "en_US"))
        for v in _voices():
            self.voice.addItem(_voice_label(v), (v.name, v.lang))
            if v.name == cfg.get("voice") and v.lang == cfg.get("voice_lang"):
                self.voice.setCurrentIndex(self.voice.count() - 1)
        if self.voice.count() == 1:
            self.voice.setToolTip("No system voices were found.")
        form.addRow("Built-in voice:", self.voice)

        self.speed = QDoubleSpinBox()
        self.speed.setRange(0.5, 2.0)
        self.speed.setSingleStep(0.1)
        self.speed.setDecimals(2)
        self.speed.setSuffix("×")
        self.speed.setValue(float(cfg.get("speed", 1.0)))
        form.addRow("Built-in speed:", self.speed)

        self.wait = QCheckBox("Let the card's own sounds play first")
        self.wait.setChecked(bool(cfg["wait_for_card_audio"]))
        form.addRow(self.wait)

        self.skip_tts = QCheckBox("Don't auto-read cards that already use {{tts}}")
        self.skip_tts.setChecked(bool(cfg["skip_cards_with_tts"]))
        form.addRow(self.skip_tts)

        self.symbols = QCheckBox("Say arrows and symbols as words (→ ↑ ↓ ≥ ±)")
        self.symbols.setChecked(bool(cfg["say_symbols"]))
        form.addRow(self.symbols)

        self.medical = QCheckBox("Medical pronunciations (IV, PO, mg/kg, Na+, acetyl-CoA, drug names\u2026)")
        self.medical.setChecked(bool(cfg.get("medical_terms", True)))
        form.addRow(self.medical)

        self.max_chars = QSpinBox()
        self.max_chars.setRange(0, 20000)
        self.max_chars.setSingleStep(250)
        self.max_chars.setSpecialValueText("No limit")
        self.max_chars.setValue(int(cfg.get("max_chars", 1500)))
        form.addRow("Stop after (characters):", self.max_chars)

        self.shortcut = QLineEdit(cfg.get("shortcut") or "")
        self.shortcut.setPlaceholderText("e.g. t")
        form.addRow("Read / stop key:", self.shortcut)

        layout.addWidget(QLabel("Say these abbreviations as words (one per line, short = long):"))
        self.replacements = QPlainTextEdit(_replacements_to_text(cfg.get("replacements")))
        self.replacements.setMinimumHeight(110)
        layout.addWidget(self.replacements)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.update_install()
        self.resize(480, self.sizeHint().height())

    def _unlisten(self):
        if self.update_install in natural.installer.listeners:
            natural.installer.listeners.remove(self.update_install)

    def update_engine(self):
        on = self.engine.currentData() == "natural"
        for w in (self.natural_voice, self.natural_speed, self.natural_volume):
            w.setEnabled(on)
        for w in (self.voice, self.speed):
            w.setEnabled(not on)

    def update_install(self):
        inst = natural.installer
        if inst.running:
            self.install_status.setText(inst.status)
            self.install_button.setText("Installing\u2026")
            self.install_button.setEnabled(False)
        elif natural.is_installed():
            self.install_status.setText("Natural voice is installed.")
            self.install_button.setText("Remove")
            self.install_button.setEnabled(True)
        else:
            text = f"The natural voice needs a one-time download ({natural.DOWNLOAD_SIZE_TEXT})."
            if inst.error:
                text = f"{inst.status} Details are in user_files/natural_voice/log.txt."
            self.install_status.setText(text)
            self.install_button.setText("Download")
            self.install_button.setEnabled(True)
        self.update_engine()

    def install_or_remove(self):
        if natural.is_installed():
            from aqt.utils import askUser

            if askUser("Remove the natural voice and free its disk space?", parent=self):
                natural.remove()
                self.engine.setCurrentIndex(1)
        else:
            self.engine.setCurrentIndex(0)
            natural.installer.start()
        self.update_install()

    def current(self):
        cfg = dict(self.cfg)
        voice, lang = self.voice.currentData() or ("", "en_US")
        cfg.update(
            engine=self.engine.currentData(),
            natural_voice=self.natural_voice.currentData(),
            natural_speed=round(self.natural_speed.value(), 2),
            natural_volume=round(self.natural_volume.value() / 100, 2),
            auto_read_front=self.front.isChecked(),
            auto_read_back=self.back.isChecked(),
            cloze_back=self.cloze.currentData(),
            read_extra=self.extra.isChecked(),
            blank_word=self.blank.text().strip() or "blank",
            voice=voice,
            voice_lang=lang,
            speed=round(self.speed.value(), 2),
            wait_for_card_audio=self.wait.isChecked(),
            skip_cards_with_tts=self.skip_tts.isChecked(),
            say_symbols=self.symbols.isChecked(),
            medical_terms=self.medical.isChecked(),
            max_chars=self.max_chars.value(),
            shortcut=self.shortcut.text().strip(),
            replacements=_text_to_replacements(self.replacements.toPlainText()),
        )
        return cfg

    def test_voice(self):
        cfg = self.current()
        if cfg["engine"] == "natural" and not natural.is_installed():
            tooltip("Download the natural voice first (or pick the built-in voice).", parent=self)
            return
        natural.helper.broken = None
        if cfg["engine"] == "natural" and not natural.helper.ready:
            tooltip("Loading the natural voice; the first time takes a few seconds\u2026", parent=self)
        if not speak(SAMPLE, cfg, interrupt=True):
            tooltip("Couldn't play the test sentence.", parent=self)

    def save(self):
        natural.helper.broken = None
        save_config(self.current())
        self.accept()
