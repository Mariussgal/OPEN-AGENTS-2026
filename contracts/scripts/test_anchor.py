import os
import requests
from dotenv import load_dotenv

load_dotenv()

registry      = os.getenv('ANCHOR_REGISTRY_ADDRESS')
etherscan_key = os.getenv('ETHERSCAN_API_KEY')

print('Registry:', registry)
print('Key:', bool(etherscan_key))

resp = requests.get(
    'https://api.etherscan.io/v2/api',
    params={
        'chainid':    '11155111',
        'module':     'account',
        'action':     'txlist',
        'address':    registry,
        'startblock': 0,
        'endblock':   99999999,
        'sort':       'desc',
        'apikey':     etherscan_key,
    }
).json()

print('Status:', resp.get('status'))
print('Message:', resp.get('message'))
result = resp.get('result')
print('Result type:', type(result))
print('Result preview:', str(result)[:200])

if not isinstance(result, list):
    print('ERROR: result is not a list')
    exit(1)

ph_clean = 'accf5e130c2d752144900bad7f626b3563e138c5344eb9f422c3b1be99398fbf'
print(f'\nCherche: {ph_clean}')
print(f'Txs a scanner: {len(result)}')

found = False
for tx in result:
    input_data = tx.get('input', '').lower()
    if ph_clean in input_data:
        print('Trouve !')
        print(f'  tx:    {tx["hash"]}')
        print(f'  input: {tx["input"][:80]}')
        found = True
        break

if not found:
    print('Not found - first inputs:')
    for tx in result[:3]:
        print(f'  input: {tx["input"]}')
