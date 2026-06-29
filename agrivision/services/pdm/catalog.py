from __future__ import annotations

from typing import Any

PDM_MODEL_CATALOG: list[dict[str, Any]] = [
    {
        'key': 'grapevine_powdery_mildew_risk_v1',
        'crop': 'grapevine',
        'label': 'Grapevine Powdery Mildew',
        'organism_name': 'Erysiphe necator',
        'eppo_code': 'UNCINE',
        'fuzzy_crop_name': 'Vineyard',
        'fuzzy_scientific_names': ['Uncinula necator', 'Erysiphe necator'],
        'calculation_type': 'risk_index',
        'description': 'Starter weather-driven risk index for grapevine powdery mildew.',
        'risk_rules': [
            {
                'label': 'high',
                'conditions': [
                    {'field': 'temperature_c', 'op': 'between', 'value': [21.0, 29.0]},
                    {'field': 'relative_humidity_pct', 'op': '>=', 'value': 60.0},
                ],
                'recommendation': 'Conditions favor grapevine powdery mildew. Intensify scouting and review treatment timing.',
            },
            {
                'label': 'moderate',
                'conditions': [
                    {'field': 'temperature_c', 'op': 'between', 'value': [16.0, 30.0]},
                    {'field': 'relative_humidity_pct', 'op': '>=', 'value': 45.0},
                ],
                'recommendation': 'Moderately favorable conditions. Continue scouting and inspect susceptible canopy zones.',
            },
        ],
        'default_label': 'low',
        'default_recommendation': 'Current conditions are not strongly favorable. Maintain routine monitoring.',
    },
    {
        'key': 'olive_leaf_spot_risk_v1',
        'crop': 'olive',
        'label': 'Olive Leaf Spot',
        'organism_name': 'Venturia oleaginea',
        'eppo_code': 'CYCLOL',
        'fuzzy_crop_name': 'Olive',
        'fuzzy_scientific_names': ['Venturia oleaginea', 'Spilocea oleagina'],
        'calculation_type': 'risk_index',
        'description': 'Starter weather-driven risk index for olive leaf spot / peacock spot.',
        'risk_rules': [
            {
                'label': 'high',
                'conditions': [
                    {'field': 'relative_humidity_pct', 'op': '>=', 'value': 90.0},
                    {'field': 'temperature_c', 'op': 'between', 'value': [10.0, 20.0]},
                    {'field': 'precipitation_mm', 'op': '>=', 'value': 1.0},
                ],
                'recommendation': 'Wet, mild conditions favor olive leaf spot infection. Prioritize scouting after rainfall or long wet periods.',
            },
            {
                'label': 'moderate',
                'conditions': [
                    {'field': 'relative_humidity_pct', 'op': '>=', 'value': 80.0},
                    {'field': 'temperature_c', 'op': 'between', 'value': [5.0, 25.0]},
                ],
                'recommendation': 'Moderately favorable conditions. Continue monitoring and inspect denser canopy areas.',
            },
        ],
        'default_label': 'low',
        'default_recommendation': 'Conditions are not strongly favorable. Maintain routine monitoring.',
    },
    {
        'key': 'grapevine_downy_mildew_risk_v1',
        'crop': 'grapevine',
        'label': 'Grapevine Downy Mildew',
        'organism_name': 'Plasmopara viticola',
        'eppo_code': 'PLASVI',
        'fuzzy_crop_name': 'Vineyard',
        'fuzzy_scientific_names': ['Plasmopora viticola', 'Plasmopara viticola'],
        'calculation_type': 'risk_index',
        'description': 'Starter weather-driven risk index for grapevine downy mildew.',
        'risk_rules': [
            {
                'label': 'high',
                'conditions': [
                    {'field': 'precipitation_mm', 'op': '>=', 'value': 5.0},
                    {'field': 'relative_humidity_pct', 'op': '>=', 'value': 85.0},
                    {'field': 'temperature_c', 'op': 'between', 'value': [12.0, 25.0]},
                ],
                'recommendation': 'Moist, mild conditions favor downy mildew infection. Inspect canopy and consider preventive management.',
            },
            {
                'label': 'moderate',
                'conditions': [
                    {'field': 'relative_humidity_pct', 'op': '>=', 'value': 75.0},
                    {'field': 'temperature_c', 'op': 'between', 'value': [10.0, 28.0]},
                ],
                'recommendation': 'Partially favorable infection conditions. Maintain close monitoring.',
            },
        ],
        'default_label': 'low',
        'default_recommendation': 'Conditions are not strongly favorable. Maintain routine monitoring.',
    },
    {
        'key': 'olive_fruit_fly_risk_v1',
        'crop': 'olive',
        'label': 'Olive Fruit Fly',
        'organism_name': 'Bactrocera oleae',
        'eppo_code': 'DACUOL',
        'fuzzy_crop_name': 'Olive',
        'fuzzy_scientific_names': ['Bactrocera oleae'],
        'calculation_type': 'risk_index',
        'description': 'Starter weather-driven risk index for olive fruit fly activity.',
        'risk_rules': [
            {
                'label': 'high',
                'conditions': [
                    {'field': 'temperature_c', 'op': 'between', 'value': [18.0, 30.0]},
                    {'field': 'relative_humidity_pct', 'op': '>=', 'value': 60.0},
                ],
                'recommendation': 'Conditions may support olive fruit fly activity. Increase trap checks and fruit inspection frequency.',
            },
            {
                'label': 'moderate',
                'conditions': [
                    {'field': 'temperature_c', 'op': 'between', 'value': [15.0, 32.0]},
                    {'field': 'relative_humidity_pct', 'op': '>=', 'value': 45.0},
                ],
                'recommendation': 'Some activity may be possible. Keep monitoring.',
            },
        ],
        'default_label': 'low',
        'default_recommendation': 'Conditions are not strongly favorable. Maintain routine monitoring.',
    },
]

DEFAULT_PDM_MODEL_KEY = 'grapevine_powdery_mildew_risk_v1'


def get_pdm_model(model_key: str | None) -> dict[str, Any]:
    if model_key:
        for item in PDM_MODEL_CATALOG:
            if item['key'] == model_key:
                return item
    return next(item for item in PDM_MODEL_CATALOG if item['key'] == DEFAULT_PDM_MODEL_KEY)


def get_models_for_crop(crop: str | None) -> list[dict[str, Any]]:
    if not crop:
        return list(PDM_MODEL_CATALOG)
    lowered = crop.strip().lower()
    return [item for item in PDM_MODEL_CATALOG if item['crop'] == lowered]
