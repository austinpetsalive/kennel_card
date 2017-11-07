import json
import os
from typing import (Iterator, Dict, List, Sequence, Any, Optional,
                    Tuple, Callable, DefaultDict, Mapping)

import requests


SHELTERLUV_KEY = os.environ['SHELTERLUV_KEY']


Animal = Dict[str, Any]
Events = Dict[str, Any]


class APIError(Exception):
    pass


def get_from_shelterluv(
        url: str, field: Optional[str] = None) -> Iterator[Dict[str, Any]]:
    offset = 0
    while True:
        print(f'Requesting offset = {offset}')
        r = requests.get(
            f'https://www.shelterluv.com/api/v1/'
            f'{url}?offset={offset}&status_type=in custody',
            headers={'X-Api-Key': SHELTERLUV_KEY})
        r.raise_for_status()
        j = r.json()
        if field is None:
            yield j
            return
        if j['success'] != 1:
            raise APIError(j['error_message'])
        yield from j[field]
        if not j['has_more']:
            return
        offset += 100

def get_all_animals() -> Iterator[Animal]:
    return get_from_shelterluv('animals', 'animals')

def get_shelter_dogs(include_not_available=False) -> Iterator[Animal]:
    return (a for a in get_all_animals()
            if a['Type'] == 'Dog'
            and (include_not_available or a['Status'] == 'Available In Shelter')
            and a.get('CurrentLocation')
            and a['CurrentLocation'].get('Tier2') == 'TLAC'
            and a['CurrentLocation'].get('Tier3') != 'Barn')

def get_shelter_dogs_test() -> Iterator[Animal]:
    yield from [
        {'Name': 'Foo', 'ID': 3},
        {'Name': 'Bar', 'ID': 12},
        {'Name': 'Baz', 'ID': 23312}
    ]

def get_id(a: Animal) -> str:
    return a['Internal-ID']

def get_animal(animal_id: str) -> Animal:
    return next(get_from_shelterluv(f'animals/{animal_id}'))

def get_events(animal_id: str) -> Iterator[Events]:
    return get_from_shelterluv(f'animals/{animal_id}/events', 'events')

def json_source():
    with open('src.json') as f:
        yield from json.load(f)

class Shelterluv(object):

    def __init__(self, source=None):
        self.source = source
        self.refresh()

    def refresh(self):
        full = list(self.source())
        self.by_name = {dog['Name']: dog for dog in full}
        self.by_location = {
            (dog['CurrentLocation']['Tier3'], dog['CurrentLocation'].get('Tier4')): dog
            for dog in full
        }
