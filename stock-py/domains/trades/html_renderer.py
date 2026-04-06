"""
HTML renderer for trade confirmation pages.
"""

from typing import Optional


class TradeHtmlRenderer:
    """HTML renderer for trade confirmation pages."""

    @staticmethod
    def render_page(emoji: str, message: str) -> str:
        """
        Render a simple status page.

        Args:
            emoji: Emoji to display.
            message: Message to display.

        Returns:
            HTML page string.
        """
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stock Signal</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100dvh;
            margin: 0;
            background: #f0f2f5;
        }}
        .card {{
            background: #fff;
            border-radius: 20px;
            padding: 40px 32px;
            text-align: center;
            max-width: 320px;
            box-shadow: 0 4px 20px rgba(0,0,0,.08);
        }}
        .emoji {{
            font-size: 56px;
            margin-bottom: 16px;
        }}
        p {{
            color: #555;
            font-size: 15px;
            line-height: 1.6;
        }}
        a {{
            color: #1677ff;
            font-size: 13px;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="emoji">{emoji}</div>
        <p>{message}</p>
        <a href="/">Back to Home</a>
    </div>
</body>
</html>"""

    @staticmethod
    def render_confirm_page(
        trade_id: str,
        token: str,
        action: str,
        symbol: str,
        trade_action: str,
        suggested_shares: float,
        suggested_price: float,
        suggested_amount: float,
    ) -> str:
        """
        Render the trade confirmation page.

        Args:
            trade_id: Trade ID.
            token: Link token.
            action: "accept" or "ignore".
            symbol: Stock symbol.
            trade_action: Trade action (buy/sell/add).
            suggested_shares: Suggested shares.
            suggested_price: Suggested price.
            suggested_amount: Suggested amount.

        Returns:
            HTML page string.
        """
        action_label = "Ignore suggestion" if action == "ignore" else "Confirm suggestion"
        helper_text = (
            "Ignoring will close this pending suggestion without updating the portfolio."
            if action == "ignore"
            else "Confirming will update the portfolio using the suggested execution values shown below."
        )
        adjust_hint = "Need custom shares or price? Use the authenticated app action or call the adjust API directly."

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Confirm stock signal</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100dvh;
            margin: 0;
            background: #f0f2f5;
        }}
        .card {{
            background: #fff;
            border-radius: 20px;
            padding: 32px;
            text-align: left;
            max-width: 420px;
            box-shadow: 0 4px 20px rgba(0,0,0,.08);
        }}
        .chip {{
            display: inline-block;
            background: #eef7f0;
            color: #256d3d;
            border-radius: 999px;
            padding: 4px 10px;
            font-size: 12px;
            margin-bottom: 14px;
        }}
        .meta {{
            color: #555;
            font-size: 14px;
            line-height: 1.8;
            margin: 16px 0;
        }}
        .actions {{
            display: flex;
            gap: 12px;
            margin-top: 20px;
        }}
        button, a {{
            appearance: none;
            border: none;
            border-radius: 12px;
            padding: 12px 16px;
            font-size: 14px;
            text-decoration: none;
            cursor: pointer;
        }}
        button {{
            background: #1677ff;
            color: #fff;
        }}
        a {{
            background: #f5f5f5;
            color: #333;
        }}
        .muted {{
            color: #777;
            font-size: 13px;
            line-height: 1.6;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="chip">{trade_action.upper()} · {symbol}</div>
        <h2 style="margin: 0 0 8px">{action_label}</h2>
        <div class="muted">{helper_text}</div>
        <div class="meta">
            <div>Suggested shares: <strong>{suggested_shares}</strong></div>
            <div>Suggested price: <strong>${suggested_price:.2f}</strong></div>
            <div>Suggested amount: <strong>${suggested_amount:.2f}</strong></div>
        </div>
        <form method="POST" action="/v1/trades/{trade_id}/confirm?action={action}&t={token}">
            <div class="actions">
                <button type="submit">{action_label}</button>
            </div>
        </form>
        <div class="muted" style="margin-top: 14px;">{adjust_hint}</div>
    </div>
</body>
</html>"""

    @staticmethod
    def status_label(status: str) -> str:
        """
        Get human-readable status label.

        Args:
            status: Status string.

        Returns:
            Human-readable label.
        """
        labels = {
            "confirmed": "confirmed",
            "adjusted": "adjusted",
            "ignored": "ignored",
            "expired": "expired",
            "pending": "pending",
        }
        return labels.get(status, status)
