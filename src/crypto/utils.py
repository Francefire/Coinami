import hashlib
import json


def hash_data(data) -> str:
    """Calcule le SHA-256 d'une structure de données (dict ou str).

    Pour garantir le déterminisme, les dicts sont sérialisés en JSON
    avec les clés triées.
    """
    if isinstance(data, str):
        raw = data
    else:
        raw = json.dumps(data, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
