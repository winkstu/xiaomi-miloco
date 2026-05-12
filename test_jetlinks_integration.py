#!/usr/bin/env python3
"""
Test script to verify JetLinks integration is working correctly
"""

import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "miloco_server"))
sys.path.insert(0, str(project_root / "jetlinks_kit"))
sys.path.insert(0, str(project_root / "miot_kit"))

print("Testing JetLinks integration...")

# Test 1: Import JetLinks client
print("\n1. Testing JetLinks client import...")
try:
    from jetlinks import JetLinksClient, JetLinksError
    from jetlinks.types import JetLinksDeviceInfo, JetLinksSceneInfo
    print("   ✓ JetLinks client imported successfully")
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Import JetLinks MCP
print("\n2. Testing JetLinks MCP import...")
try:
    from jetlinks import JetLinksMcp, JetLinksMcpInterface
    print("   ✓ JetLinks MCP imported successfully")
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Import JetLinks proxy
print("\n3. Testing JetLinks proxy import...")
try:
    from miloco_server.proxy.jetlinks_proxy import JetLinksProxy
    print("   ✓ JetLinks proxy imported successfully")
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Test schema updates
print("\n4. Testing schema updates...")
try:
    from miloco_server.schema.mcp_schema import LocalMcpClientId
    if hasattr(LocalMcpClientId, "JETLINKS"):
        print("   ✓ JETLINKS Client ID exists in schema")
    else:
        print("   ✗ JETLINKS Client ID missing from schema")
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 5: Test dao updates
print("\n5. Testing DAO updates...")
try:
    from miloco_server.dao.kv_dao import DeviceInfoKeys
    if hasattr(DeviceInfoKeys, "JETLINKS_DEVICE_INFO_KEY") and hasattr(DeviceInfoKeys, "JETLINKS_SCENE_INFO_KEY"):
        print("   ✓ JETLINKS device info keys exist in KV DAO")
    else:
        print("   ✗ JETLINKS device info keys missing from KV DAO")
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 6: Test manager update
print("\n6. Testing Manager updates...")
try:
    from miloco_server.service.manager import get_manager
    manager = get_manager()
    if hasattr(manager, "jetlinks_proxy"):
        print("   ✓ Manager has jetlinks_proxy property")
    else:
        print("   ✗ Manager is missing jetlinks_proxy property")
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n✅ All integration tests completed!")
