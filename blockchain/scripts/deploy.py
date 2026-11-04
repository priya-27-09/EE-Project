import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv, set_key

# Set up project base path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

from web3 import Web3
import solcx


def compile_contract(contract_path: Path) -> dict:
    """Compile Solidity contract using solcx and return abi & bytecode."""
    solcx.install_solc("0.8.20")
    solcx.set_solc_version("0.8.20")

    # Read source directly
    with open(contract_path, "r", encoding="utf-8") as f:
        source = f.read()

    compiled = solcx.compile_source(
        source,
        output_values=["abi", "bin"],
        solc_version="0.8.20",
    )

    contract_key = "<stdin>:CivicGuardianAudit"
    if contract_key not in compiled:
        for k in compiled:
            if "CivicGuardianAudit" in k:
                contract_key = k
                break

    data = compiled[contract_key]
    abi = data["abi"]
    bytecode = data["bin"]

    # Export ABI artifact
    abi_dir = BASE_DIR / "blockchain" / "abi"
    abi_dir.mkdir(parents=True, exist_ok=True)
    out_file = abi_dir / "CivicGuardianAudit.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"abi": abi, "bytecode": bytecode}, f, indent=2)

    print(f"[OK] Compiled CivicGuardianAudit.sol -> {out_file}")
    return {"abi": abi, "bytecode": bytecode}


def deploy():
    """Deploy CivicGuardianAudit contract to local Ganache network."""
    rpc_url = os.getenv("BLOCKCHAIN_RPC_URL", "http://127.0.0.1:7545")
    print(f"Connecting to Ethereum node at {rpc_url}...")

    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 15}))
    if not w3.is_connected():
        print(f"[ERROR] Cannot connect to Ganache RPC at {rpc_url}.")
        print("Please start Ganache on port 7545 before running deployment.")
        sys.exit(1)

    chain_id = w3.eth.chain_id
    print(f"[OK] Connected to network. Chain ID: {chain_id}")

    # Compile contract
    contract_path = BASE_DIR / "blockchain" / "contracts" / "CivicGuardianAudit.sol"
    if not contract_path.exists():
        print(f"[ERROR] Contract file not found: {contract_path}")
        sys.exit(1)

    contract_data = compile_contract(contract_path)
    abi = contract_data["abi"]
    bytecode = contract_data["bytecode"]

    # Select deployer account
    private_key = os.getenv("BLOCKCHAIN_PRIVATE_KEY", "").strip()
    account_address = os.getenv("BLOCKCHAIN_ACCOUNT_ADDRESS", "").strip()

    if private_key:
        account = w3.eth.account.from_key(private_key)
        deployer_address = account.address
        print(f"Deploying with private key account: {deployer_address}")
    else:
        accounts = w3.eth.accounts
        if not accounts:
            print("[ERROR] No unlocked accounts found on Ganache node.")
            sys.exit(1)
        deployer_address = accounts[0]
        print(f"Deploying with unlocked node account: {deployer_address}")

    balance = w3.eth.get_balance(deployer_address)
    print(f"Account Balance: {w3.from_wei(balance, 'ether')} ETH")

    # Deploy contract
    ContractFactory = w3.eth.contract(abi=abi, bytecode=bytecode)

    if private_key:
        account = w3.eth.account.from_key(private_key)
        nonce = w3.eth.get_transaction_count(deployer_address)
        tx = ContractFactory.constructor().build_transaction({
            "from": deployer_address,
            "nonce": nonce,
            "chainId": chain_id,
            "gas": 3000000,
            "gasPrice": w3.eth.gas_price,
        })
        signed_tx = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    else:
        tx_hash = ContractFactory.constructor().transact({
            "from": deployer_address,
            "gas": 3000000,
        })

    print(f"Deployment transaction broadcast: {tx_hash.hex()}")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

    if receipt.status != 1:
        print("[ERROR] Contract deployment failed (reverted on-chain).")
        sys.exit(1)

    contract_address = receipt.contractAddress
    print(f"[SUCCESS] CivicGuardianAudit deployed at: {contract_address}")
    print(f"Block Number: {receipt.blockNumber}")
    print(f"Gas Used: {receipt.gasUsed}")

    # Verify contract
    deployed_contract = w3.eth.contract(address=contract_address, abi=abi)
    owner = deployed_contract.functions.owner().call()
    authorized_writer = deployed_contract.functions.authorizedWriter().call()
    print(f"Contract Owner: {owner}")
    print(f"Authorized Writer: {authorized_writer}")

    # Save deployment metadata
    deployments_dir = BASE_DIR / "blockchain" / "deployments"
    deployments_dir.mkdir(parents=True, exist_ok=True)
    deployment_record = {
        "network": "ganache",
        "rpc_url": rpc_url,
        "chainId": chain_id,
        "contractAddress": contract_address,
        "deployerAddress": deployer_address,
        "transactionHash": tx_hash.hex(),
        "blockNumber": receipt.blockNumber,
        "owner": owner,
        "authorizedWriter": authorized_writer,
    }

    with open(deployments_dir / "ganache.json", "w", encoding="utf-8") as f:
        json.dump(deployment_record, f, indent=2)

    print(f"Saved deployment artifact -> {deployments_dir / 'ganache.json'}")

    # Update .env if it exists
    if env_path.exists():
        set_key(str(env_path), "BLOCKCHAIN_ENABLED", "true")
        set_key(str(env_path), "BLOCKCHAIN_RPC_URL", rpc_url)
        set_key(str(env_path), "BLOCKCHAIN_CHAIN_ID", str(chain_id))
        set_key(str(env_path), "BLOCKCHAIN_CONTRACT_ADDRESS", contract_address)
        set_key(str(env_path), "BLOCKCHAIN_ACCOUNT_ADDRESS", deployer_address)
        print("Updated .env with contract address, account address, and chain ID.")

    return deployment_record


if __name__ == "__main__":
    deploy()
