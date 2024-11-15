from datetime import datetime, timedelta
import hmac
import hashlib
import pprint
from typing import Optional
import urllib.parse
import uuid

import jwt
from src.config.settings import Config
from src.errors import InvalidToken, TokenExpired
from src.utils.logger import LOGGER
from init_data_py import InitData


def verifyTelegramAuthData(telegram_init_data: str) -> bool:
    bot_token=Config.TELEGRAM_TOKEN
    vals = {k: urllib.parse.unquote(v) for k, v in [s.split('=', 1) for s in telegram_init_data.split('&')]}
    data_check_string = '\n'.join(f"{k}={v}" for k, v in sorted(vals.items()) if k != 'hash')

    secret_key = hmac.new("WebAppData".encode(), bot_token.encode(), hashlib.sha256).digest()
    h = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256)
    LOGGER.info(h.hexdigest())
    LOGGER.info(vals['hash'])
    return h.hexdigest() == vals['hash']
    
    # encoded = urllib.parse.unquote(telegram_init_data)
    # secret = hmac.new('WebAppData'.encode(), Config.TELEGRAM_TOKEN.encode(), hashlib.sha256).digest()
    # data_parts = encoded.split('&')
    
    # # Find the 'hash' parameter
    # hash_index = next((i for i, part in enumerate(data_parts) if part.startswith('hash=')), -1)
    # LOGGER.debug(f"HASH: {hash_index}")
    # if hash_index == -1:
    #     return False
    
    # # Extract the hash value
    # hash_value = data_parts.pop(hash_index).split('=')[1]
    # LOGGER.debug(pprint.pprint(data_parts, indent=4))
    
    # filled_string = []
    
    # for data in data_parts:
    #     filled_string.append(data)
    
    # filled_string.append(f"hash={hash_value}")
    
    # # Sort the remaining data parts
    # filled_string.sort()
    
    # LOGGER.debug(pprint.pprint(filled_string, indent=4))
    
    # # Compute the data check string
    # data_check_string = r'\n'.join(data_parts)
    # LOGGER.debug(pprint.pprint(data_check_string, indent=4))
    
    
    # # Compute the expected hash
    # expected_hash = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    # LOGGER.debug(pprint.pprint(f"Existing HASH: {hash_value}\nExpected HASH: {expected_hash}", indent=4))
    
    # return hmac.compare_digest(expected_hash, hash_value)

    # init_data = InitData.parse(telegram_init_data)
    # LOGGER.debug(init_data)
    # LOGGER.info(Config.TELEGRAM_TOKEN)
    # isValid = init_data.validate(Config.TELEGRAM_TOKEN)
    # return isValid
    # return False
    

def createAccessToken(user_data: dict, expiry: timedelta = None, refresh: bool = False) -> str:
    payload = {}
    payload["user"] = user_data
    payload["exp"] = datetime.now() + (
        expiry if expiry is not None else timedelta(seconds=Config.ACCESS_TOKEN_EXPIRY)
    )
    payload["jti"] = str(uuid.uuid4())
    token = jwt.encode(
        payload=payload, key=Config.TELEGRAM_TOKEN, algorithm=Config.ALGORITHM
    )
    return token

def decodeAccessToken(token: str) -> dict:
    try:
        token_data = jwt.decode(
            jwt=token, key=Config.TELEGRAM_TOKEN, algorithms=[Config.ALGORITHM]
        )
        return token_data
    except jwt.ExpiredSignatureError:
        raise TokenExpired()
    except jwt.PyJWTError as e:
        raise InvalidToken()
    
# Deprecated
    # """
    # user=%7B%22id%22%3A7156514044%2C%22first_name%22%3A%22%7E%7E%22%2C%22last_name%22%3A%22%22%2C%22language_code%22%3A%22en%22%2C%22allows_write_to_pm%22%3Atrue%2C%22photo_url%22%3A%22https%3A%5C%2F%5C%2Ft.me%5C%2Fi%5C%2Fuserpic%5C%2F320%5C%2FoFY2iAKaQPureEYt_UcsSdtVtFCPtechdt88ebqNbTXiKy4iZNHvkFmIJb5rPox1.svg%22%7D&chat_instance=-7283749404892336505&chat_type=sender&auth_date=1731501643&hash=ed282cec2c91fbaec8069d49127a3eea3ec16ee029efcdc438495e707cff7cef
    # """
    # # Get hash_value from the query string
    # init_data =  parse_qs(telegram_init_data)
    
    # hash_value = init_data.get('hash', [None])[0]
    # data_to_check = []
    

    # # Sort key-value pair by alphabet
    # sorted_items = sorted((key, val[0]) for key, val in init_data.items() if key != 'hash')
    # data_to_check = [f"{key}={value}" for key, value in sorted_items]
    
    # print("Scaffolding here:: ", init_data, hash_value, sorted_items, data_to_check)
    # LOGGER.info(f"HASH: {hash_value}")
    # LOGGER.info(f"DATACHECK: {data_to_check}")

    # # HMAC Caculation
    # secret = hmac.new(b"WebAppData", Config.TELEGRAM_TOKEN.encode(), hashlib.sha256).digest()
    # _hash = hmac.new(secret, "\n".join(data_to_check).encode(), hashlib.sha256).hexdigest()
    # LOGGER.info(f"NEWHASH: {_hash}")
    # return _hash == hash_value
