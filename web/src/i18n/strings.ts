/**
 * Kannada for the interface chrome.
 *
 * Scope, stated once and enforced by what is in this file. Navigation labels,
 * panel titles, table column headers, status words, button text and the audit
 * strip keys are translated. Explanatory prose is not, and neither is anything
 * the engine produced.
 *
 * Why prose is excluded. The panel notes are the strongest thing on this
 * product, they carry the argument, and a machine assisted rendering of a
 * technical argument into Kannada would be worse than English for a reader who
 * has both. Translating them properly is a job for a Kannada speaking domain
 * reviewer, and that has not happened, so it is not claimed. `/status` says so
 * in the same words.
 *
 * What must never appear in this file. Crime numbers, AMIDs, identity ids,
 * metrics, thresholds, SQL, file paths and timestamps. Those are data, they
 * come out of the engine, and a translated identifier is a wrong identifier.
 * The lookup is keyed by the exact English string, so a figure passes through
 * untouched by construction, never having a key.
 *
 * A missing key falls through to English. That is deliberate. A half rendered
 * screen in two languages is honest about its coverage. A placeholder is not.
 */

export type Language = 'en' | 'kn'

export const LANGUAGES: Array<{ code: Language; label: string; native: string }> = [
  { code: 'en', label: 'English', native: 'English' },
  { code: 'kn', label: 'Kannada', native: 'ಕನ್ನಡ' },
]

/**
 * English chrome string to Kannada. Keys are the literal strings the screens
 * already pass to Panel, DataTable, StatusPill, Metric and the rail.
 */
export const KN: Record<string, string> = {
  /* ---- masthead and identity ---------------------------------------- */
  'Karnataka State Police': 'ಕರ್ನಾಟಕ ರಾಜ್ಯ ಪೊಲೀಸ್',
  'State Crime Records Bureau': 'ರಾಜ್ಯ ಅಪರಾಧ ದಾಖಲೆಗಳ ಬ್ಯೂರೊ',
  Language: 'ಭಾಷೆ',
  Role: 'ಪಾತ್ರ',
  District: 'ಜಿಲ್ಲೆ',
  'Role and jurisdiction': 'ಪಾತ್ರ ಮತ್ತು ವ್ಯಾಪ್ತಿ',
  'SCRB analyst': 'ಎಸ್‌ಸಿಆರ್‌ಬಿ ವಿಶ್ಲೇಷಕ',
  'Investigating officer': 'ತನಿಖಾಧಿಕಾರಿ',
  'Records operator': 'ದಾಖಲೆ ನಿರ್ವಾಹಕ',
  Reviewer: 'ಪರಿಶೀಲಕ',
  'view scoped': 'ವ್ಯಾಪ್ತಿಗೆ ಸೀಮಿತ',
  'no scope applied': 'ವ್ಯಾಪ್ತಿ ಅನ್ವಯಿಸಿಲ್ಲ',
  'view filter, not enforcement': 'ನೋಟದ ಶೋಧಕ, ಜಾರಿ ಅಲ್ಲ',
  'measured, not asserted': 'ಅಳೆಯಲಾಗಿದೆ, ಘೋಷಿಸಿಲ್ಲ',
  'two of three failed': 'ಮೂರರಲ್ಲಿ ಎರಡು ವಿಫಲ',
  Table: 'ಕೋಷ್ಟಕ',
  'Rows on file': 'ದಾಖಲೆಯ ಸಾಲುಗಳು',
  'Actual people': 'ನಿಜವಾದ ವ್ಯಕ್ತಿಗಳು',
  'Rows that are a repeat': 'ಪುನರಾವರ್ತಿತ ಸಾಲುಗಳು',
  'Share inflated': 'ಉಬ್ಬಿದ ಪಾಲು',
  'Hidden by fragmentation': 'ವಿಘಟನೆಯಿಂದ ಮರೆಯಾದವು',
  Question: 'ಪ್ರಶ್ನೆ',
  Questions: 'ಪ್ರಶ್ನೆಗಳು',
  Difficulty: 'ಕಠಿಣತೆ',
  Reachable: 'ತಲುಪಬಹುದೇ',
  Shape: 'ಸ್ವರೂಪ',
  'answerable now': 'ಈಗ ಉತ್ತರಿಸಬಹುದು',
  'needs a language layer': 'ಭಾಷಾ ಪದರ ಬೇಕು',
  'impossible on the raw schema': 'ಮೂಲ ಸ್ಕೀಮಾದಲ್ಲಿ ಅಸಾಧ್ಯ',
  Accuracy: 'ನಿಖರತೆ',
  'not measured': 'ಅಳೆದಿಲ್ಲ',

  /* ---- navigation ---------------------------------------------------- */
  'Corpus audit': 'ದತ್ತಾಂಶ ಪರಿಶೀಲನೆ',
  Evaluation: 'ಮೌಲ್ಯಮಾಪನ',
  'Review queue': 'ಪರಿಶೀಲನಾ ಸರತಿ',
  'Offender network': 'ಅಪರಾಧಿ ಜಾಲ',
  'Undetected cases': 'ಪತ್ತೆಯಾಗದ ಪ್ರಕರಣಗಳು',
  Hotspots: 'ಅಪರಾಧ ಕೇಂದ್ರಗಳು',
  'Query console': 'ಪ್ರಶ್ನೆ ಫಲಕ',
  'Audit trail': 'ಕಾರ್ಯ ದಾಖಲೆ',
  'Build status': 'ನಿರ್ಮಾಣ ಸ್ಥಿತಿ',
  Sections: 'ವಿಭಾಗಗಳು',

  /* ---- navigation hints ---------------------------------------------- */
  'what the data contains': 'ದತ್ತಾಂಶದಲ್ಲಿ ಏನಿದೆ',
  'measured against ground truth': 'ನೈಜ ಉತ್ತರದ ವಿರುದ್ಧ ಅಳೆಯಲಾಗಿದೆ',
  'merges awaiting a decision': 'ನಿರ್ಧಾರಕ್ಕೆ ಕಾಯುತ್ತಿರುವ ವಿಲೀನಗಳು',
  'resolved identities': 'ಪರಿಹರಿಸಿದ ಗುರುತುಗಳು',
  'ranked candidates': 'ಶ್ರೇಣೀಕೃತ ಅಭ್ಯರ್ಥಿಗಳು',
  'offender density, not case density': 'ಅಪರಾಧಿ ಸಾಂದ್ರತೆ, ಪ್ರಕರಣ ಸಾಂದ್ರತೆ ಅಲ್ಲ',
  'structured, no LLM': 'ರಚನಾತ್ಮಕ, ಭಾಷಾ ಮಾದರಿ ಇಲ್ಲ',
  'what the run did': 'ಈ ಚಾಲನೆ ಏನು ಮಾಡಿತು',
  'every claim, checked': 'ಪ್ರತಿ ಹಕ್ಕು, ಪರಿಶೀಲಿಸಲಾಗಿದೆ',

  /* ---- status words --------------------------------------------------- */
  BUILT: 'ನಿರ್ಮಿಸಲಾಗಿದೆ',
  PARTIAL: 'ಭಾಗಶಃ',
  'NOT BUILT': 'ನಿರ್ಮಿಸಿಲ್ಲ',
  Built: 'ನಿರ್ಮಿಸಲಾಗಿದೆ',
  Partial: 'ಭಾಗಶಃ',
  'Not built': 'ನಿರ್ಮಿಸಿಲ್ಲ',
  'synthetic corpus': 'ಕೃತಕ ದತ್ತಾಂಶ',
  'read only surface': 'ಓದಲು ಮಾತ್ರ',
  'layers 1 to 7 measured': 'ಪದರ 1 ರಿಂದ 7 ಅಳೆಯಲಾಗಿದೆ',
  'evaluation not run': 'ಮೌಲ್ಯಮಾಪನ ನಡೆದಿಲ್ಲ',
  'cannot link': 'ಜೋಡಿಸಲಾಗದು',
  'human decision': 'ಮಾನವ ನಿರ್ಧಾರ',
  'no merge is automatic here': 'ಇಲ್ಲಿ ಯಾವ ವಿಲೀನವೂ ಸ್ವಯಂಚಾಲಿತವಲ್ಲ',
  'canonical headline': 'ಅಧಿಕೃತ ಫಲಿತಾಂಶ',
  'not deployed': 'ನಿಯೋಜಿಸಿಲ್ಲ',
  'read from eval.json': 'eval.json ನಿಂದ ಓದಲಾಗಿದೆ',
  automatic: 'ಸ್ವಯಂಚಾಲಿತ',
  review: 'ಪರಿಶೀಲನೆ',
  reject: 'ತಿರಸ್ಕಾರ',
  resolved: 'ಪರಿಹರಿಸಲಾಗಿದೆ',
  conflict: 'ಸಂಘರ್ಷ',

  /* ---- column headers -------------------------------------------------- */
  Area: 'ವಿಭಾಗ',
  Claim: 'ಹಕ್ಕು',
  State: 'ಸ್ಥಿತಿ',
  'What is actually there': 'ವಾಸ್ತವದಲ್ಲಿ ಏನಿದೆ',
  Figure: 'ಅಂಕಿ',
  'Deck claims': 'ಪ್ರಸ್ತುತಿಯ ಹಕ್ಕು',
  'This repository measures': 'ಈ ರೆಪೊಸಿಟರಿ ಅಳೆದದ್ದು',
  Method: 'ವಿಧಾನ',
  Precision: 'ನಿಖರತೆ',
  Recall: 'ಮರುಪಡೆಯುವಿಕೆ',
  Signal: 'ಸೂಚಕ',
  Level: 'ಹಂತ',
  Weight: 'ತೂಕ',
  Coverage: 'ವ್ಯಾಪ್ತಿ',
  Name: 'ಹೆಸರು',
  Station: 'ಠಾಣೆ',
  Cases: 'ಪ್ರಕರಣಗಳು',
  Records: 'ದಾಖಲೆಗಳು',
  Identity: 'ಗುರುತು',
  Offence: 'ಅಪರಾಧ',
  Month: 'ತಿಂಗಳು',
  Rank: 'ಶ್ರೇಣಿ',
  Score: 'ಅಂಕ',
  Cut: 'ಮಿತಿ',
  Threshold: 'ಮಿತಿ',
  Status: 'ಸ್ಥಿತಿ',
  'Operating point': 'ಕಾರ್ಯಾಚರಣೆ ಬಿಂದು',
  'Merged pairs': 'ವಿಲೀನಗೊಂಡ ಜೋಡಿಗಳು',
  Layer: 'ಪದರ',
  Stage: 'ಹಂತ',
  Seconds: 'ಸೆಕೆಂಡುಗಳು',
  Count: 'ಎಣಿಕೆ',
  Share: 'ಪಾಲು',
  Route: 'ಮಾರ್ಗ',
  'Share of run': 'ಚಾಲನೆಯ ಪಾಲು',
  'Known cases': 'ತಿಳಿದ ಪ್ರಕರಣಗಳು',
  'Nearest case': 'ಹತ್ತಿರದ ಪ್ರಕರಣ',
  'On record as': 'ದಾಖಲೆಯಲ್ಲಿ',
  Ranking: 'ಶ್ರೇಣೀಕರಣ',
  Frequency: 'ಆವರ್ತನ',
  'Key families': 'ಕೀ ಕುಟುಂಬಗಳು',
  'Pairs completeness': 'ಜೋಡಿ ಸಂಪೂರ್ಣತೆ',
  'Reduction ratio': 'ಇಳಿಕೆ ಅನುಪಾತ',
  'Base rate': 'ಮೂಲ ದರ',
  'Candidate pairs': 'ಸಂಭಾವ್ಯ ಜೋಡಿಗಳು',
  Completeness: 'ಸಂಪೂರ್ಣತೆ',
  Delta: 'ವ್ಯತ್ಯಾಸ',
  'False merge': 'ತಪ್ಪು ವಿಲೀನ',
  'Folded tokens': 'ಮಡಚಿದ ಪದಗಳು',
  Missed: 'ತಪ್ಪಿಸಿಕೊಂಡವು',
  Movement: 'ಚಲನೆ',
  'Naive count': 'ಸರಳ ಎಣಿಕೆ',
  'Name forms': 'ಹೆಸರಿನ ರೂಪಗಳು',
  Reading: 'ಓದು',
  Reconciled: 'ಸಮನ್ವಯಗೊಳಿಸಿದ',
  'Rows reassigned': 'ಮರುಹಂಚಿದ ಸಾಲುಗಳು',
  Undercount: 'ಕಡಿಮೆ ಎಣಿಕೆ',
  'vs exact name': 'ನಿಖರ ಹೆಸರಿನ ವಿರುದ್ಧ',
  Anomalies: 'ಅಸಂಗತತೆಗಳು',
  'Apparent before': 'ಮೊದಲು ಕಂಡಂತೆ',
  'Cases each': 'ತಲಾ ಪ್ರಕರಣಗಳು',
  'Inflation removed': 'ತೆಗೆದ ಉಬ್ಬರ',
  Offenders: 'ಅಪರಾಧಿಗಳು',
  Repeat: 'ಪುನರಾವರ್ತಿತ',
  'Crime numbers': 'ಅಪರಾಧ ಸಂಖ್ಯೆಗಳು',
  Recovered: 'ಮರುಪಡೆದವು',
  'Shared cases': 'ಹಂಚಿಕೊಂಡ ಪ್ರಕರಣಗಳು',
  'Written as': 'ಬರೆದಂತೆ',
  Conflicts: 'ಸಂಘರ್ಷಗಳು',
  Shown: 'ತೋರಿಸಲಾಗಿದೆ',
  'In band': 'ಪಟ್ಟಿಯಲ್ಲಿ',

  /* ---- query console ---------------------------------------------------- */
  Parameters: 'ನಿಯತಾಂಕಗಳು',
  Result: 'ಫಲಿತಾಂಶ',
  'Equivalent SQL': 'ಸಮಾನ SQL',
  'Structured query console': 'ರಚನಾತ್ಮಕ ಪ್ರಶ್ನೆ ಫಲಕ',
  'What this console is not': 'ಈ ಫಲಕ ಏನಲ್ಲ',
  'no language model': 'ಭಾಷಾ ಮಾದರಿ ಇಲ್ಲ',
  Answer: 'ಉತ್ತರ',
  Rows: 'ಸಾಲುಗಳು',
  'Rows returned': 'ಹಿಂತಿರುಗಿದ ಸಾಲುಗಳು',
  'no rows': 'ಸಾಲುಗಳಿಲ್ಲ',
  'rows returned': 'ಸಾಲುಗಳು ಹಿಂತಿರುಗಿವೆ',
  Source: 'ಮೂಲ',
  'Identities available': 'ಲಭ್ಯ ಗುರುತುಗಳು',

  /* ---- buttons and controls -------------------------------------------- */
  Merge: 'ವಿಲೀನಗೊಳಿಸಿ',
  'Keep separate': 'ಪ್ರತ್ಯೇಕವಾಗಿ ಇರಿಸಿ',
  'Show all evidence': 'ಎಲ್ಲ ಸಾಕ್ಷ್ಯ ತೋರಿಸಿ',
  'Hide evidence': 'ಸಾಕ್ಷ್ಯ ಮರೆಮಾಡಿ',
  'Show table': 'ಕೋಷ್ಟಕ ತೋರಿಸಿ',
  'Hide table': 'ಕೋಷ್ಟಕ ಮರೆಮಾಡಿ',
  Run: 'ಚಲಾಯಿಸಿ',
  Reset: 'ಮರುಹೊಂದಿಸಿ',
  All: 'ಎಲ್ಲ',
  'Conflicts only': 'ಸಂಘರ್ಷಗಳು ಮಾತ್ರ',
  'Skip to main content': 'ಮುಖ್ಯ ವಿಷಯಕ್ಕೆ ಹೋಗಿ',

  /* ---- provenance and audit strip keys ---------------------------------- */
  run: 'ಚಾಲನೆ',
  seed: 'ಬೀಜ',
  corpus: 'ದತ್ತಾಂಶ',
  blocking: 'ವಿಂಗಡಣೆ',
  eval: 'ಮೌಲ್ಯಮಾಪನ',
  preset: 'ಸಂಯೋಜನೆ',
  read: 'ಓದಲಾಗಿದೆ',
  Provenance: 'ಮೂಲ',
}

/** English is the source, so it needs no table. */
export function translate(text: string, language: Language): string {
  if (language === 'en') return text
  return KN[text] ?? text
}
