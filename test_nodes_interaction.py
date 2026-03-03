#!/usr/bin/env python3
"""
Comprehensive test script for Coinami nodes interaction.
Tests include: peers, transactions, mining, and synchronization.
"""

import httpx
import time
from src.crypto.wallet import Wallet
from src.core.transaction import Transaction


# Node endpoints
NODES = {
    "A": "http://localhost:5000",
    "B": "http://localhost:5001",
    "C": "http://localhost:5002",
}


def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_subsection(title):
    """Print a formatted subsection header."""
    print(f"\n{title}")
    print("-" * 40)


def get_node_info(node_name: str) -> dict:
    """Get chain and state info from a node."""
    try:
        chain_resp = httpx.get(f"{NODES[node_name]}/chain")
        mempool_resp = httpx.get(f"{NODES[node_name]}/mempool")
        state_resp = httpx.get(f"{NODES[node_name]}/state")
        
        chain_data = chain_resp.json()
        mempool_data = mempool_resp.json()
        state_data = state_resp.json()
        
        return {
            "chain_length": chain_data["length"],
            "mempool_size": mempool_data["length"],
            "balances": state_data["balances"],
        }
    except Exception as e:
        print(f"  ❌ Error fetching info from Node {node_name}: {e}")
        return None


def display_node_info(node_name: str):
    """Display current state of a node."""
    info = get_node_info(node_name)
    if info:
        print(f"  Node {node_name}:")
        print(f"    - Chain length: {info['chain_length']}")
        print(f"    - Mempool size: {info['mempool_size']}")
        print(f"    - Balances: {info['balances']}")


# ============================================================================
# TEST 1: Basic Node Status
# ============================================================================
def test_node_status():
    """Check that all nodes are running and have genesis block."""
    print_section("TEST 1: Node Status Check")
    
    for node_name in ["A", "B", "C"]:
        try:
            resp = httpx.get(f"{NODES[node_name]}/chain")
            data = resp.json()
            if data["length"] == 1:
                print(f"  ✓ Node {node_name}: Running with genesis block")
            else:
                print(f"  ⚠ Node {node_name}: Has {data['length']} blocks")
        except Exception as e:
            print(f"  ❌ Node {node_name}: Not reachable - {e}")


# ============================================================================
# TEST 2: Peer Registration
# ============================================================================
def test_peer_registration():
    """Register nodes as peers of each other."""
    print_section("TEST 2: Peer Registration")
    
    # Node A connects to B and C
    print_subsection("Registering peers on Node A")
    try:
        resp = httpx.post(
            f"{NODES['A']}/peers",
            json={"peers": [NODES['B'], NODES['C']]}
        )
        data = resp.json()
        print(f"  ✓ Node A added peers: {data['added']}")
        print(f"    Total peers on A: {data['total']}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    # Node B connects to A and C
    print_subsection("Registering peers on Node B")
    try:
        resp = httpx.post(
            f"{NODES['B']}/peers",
            json={"peers": [NODES['A'], NODES['C']]}
        )
        data = resp.json()
        print(f"  ✓ Node B added peers: {data['added']}")
        print(f"    Total peers on B: {data['total']}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    # Node C connects to A and B
    print_subsection("Registering peers on Node C")
    try:
        resp = httpx.post(
            f"{NODES['C']}/peers",
            json={"peers": [NODES['A'], NODES['B']]}
        )
        data = resp.json()
        print(f"  ✓ Node C added peers: {data['added']}")
        print(f"    Total peers on C: {data['total']}")
    except Exception as e:
        print(f"  ❌ Error: {e}")


# ============================================================================
# TEST 3: Transaction Broadcasting
# ============================================================================
def test_transaction_broadcast():
    """Create and broadcast transactions."""
    print_section("TEST 3: Transaction Broadcasting")
    
    wallet1 = Wallet()
    wallet2 = Wallet()
    
    print(f"  Created Wallet 1: {wallet1.address}")
    print(f"  Created Wallet 2: {wallet2.address}")
    
    # Create a transaction
    print_subsection("Creating transaction")
    tx = Transaction(
        type_tx="transfer",
        sender_address=wallet1.address,
        receiver_address=wallet2.address,
        amount=10.0,
        nonce=1,
        payload={"public_key": wallet1.public_key_bytes.hex()},
    )
    tx.signature = wallet1.sign_tx(tx)
    print(f"  ✓ Transaction created: {tx.calculate_hash()}")
    
    # Submit to Node A
    print_subsection("Submitting to Node A")
    try:
        resp = httpx.post(
            f"{NODES['A']}/tx",
            json=tx.to_network_dict()
        )
        print(f"  ✓ Status: {resp.json()['status']}")
        print(f"    Hash: {resp.json()['hash']}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    # Wait a bit for broadcast
    print("\n  Waiting 2 seconds for broadcast...")
    time.sleep(2)
    
    # Check mempools
    print_subsection("Mempool status after broadcast")
    for node_name in ["A", "B", "C"]:
        try:
            resp = httpx.get(f"{NODES[node_name]}/mempool")
            data = resp.json()
            print(f"  Node {node_name}: {data['length']} transaction(s)")
        except Exception as e:
            print(f"  ❌ Node {node_name}: Error - {e}")


# ============================================================================
# TEST 4: Mining and Block Propagation
# ============================================================================
def test_mining():
    """Mine a block on one node and verify propagation."""
    print_section("TEST 4: Mining and Block Propagation")
    
    # First, add a transaction if mempool is empty
    print_subsection("Checking Node A mempool")
    try:
        resp = httpx.get(f"{NODES['A']}/mempool")
        data = resp.json()
        print(f"  Current mempool size: {data['length']}")
        
        if data['length'] == 0:
            print("\n  Adding transaction to mempool...")
            wallet = Wallet()
            tx = Transaction(
                type_tx="transfer",
                sender_address=wallet.address,
                receiver_address="ab" * 20,
                amount=5.0,
                nonce=1,
                payload={"public_key": wallet.public_key_bytes.hex()},
            )
            tx.signature = wallet.sign_tx(tx)
            httpx.post(f"{NODES['A']}/tx", json=tx.to_network_dict())
            time.sleep(1)
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return
    
    # Mine on Node A
    print_subsection("Mining on Node A")
    try:
        resp = httpx.get(f"{NODES['A']}/mine")
        data = resp.json()
        print(f"  ✓ Block mined: {data['hash']}")
        print(f"    Status: {data['status']}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    # Wait for propagation
    print("\n  Waiting 2 seconds for block propagation...")
    time.sleep(2)
    
    # Check chain lengths
    print_subsection("Chain status after mining")
    for node_name in ["A", "B", "C"]:
        display_node_info(node_name)


# ============================================================================
# TEST 5: Chain Synchronization
# ============================================================================
def test_synchronization():
    """Test chain synchronization between nodes."""
    print_section("TEST 5: Chain Synchronization")
    
    print_subsection("Chain status before sync")
    for node_name in ["A", "B", "C"]:
        display_node_info(node_name)
    
    # Manually trigger sync on isolated nodes
    print_subsection("Triggering sync on Node B and C")
    for node_name in ["B", "C"]:
        try:
            resp = httpx.post(f"{NODES[node_name]}/sync")
            data = resp.json()
            print(f"  ✓ Node {node_name}: {data['status']}, chain length: {data['length']}")
        except Exception as e:
            print(f"  ❌ Node {node_name}: Error - {e}")
    
    # Wait a bit
    time.sleep(1)
    
    print_subsection("Chain status after sync")
    for node_name in ["A", "B", "C"]:
        display_node_info(node_name)


# ============================================================================
# TEST 6: Full Workflow
# ============================================================================
def test_full_workflow():
    """Run a complete workflow: tx -> broadcast -> mine -> sync."""
    print_section("TEST 6: Full Workflow")
    
    print_subsection("Step 1: Create and broadcast transactions")
    wallet1 = Wallet()
    wallet2 = Wallet()
    
    for i in range(2):
        tx = Transaction(
            type_tx="transfer",
            sender_address=wallet1.address,
            receiver_address=wallet2.address,
            amount=5.0 + i,
            nonce=2 + i,
            payload={"public_key": wallet1.public_key_bytes.hex()},
        )
        tx.signature = wallet1.sign_tx(tx)
        try:
            httpx.post(f"{NODES['A']}/tx", json=tx.to_network_dict())
            print(f"  ✓ Transaction {i+1} submitted")
        except Exception as e:
            print(f"  ❌ Error submitting tx {i+1}: {e}")
    
    time.sleep(1)
    
    print_subsection("Step 2: Mine block on Node A")
    try:
        resp = httpx.get(f"{NODES['A']}/mine")
        data = resp.json()
        print(f"  ✓ Block mined with hash: {data['hash']}")
    except Exception as e:
        print(f"  ❌ Error mining: {e}")
    
    time.sleep(2)
    
    print_subsection("Step 3: Sync other nodes")
    for node_name in ["B", "C"]:
        try:
            resp = httpx.post(f"{NODES[node_name]}/sync")
            data = resp.json()
            print(f"  ✓ Node {node_name}: {data['status']}")
        except Exception as e:
            print(f"  ❌ Node {node_name}: Error - {e}")
    
    time.sleep(1)
    
    print_subsection("Step 4: Final state")
    for node_name in ["A", "B", "C"]:
        display_node_info(node_name)


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    print("\n" + "="*60)
    print("  COINAMI NODES INTERACTION TEST SUITE")
    print("="*60)
    
    # Run all tests
    test_node_status()
    test_peer_registration()
    test_transaction_broadcast()
    test_mining()
    test_synchronization()
    test_full_workflow()
    
    print_section("All Tests Complete")
    print("  ✓ Test suite finished!\n")
