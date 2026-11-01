# Changelog

## 1.9 (2026-11-01)

- **Choose where the natural voice plays.** Settings has a new "Play on" list with your speakers and headphones (for example AirPods). If the chosen device is unplugged, the voice uses the computer's default output instead. The built-in voice always uses the default output.

## 1.8 (2026-10-30)

- **Fixes cards being read two or three times.** This happened when the add-on was installed twice, for example once from AnkiWeb and once from a file: each copy read every card, often one with the built-in voice and one with the natural voice. Now only one copy reads, and it offers to turn the extra copy off (your settings come along).
- If the copy you keep hasn't downloaded the natural voice but the other copy has, it uses that download instead of fetching 500 MB again.

## 1.7 (2026-10-29)

Pronunciation update, checked against all 51,794 notes of a real AnKing collection.

- **Joined medical words are read in their parts.** *neoantigen* is "neo antigen", *oncofetal* is "onco fetal", *autoantibody* is "auto antibody", *preeclampsia* is "pre eclampsia", *thromboembolism* is "thrombo embolism", *hepatosplenomegaly* is "hepato spleno megaly". More than 100 combining forms (neo-, onco-, auto-, thrombo-, hepato-, immuno-, cardio-…) are recognised; everyday words such as *present* or *protein* are left alone.
- **Spelled-out abbreviations sound right.** A final "A" was being read as the word "a" (DNA, CEA, MRSA); letters are now always said as letter names, with the stress on the last one ("eye gee EM" for IgM).
- **Any capitalised abbreviation is spelled out** (SIADH, ECF, AUB, UTIs), except ones said as words (AIDS, GABA, STEMI, ELISA, HAART…) and ordinary words in capitals (NOT, ALL).
- **Roman numerals on their own are numbers.** "II" and "VII" no longer come out as "Roman two".
- **New readings:** CEA, ADCC, ADCP, ADC, EGFR, AFP, PSA, HER2, VEGF, dsDNA/ssRNA as letters; Ig as "I G"; Treg as "T reg"; CAR T as "car T"; /mL as "per M L".
- **About 640 new exact pronunciations** (1,481 in total) for words the voice misread, including impetigo, granules, edema, syncope, biliary, renin, alveoli, parietal, duodenum, emphysema, erythema, angiotensin, benzodiazepine, bronchiectasis, pheochromocytoma, hematopoiesis, Kaposi, Raynaud, Sjögren, Charcot and Wernicke.
- **Word families:** every "-iasis" word (candidiasis, cholelithiasis, psoriasis) and every virus family ending in "-viridae" now has the right stress.
- Words with accents (Müllerian, Sjögren, Schönlein) are no longer broken apart.

## 1.6

- Keeps the pronunciations added on the developer's Mac (818 in total).
- Fixes G3P, R5P, CoQ10 and dUMP.

## 1.5 and earlier

- Natural Kokoro voice, medical abbreviations and units, biochemistry rules, cloze-aware reading, AnKing timer fix, espeak path fix on macOS.
