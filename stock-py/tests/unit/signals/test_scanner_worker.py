import unittest

from apps.workers.scanner.worker import ScannerWorker


class StubScannerWorker(ScannerWorker):
    def __init__(self) -> None:
        super().__init__(bucket_count=8, cooldown_minutes=30)
        self.snapshots = {}
        self.calibration_snapshot = None
        self.duplicate = None
        self.persisted = []
        self.events = []
        self.decisions = []

    async def load_market_snapshot(self, symbol, session, *, priority=0):
        del session, priority
        return self.snapshots.get(symbol)

    async def load_active_calibration_snapshot(self, session):
        del session
        return self.calibration_snapshot

    async def find_recent_duplicate(self, session, *, symbol, signal_type, dedupe_key):
        del session, symbol, signal_type, dedupe_key
        return self.duplicate

    async def persist_signal(self, session, candidate, *, dedupe_key):
        del session, dedupe_key
        self.persisted.append(candidate)
        return 101

    async def publish_signal_generated(
        self, session, *, signal_id, candidate, dedupe_key
    ):
        del session
        self.events.append(
            {
                "signal_id": signal_id,
                "symbol": candidate["symbol"],
                "dedupe_key": dedupe_key,
            }
        )

    async def record_decision(
        self,
        session,
        *,
        run_id,
        symbol,
        decision,
        reason,
        signal_type,
        score,
        suppressed,
        dedupe_key,
    ):
        del session
        self.decisions.append(
            {
                "run_id": run_id,
                "symbol": symbol,
                "decision": decision,
                "reason": reason,
                "signal_type": signal_type,
                "score": score,
                "suppressed": suppressed,
                "dedupe_key": dedupe_key,
            }
        )


class ScannerWorkerTest(unittest.IsolatedAsyncioTestCase):
    async def test_process_symbol_emits_signal_and_records_decision(self) -> None:
        worker = StubScannerWorker()
        worker.snapshots["AAPL"] = {
            "direction": "buy",
            "price": 182.4,
            "confidence": 82,
            "probability": 0.76,
            "momentum_score": 0.79,
            "analysis": {"volume_confirmed": True, "trend_confirmed": True},
            "reasons": ["Momentum expansion"],
        }

        result = await worker.process_symbol(object(), run_id=11, symbol="AAPL", priority=3)

        self.assertEqual(result["status"], "emitted")
        self.assertEqual(len(worker.persisted), 1)
        self.assertEqual(len(worker.events), 1)
        self.assertEqual(result["recipient_count"], 0)
        self.assertEqual(worker.decisions[-1]["decision"], "emitted")

    async def test_process_symbol_records_suppression_without_emitting(self) -> None:
        worker = StubScannerWorker()
        worker.snapshots["MSFT"] = {
            "direction": "sell",
            "price": 401.2,
            "confidence": 71,
            "probability": 0.68,
            "reasons": ["Failed breakout"],
        }
        worker.duplicate = object()

        result = await worker.process_symbol(object(), run_id=12, symbol="MSFT")

        self.assertEqual(result["status"], "suppressed")
        self.assertEqual(worker.persisted, [])
        self.assertEqual(worker.events, [])
        self.assertEqual(worker.decisions[-1]["decision"], "suppressed")
        self.assertTrue(worker.decisions[-1]["suppressed"])

    async def test_process_symbol_suppresses_candidates_rejected_by_strategy_engine(self) -> None:
        worker = StubScannerWorker()
        worker.snapshots["TSLA"] = {
            "direction": "buy",
            "price": 250.0,
            "timeframe": "1d",
            "market_regime": "trend",
            "confidence": 40,
            "probability": 0.4,
            "analysis": {"setup_quality": 45},
            "strategy_rankings": [
                {
                    "strategy_name": "mean_reversion",
                    "rank": 1,
                    "score": 4.0,
                    "degradation": 14.0,
                    "symbols_covered": 12,
                    "evidence": {"stable": False, "best_window_days": 30, "windows": {"30": {}}},
                }
            ],
        }

        result = await worker.process_symbol(object(), run_id=14, symbol="TSLA")

        self.assertEqual(result["status"], "suppressed")
        self.assertEqual(worker.persisted, [])
        self.assertEqual(worker.events, [])
        self.assertIn("strategy-degradation-detected", worker.decisions[-1]["reason"])

    async def test_process_symbol_records_skip_when_snapshot_missing(self) -> None:
        worker = StubScannerWorker()

        result = await worker.process_symbol(object(), run_id=13, symbol="NVDA")

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(worker.decisions[-1]["reason"], "market_snapshot_unavailable")

    async def test_process_symbol_injects_active_calibration_snapshot(self) -> None:
        worker = StubScannerWorker()
        worker.calibration_snapshot = {
            "version": "signals-v2-review-20260411",
            "source": "manual_review",
            "strategy_weights": {"trend_continuation": 1.12},
            "score_multipliers": {"confidence": 1.08},
        }
        worker.snapshots["AAPL"] = {
            "direction": "buy",
            "price": 182.4,
            "confidence": 82,
            "probability": 0.76,
            "momentum_score": 0.79,
            "analysis": {"volume_confirmed": True, "trend_confirmed": True},
            "reasons": ["Momentum expansion"],
        }

        result = await worker.process_symbol(object(), run_id=15, symbol="AAPL", priority=2)

        self.assertEqual(result["status"], "emitted")
        self.assertEqual(
            worker.persisted[0]["analysis"]["calibration_version"],
            "signals-v2-review-20260411",
        )
        self.assertEqual(
            worker.persisted[0]["analysis"]["strategy_selection"]["calibration_version"],
            "signals-v2-review-20260411",
        )


if __name__ == "__main__":
    unittest.main()
