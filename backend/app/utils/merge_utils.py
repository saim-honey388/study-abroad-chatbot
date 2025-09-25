from datetime import datetime
from typing import Any, Dict


def merge_profile(existing_profile: Dict[str, Any], new_fields: Dict[str, Any]) -> Dict[str, Any]:
    """
    Minimal merge: shallow update for primitives and dicts, extend lists uniquely.
    Sets last_updated to now (ISO format).
    """
    if not new_fields:
        result = dict(existing_profile)
        result["last_updated"] = datetime.utcnow().isoformat()
        return result

    merged = dict(existing_profile)
    for key, value in new_fields.items():
        if value is None:
            continue
        if isinstance(value, list):
            existing_list = merged.get(key) or []
            # de-duplicate by value equality
            merged[key] = existing_list + [v for v in value if v not in existing_list]
        elif isinstance(value, dict):
            existing_dict = merged.get(key) or {}
            updated = dict(existing_dict)
            updated.update(value)
            merged[key] = updated
        else:
            merged[key] = value

    merged["last_updated"] = datetime.utcnow().isoformat()
    return merged


