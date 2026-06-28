import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SITE_URL = os.getenv("SITE_URL", "https://your-site.onrender.com")
OWNER_ID = int(os.getenv("OWNER_ID", 5391287151))