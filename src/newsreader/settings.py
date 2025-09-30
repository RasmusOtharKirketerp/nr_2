"""Application settings and filesystem layout helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Centralised runtime configuration for the Newsreader app."""

    package_root: Path
    src_root: Path
    project_root: Path
    config_dir: Path
    data_dir: Path
    var_dir: Path
    log_dir: Path
    templates_dir: Path
    default_db_path: Path
    default_sources_path: Path
    default_geo_places_path: Path
    daemon_log_path: Path


def _resolve_path(environment_key: str, default: Path) -> Path:
    """Return a path from environment or fall back to default."""
    raw_value = os.environ.get(environment_key)
    if not raw_value:
        return default
    return Path(raw_value).expanduser().resolve()


@lru_cache
def get_settings() -> Settings:
    """Compute and cache filesystem locations used by the app."""
    package_root = Path(__file__).resolve().parent
    src_root = package_root.parent
    project_root = src_root.parent

    config_dir = _resolve_path('NEWSREADER_CONFIG_DIR', project_root / 'config')
    data_dir = _resolve_path('NEWSREADER_DATA_DIR', project_root / 'data')
    var_dir = _resolve_path('NEWSREADER_VAR_DIR', project_root / 'var')
    log_dir = _resolve_path('NEWSREADER_LOG_DIR', var_dir / 'logs')

    templates_dir = _resolve_path('NEWSREADER_TEMPLATE_DIR', package_root / 'templates')
    default_db_path = _resolve_path('NEWSREADER_DB_PATH', var_dir / 'newsreader.db')
    default_sources_path = _resolve_path('NEWSREADER_SOURCES_PATH', data_dir / 'sources.json')
    default_geo_places_path = _resolve_path('NEWSREADER_GEO_PLACES_PATH', data_dir / 'geo_places.json')
    daemon_log_path = _resolve_path('NEWSREADER_DAEMON_LOG', log_dir / 'news_daemon.log')

    # Ensure directories exist so docker mounts work out of the box.
    for path in (config_dir, data_dir, var_dir, log_dir):
        path.mkdir(parents=True, exist_ok=True)

    default_db_path.parent.mkdir(parents=True, exist_ok=True)
    daemon_log_path.parent.mkdir(parents=True, exist_ok=True)

    return Settings(
        package_root=package_root,
        src_root=src_root,
        project_root=project_root,
        config_dir=config_dir,
        data_dir=data_dir,
        var_dir=var_dir,
        log_dir=log_dir,
        templates_dir=templates_dir,
        default_db_path=default_db_path,
        default_sources_path=default_sources_path,
        default_geo_places_path=default_geo_places_path,
        daemon_log_path=daemon_log_path,
    )
