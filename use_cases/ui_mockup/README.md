# UI mockups

Generate a mobile UI screen, then grade whether it is usable (structure, text, affordances).

Shared tables: `img_eval/images` → set `eval_ready` → `img_eval/evals`.  
`workflow` must be `"ui_mockup"`.

## Inputs (you set on the row)

| Column | Required | What it is |
|--------|----------|------------|
| `case_id` | yes | Stable id, e.g. `ui_checkout_mockup` |
| `batch_id` | no | Group rows (`demo_v1`, `run_2`, …) |
| `workflow` | yes | `"ui_mockup"` |
| `task_type` | yes | `"image_generation"` |
| `gen_prompt` | for new gens | Prompt sent to the image model |
| `prompt` | yes | Same instructions shown to the judge |
| `criteria` | yes | What “good” means for the judge |
| `model` | yes | Image model, e.g. `gpt-image-1.5` |
| `size` | no | e.g. `1024x1024` |
| `judge_model` | yes | Vision judge, e.g. `gpt-5.2` |
| `seed_image` | no | Path to an already-generated PNG (demo uses `demo_output.png`) |
| `eval_ready` | yes | `False` until you want scores; then `True` |

Demo prompt asks for a checkout screen with labels **Checkout**, **Place Order**, **Edit Cart**. Full text: [`examples.json`](examples.json).

## Outputs (computed)

On `images`:

| Column | Meaning |
|--------|---------|
| `image` | `seed_image` if set, else generated from `gen_prompt` |

On `evals` (only when `eval_ready=True`):

| Column | Meaning |
|--------|---------|
| `scores` | Judge JSON: `instruction_following`, `layout_hierarchy`, `in_image_text_rendering`, `ui_affordance_rendering`, `verdict`, `reason` |
| `verdict` | `PASS` / `FAIL` after gate rules |
| `reason` | Judge explanation |
| `tags` | Failure tags, e.g. `instruction_miss`, `text_garbled`, `weak_hierarchy`, `weak_affordances` |

### Pass rules

- `instruction_following` must be true  
- `in_image_text_rendering` must be true  
- `layout_hierarchy` ≥ 3  
- `ui_affordance_rendering` ≥ 3  

Judge prompt, schema, and gate rules: [`rubric.py`](rubric.py).  
Scoring uses `openai.responses` in [`schema.py`](../../schema.py); verdict/tags dispatch into this rubric.

## Actions

**Grade the seeded demo image** (already in `demo_output.png` after `scripts/seed_demo.py`):

```python
import udfs
import pixeltable as pxt
images = pxt.get_table('img_eval/images')
evals = pxt.get_table('img_eval/evals')
images.update({'eval_ready': True}, where=images.case_id == 'ui_checkout_mockup')
evals.where(evals.case_id == 'ui_checkout_mockup').select(
    evals.verdict, evals.scores, evals.tags
).collect()
```

**Generate a new UI, then grade:**

```python
images.insert([{
    'case_id': 'ui_checkout_v2',
    'batch_id': 'run_2',
    'workflow': 'ui_mockup',
    'task_type': 'image_generation',
    'gen_prompt': '...',  # from examples.json or your own
    'prompt': '...',
    'criteria': '...',
    'model': 'gpt-image-1.5',
    'size': '1024x1024',
    'judge_model': 'gpt-5.2',
    'eval_ready': False,
}])
images.update({'eval_ready': True}, where=images.case_id == 'ui_checkout_v2')
```

**Re-grade without regenerating:**

```python
evals.recompute_columns(columns=['scores'], where=evals.case_id == 'ui_checkout_mockup')
```

**Tune the job:** inputs on a row are mutable. `images.update(...)` `prompt` / `criteria` / `model` on an existing row and recompute. Or edit [`rubric.py`](rubric.py). Schema stays the same.
