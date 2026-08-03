# Marketing flyers

Generate a print flyer, then grade copy correctness, layout, brand fit, and visual quality. Also runs an exact-text check against a required string list.

Shared tables: `img_eval/images` → set `eval_ready` → `img_eval/evals`.  
`workflow` must be `"marketing_flyer"`.

## Inputs (you set on the row)

| Column | Required | What it is |
|--------|----------|------------|
| `case_id` | yes | e.g. `coffee_flyer_generation` |
| `batch_id` | no | Group rows |
| `workflow` | yes | `"marketing_flyer"` |
| `task_type` | yes | `"image_generation"` |
| `gen_prompt` | for new gens | Prompt for the image model (include exact copy) |
| `prompt` | yes | Same text for the judge |
| `criteria` | yes | What “good” means for the judge |
| `required_text` | yes for this job | JSON list of exact strings that must appear (see [`required_text.json`](required_text.json)) |
| `model` | yes | e.g. `gpt-image-1.5` |
| `size` | no | e.g. `1024x1024` |
| `judge_model` | yes | e.g. `gpt-5.2` |
| `seed_image` | no | Already-generated PNG (`demo_output.png` for demo) |
| `eval_ready` | yes | `False` until you want scores |

Demo is a Sunrise Coffee winter latte flyer. Prompts: [`examples.json`](examples.json).

Note: the generation prompt uses ASCII hyphens (`20% OFF - Mon-Thu`); [`required_text.json`](required_text.json) uses the cookbook’s bullet/en-dash forms for the OCR-style check. Mismatches show up in `text_check` / tag `exact_text_mismatch`.

## Outputs (computed)

On `images`:

| Column | Meaning |
|--------|---------|
| `image` | Seeded or newly generated flyer |

On `evals` (when `eval_ready=True`):

| Column | Meaning |
|--------|---------|
| `scores` | Judge JSON: `instruction_following`, `text_rendering`, `layout_hierarchy`, `style_brand_fit`, `visual_quality`, `verdict`, `reason` |
| `extracted_text` | Line list from the vision “OCR” pass |
| `text_check` | `{pass, missing, extra}` vs `required_text` |
| `verdict` | `PASS` / `FAIL` (fails if judge gates fail **or** exact text fails) |
| `reason` | Judge explanation |
| `tags` | e.g. `instruction_miss`, `text_garbled`, `exact_text_mismatch`, `brand_mismatch`, `artifacts` |

### Pass rules

- `instruction_following` and `text_rendering` true  
- `layout_hierarchy`, `style_brand_fit`, `visual_quality` each ≥ 3  
- `text_check.pass` true (exact set match)

Judge prompt, schema, and gate rules: [`rubric.py`](rubric.py). Exact-text compare: [`text.py`](text.py).  
Scoring uses `openai.responses` in [`schema.py`](../../schema.py); OCR extract is marketing-only via that same API.

## Actions

**Grade the seeded demo flyer:**

```python
import udfs
import pixeltable as pxt
images = pxt.get_table('img_eval/images')
evals = pxt.get_table('img_eval/evals')
images.update({'eval_ready': True}, where=images.case_id == 'coffee_flyer_generation')
evals.where(evals.case_id == 'coffee_flyer_generation').select(
    evals.verdict, evals.text_check, evals.extracted_text, evals.tags
).collect()
```

**Generate a new flyer, then grade:**

```python
import json
from pathlib import Path

required = json.loads(Path('use_cases/marketing_flyer/required_text.json').read_text())
images.insert([{
    'case_id': 'coffee_flyer_v2',
    'batch_id': 'run_2',
    'workflow': 'marketing_flyer',
    'task_type': 'image_generation',
    'gen_prompt': '...',
    'prompt': '...',
    'criteria': '...',
    'required_text': required,
    'model': 'gpt-image-1.5',
    'size': '1024x1024',
    'judge_model': 'gpt-5.2',
    'eval_ready': False,
}])
images.update({'eval_ready': True}, where=images.case_id == 'coffee_flyer_v2')
```

**Re-grade:**

```python
evals.recompute_columns(columns=['scores'], where=evals.case_id == 'coffee_flyer_generation')
```

**Tune:** inputs on a row are mutable. `images.update(...)` `prompt` / `criteria` / `model` on an existing row and recompute. Or edit [`required_text.json`](required_text.json) and [`rubric.py`](rubric.py).
