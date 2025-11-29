import os
from dotenv import load_dotenv

load_dotenv() 

COMPANY_CREATION_PIN = os.getenv("COMPANY_CREATION_PIN")
DATABASE_URL = os.getenv("DATABASE_URL")

# Edge API Basic Auth
EDGE_API_USERNAME = os.getenv("EDGE_API_USERNAME")
EDGE_API_PASSWORD = os.getenv("EDGE_API_PASSWORD")

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# Redis Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_USER = os.getenv("REDIS_USER", "")
REDIS_PASS = os.getenv("REDIS_PASS", "")
KEY_PREFIX = os.getenv("KEY_PREFIX", "app")

# S3/MinIO Configuration
S3_HOST = os.getenv("S3_HOST", "localhost")
S3_PORT = os.getenv("S3_PORT", "9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "anpr-images")