import re
import os
import datetime
import functools
import itertools
from collections import defaultdict

import requests
import shelterluv
import pygsheets
import pandas
from bs4 import BeautifulSoup

TESTING = False

if TESTING:
    SHEET = '1HJcSEDLYDiq6fgWJn3FsNpy407WUnjBTixxf5naE4Ic' # testing
else:
    SHEET = '1huASrSqMFRqfSgVLpq06JJxxEIRDOMOR9T_R9Vx5vXU' # production
GOOGLE_CREDENTIALS = os.environ.get('GOOGLE_CREDENTIALS', 'secret.json')
MM_PASSWORD = os.environ.get('MM_PASSWORD', '')
CC_PASSWORD = os.environ.get('CC_PASSWORD', '')
BEH_PASSWORD = os.environ.get('BEH_PASSWORD', '')

def get_name(name: str) -> str:
    return name.split('(')[0].strip()


def get_category(name: str) -> str:
    try:
        return re.search('\((.*)\)', name).group(1)
    except AttributeError:
        return ''

def fix_inplace(mmkl: pandas.DataFrame):
    mmkl['_Name'] = mmkl.iloc[:, 1].map(get_name)
    mmkl['_Category'] = mmkl.iloc[:, 1].map(get_category)


def format_breed(breed: str) -> str:
    return breed


def format_age(age: int) -> str:
    return '%.1f' %(age/12)


def format_intake(intake: int) -> int:
    return (datetime.datetime.now() - datetime.datetime.fromtimestamp(intake)).days


def format_kennel(loc):
    tier3 = loc.get('Tier3', '')
    tier4 = loc.get('Tier4', '')
    if tier3.startswith('Building') or tier3.startswith('AAC'):
        try:
            return tier4.split()[1]
        except IndexError:
            return '?'
    return tier3

def format_energy(energy):
    d = {
        'U': '',
        'L': 'Low',
        'M': 'Med',
        'H': 'High'
    }
    e = d.get(energy, '')
    print(f'Setting up energy d[{energy}] = {e}')
    return e

def format_hw(attrs):
    for d in attrs:
        if d['AttributeName'] == 'Heartworm +':
            return 'HW+'
    return ''


def format_total(dog_id: str) -> int:
    ### ACTIVATE
    #return 0
    ###
    if type(dog_id) is list:
        events = dog_id
    else:
        events = list(shelterluv.get_events(dog_id))
    events.sort(key=lambda x: int(x['Time']))
    total = 0

    state = 'START'
    for event in events:
        if state == 'START':
            if event['Type'].startswith('Intake.'):
                start_time = int(event['Time'])
                state = 'IN'
        elif state == 'IN':
            if event['Type'].startswith('Outcome.Adopt'):
                total += int(event['Time']) - start_time
                state = 'OUT'
        elif state == 'OUT':
            if event['Type'].startswith('Intake.'):
                start_time = int(event['Time'])
                state = 'IN'
    if state == 'IN':
        total += int(datetime.datetime.now().timestamp()) - start_time
    return int(total/(60*60*24))

def default(d):
    return defaultdict(lambda: defaultdict(lambda: ''), d)

def clear(ws):
    ws.clear(
        (2, 1),
        (ws.jsonSheet['properties']['gridProperties']['rowCount'],
         ws.jsonSheet['properties']['gridProperties']['columnCount']))

def fix_formulas(ws):
    rows = ws.jsonSheet['properties']['gridProperties']['rowCount']
    values = [
        [f'=IF( IF($E{i}=0,3,$E{i}) + IF($F{i}=0,3,$F{i}) > 6, IF($E{i}=0,3,$E{i})+IF($F{i}=0,3,$F{i}), 0 )']
        for i in range(2, rows)
    ]
    ws.update_cells('I2:I', values)

def dd_info(web_id):
    print(f'Getting info for {web_id}')
    r = requests.get(
        'http://www.dogdiaries.dreamhosters.com/?page_id=55&'
        f'dog_id={web_id}')
    r.raise_for_status()
    page = BeautifulSoup(r.text, 'html5lib')
    try:
        t = page.find(string='dog score')
        l = [x.text.split('-')[0].strip() for x in t.parent.parent.next_sibling.select('td')[:5]]
        beh_color = page.find(string='collar').parent.parent.next_sibling.select('td')[0].text.strip().lower()
    except Exception:
        beh_color = 'u'
        l = ['U', 'U', 'U', 'U', 'U']
    try:
        weight = page.find(string='weight').parent.parent.next_sibling.select('td')[0].text.split()[0]
    except Exception:
        weight = ''
    try:
        pg = page.find(string='pg/w/no').parent.parent.next_sibling.select('td')[2].text
        if pg == 'W' or pg =='W*' or pg == 'no':
            pg = ''
    except Exception:
        pg = ''
    def convert(x):
        if x == 'U':
            return 0
        return int(x)
    resp = {
        'dog': convert(l[0]),
        'cat': convert(l[1]),
        'child': convert(l[2]),
        'home': convert(l[3]),
        'energy': l[4],
        'collar': beh_color[0],
        'weight': weight,
        'pg': pg
    }
    return resp

def update_dd(web_id, dog, cat, child, home, energy):
    print(f'Will update {web_id} with {dog}, {cat}, {child}, {home}, {energy}')

def match(dd, dog, child, cat, home, energy):
    def convert_score(score):
        return int(score)
    def convert_energy(energy):
        if not energy:
            return 'U'
        return {
            'Low': 'L',
            'Med': 'M',
            'High': 'H'
        }[energy]
    return all([dd['dog'] == convert_score(dog),
                dd['cat'] == convert_score(cat),
                dd['child'] == convert_score(child),
                dd['home'] == convert_score(home),
                dd['energy'] == convert_energy(energy)])

class MMKL(object):

    def __init__(self, sl):
        self.sl = sl
        self.client = pygsheets.authorize(service_file=GOOGLE_CREDENTIALS)
        self.sheet = self.client.open_by_key(SHEET)
        #self.refresh()

    def refresh(self):
        self.ws = self.sheet.worksheet_by_title('MMKL')
        self.ws_df = self.ws.get_as_df()
        self.ws_df.set_index(['Name'], drop=False, inplace=True)
        self.ws_dict = default(self.ws_df.to_dict('index'))

        self.archive = self.sheet.worksheet_by_title('[Archive]')
        self.archive_df = self.archive.get_as_df()
        self.archive_df.set_index(['Name'], drop=False, inplace=True)
        self.archive_dict = default(self.archive_df.to_dict('index'))

        self.orig = self.sheet.worksheet_by_title('MMKL (old)')
        self.orig_df = self.orig.get_as_df()
        fix_inplace(self.orig_df)
        self.orig_df.set_index(['_Name'], drop=False, inplace=True)
        self.orig_dict = default(self.orig_df.to_dict('index'))

    def get_info(self):
        for name, dog in self.sl.by_name.items():
            dd = dd_info(dog['ID'])
            yield {
                'name': name,
                'breed': format_breed(dog['Breed']),
                'gender': dog['Sex'],
                'age_fraction': format_age(dog['Age']),
                'size': dog['Size'],
                'days_since_last_intake': format_intake(int(dog['LastIntakeUnixTime'])),
                'days_total': format_total(dog['Internal-ID']),
                'dd_info': dd,
                'web_id': dog['ID'],
                'kennel': format_kennel(dog['CurrentLocation']),
                'hw': format_hw(dog['Attributes']),
                'internal_id': dog['Internal-ID']
            }

    def process(self):

        def update_col(name, ws_col_name, orig_col_name, null=''):
            col = self.ws_dict[name][ws_col_name]
            if not col:
                try:
                    col = self.archive_dict[name][ws_col_name]
                except KeyError:
                    col = self.orig_dict[name][orig_col_name]
            if not col:
                return null
            return col

        all_rows = {}
        for it in self.get_info():
            name = it['name']
            dd = it['dd_info']
            new = {}
            internal_id = it['internal_id']
            new['Name'] = f'=HYPERLINK("https://www.shelterluv.com/memos_card/{internal_id}", "{name}")'
            new_notes = update_col(name, 'Notes', 'Matchmaker Notes')
            new_category = update_col(name, 'Category', '_Category')
            new_dog = update_col(name, 'Dog', 'Dog', null=0) 
            new_child = update_col(name, 'Child', 'Child', null=0)
            new_cat = update_col(name, 'Cat', 'Cat', null=0)
            new_home = update_col(name, 'Home', 'Home', null=0)
            toy = update_col(name, 'Toy preference', 'Toy Preference')
            home_notes = update_col(name, 'Has home notes (y/n)', 'Has Home Notes (Y/N)')
            last_updated = update_col(name, 'Notes/Scores last updated', 'Date Entered')

            new_energy = self.ws_dict[name]['Energy level']
            if not new_energy:
                new_energy = format_energy(dd['energy'])

            web_id = it['web_id']
            new['SL'] = f'=HYPERLINK("https://www.shelterluv.com/APA-A-{web_id}", "SL")'
            new['DD'] = f'=HYPERLINK("http://www.dogdiaries.dreamhosters.com/?page_id=55&dog_id={web_id}", "DD")'
            new['Category'] = new_category
            new['Dog'] = new_dog
            new['Child'] = new_child
            new['Cat'] = new_cat
            new['Home'] = new_home
            new['Dog+Child'] = 0
            new['Energy level'] = new_energy
            new['Collar'] = dd['collar']
            new['Notes/Scores last updated'] = last_updated
            new['Notes'] = new_notes
            new['Kennel'] = it['kennel']
            new['Days since last intake'] = it['days_since_last_intake']
            new['Total days at shelter'] = it['days_total']
            new['Size'] = it['size']
            new['Weight'] = dd['weight']
            new['Age'] = it['age_fraction']
            new['Breed'] = it['breed']
            new['Gender'] = it['gender']
            new['PG'] = dd['pg']
            new['HW'] = it['hw']
            #import pdb; pdb.set_trace()
            if self.ws_dict[name]['Scores match DD?'] == 'do update':
                print(f'Update {name} with dog: {new_dog}')
                update_dd(it['web_id'], new_dog, new_cat, new_child, new_home, new_energy)
                new['Scores match DD?'] = 'up to date'
            elif match(dd, new_dog, new_cat, new_child, new_home, new_energy):
                new['Scores match DD?'] = 'up to date'
            else:
                new['Scores match DD?'] = 'mismatch'
            new['Toy preference'] = toy 
            new['Has home notes (y/n)'] = home_notes 
            new['Memo link'] = f"https://www.shelterluv.com/memos_card/{internal_id}"
            new['SL link'] = f"https://www.shelterluv.com/APA-A-{web_id}"
            new['DD link'] = f"http://www.dogdiaries.dreamhosters.com/?page_id=55&dog_id={web_id}"
            all_rows[name] = new
        return all_rows

    def sync(self):
        all_rows = self.process()
        df = pandas.DataFrame.from_dict(all_rows, orient='index')
        clear(self.ws)
        self.ws.set_dataframe(df, start=(1, 1))
        fix_formulas(self.ws)
        self.archive_old(all_rows)

    def archive_old(self, rows):
        for name in self.ws_dict:
            if not name:
                continue
            if name not in rows:
                print(f'Will archive {name}')
                self.archive_dict[name] = {}
                self.archive_dict[name] = self.ws_dict[name]
        if not self.archive_dict:
            return
        d = {}
        for name, values in self.archive_dict.items():
             if any([v for _, v in values.items()]):
                 d[name] = values
        df = pandas.DataFrame.from_dict(d, orient='index')
        self.archive.set_dataframe(df, start=(1, 1))


def limited_source(src, limit=3):
    def _f():
        return itertools.islice(src(), limit)
    return _f

if TESTING:
    source = functools.partial(limited_source(shelterluv.json_source))
else:
    source = functools.partial(shelterluv.get_shelter_dogs, include_not_available=True)
#    source = limited_source(source)

def get_mmkl():
    mmkl = MMKL(shelterluv.Shelterluv(source))
    return mmkl


