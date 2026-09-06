# P&C Maritime Security Monitor — Starter Package

This package contains a simple Streamlit dashboard and a combined ReCAAP incident dataset for 2024–2026.

## Repository structure

```
pc-maritime-monitor/
├── app.py
├── requirements.txt
└── data/
    └── incidents.csv
```

## Step 1 — Create a GitHub repository

1. Sign in at https://github.com.
2. Click the **+** at the upper-right and choose **New repository**.
3. Name it `pc-maritime-monitor`.
4. For this first test, choose **Public**.
5. Leave the optional README / .gitignore / license boxes unchecked.
6. Click **Create repository**.

## Step 2 — Upload the files

1. Open the new repository.
2. Click **Add file** → **Upload files**.
3. Upload `app.py` and `requirements.txt`.
4. Upload the `data` folder containing `incidents.csv` (or create a folder called `data` and upload the CSV into it).
5. Confirm the structure matches the diagram above.
6. Click **Commit changes**.

## Step 3 — Deploy it in Streamlit

1. Return to Streamlit Community Cloud.
2. Click **Deploy a public app from GitHub**.
3. Connect/authorize your GitHub account when prompted.
4. Choose `YOUR-GITHUB-USERNAME/pc-maritime-monitor`.
5. Branch: `main`.
6. Main file path: `app.py`.
7. Click **Deploy**.

Streamlit will install the packages in `requirements.txt`, load the CSV and start the app.

## Step 4 — Updating it later

Edit `app.py` or replace `data/incidents.csv` in GitHub, then commit the change. Streamlit normally notices the commit and refreshes/rebuilds the app automatically.

## Important note

This first version uses a static data file created from the ReCAAP annual incident PDFs. It does not automatically scrape the ReCAAP website. That makes the first deployment much easier to troubleshoot. An automated update pipeline can be added later.

## Common problems

**FileNotFoundError: data/incidents.csv** — the CSV is not inside the `data` folder or the folder name is different.

**ModuleNotFoundError** — make sure `requirements.txt` is beside `app.py` at the repository root.

**The app did not update** — confirm the latest change was committed to the `main` branch, then reboot the app from Streamlit if needed.
