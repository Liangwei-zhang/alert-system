import unittest

from domains.trades.html_renderer import TradeHtmlRenderer


class TradeHtmlRendererTest(unittest.TestCase):
    def test_render_confirm_page_uses_public_api_route(self) -> None:
        html = TradeHtmlRenderer.render_confirm_page(
            trade_id="trade-1",
            token="token-abc",
            action="accept",
            symbol="AAPL",
            trade_action="buy",
            suggested_shares=10,
            suggested_price=150.0,
            suggested_amount=1500.0,
        )

        self.assertIn("/v1/trades/trade-1/confirm?action=accept&t=token-abc", html)
        self.assertIn("Need custom shares or price?", html)

    def test_status_label_returns_known_status(self) -> None:
        self.assertEqual(TradeHtmlRenderer.status_label("adjusted"), "adjusted")
        self.assertEqual(TradeHtmlRenderer.status_label("unknown"), "unknown")


if __name__ == "__main__":
    unittest.main()
