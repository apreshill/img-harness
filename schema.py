"""Class-based Pixeltable schema for the image eval harness.

Produce (udfs.produce_image):
  - seed_image if set (demo / already-generated) — no provider call
  - image_generation → openai.image_generations
  - image_editing → gemini.generate_content([ref images…, prompt])  # multi-image OK

Judge (this file):
  - openai.responses with input_image = Images.image (Pixeltable encodes PIL)
  - https://docs.pixeltable.com/howto/providers/working-with-openai#responses-api
  - model must be a constant here (Responses resource pool); change JUDGE_MODEL below

Apply with:
    uv run pxt schema update schema.py img_eval --allow-destructive -f
"""

from __future__ import annotations

import pixeltable as pxt
from pixeltable.functions import openai

import udfs

TableModel = pxt.model_base()

# openai.responses requires a constant model for resource-pool resolution
JUDGE_MODEL = 'gpt-5.2'


class Images(TableModel, name='images'):
    """Base table: inputs + produced image."""

    case_id: pxt.Required[pxt.String]
    batch_id: pxt.String
    workflow: pxt.Required[pxt.String]  # ui_mockup | marketing_flyer | virtual_try_on | logo_edit
    task_type: pxt.Required[pxt.String]  # image_generation | image_editing

    gen_prompt: pxt.String
    model: pxt.String  # OpenAI image model for generation (e.g. gpt-image-1.5)
    size: pxt.String
    edit_model: pxt.String  # Gemini image model for editing (e.g. gemini-2.5-flash-image)
    judge_model: pxt.String  # recorded on the row; scoring uses JUDGE_MODEL above

    seed_image: pxt.Image
    ref_image: pxt.Image
    ref_image_2: pxt.Image

    prompt: pxt.Required[pxt.String]
    criteria: pxt.Required[pxt.String]
    required_text: pxt.Json

    eval_ready: pxt.Required[pxt.Bool]

    image = udfs.produce_image(
        seed_image, task_type, gen_prompt, ref_image, ref_image_2, model, edit_model, size
    )


class Evals(TableModel, name='evals', base=Images.where(Images.eval_ready == True)):  # noqa: E712
    """View over ready rows: judge via OpenAI Responses API."""

    judge_raw = openai.responses(
        [
            {
                'role': 'user',
                'content': [
                    {'type': 'input_text', 'text': udfs.judge_user_text(Images.prompt, Images.criteria)},
                    {'type': 'input_image', 'image_url': Images.image},
                ],
            }
        ],
        model=JUDGE_MODEL,
        model_kwargs={
            'instructions': udfs.judge_instructions(Images.workflow),
            'text': udfs.judge_text_format(Images.workflow),
        },
    )
    scores = udfs.parse_json(judge_raw.output_text)
    judge_verdict = udfs.score_str(scores, 'verdict')
    reason = udfs.score_str(scores, 'reason')

    extracted_text = udfs.extract_flyer_text(Images.image, Images.workflow, JUDGE_MODEL)
    text_check = udfs.compare_required_text(extracted_text, Images.required_text)
    verdict = udfs.finalize_verdict(Images.workflow, scores, text_check)
    tags = udfs.failure_tags(Images.workflow, scores, text_check)
