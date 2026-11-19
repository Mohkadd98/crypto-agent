"""
On-chain analysis tools for the Crypto Intelligence Agent.
Tracks wallets, whale transactions, exchange flows, and token holders.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from providers.blockchain import (
    get_blockchain_provider, BlockchainProvider,
    Chain, WalletInfo, TransactionInfo, TokenInfo
)


@dataclass
class ToolResult:
    """Standard tool result format."""
    success: bool
    data: Any
    source: str
    timestamp: datetime
    error: Optional[str] = None
    metadata: Dict = None
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        return result


class OnChainTools:
    """On-chain analysis tools."""
    
    def __init__(self, provider: Optional[BlockchainProvider] = None):
        self.provider = provider
    
    async def _get_provider(self) -> BlockchainProvider:
        if self.provider is None:
            return await get_blockchain_provider()
        return self.provider
    
    async def track_wallet(self, chain: str, address: str, max_txs: int = 1000) -> ToolResult:
        """Analyze a wallet comprehensively."""
        try:
            provider = await self._get_provider()
            chain_enum = Chain(chain.lower())
            
            wallet = await provider.analyze_wallet(chain_enum, address, max_txs)
            
            return ToolResult(
                success=True,
                data={
                    'address': wallet.address,
                    'chain': wallet.chain.value,
                    'balance_native': wallet.balance_native,
                    'balance_usd': wallet.balance_usd,
                    'tx_count': wallet.tx_count,
                    'first_tx_date': wallet.first_tx_date.isoformat() if wallet.first_tx_date else None,
                    'last_tx_date': wallet.last_tx_date.isoformat() if wallet.last_tx_date else None,
                    'labels': wallet.labels,
                    'is_contract': wallet.is_contract
                },
                source=f"{chain_enum.value}_rpc",
                timestamp=datetime.utcnow(),
                metadata={"chain": chain, "max_txs": max_txs}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source=chain,
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def analyze_wallet_history(self, chain: str, address: str, limit: int = 100, include_tokens: bool = True) -> ToolResult:
        """Get transaction history for a wallet."""
        try:
            provider = await self._get_provider()
            chain_enum = Chain(chain.lower())
            
            txs = await provider.get_wallet_transactions(chain_enum, address, limit, include_tokens)
            
            return ToolResult(
                success=True,
                data=[{
                    'hash': tx.hash,
                    'from': tx.from_address,
                    'to': tx.to_address,
                    'value': tx.value,
                    'value_usd': tx.value_usd,
                    'gas_used': tx.gas_used,
                    'gas_price': tx.gas_price,
                    'block_number': tx.block_number,
                    'timestamp': tx.timestamp.isoformat(),
                    'status': tx.status,
                    'token_transfers': tx.token_transfers
                } for tx in txs],
                source=f"{chain_enum.value}_explorer",
                timestamp=datetime.utcnow(),
                metadata={"chain": chain, "address": address, "limit": limit, "count": len(txs)}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source=chain,
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def detect_whale_transactions(self, chain: str, min_value_usd: float = 100000, lookback_blocks: int = 100) -> ToolResult:
        """Detect large whale transactions."""
        try:
            provider = await self._get_provider()
            chain_enum = Chain(chain.lower())
            
            txs = await provider.detect_large_transactions(chain_enum, min_value_usd, lookback_blocks)
            
            return ToolResult(
                success=True,
                data=[{
                    'hash': tx.hash,
                    'from': tx.from_address,
                    'to': tx.to_address,
                    'value': tx.value,
                    'value_usd': tx.value_usd,
                    'gas_used': tx.gas_used,
                    'block_number': tx.block_number,
                    'timestamp': tx.timestamp.isoformat(),
                    'status': tx.status
                } for tx in txs],
                source=f"{chain_enum.value}_rpc",
                timestamp=datetime.utcnow(),
                metadata={"chain": chain, "min_value_usd": min_value_usd, "lookback_blocks": lookback_blocks, "count": len(txs)}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source=chain,
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def analyze_exchange_flows(self, chain: str, exchange_addresses: List[str], lookback_blocks: int = 1000) -> ToolResult:
        """Analyze exchange inflows/outflows."""
        try:
            provider = await self._get_provider()
            chain_enum = Chain(chain.lower())
            w3 = provider._get_web3(chain_enum)
            
            latest_block = await w3.eth.block_number
            start_block = max(0, latest_block - lookback_blocks)
            
            inflows = []
            outflows = []
            
            # This is a simplified version - in production you'd use specialized APIs
            for block_num in range(latest_block, start_block - 1, -1):
                try:
                    block = await w3.eth.get_block(block_num, full_transactions=True)
                    for tx in block.transactions:
                        to_addr = tx.to.lower() if tx.to else ""
                        from_addr = getattr(tx, 'from', '').lower() if getattr(tx, 'from', '') else ""
                        value = w3.from_wei(tx.value, "ether")
                        
                        # Check if to/from exchange
                        for exch_addr in exchange_addresses:
                            exch_lower = exch_addr.lower()
                            if to_addr == exch_lower:
                                inflows.append({
                                    'hash': tx.hash.hex(),
                                    'from': from_addr,
                                    'to': to_addr,
                                    'value': float(value),
                                    'block': block_num,
                                    'timestamp': datetime.fromtimestamp(block.timestamp).isoformat()
                                })
                            elif from_addr == exch_lower:
                                outflows.append({
                                    'hash': tx.hash.hex(),
                                    'from': from_addr,
                                    'to': to_addr,
                                    'value': float(value),
                                    'block': block_num,
                                    'timestamp': datetime.fromtimestamp(block.timestamp).isoformat()
                                })
                except Exception:
                    continue
            
            return ToolResult(
                success=True,
                data={
                    'inflows': inflows[:100],
                    'outflows': outflows[:100],
                    'total_inflow': sum(t['value'] for t in inflows),
                    'total_outflow': sum(t['value'] for t in outflows),
                    'net_flow': sum(t['value'] for t in inflows) - sum(t['value'] for t in outflows),
                    'inflow_count': len(inflows),
                    'outflow_count': len(outflows)
                },
                source=f"{chain_enum.value}_rpc",
                timestamp=datetime.utcnow(),
                metadata={"chain": chain, "exchange_addresses": exchange_addresses, "lookback_blocks": lookback_blocks}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source=chain,
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def identify_wallet_clusters(self, chain: str, addresses: List[str], min_shared_txs: int = 3) -> ToolResult:
        """Identify clusters of wallets that interact frequently."""
        try:
            provider = await self._get_provider()
            chain_enum = Chain(chain.lower())
            
            # Get transactions for each address
            wallet_txs = {}
            for addr in addresses:
                txs = await provider.get_normal_transactions(chain_enum, addr, offset=1000)
                wallet_txs[addr] = set(tx['hash'] for tx in txs)
            
            # Find clusters
            clusters = []
            processed = set()
            
            for i, addr1 in enumerate(addresses):
                if addr1 in processed:
                    continue
                
                cluster = [addr1]
                for addr2 in addresses[i+1:]:
                    if addr2 in processed:
                        continue
                    
                    shared = wallet_txs[addr1].intersection(wallet_txs[addr2])
                    if len(shared) >= min_shared_txs:
                        cluster.append(addr2)
                        processed.add(addr2)
                
                if len(cluster) > 1:
                    clusters.append(cluster)
                processed.add(addr1)
            
            return ToolResult(
                success=True,
                data={
                    'clusters': clusters,
                    'cluster_count': len(clusters),
                    'total_addresses': len(addresses),
                    'clustered_addresses': sum(len(c) for c in clusters)
                },
                source=f"{chain_enum.value}_explorer",
                timestamp=datetime.utcnow(),
                metadata={"chain": chain, "min_shared_txs": min_shared_txs}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source=chain,
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def monitor_token_holders(self, chain: str, token_address: str, limit: int = 100) -> ToolResult:
        """Get top token holders."""
        try:
            provider = await self._get_provider()
            chain_enum = Chain(chain.lower())
            
            holders = await provider.get_token_holders(chain_enum, token_address, limit)
            
            return ToolResult(
                success=True,
                data={
                    'token_address': token_address,
                    'chain': chain_enum.value,
                    'holders': holders,
                    'holder_count': len(holders)
                },
                source=f"{chain_enum.value}_explorer",
                timestamp=datetime.utcnow(),
                metadata={"chain": chain, "token_address": token_address, "limit": limit}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source=chain,
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def get_token_info(self, chain: str, token_address: str) -> ToolResult:
        """Get ERC20 token information."""
        try:
            provider = await self._get_provider()
            chain_enum = Chain(chain.lower())
            
            token = await provider.get_token_info(chain_enum, token_address)
            
            if token is None:
                return ToolResult(
                    success=False,
                    data=None,
                    source=chain,
                    timestamp=datetime.utcnow(),
                    error="Token not found or not ERC20"
                )
            
            return ToolResult(
                success=True,
                data={
                    'address': token.address,
                    'chain': token.chain.value,
                    'symbol': token.symbol,
                    'name': token.name,
                    'decimals': token.decimals,
                    'total_supply': token.total_supply,
                    'holders_count': token.holders_count,
                    'price_usd': token.price_usd,
                    'liquidity_usd': token.liquidity_usd,
                    'is_verified': token.is_verified
                },
                source=f"{chain_enum.value}_rpc",
                timestamp=datetime.utcnow(),
                metadata={"chain": chain, "token_address": token_address}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source=chain,
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def get_wallet_token_balances(self, chain: str, wallet_address: str, token_addresses: List[str]) -> ToolResult:
        """Get multiple token balances for a wallet."""
        try:
            provider = await self._get_provider()
            chain_enum = Chain(chain.lower())
            
            balances = await provider.get_wallet_token_balances(chain_enum, wallet_address, token_addresses)
            
            return ToolResult(
                success=True,
                data={
                    'wallet': wallet_address,
                    'chain': chain_enum.value,
                    'balances': balances
                },
                source=f"{chain_enum.value}_rpc",
                timestamp=datetime.utcnow(),
                metadata={"chain": chain, "wallet": wallet_address, "token_count": len(token_addresses)}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source=chain,
                timestamp=datetime.utcnow(),
                error=str(e)
            )


# Tool function wrappers
async def track_wallet(chain: str, address: str, max_txs: int = 1000) -> Dict:
    tools = OnChainTools()
    result = await tools.track_wallet(chain, address, max_txs)
    return result.to_dict()


async def analyze_wallet_history(chain: str, address: str, limit: int = 100, include_tokens: bool = True) -> Dict:
    tools = OnChainTools()
    result = await tools.analyze_wallet_history(chain, address, limit, include_tokens)
    return result.to_dict()


async def detect_whale_transactions(chain: str, min_value_usd: float = 100000, lookback_blocks: int = 100) -> Dict:
    tools = OnChainTools()
    result = await tools.detect_whale_transactions(chain, min_value_usd, lookback_blocks)
    return result.to_dict()


async def analyze_exchange_flows(chain: str, exchange_addresses: List[str], lookback_blocks: int = 1000) -> Dict:
    tools = OnChainTools()
    result = await tools.analyze_exchange_flows(chain, exchange_addresses, lookback_blocks)
    return result.to_dict()


async def identify_wallet_clusters(chain: str, addresses: List[str], min_shared_txs: int = 3) -> Dict:
    tools = OnChainTools()
    result = await tools.identify_wallet_clusters(chain, addresses, min_shared_txs)
    return result.to_dict()


async def monitor_token_holders(chain: str, token_address: str, limit: int = 100) -> Dict:
    tools = OnChainTools()
    result = await tools.monitor_token_holders(chain, token_address, limit)
    return result.to_dict()


async def get_token_info(chain: str, token_address: str) -> Dict:
    tools = OnChainTools()
    result = await tools.get_token_info(chain, token_address)
    return result.to_dict()


async def get_wallet_token_balances(chain: str, wallet_address: str, token_addresses: List[str]) -> Dict:
    tools = OnChainTools()
    result = await tools.get_wallet_token_balances(chain, wallet_address, token_addresses)
    return result.to_dict()


# Tool definitions for AI function calling
ONCHAIN_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "track_wallet",
            "description": "Comprehensive wallet analysis including balance, transaction count, labels",
            "parameters": {
                "type": "object",
                "properties": {
                    "chain": {"type": "string", "description": "Blockchain (ethereum, bsc, polygon, arbitrum, optimism, base, avalanche)"},
                    "address": {"type": "string", "description": "Wallet address"},
                    "max_txs": {"type": "integer", "default": 1000}
                },
                "required": ["chain", "address"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_wallet_history",
            "description": "Get transaction history for a wallet",
            "parameters": {
                "type": "object",
                "properties": {
                    "chain": {"type": "string", "description": "Blockchain"},
                    "address": {"type": "string", "description": "Wallet address"},
                    "limit": {"type": "integer", "default": 100},
                    "include_tokens": {"type": "boolean", "default": True}
                },
                "required": ["chain", "address"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "detect_whale_transactions",
            "description": "Detect large whale transactions in recent blocks",
            "parameters": {
                "type": "object",
                "properties": {
                    "chain": {"type": "string", "description": "Blockchain"},
                    "min_value_usd": {"type": "number", "default": 100000},
                    "lookback_blocks": {"type": "integer", "default": 100}
                },
                "required": ["chain"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_exchange_flows",
            "description": "Analyze exchange inflows and outflows",
            "parameters": {
                "type": "object",
                "properties": {
                    "chain": {"type": "string", "description": "Blockchain"},
                    "exchange_addresses": {"type": "array", "items": {"type": "string"}, "description": "List of exchange wallet addresses"},
                    "lookback_blocks": {"type": "integer", "default": 1000}
                },
                "required": ["chain", "exchange_addresses"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "identify_wallet_clusters",
            "description": "Identify clusters of wallets that interact frequently",
            "parameters": {
                "type": "object",
                "properties": {
                    "chain": {"type": "string", "description": "Blockchain"},
                    "addresses": {"type": "array", "items": {"type": "string"}, "description": "List of wallet addresses to analyze"},
                    "min_shared_txs": {"type": "integer", "default": 3}
                },
                "required": ["chain", "addresses"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "monitor_token_holders",
            "description": "Get top token holders",
            "parameters": {
                "type": "object",
                "properties": {
                    "chain": {"type": "string", "description": "Blockchain"},
                    "token_address": {"type": "string", "description": "Token contract address"},
                    "limit": {"type": "integer", "default": 100}
                },
                "required": ["chain", "token_address"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_token_info",
            "description": "Get ERC20 token information",
            "parameters": {
                "type": "object",
                "properties": {
                    "chain": {"type": "string", "description": "Blockchain"},
                    "token_address": {"type": "string", "description": "Token contract address"}
                },
                "required": ["chain", "token_address"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_wallet_token_balances",
            "description": "Get multiple token balances for a wallet",
            "parameters": {
                "type": "object",
                "properties": {
                    "chain": {"type": "string", "description": "Blockchain"},
                    "wallet_address": {"type": "string", "description": "Wallet address"},
                    "token_addresses": {"type": "array", "items": {"type": "string"}, "description": "List of token contract addresses"}
                },
                "required": ["chain", "wallet_address", "token_addresses"]
            }
        }
    }
]