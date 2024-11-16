import pprint
from typing import List
import base64
import asyncio
import requests

from src.apps.accounts.models import User
from src.apps.accounts.schemas import Coin, CoinBalance, MetaData, SuiTransferResponse, TransactionResponseData
from src.config.settings import Config
from src.utils.logger import LOGGER
from sui_python_sdk.wallet import SuiWallet


class SUIRequests:
    def __init__(self, url: str = Config.SUI_RPC) -> None:
        self.url = url
        self.decimals = 10**9
        
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

    async def paySui(self, address: str, recipient: str, amount: int, gas_budget: int, coinId: str):
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
            
    async def executeTransaction(self, bcsTxBytes: str, phrase: str):
        # NOTE WORK ON THIS TO DETERMINE THE SIGNER
        my_wallet = SuiWallet(mnemonic=phrase)
        signer = my_wallet.full_private_key
        LOGGER.debug(signer)
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sui_executeTransactionBlock",
            "params": [
                str(bcsTxBytes),
                ["0"]
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


