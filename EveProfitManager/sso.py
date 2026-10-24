"""EVE SSO sign-in: Authorization Code + PKCE (S256) for a desktop app."""
import base64
import hashlib
import json
import os
import secrets
import threading
import time
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import jwt
import requests

AUTHORIZE_URL = "https://login.eveonline.com/v2/oauth/authorize"
TOKEN_URL = "https://login.eveonline.com/v2/oauth/token"
REVOKE_URL = "https://login.eveonline.com/v2/oauth/revoke"
JWKS_URL = "https://login.eveonline.com/oauth/jwks"
ISSUER = "login.eveonline.com"

DEFAULT_PORT = 8765
SCOPES = [
    "esi-wallet.read_character_wallet.v1",
    "esi-location.read_location.v1",
    "esi-location.read_ship_type.v1",
    "esi-location.read_online.v1",
    "esi-assets.read_assets.v1",
]
CALLBACK_TIMEOUT = 300  # auth codes live 5 minutes


class InvalidToken(Exception):
    pass


class SignInError(Exception):
    pass


@dataclass
class Character:
    id: int
    name: str


def _client_id():
    client_id = os.environ.get("EVE_CLIENT_ID")
    if not client_id:
        raise SignInError(
            "Set the EVE_CLIENT_ID environment variable to your app's client ID "
            "(register at https://developers.eveonline.com/applications)."
        )
    return client_id


def _redirect_uri():
    return f"http://localhost:{os.environ.get('EVE_CALLBACK_PORT', DEFAULT_PORT)}/callback"


def _normalise_issuer(iss):
    return str(iss).removeprefix("https://").rstrip("/")


def validate_token(token, key, client_id):
    """Verify an SSO access token offline and return the Character it belongs to.

    `key` is the RS256 public key (see `fetch_signing_key` for the live JWKS one).
    """
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            options={"verify_aud": False, "verify_iss": False},
        )
    except jwt.PyJWTError as e:
        raise InvalidToken(str(e)) from e

    if _normalise_issuer(claims.get("iss", "")) != ISSUER:
        raise InvalidToken("unexpected issuer")

    aud = claims.get("aud", [])
    aud = [aud] if isinstance(aud, str) else aud
    if client_id not in aud or "EVE Online" not in aud:
        raise InvalidToken("audience mismatch")

    parts = str(claims.get("sub", "")).split(":")
    if len(parts) != 3 or parts[:2] != ["CHARACTER", "EVE"] or not parts[2].isdigit():
        raise InvalidToken("subject is not an EVE character")

    return Character(id=int(parts[2]), name=claims.get("name", ""))


def fetch_signing_key(token):
    return jwt.PyJWKClient(JWKS_URL).get_signing_key_from_jwt(token).key


def _pkce_pair():
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _wait_for_callback(port):
    """Serve one request on localhost and return its query parameters."""
    result = {}
    done = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlparse(self.path)
            if url.path != "/callback":
                self.send_error(404)
                return
            result.update({k: v[0] for k, v in parse_qs(url.query).items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Signed in. You can close this tab and return to the app.")
            done.set()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", port), Handler)
    server.timeout = 1
    deadline = time.time() + CALLBACK_TIMEOUT
    try:
        while not done.is_set() and time.time() < deadline:
            server.handle_request()
    finally:
        server.server_close()
    if not done.is_set():
        raise SignInError("Timed out waiting for the browser sign-in.")
    return result


def _token_request(data):
    response = requests.post(
        TOKEN_URL,
        data=data,
        headers={"Host": "login.eveonline.com"},
        timeout=15,
    )
    if response.status_code != 200:
        raise SignInError(f"Token endpoint returned {response.status_code}: {response.text}")
    return response.json()


def sign_in():
    """Open the browser for EVE SSO login. Returns (Character, token_response)."""
    client_id = _client_id()
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(16)
    port = int(os.environ.get("EVE_CALLBACK_PORT", DEFAULT_PORT))

    url = AUTHORIZE_URL + "?" + urlencode(
        {
            "response_type": "code",
            "redirect_uri": _redirect_uri(),
            "client_id": client_id,
            "scope": " ".join(SCOPES),
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
    )
    print(f"Opening your browser. If nothing happens, visit:\n{url}")
    webbrowser.open(url)

    params = _wait_for_callback(port)
    if params.get("state") != state:
        raise SignInError("State mismatch; sign-in aborted.")
    if "code" not in params:
        raise SignInError(f"Sign-in failed: {params.get('error_description', 'no code returned')}")

    tokens = _token_request(
        {
            "grant_type": "authorization_code",
            "code": params["code"],
            "client_id": client_id,
            "code_verifier": verifier,
        }
    )
    character = validate_token(
        tokens["access_token"], fetch_signing_key(tokens["access_token"]), client_id
    )
    return character, tokens


def refresh(refresh_token):
    """Exchange a refresh token. Always store the returned (possibly rotated) refresh token."""
    client_id = _client_id()
    tokens = _token_request(
        {"grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": client_id}
    )
    return tokens


def revoke(refresh_token):
    requests.post(
        REVOKE_URL,
        data={
            "token_type_hint": "refresh_token",
            "token": refresh_token,
            "client_id": _client_id(),
        },
        timeout=15,
    )


class TokenStore:
    """Per-character refresh tokens in the OS keychain, plus the active character id."""

    SERVICE = "EveProfitManager"
    INDEX = "_characters"

    def __init__(self):
        import keyring  # imported lazily so the rest of the app runs without it

        self._kr = keyring

    def _index(self):
        raw = self._kr.get_password(self.SERVICE, self.INDEX)
        return json.loads(raw) if raw else {"characters": {}, "active": None}

    def _save_index(self, index):
        self._kr.set_password(self.SERVICE, self.INDEX, json.dumps(index))

    def save(self, character, refresh_token):
        self._kr.set_password(self.SERVICE, str(character.id), refresh_token)
        index = self._index()
        index["characters"][str(character.id)] = character.name
        index["active"] = index["active"] or character.id
        self._save_index(index)

    def update_refresh_token(self, character_id, refresh_token):
        self._kr.set_password(self.SERVICE, str(character_id), refresh_token)

    def refresh_token(self, character_id):
        return self._kr.get_password(self.SERVICE, str(character_id))

    def characters(self):
        return [Character(int(i), n) for i, n in self._index()["characters"].items()]

    def active(self):
        index = self._index()
        active = index["active"]
        if active is None:
            return None
        return Character(int(active), index["characters"].get(str(active), ""))

    def set_active(self, character_id):
        index = self._index()
        if str(character_id) in index["characters"]:
            index["active"] = int(character_id)
            self._save_index(index)

    def remove(self, character_id):
        try:
            self._kr.delete_password(self.SERVICE, str(character_id))
        except self._kr.errors.PasswordDeleteError:
            pass
        index = self._index()
        index["characters"].pop(str(character_id), None)
        if index["active"] == int(character_id):
            remaining = list(index["characters"])
            index["active"] = int(remaining[0]) if remaining else None
        self._save_index(index)
