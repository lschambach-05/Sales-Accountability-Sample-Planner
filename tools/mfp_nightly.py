"""Nightly MFP export (Lynwood, October 2026): logs in to My Fundraising Place, downloads every fundraiser in the
planner's window, builds the same CSV as the weekly Chrome pull, works out each rep's numbers with
build_rep_progress.py, loads them onto Rep Baselines with Import-RepProgress.ps1, saves the day's CSVs to SharePoint,
and emails Lynwood if any step fails. See docs/06-nightly-mfp-export.md for setup.

Usage (Windows, from the repository folder):
  py tools/mfp_nightly.py init                 create the settings file (outside the repository)
  py tools/mfp_nightly.py set-password         store the MFP password in Windows Credential Manager
  py tools/mfp_nightly.py probe                log in, read one page of each MFP request, check the settings
  py tools/mfp_nightly.py test-sharepoint      certificate sign-in, current season, test email
  py tools/mfp_nightly.py run [--season "2027 Spring"] [--no-sharepoint] [--accept-changes]
  py tools/mfp_nightly.py check-offline PULL.csv --season "2027 Spring" --asof 2026-10-14 [--expect REP_PROGRESS.csv]
  py tools/mfp_nightly.py compare OLD_PULL.csv NEW_PULL.csv

MFP has no public API. The requests below are the ones MFP's own pages make (written down by the Chrome session in
"MFP technical notes.txt"); their paths, parameters and field names live in the settings file, so a change at MFP
is a settings change. Anything that doesn't look as expected stops the run with an error, and the email says what.

Read-only in MFP: the program only sends GET requests, plus POST to the login form and to the two list (grid)
requests if MFP's pages use POST for them. Any other request is refused in code (MfpClient._send).

No sales data goes to GitHub: the settings, password, caches, logs and CSVs all live in the data folder
(%LOCALAPPDATA%\\RiteBite\\MFP Nightly by default) and in SharePoint.
"""
import argparse, collections, csv, datetime as dt, json, os, re, shutil, subprocess, sys, time, traceback
from pathlib import Path
from zoneinfo import ZoneInfo

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import mfp_rules                                          # noqa: E402
from build_rep_progress import progress, write_csv       # noqa: E402

CENTRAL = ZoneInfo('America/Chicago')
COLUMNS = ['Owning User', 'Group ID', 'Group Owner', 'Group Name', 'Program', 'Event Name', 'Status',
           'Fundraiser State', 'Start Date', 'Delivery Date', 'Season', 'Units', 'Invoice $', 'Invoices',
           'Fundraiser ID', 'Flags']
FILL = 'FILL IN'
KEEP_DAYS = 60                                            # local logs and CSVs older than this are deleted


class Stop(Exception):
    """A problem that should stop the run and be emailed, with a message a person can act on."""


# ---------------------------------------------------------------------------------------------- settings

def data_dir_default():
    return Path(os.environ.get('LOCALAPPDATA') or Path.home() / '.local' / 'share') / 'RiteBite' / 'MFP Nightly'


def config_path(arg):
    return Path(arg or os.environ.get('MFP_NIGHTLY_CONFIG') or data_dir_default() / 'config.json')


def load_config(path):
    if not path.exists():
        raise Stop(f'No settings file at {path}. Run "py tools/mfp_nightly.py init" first.')
    cfg = json.loads(path.read_text(encoding='utf-8'))
    cfg['_path'] = path
    cfg['_data'] = Path(cfg.get('data_dir') or path.parent)
    return cfg


def unfilled(obj, prefix=''):
    """Settings still marked FILL IN (the example file marks everything that comes from the technical notes)."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not k.startswith('_'):
                out += unfilled(v, f'{prefix}{k}.')
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += unfilled(v, f'{prefix}{i}.')
    elif isinstance(obj, str) and FILL in obj:
        out.append(prefix.rstrip('.'))
    return out


def require_filled(cfg, *sections):
    missing = [m for s in sections for m in unfilled(cfg.get(s, {}), s + '.')]
    if missing:
        raise Stop('These settings are still "FILL IN" in ' + str(cfg['_path']) + ':\n  ' + '\n  '.join(missing))


# ---------------------------------------------------------------------------------------------- values

def pick(obj, path):
    """obj['A']['B'] for path 'A.B'. Raises KeyError naming the path when a key is missing (null values are fine)."""
    cur = obj
    for part in path.split('.'):
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError(path)
        cur = cur[part]
        if cur is None:
            return None
    return cur


def text(v):
    return '' if v is None else str(v).strip()


def number(v, what):
    if v is None or v == '':
        return 0.0
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    try:
        return float(str(v).replace(',', '').replace('$', '').strip())
    except ValueError:
        raise Stop(f'{what}: expected a number, MFP sent {v!r}.')


def plain(n):
    """368.0 -> '368' (Units are whole numbers in the Chrome pulls); 3680.5 stays '3680.5'."""
    return str(int(n)) if float(n).is_integer() else str(n)


_MS_DATE = re.compile(r'^/Date\((-?\d+)([+-]\d{4})?\)/$')
_US_DATE = re.compile(r'^(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([AaPp][Mm])?)?$')


def central_date(v, naive_tz, what):
    """An MFP date/time -> the calendar date in Central time (the Chrome pulls' rule). A date with no time is kept
    as is. A time with no offset is read in naive_tz (the settings' "dates_without_offset_are")."""
    s = text(v)
    if not s:
        return None
    m = _MS_DATE.match(s)                                 # ASP.NET JSON date: /Date(1757912400000)/
    if m:
        return dt.datetime.fromtimestamp(int(m.group(1)) / 1000, dt.timezone.utc).astimezone(CENTRAL).date()
    m = _US_DATE.match(s)
    if m:
        mo, d, y, hh, mi, ss, ampm = m.groups()
        if hh is None:
            return dt.date(int(y), int(mo), int(d))
        h = int(hh) % 12 + (12 if ampm and ampm.lower() == 'pm' else 0) if ampm else int(hh)
        stamp = dt.datetime(int(y), int(mo), int(d), h, int(mi), int(ss or 0))
    else:
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', s):
            return dt.date.fromisoformat(s)
        try:
            stamp = dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
        except ValueError:
            raise Stop(f'{what}: MFP sent a date in a form this program does not know: {s!r}.')
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=dt.timezone.utc if naive_tz.upper() == 'UTC' else ZoneInfo(naive_tz))
    return stamp.astimezone(CENTRAL).date()


def season_of(day):
    return f"{'Spring' if day.month <= 6 else 'Fall'} {day.year}"


def season_bounds(mfp_season):
    half, year = mfp_season.split(); year = int(year)
    return (dt.date(year, 1, 1), dt.date(year, 6, 30)) if half == 'Spring' else (dt.date(year, 7, 1), dt.date(year, 12, 31))


def window_for(planner_season):
    """'2027 Spring' -> (2025-07-01, 2027-06-30): start of the season three seasons back to the end of this one."""
    year, half = planner_season.split()
    season = f'{half} {year}'
    first = mfp_rules.seasons_before(season, 3)[-1]
    return season_bounds(first)[0], season_bounds(season)[1]


_EVENT_SEASON = re.compile(r'\b(Spring|Fall)\s*(\d{4})\b', re.I)
_PROGRAM_FIXES = {'braided pastry 2022 with pastry ring': 'Braided Pastry'}


def program_name(raw):
    """OLD/NEW labels and the ' - DO NOT USE' suffix dropped, as in the Chrome pulls (docs/05)."""
    p = re.sub(r'\s*-\s*DO NOT USE\s*$', '', text(raw), flags=re.I)
    p = re.sub(r'^(OLD|NEW)\s+', '', p, flags=re.I).strip()
    return _PROGRAM_FIXES.get(p.lower(), p)


# ---------------------------------------------------------------------------------------------- MFP

class MfpClient:
    """Signed-in session with MFP. Only GET, plus POST to the login form and the grid paths in the settings."""

    def __init__(self, cfg, password, log):
        import requests                                    # only needed on the machine that talks to MFP
        self.requests = requests
        self.m = cfg['mfp']
        self.base = self.m['base_url'].rstrip('/')
        self.username = cfg['mfp_username']
        self.password = password
        self.log = log
        self.delay = float(self.m.get('request_delay_seconds', 0.25))
        self.timeout = float(self.m.get('timeout_seconds', 60))
        self.allowed_posts = {self.m['login']['post_path']} | {g['path'] for g in self.m['grids'].values()}
        self.session = None
        self.count = 0

    def _send(self, method, path, **kw):
        if method not in ('GET', 'POST') or (method == 'POST' and path not in self.allowed_posts):
            raise Stop(f'Refused {method} {path}: this program only reads from MFP.')
        url = self.base + path
        for attempt in range(1, 4):
            try:
                time.sleep(self.delay)
                r = self.session.request(method, url, timeout=self.timeout, **kw)
                self.count += 1
                if r.status_code >= 500:
                    raise self.requests.HTTPError(f'HTTP {r.status_code}')
                return r
            except (self.requests.ConnectionError, self.requests.Timeout, self.requests.HTTPError) as e:
                if attempt == 3:
                    raise Stop(f'MFP did not answer {method} {path} after 3 tries ({e}).')
                self.log(f'   {method} {path}: {e}; trying again')
                time.sleep(10 * attempt)

    def login(self):
        lg = self.m['login']
        self.session = self.requests.Session()
        self.session.headers['User-Agent'] = 'RiteBite-MFP-Nightly/1.0 (read-only)'
        page = self._send('GET', lg['page_path'])
        form = dict(lg.get('extra_fields') or {})
        if lg.get('token_field'):
            m = re.search(r'name="%s"[^>]*value="([^"]*)"' % re.escape(lg['token_field']), page.text) or \
                re.search(r'value="([^"]*)"[^>]*name="%s"' % re.escape(lg['token_field']), page.text)
            if not m:
                raise Stop(f'The MFP login page no longer has the "{lg["token_field"]}" field. MFP may have changed '
                           f'its login page; check the login settings against the technical notes.')
            form[lg['token_field']] = m.group(1)
        form[lg['username_field']] = self.username
        form[lg['password_field']] = self.password
        r = self._send('POST', lg['post_path'], data=form, allow_redirects=True)
        back_on_login = bool(lg.get('failed_if_url_contains')) and lg['failed_if_url_contains'] in r.url
        if r.status_code >= 400 or back_on_login or \
                re.search(r'name="%s"' % re.escape(lg['password_field']), r.text):
            raise Stop('MFP login failed (the login form came back). Check the username in the settings and the '
                       'password in Credential Manager ("py tools/mfp_nightly.py set-password").')
        self.log(f'   Logged in to MFP as {self.username}')

    def _json(self, method, path, what, **kw):
        for attempt in (1, 2):
            r = self._send(method, path, **kw)
            try:
                if r.status_code < 400:
                    return r.json()
            except ValueError:
                pass
            if attempt == 1:                               # session may have expired during a long run
                self.log(f'   {what}: MFP sent HTTP {r.status_code} / not data; logging in again')
                self.login()
        raise Stop(f'{what}: MFP sent HTTP {r.status_code} and a web page instead of data, even after logging in '
                   f'again. MFP may have changed this request ({method} {path}).')

    def grid_page(self, name, page, date_from, date_to):
        g = self.m['grids'][name]
        size = int(g.get('page_size', 50))
        values = {'page': page, 'page_index': page - 1, 'page_size': size, 'skip': (page - 1) * size,
                  'date_from': date_from.strftime(g['date_format']), 'date_to': date_to.strftime(g['date_format'])}
        params = fill_template(g.get('params') or {}, values)
        if not isinstance(params, dict):
            raise Stop(f'mfp.grids.{name}.params must be an object of request parameters.')
        kw = {'query': {'params': params}, 'form': {'data': params}, 'json': {'json': params}}.get(g['send_as'])
        if kw is None:
            raise Stop(f'mfp.grids.{name}.send_as must be "query", "form" or "json".')
        body = self._json(g['method'].upper(), g['path'], f'{name} list page {page}', **kw)
        try:
            rows, total = pick(body, g['rows_key']), pick(body, g['total_key'])
        except (KeyError, TypeError):
            keys = ', '.join(body) if isinstance(body, dict) else type(body).__name__
            raise Stop(f'{name} list: the answer has no "{g["rows_key"]}"/"{g["total_key"]}" (it has: {keys}). '
                       f'MFP may have changed this request.')
        if not isinstance(rows, list) or not isinstance(total, int):
            raise Stop(f'{name} list: expected a list of rows and a whole-number total, got {type(rows).__name__} '
                       f'and {total!r}.')
        return rows, total, size

    def grid_all(self, name, date_from, date_to):
        out, page = [], 1
        while True:
            rows, total, size = self.grid_page(name, page, date_from, date_to)
            out += rows
            if not rows or len(out) >= total:
                break
            if len(rows) != size:
                raise Stop(f'{name} list page {page}: {len(rows)} rows instead of {size} before the end.')
            page += 1
            if page > 2000:
                raise Stop(f'{name} list: more than 2000 pages; stopping.')
        if len(out) != total:
            raise Stop(f'{name} list: MFP said {total} rows but sent {len(out)}.')
        self.log(f'   {name}: {total} rows in {page} pages')
        return out

    def record(self, kind, rid):
        return self._json('GET', self.m[kind]['path'].format(id=rid), f'{kind} {rid}')


def fill_template(obj, values):
    """Replace {page}, {skip}, {date_from}... in the request settings. A value that is only a placeholder keeps
    its type (a number stays a number in a JSON body)."""
    if isinstance(obj, dict):
        return {k: fill_template(v, values) for k, v in obj.items()}
    if isinstance(obj, list):
        return [fill_template(v, values) for v in obj]
    if isinstance(obj, str):
        m = re.fullmatch(r'\{(\w+)\}', obj)
        if m and m.group(1) in values:
            return values[m.group(1)]
        return re.sub(r'\{(\w+)\}', lambda mm: str(values.get(mm.group(1), mm.group(0))), obj)
    return obj


def fields_of(rows, fields, what):
    """[{logical name: value}] for each row; stops when a field in the settings is missing from MFP's rows."""
    out = []
    for i, row in enumerate(rows):
        rec = {}
        for name, path in fields.items():
            if not path:
                rec[name] = None
                continue
            try:
                rec[name] = pick(row, path)
            except KeyError:
                keys = ', '.join(sorted(row)) if isinstance(row, dict) else type(row).__name__
                raise Stop(f'{what} row {i + 1} has no "{path}" (settings field "{name}"). Fields MFP sent: {keys}. '
                           f'MFP may have renamed it; update the settings.')
        out.append(rec)
    return out


# ---------------------------------------------------------------------------------------------- building the pull

def build_rows(fundraisers, invoices, records, owners, naive_tz):
    """The Chrome pull's CSV rows (docs/05, weekly prompt) from MFP's data, already mapped to logical names:
    fundraisers  [{id, owning_user, program, event_name, status, state, start_date, units}]
    invoices     [{fundraiser_id, group_id, group_name, owning_user, delivered_on, is_primary, amount, units}]
    records      {fundraiser id: {group_id, group_name, delivered_on}} for fundraisers with no dated invoice
    owners       {group id: owning user code or ''}
    Returns (rows, notes) where notes are counts for the log."""
    by_f = collections.defaultdict(list)
    for inv in invoices:
        fid = text(inv['fundraiser_id'])
        if fid:                                           # invoices with no fundraiser are left out (docs/05)
            by_f[fid].append(inv)
    rows, notes = [], collections.Counter()
    for f in fundraisers:
        fid = text(f['id'])
        invs = by_f.get(fid, [])
        flags = []
        dated = [(central_date(i['delivered_on'], naive_tz, f'Invoice for fundraiser {fid}'), i) for i in invs]
        dated = [(d, i) for d, i in dated if d]
        primary = [p for p in dated if p[1].get('is_primary') is True]
        if invs:
            first = (primary or sorted(dated, key=lambda p: p[0]) or [(None, invs[0])])[0]
            group_id, group_name = text(first[1]['group_id']), text(first[1]['group_name'])
            if len({text(i['group_id']) for i in invs}) > 1:
                flags.append('Invoices name more than one group: ' + ' / '.join(sorted({text(i['group_id']) for i in invs})))
        else:
            group_id = group_name = ''
        delivery = first[0] if dated else None
        if not dated:
            rec = records.get(fid)
            if rec is None:
                raise Stop(f'Fundraiser {fid} has no dated invoice and its record was not read.')
            group_id = group_id or text(rec['group_id'])
            group_name = group_name or text(rec['group_name'])
            delivery = central_date(rec['delivered_on'], naive_tz, f'Fundraiser {fid} DeliveredOn')
        start = central_date(f['start_date'], naive_tz, f'Fundraiser {fid} start date')
        event = text(f['event_name'])
        program = program_name(f['program'])
        owner = text(f['owning_user'])
        units = number(f['units'], f'Fundraiser {fid} units')

        if delivery:
            season = season_of(delivery)
        elif start:
            season = season_of(start)
        else:
            season = ''
        m = _EVENT_SEASON.search(event)
        if m and delivery:
            named = f'{m.group(1).capitalize()} {m.group(2)}'
            if named != season:
                flags.append(f'Event-name season ({named}) ≠ delivery season ({season})')
        days = sorted({d for d, _ in dated})
        if len(days) > 1:
            flags.append('Multiple invoice delivery dates: ' + ' / '.join(d.isoformat() for d in days))
        other = sorted({text(i['owning_user']) for i in invs if text(i['owning_user']) and text(i['owning_user']) != owner})
        if other:
            flags.append('Invoice owner differs: ' + ', '.join(other))
        if invs and all(i.get('units') is not None for i in invs):
            inv_units = sum(number(i['units'], f'Invoice units for fundraiser {fid}') for i in invs)
            if abs(inv_units - units) > 0.001:
                flags.append(f'Units ({plain(units)}) ≠ invoice units ({plain(inv_units)})')
        if not delivery:
            flags.append('No delivery date – season from start date' if start else 'No delivery or start date')
        if not program:
            flags.append('Blank program in MFP')
        group_owner = owners.get(group_id, '') if group_id else ''
        if group_id and not group_owner:
            flags.append('Group has no owning user in MFP')
        for fl in flags:
            notes[fl.split(':')[0].split('(')[0].strip()] += 1

        rows.append({'Owning User': owner, 'Group ID': group_id, 'Group Owner': group_owner, 'Group Name': group_name,
                     'Program': program, 'Event Name': event, 'Status': text(f['status']),
                     'Fundraiser State': text(f['state']), 'Start Date': start.isoformat() if start else '',
                     'Delivery Date': delivery.isoformat() if delivery else '', 'Season': season,
                     'Units': plain(units), 'Invoice $': str(sum(number(i['amount'], f'Invoice $ for fundraiser {fid}') for i in invs)),
                     'Invoices': str(len(invs)), 'Fundraiser ID': fid, 'Flags': '; '.join(flags)})
    return rows, notes


def check_rows(rows):
    """Stops when the pull can't be right, before anything is written to SharePoint."""
    if not rows:
        raise Stop('MFP returned no fundraisers at all.')
    ids = [r['Fundraiser ID'] for r in rows]
    if '' in ids:
        raise Stop('Some fundraisers have no ID.')
    dupes = [k for k, n in collections.Counter(ids).items() if n > 1]
    if dupes:
        raise Stop(f'Fundraisers listed more than once: {", ".join(dupes[:10])}.')
    no_group = [r['Fundraiser ID'] for r in rows if not r['Group ID']]
    if no_group:
        raise Stop(f'{len(no_group)} fundraisers have no Group ID (e.g. {", ".join(no_group[:10])}).')
    users = {r['Owning User'] for r in rows}
    if not users & set(mfp_rules.CURRENT) and not users & set(mfp_rules.ROLLUP):
        raise Stop('None of the owning users is a rep code from mfp_rules.py (e.g. ' + ', '.join(sorted(users)[:5]) +
                   '). Check the "owning_user" field in the settings: it must be the MFP code (BPR, KJS, ...).')
    if any(r['Status'] not in ('Open', 'Closed', 'Canceled') for r in rows):
        odd = sorted({r['Status'] for r in rows} - {'Open', 'Closed', 'Canceled'})
        raise Stop(f'Unexpected fundraiser statuses {odd}; the rules only know Open, Closed and Canceled.')


def write_pull(rows, path):
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS); w.writeheader(); w.writerows(rows)


def season_summary(rows):
    out = collections.defaultdict(lambda: {'fundraisers': 0, 'units': 0.0})
    for r in rows:
        out[r['Season']]['fundraisers'] += 1
        out[r['Season']]['units'] += float(r['Units'] or 0)
    return dict(sorted(out.items()))


def compare_with_last(state, summary, total, today, accept):
    """Past seasons shouldn't move much, and the list shouldn't shrink: stops (until --accept-changes) if they do."""
    if accept or not state:
        return []
    problems = []
    last_total = state.get('fundraisers', 0)
    if last_total and total < last_total * 0.9:
        problems.append(f'{total} fundraisers tonight vs {last_total} last time (more than 10% fewer).')
    for season, last in state.get('seasons', {}).items():
        if not season or season_bounds(season)[1] > today - dt.timedelta(days=60):
            continue                                     # still active or recent: changes are normal
        now = summary.get(season, {'units': 0.0})['units']
        if last['units'] and abs(now - last['units']) > max(0.02 * last['units'], 50):
            problems.append(f'{season} units went from {last["units"]:,.0f} to {now:,.0f}; a past season should not move.')
    if problems:
        raise Stop('Tonight\'s pull doesn\'t look like the last one:\n  ' + '\n  '.join(problems) +
                   '\nIf that is right (for example, a big correction in MFP), run once with --accept-changes.')
    return []


# ---------------------------------------------------------------------------------------------- SharePoint (via PowerShell)

def pwsh(cfg, script, args, log):
    exe = cfg.get('pwsh') or 'pwsh'
    cmd = [exe, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(TOOLS / script)] + args
    p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    for line in (p.stdout + p.stderr).splitlines():
        if line.strip():
            log('   | ' + line.rstrip())
    if p.returncode != 0:
        raise Stop(f'{script} failed (exit {p.returncode}). The PowerShell output is in the log above.')
    results = [l[len('RESULT: '):] for l in p.stdout.splitlines() if l.startswith('RESULT: ')]
    return json.loads(results[-1]) if results else None


def sp_args(cfg, site):
    sp = cfg['sharepoint']
    return ['-SiteUrl', site, '-ClientId', sp['client_id'], '-Tenant', sp['tenant'], '-Thumbprint', sp['thumbprint']]


def sp_current_season(cfg, log):
    res = pwsh(cfg, 'mfp_nightly_sharepoint.ps1', ['-Action', 'Season'] + sp_args(cfg, cfg['sharepoint']['planner_site']), log)
    if not res or not res.get('season'):
        raise Stop('No row is ticked Current Season in the Seasons list (or more than one is).')
    return res


def sp_upload(cfg, paths, log):
    sp = cfg['sharepoint']
    pwsh(cfg, 'mfp_nightly_sharepoint.ps1', ['-Action', 'Upload', '-Folder', sp['records_folder'], '-Paths'] +
         [str(p) for p in paths] + sp_args(cfg, sp['records_site']), log)


def sp_import(cfg, progress_csv, log):
    pwsh(cfg, 'Import-RepProgress.ps1', ['-CsvPath', str(progress_csv)] + sp_args(cfg, cfg['sharepoint']['planner_site']), log)


def sp_mail(cfg, subject, body, log):
    sp = cfg['sharepoint']
    body_file = cfg['_data'] / 'logs' / 'last-email.txt'
    body_file.write_text(body, encoding='utf-8')
    pwsh(cfg, 'mfp_nightly_sharepoint.ps1', ['-Action', 'Mail', '-From', sp['alert_from'], '-To', sp['alert_to'],
                                            '-Subject', subject, '-BodyPath', str(body_file)] +
         sp_args(cfg, sp['planner_site']), log)


# ---------------------------------------------------------------------------------------------- password

def get_password(cfg):
    import keyring
    pw = keyring.get_password(cfg['keyring_service'], cfg['mfp_username'])
    if not pw:
        raise Stop(f'No MFP password in Windows Credential Manager for "{cfg["mfp_username"]}" '
                   f'(service "{cfg["keyring_service"]}"). Run "py tools/mfp_nightly.py set-password".')
    return pw


# ---------------------------------------------------------------------------------------------- the nightly run

class Log:
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.f = open(path, 'a', encoding='utf-8')

    def __call__(self, msg):
        line = f'{dt.datetime.now():%H:%M:%S} {msg}'
        print(line, flush=True)
        self.f.write(line + '\n'); self.f.flush()

    def tail(self, n=60):
        return '\n'.join(self.path.read_text(encoding='utf-8').splitlines()[-n:])


def read_json(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def write_json(path, obj):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj, indent=1, sort_keys=True), encoding='utf-8')
    tmp.replace(path)


def pull_from_mfp(cfg, client, planner_season, today, log):
    m = cfg['mfp']
    cache_dir = cfg['_data'] / 'cache'; cache_dir.mkdir(parents=True, exist_ok=True)
    date_from, date_to = window_for(planner_season)
    pad = dt.timedelta(days=int(m.get('invoice_window_pad_days', 183)))
    log(f'2. Reading MFP: deliveries {date_from} to {date_to} (invoices {date_from - pad} to {date_to + pad})')
    client.login()
    fundraisers = fields_of(client.grid_all('fundraisers', date_from, date_to), m['grids']['fundraisers']['fields'], 'Fundraisers list')
    invoices = fields_of(client.grid_all('invoices', date_from - pad, date_to + pad), m['grids']['invoices']['fields'], 'Invoices list')
    fids = {text(f['id']) for f in fundraisers}
    invoices = [i for i in invoices if text(i['fundraiser_id']) in fids]

    # Fundraiser records, for fundraisers with no dated invoice (mostly upcoming bookings). Closed and canceled
    # ones don't change, so their records are cached; open ones are read every night.
    rec_cache_path = cache_dir / 'fundraiser_records.json'
    rec_cache = read_json(rec_cache_path, {})
    naive = m.get('dates_without_offset_are', 'UTC')
    has_date = {text(i['fundraiser_id']) for i in invoices if text(i['delivered_on'])}
    records, read = {}, 0
    for f in fundraisers:
        fid = text(f['id'])
        if fid in has_date:
            continue
        status = text(f['status'])
        if status in ('Closed', 'Canceled') and fid in rec_cache:
            records[fid] = rec_cache[fid]; continue
        rec = fields_of([client.record('fundraiser_record', fid)], m['fundraiser_record']['fields'], f'Fundraiser {fid} record')[0]
        records[fid] = rec_cache[fid] = {k: rec[k] for k in ('group_id', 'group_name', 'delivered_on')}
        read += 1
    write_json(rec_cache_path, rec_cache)
    log(f'   Fundraiser records: {read} read, {len(records) - read} from cache')

    # Group owners: new groups every night, plus the oldest checks, so every owner is re-read about once a week.
    own_path = cache_dir / 'group_owners.json'
    owners = read_json(own_path, {})
    groups = {text(i['group_id']) for i in invoices} | {text(r['group_id']) for r in records.values()}
    groups.discard('')
    new = sorted(g for g in groups if g not in owners)
    per_night = int(m.get('owner_refresh_per_night', max(150, len(groups) // 7 + 1)))
    stale = sorted((g for g in groups if g in owners), key=lambda g: owners[g]['checked'])[:per_night]
    for g in new + stale:
        rec = fields_of([client.record('group_record', g)], m['group_record']['fields'], f'Group {g} record')[0]
        owners[g] = {'owner': text(rec['owner']), 'checked': today.isoformat()}
    write_json(own_path, owners)
    log(f'   Group owners: {len(new)} new groups, {len(stale)} rechecked, {len(groups)} groups in all '
        f'({client.count} MFP requests)')

    rows, notes = build_rows(fundraisers, invoices, records, {g: owners[g]['owner'] for g in groups}, naive)
    check_rows(rows)
    odd = sorted({r['Program'] for r in rows if r['Program'] and r['Program'] not in mfp_rules.PROGRAMS})
    if odd:
        log('   Programs not in mfp_rules.PROGRAMS (for Lynwood to review): ' + ', '.join(odd))
    log('   Flags: ' + (', '.join(f'{k} {n}' for k, n in notes.most_common()) or 'none'))
    return rows


def cmd_run(cfg, args):
    today = getattr(args, 'today', None) or dt.datetime.now(CENTRAL).date()
    data = cfg['_data']
    log = Log(data / 'logs' / f'mfp_nightly {today}.log')
    log(f'MFP nightly export, {today}')
    step = 'starting'
    errors, warnings = [], []
    try:
        require_filled(cfg, 'mfp')
        if not args.no_sharepoint:
            require_filled(cfg, 'sharepoint')
        step = '1. Current season'
        if args.season:
            season = args.season
            log(f'1. Season (from the command line): {season}')
        else:
            res = sp_current_season(cfg, log)
            season = res['season']
            log(f'1. Current season (Seasons list): {season}')
            days = res.get('certDaysLeft')
            if days is not None and days < 30:
                warnings.append(f'The SharePoint certificate expires in {days} days. Renew it (docs/06, Certificate).')
        step = '2. MFP export'
        rows = pull_from_mfp(cfg, MfpClient(cfg, get_password(cfg), log), season, today, log)
        summary = season_summary(rows)
        for s, v in summary.items():
            log(f'   {s or "(no date)"}: {v["fundraisers"]} fundraisers, {v["units"]:,.0f} units')
        state_path = data / 'state.json'
        compare_with_last(read_json(state_path, {}), summary, len(rows), today, args.accept_changes)

        step = '3. Rep numbers'
        exports = data / 'exports'; exports.mkdir(parents=True, exist_ok=True)
        pull_csv = exports / f'MFP progress {today}.csv'
        write_pull(rows, pull_csv)
        try:
            out, lines = progress(season, today, mfp_rules.load(str(pull_csv)))
        except ValueError as e:
            raise Stop(str(e))
        progress_csv = exports / f'Rep Progress {season} {today}.csv'
        write_csv(out, progress_csv)
        log('3. ' + '\n   '.join(lines))

        if args.no_sharepoint:
            log(f'Stopped before SharePoint (--no-sharepoint). Files: {pull_csv}, {progress_csv}')
        else:
            step = '4. Save CSVs to SharePoint'
            try:
                sp_upload(cfg, [pull_csv, progress_csv], log)
                log(f'4. Saved both CSVs to {cfg["sharepoint"]["records_folder"]}')
            except Stop as e:                              # keep going: the numbers matter more than the record
                errors.append(f'{step}: {e}')
            step = '5. Rep Baselines'
            sp_import(cfg, progress_csv, log)
            log('5. Rep Baselines updated')
        write_json(state_path, {'date': today.isoformat(), 'fundraisers': len(rows), 'seasons': summary})
    except Stop as e:
        errors.append(f'{step}: {e}')
    except Exception:
        errors.append(f'{step}: unexpected error\n{traceback.format_exc()}')
    finally:
        cleanup(data)
    try:
        return finish(cfg, args, log, today, errors, warnings)
    finally:
        log.f.close()


def finish(cfg, args, log, today, errors, warnings):
    for e in errors:
        log('PROBLEM: ' + e)
    for w in warnings:
        log('WARNING: ' + w)
    if not errors:
        log('Done.')
    if (errors or warnings) and not args.no_sharepoint and not unfilled(cfg.get('sharepoint', {})):
        if errors:
            subject = f'MFP nightly export problem ({today})'
            intro = (f'The nightly MFP export on {today} ran into a problem, so the planner\'s MFP numbers may not '
                     f'have been updated tonight.\n\n' + '\n\n'.join(errors + warnings))
        else:
            subject = f'MFP nightly export warning ({today})'
            intro = f'The nightly MFP export on {today} worked, with a warning:\n\n' + '\n\n'.join(warnings)
        body = (intro + f'\n\nComputer: {os.environ.get("COMPUTERNAME", "?")}\nFull log: {log.path}\n\n'
                f'Last lines of the log:\n' + log.tail())
        try:
            sp_mail(cfg, subject, body, log)
            log('Emailed ' + cfg['sharepoint']['alert_to'])
        except Stop as e:
            log(f'Could not send the email either: {e}')
    return 1 if errors else 0


def cleanup(data):
    cutoff = time.time() - KEEP_DAYS * 86400
    for sub in ('exports', 'logs'):
        for p in (data / sub).glob('*'):
            if p.is_file() and p.stat().st_mtime < cutoff:
                p.unlink()


# ---------------------------------------------------------------------------------------------- setup and test commands

def cmd_init(path):
    if path.exists():
        print(f'{path} already exists; not overwriting it.'); return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(TOOLS / 'mfp_nightly.example.json', path)
    print(f'Created {path}\nOpen it in Notepad and fill in every "FILL IN" (docs/06 explains each one).')
    return 0


def cmd_set_password(cfg):
    import getpass, keyring
    if FILL in cfg.get('mfp_username', FILL):
        raise Stop(f'Fill in "mfp_username" in {cfg["_path"]} first.')
    pw = getpass.getpass(f'MFP password for {cfg["mfp_username"]} (nothing shows as you type): ')
    if not pw:
        print('Nothing entered; not changed.'); return 1
    keyring.set_password(cfg['keyring_service'], cfg['mfp_username'], pw)
    print(f'Saved in Windows Credential Manager (service "{cfg["keyring_service"]}").')
    return 0


def flat_keys(obj, prefix=''):
    if isinstance(obj, dict):
        out = []
        for k, v in obj.items():
            out += flat_keys(v, f'{prefix}{k}.') if isinstance(v, dict) else [f'{prefix}{k} = {str(v)[:60]!r}']
        return out
    return [f'{prefix.rstrip(".")} = {str(obj)[:60]!r}']


def cmd_probe(cfg):
    """One page of each list and one record of each kind, with every field MFP sent, to fill in and check the
    settings. Prints MFP data on this screen only; nothing is saved."""
    m = cfg['mfp']
    require_filled(cfg, 'mfp')
    client = MfpClient(cfg, get_password(cfg), print)
    client.login()
    date_from, date_to = window_for(cfg.get('probe_season', '2027 Spring'))
    ok = True
    first = {}
    for name in ('fundraisers', 'invoices'):
        rows, total, size = client.grid_page(name, 1, date_from, date_to)
        print(f'\n== {name}: total {total}, {len(rows)} rows on page 1 (page size {size}). Fields of the first row:')
        print('   ' + '\n   '.join(flat_keys(rows[0]) if rows else ['(no rows)']))
        try:
            first[name] = fields_of(rows[:1], m['grids'][name]['fields'], f'{name} list')[0] if rows else {}
            print(f'   OK: every field in the settings for {name} is there.')
        except Stop as e:
            ok = False; print('   PROBLEM: ' + str(e))
    for kind, rid in (('fundraiser_record', text(first.get('invoices', {}).get('fundraiser_id'))),
                      ('group_record', text(first.get('invoices', {}).get('group_id')))):
        if not rid:
            continue
        rec = client.record(kind, rid)
        print(f'\n== {kind} {rid}. Fields:')
        print('   ' + '\n   '.join(flat_keys(rec)))
        try:
            fields_of([rec], m[kind]['fields'], kind); print(f'   OK: every field in the settings for {kind} is there.')
        except Stop as e:
            ok = False; print('   PROBLEM: ' + str(e))
    print(f'\n{client.count} MFP requests. ' + ('Settings look right.' if ok else 'Fix the settings above and run probe again.'))
    return 0 if ok else 1


def cmd_test_sharepoint(cfg):
    require_filled(cfg, 'sharepoint')
    res = sp_current_season(cfg, print)
    print(f'Current season: {res["season"]}; certificate expires in {res.get("certDaysLeft")} days.')
    folder = cfg['_data'] / 'logs'; folder.mkdir(parents=True, exist_ok=True)
    test = folder / 'SharePoint test.txt'
    test.write_text(f'Test from the MFP nightly export setup, {dt.datetime.now():%Y-%m-%d %H:%M}.\n', encoding='utf-8')
    sp_upload(cfg, [test], print)
    print(f'Saved "{test.name}" to {cfg["sharepoint"]["records_folder"]} (delete it there when you\'ve seen it).')
    sp_mail(cfg, 'MFP nightly export: test email', 'This is a test from the MFP nightly export setup. '
            'If you got it, failure emails will reach you.', print)
    print(f'Test email sent to {cfg["sharepoint"]["alert_to"]}.')
    return 0


def cmd_check_offline(args):
    """The calculation on a saved pull, compared with an earlier run's Rep Progress CSV (the October 14 check)."""
    rows = mfp_rules.load(args.pull)
    out, lines = progress(args.season, dt.date.fromisoformat(args.asof), rows)
    print('\n'.join(lines))
    print('\nSeason totals in the pull:')
    for s, v in season_summary(rows).items():
        print(f'   {s or "(no date)":12} {v["fundraisers"]:>5} fundraisers {v["units"]:>10,.0f} units')
    if not args.expect:
        return 0
    want = {r['Rep Code']: r for r in csv.DictReader(open(args.expect, newline='', encoding='utf-8-sig'))}
    got = {r['Rep Code']: r for r in out}
    cols = ['MFP Units to Date', 'MFP New Groups', 'MFP New Groups 12 Mo']
    diffs = [f'{rep} {c}: expected {want.get(rep, {}).get(c)}, got {got.get(rep, {}).get(c)}'
             for rep in sorted(set(want) | set(got)) for c in cols
             if str(want.get(rep, {}).get(c)) != str(got.get(rep, {}).get(c))]
    print('\nMatches ' + args.expect if not diffs else '\nDIFFERENT from ' + args.expect + ':\n   ' + '\n   '.join(diffs))
    return 0 if not diffs else 1


def cmd_compare(args):
    """Row-by-row differences between two pulls (e.g. the Chrome pull and the program's export of the same day)."""
    def rows(p):
        return {r['Fundraiser ID']: r for r in csv.DictReader(open(p, newline='', encoding='utf-8-sig'))}
    a, b = rows(args.old), rows(args.new)
    print(f'{len(a)} fundraisers in {args.old}, {len(b)} in {args.new}')
    only_a, only_b = sorted(set(a) - set(b)), sorted(set(b) - set(a))
    print(f'Only in the first: {len(only_a)} {only_a[:15]}')
    print(f'Only in the second: {len(only_b)} {only_b[:15]}')
    by_col = collections.defaultdict(list)
    for fid in sorted(set(a) & set(b)):
        for c in COLUMNS:
            if c == 'Flags':
                continue
            x, y = a[fid].get(c, ''), b[fid].get(c, '')
            if c in ('Units', 'Invoice $') and x and y:
                same = abs(float(x) - float(y)) < 0.005
            else:
                same = x == y
            if not same:
                by_col[c].append(f'{fid}: {x!r} -> {y!r}')
    for c in COLUMNS:
        if by_col[c]:
            print(f'{c}: {len(by_col[c])} differ, e.g. ' + '; '.join(by_col[c][:5]))
    if not any(by_col.values()) and not only_a and not only_b:
        print('No differences (apart from Flags wording).')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--config', help='settings file (default: %%LOCALAPPDATA%%\\RiteBite\\MFP Nightly\\config.json)')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('init'); sub.add_parser('set-password'); sub.add_parser('probe'); sub.add_parser('test-sharepoint')
    r = sub.add_parser('run')
    r.add_argument('--season', help='planner season, e.g. "2027 Spring" (default: the Current Season row)')
    r.add_argument('--no-sharepoint', action='store_true', help='stop after writing the CSVs locally')
    r.add_argument('--accept-changes', action='store_true', help='run even if past seasons moved since last time')
    c = sub.add_parser('check-offline')
    c.add_argument('pull'); c.add_argument('--season', required=True); c.add_argument('--asof', required=True)
    c.add_argument('--expect')
    k = sub.add_parser('compare'); k.add_argument('old'); k.add_argument('new')
    args = ap.parse_args(argv)
    try:
        if args.cmd == 'check-offline':
            return cmd_check_offline(args)
        if args.cmd == 'compare':
            return cmd_compare(args)
        path = config_path(args.config)
        if args.cmd == 'init':
            return cmd_init(path)
        cfg = load_config(path)
        return {'set-password': lambda: cmd_set_password(cfg), 'probe': lambda: cmd_probe(cfg),
                'test-sharepoint': lambda: cmd_test_sharepoint(cfg), 'run': lambda: cmd_run(cfg, args)}[args.cmd]()
    except Stop as e:
        print(f'PROBLEM: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
