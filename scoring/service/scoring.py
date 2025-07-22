import hashlib


class Scoring:

    def __init__(self, store):
        self.store = store

    def get_score(self, **kwargs) -> float:
        key_parts = [
            kwargs.get("first_name") or "",
            kwargs.get("last_name") or "",
            kwargs.get("phone") or "",
            kwargs.get("birthday") or "",
        ]
        key = "uid:" + hashlib.md5("".join(key_parts).encode("utf-8")).hexdigest()

        r = self.store.call("cache_get", key)
        print("TEST ", r.data)
        score = r.data[0]
        if score is not None:
            return float(score)

        score = 0.0
        if kwargs.get("phone"):
            score += 1.5
        if kwargs.get("email"):
            score += 1.5
        if kwargs.get("birthday") and kwargs.get("gender") is not None:
            score += 1.5
        if kwargs.get("first_name") and kwargs.get("last_name"):
            score += 0.5

        # Cache the score for 60 minutes
        self.store.call("cache_set", (key, score, 60 * 60))
        return score

    def get_interests(self, cid) -> list:
        r = self.store.call("interests_get", (cid))
        return r.data if r.data else []
