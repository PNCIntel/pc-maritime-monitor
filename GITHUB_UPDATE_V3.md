# GitHub Update — v3.0 Excel Build

For the current test deployment, upload/replace **the whole repository** with this package.

Keep Streamlit main file: `app.py`

Required runtime files:
- `app.py`
- `requirements.txt`
- `.streamlit/config.toml`
- entire `data/` folder

Optional second Streamlit app:
- `pc_intelligence_app.py`

Future-only files:
- `supabase_seed_v3/`

Do not split the Excel data folder between the two applications. Both applications should read the same canonical files.
