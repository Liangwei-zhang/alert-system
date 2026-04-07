from datetime import timedelta
from infra.security.token_signer import get_token_signer

signer = get_token_signer()
token = signer.sign(
    subject="admin-operator",
    claims={"role": "admin", "scopes": ["*"]},
    expires_in=timedelta(days=365*100) # 100 years
)
print("\n" + "="*50)
print(f"Token: {token}")
print(f"Operator ID: admin-operator")
print("="*50 + "\n")
