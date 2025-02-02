import time
from solders.pubkey import Pubkey
from solders.signature import Signature
from solana.rpc.api import Client
import json
import math
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Solana RPC client using the HTTP node URL from environment variables
client = Client(os.getenv("HTTP_NODE_URL"))
min_percentage = 80  # Minimum percentage threshold for common wallets

def get_mint_transactions(token_name, mint, limit=100, before=None, after=None):
    # Set a total limit for the number of signatures to retrieve
    TOTAL_LIMIT = 300000
    signatures = []
    try:
        while True:
            # Convert the mint address from string to Pubkey object
            mint_address = Pubkey.from_string(mint)
            # Get a batch of signatures for the given mint address
            new_signatures = client.get_signatures_for_address(
                mint_address, limit=limit, before=before).value
            # If no more signatures are returned, exit the loop
            if not new_signatures:
                break

            # Iterate over the new signatures
            for signature in new_signatures:
                # If an "after" signature is specified and reached, stop processing
                if after and signature.signature == after:
                    print(f"Reached after_hash for token {token_name}, stopping.")
                    return signatures, before
                
                # Append the signature to the list
                signatures.append(signature)

            # Log the number of new signatures retrieved for the token
            print("New signatures len:", len(new_signatures), "for:", token_name)
            # Update the 'before' parameter to the last signature in the batch for pagination
            before = new_signatures[-1].signature
            # Break if the total number of collected signatures exceeds the total limit
            if len(signatures) >= TOTAL_LIMIT:
                break
    except Exception as e:
        # Print any error encountered during signature retrieval
        print(f"Error for token {token_name}: {e}")
    return signatures, before

def check_transaction_for_swap(signature):
    try:
        # If the signature is provided as a string, convert it to a Signature object
        if type(signature) == str:
            signature = Signature.from_string(signature)
        # Retrieve transaction information using the signature
        tx_info = client.get_transaction(
            signature,
            max_supported_transaction_version=1,
            encoding='base64'
        ).value
        # Extract the signer address from the transaction message
        signer_address = tx_info.transaction.transaction.message.account_keys[0]
        return signer_address
    except Exception as e:
        # Print any error encountered during transaction check
        print(f"Error checking transaction {signature}: {e}")
        return None

def parse_transactions(token_name, transactions):
    wallets = []
    try:
        # Iterate over each transaction in the list
        for tx in transactions:
            # Check the transaction for a swap and retrieve the associated wallet address
            address = check_transaction_for_swap(tx.signature)
            if address:
                # Convert the address to string and append to the wallets list
                wallet_string = str(address)
                wallets.append(wallet_string)
            # Sleep briefly to avoid hitting rate limits
            time.sleep(0.2)
        return wallets
    except Exception as e:
        # Print any error encountered during transaction parsing
        print(f"Error parsing for token {token_name}: {e}")

def find_common_wallets(wallets_by_token, min_percentage):
    # Determine the total number of tokens processed
    total_tokens = len(wallets_by_token)
    # Calculate the minimum token count required based on the percentage threshold
    min_token_count = math.ceil((min_percentage / 100) * total_tokens)

    wallet_count = {}

    # Count how many tokens each wallet appears in
    for token_name, wallets in wallets_by_token.items():
        # Use set to avoid duplicate wallet entries for the same token
        for wallet in set(wallets):
            if wallet not in wallet_count:
                wallet_count[wallet] = {'count': 0, 'tokens': []}
            wallet_count[wallet]['count'] += 1
            wallet_count[wallet]['tokens'].append(token_name)

    # Filter wallets that appear in at least the minimum number of tokens
    common_wallets = {
        wallet: data['tokens']
        for wallet, data in wallet_count.items() if data['count'] >= min_token_count
    }

    return common_wallets

if __name__ == "__main__":
    # Uncomment the following lines to test checking a single transaction
    # result = check_transaction_for_swap("32ffe61RVuH9ziqBkxuec8uGFDfD52fhFzpg44ZtUoq9CpkLPCLdEgdQAi4ubgNf8cdhLgAB97abC5PkHMVDGB14")
    # print(result)
    
    # Load token mint configuration data from config.json
    with open('config.json', 'r') as f:
        mint_data = json.load(f)
    wallets_by_token = {}

    # Process each token defined in the configuration
    for token_name, token_data in mint_data.items():
        mint = token_data['mint']
        # Convert before_hash and after_hash strings to Signature objects if they exist
        before_hash = Signature.from_string(token_data['before_hash']) if token_data['before_hash'] else None
        after_hash = Signature.from_string(token_data['after_hash']) if token_data['after_hash'] else None

        # Retrieve transactions for the token's mint address
        transactions, new_before_hash = get_mint_transactions(
            token_name, mint, limit=1000, before=before_hash, after=after_hash)

        # Update the before_hash in the configuration with the latest value
        mint_data[token_name]['before_hash'] = new_before_hash

        # Parse the retrieved transactions to extract wallet addresses
        wallets = parse_transactions(token_name, transactions)
        wallets_by_token[token_name] = wallets

    # Identify wallets that appear across tokens meeting the minimum percentage threshold
    common_wallets = find_common_wallets(wallets_by_token, min_percentage)

    # Save the result to result.json if any common wallets are found
    if common_wallets:
        with open('result.json', 'w') as f:
            json.dump(common_wallets, f, indent=4)
        print(f"Wallets count (appearing in at least {min_percentage}% of tokens): {len(common_wallets)}")
    else:
        print(f"No wallets found that appear in at least {min_percentage}% of tokens.")
