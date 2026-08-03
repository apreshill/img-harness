# img-harness

Image models show up in product work. For each output you need clear answers. Did it meet the hard requirements? Where did it fail? Is the next model better?

## Glossary

Image-eval terms used in this README. Broader agent-eval vocabulary is in Anthropic's [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents).

| Term | Meaning |
|------|---------|
| Evaluation (eval) | Give an image model a prompt (and optional reference images), get an image out, then grade that image. |
| Harness | The infrastructure that runs evals end to end. |
| Criteria | What "good" means for this prompt. Sent to the judge with the image. |
| Rubric | Judge instructions, score schema, gates, and failure-tag rules for one kind of image work. |
| Judge | Vision model that scores an image against the rubric. |
| Gate | Hard pass/fail check. If it fails, the output failed even if the image looks good. |
| Graded score | A 0 to 5 quality score used after gates clear, so you can rank outputs. |
| Failure tag | Short label for how it failed, e.g. `text_garbled` or `identity_drift`. |
| Verdict | Final pass or fail after gates and scores. |

Good image evals follow a simple order ([OpenAI image evals cookbook](https://developers.openai.com/cookbook/examples/multimodal/image_evals)):

- Gates first: check hard requirements
- Graded scores next: score quality
- Failure tags last: label how it failed

But before you can run a single eval, you need an image-eval harness. Building and keeping that harness is usually what slows teams down. Time goes into runners and glue instead of into better prompts and models. Some teams skip image evals for that reason.

This repo copies OpenAI's grading method and example jobs. [Pixeltable](https://www.pixeltable.com/), an open source backend for multimodal apps, replaces their custom harness packages. Details below.

## What Pixeltable replaces

OpenAI published the grading method in their [image evals writeup](https://developers.openai.com/cookbook/examples/multimodal/image_evals) and [notebook](https://github.com/openai/openai-cookbook/blob/main/examples/multimodal/image_evals.ipynb). The runnable code lives in [`examples/evals/imagegen_evals`](https://github.com/openai/openai-cookbook/tree/main/examples/evals/imagegen_evals). That folder has three packages:

| Package | How it works | Use cases |
|---------|--------------|-----------|
| `vision_harness/` | Base library. You pass prompts, models, and a grader. It calls generate or edit, saves images, and runs the judge. It is not a finished eval by itself. | — |
| `generation_harness/` | Uses `vision_harness/` to evaluate text-to-image outputs. | UI mockups, marketing flyers |
| `editing_harness/` | Uses `vision_harness/` to evaluate image-edit outputs. | Virtual try-on, logo changes |

Pixeltable replaces those three packages.

It replaces `vision_harness/` as the evaluate loop. It stores your inputs, calls generate or edit, saves images, and runs the judge.

It replaces `generation_harness/` and `editing_harness/` because one schema covers all four use cases. You do not need a separate CLI package for text-to-image and another for edits.

### What you do instead

Open the tables with `pxt.get_table('img_eval/images')` and `pxt.get_table('img_eval/evals')`.

1. Declare the tables once in [`schema.py`](schema.py). Each row in `img_eval/images` holds one prompt, model settings, optional reference images, and the output image. `img_eval/evals` shows only rows marked ready to grade.
2. Insert into `img_eval/images`. Pixeltable calls the image APIs and stores the output image on that row.
3. Set `eval_ready=True` when you want scores. The `evals` view runs the judge and fills in scores, verdict, and tags.
4. To try another model or prompt, update fields on an existing row (inputs are mutable) or insert another row. Compare with a query on `img_eval/evals`.

You still write the prompts, criteria, rubrics, pass rules, required text, reference images, and model choices. That content comes from the cookbook. Only the runtime changes.

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
