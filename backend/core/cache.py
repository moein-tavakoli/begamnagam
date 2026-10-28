"""The cache stores JSON data and atomic integers, never executable pickle."""
import json


class JSONSerializer:
    def dumps(self, value):
        # Redis INCR must continue to operate atomically on rate-limit counters.
        if type(value) is int:
            return value
        return json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")

    def loads(self, value):
        return json.loads(value)
