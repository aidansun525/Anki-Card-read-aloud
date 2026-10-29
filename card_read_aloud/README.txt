Card Read Aloud
===============
Reads your review cards out loud, with either:
  * Natural voice: Kokoro (https://github.com/hexgrad/kokoro), an open-source
    neural voice (Apache 2.0). One-time download of about 500 MB from
    Tools > Card Read Aloud > Settings > Download. It runs on your own
    computer, offline, in a private Python under user_files/natural_voice/.
    The Remove button deletes it all.
  * Built-in voice: your computer's own voices (the same ones Anki's {{tts}}
    uses; on a Mac, System Settings > Accessibility > Spoken Content).

  * Front is read when it appears; back is read when you flip.
  * Cloze fronts say "blank" for the hidden part (and the hint, if any).
  * Cloze backs read just the hidden words, or the whole sentence (Settings).
  * Hidden hint fields, images, sound buttons and scripts are skipped.
  * Press T during review to read the current side again, or to stop.
  * Tools > Card Read Aloud has quick on/off switches and Settings.

Reading waits for the card's own audio to finish, and stops the same way
card audio does when you flip or answer.
