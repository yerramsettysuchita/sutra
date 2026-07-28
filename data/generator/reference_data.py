"""Reference data for the synthetic KSP corpus.

Everything here is static lookup content. No randomness, no logic.

The name pools carry a Kannada rendering alongside the Latin transliteration
for every entry. That pairing is what makes cross script variation possible to
plant and therefore possible to measure. A generator that only emitted Latin
names would produce a corpus on which naive string matching looks competent,
which would be a corpus that flatters the engine instead of testing it.
"""

# ---------------------------------------------------------------------------
# Territory
# ---------------------------------------------------------------------------

STATE = {
    "StateID": 29,
    "StateName": "Karnataka",
    "StateNameKn": "ಕರ್ನಾಟಕ",
    "StateCode": "KA",
}

# (DistrictCode, DistrictName, DistrictNameKn, Latitude, Longitude)
# Coordinates are district centroids to roughly two decimal places. Station and
# incident coordinates are jittered off these at generation time.
DISTRICTS = [
    (1,  "Bagalkot",         "ಬಾಗಲಕೋಟೆ",              16.18, 75.70),
    (2,  "Ballari",          "ಬಳ್ಳಾರಿ",                15.14, 76.92),
    (3,  "Belagavi",         "ಬೆಳಗಾವಿ",                15.85, 74.50),
    (4,  "Bengaluru Urban",  "ಬೆಂಗಳೂರು ನಗರ",          12.97, 77.59),
    (5,  "Bengaluru Rural",  "ಬೆಂಗಳೂರು ಗ್ರಾಮಾಂತರ",     13.23, 77.57),
    (6,  "Bidar",            "ಬೀದರ್",                  17.91, 77.52),
    (7,  "Chamarajanagar",   "ಚಾಮರಾಜನಗರ",             11.92, 76.94),
    (8,  "Chikkaballapur",   "ಚಿಕ್ಕಬಳ್ಳಾಪುರ",           13.43, 77.73),
    (9,  "Chikkamagaluru",   "ಚಿಕ್ಕಮಗಳೂರು",            13.32, 75.77),
    (10, "Chitradurga",      "ಚಿತ್ರದುರ್ಗ",              14.23, 76.40),
    (11, "Dakshina Kannada", "ದಕ್ಷಿಣ ಕನ್ನಡ",            12.87, 74.88),
    (12, "Davanagere",       "ದಾವಣಗೆರೆ",               14.47, 75.92),
    (13, "Dharwad",          "ಧಾರವಾಡ",                 15.46, 75.01),
    (14, "Gadag",            "ಗದಗ",                    15.43, 75.63),
    (15, "Hassan",           "ಹಾಸನ",                   13.00, 76.10),
    (16, "Haveri",           "ಹಾವೇರಿ",                 14.80, 75.40),
    (17, "Kalaburagi",       "ಕಲಬುರಗಿ",                17.33, 76.83),
    (18, "Kodagu",           "ಕೊಡಗು",                  12.42, 75.74),
    (19, "Kolar",            "ಕೋಲಾರ",                  13.14, 78.13),
    (20, "Koppal",           "ಕೊಪ್ಪಳ",                  15.35, 76.15),
    (21, "Mandya",           "ಮಂಡ್ಯ",                   12.52, 76.90),
    (22, "Mysuru",           "ಮೈಸೂರು",                 12.30, 76.65),
    (23, "Raichur",          "ರಾಯಚೂರು",                16.21, 77.36),
    (24, "Ramanagara",       "ರಾಮನಗರ",                 12.72, 77.28),
    (25, "Shivamogga",       "ಶಿವಮೊಗ್ಗ",                13.93, 75.57),
    (26, "Tumakuru",         "ತುಮಕೂರು",                13.34, 77.10),
    (27, "Udupi",            "ಉಡುಪಿ",                  13.34, 74.75),
    (28, "Uttara Kannada",   "ಉತ್ತರ ಕನ್ನಡ",             14.80, 74.13),
    (29, "Vijayapura",       "ವಿಜಯಪುರ",                16.83, 75.71),
    (30, "Yadgir",           "ಯಾದಗಿರಿ",                16.77, 77.14),
    (31, "Vijayanagara",     "ವಿಜಯನಗರ",                15.27, 76.46),
]

# Station name stems, paired Latin and Kannada. Combined with district names at
# generation time to produce station unit names.
LOCALITY_STEMS = [
    ("Town",          "ಟೌನ್"),
    ("Rural",         "ಗ್ರಾಮಾಂತರ"),
    ("Market",        "ಮಾರುಕಟ್ಟೆ"),
    ("Extension",     "ವಿಸ್ತರಣೆ"),
    ("Gandhi Nagar",  "ಗಾಂಧಿ ನಗರ"),
    ("Vidya Nagar",   "ವಿದ್ಯಾ ನಗರ"),
    ("Shivaji Nagar", "ಶಿವಾಜಿ ನಗರ"),
    ("Ashok Nagar",   "ಅಶೋಕ ನಗರ"),
    ("Basaveshwara Nagar", "ಬಸವೇಶ್ವರ ನಗರ"),
    ("Jayanagar",     "ಜಯನಗರ"),
    ("Vinoba Nagar",  "ವಿನೋಬಾ ನಗರ"),
    ("Kote",          "ಕೋಟೆ"),
    ("Halli",         "ಹಳ್ಳಿ"),
    ("Bazaar",        "ಬಜಾರ್"),
    ("Industrial Area", "ಕೈಗಾರಿಕಾ ಪ್ರದೇಶ"),
    ("Traffic",       "ಸಂಚಾರ"),
    ("Women",         "ಮಹಿಳಾ"),
    ("Camp",          "ಕ್ಯಾಂಪ್"),
    ("Cantonment",    "ದಂಡು ಪ್ರದೇಶ"),
    ("Ring Road",     "ರಿಂಗ್ ರಸ್ತೆ"),
]

UNIT_TYPES = [
    (1, "Range",          1),
    (2, "District",       2),
    (3, "Sub Division",   3),
    (4, "Police Station", 4),
]

# ---------------------------------------------------------------------------
# Personnel
# ---------------------------------------------------------------------------

# (RankID, RankName, RankAbbr, SeniorityOrder)
RANKS = [
    (1, "Police Constable",              "PC",   1),
    (2, "Head Constable",                "HC",   2),
    (3, "Assistant Sub Inspector",       "ASI",  3),
    (4, "Sub Inspector",                 "SI",   4),
    (5, "Police Sub Inspector",          "PSI",  5),
    (6, "Circle Police Inspector",       "CPI",  6),
    (7, "Deputy Superintendent",         "DySP", 7),
    (8, "Superintendent of Police",      "SP",   8),
]

DESIGNATIONS = [
    (1, "Beat Officer",              1),
    (2, "Station Writer",            2),
    (3, "Investigating Officer",     4),
    (4, "Station House Officer",     5),
    (5, "Circle Inspector",          6),
    (6, "Sub Divisional Officer",    7),
    (7, "District Police Chief",     8),
]

# Ranks that can appear as an investigating or arresting officer.
IO_RANK_IDS = (3, 4, 5, 6)

# ---------------------------------------------------------------------------
# Offence classification
# ---------------------------------------------------------------------------

# CaseCategoryID is the leading digit of CrimeNo.
CASE_CATEGORIES = [
    (1, "Cognizable Crime"),
    (2, "Non Cognizable Crime"),
    (3, "Special and Local Laws"),
    (4, "Motor Vehicle Accident"),
    (5, "Unnatural Death"),
]

GRAVITY = [
    (1, "Heinous",  4),
    (2, "Serious",  3),
    (3, "Ordinary", 2),
    (4, "Minor",    1),
]

CRIME_HEADS = [
    (1, "Offences Against Body",     "ದೇಹದ ವಿರುದ್ಧ ಅಪರಾಧಗಳು"),
    (2, "Offences Against Property", "ಆಸ್ತಿ ವಿರುದ್ಧ ಅಪರಾಧಗಳು"),
    (3, "Offences Against Women",    "ಮಹಿಳೆಯರ ವಿರುದ್ಧ ಅಪರಾಧಗಳು"),
    (4, "Economic Offences",         "ಆರ್ಥಿಕ ಅಪರಾಧಗಳು"),
    (5, "Special and Local Laws",    "ವಿಶೇಷ ಮತ್ತು ಸ್ಥಳೀಯ ಕಾನೂನುಗಳು"),
    (6, "Public Order",              "ಸಾರ್ವಜನಿಕ ಸುವ್ಯವಸ್ಥೆ"),
]

# (CrimeSubHeadID, CrimeHeadID, Name, NameKn)
CRIME_SUBHEADS = [
    (1,  1, "Murder",                    "ಕೊಲೆ"),
    (2,  1, "Attempt to Murder",         "ಕೊಲೆ ಯತ್ನ"),
    (3,  1, "Hurt",                      "ಗಾಯ"),
    (4,  1, "Grievous Hurt",             "ಗಂಭೀರ ಗಾಯ"),
    (5,  2, "Theft of Motor Vehicle",    "ವಾಹನ ಕಳವು"),
    (6,  2, "House Breaking Theft",      "ಮನೆ ಕನ್ನ ಕಳವು"),
    (7,  2, "Ordinary Theft",            "ಸಾಮಾನ್ಯ ಕಳವು"),
    (8,  2, "Robbery",                   "ದರೋಡೆ"),
    (9,  2, "Dacoity",                   "ಸಂಘಟಿತ ದರೋಡೆ"),
    (10, 2, "Cattle Theft",              "ಜಾನುವಾರು ಕಳವು"),
    (11, 3, "Assault on Woman",          "ಮಹಿಳೆಯ ಮೇಲೆ ಹಲ್ಲೆ"),
    (12, 4, "Cheating",                  "ವಂಚನೆ"),
    (13, 4, "Financial Fraud",           "ಹಣಕಾಸು ವಂಚನೆ"),
    (14, 5, "Excise Offence",            "ಅಬಕಾರಿ ಅಪರಾಧ"),
    (15, 5, "Narcotic Substance",        "ಮಾದಕ ವಸ್ತು"),
    (16, 5, "Illegal Mineral Transport", "ಅಕ್ರಮ ಖನಿಜ ಸಾಗಣೆ"),
    (17, 6, "Rioting",                   "ಗಲಭೆ"),
    (18, 6, "Criminal Intimidation",     "ಬೆದರಿಕೆ"),
]

# The July 2024 transition. IPC and CrPC era acts close, BNS era acts open.
BNS_TRANSITION_DATE = "2024-07-01"

# (ActID, ActName, ActAbbr, ActYear, EffectiveFrom, EffectiveTo, Active)
ACTS = [
    (1, "Indian Penal Code, 1860",            "IPC",  1860, "1862-01-01", "2024-06-30", "N"),
    (2, "Bharatiya Nyaya Sanhita, 2023",      "BNS",  2023, "2024-07-01", None,         "Y"),
    (3, "Narcotic Drugs and Psychotropic Substances Act, 1985", "NDPS", 1985, "1985-11-14", None, "Y"),
    (4, "Arms Act, 1959",                     "ARMS", 1959, "1959-01-01", None,         "Y"),
    (5, "Karnataka Excise Act, 1965",         "KEA",  1965, "1966-01-01", None,         "Y"),
    (6, "Karnataka Police Act, 1963",         "KPA",  1963, "1964-01-01", None,         "Y"),
    (7, "Motor Vehicles Act, 1988",           "MVA",  1988, "1989-07-01", None,         "Y"),
    (8, "Information Technology Act, 2000",   "ITA",  2000, "2000-10-17", None,         "Y"),
]

# IPC section, BNS successor section, description, gravity, cognizable, bailable
# The successor mapping is the operative content of Layer 9. It is illustrative
# rather than a legal authority, and the engine reads it from this table rather
# than hard coding it, so correcting an entry is a data change.
IPC_TO_BNS = [
    # (ipc_no, bns_no, description, description_kn, gravity_id, cognizable, bailable)
    ("302", "103", "Murder",                                  "ಕೊಲೆ",                     1, "Y", "N"),
    ("304", "105", "Culpable homicide not amounting to murder","ಕೊಲೆಯಲ್ಲದ ನರಹತ್ಯೆ",        1, "Y", "N"),
    ("307", "109", "Attempt to murder",                       "ಕೊಲೆ ಯತ್ನ",                1, "Y", "N"),
    ("323", "115", "Voluntarily causing hurt",                "ಸ್ವಯಂಪ್ರೇರಿತ ಗಾಯ",          4, "N", "Y"),
    ("324", "118", "Hurt by dangerous weapon",                "ಅಪಾಯಕಾರಿ ಆಯುಧದಿಂದ ಗಾಯ",    3, "Y", "N"),
    ("341", "126", "Wrongful restraint",                      "ಅನ್ಯಾಯದ ತಡೆ",              4, "N", "Y"),
    ("354", "74",  "Assault on woman with intent to outrage modesty", "ಮಹಿಳೆಯ ಮೇಲೆ ಹಲ್ಲೆ", 2, "Y", "N"),
    ("379", "303", "Theft",                                   "ಕಳವು",                     3, "Y", "N"),
    ("380", "305", "Theft in dwelling house",                 "ವಾಸದ ಮನೆಯಲ್ಲಿ ಕಳವು",       3, "Y", "N"),
    ("392", "309", "Robbery",                                 "ದರೋಡೆ",                    2, "Y", "N"),
    ("395", "310", "Dacoity",                                 "ಸಂಘಟಿತ ದರೋಡೆ",             1, "Y", "N"),
    ("411", "317", "Dishonestly receiving stolen property",   "ಕಳವು ಮಾಲು ಸ್ವೀಕಾರ",        3, "Y", "N"),
    ("420", "318", "Cheating and dishonestly inducing delivery of property", "ವಂಚನೆ",     2, "Y", "N"),
    ("427", "324", "Mischief causing damage",                 "ಹಾನಿ ಉಂಟುಮಾಡುವ ಕಿಡಿಗೇಡಿತನ",4, "Y", "Y"),
    ("457", "331", "Lurking house trespass by night",         "ರಾತ್ರಿ ಮನೆ ಅತಿಕ್ರಮಣ",       2, "Y", "N"),
    ("506", "351", "Criminal intimidation",                   "ಬೆದರಿಕೆ",                  4, "Y", "Y"),
    ("143", "189", "Unlawful assembly",                       "ಕಾನೂನುಬಾಹಿರ ಸಭೆ",          4, "Y", "Y"),
    ("147", "191", "Rioting",                                 "ಗಲಭೆ",                     3, "Y", "Y"),
]

# Sections on acts unaffected by the transition.
# (ActAbbr, SectionNo, Description, DescriptionKn, gravity, cognizable, bailable)
OTHER_SECTIONS = [
    ("NDPS", "20",   "Contravention in relation to cannabis",   "ಗಾಂಜಾ ಸಂಬಂಧಿತ ಉಲ್ಲಂಘನೆ",   2, "Y", "N"),
    ("NDPS", "22",   "Contravention in relation to psychotropic substance", "ಮಾದಕ ವಸ್ತು ಉಲ್ಲಂಘನೆ", 2, "Y", "N"),
    ("ARMS", "25",   "Possession of prohibited arms",           "ನಿಷೇಧಿತ ಆಯುಧ ಹೊಂದಿರುವಿಕೆ", 2, "Y", "N"),
    ("KEA",  "32",   "Illicit possession of liquor",            "ಅಕ್ರಮ ಮದ್ಯ ಸಂಗ್ರಹ",        3, "Y", "Y"),
    ("KEA",  "34",   "Illicit transport of liquor",             "ಅಕ್ರಮ ಮದ್ಯ ಸಾಗಣೆ",         3, "Y", "Y"),
    ("KPA",  "98",   "Unlawful transport of minor mineral",     "ಅಕ್ರಮ ಖನಿಜ ಸಾಗಣೆ",         3, "Y", "Y"),
    ("MVA",  "184",  "Driving dangerously",                     "ಅಪಾಯಕಾರಿ ಚಾಲನೆ",           4, "Y", "Y"),
    ("ITA",  "66C",  "Identity theft",                          "ಗುರುತಿನ ಕಳವು",             3, "Y", "Y"),
    ("ITA",  "66D",  "Cheating by personation using computer",  "ಗಣಕ ಬಳಸಿ ವಂಚನೆ",           3, "Y", "Y"),
]

# ---------------------------------------------------------------------------
# Modus operandi families
# ---------------------------------------------------------------------------
#
# Each offender is assigned one primary family and mostly stays in it. This is
# what gives Layer 3e something real to find. The BriefFacts templates within a
# family share vocabulary and structure, so embeddings cluster by family, while
# the slot fills vary enough that the text is never identical.
#
# ipc keys reference IPC_TO_BNS by IPC section number. The generator swaps them
# for the BNS successor when the case date falls after the transition, which is
# what makes Layer 9 testable.

MO_FAMILIES = {
    "two_wheeler_theft": {
        "subhead": 5, "gravity": 3, "category": 1,
        "ipc": ["379"],
        "hours": (20, 30),          # 20:00 to 06:00, wraps past midnight
        "en": [
            "Complainant had parked his {vehicle} bearing registration {regno} in front of {place} at about {time} hours. On returning he found the vehicle missing. Unknown accused has broken the handle lock and committed theft of the vehicle worth Rs {value}.",
            "The complainant parked his {vehicle} near {place} and went inside. At about {time} hours he found the vehicle had been stolen. The handle lock was found broken and lying at the spot. Value of the vehicle is Rs {value}.",
            "During night hours unknown persons committed theft of a {vehicle} bearing number {regno} parked in the open compound of {place}. Accused appears to have used a duplicate key. Property value Rs {value}.",
        ],
        "kn": [
            "ದೂರುದಾರರು ತಮ್ಮ {vehicle} ವಾಹನ ಸಂಖ್ಯೆ {regno} ಅನ್ನು {place} ಬಳಿ ನಿಲ್ಲಿಸಿದ್ದು, {time} ಗಂಟೆ ಸುಮಾರಿಗೆ ವಾಹನ ಕಾಣೆಯಾಗಿರುತ್ತದೆ. ಆರೋಪಿಯು ಹ್ಯಾಂಡಲ್ ಲಾಕ್ ಮುರಿದು ಕಳವು ಮಾಡಿರುತ್ತಾನೆ. ಮಾಲಿನ ಬೆಲೆ ರೂ {value}.",
        ],
    },
    "chain_snatching": {
        "subhead": 8, "gravity": 2, "category": 1,
        "ipc": ["392"],
        "hours": (6, 11),
        "en": [
            "The complainant was walking near {place} at about {time} hours. Two persons who came on a motorcycle snatched the gold chain weighing {weight} grams from her neck and sped away towards {direction}. Value of property Rs {value}.",
            "While the complainant was returning from the temple near {place}, the pillion rider of a motorcycle pulled the mangalsutra from her neck and escaped. The accused wore a full face helmet. Gold weighing {weight} grams valued at Rs {value} was taken.",
            "Two unknown persons on a black motorcycle approached the complainant near {place} at {time} hours, snatched her gold chain and fled. The complainant sustained minor abrasion on the neck. Property value Rs {value}.",
        ],
        "kn": [
            "ದೂರುದಾರರು {place} ಬಳಿ ನಡೆದುಕೊಂಡು ಹೋಗುತ್ತಿದ್ದಾಗ, ಮೋಟಾರ್ ಸೈಕಲ್‌ನಲ್ಲಿ ಬಂದ ಇಬ್ಬರು ವ್ಯಕ್ತಿಗಳು ಕೊರಳಿನಲ್ಲಿದ್ದ {weight} ಗ್ರಾಂ ಚಿನ್ನದ ಸರವನ್ನು ಕಿತ್ತುಕೊಂಡು ಪರಾರಿಯಾಗಿರುತ್ತಾರೆ. ಮಾಲಿನ ಬೆಲೆ ರೂ {value}.",
        ],
    },
    "house_break_night": {
        "subhead": 6, "gravity": 2, "category": 1,
        "ipc": ["457", "380"],
        "hours": (23, 29),
        "en": [
            "The complainant had locked the house at {place} and gone to his native place. On return he found the rear door broken open. Unknown accused entered the house during night hours, broke open the almirah and committed theft of gold ornaments and cash totalling Rs {value}.",
            "During the intervening night unknown persons removed the window grill of the house situated at {place}, entered inside and committed theft of gold ornaments weighing {weight} grams and cash. Total property value Rs {value}.",
            "Accused persons gained entry into the locked house at {place} by breaking the latch of the back door using an iron rod, ransacked the bedroom and took away valuables worth Rs {value}.",
        ],
        "kn": [
            "ದೂರುದಾರರು {place} ನಲ್ಲಿರುವ ತಮ್ಮ ಮನೆಗೆ ಬೀಗ ಹಾಕಿ ಊರಿಗೆ ಹೋಗಿದ್ದರು. ವಾಪಸ್ ಬಂದಾಗ ಹಿಂಬಾಗಿಲು ಮುರಿದಿರುವುದು ಕಂಡುಬಂದಿದೆ. ಆರೋಪಿಗಳು ರಾತ್ರಿ ವೇಳೆ ಮನೆ ಪ್ರವೇಶಿಸಿ ಬೀರುವನ್ನು ಮುರಿದು ರೂ {value} ಮೌಲ್ಯದ ಚಿನ್ನಾಭರಣ ಮತ್ತು ನಗದು ಕಳವು ಮಾಡಿರುತ್ತಾರೆ.",
        ],
    },
    "mobile_snatching": {
        "subhead": 8, "gravity": 3, "category": 1,
        "ipc": ["392"],
        "hours": (17, 23),
        "en": [
            "The complainant was speaking on his mobile phone standing near {place} when an unknown person snatched the handset from his hand and ran towards {direction}. The phone is a {brand} valued at Rs {value}.",
            "At about {time} hours near {place} the accused riding pillion on a motorcycle snatched the mobile phone of the complainant and escaped. Handset make {brand}, value Rs {value}.",
        ],
        "kn": [
            "ದೂರುದಾರರು {place} ಬಳಿ ನಿಂತು ಮೊಬೈಲ್‌ನಲ್ಲಿ ಮಾತನಾಡುತ್ತಿದ್ದಾಗ ಅಪರಿಚಿತ ವ್ಯಕ್ತಿ ಫೋನ್ ಕಿತ್ತುಕೊಂಡು ಓಡಿಹೋಗಿರುತ್ತಾನೆ. ಫೋನ್ ಬೆಲೆ ರೂ {value}.",
        ],
    },
    "shop_burglary": {
        "subhead": 6, "gravity": 2, "category": 1,
        "ipc": ["457", "380"],
        "hours": (0, 5),
        "en": [
            "Unknown accused broke the shutter lock of the shop of the complainant situated at {place} during night hours and committed theft of cash from the counter and goods worth Rs {value}.",
            "The complainant closed his provision store at {place} at {time} hours. In the early morning it was found that the rolling shutter had been prised open with a crowbar and stock and cash totalling Rs {value} was missing.",
        ],
        "kn": [
            "{place} ನಲ್ಲಿರುವ ದೂರುದಾರರ ಅಂಗಡಿಯ ಶಟರ್ ಬೀಗವನ್ನು ಅಪರಿಚಿತ ಆರೋಪಿಗಳು ರಾತ್ರಿ ವೇಳೆ ಮುರಿದು ರೂ {value} ಮೌಲ್ಯದ ನಗದು ಮತ್ತು ಸಾಮಗ್ರಿಗಳನ್ನು ಕಳವು ಮಾಡಿರುತ್ತಾರೆ.",
        ],
    },
    "cattle_theft": {
        "subhead": 10, "gravity": 3, "category": 1,
        "ipc": ["379"],
        "hours": (1, 5),
        "en": [
            "The complainant had tied his cattle in the shed adjoining his house at {place}. During the night the accused untied and took away {count} head of cattle valued at Rs {value} in a goods vehicle.",
            "Unknown persons loaded {count} cattle belonging to the complainant from the grazing ground near {place} into a lorry and transported them away. Value of the cattle is Rs {value}.",
        ],
        "kn": [
            "ದೂರುದಾರರು {place} ನಲ್ಲಿರುವ ತಮ್ಮ ಮನೆಯ ಕೊಟ್ಟಿಗೆಯಲ್ಲಿ ಜಾನುವಾರುಗಳನ್ನು ಕಟ್ಟಿದ್ದರು. ರಾತ್ರಿ ವೇಳೆ ಆರೋಪಿಗಳು {count} ಜಾನುವಾರುಗಳನ್ನು ಬಿಚ್ಚಿಕೊಂಡು ಹೋಗಿರುತ್ತಾರೆ. ಬೆಲೆ ರೂ {value}.",
        ],
    },
    "hurt_affray": {
        "subhead": 3, "gravity": 4, "category": 1,
        "ipc": ["323", "324", "341"],
        "hours": (16, 23),
        "en": [
            "There was a quarrel between the complainant and the accused over {dispute} near {place}. The accused abused the complainant in filthy language, restrained him and assaulted him with a wooden club causing bleeding injury on the head.",
            "On {time} hours near {place} the accused picked up a quarrel with the complainant regarding {dispute}, caught hold of his collar and assaulted him with hands and a soda bottle causing injuries.",
            "The accused, in furtherance of an old dispute over {dispute}, waylaid the complainant near {place}, obstructed his path and beat him with a stick causing a fracture.",
        ],
        "kn": [
            "{place} ಬಳಿ ದೂರುದಾರರು ಮತ್ತು ಆರೋಪಿಯ ನಡುವೆ {dispute} ವಿಚಾರವಾಗಿ ಜಗಳ ನಡೆದಿದೆ. ಆರೋಪಿಯು ಅವಾಚ್ಯ ಶಬ್ದಗಳಿಂದ ನಿಂದಿಸಿ ದೊಣ್ಣೆಯಿಂದ ಹಲ್ಲೆ ಮಾಡಿ ಗಾಯಗೊಳಿಸಿರುತ್ತಾನೆ.",
        ],
    },
    "murder": {
        "subhead": 1, "gravity": 1, "category": 1,
        "ipc": ["302"],
        "hours": (18, 28),
        "en": [
            "On account of a long standing dispute over {dispute}, the accused waylaid the deceased near {place} at about {time} hours and assaulted him on the head with a chopper resulting in his death on the spot.",
            "The deceased was found lying in a pool of blood near {place}. Investigation reveals that the accused, over a dispute regarding {dispute}, stabbed the deceased with a knife causing fatal injuries.",
        ],
        "kn": [
            "{dispute} ವಿಚಾರವಾಗಿ ಬಹುದಿನಗಳ ವೈಷಮ್ಯದ ಹಿನ್ನೆಲೆಯಲ್ಲಿ ಆರೋಪಿಯು {place} ಬಳಿ ಮೃತರನ್ನು ತಡೆದು ಮಾರಕಾಯುಧದಿಂದ ಹಲ್ಲೆ ಮಾಡಿ ಸಾವಿಗೆ ಕಾರಣನಾಗಿರುತ್ತಾನೆ.",
        ],
    },
    "highway_dacoity": {
        "subhead": 9, "gravity": 1, "category": 1,
        "ipc": ["395"],
        "hours": (22, 28),
        "en": [
            "A gang of five to six persons armed with long weapons stopped the goods vehicle of the complainant on the highway near {place} at about {time} hours, threatened the driver and cleaner and took away cash and the consignment valued at Rs {value}.",
            "The complainant was travelling in his car near {place} when a group of unknown persons blocked the road with a tempo, assaulted the occupants and robbed cash, ornaments and mobile phones worth Rs {value}.",
        ],
        "kn": [
            "{place} ಬಳಿ ಹೆದ್ದಾರಿಯಲ್ಲಿ ಐದಾರು ಜನರ ಗುಂಪು ಮಾರಕಾಯುಧಗಳೊಂದಿಗೆ ದೂರುದಾರರ ವಾಹನವನ್ನು ತಡೆದು ಬೆದರಿಸಿ ರೂ {value} ಮೌಲ್ಯದ ನಗದು ಮತ್ತು ಸರಕನ್ನು ದೋಚಿಕೊಂಡು ಹೋಗಿರುತ್ತಾರೆ.",
        ],
    },
    "chit_fund_cheating": {
        "subhead": 12, "gravity": 2, "category": 1,
        "ipc": ["420"],
        "hours": (10, 17),
        "en": [
            "The accused, representing himself as the proprietor of a finance establishment at {place}, collected deposits from the complainant and other members of the public promising monthly returns, and thereafter closed the office and absconded. Total amount cheated Rs {value}.",
            "The accused induced the complainant to invest in a chit scheme operated from {place}, collected Rs {value} in instalments and failed to pay the prize amount on maturity, thereby cheating the complainant.",
        ],
        "kn": [
            "ಆರೋಪಿಯು {place} ನಲ್ಲಿ ಹಣಕಾಸು ಸಂಸ್ಥೆಯ ಮಾಲೀಕನೆಂದು ಹೇಳಿಕೊಂಡು ದೂರುದಾರರಿಂದ ಠೇವಣಿ ಸಂಗ್ರಹಿಸಿ, ನಂತರ ಕಚೇರಿ ಮುಚ್ಚಿ ಪರಾರಿಯಾಗಿರುತ್ತಾನೆ. ವಂಚಿಸಿದ ಮೊತ್ತ ರೂ {value}.",
        ],
    },
    "card_skimming": {
        "subhead": 13, "gravity": 3, "category": 1,
        "ipc": ["420"],
        "extra": [("ITA", "66C")],
        "hours": (9, 21),
        "en": [
            "The complainant used the ATM kiosk at {place}. Subsequently an amount of Rs {value} was withdrawn from his account in {count} transactions without his knowledge. It appears the accused installed a skimming device and captured the card data.",
            "Unknown accused obtained the card details of the complainant and made online transactions totalling Rs {value}. The complainant had used his card last at {place}.",
        ],
        "kn": [
            "ದೂರುದಾರರು {place} ನಲ್ಲಿನ ಎಟಿಎಂ ಬಳಸಿದ್ದು, ನಂತರ ಅವರ ಖಾತೆಯಿಂದ ರೂ {value} ಹಣ ಅವರ ಅರಿವಿಲ್ಲದೆ ವರ್ಗಾವಣೆಯಾಗಿರುತ್ತದೆ.",
        ],
    },
    "illicit_liquor": {
        "subhead": 14, "gravity": 3, "category": 3,
        "ipc": [],
        "extra": [("KEA", "32"), ("KEA", "34")],
        "hours": (19, 26),
        "en": [
            "On credible information a raid was conducted near {place} at about {time} hours. The accused was found transporting {count} boxes of Indian made liquor without a valid permit in a {vehicle}. Contraband valued at Rs {value} was seized.",
            "During patrolling near {place} the accused was found in possession of {count} litres of illicitly distilled arrack kept for sale. The contraband and the vehicle bearing number {regno} were seized under panchanama.",
        ],
        "kn": [
            "ಖಚಿತ ಮಾಹಿತಿಯ ಮೇರೆಗೆ {place} ಬಳಿ ದಾಳಿ ನಡೆಸಲಾಯಿತು. ಆರೋಪಿಯು ಪರವಾನಗಿ ಇಲ್ಲದೆ {count} ಪೆಟ್ಟಿಗೆ ಮದ್ಯವನ್ನು ಸಾಗಿಸುತ್ತಿದ್ದು, ರೂ {value} ಮೌಲ್ಯದ ಮಾಲನ್ನು ವಶಪಡಿಸಿಕೊಳ್ಳಲಾಗಿದೆ.",
        ],
    },
    "ndps_ganja": {
        "subhead": 15, "gravity": 2, "category": 3,
        "ipc": [],
        "extra": [("NDPS", "20")],
        "hours": (8, 22),
        "en": [
            "Acting on information the staff conducted a check near {place}. The accused was found in possession of {weight} kilograms of dried ganja concealed in a gunny bag, for which he could produce no authorisation. Contraband seized in the presence of panchas.",
            "During vehicle checking near {place} the accused travelling in a {vehicle} bearing number {regno} was found transporting {weight} kilograms of ganja. The substance tested positive on field kit and was seized.",
        ],
        "kn": [
            "ಮಾಹಿತಿಯ ಮೇರೆಗೆ {place} ಬಳಿ ತಪಾಸಣೆ ನಡೆಸಿದಾಗ ಆರೋಪಿಯು {weight} ಕಿಲೋ ಗಾಂಜಾವನ್ನು ಗೋಣಿಚೀಲದಲ್ಲಿ ಇಟ್ಟುಕೊಂಡಿರುವುದು ಕಂಡುಬಂದಿದ್ದು, ವಶಪಡಿಸಿಕೊಳ್ಳಲಾಗಿದೆ.",
        ],
    },
    "sand_smuggling": {
        "subhead": 16, "gravity": 3, "category": 3,
        "ipc": [],
        "extra": [("KPA", "98")],
        "hours": (0, 6),
        "en": [
            "During night patrolling near the river bed at {place} a {vehicle} bearing registration {regno} was found transporting sand without a valid permit. The vehicle and {count} units of sand valued at Rs {value} were seized.",
            "The accused was found illegally extracting and transporting minor mineral from the river bed near {place} using a {vehicle}. No royalty receipt or transport permit was produced.",
        ],
        "kn": [
            "{place} ಬಳಿ ನದಿ ಪಾತ್ರದಲ್ಲಿ ರಾತ್ರಿ ಗಸ್ತು ವೇಳೆ ಪರವಾನಗಿ ಇಲ್ಲದೆ ಮರಳು ಸಾಗಿಸುತ್ತಿದ್ದ ವಾಹನ ಸಂಖ್ಯೆ {regno} ಅನ್ನು ವಶಪಡಿಸಿಕೊಳ್ಳಲಾಗಿದೆ.",
        ],
    },
}

# ---------------------------------------------------------------------------
# BriefFacts slot fills
# ---------------------------------------------------------------------------

VEHICLES = [
    "Hero Splendor motorcycle", "Bajaj Pulsar motorcycle", "Honda Activa scooter",
    "TVS XL moped", "Royal Enfield motorcycle", "Mahindra Bolero pickup",
    "Tata Ace goods vehicle", "Ashok Leyland lorry", "Maruti Omni van",
    "Yamaha FZ motorcycle", "Tata 407 lorry", "auto rickshaw",
]

BRANDS = ["Redmi Note", "Samsung Galaxy M", "Realme C", "Vivo Y", "Oppo A", "iPhone SE"]

DIRECTIONS = ["the bus stand", "the highway", "the market road", "the railway gate",
              "the ring road", "the village outskirts", "the flyover"]

DISPUTES = [
    "a boundary of agricultural land", "an old money transaction",
    "flow of drain water", "parking of a vehicle", "a village festival collection",
    "grazing of cattle", "a share in ancestral property", "supply of water to a field",
    "a previous quarrel between the families", "a wage payment",
]

PLACE_TYPES = [
    "the bus stand", "the vegetable market", "the government hospital",
    "the temple street", "the main road junction", "the railway station",
    "the taluk office", "the sugar factory road", "the housing board colony",
    "the APMC yard", "the college ground", "the petrol bunk",
]

COURT_NAMES = [
    "JMFC Court", "Principal Civil Judge and JMFC Court", "Sessions Court",
    "Additional Sessions Court", "Special Court for NDPS cases",
]

# ---------------------------------------------------------------------------
# Name pools
# ---------------------------------------------------------------------------
#
# Ordered roughly by real world frequency. The generator samples with a Zipf
# like weight over position, which produces the heavy skew that makes inverse
# name frequency weighting in Layer 4 worth doing. Matching on Manjunath is
# genuinely weaker evidence than matching on Yallappa, and the corpus has to
# reflect that or the correction cannot be demonstrated.

GIVEN_NAMES_MALE = [
    ("Manjunath",     "ಮಂಜುನಾಥ"),
    ("Ramesh",        "ರಮೇಶ"),
    ("Suresh",        "ಸುರೇಶ"),
    ("Shivakumar",    "ಶಿವಕುಮಾರ"),
    ("Basavaraj",     "ಬಸವರಾಜ"),
    ("Mahesh",        "ಮಹೇಶ"),
    ("Nagaraj",       "ನಾಗರಾಜ"),
    ("Ravi",          "ರವಿ"),
    ("Prakash",       "ಪ್ರಕಾಶ"),
    ("Kumar",         "ಕುಮಾರ"),
    ("Santosh",       "ಸಂತೋಷ"),
    ("Ganesh",        "ಗಣೇಶ"),
    ("Venkatesh",     "ವೆಂಕಟೇಶ"),
    ("Umesh",         "ಉಮೇಶ"),
    ("Girish",        "ಗಿರೀಶ"),
    ("Harish",        "ಹರೀಶ"),
    ("Lokesh",        "ಲೋಕೇಶ"),
    ("Naveen",        "ನವೀನ"),
    ("Chandru",       "ಚಂದ್ರು"),
    ("Mallikarjuna",  "ಮಲ್ಲಿಕಾರ್ಜುನ"),
    ("Siddaraju",     "ಸಿದ್ದರಾಜು"),
    ("Yallappa",      "ಯಲ್ಲಪ್ಪ"),
    ("Hanumantha",    "ಹನುಮಂತ"),
    ("Srinivas",      "ಶ್ರೀನಿವಾಸ"),
    ("Anand",         "ಆನಂದ"),
    ("Praveen",       "ಪ್ರವೀಣ"),
    ("Vijay",         "ವಿಜಯ"),
    ("Kiran",         "ಕಿರಣ"),
    ("Rakesh",        "ರಾಕೇಶ"),
    ("Sunil",         "ಸುನೀಲ"),
    ("Dinesh",        "ದಿನೇಶ"),
    ("Gopal",         "ಗೋಪಾಲ"),
    ("Shankar",       "ಶಂಕರ"),
    ("Somashekar",    "ಸೋಮಶೇಖರ"),
    ("Devaraj",       "ದೇವರಾಜ"),
    ("Nanjundappa",   "ನಂಜುಂಡಪ್ಪ"),
    ("Puttaswamy",    "ಪುಟ್ಟಸ್ವಾಮಿ"),
    ("Rajanna",       "ರಾಜಣ್ಣ"),
    ("Chandrashekar", "ಚಂದ್ರಶೇಖರ"),
    ("Ashok",         "ಅಶೋಕ"),
    ("Arun",          "ಅರುಣ"),
    ("Deepak",        "ದೀಪಕ"),
    ("Nagesh",        "ನಾಗೇಶ"),
    ("Raju",          "ರಾಜು"),
    ("Madhu",         "ಮಧು"),
    ("Prasad",        "ಪ್ರಸಾದ"),
    ("Gangadhar",     "ಗಂಗಾಧರ"),
    ("Veeresh",       "ವೀರೇಶ"),
    ("Sharanappa",    "ಶರಣಪ್ಪ"),
    ("Mahadev",       "ಮಹಾದೇವ"),
    ("Ningaraj",      "ನಿಂಗರಾಜ"),
    ("Basappa",       "ಬಸಪ್ಪ"),
    ("Krishnamurthy", "ಕೃಷ್ಣಮೂರ್ತಿ"),
    ("Shivanna",      "ಶಿವಣ್ಣ"),
    ("Thimmaraju",    "ತಿಮ್ಮರಾಜು"),
    ("Erappa",        "ಈರಪ್ಪ"),
    ("Doddabasappa",  "ದೊಡ್ಡಬಸಪ್ಪ"),
    ("Ayyappa",       "ಅಯ್ಯಪ್ಪ"),
]

GIVEN_NAMES_FEMALE = [
    ("Lakshmi",        "ಲಕ್ಷ್ಮಿ"),
    ("Savitha",        "ಸವಿತಾ"),
    ("Geetha",         "ಗೀತಾ"),
    ("Kavitha",        "ಕವಿತಾ"),
    ("Roopa",          "ರೂಪಾ"),
    ("Sunitha",        "ಸುನೀತಾ"),
    ("Nagaratna",      "ನಾಗರತ್ನ"),
    ("Shobha",         "ಶೋಭಾ"),
    ("Rekha",          "ರೇಖಾ"),
    ("Pushpa",         "ಪುಷ್ಪಾ"),
    ("Manjula",        "ಮಂಜುಳಾ"),
    ("Bhagya",         "ಭಾಗ್ಯ"),
    ("Shwetha",        "ಶ್ವೇತಾ"),
    ("Ambika",         "ಅಂಬಿಕಾ"),
    ("Vijayalakshmi",  "ವಿಜಯಲಕ್ಷ್ಮಿ"),
    ("Sharada",        "ಶಾರದಾ"),
    ("Yashoda",        "ಯಶೋದಾ"),
    ("Renuka",         "ರೇಣುಕಾ"),
]

FATHER_NAMES = [
    ("Basappa",     "ಬಸಪ್ಪ"),
    ("Krishnappa",  "ಕೃಷ್ಣಪ್ಪ"),
    ("Ningappa",    "ನಿಂಗಪ್ಪ"),
    ("Shivappa",    "ಶಿವಪ್ಪ"),
    ("Rangappa",    "ರಂಗಪ್ಪ"),
    ("Siddappa",    "ಸಿದ್ದಪ್ಪ"),
    ("Mallappa",    "ಮಲ್ಲಪ್ಪ"),
    ("Hanumappa",   "ಹನುಮಪ್ಪ"),
    ("Nagappa",     "ನಾಗಪ್ಪ"),
    ("Timmappa",    "ತಿಮ್ಮಪ್ಪ"),
    ("Chennappa",   "ಚೆನ್ನಪ್ಪ"),
    ("Gurappa",     "ಗುರಪ್ಪ"),
    ("Muniyappa",   "ಮುನಿಯಪ್ಪ"),
    ("Puttappa",    "ಪುಟ್ಟಪ್ಪ"),
    ("Doddappa",    "ದೊಡ್ಡಪ್ಪ"),
    ("Boregowda",   "ಬೋರೇಗೌಡ"),
    ("Kempegowda",  "ಕೆಂಪೇಗೌಡ"),
    ("Ramegowda",   "ರಾಮೇಗೌಡ"),
    ("Chikkegowda", "ಚಿಕ್ಕೇಗೌಡ"),
    ("Lingappa",    "ಲಿಂಗಪ್ಪ"),
    ("Somappa",     "ಸೋಮಪ್ಪ"),
    ("Eranna",      "ಈರಣ್ಣ"),
    ("Mariyappa",   "ಮಾರಿಯಪ್ಪ"),
    ("Venkatappa",  "ವೆಂಕಟಪ್ಪ"),
    ("Yamanappa",   "ಯಮನಪ್ಪ"),
    ("Sangappa",    "ಸಂಗಪ್ಪ"),
    ("Fakirappa",   "ಫಕೀರಪ್ಪ"),
    ("Durgappa",    "ದುರ್ಗಪ್ಪ"),
]

# Locality and trade monikers. In Karnataka station practice these are often
# the only handle a station has on a man, and they appear inside AccusedName
# with or without the given name. They are strong evidence when present and
# they are exactly what a lexical matcher throws away.
MONIKERS = [
    ("Kadu",     "ಕಾಡು"),      # forest
    ("Dodda",    "ದೊಡ್ಡ"),      # big
    ("Chikka",   "ಚಿಕ್ಕ"),       # small
    ("Gundu",    "ಗುಂಡು"),      # stout
    ("Pailwan",  "ಪೈಲ್ವಾನ್"),    # wrestler
    ("Auto",     "ಆಟೋ"),
    ("Lorry",    "ಲಾರಿ"),
    ("Kuri",     "ಕುರಿ"),        # sheep
    ("Kabbina",  "ಕಬ್ಬಿನ"),      # sugarcane
    ("Bidi",     "ಬೀಡಿ"),
    ("Chota",    "ಛೋಟಾ"),
    ("Kempu",    "ಕೆಂಪು"),       # red
    ("Uddha",    "ಉದ್ದ"),        # tall
    ("Battale",  "ಬಟ್ಟಲೆ"),
]

# ---------------------------------------------------------------------------
# Name pool expansion
# ---------------------------------------------------------------------------
#
# The pools above hold 58 given and 28 patronymic forms, which is the fixture
# the project was measured on. That is far narrower than reality. Karnataka
# carries thousands of distinct names, and a narrow vocabulary makes every
# phonetic block enormous, floods the candidate set and collapses the base
# rate. Precision pays for all of it.
#
# So the pool is expandable, and the effect is measured rather than argued.
# `--name-pool N` composes additional names until the vocabulary reaches N.
#
# Composition is syllable based and paired. A name is built as
# syllable + syllable + suffix, and both the Latin and the Kannada forms are
# assembled from the same parts in the same order, so the cross script
# correspondence is exact by construction rather than by transliteration luck.
#
# Every suffix begins with a consonant. A Kannada dependent vowel sign replaces
# the inherent vowel of the character before it, so a suffix starting with a
# matra would attach to the previous syllable and break the correspondence.
# Consonant initial suffixes concatenate cleanly on both sides.

SYLLABLES = [
    ("ka", "ಕ"), ("ki", "ಕಿ"), ("ku", "ಕು"),
    ("ga", "ಗ"), ("gi", "ಗಿ"), ("gu", "ಗು"),
    ("cha", "ಚ"), ("chi", "ಚಿ"),
    ("ja", "ಜ"), ("ji", "ಜಿ"),
    ("ta", "ತ"), ("ti", "ತಿ"), ("tu", "ತು"),
    ("da", "ದ"), ("di", "ದಿ"), ("du", "ದು"),
    ("na", "ನ"), ("ni", "ನಿ"), ("nu", "ನು"),
    ("pa", "ಪ"), ("pi", "ಪಿ"), ("pu", "ಪು"),
    ("ba", "ಬ"), ("bi", "ಬಿ"), ("bu", "ಬು"),
    ("ma", "ಮ"), ("mi", "ಮಿ"), ("mu", "ಮು"),
    ("ya", "ಯ"), ("ra", "ರ"), ("ri", "ರಿ"), ("ru", "ರು"),
    ("la", "ಲ"), ("li", "ಲಿ"), ("lu", "ಲು"),
    ("va", "ವ"), ("vi", "ವಿ"),
    ("sha", "ಶ"), ("shi", "ಶಿ"),
    ("sa", "ಸ"), ("si", "ಸಿ"), ("su", "ಸು"),
    ("ha", "ಹ"), ("hi", "ಹಿ"), ("hu", "ಹು"),
]

GIVEN_SUFFIXES = [
    ("raja", "ರಾಜ"), ("kumara", "ಕುಮಾರ"), ("murti", "ಮೂರ್ತಿ"),
    ("natha", "ನಾಥ"), ("prasada", "ಪ್ರಸಾದ"), ("shekara", "ಶೇಖರ"),
    ("svami", "ಸ್ವಾಮಿ"), ("dhara", "ಧರ"), ("pala", "ಪಾಲ"),
    ("chandra", "ಚಂದ್ರ"), ("kanta", "ಕಾಂತ"), ("vira", "ವೀರ"),
]

FATHER_SUFFIXES = [
    ("ppa", "ಪ್ಪ"), ("nna", "ಣ್ಣ"), ("gauda", "ಗೌಡ"),
    ("aiah", "ಯ್ಯ"), ("shetti", "ಶೆಟ್ಟಿ"), ("raja", "ರಾಜ"),
    ("murti", "ಮೂರ್ತಿ"), ("svami", "ಸ್ವಾಮಿ"),
]


def expand_pool(base, target, suffixes, seed_offset=0):
    """Grow a paired name pool to `target` distinct entries, deterministically.

    Returns the base pool unchanged when it already meets the target, so the
    default corpus is bit for bit identical to every figure published before
    this parameter existed.
    """
    pool = list(base)
    if len(pool) >= target:
        return pool
    seen = {latin for latin, _ in pool}
    # Deterministic ordered walk rather than sampling, so the same target
    # always yields the same pool on any machine.
    for suffix_index, (suf_la, suf_kn) in enumerate(suffixes):
        for i, (a_la, a_kn) in enumerate(SYLLABLES):
            for j, (b_la, b_kn) in enumerate(SYLLABLES):
                if (i + j + suffix_index + seed_offset) % 2:
                    continue
                latin = (a_la + b_la + suf_la).capitalize()
                if latin in seen:
                    continue
                seen.add(latin)
                pool.append((latin, a_kn + b_kn + suf_kn))
                if len(pool) >= target:
                    return pool
    # Second pass without the parity filter, if the first was not enough.
    for suf_la, suf_kn in suffixes:
        for a_la, a_kn in SYLLABLES:
            for b_la, b_kn in SYLLABLES:
                latin = (a_la + b_la + suf_la).capitalize()
                if latin in seen:
                    continue
                seen.add(latin)
                pool.append((latin, a_kn + b_kn + suf_kn))
                if len(pool) >= target:
                    return pool
    return pool


# Vocabulary of the shipped fixture, given plus patronymic forms.
BASE_VOCABULARY = len(GIVEN_NAMES_MALE) + len(FATHER_NAMES)

GENDERS = {1: "Male", 2: "Female"}

ARREST_PLACES = [
    "the bus stand", "his residence", "the taluk border check post",
    "the vegetable market", "the railway station", "the highway toll gate",
    "the village outskirts", "a lodge in the town",
]

# Values used for the columns that exist in the schema, are generated for
# fidelity, and are never read by the engine. See docs/ethics.md section 5 and
# engine/policy.py for the guard that enforces that.
CASTE_ID_RANGE = (1, 40)
RELIGION_ID_RANGE = (1, 7)
OCCUPATION_ID_RANGE = (1, 25)
