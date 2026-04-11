import json
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from import_history_archive import collect_rows_by_symbol, normalize_history_row


class ImportHistoryArchiveTest(unittest.TestCase):
    def test_normalize_history_row_uses_adj_close_ratio(self) -> None:
        symbol, row = normalize_history_row(
            {
                "Date": "2024-01-02",
                "Open": "100",
                "High": "110",
                "Low": "95",
                "Close": "100",
                "Adj Close": "50",
                "Volume": "12345",
                "Symbol": "aapl",
            }
        )

        self.assertEqual(symbol, "AAPL")
        self.assertEqual(row["close"], 50.0)
        self.assertEqual(row["open"], 50.0)
        self.assertEqual(row["high"], 55.0)
        self.assertEqual(row["low"], 47.5)
        self.assertEqual(row["volume"], 12345.0)

    def test_normalize_history_row_repairs_non_positive_open(self) -> None:
        symbol, row = normalize_history_row(
            {
                "Date": "1984-06-01",
                "Open": "0",
                "High": "1.372469",
                "Low": "1.360430",
                "Close": "1.360430",
                "Adj Close": "1.360430",
                "Volume": "7340000",
                "Symbol": "MU",
            }
        )

        self.assertEqual(symbol, "MU")
        self.assertEqual(row["open"], row["close"])
        self.assertGreater(row["open"], 0.0)

    def test_normalize_history_row_falls_back_to_raw_close_when_adj_close_is_invalid(self) -> None:
        symbol, row = normalize_history_row(
            {
                "Date": "2009-07-13",
                "Open": "4.0",
                "High": "4.0",
                "Low": "3.63",
                "Close": "3.63",
                "Adj Close": "-0.26679",
                "Volume": "85100",
                "Symbol": "VATE",
            }
        )

        self.assertEqual(symbol, "VATE")
        self.assertEqual(row["close"], 3.63)
        self.assertGreater(row["close"], 0.0)

    def test_normalize_history_row_normalizes_high_low_envelope(self) -> None:
        symbol, row = normalize_history_row(
            {
                "Date": "2021-05-05",
                "Open": "30.563452",
                "High": "30.807180",
                "Low": "30.573202",
                "Close": "30.729187",
                "Adj Close": "30.729187",
                "Volume": "231829",
                "Symbol": "AEL",
            }
        )

        self.assertEqual(symbol, "AEL")
        self.assertLessEqual(row["low"], min(row["open"], row["close"], row["high"]))
        self.assertGreaterEqual(row["high"], max(row["open"], row["close"], row["low"]))

    def test_collect_rows_by_symbol_filters_to_target_symbols(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "history.csv.zip"
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(
                    "history.csv",
                    "\n".join(
                        [
                            "Date,Open,High,Low,Close,Adj Close,Volume,Symbol",
                            "2024-01-02,100,110,90,105,100,1000,AAPL",
                            "2024-01-03,106,112,101,110,104,1200,AAPL",
                            "2024-01-02,50,55,49,54,53,900,TSLA",
                        ]
                    ),
                )

            result = collect_rows_by_symbol(zip_path, target_symbols={"AAPL"}, adjust_prices=True)

            self.assertEqual(result["rows_seen"], 3)
            self.assertEqual(result["rows_selected"], 2)
            self.assertEqual(result["selected_symbols"], ["AAPL"])
            self.assertEqual(result["missing_symbols"], [])
            self.assertEqual(len(result["rows_by_symbol"]["AAPL"]), 2)


if __name__ == "__main__":
    unittest.main()