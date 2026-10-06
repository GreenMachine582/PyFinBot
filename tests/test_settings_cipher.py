"""Secret settings are encrypted with greentechhub-core's settings_cipher
(core v0.11) instead of PyFinBot's own key code: SETTINGS_CIPHER_KEY when
set, else the same key PyFinBot always derived from SECRET_KEY, so app
passwords saved before the switch still decrypt."""
import base64
import hashlib
import warnings

import pytest
from cryptography.fernet import Fernet
from greentechhub_core.settings.crypto import settings_cipher

import pyfinbot.pyfinbot as app_module
from pyfinbot.core.settings import Settings


def _config(monkeypatch, secret, cipher_key=None) -> Settings:
    if cipher_key is None:
        monkeypatch.delenv("SETTINGS_CIPHER_KEY", raising=False)
    else:
        monkeypatch.setenv("SETTINGS_CIPHER_KEY", cipher_key)
    return Settings(_env_file=None, secret_key=secret)


def _old_key(secret: str) -> bytes:
    """PyFinBot's derivation before core's settings_cipher."""
    return base64.urlsafe_b64encode(hashlib.sha256(f"pyfinbot-settings:{secret}".encode()).digest())


def test_the_app_keeps_its_derivation_context():
    assert app_module.CIPHER_CONTEXT == "pyfinbot-settings"


def test_a_configured_key_is_used_without_a_warning(monkeypatch):
    key = Fernet.generate_key().decode()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        cipher = settings_cipher(_config(monkeypatch, "k", key), context=app_module.CIPHER_CONTEXT)
    token = cipher.encrypt("app password")
    assert Fernet(key.encode()).decrypt(token.encode()).decode() == "app password"


def test_passwords_saved_before_the_switch_still_decrypt(monkeypatch):
    old_token = Fernet(_old_key("server-secret")).encrypt(b"abcd efgh").decode()
    with pytest.warns(UserWarning, match="SETTINGS_CIPHER_KEY is not set"):
        cipher = settings_cipher(_config(monkeypatch, "server-secret"),
                                 context=app_module.CIPHER_CONTEXT)
    assert cipher.decrypt(old_token) == "abcd efgh"


def test_a_different_secret_key_gives_a_different_key(monkeypatch):
    with pytest.warns(UserWarning):
        first = settings_cipher(_config(monkeypatch, "one"), context=app_module.CIPHER_CONTEXT)
    with pytest.warns(UserWarning):
        second = settings_cipher(_config(monkeypatch, "two"), context=app_module.CIPHER_CONTEXT)
    with pytest.raises(ValueError):
        second.decrypt(first.encrypt("x"))
