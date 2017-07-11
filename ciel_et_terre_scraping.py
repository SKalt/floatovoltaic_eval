import os
import re
from lxml import html
import requests
import pandas as pd
from datetime import datetime, timedelta
from tqdm import tqdm
#%%
def fetch(target):
    if not re.match(r'^http://www.ciel-et-terre.net', target):
        if not re.match('^/', target):
            target = '/' + target
        target = 'http://www.ciel-et-terre.net' + target
    fetched = requests.get(target)
    if fetched.status_code == 200:
        return html.fromstring(fetched.content.decode())
    else:
        raise ValueError('Status code {}'.format(fetched.status_code))
        
def get_page(li):
    try:
        a = li.cssselect('a.eg-washington-element-10')[0]
        href = a.get('href')
        return fetch(href)
    except IndexError:
      raise IndexError('no a.eg-washington-element-10 found')

def get_name_kwp(li):
    try:
        div = li.cssselect('div.esg-center.esg-flipdown')[0]
        text = re.sub('(?i)floating solar(?: pv)? (system|plant)\W*-', '', div.text)
        name, _, kwp = text.partition('-')
        return name.strip(), kwp.strip()
    except IndexError:
        raise IndexError('no title div found')

def search(regex_pattern, text):
    if not text:
        text = ''
    regex = re.compile(regex_pattern) # should include a group
    try:
        result = regex.search(text)
        if result:
            return result.group(1)
        else:
            return None
    except IndexError:
        return None

def parse_basic(text, title):
    df.loc[title, 'kWp'] = search(r'(\d+) kWp', text)
    df.loc[title, 'location'] = search(
        r'installed on [^,]+,(?: located in )?([^\n]+)\.?\n', text
        )
    df.loc[title, 'water_body_type'] = search(r'installed on ([^,\.]+),', text)
    
def parse_system(text, title):
    df.loc[title, 'panel_number'] = search(r'(\d+) panels', text)
    df.loc[title, 'panel_type'] = search(r'\(([^\)]+(?:modules|panels))', text)
    df.loc[title, 'covers_pct'] = search(r'covers (?:about )?([^%]+) ?%', text)
    regex = re.compile(r'\((\S+) out of (\S+) ha\).')
    results = regex.search(text)
    if results:
        try:
            covers_panels = results.group(1)
        except IndexError:
            covers_panels = None
        try:
            covers_total = results.group(2)
        except IndexError:
            covers_total = None
    else:
        covers_panels = covers_total = None
    
    df.loc[title, 'covers_panels'] = covers_panels
    df.loc[title, 'covers_total'] = covers_total
    
def parse_advanced(text, title):
    df.loc[title, 'max_depth'] = search(r'a maximum depth of (\S+) m', text)
    df.loc[title, 'level_variation'] = search(r'variation of (\S+) m', text)
    
def parse_date(text, title):
    interconnect_str = search(r'effective in ((?:\w+ ){0,1}\d+)', text)
    try:
        interconnect_date = datetime.strptime(interconnect_str, '%B %Y')
    except ValueError:
        interconnect_date = datetime.strptime(interconnect_str, '%Y')
    construction_duration = search(
        r'construction lasted (\d+ (days|weeks?|months))', text
        )
    df.loc[title, 'interconnection_date'] = interconnect_date
    df.loc[title, 'construction_duration'] = construction_duration
    
def parse_page(page, title):
    ps = []
    for p in page.xpath('//div[contains(@class, "content-article")]//p/text()'):
        if p:
            ps.append(p.replace(u'\xa0', ' ').strip())
    text  = '\n'.join(ps)
    if text:
        parse_basic(text, title)
        parse_system(text, title)
        parse_advanced(text, title)
        parse_date(text, title)
    
def download_page(li, title):
    page = get_page(li)
    with open(title, 'w') as target_file:
        target_file.write(
            html.etree.tostring(
                page.cssselect('div.content-article')[0]
                ).decode().strip()
            )
    last_downloaded.loc[title, 'last_download'] = now.date()
    last_downloaded.to_csv('last_downloaded.csv')
    
def get_projects():
    if 'main' in last_downloaded.index:
        main = html.parse('ciel_et_terre_projects/main.html').getroot()
    else:
        main = fetch('our-floating-solar-power-plants-references/')
        with open('ciel_et_terre_projects/main.html', 'w') as f:
            f.write(html.tostring(main).decode())
        last_downloaded.loc['main', 'last_downloaded'] = now.date()
    floating_solar_lis = main.cssselect('li.filter-floating-solar-system')
    for li in tqdm(floating_solar_lis):
        name, kwp = get_name_kwp(li)
        title = '{}-{}'.format(name, kwp)
        file_path = 'ciel_et_terre_projects/{}.html'.format(title)
        if not os.path.exists(file_path):
            if title in last_downloaded.index:
                recency = datetime.strptime(
                    last_downloaded.loc[title, 'last_downloaded'], '%Y-%m'
                    )
                if now - recency > timedelta(days=30):
                    download_page(li, file_path)
                else:
                    pass
            else:
                download_page(li, file_path)
        with open(file_path) as f:
            page = html.fromstring(f.read())
        parse_page(page, title)

def lookup(title):
    with open('ciel_et_terre_projects/{}.html'.format(title)) as f:
        page = html.fromstring(f.read())
    for p in page.xpath('//div[contains(@class, "content-article")]//p/text()'):
        print(p+ '\n')
    
    #%%
if __name__ == '__main__':
    now = datetime.now()
    df = pd.DataFrame(columns=[
        'kWp', 'location', 'water_body_type',
        'panel_number', 'panel_type', 'covers_pct', 'covers_panels',
        'covers_total', 'max_depth', 'level_variation', 'interconnection_date',
        'construction_duration'
        ])
    if os.path.exists('last_downloaded.csv'):
        last_downloaded = pd.read_csv('last_downloaded.csv', index_col=0)
    else:
        last_downloaded = pd.DataFrame(columns=['last_downloaded'])
    get_projects()
    make_decimal = lambda s: float(s.replace(',', '.')) if s else None
    for col in [
        'covers_pct', 'covers_panels', 'covers_total', 'max_depth',
       'level_variation'
       ]:
           df[col] = df[col].apply(make_decimal)
    df['kWp'] = df['kWp'].apply(lambda s: int(s))
    df['panel_number'] = df['panel_number'].apply(lambda s: int(s))
    def to_days(s):
        if s:
            m = re.match('(?P<num>\d+) (?P<name>[^s]+)s?', s)
            delta = timedelta(**{m.group('name') + 's' : int(m.group('num'))})
            return delta.days
        else:
            return None
    df['construction_duration'] = df['construction_duration'].apply(to_days)
    #df['level_variation'] = df['level_variation'].apply(make_decimal)

    df.to_csv('floating_solar_dataset.csv')
    last_downloaded.to_csv('last_downloaded.csv')
