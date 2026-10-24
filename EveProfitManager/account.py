"""The signed-in EVE account the app reads from: saved characters, the active one, its ESI client."""
import jwt
import requests

import sso
from esi import EsiClient

# What a sign-in or token refresh can raise for the user to read
SIGN_IN_ERRORS = (sso.SignInError, sso.InvalidToken, jwt.PyJWTError, requests.RequestException)
try:
    import keyring.errors

    SIGN_IN_ERRORS += (keyring.errors.KeyringError,)  # e.g. no usable keychain backend
except ImportError:
    pass  # Account.store reports the missing package


class Account:
    def __init__(self):
        self._store = None
        self._client = None

    @property
    def store(self):
        if self._store is None:
            try:
                self._store = sso.TokenStore()
            except ImportError as e:
                raise sso.SignInError("Install the 'keyring' package to use EVE sign-in.") from e
        return self._store

    def characters(self):
        return self.store.characters()

    def active(self):
        return self.store.active()

    def select(self, character_id):
        self.store.set_active(character_id)
        self._client = None

    def sign_in(self):
        """Browser login; saves the character and makes it the active one."""
        character, tokens = sso.sign_in()
        self.store.save(character, tokens["refresh_token"])
        self.select(character.id)
        return character

    def sign_out(self):
        """Revoke and forget the active character."""
        active = self.active()
        if active is None:
            return None
        try:
            sso.revoke(self.store.refresh_token(active.id))
        except Exception:
            pass  # still remove the local copy
        self.store.remove(active.id)
        self._client = None
        return active

    def client(self):
        """ESI client for the active character, or None when nobody is signed in."""
        active = self.active()
        if active is None:
            return None
        if self._client is None or self._client.character.id != active.id:
            self._client = EsiClient(self.store, active)
        return self._client
