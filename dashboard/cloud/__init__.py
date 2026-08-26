"""BioGuard cloud layer.

One farm node proves the product works. A fleet proves it's a business — so
the bridge mirrors everything it sees into Firestore under a farm id, and the
cloud layer turns many farms' history into something no single node can know.

Configuration is entirely environment-driven, so the same code runs on Alp's
laptop, on a demo laptop with no credentials, and in a real deployment:

  BIOGUARD_FIREBASE_KEY   path to the service-account .json  (unset -> local)
  BIOGUARD_PROJECT_ID     override the project id in that key file
  BIOGUARD_FARM_ID        which farm this gateway is          (strajer-01)
  BIOGUARD_CLOUD          on | off | auto                     (auto)
  BIOGUARD_LOCAL_DB       where the offline store lives

With no credentials at all, everything still runs against LocalStore. That is
not a stub: it is the same data, the same model, the same console. It just
isn't shared between machines.
"""
from __future__ import annotations

import os
import threading

from .store import FirestoreStore, LocalStore

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOCAL = os.path.join(_HERE, "..", "cloud_local.json")


class Config:
    def __init__(self):
        self.key_path = os.environ.get("BIOGUARD_FIREBASE_KEY", "").strip()
        self.project_id = os.environ.get("BIOGUARD_PROJECT_ID", "").strip()
        self.farm_id = os.environ.get("BIOGUARD_FARM_ID", "strajer-01").strip()
        self.mode = os.environ.get("BIOGUARD_CLOUD", "auto").strip().lower()
        self.local_db = os.path.abspath(
            os.environ.get("BIOGUARD_LOCAL_DB", DEFAULT_LOCAL))
        self.web_api_key = os.environ.get("BIOGUARD_WEB_API_KEY", "").strip()


CFG = Config()

_store = None
_store_lock = threading.Lock()
_status = {"backend": "none", "detail": "not initialised", "project": ""}


def open_store(force: bool = False):
    """The one place a store is constructed. Falling back is never fatal —
    a demo that dies because Firestore 500s is a demo that dies."""
    global _store
    with _store_lock:
        if _store is not None and not force:
            return _store
        if CFG.mode == "off":
            _store = LocalStore(CFG.local_db)
            _status.update(backend="local", project="local-offline",
                           detail="cloud disabled (BIOGUARD_CLOUD=off)")
            return _store
        if CFG.key_path and os.path.exists(CFG.key_path):
            try:
                s = FirestoreStore(CFG.key_path, CFG.project_id)
                s.cred.token()          # fail fast on a bad key, not mid-demo
                _store = s
                _status.update(backend="firestore", project=s.project_id,
                               detail="connected")
                return _store
            except Exception as e:
                _status.update(backend="local", project="local-offline",
                               detail=f"firestore unavailable ({e}) — using local store")
        elif CFG.key_path:
            _status.update(backend="local", project="local-offline",
                           detail=f"key file not found: {CFG.key_path}")
        else:
            _status.update(backend="local", project="local-offline",
                           detail="no BIOGUARD_FIREBASE_KEY set — using local store")
        _store = LocalStore(CFG.local_db)
        return _store


def status() -> dict:
    open_store()
    return dict(_status, farm_id=CFG.farm_id, local_db=CFG.local_db)
