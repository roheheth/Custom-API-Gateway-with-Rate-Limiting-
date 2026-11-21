ROUTES_CONFIG = [
    {
        "route": "/api/users",
        "target": "http://user-service:5051",
        "protected": False
    },
    {
        "route": "/api/products",
        "target": "http://product-service:5052",
        "protected": False
    },
    {
        "route": "/api/orders",
        "target": "http://order-service:5053",
        "protected": True
    },
    {
        "route": "/auth",
        "target": "http://auth-service:5054",
        "protected": True
    }
]
