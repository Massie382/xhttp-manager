#!/usr/bin/env python3
"""Start the xhttp-manager API server, reading settings from config.toml."""
import sys, os, toml

sys.path.insert(0, '/opt/xhttp-manager/addon')

from api.main import app
import uvicorn

# ---------------------------------------------------------------------------
# Load settings from config.toml
# ---------------------------------------------------------------------------
def _load_config():
    config_paths = [
        os.environ.get('XHTTP_MANAGER_CONFIG', ''),
        '/etc/xhttp-manager/config.toml',
        '/opt/xhttp-manager/addon/config.toml',
    ]
    for cp in config_paths:
        try:
            if cp and os.path.exists(cp):
                return toml.load(cp)
        except Exception:
            pass
    return {}

cfg = _load_config()
host      = cfg.get('api', {}).get('host', '127.0.0.1')
port      = cfg.get('api', {}).get('port', 7171)
log_level = cfg.get('api', {}).get('log_level', 'info')

uvicorn.run(app, host=host, port=port, log_level=log_level)
