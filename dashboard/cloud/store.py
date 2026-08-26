"""Firestore access with zero third-party dependencies.

The bridge already has `cryptography` and `requests`, so this module signs the
service-account JWT itself and speaks the Firestore REST API directly. A
`pip install firebase-admin` that has to succeed on venue Wi-Fi the morning of
the pitch is a risk we simply don't take.

Two interchangeable backends behind one interface:

  FirestoreStore  real Google Cloud Firestore (credentials present)
  LocalStore      a JSON file on disk (no credentials, or the network is down)

Everything above this layer — the sink, the fleet model, the console, the
app's fallback endpoint — is written against the interface, so the whole
system renders identically either way. Losing the internet degrades the cloud
story to "the last synced snapshot"; it never breaks the demo.
"""
from __future__ import annotations

import atexit
import base64
import json
import os
import threading
import time
from datetime import datetime, timezone

import requests

TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/datastore"
API = "https://firestore.googleapis.com/v1"


# ── value codec (Firestore REST uses typed values) ───────────────────────
def enc(v):
    if v is None:
        return {"nullValue": None}
    if isinstance(v, bool):
        return {"booleanValue": v}
    if isinstance(v, int):
        return {"integerValue": str(v)}
    if isinstance(v, float):
        return {"doubleValue": v}
    if isinstance(v, datetime):
        t = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        return {"timestampValue": t.astimezone(timezone.utc)
                .strftime("%Y-%m-%dT%H:%M:%S.%fZ")}
    if isinstance(v, (list, tuple)):
        return {"arrayValue": {"values": [enc(x) for x in v]}}
    if isinstance(v, dict):
        return {"mapValue": {"fields": {k: enc(x) for k, x in v.items()}}}
    return {"stringValue": str(v)}


def dec(v):
    if not isinstance(v, dict) or not v:
        return None
    k, val = next(iter(v.items()))
    if k == "nullValue":
        return None
    if k == "integerValue":
        return int(val)
    if k == "doubleValue":
        return float(val)
    if k == "booleanValue":
        return bool(val)
    if k == "timestampValue":
        return val
    if k == "arrayValue":
        return [dec(x) for x in (val or {}).get("values", [])]
    if k == "mapValue":
        return {kk: dec(vv) for kk, vv in (val or {}).get("fields", {}).items()}
    return val


def fields(d: dict) -> dict:
    return {k: enc(v) for k, v in d.items()}


def unfields(doc: dict) -> dict:
    return {k: dec(v) for k, v in (doc or {}).get("fields", {}).items()}


# ── service-account auth (RS256 JWT -> OAuth access token) ───────────────
class _Credentials:
    """Signs a JWT with the service-account private key and trades it for an
    access token. Tokens last an hour; we refresh a minute early."""

    def __init__(self, path: str):
        with open(path) as f:
            self.sa = json.load(f)
        self.project_id = self.sa["project_id"]
        self._token = None
        self._exp = 0.0
        self._lock = threading.Lock()

    def _sign(self, msg: bytes) -> bytes:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        key = serialization.load_pem_private_key(
            self.sa["private_key"].encode(), password=None)
        return key.sign(msg, padding.PKCS1v15(), hashes.SHA256())

    def token(self) -> str:
        with self._lock:
            if self._token and time.time() < self._exp:
                return self._token
            now = int(time.time())
            b64 = lambda o: base64.urlsafe_b64encode(
                json.dumps(o, separators=(",", ":")).encode()).rstrip(b"=")
            head = b64({"alg": "RS256", "typ": "JWT"})
            body = b64({"iss": self.sa["client_email"], "scope": SCOPE,
                        "aud": TOKEN_URL, "iat": now, "exp": now + 3600})
            unsigned = head + b"." + body
            sig = base64.urlsafe_b64encode(self._sign(unsigned)).rstrip(b"=")
            r = requests.post(TOKEN_URL, timeout=15, data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": (unsigned + b"." + sig).decode()})
            r.raise_for_status()
            j = r.json()
            self._token = j["access_token"]
            self._exp = time.time() + int(j.get("expires_in", 3600)) - 60
            return self._token


# ── backends ─────────────────────────────────────────────────────────────
class FirestoreStore:
    kind = "firestore"

    def __init__(self, key_path: str, project_id: str = ""):
        self.cred = _Credentials(key_path)
        self.project_id = project_id or self.cred.project_id
        self.root = (f"{API}/projects/{self.project_id}"
                     f"/databases/(default)/documents")
        self.s = requests.Session()

    def _h(self):
        return {"Authorization": f"Bearer {self.cred.token()}",
                "Content-Type": "application/json"}

    def set_doc(self, path: str, data: dict, merge: bool = True):
        url = f"{self.root}/{path}"
        params = []
        if merge:
            params = [("updateMask.fieldPaths", k) for k in data]
        r = self.s.patch(url, headers=self._h(), params=params, timeout=20,
                         data=json.dumps({"fields": fields(data)}))
        r.raise_for_status()
        return unfields(r.json())

    def get_doc(self, path: str):
        r = self.s.get(f"{self.root}/{path}", headers=self._h(), timeout=20)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return unfields(r.json())

    def add_doc(self, collection: str, data: dict):
        r = self.s.post(f"{self.root}/{collection}", headers=self._h(),
                        timeout=20, data=json.dumps({"fields": fields(data)}))
        r.raise_for_status()
        return unfields(r.json())

    def commit(self, writes: list[tuple[str, dict]]):
        """Batch set_doc. Firestore caps a commit at 500 writes."""
        if not writes:
            return
        for i in range(0, len(writes), 400):
            chunk = writes[i:i + 400]
            body = {"writes": [
                {"update": {"name": f"projects/{self.project_id}"
                                    f"/databases/(default)/documents/{p}",
                            "fields": fields(d)},
                 "updateMask": {"fieldPaths": list(d)}}
                for p, d in chunk]}
            r = self.s.post(f"{API}/projects/{self.project_id}"
                            f"/databases/(default)/documents:commit",
                            headers=self._h(), timeout=45, data=json.dumps(body))
            r.raise_for_status()

    def list_docs(self, collection: str, order_by: str = "", desc: bool = False,
                  limit: int = 100):
        parent, _, coll = collection.rpartition("/")
        q = {"from": [{"collectionId": coll}], "limit": limit}
        if order_by:
            q["orderBy"] = [{"field": {"fieldPath": order_by},
                             "direction": "DESCENDING" if desc else "ASCENDING"}]
        url = f"{self.root}/{parent}:runQuery" if parent else f"{self.root}:runQuery"
        r = self.s.post(url, headers=self._h(), timeout=45,
                        data=json.dumps({"structuredQuery": q}))
        r.raise_for_status()
        out = []
        for row in r.json():
            d = row.get("document")
            if d:
                rec = unfields(d)
                rec["_id"] = d["name"].rsplit("/", 1)[-1]
                out.append(rec)
        return out

    def flush(self):
        """No-op — Firestore writes are already durable when commit returns."""

    def list_collection_ids(self, parent: str = ""):
        url = f"{self.root}/{parent}:listCollectionIds" if parent \
            else f"{self.root}:listCollectionIds"
        r = self.s.post(url, headers=self._h(), timeout=20, data="{}")
        r.raise_for_status()
        return r.json().get("collectionIds", [])


class LocalStore:
    """File-backed stand-in. Same interface, same shapes, no network."""
    kind = "local"

    def __init__(self, path: str):
        self.path = path
        self.project_id = "local-offline"
        self._lock = threading.Lock()
        self.db: dict[str, dict] = {}
        self._auto = 0
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.db = json.load(f)
            except (json.JSONDecodeError, OSError):
                self.db = {}
        self._dirty = False
        self._last_flush = 0.0
        # The 2 s write throttle below is what makes a 3 000-doc seed fast, but
        # on its own it silently loses whichever writes land inside the last
        # window before the process exits — which is exactly where a seed puts
        # fleet/model. A daemon flusher plus an atexit hook close that hole.
        threading.Thread(target=self._flusher, daemon=True).start()
        atexit.register(self.flush)

    def _flusher(self):
        while True:
            time.sleep(2.0)
            try:
                with self._lock:
                    self._flush(force=True)
            except OSError:
                pass

    def flush(self):
        with self._lock:
            self._flush(force=True)

    def _flush(self, force=False):
        # the sink writes ~1 doc/s; fsyncing each one would be silly
        if not self._dirty:
            return
        if not force and time.time() - self._last_flush < 2.0:
            return
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.db, f)
        os.replace(tmp, self.path)
        self._dirty = False
        self._last_flush = time.time()

    def set_doc(self, path: str, data: dict, merge: bool = True):
        with self._lock:
            cur = self.db.get(path, {}) if merge else {}
            cur.update({k: _plain(v) for k, v in data.items()})
            self.db[path] = cur
            self._dirty = True
            self._flush()
            return cur

    def get_doc(self, path: str):
        return self.db.get(path)

    def add_doc(self, collection: str, data: dict):
        with self._lock:
            self._auto += 1
            key = f"{collection}/a{int(time.time()*1000)}{self._auto:04d}"
        return self.set_doc(key, data, merge=False)

    def commit(self, writes):
        for p, d in writes:
            self.set_doc(p, d)
        self.flush()

    def list_docs(self, collection: str, order_by: str = "", desc: bool = False,
                  limit: int = 100):
        pre = collection.rstrip("/") + "/"
        out = []
        for k, v in self.db.items():
            if k.startswith(pre) and "/" not in k[len(pre):]:
                rec = dict(v)
                rec["_id"] = k[len(pre):]
                out.append(rec)
        if order_by:
            out.sort(key=lambda r: (r.get(order_by) is None, r.get(order_by)),
                     reverse=desc)
        return out[:limit]

    def list_collection_ids(self, parent: str = ""):
        pre = (parent.rstrip("/") + "/") if parent else ""
        ids = set()
        for k in self.db:
            rest = k[len(pre):] if k.startswith(pre) else None
            if rest and "/" in rest:
                ids.add(rest.split("/", 1)[0])
            elif rest and not parent:
                pass
        return sorted(ids)


def _plain(v):
    if isinstance(v, datetime):
        t = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    return v
