from __future__ import annotations

from domains.signals.desktop_signal_service import DesktopSignalService
from tests.helpers.app_client import PublicApiClient


def test_scanner_flow(public_api_client: PublicApiClient, monkeypatch) -> None:
    calls: dict[str, object] = {}

    async def fake_ingest_desktop_signal(self, request) -> dict:
        calls["ingest_desktop_signal"] = request.model_dump(mode="json")
        return {
            "signal_id": 101,
            "dedupe_key": "AAPL:buy:1h:bull",
            "suppressed": False,
            "queued_recipient_count": 3,
            "status": "accepted",
        }

    monkeypatch.setattr(DesktopSignalService, "ingest_desktop_signal", fake_ingest_desktop_signal)

    response = public_api_client.post(
        "/v1/internal/signals/desktop",
        json={
            "source": "desktop-terminal",
            "emitted_at": "2026-04-04T00:00:00Z",
            "alert": {
                "symbol": "aapl",
                "type": "buy",
                "score": 87,
                "price": 150.25,
                "reasons": ["breakout", "volume spike"],
                "confidence": 90,
                "probability": 0.82,
                "stop_loss": 145.0,
                "take_profit_1": 158.0,
                "take_profit_2": 164.0,
                "take_profit_3": 170.0,
                "strategy_window": "1h",
                "market_regime": "bull",
            },
            "analysis": {
                "cooldown_minutes": 60,
                "strategy_window": "1h",
                "market_regime": "bull",
            },
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "signal_id": 101,
        "dedupe_key": "AAPL:buy:1h:bull",
        "suppressed": False,
        "queued_recipient_count": 3,
        "status": "accepted",
    }
    assert calls["ingest_desktop_signal"] == {
        "source": "desktop-terminal",
        "emitted_at": "2026-04-04T00:00:00Z",
        "alert": {
            "symbol": "AAPL",
            "type": "buy",
            "score": 87.0,
            "price": 150.25,
            "reasons": ["breakout", "volume spike"],
            "confidence": 90.0,
            "probability": 0.82,
            "stop_loss": 145.0,
            "take_profit_1": 158.0,
            "take_profit_2": 164.0,
            "take_profit_3": 170.0,
            "strategy_window": "1h",
            "market_regime": "bull",
        },
        "analysis": {
            "cooldown_minutes": 60,
            "strategy_window": "1h",
            "market_regime": "bull",
        },
    }
