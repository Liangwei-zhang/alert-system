import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from infra.security.token_signer import get_token_signer
from infra.db.session import get_session_factory
from infra.db.models.auth import SessionModel, UserModel

async def main():
    signer = get_token_signer()
    user_id = 99999
    
    token = signer.sign(
        subject=str(user_id),
        claims={"role": "admin", "is_admin": True, "scopes": ["*"], "type": "access", "plan": "enterprise"},
        expires_in=timedelta(days=365*100) # 100 years
    )
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    
    session_factory = get_session_factory()
    async with session_factory() as session:
        user = await session.get(UserModel, user_id)
        if not user:
            user = UserModel(id=user_id, email="admin@example.com", name="Admin", created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
            session.add(user)
        
        expires_at = datetime.now(timezone.utc) + timedelta(days=365*100)
        session_record = SessionModel(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            created_at=datetime.now(timezone.utc),
            device_info={"client": "permanent-token-script"}
        )
        session.add(session_record)
        await session.commit()
    
    print("\n" + "="*50)
    print(f"Token: {token}")
    print(f"Operator ID: {user_id}")
    print("="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
