# tests/test_performance_benchmarks.py
import time

import pytest
from fastapi.testclient import TestClient


def test_health_endpoint_performance(client: TestClient):
    """Test that health endpoint responds quickly"""
    start_time = time.time()
    response = client.get("/health")
    end_time = time.time()

    assert response.status_code == 200
    assert (end_time - start_time) < 0.1  # Should respond in < 100ms


def test_alerts_endpoint_performance(client: TestClient, test_user, db_session):
    """Test alerts endpoint performance"""
    client.set_user_id(test_user.userid)

    start_time = time.time()
    response = client.get("/alerts/")
    end_time = time.time()

    assert response.status_code == 200
    assert (end_time - start_time) < 0.5  # Should respond in < 500ms


@pytest.mark.benchmark
def test_concurrent_requests_simulation(client: TestClient):
    """Simulate concurrent requests"""
    import concurrent.futures

    def make_request():
        return client.get("/health")

    # Simulate 10 concurrent requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request) for _ in range(10)]
        results = [future.result() for future in futures]

    # All requests should succeed
    assert all(r.status_code == 200 for r in results)
