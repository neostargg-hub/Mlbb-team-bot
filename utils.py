import hashlib
import hmac
import json
from typing import Dict, Any
from config import BOT_TOKEN, OWNER_ID

def validate_telegram_data(init_data: str) -> bool:
    try:
        data = dict(x.split('=') for x in init_data.split('&'))
        hash_str = data.pop('hash', None)
        if not hash_str:
            return False
        secret_key = hmac.new(
            key=BOT_TOKEN.encode(),
            msg=b"WebAppData",
            digestmod=hashlib.sha256
        ).digest()
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
        computed_hash = hmac.new(
            key=secret_key,
            msg=data_check_string.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()
        return computed_hash == hash_str
    except Exception:
        return False

def can_manage(user_id: int, author_id: int) -> bool:
    return user_id == author_id or user_id == OWNER_ID

def parse_user_from_init_data(init_data: str) -> Dict[str, Any]:
    params = dict(x.split('=') for x in init_data.split('&'))
    user_data = params.get("user")
    if user_data:
        return json.loads(user_data)
    return {}