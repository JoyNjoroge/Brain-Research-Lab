"""
main.py
~~~~~~~
Core WorldQuant Brain session + simulator.

Run:
    python main.py

Progress is printed to the console AND written to data/api_<ts>.log.
Results stream into data/api_<ts>.csv as each simulation finishes.
"""
import csv
import json
import logging
import sys
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import current_thread, Lock

from parameters import DATA

# Brain allows ~3 concurrent simulations per account. More just queues and errors.
MAX_WORKERS = 3

CSV_COLUMNS = [
    'passed', 'delay', 'region', 'neutralization', 'decay',
    'truncation', 'sharpe', 'fitness', 'turnover', 'weight',
    'subsharpe', 'correlation', 'universe', 'link', 'code',
]


def _setup_logging(filename=None):
    """Log to console always; to a file too when a filename is given."""
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    fmt = logging.Formatter('%(asctime)s: %(message)s')
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(console)
    if filename:
        fh = logging.FileHandler(filename, encoding='utf-8')
        fh.setFormatter(fmt)
        root.addHandler(fh)
    root.setLevel(logging.INFO)


class WQSession(requests.Session):
    def __init__(self, json_fn='credentials.json'):
        super().__init__()
        _setup_logging()
        self.json_fn = json_fn
        self.login_expired = False
        self.rows_processed = []
        self._lock = Lock()
        self.login()

    # ── Auth ──────────────────────────────────────────────────────
    def login(self):
        with open(self.json_fn) as f:
            creds = json.load(f)
        if creds['email'].startswith('your_'):
            sys.exit('Fill in credentials.json with your Brain email/password first.')
        self.auth = (creds['email'], creds['password'])

        r = self.post('https://api.worldquantbrain.com/authentication')
        body = r.json() if r.content else {}
        if 'user' not in body:
            if 'inquiry' in body:
                input(
                    f"Complete biometric auth at\n"
                    f"  {r.url}/persona?inquiry={body['inquiry']}\n"
                    f"then press Enter here... "
                )
                self.post(f"{r.url}/persona", json=body)
            else:
                sys.exit(f'Login failed: {body}')
        logging.info('Logged in to WQBrain!')

    def _get_retry(self, url, **kw):
        for _ in range(5):
            try:
                return self.get(url, **kw)
            except requests.RequestException as e:
                logging.info(f'GET retry ({e})')
                time.sleep(3)
        raise RuntimeError(f'GET failed repeatedly: {url}')

    # ── One simulation ────────────────────────────────────────────
    def _run_one(self, sim):
        thread = current_thread().name.split('_')[-1]
        alpha          = sim['code'].strip()
        delay          = sim.get('delay', 1)
        universe       = sim.get('universe', 'TOP3000')
        truncation     = sim.get('truncation', 0.08)
        region         = sim.get('region', 'USA')
        decay          = sim.get('decay', 4)
        neutralization = sim.get('neutralization', 'SUBINDUSTRY').upper()
        pasteurization = sim.get('pasteurization', 'ON')
        nan            = sim.get('nanHandling', 'OFF')

        logging.info(f'[w{thread}] Simulating: {alpha[:90]}')

        payload = {
            'type': 'REGULAR',
            'regular': alpha,
            'settings': {
                'instrumentType': 'EQUITY',
                'region': region,
                'universe': universe,
                'delay': delay,
                'decay': decay,
                'neutralization': neutralization,
                'truncation': truncation,
                'pasteurization': pasteurization,
                'unitHandling': 'VERIFY',
                'nanHandling': nan,
                'language': 'FASTEXPR',
                'visualization': False,
            },
        }

        # POST — retry while the account is at its concurrent-sim limit
        while True:
            r = self.post('https://api.worldquantbrain.com/simulations', json=payload)
            if 'Location' in r.headers:
                progress_url = r.headers['Location']
                break
            try:
                detail = r.json()
            except ValueError:
                detail = r.text
            text = str(detail)
            if 'credentials' in text.lower() or r.status_code == 401:
                self.login_expired = True
                logging.info(f'[w{thread}] Session expired — will re-login.')
                return None
            if 'SIMULATION_LIMIT' in text or r.status_code == 429:
                time.sleep(15)
                continue
            logging.info(f'[w{thread}] Rejected: {text[:200]}')
            return self._fail_row(sim, alpha, f'rejected: {text[:80]}')

        # Poll
        while True:
            r = self._get_retry(progress_url)
            if not r.content:
                time.sleep(5); continue
            body = r.json()
            if 'alpha' in body:
                alpha_id = body['alpha']
                break
            if 'progress' in body:
                logging.info(f'[w{thread}] {int(100 * body["progress"])}%')
                time.sleep(8)
                continue
            msg = body.get('message', body)
            logging.info(f'[w{thread}] Simulation failed: {msg}')
            return self._fail_row(sim, alpha, msg)

        # Fetch result
        a = self._get_retry(f'https://api.worldquantbrain.com/alphas/{alpha_id}').json()
        link = f'https://platform.worldquantbrain.com/alpha/{alpha_id}'
        passed, weight_check, subsharpe = 0, 'N/A', -1
        for check in a['is']['checks']:
            passed += check['result'] == 'PASS'
            if check['name'] == 'CONCENTRATED_WEIGHT':
                weight_check = check['result']
            if check['name'] == 'LOW_SUB_UNIVERSE_SHARPE':
                subsharpe = check.get('value', -1)

        is_ = a['is']
        logging.info(
            f'[w{thread}] DONE sharpe={is_["sharpe"]:.2f} fitness={is_["fitness"]:.2f} '
            f'turnover={100*is_["turnover"]:.1f}% checks={passed}  {link}'
        )
        return [
            passed, delay, region, neutralization, decay, truncation,
            is_['sharpe'], is_['fitness'], round(100 * is_['turnover'], 2),
            weight_check, subsharpe, -1, universe, link, alpha,
        ]

    @staticmethod
    def _fail_row(sim, alpha, reason):
        return [
            0, sim.get('delay', 1), sim.get('region', 'USA'),
            sim.get('neutralization', 'SUBINDUSTRY').upper(),
            sim.get('decay', 4), sim.get('truncation', 0.08),
            0, 0, 0, 'FAIL', 0, -1, sim.get('universe', 'TOP3000'),
            str(reason)[:120], alpha,
        ]

    # ── Batch ─────────────────────────────────────────────────────
    def simulate(self, data):
        self.rows_processed = []
        stamp = str(time.time()).replace('.', '_')
        csv_file = f'data/api_{stamp}.csv'
        _setup_logging(csv_file.replace('.csv', '.log'))
        logging.info(f'Writing results to {csv_file}  ({len(data)} alphas, {MAX_WORKERS} workers)')

        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(CSV_COLUMNS)
            f.flush()

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
                futures = {ex.submit(self._run_one, sim): sim for sim in data}
                for fut in as_completed(futures):
                    sim = futures[fut]
                    try:
                        row = fut.result()
                    except Exception as e:
                        logging.info(f'Worker crashed: {type(e).__name__}: {e}')
                        row = self._fail_row(sim, sim['code'], f'{type(e).__name__}: {e}')
                    if row is None:          # login expired, retry later
                        continue
                    with self._lock:
                        writer.writerow(row)
                        f.flush()
                        self.rows_processed.append(sim)
                    print(f'  -> {len(self.rows_processed)}/{len(data)} written', flush=True)

        return [s for s in data if s not in self.rows_processed]


if __name__ == '__main__':
    total = len(DATA)
    remaining = DATA
    print(f'{total} alphas queued. Watch the dashboard or data/api_*.log for live progress.')
    while remaining:
        wq = WQSession()
        remaining = wq.simulate(remaining)
        print(f'{total - len(remaining)}/{total} simulations complete.')
        if remaining:
            print(f'{len(remaining)} left — re-logging in...')
    print('All done. Load the newest data/api_*.csv in dashboard.html.')
