# img-harness

Image models show up in product work. For each output you need clear answers. Did it meet the hard requirements? Where did it fail? Is the next model better?

Good image evals follow a simple order. Check hard requirements first. Then score quality. Then tag the failure so the next fix is concrete. OpenAI lays this out in their [image evals cookbook](https://developers.openai.com/cookbook/examples/multimodal/image_evals).

Before you can run a single eval, you need an image-eval harness. The harness stores each prompt and its criteria, calls generate or edit, keeps the output images, runs the judge, and lets you compare runs. Building and keeping that harness is usually what slows teams down. Time goes into runners and glue instead of into better prompts and models. Some teams skip image evals for that reason.

This repo follows the cookbook's grading method and example jobs. [Pixeltable](https://docs.pixeltable.com/) is the harness. You store prompts, settings, and output images in tables, call the image models and judge from computed columns, and score a batch when you set `eval_ready`. You still write rubrics, prompts, and pass rules.

## What Pixeltable replaces

An image-eval harness usually does these jobs:

- Define each prompt to run, plus model settings and score shapes
- Call generate or edit and collect outputs
- Store images and track paths
- Encode images for the judge
- Wire LLM-as-judge calls
- Sweep model settings
- Loop over prompts and models, then compare results

OpenAI's cookbook includes one concrete harness for that, a Python package named `vision_harness/`:

- Writeup: [Image Evals for Image Generation and Editing Use Cases](https://developers.openai.com/cookbook/examples/multimodal/image_evals)
- Code: [`examples/evals/imagegen_evals`](https://github.com/openai/openai-cookbook/tree/main/examples/evals/imagegen_evals) in the [openai-cookbook](https://github.com/openai/openai-cookbook) repo (notebook: [`image_evals.ipynb`](https://github.com/openai/openai-cookbook/blob/main/examples/multimodal/image_evals.ipynb))

In this repo you do not copy or maintain that package. Pixeltable takes those jobs. In Python you open the tables with `pxt.get_table('img_eval/images')` and `pxt.get_table('img_eval/evals')`, then:

1. Declare the tables once in [`schema.py`](schema.py). Each row in `img_eval/images` is one prompt to generate or edit, plus model settings, optional reference images, and the output image. `img_eval/evals` is a filtered view of rows you mark ready to grade.
2. Call `images.insert([...])` on `img_eval/images`. Computed columns call the image APIs and store the output image on that row. No runner script. No hand-managed PNG folder.
3. Call `images.update({'eval_ready': True}, ...)` on those rows when you want scores. The `img_eval/evals` view runs the vision judge and fills in scores, verdict, and tags. No evaluate loop over prompts and models.
4. To try another model or prompt, update fields on an existing row in `img_eval/images` (inputs are mutable) or insert another row. Comparison is `evals.select(...).collect()` on `img_eval/evals`, not stitching JSON from a results directory.

You still write and tune the grading method, prompts, criteria, judge rubrics, JSON score schemas, pass rules, required text lists, reference images, and which model and settings to run. That content comes from the cookbook. Only the runtime changes.

## Start here (about 5 minutes)

This first run loads four sample images from disk and grades them. You need an OpenAI API key for the judge.

### 1. Install and add your key

```bash
uv sync
cp .env.example .env
# put OPENAI_API_KEY in .env
```

`uv sync` also installs Jupyter for [`demo.ipynb`](demo.ipynb). You only need `GEMINI_API_KEY` later, if you run new image edits without a pre-made image.

### 2. Create the tables

```bash
uv run pxt schema update schema.py img_eval --allow-destructive -f
uv run pxt ls img_eval
uv run pxt count img_eval/images
```

`pxt ls` should show `img_eval/images` (table) and `img_eval/evals` (view). `pxt count` should print `0`.

### 3. Load the sample images

```bash
uv run python scripts/seed_demo.py
uv run pxt count img_eval/images
```

You should see `4`. The CLI will not show the images themselves. To browse rows and images in a browser, run `uv run pxt dashboard`. Nothing is graded yet.

### 4. Grade them (and keep going) in the notebook

```bash
uv run python -m ipykernel install --user --name=img-harness --display-name="Python (img-harness)"
uv run jupyter notebook demo.ipynb
```

In the notebook, pick the kernel **Python (img-harness)**. It uses this project's `.venv`. The notebook turns grading on, shows verdicts and images, and has cells for re-grading, generating a new image, editing, and resetting the sample batch.

In any Python session (including the notebook), start with `import udfs` before you touch the tables.

---

## How it works

There are two tables:

1. `img_eval/images`. Each row is one prompt to generate or edit, plus model settings, optional reference images, and the output image.
2. `img_eval/evals`. A view over rows where `eval_ready=True`. This is where scores, verdict, and tags appear.

```text
img_eval/images
  inputs → produce_image → image
           (seed on disk | OpenAI generate | Gemini edit)
       │
       │  set eval_ready = True
       ▼
img_eval/evals
  openai.responses → scores → verdict, tags
```

The sample batch uses images already on disk (`seed_image`), so the first run does not call a generate or edit API. The normal path is: insert into `img_eval/images` → the image model generates or edits → set `eval_ready` → read scores from `img_eval/evals`.

Inputs you insert are mutable. You can `images.update(...)` a prompt, model, reference image, or other field on an existing row. Computed columns (including `image` and, on `evals`, the judge outputs) refresh from the new values. You do not have to insert a new row every time you change an input.

Who produces what:

| Step | Who | Notes |
|------|-----|--------|
| Generate | OpenAI `image_generations` | Used when there is no `seed_image` and `task_type` is `image_generation` |
| Edit | Gemini `generate_content` | Used for `image_editing`. Can take one or more reference images |
| Judge | [OpenAI Responses](https://docs.pixeltable.com/howto/providers/working-with-openai#responses-api) | Passes the row's `image` as `input_image`. Pixeltable encodes the PIL image |

`produce_image` in [`udfs.py`](udfs.py) only routes. If `seed_image` is set, it returns that image and skips the providers. Judge prompts, JSON schemas, pass rules, and failure tags live in each job's `rubric.py`. [`schema.py`](schema.py) wires the tables and the judge column.

Always `import udfs` before you use the tables in a Python process so the UDF symbols resolve.

Scores are cached. Setting `eval_ready` again does not re-run the judge. To re-grade, recompute `scores` on `img_eval/evals` (see [`demo.ipynb`](demo.ipynb)).

---

## The four example jobs

The demo covers four common image tasks. Each has its own folder with the judge rules, sample prompts, and (for the demo) a pre-made image:

| Job | Folder | Produce |
|-----|--------|---------|
| Mobile UI mockup | [`use_cases/ui_mockup/`](use_cases/ui_mockup/) | OpenAI generate |
| Marketing flyer | [`use_cases/marketing_flyer/`](use_cases/marketing_flyer/) | OpenAI generate |
| Virtual try-on | [`use_cases/virtual_try_on/`](use_cases/virtual_try_on/) | Gemini edit (2 images) |
| Logo edit | [`use_cases/logo_edit/`](use_cases/logo_edit/) | Gemini edit (1 image) |

What each job folder includes:

| File | Role |
|------|------|
| `README.md` | Inputs, outputs, and actions for that job |
| `rubric.py` | Judge prompt, JSON schema, gate and tag helpers |
| `examples.json` | Sample row fields (models, prompts, paths) |
| `demo_output.png` | Pre-made image used as `seed_image` in the demo |
| `assets/` | Edit reference images (try-on person/garment, logo input) |
| `required_text.json` | Marketing only. Exact copy list |
| `text.py` | Marketing only. Exact-text compare |

One shared schema (`schema.py`) backs all of them. The `workflow` field on each row picks which judge rules to use. Open a folder's README for that job's details. You can ignore the other three if you only care about one.

More product context: [`PLAN.md`](PLAN.md).
