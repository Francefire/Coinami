#!/usr/bin/env python
"""
Start a small network of Coinami nodes.

This script launches multiple nodes on different ports and connects them
as peers to form a functional P2P network.
"""

import subprocess
import time
import httpx
import sys
from typing import List


def start_node(port: int, difficulty: int = 3):
    """Start a node on the specified port."""
    cmd = [
        sys.executable, "-m", "uvicorn",
        "src.p2p.node:app",
        "--host", "0.0.0.0",
        "--port", str(port),
        "--reload"
    ]
    print(f"Starting node on port {port}...")
    return subprocess.Popen(cmd)


def wait_for_node(port: int, max_attempts: int = 10) -> bool:
    """Wait for a node to be ready by checking its /state endpoint."""
    for attempt in range(max_attempts):
        try:
            response = httpx.get(f"http://localhost:{port}/state", timeout=1)
            if response.status_code == 200:
                print(f"✓ Node on port {port} is ready")
                return True
        except Exception:
            pass
        time.sleep(0.5)
    
    print(f"✗ Node on port {port} failed to start")
    return False


def connect_peers(nodes: List[int]) -> None:
    """Connect all nodes as peers with each other."""
    for i, port in enumerate(nodes):
        peer_urls = [f"http://localhost:{p}" for j, p in enumerate(nodes) if i != j]
        if not peer_urls:
            continue
        
        try:
            response = httpx.post(
                f"http://localhost:{port}/peers",
                json={"peers": peer_urls},
                timeout=5
            )
            if response.status_code == 201:
                data = response.json()
                print(f"✓ Node {port}: Connected to {data['total']} peers")
            else:
                print(f"✗ Node {port}: Failed to add peers")
        except Exception as e:
            print(f"✗ Node {port}: Error connecting peers: {e}")


def main():
    """Start a network of 3 nodes on ports 5000, 5001, 5002."""
    nodes_config = [5000, 5001, 5002]
    processes = []
    
    print("=" * 60)
    print("Starting Coinami P2P Network")
    print("=" * 60)
    
    # Start all nodes
    for port in nodes_config:
        process = start_node(port)
        processes.append((port, process))
        time.sleep(1)  # Stagger startup
    
    print("\nWaiting for nodes to initialize...")
    time.sleep(3)  # Give time for all to start
    
    # Wait for all nodes to be ready
    ready_nodes = []
    for port, _ in processes:
        if wait_for_node(port):
            ready_nodes.append(port)
    
    if not ready_nodes:
        print("\n✗ No nodes started successfully!")
        for _, process in processes:
            process.terminate()
        return
    
    print(f"\n✓ {len(ready_nodes)} node(s) started successfully")
    
    # Connect nodes as peers
    print("\nConnecting nodes as peers...")
    time.sleep(1)
    connect_peers(ready_nodes)
    
    print("\n" + "=" * 60)
    print("Network is running!")
    print("=" * 60)
    print(f"\nNodes available at:")
    for port in ready_nodes:
        print(f"  - http://localhost:{port}")
    print("\nAPI Endpoints available:")
    print("  - GET  /state       - View account balances")
    print("  - GET  /chain       - View blockchain")
    print("  - GET  /mempool     - View pending transactions")
    print("  - GET  /peers       - View connected peers")
    print("  - POST /tx          - Submit transaction")
    print("  - POST /peers       - Register peers")
    print("  - GET  /mine        - Mine a block")
    print("  - POST /sync        - Sync with peers")
    print("\nPress Ctrl+C to stop the network...")
    print("=" * 60 + "\n")
    
    try:
        # Keep the script running
        for _, process in processes:
            process.wait()
    except KeyboardInterrupt:
        print("\n\nShutting down network...")
        for port, process in processes:
            print(f"Stopping node on port {port}...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        print("✓ Network stopped")


if __name__ == "__main__":
    main()
