import os

# Tests never need a real secret; CI and local runs both work without a .env file.
os.environ.setdefault("SECRET_KEY", "test-only-not-secret")
