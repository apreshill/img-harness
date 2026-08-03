"""Seed already-generated demo rows (eval_ready=False).

Usage:
    uv run pxt schema update schema.py img_eval -f
    uv run python scripts/seed_demo.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import udfs  # noqa: F401  # register UDFs before touching tables
import pixeltable as pxt

USE_CASES = ROOT / 'use_cases'
BATCH_ID = 'demo_v1'


def _load_example(name: str) -> tuple[Path, dict]:
    folder = USE_CASES / name
    data = json.loads((folder / 'examples.json').read_text())
    return folder, data


def _row(folder: Path, data: dict) -> dict:
    row: dict = {
        'case_id': data['case_id'],
        'batch_id': BATCH_ID,
        'workflow': data['workflow'],
        'task_type': data['task_type'],
        'gen_prompt': data.get('gen_prompt'),
        'model': data.get('model'),
        'edit_model': data.get('edit_model'),
        'size': data.get('size'),
        'judge_model': data['judge_model'],
        'prompt': data['prompt'],
        'criteria': data['criteria'],
        'eval_ready': False,
    }
    if seed := data.get('seed_image'):
        row['seed_image'] = str(folder / seed)
    if ref := data.get('ref_image'):
        row['ref_image'] = str(folder / ref)
    if ref2 := data.get('ref_image_2'):
        row['ref_image_2'] = str(folder / ref2)
    if req_file := data.get('required_text_file'):
        row['required_text'] = json.loads((folder / req_file).read_text())
    return row


def main() -> None:
    images = pxt.get_table('img_eval/images')
    existing = images.where(images.batch_id == BATCH_ID).collect()
    if len(existing) > 0:
        print(f'batch {BATCH_ID!r} already has {len(existing)} rows; skipping insert')
        return

    rows = []
    for name in ('ui_mockup', 'marketing_flyer', 'virtual_try_on', 'logo_edit'):
        folder, data = _load_example(name)
        rows.append(_row(folder, data))

    status = images.insert(rows)
    print(f'inserted {status.num_rows} demo rows into img_eval/images (eval_ready=False)')
    print('evaluate with:')
    print('  import udfs')
    print('  import pixeltable as pxt')
    print('  images = pxt.get_table("img_eval/images")')
    print(f'  images.update({{"eval_ready": True}}, where=images.batch_id == "{BATCH_ID}")')
    print('  evals = pxt.get_table("img_eval/evals")')
    print('  evals.select(evals.case_id, evals.verdict, evals.reason, evals.tags).collect()')


if __name__ == '__main__':
    main()
