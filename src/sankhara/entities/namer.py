import random

from sankhara.constants.config import CULTURE_GROUPS


def _join(rng, stems, suffixes):
    return (rng.choice(stems) + rng.choice(suffixes).split("-")[1]).capitalize()


def make_first_name(culture, gender, rng=random):
    group = CULTURE_GROUPS[culture]
    if gender == "male":
        return _join(rng, group["male_stems"], group["male_suffixes"])
    return _join(rng, group["female_stems"], group["female_suffixes"])


def make_family_name(culture, rng=random):
    group = CULTURE_GROUPS[culture]
    return _join(rng, group["last_stems"], group["last_suffixes"])


def make_name(elevation, gender, rng=random):
    return f"{make_first_name(elevation, gender, rng)} {make_family_name(elevation, rng)}"
