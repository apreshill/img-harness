# Virtual try-on

Edit: put a person into a garment (two reference images), then grade identity preservation, garment fidelity, and body shape.

Shared tables: `img_eval/images` → set `eval_ready` → `img_eval/evals`.  
`workflow` must be `"virtual_try_on"`.

## Inputs (you set on the row)

| Column | Required | What it is |
|--------|----------|------------|
| `case_id` | yes | e.g. `vto_jacket_tryon` |
| `batch_id` | no | Group rows |
| `workflow` | yes | `"virtual_try_on"` |
| `task_type` | yes | `"image_editing"` |
| `gen_prompt` | for new edits | Edit instruction for the image model |
| `prompt` | yes | Same instruction for the judge |
| `criteria` | yes | What “good” means for the judge |
| `ref_image` | for new edits | Person photo ([`assets/person.png`](assets/person.png)) |
| `ref_image_2` | for new edits | Garment flat-lay ([`assets/garment.png`](assets/garment.png)) |
| `edit_model` | for new edits | Gemini image model, e.g. `gemini-2.5-flash-image` |
| `judge_model` | yes | e.g. `gpt-5.2` |
| `seed_image` | no | Already-edited output (`demo_output.png` for demo) |
| `eval_ready` | yes | `False` until you want scores |

Demo: jacket try-on. Full prompts: [`examples.json`](examples.json).

When `seed_image` is set, refs are still useful context for humans / future gens but `produce_image` returns the seed and does not call edit.

## Outputs (computed)

On `images`:

| Column | Meaning |
|--------|---------|
| `image` | Seeded try-on result, or new multi-image edit from `ref_image` + `ref_image_2` |

On `evals` (when `eval_ready=True`):

| Column | Meaning |
|--------|---------|
| `scores` | Judge JSON: `facial_similarity`, `outfit_fidelity`, `body_shape_preservation`, `verdict`, `reason` (each metric 0–5) |
| `verdict` | `PASS` if all metrics ≥ 3; else `FAIL` |
| `reason` | Judge explanation |
| `tags` | e.g. `identity_drift`, `garment_mismatch`, `body_warp` |

Judge prompt, schema, and gate rules: [`rubric.py`](rubric.py).  
Scoring uses `openai.responses` in [`schema.py`](../../schema.py); edits use Gemini with both refs (`edit_model`).

## Actions

**Grade the seeded demo try-on:**

```python
import udfs
import pixeltable as pxt
images = pxt.get_table('img_eval/images')
evals = pxt.get_table('img_eval/evals')
images.update({'eval_ready': True}, where=images.case_id == 'vto_jacket_tryon')
evals.where(evals.case_id == 'vto_jacket_tryon').select(
    evals.verdict, evals.scores, evals.tags
).collect()
```

**Run a new try-on edit, then grade** (omit `seed_image`):

```python
images.insert([{
    'case_id': 'vto_jacket_v2',
    'batch_id': 'run_2',
    'workflow': 'virtual_try_on',
    'task_type': 'image_editing',
    'gen_prompt': 'Put the person in the first image into the jacket...',
    'prompt': 'Put the person in the first image into the jacket...',
    'criteria': 'Same person and background; jacket matches; body preserved.',
    'ref_image': 'use_cases/virtual_try_on/assets/person.png',
    'ref_image_2': 'use_cases/virtual_try_on/assets/garment.png',
    'edit_model': 'gemini-2.5-flash-image',
    'judge_model': 'gpt-5.2',
    'eval_ready': False,
}])
images.update({'eval_ready': True}, where=images.case_id == 'vto_jacket_v2')
```

**Re-grade:**

```python
evals.recompute_columns(columns=['scores'], where=evals.case_id == 'vto_jacket_tryon')
```

**Tune an existing row** (inputs are mutable; computed columns refresh):

```python
images.update(
    {'gen_prompt': '...', 'prompt': '...', 'criteria': '...'},
    where=images.case_id == 'vto_jacket_v2',
)
evals.recompute_columns(columns=['scores'], where=evals.case_id == 'vto_jacket_v2')
```

Also swap files under `assets/`, or edit [`rubric.py`](rubric.py).
