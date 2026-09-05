# img-harness

Image models now do real work in products. They generate UI mockups and marketing flyers, and they edit photos for try-on and brand assets. When you ship that work, you need clear answers about each output. Did it meet the hard requirements? Where did it fail? Is the next model better than the last one?

To answer those questions you run image evals. An eval gives an image model a prompt and optional reference images, takes the image it produces, and grades that image against what you asked for. The grading method in this repo comes from OpenAI's [image evals cookbook](https://developers.openai.com/cookbook/examples/multimodal/image_evals).

The part that slows teams down is usually not the grading method. It is building and keeping the harness that runs the evals. That harness stores inputs, calls the image model, saves outputs, and runs the judge. Teams often build a one-off harness for one project and then build it again for the next one. Some teams skip image evals because of that cost. This repo uses [Pixeltable](https://www.pixeltable.com/), an open source backend for multimodal apps, as the harness. You spend your time on prompts, rubrics, and model choices instead of runner code.

## The method

Good image evals run three checks in order. This order comes from the OpenAI cookbook.

- Gates first. Check the hard requirements, for example required text or an edit that must stay in one place. A gate failure fails the output even if the image looks good.
- Graded scores next. For the outputs that clear the gates, score quality from 0 to 5 so you can rank them.
- Failure tags last. Label how an output failed, for example `text_garbled` or `identity_drift`, so the next fix has a target.

Image outputs are hard to grade because they mix three things at once. They have hard constraints such as exact text and required parts. They have perceptual quality such as sharpness and brand fit. They have hidden failure modes such as a garbled word or a small change to the wrong part of an image. An eval should measure reliability for one workflow, not general visual appeal.

<details>
<summary>Glossary of terms used in this README</summary>

The broader vocabulary for agent evals is in Anthropic's [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents).

| Term | Meaning |
|------|---------|
| Evaluation (eval) | Give an image model a prompt and optional reference images, get an image out, then grade that image. |
| Harness | The code that runs evals from input to score. |
| Criteria | What good means for this prompt. Sent to the judge with the image. |
| Rubric | The judge instructions, score schema, gates, and failure-tag rules for one kind of image work. |
| Judge | A vision model that scores an image against the rubric. |
| Gate | A hard pass or fail check. If it fails, the output failed even if the image looks good. |
| Graded score | A score from 0 to 5 for quality, used after the gates clear so you can rank outputs. |
| Failure tag | A short label for how an output failed, for example `text_garbled` or `identity_drift`. |
| Verdict | The final pass or fail after the gates and scores. |

</details>

## What Pixeltable replaces

OpenAI published the grading method in their [cookbook](https://developers.openai.com/cookbook/examples/multimodal/image_evals) and a [notebook](https://github.com/openai/openai-cookbook/blob/main/examples/multimodal/image_evals.ipynb). The runnable version lives in [`examples/evals/imagegen_evals`](https://github.com/openai/openai-cookbook/tree/main/examples/evals/imagegen_evals). It has three packages that together make a custom harness. There is a base library that calls generate or edit, saves images, and runs the judge. On top of it there are two wrappers, one for text-to-image jobs and one for image-edit jobs.

Pixeltable replaces all three. The harness is two base tables and two views, and each table produces its image with a built-in Pixeltable function that names the provider and the model. You do not need a separate package for text-to-image and another for edits.

You still write the prompts, criteria, rubrics, pass rules, required text, and reference images. That content comes from the cookbook. Only the runtime changes.

### What you do instead

The harness is two base tables and two views. You work with them through Pixeltable.

1. Declare them once in [`schema.py`](schema.py). The `generations` table produces its image with `openai.image_generations`. The `edits` table produces its image with `gemini.generate_content`. The `gen_evals` and `edit_evals` views show only the rows you have marked ready to grade.
2. Insert a row. Pixeltable calls the image API on insert and stores the output image on the row.
3. Set `eval_ready=True` when you want scores. The matching view runs the judge and fills in the scores, verdict, and tags.
4. To try another prompt, update fields on an existing row, because inputs are mutable, or insert another row. Compare the results with a query on the view.

Open the tables with `pxt.get_table('img_eval/generations')` and `pxt.get_table('img_eval/gen_evals')`, and the same for `edits` and `edit_evals`.

## Start here (about 5 minutes)

This first run generates four demo images and grades them. Inserting a row runs the image model, so you need both keys. Put `OPENAI_API_KEY` and `GEMINI_API_KEY` in `.env`.

### 1. Install and add your keys

```bash
uv sync
cp .env.example .env
# put OPENAI_API_KEY and GEMINI_API_KEY in .env
```

`uv sync` also installs Jupyter for [`demo.ipynb`](demo.ipynb).

### 2. Create the tables

```bash
uv run pxt schema update schema.py img_eval --allow-destructive -f
uv run pxt ls img_eval
```

`pxt ls` should show `img_eval/generations` and `img_eval/edits` as tables, and `img_eval/gen_evals` and `img_eval/edit_evals` as views.

### 3. Generate the demo images

```bash
uv run python scripts/seed_demo.py
```

This inserts the four demo cases. Inserting generates each image, so it calls OpenAI for the two generations and Gemini for the two edits. The rows start with `eval_ready=False`, so nothing is graded yet. To browse the rows and images in a browser, run `uv run pxt dashboard`.

### 4. Grade them in the notebook

```bash
uv run python -m ipykernel install --user --name=img-harness --display-name="Python (img-harness)"
uv run jupyter notebook demo.ipynb
```

In the notebook, pick the kernel named Python (img-harness). It uses this project's `.venv`. The notebook turns grading on, shows the verdicts and images, and has cells for re-grading, generating a new image, editing, and resetting the sample batch.

In any Python session, including the notebook, run `import udfs` before you touch the tables. That import registers the functions the tables use.

## How it works

There are two base tables and two views.

1. `generations`. Text-to-image rows for UI mockups and marketing flyers. The `image` column is produced by `openai.image_generations`.
2. `edits`. Image-edit rows for virtual try-on and logo edits. The `image` column is produced by `gemini.generate_content`.
3. `gen_evals` and `edit_evals`. A view over each table's rows where `eval_ready=True`. This is where the scores, verdict, and tags appear.

```text
img_eval/generations                          img_eval/edits
  gen_prompt → openai.image_generations         refs + prompt → gemini.generate_content
       │  image                                        │  image
       │  set eval_ready = True                        │  set eval_ready = True
       ▼                                               ▼
img_eval/gen_evals                             img_eval/edit_evals
  openai.responses → scores → verdict, tags      openai.responses → scores → verdict, tags
```

Inserting a row runs the image model and stores the result in the `image` column. Setting `eval_ready` to `True` moves the row into the view, which runs the judge.

The provider and the model are part of the schema. The `image` column calls the built-in Pixeltable function directly, so the schema shows `openai.image_generations` or `gemini.generate_content` and the model that ran. The three models are constants in [`schema.py`](schema.py): `GEN_MODEL`, `EDIT_MODEL`, and `JUDGE_MODEL`. These functions need a constant model to resolve their rate-limit pool, so the model is set in the schema, not passed as a per-row column. Change a constant to run a different model.

The judge returns JSON. One `udfs.parse_json` turns the JSON string into an object, and after that the fields are native Pixeltable access, for example `scores.verdict` and `scores.reason`. Pixeltable has no native string-to-JSON parser, so that one parse is the only custom step in the judge path. The verdict and tags come from each job's `rubric.py`, selected by the `workflow` field.

The inputs you insert are mutable. You can call `update(...)` to change a prompt or reference image on an existing row, and the computed columns refresh from the new values.

Each row has two prompt fields. `gen_prompt` is sent to the image model. `prompt` is the instruction shown to the judge. They often hold the same text, but you can set them apart when you want the judge to grade against different wording than the model saw.

The judge output is cached. To re-grade, for example after you change a rubric, recompute the `judge_raw` column on the view, as shown in [`demo.ipynb`](demo.ipynb).

### Editing uses Gemini

The edit jobs call Gemini, not OpenAI. Gemini's `generate_content` accepts several reference images in one call, which virtual try-on needs, because it passes both the person and the garment. The built-in Pixeltable function for OpenAI image edits takes a single image. The OpenAI API itself does accept several images for an edit, so a later version can move editing to OpenAI and use one provider. That change needs a test against the live API first.

## The four example jobs

The demo covers four common image tasks. Two are generations and two are edits.

| Job | Folder | Table | Produced by |
|-----|--------|-------|-------------|
| Mobile UI mockup | [`use_cases/ui_mockup/`](use_cases/ui_mockup/) | generations | `openai.image_generations` |
| Marketing flyer | [`use_cases/marketing_flyer/`](use_cases/marketing_flyer/) | generations | `openai.image_generations` |
| Virtual try-on | [`use_cases/virtual_try_on/`](use_cases/virtual_try_on/) | edits | `gemini.generate_content`, two images |
| Logo edit | [`use_cases/logo_edit/`](use_cases/logo_edit/) | edits | `gemini.generate_content`, one image |

Here is what each job folder holds.

| File | Role |
|------|------|
| `README.md` | The inputs, outputs, and actions for that job. |
| `rubric.py` | The judge prompt, JSON schema, and gate and tag rules. |
| `examples.json` | The sample row fields: the table, workflow, prompts, and reference paths. |
| `assets/` | The edit reference images, such as the try-on person and garment or the logo input. |
| `required_text.json` | Marketing only. The list of exact copy. |
| `text.py` | Marketing only. The exact-text compare. |

The `workflow` field on each row picks which judge rules to use. Open a folder's README for that job's details. You can ignore the other three if you only care about one.

## Generate synthetic test data

You do not need real images to test an eval. You can generate the inputs and outputs with the same built-in functions, mark them ready, and grade them. This is useful when you are building or changing a rubric and want cases to run it against before you have real data. Generate a batch, then check that the verdicts and failure tags match what you expect. A rubric that passes a clean case and fails a broken one is one you can rely on.

[`scripts/make_tryon_inputs.py`](scripts/make_tryon_inputs.py) shows the pattern. The try-on edit itself is produced by the `edits` table, so this script only makes the two reference images. It declares a small class-based table whose image is computed by `openai.image_generations`, generates the person and the garment, and saves them under `use_cases/virtual_try_on/assets/`. That gives the references clean provenance, because the model produced them.
