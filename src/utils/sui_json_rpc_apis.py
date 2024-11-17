from decimal import Decimal
import pprint
from typing import List
import base64
import hashlib
import asyncio
import requests

from src.apps.accounts.models import User
from src.apps.accounts.schemas import Coin, CoinBalance, MetaData, SuiTransferResponse, TransactionResponseData
from src.config.settings import Config
from src.utils.logger import LOGGER
from sui_python_sdk.wallet import SuiWallet
import ecdsa

class SUIRequests:
    def __init__(self, url: str = Config.SUI_RPC) -> None:
        self.url = url
        self.decimals = 10**9
                
    async def sign_transaction(self, txBytes: bytes, pk: str, pubKey: bytes):
        hasher = hashlib.blake2b(digest_size=32)
        hasher.update(txBytes)
        digest = hasher.digest()
        
        pkBytes = bytes.fromhex(pk)
        pkECDSAKey = ecdsa.SigningKey.from_string(pkBytes, curve=ecdsa.SECP256k1)
        signature = pkECDSAKey.sign(digest, hashfunc=hashlib.blake2b, sigencode=ecdsa.util.sigencode_string)
        
        flag = b"0x01"
        serialized_sig = flag + signature + pubKey
        return serialized_sig
        
        
    async def getBalance(self, address: str, coinType: str = "0x2::sui::SUI"):
        """
        Geets the balance for a specific coin defaults to sui and returns the balance of the coin and coinId
        """
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "suix_getBalance",
            "params": [
                address,
                coinType
            ]
        }
        
        response = await asyncio.to_thread(requests.post, self.url, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            if 'error' in result:
                raise Exception(f"Error: {result['error']}")
            res = result["result"]
            LOGGER.debug(res)
            return CoinBalance(**res)
        else:
            response.raise_for_status()
            
    async def getCoinMetadata(self, coinType: str = "0x2::sui::SUI"):
        """
        Gets the metadata for a specified coin type defaults to sui and returns a response which includes the coin id used for transafers 
        """
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "suix_getCoinMetadata",
            "params": [
                coinType
            ]
        }
        
        response = await asyncio.to_thread(requests.post, self.url, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            if 'error' in result:
                raise Exception(f"Error: {result['error']}")
            metadata = result["result"]
            return MetaData(**metadata)
        else:
            response.raise_for_status()
 
    async def getCoins(self, address: str):
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "suix_getAllCoins",
            "params": [
                address
            ]
        }
        
        response = await asyncio.to_thread(requests.post, self.url, json=payload)
        coins: List[Coin] = []
        if response.status_code == 200:
            result = response.json()
            if 'error' in result:
                raise Exception(f"Error: {result['error']}")
            for coin in result['result']["data"]:
                if coin["coinType"] == "0x2::sui::SUI":
                    coins.append(Coin(**coin))
            return coins
        else:
            response.raise_for_status()

    async def paySui(self, address: str, recipient: str, amount: Decimal, gas_budget: int, coinId: str):
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "unsafe_paySui",
            "params": [
                address,
                [coinId],
                [recipient],
                [str(amount)],
                str(gas_budget)
            ]
        }
        
        response = await asyncio.to_thread(requests.post, self.url, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            if 'error' in result:
                raise Exception(f"Error: {result['error']}")
            res = result["result"]
            return SuiTransferResponse(**res)
        else:
            response.raise_for_status()
        
    async def payAllSui(self, address: str, recipient: str, gas_budget: int, coinId: str):
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "unsafe_payAllSui",
            "params": [
                address,
                [coinId],
                [recipient],
                str(gas_budget)
            ]
        }
        
        response = await asyncio.to_thread(requests.post, self.url, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            if 'error' in result:
                raise Exception(f"Error: {result['error']}")
            res = result["result"]
            return SuiTransferResponse(**res)
        else:
            response.raise_for_status()
            
    async def dryRun(self, txBytes: str):
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sui_dryRunTransactionBlock",
            "params": [
                txBytes,
            ]
        }
        response = await asyncio.to_thread(requests.post, self.url, json=payload)
        LOGGER.debug(response)
        
        if response.status_code == 200:
            result = response.json()
            if 'error' in result:
                raise Exception(f"Error: {result['error']}")
            res = result["result"]["transaction"]["txSignatures"]
            LOGGER.debug(pprint.pprint(res, indent=4))
            return TransactionResponseData(**res)
        else:
            response.raise_for_status()

    async def executeTransaction(self, bcsTxBytes: str, phrase: str):
        # NOTE WORK ON THIS TO DETERMINE THE SIGNER
        my_wallet = SuiWallet(mnemonic=phrase)
        pk = my_wallet.private_key.hex()
        txBytes = base64.b64decode(bcsTxBytes)
        signatuure = await self.sign_transaction(txBytes, pk, my_wallet.public_key)
        pub_key = base64.b64encode(my_wallet.public_key).decode()
        LOGGER.debug(f"signatuure: {base64.b64encode(signatuure).decode()}")
        LOGGER.debug(f"pub_key: {pub_key}")
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sui_executeTransactionBlock",
            "params": [
                bcsTxBytes,
                [signatuure]
            ]
        }
        response = await asyncio.to_thread(requests.post, self.url, json=payload)
        LOGGER.debug(response)
        
        if response.status_code == 200:
            result = response.json()
            if 'error' in result:
                raise Exception(f"Error: {result['error']}")
            res = result["result"]
            LOGGER.debug(pprint.pprint(res, indent=4))
            return TransactionResponseData(**res)
        else:
            response.raise_for_status()

SUI = SUIRequests()

"""
sui keytool sign --address <SUI-ADDRESS> --data <TX_BYTES>

Ed25519 Pure: 0x00
ECDSA Secp256k1: 0x01
ECDSA Secp256r1: 0x02
Multisig: 0x03
zkLogin: 0x05

import { Secp256k1Keypair } from '@mysten/sui/keypairs/secp256k1';
import { Transaction } from '@mysten/sui/transactions';

// Assuming you have the serialized transaction bytes
const txBytes = ...; // Your serialized transaction bytes

// Create a keypair
const keypair = new Secp256k1Keypair();

// Get the public key
const publicKey = keypair.getPublicKey();

// Hash the transaction data
const digest = hashTransactionData(txBytes); // Implement Blake2b hashing

// Sign the digest
const signature = keypair.sign(digest);

// Concatenate flag, signature, and public key
const flag = Buffer.from([0x01]);
const serializedSignature = Buffer.concat([flag, signature, publicKey]);
"""