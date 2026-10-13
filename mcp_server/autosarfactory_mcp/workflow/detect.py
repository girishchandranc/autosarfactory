"""
Classify a natural-language modelling request as ECUC (BSW module configuration)
or SYSTEM (SWCs, interfaces, networks, data types ...). Deterministic keyword
scoring - no AI involved.

detect(request) -> {type, confidence, scores, signals, ecuc_modules, use_cases}
"""

import re

from . import srv

_ECUC_TERMS = {
    "ecuc": 4, "bsw": 3, "bsw module": 4, "module configuration": 4, "ecu configuration": 4,
    "container": 2, "parameter value": 2, "param def": 3, "definition-ref": 4,
    "ecucvalues": 4, "configure the": 1, "configuration of": 1, "pre-compile": 2,
    "post-build": 2, "link-time": 2, "basic software": 3,
}
_SYSTEM_TERMS = {
    "swc": 4, "software component": 4, "component type": 3, "port": 2, "pport": 3, "rport": 3,
    "interface": 2, "sender-receiver": 4, "sender receiver": 4, "client-server": 4,
    "client server": 4, "data element": 3, "runnable": 3, "composition": 3,
    "ecu instance": 4, "ecuinstance": 4, "system": 1, "cluster": 2, "physical channel": 3,
    "frame": 2, "pdu": 1, "isignal": 3, "signal": 2, "can network": 3, "ethernet": 2,
    "some/ip": 3, "someip": 3, "lin": 1, "flexray": 2, "data type": 2, "datatype": 2,
    "implementation data type": 4, "application data type": 4, "compu method": 3,
    "compumethod": 3, "base type": 3, "dext": 3, "dtc": 2, "connector": 2, "mode switch": 3,
}


def _score(text: str, terms: dict) -> tuple[int, list]:
    hits, score = [], 0
    for term, weight in terms.items():
        if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text):
            hits.append(term)
            score += weight
    return score, hits


def detect(request: str) -> dict:
    text = request.lower()
    ecuc_score, ecuc_hits = _score(text, _ECUC_TERMS)
    sys_score, sys_hits = _score(text, _SYSTEM_TERMS)

    # BSW module names (CanIf, Os, ComM ...) are strong ECUC signals. Require a
    # word-boundary, case-sensitive match so "Os" doesn't fire on "most".
    modules = [m for m in srv()._ecuc_modules
               if len(m) > 2 and re.search(rf"\b{re.escape(m)}\b", request)
               or len(m) <= 2 and re.search(rf"\b{re.escape(m)}\b(?=\s+(module|config|task|alarm|counter|application|isr|event))", request)]
    ecuc_score += 4 * len(modules)
    # Container names (OsTask, CanIfRxPduCfg ...) are even stronger.
    containers = [c for c in srv()._ecuc_containers if len(c) > 4 and re.search(rf"\b{re.escape(c)}\b", request)]
    ecuc_score += 5 * len(containers)

    # Explicit class names from the API DB that belong to the system side.
    classes = [c for c in srv()._db["classes"]
               if len(c) > 5 and not c.startswith("Ecuc") and re.search(rf"\b{re.escape(c)}\b", request)]
    sys_score += 3 * len(classes)

    # Rank element-map use cases by how many of their title words appear in the request.
    _stop = {"and", "the", "with", "use", "case", "from", "into", "over", "same", "communication"}
    ranked = []
    for title in srv()._elem_map_sections:
        words = {w for w in re.findall(r"[a-z/\-]{3,}", title.lower()) if w not in _stop}
        hits = sum(1 for w in words if re.search(rf"(?<![a-z]){re.escape(w)}s?(?![a-z])", text))
        if hits:
            ranked.append((hits, title))
    ranked.sort(key=lambda x: -x[0])
    best = ranked[0][0] if ranked else 0
    use_cases = [t for h, t in ranked if h == best or (best >= 3 and h == best - 1)][:4]

    total = ecuc_score + sys_score
    if total == 0:
        kind, confidence = "unknown", 0.0
    elif ecuc_score > 0 and sys_score > 0 and min(ecuc_score, sys_score) / max(ecuc_score, sys_score) > 0.6:
        kind, confidence = "mixed", round(max(ecuc_score, sys_score) / total, 2)
    else:
        kind = "ecuc" if ecuc_score > sys_score else "system"
        confidence = round(max(ecuc_score, sys_score) / total, 2)

    return {
        "type": kind,
        "confidence": confidence,
        "scores": {"ecuc": ecuc_score, "system": sys_score},
        "signals": {"ecuc_terms": ecuc_hits, "system_terms": sys_hits,
                    "ecuc_containers": containers[:10], "system_classes": classes[:10]},
        "ecuc_modules": modules,
        "use_cases": use_cases[:6] if kind != "ecuc" else [],
    }

