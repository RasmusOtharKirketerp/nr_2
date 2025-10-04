# Copilot Instructions for newsreader

This guide enables AI coding agents to work productively in the `newsreader` codebase. It summarizes architecture, workflows, and conventions unique to this project.

## Architecture Overview
- **Core package:** All main logic lives in `src/newsreader/` (Flask app, background daemon, database, NLP, config).
- **Data flow:** News articles are fetched, geo-tagged via NLP, and exposed via a Flask web UI. Daemon and web UI can run together or separately.
- **Runtime state:** All persistent data (SQLite DB, logs, geo places, sources) is stored in `var/` and `data/`.
- **Config:** Environment-specific configs go in `config/` and are mounted in Docker.
- **Scripts:** Operational helpers in `scripts/` (e.g., geo data generation, tag listing).
- **Tests:** All tests in `tests/` use pytest/unittest. Some integration tests require network access.
- **Docker:** Containerization assets in `docker/` support local and remote deployment. Compose file mounts persistent state.

## Developer Workflows
- **Local setup:**
  - Use Python ≥3.10 (3.11+ recommended for Windows).
  - Create venv, install requirements, download spaCy/NLTK models:
    ```pwsh
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    python -m spacy download da_core_news_lg
    python -m spacy download en_core_web_sm
    python -m nltk.downloader punkt stopwords
    ```
- **Run app locally:**
  - Set `PYTHONPATH` to `src`.
  - Start Flask UI: `python -m newsreader.main --web`
  - Start daemon: `python -m newsreader.main --daemon`
- **Scripts:** Run helpers with same module path, e.g. `python scripts\list_geo_tags.py`.
- **Testing:** Run `pytest`. Some tests require network; set `PYTEST_CURRENT_TEST` to skip network-dependent paths.
- **Deployment:** Use PowerShell scripts in `scripts/` for AWS EC2 deployment. See `deploy-config.example.json` for config template.
- **Docker:**
  - Build: `docker build -t newsreader -f docker/Dockerfile .`
  - Run: `docker run --rm -p 8000:8000 ... newsreader`
  - Compose: `docker compose -f docker/docker-compose.yml up --build`

## Project-Specific Conventions
- **Runtime directories:** Only `var/`, `data/`, and `config/` are writable/mounted in containers.
- **Environment variables:** See `src/newsreader/settings.py` for all runtime env vars. Update `FLASK_SECRET_KEY` in Compose for production.
- **Module path:** Always set `PYTHONPATH` to `src` for local runs/scripts.
- **Database:** SQLite DB is at `var/newsreader.db` by default.
- **Geo places:** Regenerate with `python scripts/generate_geo_places.py`.

## Integration Points
- **NLP:** Uses spaCy and NLTK; models must be downloaded in setup.
- **AWS EC2:** Deployment scripts automate Docker image build, SCP upload, and container start.
  - Container logs: `./scripts/manage.ps1 -Action logs -Lines 200`
  - Inspect SQLite tables fast (container lacks the `sqlite3` CLI):
    ```pwsh
    ssh -i data/aws_ec2_rex.pem -o StrictHostKeyChecking=no ubuntu@<ip> `
      'docker exec newsreader-stack python -c "import sqlite3, json;\nconn = sqlite3.connect(\'/var/newsreader/newsreader.db\');\nprint(json.dumps([tuple(r) for r in conn.execute(\'SELECT id, url, thumbnail_url FROM articles ORDER BY id DESC LIMIT 5\')], ensure_ascii=False))"'
    ```
  - Swap the SQL inside the command above to run other queries (e.g. `PRAGMA table_info(articles)` to inspect columns).
- **Flask UI:** Templates in `src/newsreader/templates/`.

## Debugging & Communication Playbook
- **Collect context first:** Confirm the active branch, recent commands, and log tail before editing. Reference `./scripts/manage.ps1 -Action logs -Lines 200` when diagnosing production issues.
- **Run targeted remote probes:** Reuse the SSH + `docker exec` pattern to run single-line Python checks inside the container. Examples:
  - Validate Newspaper3k parsing: `python -c "from newspaper import Article; ..."`
  - Compare with raw HTTP: `python -c "import requests; print(requests.get(url, timeout=10).status_code)"`
- **Inspect SQLite data programmatically:** Prefer the Python snippet in the section above to dump result tuples, then swap in queries such as `SELECT COUNT(*) FROM articles WHERE thumbnail_url IS NOT NULL`.
- **Share findings clearly:** When reporting back, summarize the question, the commands executed, and key log or query snippets. Highlight differences between local and EC2 runs and call out assumptions (e.g., when a CDN blocks cloud IPs).
- **Iterate with small steps:** After each probe or change, capture the delta (e.g., “logs now include fetch failures” or “DB rows still NULL”) so the user can follow the debugging trail quickly.

## Examples
- To run the Flask UI locally:
  ```pwsh
  $env:PYTHONPATH = "$(Get-Location)\src"
  python -m newsreader.main --web
  ```
- To deploy to AWS EC2:
  ```pwsh
  .\scripts\deploy.ps1 -InstanceIP "<ip>" -KeyPath "<key.pem>"
  ```

## References
- See `README.md` for full setup and deployment details.
- See `src/newsreader/settings.py` for all runtime configuration options.
- See `docker/docker-compose.yml` for container orchestration.

---