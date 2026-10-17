from sankhara.constants.config import CULTURE_GROUPS
import random


def make_name(elevation, gender):
    first_name = ''
    if gender == 'male':
        first_name = random.sample(CULTURE_GROUPS[elevation]['male_stems'], 1)[0] + \
                     random.sample(CULTURE_GROUPS[elevation]['male_suffixes'], 1)[0].split('-')[1]
    elif gender == 'female':
        first_name = random.sample(CULTURE_GROUPS[elevation]['female_stems'], 1)[0] + \
                     random.sample(CULTURE_GROUPS[elevation]['female_suffixes'], 1)[0].split('-')[1]
    last_name = random.sample(CULTURE_GROUPS[elevation]['last_stems'], 1)[0] + \
                random.sample(CULTURE_GROUPS[elevation]['last_suffixes'], 1)[0].split('-')[1]
    return f'{first_name} {last_name}'
