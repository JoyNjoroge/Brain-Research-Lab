"""
scrape_alphas.py
~~~~~~~~~~~~~~~~
Scrapes all IS-passing, unsubmitted alphas from your WQ Brain account
and writes them to a CSV for manual review on BRAIN.

Usage:
    python scrape_alphas.py
"""
from main import WQSession
import time
import logging
import csv
import pandas as pd
from concurrent.futures import as_completed, ThreadPoolExecutor
from threading import current_thread

OFFSET, LIMIT = 0, 30


def get_link(offset):
    return (
        f'https://api.worldquantbrain.com/users/self/alphas'
        f'?limit={LIMIT}&offset={offset}'
        f'&stage=IS%1fOS'
        f'&is.sharpe%3E=1.25'
        f'&is.turnover%3E=0.01'
        f'&is.fitness%3E=1'
        f'&status=UNSUBMITTED'
        f'&order=-dateCreated'
        f'&hidden=false'
    )


wq = WQSession()


def scrape(result):
    thread = current_thread().name
    alpha    = result['regular']['code']
    settings = result['settings']
    aid      = result['id']

    passed = sum(check['result'] == 'PASS'             for check in result['is']['checks'])
    failed = sum(check['result'] in ('FAIL', 'ERROR')  for check in result['is']['checks'])
    if failed != 0:
        return -1

    # Wait for full check result
    while True:
        check_r = wq.get(f'https://api.worldquantbrain.com/alphas/{aid}/check')
        if check_r.content:
            try:
                checks = check_r.json()['is']['checks']
                break
            except Exception:
                pass
        time.sleep(2.5)

    if not all(check['result'] == 'PASS' for check in checks):
        return -1

    score = {'before': -1, 'after': -1}
    score['max_corr'] = next(
        check['value'] for check in checks if check['name'] == 'SELF_CORRELATION'
    )
    score |= settings

    def clean(code):
        lines = code.split('\n')
        cleaned = []
        for line in lines:
            if '#' in line:
                line = line[:line.find('#')].strip()
            line = line.strip()
            if line:
                cleaned.append(line)
        return ''.join(cleaned)

    score['passed'] = passed
    score['alpha']  = clean(alpha)
    score['link']   = f'https://platform.worldquantbrain.com/alpha/{aid}'
    logging.info(f'{thread} -- Success! -- {score}')
    return score


# ── Setup logging & CSV ────────────────────────────────────────────
ret      = []
SCRAPE_FN = f'data/alpha_scrape_result_{int(time.time())}.csv'

for handler in logging.root.handlers:
    logging.root.removeHandler(handler)
logging.basicConfig(
    encoding='utf-8',
    level=logging.INFO,
    format='%(asctime)s: %(message)s',
    filename=SCRAPE_FN.replace('csv', 'log'),
)

FIELDNAMES = (
    'before,after,max_corr,instrumentType,region,universe,delay,decay,'
    'neutralization,truncation,pasteurization,unitHandling,nanHandling,'
    'language,visualization,passed,alpha,link'
).split(',')

with open(SCRAPE_FN, 'w', newline='') as c:
    writer = csv.DictWriter(c, fieldnames=FIELDNAMES, extrasaction='ignore')
    writer.writeheader()
    c.flush()

    with ThreadPoolExecutor(max_workers=10) as executor:
        offset = 0
        try:
            while True:
                r = wq.get(get_link(offset)).json()
                logging.info(f'Fetched alphas #{offset+1}–#{offset+LIMIT}')
                futures = [executor.submit(scrape, res) for res in r['results']]
                for f in as_completed(futures):
                    res = f.result()
                    if res != -1:
                        ret.append(res)
                        writer.writerow(res)
                        c.flush()
                offset += LIMIT
                if not r.get('next'):
                    break
        except Exception as e:
            logging.info(f'{type(e).__name__}: {e}')
            try:
                logging.info(r.content)
            except Exception:
                pass

if ret:
    (
        pd.DataFrame(ret)
          .sort_values(by=['after', 'max_corr'], ascending=[False, True])
          .to_csv(SCRAPE_FN, index=False)
    )
    print(f'Done! Review results locally: {SCRAPE_FN}')
else:
    print('No qualifying alphas found this run.')
