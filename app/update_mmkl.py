import datetime
import functools

import shelterluv


def format_breed(breed: str) -> str:
    return breed


def format_age(age: int) -> str:
    return '%.1f' %(age/12)


def format_intake(intake: int) -> int:
    return (datetime.datetime.now() - datetime.datetime.fromtimestamp(intake)).days


def format_total(dog_id: str) -> int:
    events = shelterluv.get_events(dog_id)
    events.sort(key=lambda x: int(x['Time']))
    partial = total = 0
    for event in events:
        if event['Type'].startswith('Intake.'):
            partial = int(event['Time'])
        if event['Type'].startswith('Outcome.'):
            total += int(event['Time']) - partial
            partial = 0
    if partial != 0:
        total += int(datetime.datetime.now().timestamp()) - partial
    return int(total/(60*60*24))


class MMKL(object):

    def __init__(self, sl):
        self.sl = sl

    def refresh(self):
        self.sl.refresh()

    def __iter__(self):
        for name, dog in self.sl.by_name.items():
            yield {
                'name': name,
                'breed': format_breed(dog['Breed']),
                'gender': dog['Sex'],
                'age_fraction': format_age(dog['Age']),
                'size': dog['Size'],
                'days_since_last_intake': format_intake(int(dog['LastIntakeUnixTime'])),
                'days_total': format_total(dog['Internal-ID'])
            }


#source = functools.partial(shelterluv.get_shelter_dogs, include_not_available=True)
source = functools.partial(shelterluv.json_source)
mmkl = MMKL(shelterluv.Shelterluv(source))

