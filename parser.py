import time
from solders.pubkey import Pubkey
from solders.signature import Signature
from solana.rpc.api import Client
import json
import math
import os
from dotenv import load_dotenv

load_dotenv()


client = Client(os.getenv("HTTP_NODE_URL"))
min_percentage = 80


def get_mint_transactions(token_name, mint, limit=100, before=None):
    TOTAL_LIMIT = 300000
    signatures = []
    try:
        while True:
            mint_address = Pubkey.from_string(mint)
            new_signatures = client.get_signatures_for_address(
                mint_address, limit=limit, before=before).value
            if not new_signatures:
                break
            signatures.extend(new_signatures)
            print("New signatures len:", len(
                new_signatures), "for:", token_name)
            before = new_signatures[-1].signature
            if len(signatures) >= TOTAL_LIMIT:
                break
    except Exception as e:
        print(f"Error for token {token_name}: {e}")
    return signatures, before


def check_transaction_for_swap(signature):
    try:
        if type(signature) == str:
            signature = Signature.from_string(signature)
        tx_info = client.get_transaction(
            signature,
            max_supported_transaction_version=1,
            encoding='base64'
        ).value
        signer_address = tx_info.transaction.transaction.message.account_keys[0]
        return signer_address
    except Exception as e:
        print(f"Error checking transaction {signature}: {e}")
        return None


def parse_transactions(token_name, transactions):
    wallets = []
    try:
        for tx in transactions:
            address = check_transaction_for_swap(tx.signature)
            if address:
                wallet_string = str(address)
                wallets.append(wallet_string)
            time.sleep(0.2)
        return wallets
    except Exception as e:
        print(f"Error parsing for token {token_name}: {e}")


def find_common_wallets(wallets_by_token, min_percentage):
    total_tokens = len(wallets_by_token)
    min_token_count = math.ceil((min_percentage / 100) * total_tokens)

    wallet_count = {}

    for token_name, wallets in wallets_by_token.items():
        for wallet in set(wallets):
            if wallet not in wallet_count:
                wallet_count[wallet] = {'count': 0, 'tokens': []}
            wallet_count[wallet]['count'] += 1
            wallet_count[wallet]['tokens'].append(token_name)

    common_wallets = {
        wallet: data['tokens']
        for wallet, data in wallet_count.items() if data['count'] >= min_token_count
    }

    return common_wallets


if __name__ == "__main__":
    # result = check_transaction_for_swap("32ffe61RVuH9ziqBkxuec8uGFDfD52fhFzpg44ZtUoq9CpkLPCLdEgdQAi4ubgNf8cdhLgAB97abC5PkHMVDGB14")
    # print(result)
    
    with open('config.json', 'r') as f:
        mint_data = json.load(f)
    wallets_by_token = {}

    for token_name, token_data in mint_data.items():
        mint = token_data['mint']
        before_hash = Signature.from_string(
            token_data['before_hash']) if token_data['before_hash'] else None

        transactions, new_before_hash = get_mint_transactions(
            token_name, mint, limit=1000, before=before_hash)

        mint_data[token_name]['before_hash'] = new_before_hash

        wallets = parse_transactions(token_name, transactions)
        wallets_by_token[token_name] = wallets

    common_wallets = find_common_wallets(wallets_by_token, min_percentage)

    if common_wallets:
        with open('result.json', 'w') as f:
            json.dump(common_wallets, f, indent=4)
        print(
            f"Wallets count (appearing in at least {min_percentage}% of tokens): {len(common_wallets)}")
    else:
        print(
            f"No wallets found that appear in at least {min_percentage}% of tokens.")
