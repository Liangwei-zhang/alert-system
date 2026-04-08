import urllib.request
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# US: SEC (needs User-Agent)
req = urllib.request.Request(
    'https://www.sec.gov/files/company_tickers.json',
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Admin/1.0'}
)
try:
    with urllib.request.urlopen(req, context=ctx) as response:
        us_data = json.loads(response.read().decode())
        print(f"US Stocks (SEC): {len(us_data)}")
        first_key = list(us_data.keys())[0]
        print(f"Sample: {us_data[first_key]}")
except Exception as e:
    print(f"US fail: {e}")

# Crypto: Binance
try:
    req2 = urllib.request.Request('https://api.binance.com/api/v3/exchangeInfo')
    with urllib.request.urlopen(req2, context=ctx) as response:
        crypto_data = json.loads(response.read().decode())
        pairs = [s for s in crypto_data['symbols'] if s['status'] == 'TRADING' and s['quoteAsset'] == 'USDT']
        print(f"Crypto Pairs (Binance USDT): {len(pairs)}")
        print(f"Sample Crypto: {pairs[0]['symbol']}")
except Exception as e:
    print(f"Crypto fail: {e}")

