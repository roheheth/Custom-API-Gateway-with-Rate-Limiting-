import uuid
from locust import HttpUser, task, between

class APIUser(HttpUser):
    # Simulate a delay between 1 and 3 seconds between tasks
    wait_time = between(1, 3)

    def on_start(self):
        # Generate a unique virtual user for registration and login
        self.username = f"locust_{uuid.uuid4().hex[:8]}"
        self.password = "pass123"
        self.token = None

        # 1. Register User
        register_payload = {
            "username": self.username,
            "password": self.password,
            "role": "premium"  # Register as premium to test the 20 req/min limit
        }
        
        # We disable redirect and warnings for cleaner logs
        response = self.client.post("/auth/register", json=register_payload)
        if response.status_code == 201:
            # 2. Login User to get JWT token
            login_payload = {
                "username": self.username,
                "password": self.password
            }
            login_response = self.client.post("/auth/login", json=login_payload)
            if login_response.status_code == 200:
                self.token = login_response.json().get("token")

    @task(3)
    def view_users(self):
        # Query the unprotected User Service
        self.client.get("/api/users")

    @task(3)
    def view_products(self):
        # Query the unprotected Product Service
        self.client.get("/api/products")

    @task(4)
    def view_orders(self):
        # Query the protected Order Service (requires token)
        if self.token:
            headers = {"Authorization": f"Bearer {self.token}"}
            # We allow 429 status code responses so Locust doesn't mark them as failures
            # since rate limiting is expected behavior under heavy loads.
            with self.client.get("/api/orders", headers=headers, catch_response=True) as response:
                if response.status_code == 200:
                    response.success()
                elif response.status_code == 429:
                    response.success()  # It's a successful test of the rate limiter!
                else:
                    response.failure(f"Unexpected status code: {response.status_code}")
        else:
            # If token wasn't fetched, hit the endpoint anyway (should get 401)
            self.client.get("/api/orders")
