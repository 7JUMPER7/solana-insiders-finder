import requests
import json
from solana.rpc.api import Client
from solders.pubkey import Pubkey

client = Client(
    "https://mainnet.helius-rpc.com/?api-key=87f91e12-46ac-4c12-8442-998e8f0e8cb9"
)

with open('config.json', 'r') as f:
    mint_data = json.load(f)

min_percentage = 70 

def get_mint_transactions(token_name, mint, limit=100, before=None):
    TOTAL_LIMIT = 100
    signatures = []
    try:
        while True:
            mint_address = Pubkey.from_string(mint)
            new_signatures = client.get_signatures_for_address(
                mint_address, limit=limit, before=before).value
            if not new_signatures:
                break
            signatures.extend(new_signatures)
            before = new_signatures[-1].signature
            if len(signatures) >= TOTAL_LIMIT:
                break
    except Exception as e:
        print(f"Error for token {token_name}: {e}")
    return signatures, before


def check_transaction_for_swap(signature):
    try:
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
        return wallets
    except Exception as e:
        print(f"Error parsing for token {token_name}: {e}")


def find_common_wallets(wallets_by_token, min_percentage):
    total_tokens = len(wallets_by_token)
    min_token_count = round((min_percentage / 100) * total_tokens)

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


wallets_by_token = {}

for token_name, token_data in mint_data.items():
    mint = token_data['mint']
    before_hash = token_data['before_hash'] 
    
    transactions, new_before_hash = get_mint_transactions(token_name, mint, 10, before_hash)
    
    mint_data[token_name]['before_hash'] = new_before_hash
    
    wallets = parse_transactions(token_name, transactions)
    wallets_by_token[token_name] = wallets

common_wallets = find_common_wallets(wallets_by_token, min_percentage)

if common_wallets:
    with open('result.json', 'w') as f:
        json.dump(common_wallets, f, indent=4)
    print(f"Wallets (appearing in at least {min_percentage}% of tokens): {common_wallets}")
else:
    print(f"No wallets found that appear in at least {min_percentage}% of tokens.")
