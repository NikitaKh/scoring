import random


class Scoring:

    @staticmethod
    def get_score(**kwargs):
        score = 0
        if kwargs.get("phone"):
            score += 1.5
        if kwargs.get("email"):
            score += 1.5
        if kwargs.get("birthday") and kwargs.get("gender") is not None:
            score += 1.5
        if kwargs.get("first_name") and kwargs.get("last_name"):
            score += 0.5
        return score

    @staticmethod
    def get_interests():
        interests = ["cars", "pets", "travel", "hi-tech", "sport", "music", "books", "tv", "cinema", "geek", "otus"]
        return random.sample(interests, 2)
