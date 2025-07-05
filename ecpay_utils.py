import urllib.parse
import hashlib


def gen_check_mac_value(params, hash_key, hash_iv):
    sorted_params = sorted(params.items())
    encode_str = (
        f"HashKey={hash_key}&" + "&".join(f"{k}={v}" for k, v in sorted_params) + f"&HashIV={hash_iv}"
    )
    encode_str = urllib.parse.quote_plus(encode_str).lower()
    check_mac_value = hashlib.sha256(encode_str.encode('utf-8')).hexdigest().upper()
    return check_mac_value
