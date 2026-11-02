"""
Credence Core — QA Test Suite 5: Load and Performance Benchmark Testing
Benchmarks throughput (RPS), p50, p95, and p99 response times under load.
"""

import unittest
import time
from backend.app import create_app
import security


class LoadPerformanceTestSuite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.app.config["RATE_LIMIT_API_MAX"] = 10000
        cls.client = cls.app.test_client()

    def setUp(self):
        security.IP_REQUEST_HISTORY.clear()
        security.FAILED_ATTEMPTS_STORE.clear()

    def _login_session(self, account="40273146502136"):
        with self.client.session_transaction() as sess:
            sess["user_id"] = str(account)
            sess["role"] = "user"
            sess["auth_time"] = 9999999999.0
            sess["csrf_token"] = security.generate_csrf_token()
            token = sess["csrf_token"]
        return {"X-CSRF-Token": token}

    def test_benchmark_api_throughput_and_latencies(self):
        """Execute 150 requests and measure latency percentiles (p50, p95, p99)."""
        headers = self._login_session()
        latencies = []
        num_requests = 150

        start_time = time.perf_counter()
        for i in range(num_requests):
            t0 = time.perf_counter()
            # Alternate between fast liveness probe and authenticated account details
            if i % 2 == 0:
                res = self.client.get("/health/live")
            else:
                res = self.client.get("/api/account/40273146502136", headers=headers)
            t1 = time.perf_counter()

            self.assertEqual(res.status_code, 200)
            latencies.append((t1 - t0) * 1000.0)  # ms

        total_duration = time.perf_counter() - start_time
        rps = num_requests / total_duration

        latencies.sort()
        n = len(latencies)
        p50 = latencies[int(n * 0.50)]
        p95 = latencies[min(int(n * 0.95), n - 1)]
        p99 = latencies[min(int(n * 0.99), n - 1)]
        avg = sum(latencies) / n

        print(f"\n  [Performance Benchmark] Requests: {num_requests} in {total_duration:.2f}s ({rps:.1f} req/s)")
        print(f"  [Latency Percentiles] Avg: {avg:.2f}ms | p50: {p50:.2f}ms | p95: {p95:.2f}ms | p99: {p99:.2f}ms")

        # Performance SLA assertions
        self.assertLess(p50, 50.0, f"p50 latency {p50:.2f}ms exceeds 50ms SLA")
        self.assertLess(p95, 150.0, f"p95 latency {p95:.2f}ms exceeds 150ms SLA")


if __name__ == "__main__":
    unittest.main()
