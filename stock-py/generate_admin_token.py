from __future__ import annotations

import asyncio
from datetime import timedelta

from sqlalchemy import select

from infra.db.models.admin import AdminOperatorModel
from infra.db.models.auth import UserModel
from infra.db.session import get_session_factory
from infra.security.token_signer import get_token_signer


async def resolve_default_operator() -> tuple[int, str]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(AdminOperatorModel.user_id, UserModel.email)
            .join(UserModel, UserModel.id == AdminOperatorModel.user_id)
            .where(AdminOperatorModel.is_active.is_(True), UserModel.is_active.is_(True))
            .order_by(AdminOperatorModel.user_id.asc())
            .limit(1)
        )
        row = result.one_or_none()
        if row is None:
            raise RuntimeError("No active admin operator found")
        return int(row[0]), str(row[1])


def main() -> None:
    operator_id, operator_email = asyncio.run(resolve_default_operator())
    signer = get_token_signer()
    token = signer.sign(
        subject=str(operator_id),
        claims={"role": "admin", "is_admin": True, "scopes": ["*"]},
        expires_in=timedelta(days=365 * 100),
    )
    print("\n" + "=" * 50)
    print(f"Token: {token}")
    print(f"Operator ID: {operator_id}")
    print(f"Operator Email: {operator_email}")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
