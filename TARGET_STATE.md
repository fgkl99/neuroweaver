# TARGET_STATE.md — NeuroWeaver: Stato Obiettivo

Questo documento descrive lo stato a cui il progetto vuole arrivare per essere
considerato **completo e rigoroso**. Non è un backlog operativo, ma una
specifica del target: ogni sezione descrive il gap rispetto all'as-is e i
criteri di accettazione del to-be.

---

## 1. Libreria di Feature — da stub a sistema modulare completo

### As-is
- Esiste solo `features/bandpower/` come modulo
- `features/bandpower/feature.py` calcola una **rolling mean-square** (proxy),
  non una vera bandpower via Welch
- La vera estrazione (Welch, RMS, entropia spettrale) vive in
  `extract_features.py` come logica monolitica hardcoded
- `extract_features.py` **ignora completamente** il sistema
  `features/<name>/feature.py`; le due implementazioni sono parallele e
  divergenti
- Inconsistenza di naming: il modulo produce `power_ms_<CH>`, lo stage 4
  produce `bandpower_alpha_<CH>`

### To-be
Ogni tipo di feature supportato deve esistere come modulo indipendente in
`features/`:

| Modulo | Famiglia | Output principale | Note |
|--------|----------|------------------|-------|
| `features/bandpower/` | `bandpower` | `bandpower_alpha_<CH>` (Welch, 8-12 Hz) | Sostituisce la stub con vera Welch |
| `features/spectral_entropy/` | `spectral_entropy` | `spectral_entropy_<CH>` (Shannon, 4-30 Hz) | Estratto da `extract_features.py` |
| `features/rms/` | `time_domain` | `rms_<CH>` | Estratto da `extract_features.py` |
| `features/alpha_asymmetry/` | `bandpower` | `alpha_asymmetry_f3_f4` | Dalla fallback del planner |

Ogni modulo deve soddisfare il feature contract:
- `meta.json` valido contro `schemas/feature_meta.schema.json`
- `feature.py` con `compute(df, meta) -> pd.DataFrame` deterministico
- `tests/features/<name>/test_feature.py` con almeno 3 assertion (callable,
  shape, range)

`extract_features.py` deve essere refactored per **invocare i moduli** invece
di duplicare la logica. Il contratto è: Stage 4 = orchestrazione di
`features/<name>/feature.py`, non reimplementazione.

**Criterio di accettazione:** `python tools/nw_orch.py` passa tutti e 4 i gate
con tutti i moduli sopra presenti.

---

## 2. Coerenza Pipeline — coupling implicito da eliminare

### As-is
- Gli stage 2, 3, 4 trovano la run directory con `sorted(glob("run_*"))[-1]`
  — fragile, non testabile in isolamento
- `extract_features.py` hardcoda il path `data/recording_001.meta.json`
  invece di leggerlo dal summary della run corrente
- `run_feature_planner.py` crasha con `FileNotFoundError` se
  `llm_data_assessment.json` non esiste (stage 2 mai eseguito)
- Nessuno stage accetta `--run-dir` come argomento esplicito

### To-be
Ogni script di stage deve accettare `--run-dir <path>` per operare su una run
specifica:

```bash
python run_llm.py --run-dir runs/run_20260228_120000
python run_feature_planner.py --run-dir runs/run_20260228_120000
python extract_features.py --run-dir runs/run_20260228_120000
```

`run_feature_planner.py` deve avere un fallback esplicito se
`llm_data_assessment.json` manca: usare `fallback_feature_plan()` con un
assessment sintetico minimo, loggando un warning — non crashare.

L'orchestratore deve passare `--run-dir` esplicitamente agli stage 2-4 invece
di affidarsi all'auto-detect.

**Criterio di accettazione:** è possibile rieseguire qualsiasi stage su una run
precedente senza side effect su run correnti.

---

## 3. Packaging e Dipendenze — zero ambiguità di ambiente

### As-is
- Nessun `requirements.txt`
- Nessun `pyproject.toml`
- Nessun `.env.example`
- Dipendenze note solo via README e CLAUDE.md

### To-be

**`requirements.txt`** con versioni minime testate:
```
pandas>=1.5
numpy>=1.23
scipy>=1.9
jsonschema>=4.17
google-genai>=0.5
PyYAML>=6.0
pytest>=7.0
```

**`.env.example`**:
```bash
# Richiesto solo per run_llm.py e run_feature_planner.py (path LLM)
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-2.0-flash
```

**Criterio di accettazione:** `pip install -r requirements.txt` in un
virtualenv pulito permette di eseguire `python -m pytest` e `python run.py`
senza errori di import.

---

## 4. Copertura di Test — da smoke test a suite robusta

### As-is
- 5 file di test, quasi tutti triviali (1-3 righe)
- Nessun test di integrazione
- `fallback_feature_plan()` non è testata direttamente
- I guardrail (ban connectivity) non hanno test dedicati
- Nessun test per `run.py` (quality grading, exit codes)

### To-be

#### Unit test minimi per modulo

| File | Cosa testare |
|------|-------------|
| `tests/features/bandpower/test_feature.py` | callable, shape (8 col), no NaN su input valido, range values |
| `tests/features/spectral_entropy/test_feature.py` | idem, valori in [0, 1] |
| `tests/features/rms/test_feature.py` | idem, valori >= 0 |
| `tests/pipeline/test_run_quality.py` | grade `good` su dati mock, grade `poor` su dati mancanti, exit code 2 |
| `tests/pipeline/test_fallback_planner.py` | produce piano valido, confidence <= 0.2 se duration < 10s, nessuna feature connectivity |
| `tests/guardrails/test_connectivity_ban.py` | rileva "coherence", "plv", "graph", "Coherence" (maiuscolo) e solleva errore |

#### Test di integrazione end-to-end

`tests/integration/test_pipeline_e2e.py`:
- Esegue Stage 1 sui dati mock -> verifica `checks.json` e `data_summary.json`
- Esegue Stage 4 sulla run generata -> verifica `features.csv` con tutte le
  colonne attese
- Verifica che il numero di colonne in `features.csv` corrisponda ai moduli
  presenti in `features/`

**Criterio di accettazione:** `python -m pytest --tb=short` produce almeno 20
test, nessuno skippato, copertura funzionale di ogni stage.

---

## 5. Documentazione Tecnica — zero file vuoti

### As-is
- `docs/ORCHESTRATOR.md` e' vuoto (1 riga)
- Nessun documento per il feature registry
- Nessuna guida per estendere il sistema

### To-be

**`docs/ORCHESTRATOR.md`** — documenta:
- Architettura a 4 stage + 2 gate
- Formato di `CHANGE_REQUEST.yaml` (tutti i campi)
- Exit codes e loro significato
- Come interpretare `artifacts/run_*/report.json`

**`docs/FEATURE_REGISTRY.md`** — tabella di tutti i moduli in `features/`:
- ID, famiglia, canali, range output atteso
- Aggiornata manualmente ad ogni nuovo modulo

**`docs/EXTENDING.md`** — guida per:
- Aggiungere un nuovo modulo feature (con template)
- Aggiungere un nuovo schema EEG (es. `eeg16_v0`)
- Modificare un prompt (con nota sulle implicazioni contrattuali)

**Criterio di accettazione:** nessun file `.md` in `docs/` e' vuoto o
segnaposto.

---

## 6. Qualita' del Codice — inconsistenze da eliminare

### As-is
- `EIGHT_CH` e' definita 3 volte in file diversi (`run.py`,
  `extract_features.py`, `features/bandpower/feature.py`)
- `load_json()` e `load_text()` sono reimplementate in piu' script
- `fallback_feature_plan()` e' inline in `run_feature_planner.py` ma abbastanza
  grande da meritare un file separato

### To-be

**`neuroweaver/constants.py`** (o modulo condiviso):
```python
EIGHT_CH = ["F3", "F4", "C3", "C4", "P3", "P4", "O1", "O2"]
```
Importato da tutti i moduli — zero ridefinizioni.

`fallback_feature_plan()` estratta in `neuroweaver/fallback_planner.py` e
testata separatamente.

**Criterio di accettazione:** `grep -r "EIGHT_CH\s*=" .` restituisce solo la
definizione in `constants.py` e zero ridefinizioni.

---

## 7. Robustezza dei Guardrail — espliciti e testabili

### As-is
- Il guardrail connectivity cerca substring lowercase (`"plv"`, `"graph"`) nel
  JSON serializzato — bypassabile con varianti maiuscole
- Lo schema `feature_plan_v0.json` valida `family` come stringa libera, non
  come `enum`
- La lista di keyword vietate non e' centralizzata (duplicata tra
  `run_llm.py` e `run_feature_planner.py`)

### To-be
- `schemas/feature_plan_v0.schema.json`: il campo `family` diventa
  `"enum": ["bandpower", "spectral_entropy", "time_domain"]`
- Lista centralizzata di keyword vietate:
  ```python
  BANNED_KEYWORDS = frozenset([
      "connectivity", "coherence", "plv", "pli", "wpli", "graph", "granger"
  ])
  ```
  Usata da entrambi gli script, check case-insensitive
- Testata in `tests/guardrails/test_connectivity_ban.py`

**Criterio di accettazione:** un test inietta un piano con `"Coherence"`
(maiuscolo) e verifica il rigetto.

---

## 8. CI/CD — validazione automatica su ogni push

### As-is
- Nessun pipeline CI/CD (no `.github/workflows/`)
- La validazione e' solo locale via orchestratore

### To-be

**`.github/workflows/ci.yml`** — esegue su ogni push e PR:
- `pip install -r requirements.txt`
- `python -m pytest -q`
- Stage 1 sui dati mock
- Determinism check su tutti i moduli

Non richiede `GEMINI_API_KEY` — gli stage LLM usano il fallback deterministico.

**Criterio di accettazione:** il workflow CI e' verde su `main` senza variabili
d'ambiente segrete.

---

## Riepilogo Gap -> To-be

| Area | Priorita' | Gap principale | Effort |
|------|-----------|----------------|--------|
| Feature library | Alta | Solo bandpower stub; extract_features.py disconnesso | Medio |
| Pipeline coupling | Alta | Auto-detect "latest run" fragile | Basso |
| Packaging | Media | Nessun requirements.txt o .env.example | Minimo |
| Test coverage | Alta | Smoke test only; nessuna integrazione | Medio |
| Documentazione | Media | docs/ quasi vuota | Basso |
| Code quality | Media | EIGHT_CH triplicata, helper duplicati | Basso |
| Guardrail robustezza | Alta | Schema non enumera famiglie; keyword matching fragile | Basso |
| CI/CD | Bassa | Nessun workflow automatico | Basso |

---

## Invarianti da Non Toccare

Anche nel to-be, le seguenti invarianti del progetto rimangono inalterate:

1. Nessuna feature di connettivita' (PLV, PLI, coerenza, WPLI, grafi)
2. Nessun training ML — solo estrazione di feature
3. `compute()` deterministico, verificato SHA256
4. Schema JSON validato prima di ogni scrittura su disco
5. Montaggio fisso 8 canali — nuove configurazioni = nuovi schema (es. eeg16_v0)
6. I prompt LLM sono contratti — modifiche deliberate e versionabili
