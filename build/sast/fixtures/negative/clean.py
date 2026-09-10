# SAST negative fixture — must NOT trigger any rule. Compliant tooling:
# JSON-only deserialization, no pickle.
import json


def load(blob: str):
    return json.loads(blob)
