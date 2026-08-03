# Pixeltable Image Eval Harness

Homegrown image-eval harnesses slow teams down. Base `images` table generates outputs; `evals` view (gated by `eval_ready`) scores them. Story: evaluate a batch we already generated, then insert new inputs, generate again, and eval those. Same OpenAI gates-then-graded rubrics. uv for deps.

## Sources

Primary source for eval method, harness shape, rubrics, and demo cases:

- Notebook: [image_evals.ipynb](https://github.com/openai/openai-cookbook/blob/main/examples/multimodal/image_evals.ipynb)
- Rendered page: [Image Evals cookbook](https://developers.openai.com/cookbook/examples/multimodal/image_evals)

### What Pixeltable replaces

Looking at the notebook’s `vision_harness/` package and evaluate loop:

**Pixeltable replaces (the plumbing):**

- `types.py` — TestCase / ModelRun / Score dataclasses
- `storage.py` — saving PNGs to disk
- `io.py` — image → base64 for the judge
- `runners.py` — call generate/edit, collect artifacts
- `graders.py` — LLM-as-judge class wiring
- `sweeps.py` — grid of model settings
- `evaluate.py` — nested for-loops over cases × models

Those become a generating base table plus an `evals` view. Generate first; mark `eval_ready=True` → scores show up on the view.

**Pixeltable does not replace (what you still write and tune):**

- Why evals are hard, and the gates → graded scores → failure tags method
- The four jobs (UI, flyer, try-on, logo)
- Prompts, criteria, judge rubrics, JSON score schemas, pass rules
- Required text lists, reference images
- Choosing which model and settings to run

Same cookbook teaching and rubrics. Different runtime. No custom `vision_harness/`.

### Notebook cross-check

Checked against the notebook. Plan coverage matches on:

- Why vision evals are hard
- Gates, then graded scores, then failure tags
- Harness pieces: test cases, runners, graders, evaluate loop
- Four jobs: UI mockup, marketing flyer, virtual try-on, logo edit
- Demo cases and rubrics from the notebook cells
- Marketing exact-text extract vs required strings
- Multi-reference inputs for try-on

Deferred on purpose (not required for first ship):

- Extra suggested prompts the notebook lists in prose after each demo. Example: the UI section runs one checkout mockup cell, then also lists ideas like minimal layout, dense hierarchy, and exact CTA text. First ship ports the runnable demo case per job. Those extra prompts can be added later as more rows in `cases.json`.
- Human pairwise preference flow from the notebook (pick image A vs B).
- Optional second try-on judge from the notebook. It uses OpenAI Code Interpreter and a `crop` tool so the model can zoom into face or garment regions before scoring. The main try-on rubric judge is enough for first ship.

---

## POV

**Product need.** Image models are in real workflows (UI mockups, marketing assets, try-on, brand edits). “Looks good” is not enough. You need repeatable answers: did this output meet the hard requirements, where did it fail, and is the next model better or worse?

**Why that is hard (the eval problem).** An image mixes hard constraints, perceptual quality, and subtle failure modes. The [OpenAI cookbook](https://developers.openai.com/cookbook/examples/multimodal/image_evals) gives a clear method for that:

1. **Gates first.** Wrong copy or edit spill means the job failed. Quality scores must not paper over that.
2. **Graded metrics next.** Among outputs that clear the bar, 0 to 5 scores rank usability (hierarchy, brand fit, fidelity).
3. **Failure tags after.** Tags like `text_garbled` or `identity_drift` make the next fix concrete.

That method is sound. The blocker is usually not the rubric. It is everything around it.

**Delivery problem: homegrown harnesses.** To run that method you still need cases, generate/edit, grading, storage, and comparison. Teams often build a one-off image harness, then rebuild it on the next project. That cost slows people down. Guardrails arrive late or never. The team never gets to an eval loop that actually improves outputs, because maintaining the harness is already a drain. Many teams skip vision evals entirely if they have to build the harness too. And a homegrown image harness is image-only. It does not carry over when the next eval involves video, audio, or documents.

**This project.** Pixeltable is the harness included. Same gates-then-graded method and the same four use cases, but developers spend time on cases, rubrics, verdicts, and model settings instead of runners and evaluate loops. The same table model also covers other media types when you outgrow image-only evals.

Deps with uv only (`uv add`, `uv sync`, `uv run`). No pip. No requirements.txt.

---

## Why image evals are hard

Keep this in the README. From the cookbook.

Image outputs mix:

1. Hard constraints (exact text, required components, locality)
2. Perceptual quality (sharpness, coherence, brand/style match)
3. Hidden failure modes (subtle drift, garbled text, unintended edits)

Evals should measure reliability for a specific workflow, not generic visual appeal.

---

## Approach

From the cookbook. Keep this thinking in the README.

1. Gates first (pass/fail for non-negotiables), so pretty-but-wrong cannot pass
2. Graded metrics next (0 to 5), so you can rank outputs that already cleared the gates
3. Do not average a high quality score over a failed gate
4. Tag failure modes, so the next change has a target
5. Use humans for subjective dimensions when needed

```text
Inputs → Model → Outputs → Graders → Scores → Feedback → Improvement
```

Harness pieces (test cases, runners, graders) are Pixeltable tables and computed columns.

---

## Developer workflow

Base `images` table **generates** outputs (generate or edit computed columns). `evals` view (rows with `eval_ready=True`) holds judge compute.

The story we tell and ship:

1. **We already generated these.** Demo starts with a batch that already has images (seeded from prior gens, or generated once with `eval_ready=False`).
2. **Evaluate them.** Set `eval_ready=True` → rows enter `evals` → scores appear.
3. **Generate new ones.** Insert new rows with new prompts / model settings / edit inputs. Base table produces new `image` values.
4. **Evaluate those.** Flip `eval_ready` on the new rows → view grades only those (earlier scores stay).

`eval_ready` is the gate between “generation finished / we want scores” and judge spend. You do not grade until you say so.

### Typical workflow

```text
[already-generated batch] → eval_ready=True → scores on evals view
         ↓
[insert new gen/edit inputs] → base table generates images
         ↓
eval_ready=True on new rows → scores for the new batch
```

### One-time setup

```bash
uv sync
export OPENAI_API_KEY=...
uv run pxt schema update schema.py img_eval -f
uv run python scripts/seed_demo.py
```

Schema is class-based: `TableModel = pxt.model_base()` in `schema.py` (`Images` table + `Evals` view with `base=`).

Rubrics live under `use_cases/` and are selected by `workflow` on the row.

### What you do not build

No `vision_harness/` package. No evaluate loop. No required day-to-day eval scripts. Generate on the base table; set `eval_ready`; the view computes.

---

## Four use cases (eval content to ship)

Same jobs and rubrics as the cookbook. These are the first things developers tune.

### UI mockups (generation)

Gates: instruction following, in-image text. Graded: layout/hierarchy, UI affordances.

### Marketing flyers (generation)

Gates: instruction following, exact copy. Graded: layout, brand fit, visual quality. Plus OCR-style text extract vs required strings.

### Virtual try-on (editing)

Graded: facial similarity, outfit fidelity, body-shape preservation. Needs person + garment inputs (small multi-image edit UDF; stock `image_edits` is single-image).

### Logo editing (editing)

Graded: edit intent, non-target invariance, character/style integrity (high thresholds).

---

## Core harness vs use-case elements

Concept: the **table schema** is reusable. The **specific rows** depend on the use case (which images, which rubric, which criteria).

### Core harness (shared, once)

Shared schema and compute in `schema.py` + `udfs.py`. Same columns for every job.

| Harness element | In Pixeltable | Now you can |
|-----------------|---------------|-------------|
| Base images table | Gen/edit inputs + computed `image` + `eval_ready` | Produce outputs without always paying for a judge call |
| Evals view | `base.where(eval_ready == True)` + judge computed columns | Grade only rows you mark ready |
| Image on the row | Computed generate/edit on base (demo may seed prior gens) | Same grading path for first batch and later gens |
| LLM-as-judge | Computed columns on the view | Score ready rows automatically |
| Scores + verdict | Columns on the view | See results beside the image |
| Iterate | Insert new inputs → generate → set `eval_ready` | Eval existing gens, then new gens |

### Use-case / project-specific (row content + rubrics)

| Element | Where it lives | Now you can |
|---------|----------------|-------------|
| Gen/edit prompts + model settings | Fields on base rows | Drive what the model produces next |
| Prompt / criteria for the judge | Fields on those rows | Tell the judge what the image should satisfy |
| Job rubric | `use_cases/<name>/rubric.py`, selected by `workflow` | Change what “good” means per job |
| Exact-copy list (marketing) | Field or `required_text.json` | Catch text mistakes a soft judge misses |
| Reference images (try-on, logo) | Extra image fields on the row | Edit inputs + grade against person/garment/logo |

### Rule of thumb

- Base schema (generate) + evals view + judge compute → core harness.
- Which prompts, criteria, and rubric → rows / use case data.

---

## Tables

Two objects:

1. **Base table** `images` (name flexible) — source rows
2. **View** `evals` — `images.where(images.eval_ready == True)` with judge computed columns

### Base table (`images`)

You set generation/edit inputs and when to grade:

- `gen_prompt` / edit prompt, model settings, optional ref images
- `workflow`, judge `prompt` / `criteria`
- `eval_ready` — `False` until you want grading; `True` to enter the evals view
- optional `required_text`

Pixeltable fills `image` via generate/edit computed columns on the base table. That is the default path.

**Demo bootstrap:** first discussion batch can be “we already generated these” — seed rows whose `image` is already filled (from a prior generate, or assets treated as prior gens) with `eval_ready=False`, then flip ready to show eval. After that, new work is insert inputs → generate → eval.

**Where images are stored:** computed `image` (`pxt.Image`) on the base row; Pixeltable media store. Edit refs under `use_cases/*/assets/`.

### View (`evals`)

Filtered to `eval_ready == True`. Computed columns:

- judge JSON, metrics, pass/fail
- flyer text compare when `required_text` is set

Only ready rows are graded. Flipping `eval_ready` from `False` to `True` makes the row appear in the view and triggers judge compute.

```python
# 1) Already-generated batch — evaluate it
images.update({"eval_ready": True}, where=images.batch_id == "demo_v1")
evals.select(evals.image, evals.verdict, ...).collect()

# 2) New generations — insert inputs; base table produces image
images.insert([
    {
        "gen_prompt": "...",
        "model": "...",
        "workflow": "ui_mockup",
        "prompt": "...",
        "criteria": "...",
        "eval_ready": False,  # wait until gen is done / you want scores
    },
])

# 3) Evaluate the new batch
images.update({"eval_ready": True}, where=...)
evals.select(...).collect()
```

Class-based models via `TableModel = pxt.model_base()` in [`schema.py`](schema.py) (`base=` for the `evals` view). Apply with `uv run pxt schema update schema.py img_eval -f`. Do not use imperative `create_table` / `create_view` for the harness schema.

---

## Directory structure

Each use case is its own folder with everything you tune for that job: rubric, cases, assets, and a short note on what is being measured.

```text
img-harness/
├── README.md
├── pyproject.toml
├── uv.lock
├── .env.example
├── schema.py                      # images table + evals view (eval_ready filter + judge cols)
├── udfs.py                        # parse, verdict, text_compare, multi_image_edits
└── use_cases/
    ├── ui_mockup/
    │   ├── README.md
    │   ├── rubric.py
    │   └── examples.json          # optional demo rows to insert
    ├── marketing_flyer/
    │   ├── README.md
    │   ├── rubric.py
    │   ├── examples.json
    │   └── required_text.json
    ├── virtual_try_on/
    │   ├── README.md
    │   ├── rubric.py
    │   ├── examples.json
    │   └── assets/
    │       ├── person.png
    │       └── garment.png
    └── logo_edit/
        ├── README.md
        ├── rubric.py
        ├── examples.json
        └── assets/
            └── logo_input.png
```

Notes:

- Daily path: generate on base `images` → set `eval_ready` → read `evals` view. Demo opens on an already-generated batch first.
- `use_cases/` holds rubrics, example gen inputs, and edit assets.
- No `vision_harness/`. No `requirements.txt`. No required `run_eval.py`.

---

## Build order

**Phase 1.** uv project; `images` table with generate columns + `eval_ready`; `evals` view with judge columns; UI + marketing rubrics; seed an already-generated demo batch. README story: eval existing → insert new inputs → generate → eval.

**Phase 2.** Logo + try-on (edit path + multi-image edit helper + refs).

**Phase 3.** Failure tags, dashboard polish, model sweeps via more inserts.

---

## Done when

A team can evaluate an already-generated batch via `eval_ready`, then insert new generation inputs, let the base table produce images, flip ready, and see scores on the `evals` view — without harness code or an evaluate script. All four cookbook jobs work.
