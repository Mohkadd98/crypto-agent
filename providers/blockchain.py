"""
Blockchain provider for the Crypto Intelligence Agent.
Supports Ethereum, BSC, Polygon, Arbitrum, Solana via RPC and block explorers.
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache

import httpx
from web3 import AsyncWeb3
from web3.types import BlockData, TxData, TxReceipt, LogReceipt
from web3.exceptions import Web3Exception

from core.config import get_settings, BlockchainSettings


class Chain(str, Enum):
    ETHEREUM = "ethereum"
    BSC = "bsc"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    BASE = "base"
    AVALANCHE = "avalanche"
    SOLANA = "solana"


@dataclass
class ChainConfig:
    chain_id: int
    rpc_url: str
    fallback_rpcs: List[str]
    explorer_api_url: str
    explorer_api_key: str
    native_token: str
    block_time: float  # seconds


@dataclass
class WalletInfo:
    address: str
    chain: Chain
    balance_native: float
    balance_usd: Optional[float] = None
    token_balances: List[Dict] = field(default_factory=list)
    tx_count: int = 0
    first_tx_date: Optional[datetime] = None
    last_tx_date: Optional[datetime] = None
    labels: List[str] = field(default_factory=list)
    is_contract: bool = False


@dataclass
class TransactionInfo:
    hash: str
    chain: Chain
    from_address: str
    to_address: Optional[str]
    value: float  # in native token
    gas_used: int
    gas_price: int
    block_number: int
    timestamp: datetime
    status: bool  # True = success
    value_usd: Optional[float] = None
    token_transfers: List[Dict] = field(default_factory=list)
    logs: List[Dict] = field(default_factory=list)


@dataclass
class TokenInfo:
    address: str
    chain: Chain
    symbol: str
    name: str
    decimals: int
    total_supply: Optional[float] = None
    holders_count: Optional[int] = None
    price_usd: Optional[float] = None
    liquidity_usd: Optional[float] = None
    is_verified: bool = False


class BlockchainError(Exception):
    """Base exception for blockchain errors."""
    pass


class RPCError(BlockchainError):
    """RPC connection error."""
    pass


class ExplorerError(BlockchainError):
    """Block explorer API error."""
    pass


class BlockchainProvider:
    """Unified blockchain provider with multi-chain support."""
    
    # Chain configurations
    CHAIN_CONFIGS = {
        Chain.ETHEREUM: ChainConfig(
            chain_id=1,
            rpc_url="",
            fallback_rpcs=[],
            explorer_api_url="https://api.etherscan.io/api",
            explorer_api_key="",
            native_token="ETH",
            block_time=12.0
        ),
        Chain.BSC: ChainConfig(
            chain_id=56,
            rpc_url="",
            fallback_rpcs=[],
            explorer_api_url="https://api.bscscan.com/api",
            explorer_api_key="",
            native_token="BNB",
            block_time=3.0
        ),
        Chain.POLYGON: ChainConfig(
            chain_id=137,
            rpc_url="",
            fallback_rpcs=[],
            explorer_api_url="https://api.polygonscan.com/api",
            explorer_api_key="",
            native_token="MATIC",
            block_time=2.0
        ),
        Chain.ARBITRUM: ChainConfig(
            chain_id=42161,
            rpc_url="",
            fallback_rpcs=[],
            explorer_api_url="https://api.arbiscan.io/api",
            explorer_api_key="",
            native_token="ETH",
            block_time=0.25
        ),
        Chain.OPTIMISM: ChainConfig(
            chain_id=10,
            rpc_url="",
            fallback_rpcs=[],
            explorer_api_url="https://api-optimistic.etherscan.io/api",
            explorer_api_key="",
            native_token="ETH",
            block_time=2.0
        ),
        Chain.BASE: ChainConfig(
            chain_id=8453,
            rpc_url="",
            fallback_rpcs=[],
            explorer_api_url="https://api.basescan.org/api",
            explorer_api_key="",
            native_token="ETH",
            block_time=2.0
        ),
        Chain.AVALANCHE: ChainConfig(
            chain_id=43114,
            rpc_url="",
            fallback_rpcs=[],
            explorer_api_url="https://api.snowtrace.io/api",
            explorer_api_key="",
            native_token="AVAX",
            block_time=2.0
        ),
    }
    
    # ERC20 ABI for token interactions
    ERC20_ABI = [
        {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
        {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
        {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
        {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
        {"constant": True, "inputs": [], "name": "totalSupply", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
        {"anonymous": False, "inputs": [{"indexed": True, "name": "from", "type": "address"}, {"indexed": True, "name": "to", "type": "address"}, {"indexed": False, "name": "value", "type": "uint256"}], "name": "Transfer", "type": "event"}
    ]
    
    def __init__(self, settings: Optional[BlockchainSettings] = None):
        self.settings = settings or get_settings().blockchain
        self._web3_clients: Dict[Chain, AsyncWeb3] = {}
        self._http_client: Optional[httpx.AsyncClient] = None
        self._chain_configs: Dict[Chain, ChainConfig] = {}
        self._initialized = False
    
    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
        return self._http_client
    
    async def initialize(self) -> None:
        """Initialize RPC connections and chain configs."""
        if self._initialized:
            return
        
        # Load chain configs from settings
        chain_mapping = {
            Chain.ETHEREUM: self.settings.ethereum,
            Chain.BSC: self.settings.bsc,
            Chain.POLYGON: self.settings.polygon,
            Chain.ARBITRUM: self.settings.arbitrum,
            Chain.OPTIMISM: self.settings.optimism,
            Chain.BASE: self.settings.base,
            Chain.AVALANCHE: self.settings.avalanche,
            Chain.SOLANA: self.settings.solana,
        }
        
        for chain, config in chain_mapping.items():
            if chain in self.CHAIN_CONFIGS:
                chain_config = self.CHAIN_CONFIGS[chain]
                chain_config.rpc_url = config.rpc_url
                chain_config.fallback_rpcs = config.fallback_rpcs
                
                # Set explorer API keys from environment
                explorer_keys = {
                    Chain.ETHEREUM: "ETHERSCAN_API_KEY",
                    Chain.BSC: "BSCSCAN_API_KEY",
                    Chain.POLYGON: "POLYGONSCAN_API_KEY",
                    Chain.ARBITRUM: "ARBISCAN_API_KEY",
                    Chain.OPTIMISM: "OPTIMISTIC_ETHERSCAN_API_KEY",
                    Chain.BASE: "BASESCAN_API_KEY",
                    Chain.AVALANCHE: "SNOWTRACE_API_KEY",
                }
                if chain in explorer_keys:
                    from core.config import get_env
                    chain_config.explorer_api_key = get_env(explorer_keys[chain], "")
                
                self._chain_configs[chain] = chain_config

        async def _connect(chain: Chain, chain_config) -> None:
            """Try the primary RPC then fallbacks, with a short timeout each."""
            candidates = [u for u in [chain_config.rpc_url, *chain_config.fallback_rpcs] if u]
            for url in candidates:
                try:
                    w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(url))
                    await asyncio.wait_for(w3.eth.chain_id, timeout=2.0)
                    self._web3_clients[chain] = w3
                    return
                except Exception:
                    continue

        # Chains are independent: connect them concurrently so a dead endpoint
        # cannot delay startup for the whole roster.
        await asyncio.gather(
            *[_connect(chain, cfg) for chain, cfg in self._chain_configs.items()],
            return_exceptions=True,
        )

        self._initialized = True
    
    async def close(self) -> None:
        """Close all connections."""
        for w3 in self._web3_clients.values():
            await w3.provider.disconnect()
        self._web3_clients.clear()
        
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
    
    def _get_web3(self, chain: Chain) -> AsyncWeb3:
        """Get Web3 client for a chain."""
        if chain not in self._web3_clients:
            raise RPCError(f"No RPC connection for {chain.value}")
        return self._web3_clients[chain]
    
    def _get_chain_config(self, chain: Chain) -> ChainConfig:
        """Get chain configuration."""
        if chain not in self._chain_configs:
            raise BlockchainError(f"Chain {chain.value} not configured")
        return self._chain_configs[chain]
    
    # ===========================================
    # Basic RPC Methods
    # ===========================================
    
    async def get_latest_block(self, chain: Chain) -> BlockData:
        """Get latest block."""
        await self.initialize()
        w3 = self._get_web3(chain)
        return await w3.eth.get_block("latest")
    
    async def get_block(self, chain: Chain, block_number: Union[int, str]) -> BlockData:
        """Get block by number."""
        await self.initialize()
        w3 = self._get_web3(chain)
        return await w3.eth.get_block(block_number)
    
    async def get_block_number(self, chain: Chain) -> int:
        """Get latest block number."""
        await self.initialize()
        w3 = self._get_web3(chain)
        return await w3.eth.block_number
    
    async def get_balance(self, chain: Chain, address: str, block: Union[int, str] = "latest") -> float:
        """Get native token balance."""
        await self.initialize()
        w3 = self._get_web3(chain)
        balance_wei = await w3.eth.get_balance(w3.to_checksum_address(address), block)
        return w3.from_wei(balance_wei, "ether")
    
    async def get_transaction(self, chain: Chain, tx_hash: str) -> Optional[TxData]:
        """Get transaction by hash."""
        await self.initialize()
        w3 = self._get_web3(chain)
        try:
            return await w3.eth.get_transaction(tx_hash)
        except Exception:
            return None
    
    async def get_transaction_receipt(self, chain: Chain, tx_hash: str) -> Optional[TxReceipt]:
        """Get transaction receipt."""
        await self.initialize()
        w3 = self._get_web3(chain)
        try:
            return await w3.eth.get_transaction_receipt(tx_hash)
        except Exception:
            return None
    
    async def get_code(self, chain: Chain, address: str) -> bytes:
        """Get contract code at address."""
        await self.initialize()
        w3 = self._get_web3(chain)
        return await w3.eth.get_code(w3.to_checksum_address(address))
    
    async def get_gas_price(self, chain: Chain) -> Dict:
        """Get current gas price information for a chain."""
        await self.initialize()
        w3 = self._get_web3(chain)
        try:
            gas_price_wei = await asyncio.wait_for(w3.eth.gas_price, timeout=10.0)
        except Exception:
            # Some public endpoints allow connections but refuse fee methods;
            # fall through to the other configured endpoints.
            chain_config = self._get_chain_config(chain)
            gas_price_wei = None
            for url in [chain_config.rpc_url, *chain_config.fallback_rpcs]:
                if not url:
                    continue
                try:
                    candidate = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(url))
                    gas_price_wei = await asyncio.wait_for(candidate.eth.gas_price, timeout=8.0)
                    self._web3_clients[chain] = candidate
                    w3 = candidate
                    break
                except Exception:
                    continue
            if gas_price_wei is None:
                raise RPCError(f"Unable to fetch gas price for {chain.value}")
        gas_price_gwei = float(w3.from_wei(gas_price_wei, "gwei"))
        
        result = {
            "chain": chain.value,
            "gas_price_wei": int(gas_price_wei),
            "gas_price_gwei": gas_price_gwei,
            "native_token": self._get_chain_config(chain).native_token,
        }
        
        # Try EIP-1559 base fee
        try:
            latest = await w3.eth.get_block("latest")
            base_fee = latest.get("baseFeePerGas")
            if base_fee is not None:
                result["base_fee_gwei"] = float(w3.from_wei(base_fee, "gwei"))
                result["priority_fee_gwei"] = max(gas_price_gwei - result["base_fee_gwei"], 0.0)
        except Exception:
            pass
        
        # Rough USD estimates for common tx types (native price not fetched here)
        result["estimated_costs"] = {
            "transfer": gas_price_gwei * 21000 / 1e9,
            "swap": gas_price_gwei * 150000 / 1e9,
            "nft_mint": gas_price_gwei * 200000 / 1e9,
        }
        return result
    
    async def is_contract(self, chain: Chain, address: str) -> bool:
        """Check if address is a contract."""
        code = await self.get_code(chain, address)
        return len(code) > 0
    
    # ===========================================
    # Token Methods (ERC20)
    # ===========================================
    
    async def get_token_info(self, chain: Chain, token_address: str) -> Optional[TokenInfo]:
        """Get ERC20 token info."""
        await self.initialize()
        w3 = self._get_web3(chain)
        
        try:
            contract = w3.eth.contract(
                address=w3.to_checksum_address(token_address),
                abi=self.ERC20_ABI
            )
            
            symbol = await contract.functions.symbol().call()
            name = await contract.functions.name().call()
            decimals = await contract.functions.decimals().call()
            total_supply = await contract.functions.totalSupply().call()
            
            return TokenInfo(
                address=token_address,
                chain=chain,
                symbol=symbol,
                name=name,
                decimals=decimals,
                total_supply=total_supply / (10 ** decimals)
            )
        except Exception:
            return None
    
    async def get_token_balance(self, chain: Chain, token_address: str, wallet_address: str) -> float:
        """Get ERC20 token balance for a wallet."""
        await self.initialize()
        w3 = self._get_web3(chain)
        
        try:
            contract = w3.eth.contract(
                address=w3.to_checksum_address(token_address),
                abi=self.ERC20_ABI
            )
            
            balance = await contract.functions.balanceOf(w3.to_checksum_address(wallet_address)).call()
            decimals = await contract.functions.decimals().call()
            
            return balance / (10 ** decimals)
        except Exception:
            return 0.0
    
    async def get_wallet_token_balances(self, chain: Chain, wallet_address: str, token_addresses: List[str]) -> List[Dict]:
        """Get multiple token balances for a wallet."""
        balances = []
        for token_address in token_addresses:
            balance = await self.get_token_balance(chain, token_address, wallet_address)
            if balance > 0:
                token_info = await self.get_token_info(chain, token_address)
                balances.append({
                    "token_address": token_address,
                    "symbol": token_info.symbol if token_info else "UNKNOWN",
                    "name": token_info.name if token_info else "Unknown Token",
                    "decimals": token_info.decimals if token_info else 18,
                    "balance": balance,
                    "balance_raw": int(balance * (10 ** (token_info.decimals if token_info else 18)))
                })
        return balances
    
    # ===========================================
    # Transaction History via Explorer APIs
    # ===========================================
    
    async def _explorer_request(self, chain: Chain, params: Dict) -> Dict:
        """Make a request to a block explorer API."""
        config = self._get_chain_config(chain)
        client = await self._get_http_client()
        
        params["apikey"] = config.explorer_api_key
        response = await client.get(config.explorer_api_url, params=params)
        
        if response.status_code >= 400:
            raise ExplorerError(f"Explorer API error: {response.status_code}")
        
        data = response.json()
        if data.get("status") == "0" and data.get("message") != "No transactions found":
            raise ExplorerError(f"Explorer error: {data.get('result', 'Unknown error')}")
        
        return data
    
    async def get_normal_transactions(
        self,
        chain: Chain,
        address: str,
        start_block: int = 0,
        end_block: int = 99999999,
        page: int = 1,
        offset: int = 100,
        sort: str = "desc"
    ) -> List[Dict]:
        """Get normal transactions for an address."""
        params = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": start_block,
            "endblock": end_block,
            "page": page,
            "offset": offset,
            "sort": sort
        }
        data = await self._explorer_request(chain, params)
        return data.get("result", [])
    
    async def get_token_transfers(
        self,
        chain: Chain,
        address: str,
        contract_address: Optional[str] = None,
        start_block: int = 0,
        end_block: int = 99999999,
        page: int = 1,
        offset: int = 100,
        sort: str = "desc"
    ) -> List[Dict]:
        """Get ERC20/ERC721 token transfers for an address."""
        params = {
            "module": "account",
            "action": "tokentx" if contract_address else "tokenlist",
            "address": address,
            "startblock": start_block,
            "endblock": end_block,
            "page": page,
            "offset": offset,
            "sort": sort
        }
        if contract_address:
            params["contractaddress"] = contract_address
        
        data = await self._explorer_request(chain, params)
        return data.get("result", [])
    
    async def get_internal_transactions(
        self,
        chain: Chain,
        address: str,
        start_block: int = 0,
        end_block: int = 99999999,
        page: int = 1,
        offset: int = 100,
        sort: str = "desc"
    ) -> List[Dict]:
        """Get internal transactions for an address."""
        params = {
            "module": "account",
            "action": "txlistinternal",
            "address": address,
            "startblock": start_block,
            "endblock": end_block,
            "page": page,
            "offset": offset,
            "sort": sort
        }
        data = await self._explorer_request(chain, params)
        return data.get("result", [])
    
    # ===========================================
    # Wallet Analysis
    # ===========================================
    
    async def analyze_wallet(self, chain: Chain, address: str, max_txs: int = 1000) -> WalletInfo:
        """Comprehensive wallet analysis."""
        await self.initialize()
        
        checksum_address = AsyncWeb3.to_checksum_address(address)
        
        # Get native balance
        balance_native = await self.get_balance(chain, checksum_address)
        
        # Get transaction count
        w3 = self._get_web3(chain)
        tx_count = await w3.eth.get_transaction_count(checksum_address)
        
        # Get transactions via explorer
        txs = await self.get_normal_transactions(chain, checksum_address, offset=min(max_txs, 10000))
        
        first_tx_date = None
        last_tx_date = None
        labels = []
        
        if txs:
            # Sort by timestamp
            txs.sort(key=lambda x: int(x.get("timeStamp", 0)))
            
            if txs:
                first_tx_date = datetime.fromtimestamp(int(txs[0]["timeStamp"]))
                last_tx_date = datetime.fromtimestamp(int(txs[-1]["timeStamp"]))
            
            # Detect patterns
            unique_counterparties = set()
            for tx in txs:
                to_addr = tx.get("to", "").lower()
                from_addr = tx.get("from", "").lower()
                if to_addr and to_addr != checksum_address.lower():
                    unique_counterparties.add(to_addr)
                if from_addr and from_addr != checksum_address.lower():
                    unique_counterparties.add(from_addr)
            
            # Simple labeling
            if len(txs) > 1000:
                labels.append("high_activity")
            if len(unique_counterparties) > 100:
                labels.append("diverse_counterparties")
            if tx_count == len(txs):
                labels.append("fresh_wallet")
        
        is_contract = await self.is_contract(chain, checksum_address)
        if is_contract:
            labels.append("contract")
        
        return WalletInfo(
            address=checksum_address,
            chain=chain,
            balance_native=balance_native,
            tx_count=tx_count,
            first_tx_date=first_tx_date,
            last_tx_date=last_tx_date,
            labels=labels,
            is_contract=is_contract
        )
    
    async def get_wallet_transactions(
        self,
        chain: Chain,
        address: str,
        limit: int = 100,
        include_tokens: bool = True
    ) -> List[TransactionInfo]:
        """Get formatted transaction history for a wallet."""
        await self.initialize()
        
        checksum_address = AsyncWeb3.to_checksum_address(address)
        txs = await self.get_normal_transactions(chain, checksum_address, offset=limit)
        
        transactions = []
        for tx in txs[:limit]:
            receipt = await self.get_transaction_receipt(chain, tx["hash"])
            
            # Get token transfers for this transaction
            token_transfers = []
            if include_tokens and receipt:
                token_txs = await self.get_token_transfers(chain, checksum_address, start_block=int(tx["blockNumber"]), end_block=int(tx["blockNumber"]), offset=50)
                for ttx in token_txs:
                    if ttx["hash"] == tx["hash"]:
                        token_transfers.append({
                            "token_address": ttx.get("contractAddress"),
                            "token_symbol": ttx.get("tokenSymbol"),
                            "token_name": ttx.get("tokenName"),
                            "from": ttx.get("from"),
                            "to": ttx.get("to"),
                            "value": int(ttx.get("value", 0)) / (10 ** int(ttx.get("tokenDecimal", 18))),
                            "decimals": int(ttx.get("tokenDecimal", 18))
                        })
            
            transactions.append(TransactionInfo(
                hash=tx["hash"],
                chain=chain,
                from_address=tx.get("from", ""),
                to_address=tx.get("to"),
                value=int(tx.get("value", 0)) / 1e18,
                gas_used=int(tx.get("gasUsed", 0)) if tx.get("gasUsed") else int(tx.get("gas", 0)),
                gas_price=int(tx.get("gasPrice", 0)),
                block_number=int(tx.get("blockNumber", 0)),
                timestamp=datetime.fromtimestamp(int(tx.get("timeStamp", 0))),
                status=receipt.get("status", 1) == 1 if receipt else True,
                token_transfers=token_transfers
            ))
        
        return transactions
    
    # ===========================================
    # Whale Tracking
    # ===========================================
    
    async def detect_large_transactions(
        self,
        chain: Chain,
        min_value_usd: float = 100000,
        lookback_blocks: int = 100
    ) -> List[TransactionInfo]:
        """Detect large transactions in recent blocks."""
        await self.initialize()
        
        w3 = self._get_web3(chain)
        latest_block = await w3.eth.block_number
        start_block = max(0, latest_block - lookback_blocks)
        
        large_txs = []
        
        # This is a simplified version - in production you'd use specialized APIs
        # or indexers like Alchemy, QuickNode, or The Graph
        for block_num in range(latest_block, start_block - 1, -1):
            try:
                block = await w3.eth.get_block(block_num, full_transactions=True)
                for tx in block.transactions:
                    value_eth = w3.from_wei(tx.value, "ether")
                    # Would need price feed to convert to USD
                    # For now, use a rough threshold
                    if value_eth > 100:  # > 100 ETH
                        receipt = await w3.eth.get_transaction_receipt(tx.hash.hex())
                        large_txs.append(TransactionInfo(
                            hash=tx.hash.hex(),
                            chain=chain,
                            from_address=tx["from"],
                            to_address=tx["to"],
                            value=float(value_eth),
                            gas_used=receipt.gasUsed if receipt else 0,
                            gas_price=int(tx.gasPrice) if tx.gasPrice else 0,
                            block_number=block_num,
                            timestamp=datetime.fromtimestamp(block.timestamp),
                            status=receipt.status == 1 if receipt else True
                        ))
            except Exception:
                continue
        
        return large_txs
    
    async def get_token_holders(
        self,
        chain: Chain,
        token_address: str,
        limit: int = 100
    ) -> List[Dict]:
        """Get top token holders (requires explorer API with token holder endpoint)."""
        # This varies by explorer - simplified implementation
        config = self._get_chain_config(chain)
        client = await self._get_http_client()
        
        # Etherscan-style token holder endpoint
        params = {
            "module": "token",
            "action": "tokenholderlist",
            "contractaddress": token_address,
            "page": 1,
            "offset": limit,
            "apikey": config.explorer_api_key
        }
        
        try:
            response = await client.get(config.explorer_api_url, params=params)
            data = response.json()
            return data.get("result", [])
        except Exception:
            return []


# Global provider instance
_blockchain_provider: Optional[BlockchainProvider] = None


async def get_blockchain_provider() -> BlockchainProvider:
    """Get the global blockchain provider instance."""
    global _blockchain_provider
    if _blockchain_provider is None:
        _blockchain_provider = BlockchainProvider()
        await _blockchain_provider.initialize()
    return _blockchain_provider


async def close_blockchain_provider() -> None:
    """Close the global blockchain provider."""
    global _blockchain_provider
    if _blockchain_provider:
        await _blockchain_provider.close()
        _blockchain_provider = None