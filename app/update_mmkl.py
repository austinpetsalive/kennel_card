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


SHEET = '1vBN4Z1IxXvdbYkOmJDSZ_h_iD3SSdDpgTxW704bSDJA' # testing
#SHEET = '1huASrSqMFRqfSgVLpq06JJxxEIRDOMOR9T_R9Vx5vXU' # production
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
        [f'=IF(C{i}+D{i}>=6,C{i}+D{i},0)'] for i in range(2, rows)
    ]
    ws.update_cells('G2:G', values)

def dd_info(web_id):
    print(f'Getting info for {web_id}')
    r = requests.get(
        'http://www.dogdiaries.dreamhosters.com/?page_id=55&'
        f'dog_id={web_id}')
    r.raise_for_status()
    page = BeautifulSoup(r.text, 'html5lib')
    t = page.find(string='dog score')
    l = [x.text.split('-')[0].strip() for x in t.parent.parent.next_sibling.select('td')[:5]]
    beh_color = page.find(string='collar').parent.parent.next_sibling.select('td')[0].text.strip().lower()
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
        'collar': beh_color[0]
    }
    return resp

def update_dd(web_id, dog, cat, child, home, energy):
    print(f'Will update {web_id} with {dog}, {cat}, {child}, {home}, {energy}')

class MMKL(object):

    def __init__(self, sl):
        self.sl = sl
        self.client = pygsheets.authorize(service_file=GOOGLE_CREDENTIALS)
        self.sheet = self.client.open_by_key(SHEET)
        #self.refresh()

    def refresh(self):
        self.ws = self.sheet.worksheet_by_title('Experiments')
        self.ws_df = self.ws.get_as_df()
        self.ws_df.set_index(['Name'], drop=False, inplace=True)
        self.ws_dict = default(self.ws_df.to_dict('index'))

#        self.archive = self.sheet.worksheet_by_title('Experiments [Archive]')
#        self.archive_df = self.archive.get_as_df()
#        self.archive_df.set_index(['Name'], drop=False, inplace=True)
#        self.archive_dict = default(self.ws_df.to_dict('index'))

        self.orig = self.sheet.worksheet_by_title('MMKL')
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
                'web_id': dog['ID']
            }

    def process(self):
        all_rows = {}
        for it in self.get_info():
            name = it['name']
            dd = it['dd_info']
            new = {}
            new['Name'] = name
            new_notes = self.ws_dict[name]['Notes']
            if not new_notes:
                new_notes = self.orig_dict[name]['Matchmaker Notes']
            new_dog = self.ws_dict[name]['Dog']
            if not new_dog:
                new_dog = self.orig_dict[name]['Dog']
            new_category = self.ws_dict[name]['Category']
            if not new_category:
                new_category = self.orig_dict[name]['_Category']
            new_child = self.ws_dict[name]['Child']
            if not new_child:
                new_child = self.orig_dict[name]['Child']
            new_cat = self.ws_dict[name]['Cat']
            if not new_cat:
                new_cat = self.orig_dict[name]['Cat']
            new_home = self.ws_dict[name]['Home']
            if not new_home:
                new_home = self.orig_dict[name]['Home']
            toy = self.ws_dict[name]['Toy preference']
            if not toy:
                toy = self.orig_dict[name]['Toy Preference']
            home_notes = self.ws_dict[name]['Has home notes (y/n)']
            if not home_notes:
                home_notes = self.orig_dict[name]['Has Home Notes (Y/N)']
            new_energy = self.ws_dict[name]['Energy level']
            if not new_energy:
                new_energy = dd['energy']
            new['Category'] = new_category
            new['Dog'] = new_dog
            new['Child'] = new_child
            new['Cat'] = new_cat
            new['Home'] = new_home
            new['Dog+Child'] = 0
            new['Energy level'] = new_energy 
            new['Collar'] = dd['collar']
            new['Notes'] = new_notes
            new['Days since last intake'] = it['days_since_last_intake']
            new['Total days at shelter'] = it['days_total']
            new['Size'] = it['size']
            new['Age'] = it['age_fraction']
            new['Breed'] = it['breed']
            new['Gender'] = it['gender']
            if self.ws_dict[name]['Scores match DD?'] == 'do update':
                print(f'Update {name} with dog: {new_dog}')
                update_dd(it['web_id'], new_dog, new_cat, new_child, new_home, new_energy)
                new['Scores match DD?'] = 'up to date'
            elif all([dd['dog'] == new_dog, dd['cat'] == new_cat,
                      dd['child'] == new_child, dd['home'] == new_home,
                      dd['energy'] == new_energy]):
                new['Scores match DD?'] = 'up to date'
            else:
                new['Scores match DD?'] = 'mismatch'
            new['Toy preference'] = toy 
            new['Has home notes (y/n)'] = home_notes 
            all_rows[name] = new
        return all_rows

    def sync(self):
        clear(self.ws)
        df = pandas.DataFrame.from_dict(self.process(), orient='index')
        self.ws.set_dataframe(df, start=(1, 1))
        fix_formulas(self.ws)



#source = functools.partial(shelterluv.get_shelter_dogs, include_not_available=True)

def limited_source(src, limit=10):
    def _f():
        return itertools.islice(src(), limit)
    return _f

source = functools.partial(limited_source(shelterluv.json_source))
mmkl = MMKL(shelterluv.Shelterluv(source))


