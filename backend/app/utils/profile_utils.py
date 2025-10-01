from typing import Dict, Any, List, Tuple


def _list_intake_field_keys() -> List[str]:
    try:
        # Prefer deriving keys from the Pydantic model to keep in sync
        from app.schemas.intake import IntakeFields  # lazy import to avoid heavy deps at module import
        return list(IntakeFields.model_fields.keys())
    except Exception:
        # Fallback hardcoded list (must mirror IntakeFields)
        return [
            "full_name",
            "age",
            "email",
            "phone",
            "academic_level",
            "recent_grades",
            "institution",
            "year_completed",
            "major",
            "field_of_study",
            "preferred_countries",
            "target_level",
            "english_tests",
            "financial",
            "budget_min",
            "budget_max",
            "career_goals",
            "completed_fields",
        ]


def normalize_profile_shape(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure profile has all IntakeFields keys and a normalized completed_fields list."""
    profile = dict(profile or {})
    keys = _list_intake_field_keys()
    for k in keys:
        profile.setdefault(k, None if k != "completed_fields" else [])
    # Normalize completed_fields as a list of strings
    completed_raw = profile.get("completed_fields")
    if isinstance(completed_raw, list):
        completed = [str(x) for x in completed_raw if isinstance(x, (str,))]
    elif isinstance(completed_raw, str):
        completed = [completed_raw]
    else:
        completed = []
    # Seed contact fields as completed if present
    for seed_key in ("full_name", "email", "phone"):
        if profile.get(seed_key):
            if seed_key not in completed:
                completed.append(seed_key)
    # De-duplicate and store
    profile["completed_fields"] = sorted(list({*completed}))
    return profile


def split_incomplete_fields(profile: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Return a dict of only incomplete fields (value is currently empty) and the ordered list of all intake keys.

    A field is considered incomplete if it is not in completed_fields AND its value is falsy/empty
    (None, "", empty list/dict).
    """
    normalized = normalize_profile_shape(profile)
    completed = set(normalized.get("completed_fields") or [])
    keys = _list_intake_field_keys()

    def _is_empty(v: Any) -> bool:
        if v is None:
            return True
        if isinstance(v, str) and v.strip() == "":
            return True
        if isinstance(v, (list, dict)) and len(v) == 0:
            return True
        return False

    incomplete: Dict[str, Any] = {}
    for k in keys:
        if k == "completed_fields":
            continue
        if k in completed:
            continue
        if _is_empty(normalized.get(k)):
            incomplete[k] = None
    return incomplete, keys


