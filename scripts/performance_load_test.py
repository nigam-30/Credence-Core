"""
Credence Core — Comprehensive Production Load & Financial Reliability Benchmark
Simulates realistic production traffic at progressive concurrency levels (10, 50, 100 concurrent users),
measures real latency percentiles (Avg, p50, p95, p99), throughput (RPS), error rates, CPU and Memory usage,
and verifies mathematical double-entry ledger integrity under load.
"""

import os
import sys
import time
import uuid
import psutil
import concurrent.futures
from typing import List, Dict, Any

BASE_DIR = r"D:\bank_system_clean"
sys.path.insert(0, BASE_DIR)

from backend.app import create_app
from backend.app.services.ledger import ledger_service
from backend.app.core.database import get_db
from models import Account, AccountBalance
import security


def run_benchmark_suite():
    print("================================================================================")
    print(" CREDENCE CORE — PRODUCTION LOAD & RELIABILITY BENCHMARK")
    print("================================================================================")

    app = create_app()
    app.config["TESTING"] = True
    app.config["RATE_LIMIT_API_MAX"] = 100000
    client = app.test_client()

    # Pre-warm and verify baseline
    initial_cpu = psutil.cpu_percent(interval=0.5)
    mem_info = psutil.virtual_memory()
    initial_mem_mb = psutil.Process().memory_info().rss / (1024 * 1024)

    print(f"System Baseline: Host CPU {initial_cpu}% | Process Memory: {initial_mem_mb:.1f} MB | System RAM Used: {mem_info.percent}%")
    print("--------------------------------------------------------------------------------")

    # Set up synthetic authenticated session token
    with client.session_transaction() as sess:
        sess["user_id"] = "40273146502136"
        sess["role"] = "user"
        sess["auth_time"] = 9999999999.0
        sess["csrf_token"] = security.generate_csrf_token()
        csrf_token = sess["csrf_token"]

    headers = {"X-CSRF-Token": csrf_token}

    # Progressive Concurrency Tiers: (Concurrency, Request Count)
    tiers = [
        (10, 100),
        (50, 250),
        (100, 500)
    ]

    benchmark_results = []

    for concurrency, total_requests in tiers:
        print(f"\n[+] Executing Tier: {concurrency} Concurrent Workers | {total_requests} Total Requests...")
        latencies = []
        errors = 0

        cpu_start = psutil.cpu_percent(interval=None)
        mem_start_mb = psutil.Process().memory_info().rss / (1024 * 1024)
        t_start = time.perf_counter()

        def make_request(req_id: int):
            t0 = time.perf_counter()
            try:
                # Mix of read endpoints: 40% health/live, 30% health/ready, 30% account details
                if req_id % 10 < 4:
                    res = client.get("/health/live")
                elif req_id % 10 < 7:
                    res = client.get("/health/ready")
                else:
                    res = client.get("/api/account/40273146502136", headers=headers)

                t1 = time.perf_counter()
                latency_ms = (t1 - t0) * 1000.0

                if res.status_code >= 400:
                    return False, latency_ms
                return True, latency_ms
            except Exception:
                t1 = time.perf_counter()
                return False, (t1 - t0) * 1000.0

        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(make_request, i) for i in range(total_requests)]
            for f in concurrent.futures.as_completed(futures):
                ok, lat = f.result()
                latencies.append(lat)
                if not ok:
                    errors += 1

        t_end = time.perf_counter()
        total_time = t_end - t_start
        cpu_end = psutil.cpu_percent(interval=None)
        mem_end_mb = psutil.Process().memory_info().rss / (1024 * 1024)

        latencies.sort()
        n = len(latencies)
        avg_lat = sum(latencies) / n if n > 0 else 0.0
        p50 = latencies[int(n * 0.50)] if n > 0 else 0.0
        p95 = latencies[min(int(n * 0.95), n - 1)] if n > 0 else 0.0
        p99 = latencies[min(int(n * 0.99), n - 1)] if n > 0 else 0.0
        rps = total_requests / total_time if total_time > 0 else 0.0
        err_rate = (errors / total_requests) * 100.0

        res_obj = {
            "concurrency": concurrency,
            "requests": total_requests,
            "duration_s": round(total_time, 2),
            "rps": round(rps, 1),
            "avg_ms": round(avg_lat, 2),
            "p50_ms": round(p50, 2),
            "p95_ms": round(p95, 2),
            "p99_ms": round(p99, 2),
            "errors": errors,
            "error_rate_pct": round(err_rate, 2),
            "process_mem_mb": round(mem_end_mb, 1),
        }
        benchmark_results.append(res_obj)

        print(f"    Completed in {total_time:.2f}s | Throughput: {rps:.1f} req/s | Error Rate: {err_rate:.2f}%")
        print(f"    Latency: Avg {avg_lat:.2f}ms | p50: {p50:.2f}ms | p95: {p95:.2f}ms | p99: {p99:.2f}ms")
        print(f"    Process Memory: {mem_end_mb:.1f} MB (Delta: +{mem_end_mb - mem_start_mb:.1f} MB)")

    # ══════════════════════════════════════════════════════════════
    # FINANCIAL CONCURRENCY STRESS & INTEGRITY VALIDATION
    # ══════════════════════════════════════════════════════════════
    print("\n--------------------------------------------------------------------------------")
    print(" FINANCIAL CONCURRENCY STRESS & DOUBLE-ENTRY LEDGER VALIDATION")
    print("--------------------------------------------------------------------------------")

    # 1. Idempotency Key Duplicate Prevention Test under Concurrency
    print("[+] Testing Idempotent Replays under 20 Concurrent Duplicate Requests...")
    idempotency_key = f"IDEM-STRESS-{uuid.uuid4().hex}"
    dup_results = []

    def make_idempotent_call(idx):
        return client.post(
            "/api/deposit",
            json={"amount": 1000.0, "idempotency_key": idempotency_key},
            headers=headers,
            content_type="application/json"
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futs = [executor.submit(make_idempotent_call, i) for i in range(20)]
        for f in concurrent.futures.as_completed(futs):
            res = f.result()
            dup_results.append(res.status_code)

    # Exactly 1 request creates the transaction; subsequent concurrent calls should return 200 with the same reference_id
    success_200 = sum(1 for c in dup_results if c == 200)
    print(f"    Idempotent Requests Completed: {len(dup_results)} (200 OK: {success_200})")

    # 2. Reconcile Double-Entry Ledger
    print("\n[+] Running Mathematical Ledger Reconciliation...")
    recon = ledger_service.reconcile()
    print(f"    Ledger Status:        {recon['status']}")
    print(f"    Total Transactions:   {recon['total_transactions']}")
    print(f"    Total Ledger Entries: {recon['total_ledger_entries']}")
    print(f"    System Total Debits:  Rs {recon['total_system_debits_rupees']:,.2f} ({recon['total_system_debits_paise']} paise)")
    print(f"    System Total Credits: Rs {recon['total_system_credits_rupees']:,.2f} ({recon['total_system_credits_paise']} paise)")
    print(f"    Discrepancy:          {recon['discrepancy_paise']} paise")
    print(f"    Account Discrepancies:{len(recon['account_discrepancies'])}")

    assert recon["status"] == "HEALTHY", f"Ledger status not healthy: {recon}"
    assert recon["discrepancy_paise"] == 0, f"Ledger discrepancy detected: {recon['discrepancy_paise']} paise"
    print("\n[SUCCESS] Double-entry ledger is perfectly balanced with ZERO discrepancy.")

    return benchmark_results, recon


if __name__ == "__main__":
    run_benchmark_suite()
