import json
import time
from typing import Callable, Iterator

from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw

import shelterluv
import generator

def break_text(text, font, maxsize=2300, indent=False, total=1):
    partial = []
    first = True
    for c in text.split():
        s = font.getsize(' '.join(partial + [c]))[0]
        if s > maxsize:
            line = ' '.join(partial)
            if first and total > 1:
                line = '. ' + line
            if indent and not first and total > 1:
                line = '  ' + line
            yield line
            first = False
            partial = []
        partial.append(c)
    line = ' '.join(partial)
    if first and total > 1:
        line = '. ' + line
    if indent and not first and total > 1:
        line = '  ' + line
    yield line

def my_source() -> Iterator[shelterluv.Animal]:
    with open('src.json') as f:
        yield from json.load(f)


def get_dogs_newer_than(
        intake: int,
        source: Callable[[], Iterator[shelterluv.Animal]]) -> Iterator[shelterluv.Animal]:
    src = reversed(sorted(source(), key=lambda k: int(k['LastIntakeUnixTime'])))
    for dog in src:
        if int(dog['LastIntakeUnixTime']) < intake:
            return
        yield dog

def get_dogs_newer_than_days(
        days_ago: int,
        source: Callable[[], Iterator[shelterluv.Animal]]) -> Iterator[shelterluv.Animal]:
    now = int(time.time())
    yield from get_dogs_newer_than(now - days_ago*24*60*60, source=source)


def _write(text, x, y, img, font):
    size = font.getsize(text)
    text_img = Image.new('L', size, 255)
    draw_text_img = ImageDraw.Draw(text_img)
    draw_text_img.text((0, 0), text, font=font, fill=0)
    img.paste(text_img, (x, y))

def generate_card(name, breed, age, sex, location):
    img = Image.open('extra/new.jpg')
    draw = ImageDraw.Draw(img)
    font1 = ImageFont.truetype('fonts/Lato-Regular.ttf', 130)
    font2 = ImageFont.truetype('fonts/Lato-Regular.ttf', 80)
    font3 = ImageFont.truetype('fonts/Lato-Regular.ttf', 90)

    _write(name, 1050, 990, img, font1)
    words = [w for w in break_text(breed, font3, 1000) if w]
    n = len(words)
    for i, word in enumerate(words):
        if word:
            _write(word, 1050, 1500 - (n - i - 1)*110, img, font3)
    _write(age, 750, 1930, img, font1)
    _write(sex, 550, 2340, img, font1)
    _write(location, 10, 2900, img, font2)

    return img

def age_to_text(age):
    if age == 0:
        return 'younger than 1 month'
    years = age // 12
    months = age % 12
    year_plural = 's' if years > 1 else '' 
    month_plural = 's' if months > 1 else ''
    if years == 0:
        return f'{months} month{month_plural}'
    elif months == 0:
        return f'{years} year{year_plural}'
    else:
        return f'{years} year{year_plural}, {months} month{month_plural}'

def generate_temp_for_name(name):
    pass

def generate_temp_for_kennel(kennel):
    pass

def generate_file_for_days(n, source):
    filenames = []
    for animal in get_dogs_newer_than_days(n, source):
        name = animal['Name']
        print(f'Generating {name}')
        loc = animal['CurrentLocation']
        card = generate_card(
            animal['Name'], animal['Breed'],
            age_to_text(animal['Age']), animal['Sex'],
            ', '.join(x for x in [loc['Tier3'], loc.get('Tier4', None)] if x))
        card_filename = f'/tmp/temp_{name}.jpg'
        card.save(card_filename)
        filenames.append(card_filename)
        checklist_filename = f'/tmp/temp_{name}_checklist.jpg'
        checklist = generator.generate_checklist(animal['Name'])
        checklist.save(checklist_filename)
        filenames.append(checklist_filename)
    generator.concatenate(filenames)
