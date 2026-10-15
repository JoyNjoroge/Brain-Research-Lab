"""Generate reproducible alpha research batches for WorldQuant BRAIN."""
import random

random.seed()

BASE = dict(region='USA', delay=1, truncation=0.08, decay=4,
            pasteurization='ON', nanHandling='OFF')


def _mk(code, **over):
    d = dict(BASE); d.update(over); d['code'] = code
    return d


# ── Family 1: options skew  (research template) ───────────────────────
# Put/call IV ratio is a fear gauge. Fading its short-term mean, within sector.
def family_options_skew(n=4):
    tenors  = ['10', '20', '30', '60']
    windows = [5, 10, 20]
    groups  = ['sector', 'industry', 'subindustry']
    out = []
    for _ in range(n):
        t, w, g = random.choice(tenors), random.choice(windows), random.choice(groups)
        ratio = f'implied_volatility_put_{t} / implied_volatility_call_{t}'
        template = random.choice([
            f'group_neutralize(rank(-ts_mean({ratio}, {w})), {g})',
            f'group_rank(-ts_zscore({ratio}, {w}), {g})',
            f'group_neutralize(rank(-ts_delta({ratio}, {w})), {g})',
        ])
        out.append(_mk(template, universe=random.choice(['TOP200', 'TOP500', 'TOP1000']),
                       neutralization='SECTOR', nanHandling='ON'))
    return out


# ── Family 2: fundamental yield, time-ranked then group-ranked (research template) ─
def family_fundamental_yield(n=6):
    numerators = ['cashflow_op', 'cashflow', 'ebit', 'ebitda', 'operating_income',
                  'sales', 'income', 'cashflow_fin', 'est_netprofit', 'est_eps*sharesout']
    denoms     = ['cap', 'assets', 'enterprise_value', 'close*sharesout']
    windows    = [20, 60, 120, 252]
    groups     = ['subindustry', 'industry', 'sector']
    out = []
    for _ in range(n):
        num, den, w, g = (random.choice(numerators), random.choice(denoms),
                          random.choice(windows), random.choice(groups))
        code = f'alpha = ts_rank({num}/{den},{w}); group_rank(alpha, {g})'
        out.append(_mk(code, universe=random.choice(['TOP3000', 'TOP2000']),
                       neutralization=g.upper()))
    return out


# ── Family 3: news-gated reversal + size tilt (research template) ─────
def family_news_gated(n=4):
    news_fields = ['nws12_afterhsz_sl', 'nws12_prez_sl', 'nws12_afterhsz_prez',
                   'nws12_prez_mkt', 'nws12_afterhsz_mkt']
    out = []
    for _ in range(n):
        f   = random.choice(news_fields)
        nw  = random.choice([10, 25, 60])
        rw  = random.choice([5, 10, 20])
        thr = random.choice([0.3, 0.4, 0.5])
        wr  = random.choice([0.6, 0.7, 0.8])
        code = (f'rank(ts_sum(vec_avg({f}), {nw})) > {thr} ? 1 : '
                f'{wr} * rank(-ts_delta(close, {rw})) + {round(1-wr,1)} * rank(ts_mean(cap, 1800))')
        out.append(_mk(code, universe='TOP3000', neutralization='SUBINDUSTRY', truncation=0.15))
    return out


# ── Family 4: weighted multi-factor fundamentals (research template) ───
def family_multifactor(n=6):
    quality  = ['ebit/capex', 'operating_income/assets', 'cashflow_op/liabilities',
                'ebitda/enterprise_value', 'income/equity']
    estimate = ['est_eps/close', 'est_netprofit/close', 'est_sales/cap',
                'est_ebit/cap', 'est_cashflow_op/cap']
    leverage = ['liabilities/assets', 'debt/assets', 'debt_lt/equity', '1']
    out = []
    for _ in range(n):
        q, lv = random.choice(quality), random.choice(leverage)
        e1, e2 = random.sample(estimate, 2)
        w1, w2 = random.choice([1, 2, 3]), random.choice([4, 6, 8])
        lw = random.choice([252, 504])
        code = (f'{w1}*ts_rank(-rank({q})/operating_income,{lw}) + '
                f'{w2}*rank((ts_rank({e1},252)+ts_rank({e2},252))/2)*{lv}')
        out.append(_mk(code, universe='TOP3000', neutralization='SUBINDUSTRY'))
    return out


def build(seed=None):
    if seed is not None:
        random.seed(seed)
    data = (family_options_skew() + family_fundamental_yield()
            + family_news_gated() + family_multifactor())
    random.shuffle(data)
    return data


# ──────────────────────────────────────────────────────────────────
DATA = build()

if __name__ == '__main__':
    print(f'{len(DATA)} alphas queued:\n')
    for i, a in enumerate(DATA, 1):
        print(f'{i:>2}. [{a["universe"]:<7} {a["neutralization"]:<11} d{a["decay"]}] {a["code"]}')
