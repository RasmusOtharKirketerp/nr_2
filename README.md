# newsreader

An end-to-end news aggregation application featuring background fetching, NLP-driven geo tagging, and a Flask web UI. The repository now mirrors the runtime layout that previously lived in Docker so you can develop locally or run everything in containers without guesswork.

## Project layout

- `src/newsreader/` – core application package (Flask app, daemon, database, NLP pipelines, shared settings).
- `data/` – runtime data, including `sources.json` and a starter `geo_places.json` list.
- `var/` – writable directory for SQLite databases, PID files, and logs (safe to mount/ignore).
- `config/` – drop-in spot for environment-specific configuration files (mounted in Docker).
- `scripts/` – operational helpers (generate geo data, list tags, etc.).
- `tests/` – pytest/unittest suites for the refactored package layout.
- `docker/` – container assets (`Dockerfile`, `entrypoint.sh`, `docker-compose.yml`).
- `entrypoint.sh` – thin wrapper that forwards to `docker/entrypoint.sh` for backwards compatibility.

## Prerequisites

- Python ≥ 3.10 (3.11 recommended on Windows so spaCy wheels install without a compiler)
- Docker (optional, for container workflow)
- PowerShell 7+ (commands below assume the default Windows shell)

## Local setup (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m spacy download da_core_news_lg
python -m spacy download en_core_web_sm
python -m nltk.downloader punkt stopwords
```

### Bootstrap project data

`data/sources.json` ships with a minimal Danish news configuration. Update it with your own sources as needed. To regenerate a comprehensive geo-place list (recommended for production), run:

```powershell
python scripts\generate_geo_places.py
```

This will download the full dataset and overwrite `data\geo_places.json`.

### Running the app locally

```powershell
$env:PYTHONPATH = "$(Get-Location)\src"
python -m newsreader.main --web    # Flask UI on http://127.0.0.1:8000
# Or start the background daemon instead:
python -m newsreader.main --daemon
```

Utility scripts inherit the same module path, e.g. `python scripts\list_geo_tags.py`. SQLite databases and logs land in `var/`.

### Tests

```powershell
pytest
```

Some integration tests reach out to real HTTP endpoints; set `PYTEST_CURRENT_TEST` if you want to bypass certain network-dependent paths.

## Deployment to AWS EC2

### Automated deployment script

The repository includes PowerShell scripts to automate deployment to AWS EC2:

```powershell
# One-time deployment with manual parameters
.\scripts\deploy.ps1 -InstanceIP "63.179.143.196" -KeyPath "C:\path\to\your\key.pem"

# Deploy to port 80 (requires EC2 security group rule for HTTP)
.\scripts\deploy.ps1 -InstanceIP "63.179.143.196" -KeyPath ".\aws_ec2_rex.pem" -Port 80

# Force rebuild and redeploy
.\scripts\deploy.ps1 -InstanceIP "63.179.143.196" -KeyPath ".\aws_ec2_rex.pem" -Force
```

### Environment-based deployment

For multiple environments, copy the configuration template and customize:

```powershell
# Copy and edit configuration
Copy-Item scripts\deploy-config.example.json scripts\deploy-config.json
# Edit deploy-config.json with your instance details

# Deploy to specific environment
.\scripts\deploy-env.ps1 -Environment production
.\scripts\deploy-env.ps1 -Environment staging
```

### What the deployment script does

1. **Builds** the Docker image locally
2. **Exports** image to tar file  
3. **Uploads** tar to EC2 via SCP
4. **Loads** image on remote instance
5. **Stops** any existing container
6. **Sets up** proper directory ownership for container user
7. **Starts** new container with correct port mapping and volumes
8. **Verifies** deployment with health check
9. **Cleans up** temporary files

### Prerequisites

- Docker Desktop installed locally
- OpenSSH client (for SCP)
- SSH key pair for EC2 instance
- Port opened in EC2 security group (8000 or 80)

### Manual Docker workflow

```powershell
# Build the image (installs dependencies, spaCy models, and NLTK data)
docker build -t newsreader -f docker/Dockerfile .

# Run both the Flask UI and the background daemon (default command)
docker run --rm -p 8000:8000 `
  -v "$(Get-Location)\data:/app/data" `
  -v "$(Get-Location)\config:/app/config" `
  -v "$(Get-Location)\var:/var/newsreader" `
  newsreader

# Launch only the web UI
docker run --rm -p 8000:8000 `
  -v "$(Get-Location)\data:/app/data" `
  -v "$(Get-Location)\config:/app/config" `
  -v "$(Get-Location)\var:/var/newsreader" `
  newsreader web

# Launch only the daemon
docker run --rm `
  -v "$(Get-Location)\data:/app/data" `
  -v "$(Get-Location)\config:/app/config" `
  -v "$(Get-Location)\var:/var/newsreader" `
  newsreader daemon

# Or run the full stack with docker compose (separate containers)
docker compose -f docker/docker-compose.yml up --build
```

`docker/docker-compose.yml` starts the combined stack service by default; enable the `dev` profile if you want individual
web-only or daemon-only containers (e.g. `docker compose --profile dev up web`).

`entrypoint.sh` exposes the combined mode under the `stack` command (the image default). You can customise the subprocess commands with
`NEWSREADER_STACK_WEB_CMD` or `NEWSREADER_STACK_DAEMON_CMD` environment variables if you need to add CLI flags.

The Compose file mounts `../data`, `../config`, and `../var` so that state persists between container runs. Update `FLASK_SECRET_KEY` in `docker/docker-compose.yml` before deploying outside of local development.

### Runtime environment variables

These defaults come from `src/newsreader/settings.py` and can be overridden for custom deployments:

- `NEWSREADER_DATA_DIR=/app/data`
- `NEWSREADER_VAR_DIR=/var/newsreader`
- `NEWSREADER_LOG_DIR=/var/newsreader/logs`
- `NEWSREADER_DB_PATH=$NEWSREADER_VAR_DIR/newsreader.db`
- `NEWSREADER_SOURCES_PATH=$NEWSREADER_DATA_DIR/sources.json`
- `NEWSREADER_GEO_PLACES_PATH=$NEWSREADER_DATA_DIR/geo_places.json`

## Next steps

- Automate image builds and pushes (GitHub Actions, GHCR, etc.).
- Add health-check endpoints for daemon/web services when orchestrating.
- Extend tests to mock external HTTP/spaCy resources for faster CI runs.
