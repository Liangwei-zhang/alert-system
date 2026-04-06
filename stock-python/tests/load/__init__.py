"""
Load testing package for stock-python.

Usage:
    locust -f tests/load/auth_load_test.py --host=http://localhost:8000
    locust -f tests/load/portfolio_load_test.py --host=http://localhost:8000
    locust -f tests/load/notifications_load_test.py --host=http://localhost:8000
    locust -f tests/load/scanner_load_test.py --host=http://localhost:8000

For distributed testing:
    locust -f tests/load/auth_load_test.py --headless -r 100 -t 60s --host=http://localhost:8000
"""