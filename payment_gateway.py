"""Utilities for payment gateway integrations.

Currently this module provides a helper for generating the CheckMacValue used
by ECPay (綠界科技) APIs.  The function does not depend on any external
libraries and follows the algorithm described in ECPay's documentation:

1. Remove the ``CheckMacValue`` field if present.
2. Sort parameters alphabetically by their names.
3. Concatenate them with the ``HashKey`` and ``HashIV``.
4. URL‑encode the resulting string using ``quote_plus``.
5. Convert to lowercase, compute the MD5 digest and output the hex string in
   uppercase.

This helper can be used by other modules when signing requests to the ECPay
gateway.
"""

from __future__ import annotations

import hashlib
from urllib.parse import quote_plus


def generate_check_mac_value(
    params: dict[str, str], hash_key: str, hash_iv: str
) -> str:
    """Return the ECPay CheckMacValue for ``params``.

    Parameters
    ----------
    params:
        The key/value pairs to include in the MAC generation. Keys are sorted
        alphabetically. Any key named ``"CheckMacValue"`` is ignored.
    hash_key, hash_iv:
        Credentials provided by ECPay for your merchant account.
    """

    # Filter out the CheckMacValue field if it already exists.
    filtered = {k: v for k, v in params.items() if k != "CheckMacValue"}
    # Sort parameters alphabetically by key.
    query = "&".join(f"{k}={v}" for k, v in sorted(filtered.items()))
    raw = f"HashKey={hash_key}&{query}&HashIV={hash_iv}"
    encoded = quote_plus(raw, safe="-_.!*()")
    mac = hashlib.md5(encoded.lower().encode("utf-8")).hexdigest().upper()
    return mac


__all__ = ["generate_check_mac_value"]

