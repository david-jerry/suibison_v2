from datetime import datetime, timedelta
import hmac
import hashlib
import pprint
from typing import Optional
import urllib.parse
import uuid
from passlib.context import CryptContext
import jwt
from src.config.settings import Config
from src.errors import InvalidToken, TokenExpired
from src.utils.logger import LOGGER
from init_data_py import InitData

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated='auto')

def generateHashKey(word: str) -> str:
    """
    The function `generateHashKey` takes a string input, hashes it using bcrypt, and returns the hashed
    value.

    :param word: The `generateHashKey` function takes a string `word` as input and generates a hash key
    using the `bcrypt_context.hash` function. The hash key is then returned as a string
    :type word: str
    :return: The function `generateHashKey` takes a string input `word`, hashes it using bcrypt, and
    returns the hashed value as a string.
    """
    hash = bcrypt_context.hash(word)
    return hash

def verifyHashKey(word: str, hash: str) -> bool:
    """
    The function `verifyHashKey` checks if a given word matches a given hash using bcrypt hashing.

    :param word: The `word` parameter is a string that represents the plaintext password that you want
    to verify against the hashed password
    :type word: str
    :param hash: The `hash` parameter in the `verifyHashKey` function is typically a hashed version of a
    password or some other sensitive information. It is used for comparison with the original plaintext
    value to verify its authenticity without storing the actual password in plain text
    :type hash: str
    :return: The function `verifyHashKey` is returning a boolean value indicating whether the provided
    `word` matches the `hash` value after verification using bcrypt.
    """
    correct = bcrypt_context.verify(word, hash)
    return correct

def verifyTelegramAuthData(telegram_init_data: str) -> bool:
    bot_token=Config.TELEGRAM_TOKEN
    vals = {k: urllib.parse.unquote(v) for k, v in [s.split('=', 1) for s in telegram_init_data.split('&')]}
    data_check_string = '\n'.join(f"{k}={v}" for k, v in sorted(vals.items()) if k != 'hash')

    secret_key = hmac.new("WebAppData".encode(), bot_token.encode(), hashlib.sha256).digest()
    h = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256)
    LOGGER.info(h.hexdigest())
    LOGGER.info(vals['hash'])
    return h.hexdigest() == vals['hash']    

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
    
