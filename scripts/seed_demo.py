"""Load the demo cases into the harness. Inserting generates each image.

This inserts the four example rows into the generations and edits tables with
eval_ready=False. Pixeltable generates each image on insert, so this calls OpenAI
(the two generations) and Gemini (the two edits). Set eval_ready=True later to
grade them.

Usage:
    uv run pxt schema update schema.py img_eval --allow-destructive -f
    uv run python scripts/seed_demo.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import udfs  # noqa: F401  # register the UDFs before touching tables
import pixeltable as pxt

USE_CASES = ROOT / 'use_cases'
BATCH_ID = 'demo_v1'
CASES = ('ui_mockup', 'marketing_flyer', 'virtual_try_on', 'logo_edit')


def _row(folder: Path, data: dict) -> dict:
    row: dict = {
        'case_id': data['case_id'],
        'batch_id': BATCH_ID,
        'workflow': data['workflow'],
        'gen_prompt': data['gen_prompt'],
        'prompt': data['prompt'],
        'criteria': data['criteria'],
        'eval_ready': False,
    }
    if ref := data.get('ref_image'):
        row['ref_image'] = str(folder / ref)
    if ref2 := data.get('ref_image_2'):
        row['ref_image_2'] = str(folder / ref2)
    if req_file := data.get('required_text_file'):
        row['required_text'] = json.loads((folder / req_file).read_text())
    return row


def main() -> None:
    generations = pxt.get_table('img_eval/generations')
    edits = pxt.get_table('img_eval/edits')

    seeded = len(generations.where(generations.batch_id == BATCH_ID).collect()) + len(
        edits.where(edits.batch_id == BATCH_ID).collect()
    )
    if seeded > 0:
        print(f'batch {BATCH_ID!r} already seeded ({seeded} rows); skipping insert')
        return

    gen_rows: list[dict] = []
    edit_rows: list[dict] = []
    for name in CASES:
        folder = USE_CASES / name
        data = json.loads((folder / 'examples.json').read_text())
        target = gen_rows if data['table'] == 'generations' else edit_rows
        target.append(_row(folder, data))

    print(f'generating {len(gen_rows)} images with OpenAI and {len(edit_rows)} edits with Gemini...')
    generations.insert(gen_rows)
    edits.insert(edit_rows)
    print('done. images are generated, eval_ready=False (not graded yet).')
    print('grade them in demo.ipynb, or:')
    print('  generations = pxt.get_table("img_eval/generations")')
    print(f'  generations.update({{"eval_ready": True}}, where=generations.batch_id == "{BATCH_ID}")')
    print('  pxt.get_table("img_eval/gen_evals").select(gen_evals.case_id, gen_evals.verdict).collect()')


if __name__ == '__main__':
    main()
