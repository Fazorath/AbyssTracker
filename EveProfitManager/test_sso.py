import time
import unittest

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from sso import InvalidToken, validate_token

CLIENT_ID = "my-client-id"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def make_token(key=KEY, **overrides):
    claims = {
        "iss": "https://login.eveonline.com",
        "aud": [CLIENT_ID, "EVE Online"],
        "sub": "CHARACTER:EVE:123456",
        "name": "Test Pilot",
        "exp": int(time.time()) + 1200,
    }
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256")


def validate(token):
    return validate_token(token, KEY.public_key(), CLIENT_ID)


class ValidateTokenTests(unittest.TestCase):
    def test_valid_token_returns_character(self):
        character = validate(make_token())
        self.assertEqual(character.id, 123456)
        self.assertEqual(character.name, "Test Pilot")

    def test_issuer_accepted_with_or_without_scheme_and_slash(self):
        for iss in ("login.eveonline.com", "https://login.eveonline.com/"):
            with self.subTest(iss=iss):
                self.assertEqual(validate(make_token(iss=iss)).id, 123456)

    def test_rejects_bad_tokens(self):
        bad = {
            "wrong signature": make_token(key=OTHER_KEY),
            "wrong issuer": make_token(iss="https://evil.example.com"),
            "missing client id in aud": make_token(aud=["other", "EVE Online"]),
            "missing EVE Online in aud": make_token(aud=[CLIENT_ID]),
            "expired": make_token(exp=int(time.time()) - 10),
            "non-character subject": make_token(sub="CORPORATION:EVE:1"),
        }
        for label, token in bad.items():
            with self.subTest(label):
                with self.assertRaises(InvalidToken):
                    validate(token)


if __name__ == "__main__":
    unittest.main()
