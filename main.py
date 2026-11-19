#!/usr/bin/env python3
"""
Crypto Intelligence Agent - Main Entry Point
Autonomous AI Agent for Cryptocurrency Research and Market Intelligence
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.agent import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)