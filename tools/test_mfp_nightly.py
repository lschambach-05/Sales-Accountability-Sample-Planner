"""Tests for mfp_nightly.py with a fake MFP. All names and numbers here are made up.

Run: python tools/test_mfp_nightly.py  (needs the requests package)
"""
import csv, datetime as dt, json, sys, tempfile, types, unittest
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mfp_nightly as mn


def fake_config(tmp):
    cfg = json.loads((Path(mn.TOOLS) / 'mfp_nightly.example.json').read_text(encoding='utf-8'))
    cfg['mfp_username'] = 'nightly@example.com'
    m = cfg['mfp']
    m['request_delay_seconds'] = 0
    m['login'].update(page_path='/Account/Login', post_path='/Account/Login', username_field='Email',
                      password_field='Password', token_field='__RequestVerificationToken',
                      failed_if_url_contains='/Account/Login')
    for name, g in m['grids'].items():
        g.update(method='POST', send_as='form', date_format='%m/%d/%Y', rows_key='Data', total_key='Total', page_size=2,
                 params={'page': '{page}', 'pageSize': '{page_size}', 'filter': 'DeliveredOn~gte~{date_from}~and~DeliveredOn~lte~{date_to}'})
    m['grids']['fundraisers']['fields'] = {'id': 'Id', 'owning_user': 'Owner.Code', 'program': 'Program', 'event_name': 'Name',
                                           'status': 'Status', 'state': 'State', 'start_date': 'StartDate', 'units': 'TotalItems'}
    m['grids']['invoices']['fields'].update(group_name='GroupName', owning_user='OwnerCode', amount='Amount')
    m['fundraiser_record']['fields'].update(group_id='Group.Id', group_name='Group.Name')
    m['group_record']['fields']['owner'] = 'OwningUser.Code'
    for k in ('client_id', 'thumbprint'):
        cfg['sharepoint'][k] = 'x'
    cfg['_path'] = Path(tmp) / 'config.json'
    cfg['_data'] = Path(tmp)
    return cfg


def F(fid, owner, status, start, units, program='NEW Combo', name=None, state='Paid'):
    return {'Id': fid, 'Owner': {'Code': owner}, 'Program': program, 'Name': name or f'Group {fid} - Fall 2025',
            'Status': status, 'State': state, 'StartDate': start, 'TotalItems': units}


def I(fid, gid, owner, delivered, amount, primary=False):
    return {'FundraiserId': fid, 'GroupId': gid, 'GroupName': f'Group {gid}', 'OwnerCode': owner,
            'DeliveredOn': delivered, 'IsPrimary': primary, 'Amount': amount}


# Fall 2025, Spring 2026 and Fall 2026 have history; Spring 2027 is the planner season (2027 Spring).
FUNDRAISERS = [
    F(1, 'KJS', 'Closed', '2025-09-01T00:00:00', 100),             # group 10, Fall 2025
    F(2, 'KJS', 'Closed', '2026-02-01T00:00:00', 50),              # group 10, Spring 2026
    F(3, 'BLS', 'Closed', '2026-09-01T00:00:00', 30),              # group 11, Fall 2026 (rolls up to KJS)
    F(4, 'BPR', 'Open', '2027-02-01T00:00:00', 0, name='Group 12 - Spring 2027', state='Booked'),  # new group 12, no invoice
    F(5, 'BPR', 'Canceled', '2027-03-01T00:00:00', 0, state='Canceled'),                         # canceled, no invoice
    F(6, 'JK', 'Closed', '2026-03-01T00:00:00', 20, program='OLD Wooden Spoon - DO NOT USE'),  # two invoice dates
]
INVOICES = [
    I(1, 10, 'KJS', '2025-09-20T04:00:00Z', 1000.0),
    I(2, 10, 'KJS', '/Date(1772172000000)/', 500.0),                # 2026-02-27 06:00 UTC
    I(3, 11, 'KJS', '2026-09-30T03:00:00Z', 300.0),                 # 2026-09-29 in Central time
    I(6, 13, 'JK', '2026-03-10T12:00:00Z', 150.0),
    I(6, 13, 'JK', '2026-03-17T12:00:00Z', 50.0),
    I(None, 99, 'GJS', '2026-03-17T12:00:00Z', 50.0),               # no fundraiser: left out
]
RECORDS = {4: {'Group': {'Id': 12, 'Name': 'Group 12'}, 'DeliveredOn': '2027-03-01T18:00:00Z'},
           5: {'Group': {'Id': 12, 'Name': 'Group 12'}, 'DeliveredOn': None}}
GROUPS = {10: 'KJS', 11: 'KJS', 12: 'BPR', 13: 'JK'}


class FakeResponse:
    def __init__(self, url, body=None, html=None, status=200):
        self.url, self.status_code, self._body = url, status, body
        self.text = html if html is not None else json.dumps(body)

    def json(self):
        if self._body is None:
            raise ValueError('not json')
        return self._body


class FakeMfp:
    """Answers like MFP would, and records every request."""
    def __init__(self, fundraisers=FUNDRAISERS, invoices=INVOICES, password='secret'):
        self.fundraisers, self.invoices, self.password = fundraisers, invoices, password
        self.calls, self.logged_in = [], False
        self.headers = {}

    def request(self, method, url, timeout=None, data=None, params=None, json=None, allow_redirects=True):
        path = urlparse(url).path
        self.calls.append((method, path, data))
        if path == '/Account/Login' and method == 'GET':
            return FakeResponse(url, html='<form><input name="__RequestVerificationToken" type="hidden" value="tok123" />'
                                          '<input name="Password" /></form>')
        if path == '/Account/Login':
            assert data['__RequestVerificationToken'] == 'tok123'
            if data['Password'] != self.password:
                return FakeResponse(url, html='<input name="Password" />')
            self.logged_in = True
            return FakeResponse('https://app.myfundraisingplace.com/Home', html='<html>Welcome</html>')
        if not self.logged_in:
            return FakeResponse(url + '?ReturnUrl=x', html='<html>login</html>')
        if path.startswith('/grid/'):
            rows = self.fundraisers if path == '/grid/Fundraisers' else self.invoices
            page, size = int(data['page']), int(data['pageSize'])
            return FakeResponse(url, {'Data': rows[(page - 1) * size: page * size], 'Total': len(rows)})
        if path.startswith('/api/fundraisers/'):
            return FakeResponse(url, RECORDS[int(path.rsplit('/', 1)[1])])
        if path.startswith('/api/groups/'):
            return FakeResponse(url, {'Id': 1, 'OwningUser': {'Code': GROUPS[int(path.rsplit('/', 1)[1])]}})
        return FakeResponse(url, html='not found', status=404)


REAL_CLIENT = mn.MfpClient


def client_with(cfg, fake, password='secret'):
    c = REAL_CLIENT(cfg, password, lambda m: None)
    c.requests.Session = lambda: fake
    return c


class Values(unittest.TestCase):
    def test_central_date(self):
        self.assertEqual(mn.central_date('2026-09-30T03:00:00Z', 'UTC', 'x'), dt.date(2026, 9, 29))
        self.assertEqual(mn.central_date('2026-09-30T03:00:00', 'UTC', 'x'), dt.date(2026, 9, 29))
        self.assertEqual(mn.central_date('2026-09-30T03:00:00', 'America/Chicago', 'x'), dt.date(2026, 9, 30))
        self.assertEqual(mn.central_date('2026-07-01', 'UTC', 'x'), dt.date(2026, 7, 1))
        self.assertEqual(mn.central_date('7/1/2026', 'UTC', 'x'), dt.date(2026, 7, 1))
        self.assertEqual(mn.central_date('7/1/2026 2:00:00 AM', 'UTC', 'x'), dt.date(2026, 6, 30))
        self.assertEqual(mn.central_date('/Date(1772172000000)/', 'UTC', 'x'), dt.date(2026, 2, 27))
        self.assertIsNone(mn.central_date(None, 'UTC', 'x'))
        with self.assertRaises(mn.Stop):
            mn.central_date('next Tuesday', 'UTC', 'x')

    def test_program_and_window(self):
        self.assertEqual(mn.program_name('OLD Combo - DO NOT USE'), 'Combo')
        self.assertEqual(mn.program_name('NEW Wooden Spoon'), 'Wooden Spoon')
        self.assertEqual(mn.program_name('Braided Pastry 2022 With Pastry Ring'), 'Braided Pastry')
        self.assertEqual(mn.window_for('2027 Spring'), (dt.date(2025, 7, 1), dt.date(2027, 6, 30)))
        self.assertEqual(mn.window_for('2027 Fall'), (dt.date(2026, 1, 1), dt.date(2027, 12, 31)))

    def test_fill_template(self):
        t = {'page': '{page}', 'f': 'd~gte~{date_from}', 'n': [{'skip': '{skip}'}], 'keep': '{other}'}
        self.assertEqual(mn.fill_template(t, {'page': 3, 'skip': 100, 'date_from': '07/01/2025'}),
                         {'page': 3, 'f': 'd~gte~07/01/2025', 'n': [{'skip': 100}], 'keep': '{other}'})

    def test_unfilled_example(self):
        cfg = json.loads((Path(mn.TOOLS) / 'mfp_nightly.example.json').read_text(encoding='utf-8'))
        missing = mn.unfilled(cfg)
        self.assertIn('mfp.login.page_path', missing)
        self.assertIn('mfp.grids.fundraisers.params', missing)
        self.assertIn('sharepoint.thumbprint', missing)


class Mfp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = fake_config(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_paging_and_read_only(self):
        fake = FakeMfp()
        c = client_with(self.cfg, fake)
        c.login()
        rows = c.grid_all('fundraisers', dt.date(2025, 7, 1), dt.date(2027, 6, 30))
        self.assertEqual([r['Id'] for r in rows], [1, 2, 3, 4, 5, 6])
        self.assertEqual(fake.calls[2][2]['filter'], 'DeliveredOn~gte~07/01/2025~and~DeliveredOn~lte~06/30/2027')
        with self.assertRaises(mn.Stop):
            c._send('POST', '/api/fundraisers/1')
        with self.assertRaises(mn.Stop):
            c._send('DELETE', '/grid/Fundraisers')

    def test_bad_password(self):
        with self.assertRaisesRegex(mn.Stop, 'login failed'):
            client_with(self.cfg, FakeMfp(), password='wrong').login()

    def test_total_mismatch_and_renamed_field(self):
        fake = FakeMfp()
        c = client_with(self.cfg, fake)
        c.login()
        c.grid_page = lambda *a: (FUNDRAISERS[:1], 1, 2)
        rows = c.grid_all('fundraisers', dt.date(2025, 7, 1), dt.date(2027, 6, 30))
        renamed = [dict(rows[0], TotalItemz=1)]
        del renamed[0]['TotalItems']
        with self.assertRaisesRegex(mn.Stop, 'no "TotalItems"'):
            mn.fields_of(renamed, self.cfg['mfp']['grids']['fundraisers']['fields'], 'Fundraisers list')

    def test_full_pull(self):
        fake = FakeMfp()
        rows = mn.pull_from_mfp(self.cfg, client_with(self.cfg, fake), '2027 Spring', dt.date(2026, 10, 14), lambda m: None)
        by = {r['Fundraiser ID']: r for r in rows}
        self.assertEqual(by['1']['Delivery Date'], '2025-09-19')
        self.assertEqual(by['1']['Program'], 'Combo')
        self.assertEqual(by['1']['Units'], '100')
        self.assertEqual(by['1']['Invoice $'], '1000.0')
        self.assertEqual(by['2']['Season'], 'Spring 2026')
        self.assertIn('Event-name season (Fall 2025) ≠ delivery season (Spring 2026)', by['2']['Flags'])
        self.assertEqual(by['3']['Delivery Date'], '2026-09-29')
        self.assertIn('Invoice owner differs: KJS', by['3']['Flags'])
        self.assertEqual((by['4']['Group ID'], by['4']['Group Owner'], by['4']['Season']), ('12', 'BPR', 'Spring 2027'))
        self.assertEqual(by['4']['Invoices'], '0')
        self.assertEqual(by['5']['Season'], 'Spring 2027')
        self.assertIn('No delivery date – season from start date', by['5']['Flags'])
        self.assertEqual(by['6']['Delivery Date'], '2026-03-10')
        self.assertEqual(by['6']['Program'], 'Wooden Spoon')
        self.assertIn('Multiple invoice delivery dates: 2026-03-10 / 2026-03-17', by['6']['Flags'])
        self.assertEqual(by['6']['Invoice $'], '200.0')
        self.assertNotIn('None', by)                                    # invoice with no fundraiser left out
        self.assertTrue(all(m in ('GET', 'POST') for m, _, _ in fake.calls))
        self.assertTrue(all(p in ('/Account/Login', '/grid/Fundraisers', '/grid/Invoices') for m, p, _ in fake.calls if m == 'POST'))

        # Second night: owners and closed/canceled records come from the cache.
        fake2 = FakeMfp()
        self.cfg['mfp']['owner_refresh_per_night'] = 1
        mn.pull_from_mfp(self.cfg, client_with(self.cfg, fake2), '2027 Spring', dt.date(2026, 10, 15), lambda m: None)
        paths = [p for _, p, _ in fake2.calls]
        self.assertEqual(sum(p.startswith('/api/groups/') for p in paths), 1)
        self.assertEqual([p for p in paths if p.startswith('/api/fundraisers/')], ['/api/fundraisers/4'])

    def test_missing_group_stops(self):
        invoices = [dict(i) for i in INVOICES]
        invoices[0]['GroupId'] = None
        with self.assertRaisesRegex(mn.Stop, 'no Group ID'):
            mn.pull_from_mfp(self.cfg, client_with(self.cfg, FakeMfp(invoices=invoices)), '2027 Spring',
                             dt.date(2026, 10, 14), lambda m: None)

    def test_run_without_sharepoint(self):
        args = types.SimpleNamespace(season='2027 Spring', no_sharepoint=True, accept_changes=False, today=dt.date(2026, 10, 14))
        fake = FakeMfp()
        orig_client, orig_pw = mn.MfpClient, mn.get_password
        mn.MfpClient = lambda cfg, pw, log: client_with(cfg, fake)
        mn.get_password = lambda cfg: 'secret'
        try:
            self.assertEqual(mn.cmd_run(self.cfg, args), 0)
        finally:
            mn.MfpClient, mn.get_password = orig_client, orig_pw
        prog = next(Path(self.tmp.name, 'exports').glob('Rep Progress 2027 Spring *.csv'))
        got = {r['Rep Code']: r for r in csv.DictReader(open(prog, newline=''))}
        self.assertEqual(got['BPR']['MFP New Groups'], '1')                  # group 12 is new in Spring 2027
        self.assertEqual(got['KJS']['MFP New Groups 12 Mo'], '1')            # group 11, new in Fall 2026
        self.assertEqual(sorted(got), ['BPR', 'KJS'])

    def run_with_sharepoint(self, fake, cert_days=200):
        calls = []

        def fake_pwsh(cfg, script, args, log):
            calls.append((script, args[args.index('-Action') + 1] if '-Action' in args else 'Import'))
            return {'season': '2027 Spring', 'certDaysLeft': cert_days} if 'Season' in args else None
        args = types.SimpleNamespace(season=None, no_sharepoint=False, accept_changes=False, today=dt.date(2026, 10, 14))
        orig = mn.MfpClient, mn.get_password, mn.pwsh
        mn.MfpClient = lambda cfg, pw, log: client_with(cfg, fake)
        mn.get_password = lambda cfg: 'secret'
        mn.pwsh = fake_pwsh
        try:
            return mn.cmd_run(self.cfg, args), calls
        finally:
            mn.MfpClient, mn.get_password, mn.pwsh = orig

    def test_run_with_sharepoint(self):
        code, calls = self.run_with_sharepoint(FakeMfp())
        self.assertEqual(code, 0)
        self.assertEqual(calls, [('mfp_nightly_sharepoint.ps1', 'Season'), ('mfp_nightly_sharepoint.ps1', 'Upload'),
                                 ('Import-RepProgress.ps1', 'Import')])

    def test_failure_emails(self):
        code, calls = self.run_with_sharepoint(FakeMfp(password='changed'))
        self.assertEqual(code, 1)
        self.assertEqual(calls[-1], ('mfp_nightly_sharepoint.ps1', 'Mail'))
        self.assertNotIn(('Import-RepProgress.ps1', 'Import'), calls)
        self.assertIn('login failed', (Path(self.tmp.name) / 'logs' / 'last-email.txt').read_text(encoding='utf-8'))

    def test_certificate_warning(self):
        code, calls = self.run_with_sharepoint(FakeMfp(), cert_days=10)
        self.assertEqual(code, 0)
        self.assertEqual(calls[-1], ('mfp_nightly_sharepoint.ps1', 'Mail'))
        self.assertIn('warning', (Path(self.tmp.name) / 'logs' / 'last-email.txt').read_text(encoding='utf-8'))

    def test_compare_with_last(self):
        state = {'fundraisers': 100, 'seasons': {'Fall 2025': {'fundraisers': 50, 'units': 10000.0}}}
        today = dt.date(2026, 10, 14)
        mn.compare_with_last(state, {'Fall 2025': {'units': 10050.0}}, 100, today, False)
        with self.assertRaisesRegex(mn.Stop, 'Fall 2025 units'):
            mn.compare_with_last(state, {'Fall 2025': {'units': 9000.0}}, 100, today, False)
        with self.assertRaisesRegex(mn.Stop, 'more than 10% fewer'):
            mn.compare_with_last(state, {'Fall 2025': {'units': 10000.0}}, 80, today, False)
        mn.compare_with_last(state, {'Fall 2025': {'units': 9000.0}}, 80, today, True)


if __name__ == '__main__':
    unittest.main()
