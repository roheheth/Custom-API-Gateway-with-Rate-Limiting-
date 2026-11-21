import time
import uuid
import pytest
import httpx

BASE_URL = "http://127.0.0.1:5050"

@pytest.fixture(scope="module")
def client():
    # Use httpx Client for synchronous requests in test cases
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as c:
        yield c

def test_gateway_health(client):
    # Test that the gateway is online and responding
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Custom API Gateway Running"}
    assert "x-frame-options" in response.headers

def test_unprotected_routes(client):
    # Test forwarding to User Service
    user_response = client.get("/api/users")
    assert user_response.status_code == 200
    assert user_response.json()["service"] == "User Service"
    assert "users" in user_response.json()

    # Test forwarding to Product Service
    product_response = client.get("/api/products")
    assert product_response.status_code == 200
    assert product_response.json()["service"] == "Product Service"
    assert "products" in product_response.json()

def test_protected_route_without_token(client):
    # Test that access is blocked on protected routes without JWT
    response = client.get("/api/orders")
    assert response.status_code == 401
    assert response.json() == {"message": "No token provided"}

def test_auth_flow(client):
    # Create a unique username using uuid to avoid conflicts
    username = f"user_{uuid.uuid4().hex[:6]}"
    password = "password123"

    # 1. Register User
    reg_response = client.post(
        "/auth/register",
        json={"username": username, "password": password, "role": "premium"}
    )
    assert reg_response.status_code == 201
    assert reg_response.json()["message"] == "User registered successfully"

    # 2. Login with wrong password (Expect 401)
    login_fail = client.post(
        "/auth/login",
        json={"username": username, "password": "wrongpassword"}
    )
    assert login_fail.status_code == 401
    assert login_fail.json() == {"detail": "Invalid username or password"}

    # 3. Login with correct credentials (Expect 200 + token)
    login_ok = client.post(
        "/auth/login",
        json={"username": username, "password": password}
    )
    assert login_ok.status_code == 200
    token = login_ok.json().get("token")
    assert token is not None

    # 4. Access protected route with token
    headers = {"Authorization": f"Bearer {token}"}
    orders_response = client.get("/api/orders", headers=headers)
    assert orders_response.status_code == 200
    assert orders_response.json()["service"] == "Order Service"
    assert "orders" in orders_response.json()

def test_rate_limiter_free_tier(client):
    # Create a free user to test the 5-request rate limit threshold
    username = f"free_{uuid.uuid4().hex[:6]}"
    password = "password123"

    # Register & Login as free tier
    client.post(
        "/auth/register",
        json={"username": username, "password": password, "role": "free"}
    )
    login_res = client.post(
        "/auth/login",
        json={"username": username, "password": password}
    )
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Clean previous Redis rate limit state if any by sleeping 1 second 
    # (IP based key will be fresh since we use new queries in loop)
    time.sleep(1.0)

    # Send 5 requests (all should succeed)
    for _ in range(5):
        resp = client.get("/api/orders", headers=headers)
        assert resp.status_code == 200

    # 6th request should trigger 429 Too Many Requests
    blocked_resp = client.get("/api/orders", headers=headers)
    assert blocked_resp.status_code == 429
    assert blocked_resp.json() == {"message": "Too many requests", "limit": 5}
