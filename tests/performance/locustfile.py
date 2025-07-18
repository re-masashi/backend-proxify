# tests/performance/locustfile.py

from locust import HttpUser, between, task


class BackendUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """Setup method called once per user"""
        # Health check
        self.client.get("/health")

    @task(3)
    def health_check(self):
        """Test health endpoint"""
        self.client.get("/health")

    @task(2)
    def get_alerts(self):
        """Test alerts listing endpoint"""
        self.client.get("/alerts/")

    @task(1)
    def create_alert(self):
        """Test alert creation (will fail auth but tests endpoint)"""
        alert_data = {
            "description": "Test alert for performance testing",
            "type": "news",
            "location": {"type": "Point", "coordinates": [-122.4194, 37.7749]},
            "severity": 3,
        }
        # This will return 401 but tests the endpoint performance
        with self.client.post(
            "/alerts/", json=alert_data, catch_response=True
        ) as response:
            if response.status_code in [401, 422]:
                response.success()

    @task(1)
    def get_nearby_alerts(self):
        """Test nearby alerts endpoint"""
        self.client.get("/alerts/nearby?lat=37.7749&lon=-122.4194&radius_km=5")
