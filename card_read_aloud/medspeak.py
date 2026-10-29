"""Medical reading rules: say abbreviations, units, ions and symbols the way
a clinician would read them out loud. Used by both voices; drug, bug and
enzyme names are handled separately by the natural voice's lexicon.

Rules here are deliberately conservative: an abbreviation is only touched
when it's written the usual way (case matters: "IV" yes, "iv" no).
"""

import re

# Letters of one abbreviation are joined with a no-break space, so the natural
# voice can tell "I G M" from two abbreviations side by side ("IgM IgG").
NB = "\u00a0"


def _nb(text):
    return re.sub(r"(?<![\w])([A-Z]) (?=[A-Z](?![\w]))", r"\1" + NB, text)

# Said as letters, the way they're said on the wards. Written with spaces so
# neither voice reads them as a word ("IV" as Roman four, "DIC" as a word).
LETTERS = """
IV IM IO SC SQ PO PR SL NG NPO PRN BID TID QID QD QHS ICU ED ER
MI CHF CAD PE DVT COPD ARDS DKA HHS AKI CKD ESRD GFR UTI URI STI STD
DIC TTP HUS ITP HIT SLE RA OA MS ALS IBD IBS GI GU GERD PUD UC CNS PNS
CSF EEG EKG ECG MRI CT CXR ABG CBC BMP CMP LFT LFTs PT PTT INR ESR CRP
WBC RBC RBCs WBCs HCT MCV TSH ACTH ADH GH FSH LH PTH HCG IGF ANP BNP
HIV HPV HSV EBV CMV VZV HBV HCV HAV RSV MRSA MSSA VRE ESBL CRE TB MTB LTBI
AFB PPD IGRA PCR RPR VDRL FTA HLA MHC TCR BCR NK APC
DNA RNA mRNA tRNA rRNA ATP ADP AMP GTP GDP UTP CTP NAD NADH NADP NADPH
FAD FADH FMN PRPP PLP TPP THF DHF SAM SAH UDP ROS RNS GSH GSSG SOD
LDL HDL VLDL IDL LPL LCAT CETP HMG PFK PDH DHAP BPG OAA TCA ETC
CPT ACC FAS ALT AST ALP GGT LDH CK BUN PKU MSUD OTC CPS NSAID NSAIDs SSRI
SSRIs SNRI SNRIs MAOI ARB ARBs CCB PPI PPIs DOAC LMWH UFH
G6PD PPAR GLUT SGLT DPP GLP GIP
CPS OTC NAGS ASL BCKDH BCAA BH HSL ATGL MTP LCFA MCFA VLCFA SCFA PUFA EPA DHA
PEP ALA PBG ADA PNP HGPRT HGPRTase APRT UMP OMP IMP XMP CBS MMA ACAT ABCA SREBP NPC MCAD SCAD LCAD VLCAD LCHAD BCKD BCAT GDH PAH HGD FAH IVC IVF SVC PCSK dUMP dTMP dNTP dNTPs CEA ADCC ADCP ADC EGFR HER VEGF PDGF FGF AFP PSA LDH CA ssDNA dsDNA cDNA mtDNA ctDNA ssRNA dsRNA siRNA miRNA snRNA lncRNA PK MAO COMT PG PGE PGI PGF LTB LTC LTD MTHFR
"""

EXPANSIONS = {
    # shorthand
    "SOB": "shortness of breath",
    "DOE": "dyspnea on exertion",
    "N/V/D": "nausea, vomiting and diarrhea",
    "N/V": "nausea and vomiting",
    "b/l": "bilateral",
    "s/p": "status post",
    "r/o": "rule out",
    "c/o": "complains of",
    "h/o": "history of",
    "f/u": "follow up",
    "w/u": "workup",
    "d/t": "due to",
    "y/o": "year old",
    "yo": "year old",
    "pt": "patient",
    "pts": "patients",
    "Pt": "Patient",
    "Pts": "Patients",
    "hx": "history", "Hx": "history",
    "dx": "diagnosis", "Dx": "diagnosis",
    "ddx": "differential diagnosis", "DDx": "differential diagnosis", "Ddx": "differential diagnosis",
    "tx": "treatment", "Tx": "treatment",
    "sx": "symptoms", "Sx": "symptoms",
    "rx": "prescription", "Rx": "prescription",
    "px": "prognosis", "Px": "prognosis",
    "bx": "biopsy", "Bx": "biopsy",
    "fx": "fracture", "Fx": "fracture",
    "cx": "culture", "Cx": "culture",
    "abx": "antibiotics", "Abx": "antibiotics",
    "rxn": "reaction", "Rxn": "reaction",
    "MOA": "mechanism of action",
    "DOC": "drug of choice",
    "AE": "adverse effect",
    "AEs": "adverse effects",
    "ADR": "adverse drug reaction",
    "ADRs": "adverse drug reactions",
    "Ab": "antibody",
    "Abs": "antibodies",
    "Ag": "antigen",
    "Ags": "antigens",
    "Hb": "hemoglobin", "Hgb": "hemoglobin",
    "Hct": "hematocrit",
    "plt": "platelets", "Plt": "platelets",
    "BP": "blood pressure",
    "HR": "heart rate",
    "RR": "respiratory rate",
    "SpO2": "oxygen saturation",
    "vs": "versus", "vs.": "versus",
    "e.g.": "for example",
    "i.e.": "that is",
    "etc.": "et cetera",
    "approx": "approximately", "approx.": "approximately",
    "incr": "increased", "decr": "decreased",
    "CABG": "cabbage",
    "IVDU": "I V drug use",
    "IVDA": "I V drug abuse",
    "IVIG": "I V I G",
    "ACEi": "ace inhibitor",
    "ACEI": "ace inhibitor",
    "GPC": "gram positive cocci",
    "GPR": "gram positive rod",
    "GNC": "gram negative cocci",
    "GNR": "gram negative rod",
    "GNRs": "gram negative rods",
    "C. diff": "C diff",
    "C.diff": "C diff",
    # bugs: the way they're said aloud
    "S. aureus": "Staph aureus",
    "S. epidermidis": "Staph epidermidis",
    "S. saprophyticus": "Staph saprophyticus",
    "S. lugdunensis": "Staph lugdunensis",
    "S. pneumoniae": "Strep pneumoniae",
    "S. pyogenes": "Strep pyogenes",
    "S. agalactiae": "Strep agalactiae",
    "S. mutans": "Strep mutans",
    "S. bovis": "Strep bovis",
    "S. gallolyticus": "Strep gallolyticus",
    "S. viridans": "Strep viridans",
    # biochemistry
    "CoA": "co A",
    "CoQ10": "co Q 10",
    "CoQ": "co Q",
    "acetyl-CoA": "acetyl co A",
    "HMG-CoA": "H M G co A",
    "malonyl-CoA": "malonyl co A",
    "propionyl-CoA": "propionyl co A",
    "methylmalonyl-CoA": "methylmalonyl co A",
    "succinyl-CoA": "succinyl co A",
    "acyl-CoA": "acyl co A",
    "NAD+": "N A D plus",
    "NADP+": "N A D P plus",
    "FADH2": "F A D H 2",
    "QH2": "Q H 2",
    "cAMP": "cyclic A M P",
    "cGMP": "cyclic G M P",
    "IP3": "I P 3",
    "DAG": "D A G",
    "PIP2": "P I P 2",
    "TXA2": "thromboxane A 2",
    "TAG": "triglyceride",
    "TAGs": "triglycerides",
    "FFA": "free fatty acids",
    "FFAs": "free fatty acids",
    "Km": "K M",
    "Vmax": "V max",
    "pKa": "p K a",
    "pH": "P H",
    "Hz": "hertz",
    # ions and small molecules
    "Na+": "sodium",
    "K+": "potassium",
    "Ca2+": "calcium", "Ca++": "calcium", "Ca": "calcium",
    "Mg2+": "magnesium", "Mg++": "magnesium",
    "Cl-": "chloride",
    "HCO3-": "bicarbonate", "HCO3": "bicarbonate",
    "H+": "hydrogen ion",
    "Fe2+": "ferrous iron", "Fe3+": "ferric iron",
    "Zn2+": "zinc", "Cu2+": "copper",
    "NH3": "ammonia",
    "NH4+": "ammonium",
    "PO4": "phosphate",
    "SO4": "sulfate",
    "CO2": "C O 2",
    "O2": "oxygen",
    "H2O": "water",
    "H2O2": "hydrogen peroxide",
    "O2-": "superoxide",
    "CAR-T": "car T",
    "CAR T": "car T",
    "Treg": "T reg",
    "Tregs": "T regs",
    "Ig": "I G",
    "OBGYN": "O B G Y N",
    "OB/GYN": "O B G Y N",
    "NaCl": "sodium chloride",
    "KCl": "potassium chloride",
    "HCl": "hydrochloric acid",
    "Pi": "phosphate",
    "PPi": "pyrophosphate",
}

GREEK = {
    "α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "epsilon",
    "ζ": "zeta", "η": "eta", "θ": "theta", "κ": "kappa", "λ": "lambda",
    "μ": "mu", "ν": "nu", "π": "pi", "ρ": "rho", "σ": "sigma", "τ": "tau",
    "φ": "phi", "χ": "chi", "ψ": "psi", "ω": "omega",
    "Δ": "delta", "Σ": "sigma", "Ω": "omega",
}

UNITS = {
    "mg/kg/day": "milligrams per kilogram per day",
    "mg/kg/d": "milligrams per kilogram per day",
    "mg/kg": "milligrams per kilogram",
    "mcg/kg": "micrograms per kilogram",
    "mg/dL": "milligrams per deciliter",
    "mg/dl": "milligrams per deciliter",
    "g/dL": "grams per deciliter",
    "g/dl": "grams per deciliter",
    "mg/L": "milligrams per liter",
    "ng/mL": "nanograms per milliliter",
    "pg/mL": "picograms per milliliter",
    "mEq/L": "milliequivalents per liter",
    "mmol/L": "millimoles per liter",
    "mOsm/kg": "milliosmoles per kilogram",
    "mL/min": "milliliters per minute",
    "mL/hr": "milliliters per hour",
    "mL/h": "milliliters per hour",
    "cells/mm3": "cells per cubic millimeter",
    "cells/μL": "cells per microliter",
    "/mm3": "per cubic millimeter",
    "/μL": "per microliter",
    "/min": "per minute",
    "mmHg": "millimeters of mercury",
    "cmH2O": "centimeters of water",
    "mcg": "micrograms", "μg": "micrograms", "µg": "micrograms",
    "mg": "milligrams", "kg": "kilograms", "g": "grams", "ng": "nanograms",
    "mL": "milliliters", "ml": "milliliters", "dL": "deciliters", "L": "liters",
    "mEq": "milliequivalents", "mmol": "millimoles", "μmol": "micromoles", "nmol": "nanomoles",
    "mOsm": "milliosmoles",
    "IU": "international units", "U": "units", "units": "units",
    "bpm": "beats per minute",
    "mm": "millimeters", "cm": "centimeters", "μm": "micrometers", "µm": "micrometers", "nm": "nanometers",
    "kcal": "kilocalories", "kDa": "kilodaltons",
    "hr": "hours", "hrs": "hours", "h": "hours", "min": "minutes", "mins": "minutes",
    "wk": "weeks", "wks": "weeks", "mo": "months", "yr": "years", "yrs": "years",
    "°C": "degrees Celsius", "°F": "degrees Fahrenheit",
    "%": "percent",
}

# words after which a Roman numeral really is a number ("type IV", "factor VIII")
ROMAN_CONTEXT = (
    "type", "types", "class", "classes", "factor", "factors", "stage", "stages",
    "grade", "grades", "phase", "phases", "complex", "complexes", "cn", "nerve",
    "nerves", "collagen", "chapter", "part", "level", "degree", "lead", "leads",
    "mobitz", "trisomy", "cps", "hypersensitivity", "group", "groups", "zone",
)
ROMAN_VALUES = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8,
    "IX": 9, "X": 10, "XI": 11, "XII": 12, "XIII": 13,
}


def _word_re(key):
    start = r"(?<![\w])" if key[0].isalnum() else ""
    end = r"(?![\w])" if key[-1].isalnum() else ""
    if key[-1] in "+-":
        # "Na+" but not "Na+K" style joins
        end = r"(?![\w+])"
    return re.compile(start + re.escape(key) + end)


_EXPANSIONS = sorted(EXPANSIONS.items(), key=lambda kv: -len(kv[0]))
_EXPANSION_RES = [(_word_re(k), _nb(v)) for k, v in _EXPANSIONS]
_LETTERS = sorted(set(LETTERS.split()), key=len, reverse=True)


def _spell(abbr):
    # "LFTs" -> "L F Ts", "mRNA" -> "m R N A", digits stay together
    plural = abbr.endswith("s") and abbr[:-1].isupper() and len(abbr) > 2
    core = abbr[:-1] if plural else abbr
    out = " ".join(re.findall(r"\d+|.", core))
    return _nb(out) + ("s" if plural else "")


# Capitalized abbreviations not listed above are spelled out too ("SIADH",
# "ECF", "AUB"), except ones that are said as words and ordinary words written
# in capitals for emphasis ("NOT", "ALL").
SAID_AS_WORDS = set("""
AIDS GABA STEMI NSTEMI SOAP SOAPs RAAS ANCA ELISA HAART SARS COVID PEEP SNARE
MALT FAST FISH MASH NASH TIPS SABA LABA LAMA SCID PROM PPROM NAAT AMBOSS DEXA
LASIK MODY MERS HELLP CREST TORCH VACTERL WAGR PANDAS POEMS HACEK SPIKES NOTCH
GOLD BRAT CHADS PERC WELLS CURB SIRS SOFA DASH NICE AMBU CPAP BIPAP SPECT PET
TENS ACE UNICEF NASA LASER RADAR SCUBA ACTH NADPH CABG HEENT SIDS ARDS CREST
SMART TRAP REDS RICE MONA SALT PAINT MUDPILES CHAMPS SAD SAMPLE OPQRST
""".split())
TWO_LETTER_WORDS = set("AM AN AS AT BE BY DO GO HE IF IN IS IT ME MY NO OF OH ON OR SO TO UP US WE OK".split())
ROMAN_NUMBERS = {"II": 2, "III": 3, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "XI": 11, "XII": 12, "XIII": 13}
_CAPS_RE = re.compile(r"(?<![\w])([A-Z]{2,7})(s?)(\d*)(?![\w])")
_common = None


def _common_words():
    global _common
    if _common is None:
        import os

        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "natural_voice", "words_common.txt")
        try:
            with open(path, encoding="utf-8") as f:
                _common = {line.strip() for line in f if line.strip()}
        except OSError:
            _common = set()
    return _common


def _caps(m):
    word, plural, digits = m.groups()
    if word in ROMAN_NUMBERS and not plural and not digits:
        # a Roman numeral on its own is a number, never "Roman two"
        return str(ROMAN_NUMBERS[word])
    if word in SAID_AS_WORDS or (word + plural) in SAID_AS_WORDS:
        return m.group(0)
    if not digits:
        if word in TWO_LETTER_WORDS or (word + plural).lower() in _common_words() or word.lower() in _common_words():
            return m.group(0)
    return NB.join(word) + plural + (" " + digits if digits else "")


_LETTER_RE = re.compile(r"(?<![\w])((?:" + "|".join(re.escape(a) for a in _LETTERS) + r")\d*)(?![\w])")
_UNIT_RE = re.compile(
    r"(\d(?:[\d,.]*\d)?)\s?("
    + "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
    + r")(?![\w])"
)
_ROMAN_RE = re.compile(r"(?<![\w])([A-Za-z]+)([\s-]+)(XIII|XII|XI|IX|X|VIII|VII|VI|V|IV|III|II|I)(?![\w])")


def apply(text):
    # Roman numerals that are numbers: "type IV" -> "type 4"
    def roman(m):
        if m.group(1).lower() in ROMAN_CONTEXT:
            return f"{m.group(1)}{m.group(2)}{ROMAN_VALUES[m.group(3)]}"
        return m.group(0)

    text = _ROMAN_RE.sub(roman, text)

    # ordinals written with a degree sign: 1° and 2° prevention, 3° syphilis
    text = re.sub(r"(?<![\d.])1°(?!\s?[CF]\b)", "primary", text)
    text = re.sub(r"(?<![\d.])2°(?!\s?[CF]\b)", "secondary", text)
    text = re.sub(r"(?<![\d.])3°(?!\s?[CF]\b)", "tertiary", text)

    # dosing frequency: q6h, q4-6h, q12 hours
    text = re.sub(r"(?<![\w])q(\d+(?:-\d+)?)\s?h(?:rs?|ours?)?(?![\w])", r"every \1 hours", text)
    text = re.sub(r"(?<![\w])q(\d+)\s?min(?![\w])", r"every \1 minutes", text)
    text = re.sub(r"(?<![\w])qd(?![\w])", "daily", text)
    text = re.sub(r"(?<![\w])qhs(?![\w])", "at bedtime", text)
    text = re.sub(r"(?<![\w])x\s?(\d+)(?![\w])", r"times \1", text)
    text = re.sub(r"(?<![\w])(\d+)x(?![\w])", r"\1 times", text)

    # numbers with units
    text = _UNIT_RE.sub(lambda m: f"{m.group(1)} {UNITS[m.group(2)]}", text)

    # charges, CD markers and ratios
    text = re.sub(r"(?<![\w])CD(\d+)\+", "C" + NB + r"D \1 positive", text)
    text = re.sub(r"(?<![\w])CD(\d+)(?![\w])", "C" + NB + r"D \1", text)
    text = re.sub(r"(?<![\w])IL-?(\d+)", r"interleukin \1", text)
    text = re.sub(r"(?<![\w])TNF-?(?=[αβa])", _nb("T N F "), text)
    text = re.sub(r"(?<![\w])TNF(?![\w])", _nb("T N F"), text)
    text = re.sub(r"(?<![\w])IFN-?", "interferon ", text)
    text = re.sub(r"(?<![\w])TGF-?", _nb("T G F "), text)
    text = re.sub(r"(?<![\w])Ig([AGMDE])(?![\w])", "I" + NB + "G" + NB + r"\1", text)
    text = re.sub(r"/mL(?![\w])", " per M L", text)
    text = re.sub(r"(?<![\w])HLA-?([A-Z]+)(\d*)", lambda m: _nb("H L A " + " ".join(m.group(1))) + (" " + m.group(2) if m.group(2) else ""), text)
    text = re.sub(r"(?<![\w])apo\s?([A-E])-?(\d*)", lambda m: f"apo {m.group(1)}" + (f" {m.group(2)}" if m.group(2) else ""), text, flags=re.I)
    text = re.sub(r"(?<![\w])(\d+),\s?(XX|XY|XXY|XO|XXX|XYY)(?![\w])", lambda m: f"{m.group(1)} {' '.join(m.group(2))}", text)
    text = re.sub(r"(?<![\w])t\((\d+|[XY]);(\d+|[XY])\)", r"translocation \1 \2", text)
    text = re.sub(r"(?i)\bgram\s?\+", "gram positive", text)
    text = re.sub(r"(?i)\bgram\s?[-−–]", "gram negative", text)
    text = re.sub(r"\(\s?\+\s?\)", " positive ", text)
    text = re.sub(r"\(\s?[-−–]\s?\)", " negative ", text)
    text = re.sub(r"(?<![\w])\+ve(?![\w])", "positive", text)
    text = re.sub(r"(?<![\w])-ve(?![\w])", "negative", text)

    # sugar phosphates written short: F-1,6-BP, F2,6BP, G-6-P, G1P, 1,3-BPG
    sugars = {"F": "fructose", "G": "glucose"}
    text = re.sub(r"(?<![\w])([FG])-?(\d),(\d)-?BP(?![\w])", lambda m: f"{sugars[m.group(1)]} {m.group(2)} {m.group(3)} bisphosphate", text)
    text = re.sub(r"(?<![\w])G-?3-?P(?![\w])", "glyceraldehyde 3 phosphate", text)
    text = re.sub(r"(?<![\w])R(?:u)?-?5-?P(?![\w])", lambda m: ("ribulose" if "u" in m.group(0) else "ribose") + " 5 phosphate", text)
    text = re.sub(r"(?<![\w])([23])-?PG(?![\w])", r"\1 phosphoglycerate", text)
    text = re.sub(r"(?<![\w])Xu-?5-?P(?![\w])", "xylulose 5 phosphate", text)
    text = re.sub(r"(?<![\w])E-?4-?P(?![\w])", "erythrose 4 phosphate", text)
    text = re.sub(r"(?<![\w])S-?7-?P(?![\w])", "sedoheptulose 7 phosphate", text)
    text = re.sub(r"(?<![\w])(?:α|alpha|a)-?KGDH(?![\w])", "alpha ketoglutarate dehydrogenase", text)
    text = re.sub(r"(?<![\w])([FG])-?(\d)-?P(?![\w])", lambda m: f"{sugars[m.group(1)]} {m.group(2)} phosphate", text)
    text = re.sub(r"(?<![\w])(\d),(\d)-?BP(?![\w])", r"\1 \2 bisphosphate", text)
    text = re.sub(r"(?<![\w])(\d),(\d)-?BPG(?![\w])", r"\1 \2 B P G", text)
    text = re.sub(r"(?<![\w])(?:α|alpha|a)-?KG(?![\w])", "alpha ketoglutarate", text)

    # fixed expansions (longest first), then letter-by-letter abbreviations
    for rx, val in _EXPANSION_RES:
        text = rx.sub(val, text)
    text = _LETTER_RE.sub(lambda m: _spell(m.group(1)), text)
    text = _CAPS_RE.sub(_caps, text)

    # glucose 6-phosphate, fructose 1,6-bisphosphate, 2,3-BPG
    text = re.sub(r"(?<![\w])(\d),(\d)-", r"\1 \2 ", text)
    text = re.sub(r"(?<![\w])G(\d)P(?![\w])", r"glucose \1 phosphate", text)
    text = re.sub(r"(?<![\w])F(\d)P(?![\w])", r"fructose \1 phosphate", text)

    for ch, name in GREEK.items():
        # "β-lactam" -> "beta lactam", "TNF-α" -> "T N F alpha"
        text = re.sub(re.escape(ch) + r"-?", name + " ", text)

    # "E. coli", "N. gonorrhoeae": drop the period so it isn't a sentence end
    text = re.sub(r"(?<![\w.])([A-Z])\.\s+(?=[a-z]{3,})", r"\1 ", text)
    return text
