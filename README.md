# Establishment Master Search (Web App)

A Flask web application for browsing and searching the EPFO Establishment
Master download (`establishment_master.csv`).

## Features

- Free-text search across ID, name, address, city/district/PIN, PAN/CIN, LIN
- Dropdown filters (status, district, industry group, DSC, eSign, Form 5A, etc.)
- Sortable, paginated results table
- Click any row to view the full establishment record
- Export current results to CSV or Excel

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000

## Deploy to Railway

1. Push this repo to GitHub.
2. On [railway.app](https://railway.app), create a **New Project > Deploy from GitHub repo** and select this repository.
3. Railway auto-detects the `Procfile` and deploys with gunicorn.
4. Under the service **Settings > Networking**, click **Generate Domain** to get a public URL.

## Updating the data

Replace `establishment_master.csv` with a fresh export, commit and push —
Railway redeploys automatically.