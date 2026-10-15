# WQ BRAIN Alpha Desk

An independent Python research tool for generating candidate alpha expressions, running **unsubmitted** simulations through the WorldQuant BRAIN API, and reviewing results in a live web dashboard. Successful candidates can be opened directly on the BRAIN platform for **manual review and submission**.

This public repository contains **no credentials, simulation history, logs, account alpha IDs, or personal research results**. The bundled video shows the original workflow; its on-screen results are historical demonstration footage, not bundled datasets.

## Demo

[Watch the recorded walkthrough](docs/demo-simulation.mp4)

> The video is a phone recording, so some details may be difficult to read. The actual application is the HTML dashboard (`dashboard.html`).

## Features

- Four configurable expression generator families in `parameters.py`
- Multi-worker simulation runner (`main.py`) with progress logging and per-run CSV output
- Locally served dashboard with run history, sortable results, performance chart, leaderboard and log viewer
- Direct **Open on BRAIN** links for simulated alphas
- Optional scrape of passing unsubmitted alphas for review (`scrape_alphas.py`)
- **No automatic submission** in the public project. Any submission is performed by the researcher on the BRAIN website.

## Setup

Requires Python 3.10+ and a WorldQuant BRAIN account. Use this tool only in accordance with BRAIN's access terms and API limits.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp credentials.example.json credentials.json
```

Edit the **untracked** `credentials.json` with your own account login. Do not commit it or any output under `data/`.

## Run

Use separate terminals:

```bash
python serve.py
# open http://127.0.0.1:8787
```

```bash
python parameters.py  # review the generated expressions
python main.py        # simulate and stream results to data/
```

Depending on your account authentication flow, BRAIN may require an interactive verification step. Generated expressions are research candidates and some may fail validation due to field availability or API constraints.

The dashboard can also open local CSV and log files. After simulation, use its **Open** link to inspect the corresponding alpha directly in WorldQuant BRAIN, then decide whether to submit it manually.

Optional account review:

```bash
python scrape_alphas.py
```

This writes account-specific results to the locally ignored `data/` directory. Do not publish those files.

## Project layout

| Path | Purpose |
| --- | --- |
| `parameters.py` | Generate batches of expressions |
| `main.py` | Authenticate and simulate candidate alphas |
| `commands.py`, `database.py` | Expression utilities and reference data |
| `serve.py` | Local dashboard HTTP server and run list |
| `dashboard.html` | Research dashboard and direct alpha links |
| `scrape_alphas.py` | Optional passing-alpha review |
| `credentials.example.json` | Safe credential placeholder |
| `data/` | Private local results, git-ignored |
| `docs/demo-simulation.mp4` | Recorded project demo |

## Privacy and limitations

The sample templates are illustrative, not verified trading signals. Reported historical simulation results are not evidence of future performance. Do not publish credentials, personal research output, generated logs, or account-specific alpha details. The local development server binds to `127.0.0.1` and is not designed for public hosting.

Built by **Joy Njoroge**. Not affiliated with or endorsed by WorldQuant.
