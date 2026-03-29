from __future__ import annotations

import pytest

from agrivision.app.schemas.runs import RunCreateRequest


def test_run_schema_requires_non_blank_names() -> None:
    payload = {
        'run_name': 'Spring Survey',
        'dataset_name': 'Field A',
        'upload_run_id': 'upload-1',
        'selected_steps': {'run_odm': True, 'fetch_weather': True, 'generate_report': True},
        'parameters': {},
    }
    model = RunCreateRequest.model_validate(payload)
    assert model.run_name == 'Spring Survey'

    payload['run_name'] = '   '
    with pytest.raises(Exception):
        RunCreateRequest.model_validate(payload)
