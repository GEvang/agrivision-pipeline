from __future__ import annotations


def format_system_datetime(value):
    if value is None:
        return ''
    if isinstance(value, str):
        try:
            from datetime import datetime
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return value
    try:
        localized = value.astimezone() if getattr(value, 'tzinfo', None) is not None else value
    except Exception:
        localized = value
    return localized.strftime('%Y-%m-%d %H:%M:%S')


def format_duration(started_at, finished_at):
    if started_at is None:
        return '-'
    end_value = finished_at
    if end_value is None:
        from datetime import datetime, timezone
        end_value = datetime.now(timezone.utc)
    try:
        seconds = int(max(0, (end_value - started_at).total_seconds()))
    except Exception:
        return '-'
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f'{hours}h {minutes}m'
    if minutes:
        return f'{minutes}m {secs}s'
    return f'{secs}s'


def step_summary(run) -> str:
    selected = run.selected_steps
    parts = [
        'ODM' if selected.run_odm else 'Existing orthos',
        'Weather' if selected.fetch_weather else 'No weather',
        'Irrigation' if selected.run_irrigation else 'No irrigation',
        'PDM' if selected.run_pdm else 'No PDM',
    ]
    return ' / '.join(parts)
