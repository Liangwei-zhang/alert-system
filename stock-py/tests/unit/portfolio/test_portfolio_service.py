import asyncio
import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from domains.portfolio.service import PortfolioService


class PortfolioServiceTest(unittest.TestCase):
    def test_list_positions_deserializes_extra_metadata(self) -> None:
        repository = SimpleNamespace(session=SimpleNamespace(info={}))
        item = SimpleNamespace(
            id=1,
            symbol="AAPL",
            shares=10,
            avg_cost=100.0,
            total_capital=1000.0,
            target_profit=0.2,
            stop_loss=0.08,
            notify=True,
            notes="starter",
            extra=json.dumps(
                {
                    "sell_plan": {
                        "base_shares": 10,
                        "stages": [{"id": "tp1", "sell_pct": 0.25}],
                    },
                    "sell_progress": {"completed_stage_ids": []},
                }
            ),
            updated_at=datetime(2026, 4, 9, tzinfo=timezone.utc),
        )

        async def fake_list_by_user(user_id: int):
            self.assertEqual(user_id, 7)
            return [item]

        repository.list_by_user = fake_list_by_user
        service = PortfolioService(repository)

        result = asyncio.run(service.list_positions(7))

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].extra["sell_plan"]["base_shares"], 10)


if __name__ == "__main__":
    unittest.main()