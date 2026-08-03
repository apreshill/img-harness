# Logo editing

Edit: change specific logo text while preserving everything else, then grade with strict thresholds (near-misses fail).

Shared tables: `img_eval/images` → set `eval_ready` → `img_eval/evals`.  
`workflow` must be `"logo_edit"`.

## Inputs (you set on the row)

| Column | Required | What it is |
|--------|----------|------------|
| `case_id` | yes | e.g. `logo_year_edit` |
| `batch_id` | no | Group rows |
| `workflow` | yes | `"logo_edit"` |
| `task_type` | yes | `"image_editing"` |
| `gen_prompt` | for new edits | Narrow edit instruction |
| `prompt` | yes | Same instruction for the judge |
| `criteria` | yes | What “good” means for the judge |
| `ref_image` | for new edits | Source logo ([`assets/logo_input.png`](assets/logo_input.png)) |
| `edit_model` | for new edits | Gemini image model, e.g. `gemini-2.5-flash-image` |
| `judge_model` | yes | e.g. `gpt-5.2` |
| `seed_image` | no | Already-edited output (`demo_output.png` for demo) |
| `eval_ready` | yes | `False` until you want scores |

Demo edit: change text **FIELD → BUTTER**, change nothing else. Prompts: [`examples.json`](examples.json).

## Outputs (computed)

On `images`:

| Column | Meaning |
|--------|---------|
| `image` | Seeded edit result, or new edit from `ref_image` + `gen_prompt` |

On `evals` (when `eval_ready=True`):

| Column | Meaning |
|--------|---------|
| `scores` | Judge JSON: `edit_intent_correctness`, `non_target_invariance`, `character_and_style_integrity`, `verdict`, `reason` (each metric 0–5) |
| `verdict` | `PASS` only if every metric ≥ 4; else `FAIL` |
| `reason` | Judge explanation |
| `tags` | e.g. `edit_miss`, `edit_spill`, `style_drift` |

Cookbook demo often **FAIL**s on spill (background/style drift) even when the text change is right — that is expected with these thresholds.

Judge prompt, schema, and gate rules: [`rubric.py`](rubric.py).  
Scoring uses `openai.responses` in [`schema.py`](../../schema.py); edits use Gemini (`edit_model`).

## Actions

**Grade the seeded demo edit:**

```python
import udfs
import pixeltable as pxt
images = pxt.get_table('img_eval/images')
evals = pxt.get_table('img_eval/evals')
images.update({'eval_ready': True}, where=images.case_id == 'logo_year_edit')
evals.where(evals.case_id == 'logo_year_edit').select(
    evals.verdict, evals.scores, evals.tags, evals.reason
).collect()
```

**Run a new logo edit, then grade** (omit `seed_image`):

```python
images.insert([{
    'case_id': 'logo_butter_v2',
    'batch_id': 'run_2',
    'workflow': 'logo_edit',
    'task_type': 'image_editing',
    'gen_prompt': 'Edit the logo by changing the text from FIELD to BUTTER. Do not change any other text, colors, shapes, or layout.',
    'prompt': 'Edit the logo by changing the text from FIELD to BUTTER. Do not change any other text, colors, shapes, or layout.',
    'criteria': 'Exact edit; non-target unchanged; style preserved.',
    'ref_image': 'use_cases/logo_edit/assets/logo_input.png',
    'edit_model': 'gemini-2.5-flash-image',
    'judge_model': 'gpt-5.2',
    'eval_ready': False,
}])
images.update({'eval_ready': True}, where=images.case_id == 'logo_butter_v2')
```

**Re-grade:**

```python
evals.recompute_columns(columns=['scores'], where=evals.case_id == 'logo_year_edit')
```

**Tune:** inputs on a row are mutable. `images.update(...)` a prompt, `ref_image`, or model on an existing row and recompute. Or replace [`assets/logo_input.png`](assets/logo_input.png), or edit thresholds in [`rubric.py`](rubric.py).
