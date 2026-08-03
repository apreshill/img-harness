"""UDFs for the image-eval schema.

Judge scoring uses Pixeltable openai.responses in schema.py (PIL on
input_image — Pixeltable encodes it).

Produce is routed here so seed_image short-circuits without provider calls:
  - image_generation → openai.image_generations (stock .aexec)
  - image_editing → gemini.generate_content with image list (stock .aexec)

Per-job gates/tags: use_cases/<name>/rubric.py
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json

import pixeltable as pxt
from PIL import Image

from use_cases.logo_edit import rubric as logo_rubric
from use_cases.marketing_flyer import rubric as marketing_rubric
from use_cases.marketing_flyer import text as marketing_text
from use_cases.ui_mockup import rubric as ui_rubric
from use_cases.virtual_try_on import rubric as vto_rubric

_RUBRICS = {
    'ui_mockup': ui_rubric,
    'marketing_flyer': marketing_rubric,
    'virtual_try_on': vto_rubric,
    'logo_edit': logo_rubric,
}

_GEMINI_IMAGE_CONFIG = {'response_modalities': ['IMAGE']}
_OCR_INSTRUCTIONS = (
    'List every piece of text visible in this flyer image. '
    'Return one line per text item and preserve capitalization, punctuation, and spacing exactly.'
)


def _rubric(workflow: str):
    rubric = _RUBRICS.get(workflow)
    if rubric is None:
        raise ValueError(f'unsupported workflow: {workflow}')
    return rubric


def _run(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _first_gemini_image(response: dict) -> Image.Image:
    for candidate in response.get('candidates') or []:
        content = candidate.get('content') or {}
        for part in content.get('parts') or []:
            blob = part.get('inline_data') or {}
            data = blob.get('data')
            if isinstance(data, Image.Image):
                return data
            if isinstance(data, (bytes, bytearray)):
                import io

                img = Image.open(io.BytesIO(data))
                img.load()
                return img
    raise RuntimeError('Gemini response contained no image')


@pxt.udf(is_deterministic=False)
def produce_image(
    seed_image: Image.Image | None,
    task_type: str,
    gen_prompt: str | None,
    ref_image: Image.Image | None,
    ref_image_2: Image.Image | None,
    model: str | None,
    edit_model: str | None,
    size: str | None,
) -> Image.Image:
    """seed_image if set; else OpenAI generate or Gemini edit (stock Pixeltable UDFs)."""
    if seed_image is not None:
        return seed_image

    if task_type == 'image_generation':
        if not gen_prompt:
            raise ValueError('gen_prompt is required for image_generation when seed_image is unset')
        if not model:
            raise ValueError('model is required for image_generation')
        from pixeltable.functions.openai import image_generations

        model_kwargs = {'size': size} if size else None
        resp = _run(image_generations.aexec(gen_prompt, model=model, model_kwargs=model_kwargs))
        return resp['data'][0]

    if task_type == 'image_editing':
        if ref_image is None:
            raise ValueError('ref_image is required for image_editing when seed_image is unset')
        if not edit_model:
            raise ValueError('edit_model is required for image_editing (Gemini image model)')
        from pixeltable.functions.gemini import generate_content

        contents: list = [ref_image]
        if ref_image_2 is not None:
            contents.append(ref_image_2)
        contents.append(gen_prompt or '')
        resp = _run(generate_content.aexec(contents, model=edit_model, config=_GEMINI_IMAGE_CONFIG))
        return _first_gemini_image(resp)

    raise ValueError(f'unknown task_type: {task_type}')


@pxt.udf
def judge_instructions(workflow: str) -> str:
    return _rubric(workflow).SYSTEM_PROMPT


@pxt.udf
def judge_text_format(workflow: str) -> dict:
    rubric = _rubric(workflow)
    return {
        'format': {
            'type': 'json_schema',
            'name': rubric.SCHEMA_NAME,
            'schema': rubric.JSON_SCHEMA,
            'strict': True,
        }
    }


@pxt.udf
def judge_user_text(prompt: str, criteria: str) -> str:
    return f'Prompt:\n{prompt}\n\nCriteria:\n{criteria}\n\nScore the image.'


@pxt.udf
def parse_json(text: str | None) -> dict:
    if not text:
        return {}
    return json.loads(text)


@pxt.udf
def score_str(scores: dict | None, key: str) -> str | None:
    if not scores:
        return None
    val = scores.get(key)
    return None if val is None else str(val)


@pxt.udf(is_deterministic=False)
def extract_flyer_text(image: Image.Image, workflow: str, judge_model: str) -> list[str] | None:
    """Marketing only — OpenAI Responses via stock UDF (PIL in input_image)."""
    if workflow != 'marketing_flyer':
        return None
    from pixeltable.functions.openai import responses

    raw = _run(
        responses.aexec(
            [
                {
                    'role': 'user',
                    'content': [{'type': 'input_image', 'image_url': image}],
                }
            ],
            model=judge_model,
            model_kwargs={'instructions': _OCR_INSTRUCTIONS},
        )
    )
    text = raw.get('output_text') if isinstance(raw, dict) else None
    if not text:
        return []
    return [line.strip() for line in text.splitlines() if line.strip()]


@pxt.udf
def compare_required_text(extracted: list[str] | None, required_text: list | None) -> dict | None:
    if extracted is None or required_text is None:
        return None
    return marketing_text.compare_required(extracted, required_text)


@pxt.udf
def finalize_verdict(workflow: str, scores: dict | None, text_check: dict | None) -> str | None:
    if not scores:
        return None
    return _rubric(workflow).finalize_verdict(scores, text_check)


@pxt.udf
def failure_tags(workflow: str, scores: dict | None, text_check: dict | None) -> list[str]:
    if not scores:
        return []
    return _rubric(workflow).failure_tags(scores, text_check)
