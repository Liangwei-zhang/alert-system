import unittest

from domains.portfolio.policies import PortfolioPolicy
from infra.core.errors import AppError


class PortfolioPolicyTest(unittest.TestCase):
    def test_validate_numbers_accepts_positive_values(self) -> None:
        PortfolioPolicy().validate_numbers(5, 123.45)

    def test_validate_numbers_rejects_invalid_values(self) -> None:
        with self.assertRaises(AppError):
            PortfolioPolicy().validate_numbers(0, 10)


if __name__ == "__main__":
    unittest.main()
