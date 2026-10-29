Use **Tools > Card Read Aloud > Settings** for a friendlier window. Raw options:

- `auto_read_front` / `auto_read_back`: read each side when it appears in review.
- `cloze_back`: on the back of a cloze card, `"answers"` reads just the hidden words; `"sentence"` reads the whole sentence with them filled in.
- `read_extra`: also read the Extra field (AnKing) on the back.
- `blank_word`: what to say for a hidden cloze on the front.
- `engine`: `"natural"` for the Kokoro neural voice (download it from Settings first) or `"system"` for the computer's built-in voices.
- `natural_voice`: a Kokoro voice such as `af_heart`, `af_nicole`, `bf_emma`; blend two with `af_heart:0.6+af_nicole:0.4`.
- `natural_speed` / `natural_volume`: for the natural voice (speed 0.5 to 2.0, volume 0.05 to 1.0).
- `voice` / `voice_lang`: a voice name from the Settings window (empty = the system's default English voice).
- `speed`: built-in voice speed; 1.0 is normal; 0.5 to 2.0.
- `wait_for_card_audio`: let the card's own sounds finish first instead of cutting them off.
- `skip_cards_with_tts`: don't auto-read cards whose template already uses Anki's `{{tts}}`.
- `say_symbols`: say arrows and symbols (→ ↑ ↓ ≥ ±) as words.
- `medical_terms`: read medical shorthand the way it's said on the wards (IV as "I V", q8h as "every 8 hours", Na+ as "sodium", acetyl-CoA as "acetyl co A"). The natural voice also uses an exact pronunciation list for about 1,400 drug, bug, anatomy and biochemistry names (natural_voice/lexicon.json), and reads joined words in their parts ("neo antigen", "onco fetal").
- `max_chars`: stop after this many characters.
- `shortcut`: key that reads the current side again, or stops reading.
- `replacements`: abbreviations to say as words.
