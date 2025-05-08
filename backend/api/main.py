from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from elasticsearch import Elasticsearch
from minio import Minio
from jose import jwt
from jwt import PyJWKClient
from jose.exceptions import JWTError
import os

# --- Конфигурация окружения ---
ES_URL = os.getenv("ES_URL", "http://elasticsearch:9200")
MINIO_URL = os.getenv("MINIO_URL", "http://minio:9000")
MINIO_ACCESS = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET = os.getenv("MINIO_SECRET_KEY", "admin12345")
KEYCLOAK_URL = os.getenv("KEYCLOAK_SERVER_URL", "http://keycloak:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "nica")
KEYCLOAK_AUDIENCE = "tier1-frontend"  # client_id из Keycloak

# --- Инициализация клиентов ---
es = Elasticsearch(ES_URL)
minio_client = Minio(MINIO_URL.replace("http://", ""), access_key=MINIO_ACCESS,
                     secret_key=MINIO_SECRET, secure=False)

app = FastAPI(title="Tier-1 API")

# --- Метрики ---
Instrumentator().instrument(app).expose(app)

# --- CORS для фронтенда ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- JWT проверка ---
bearer_scheme = HTTPBearer()
JWKS_URL = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
jwks_client = PyJWKClient(JWKS_URL)

def verify_token(token: str) -> dict:
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_exp": True, "verify_aud": False}
        )
        return decoded
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    return verify_token(credentials.credentials)

# --- Эндпоинты API ---
@app.get("/tasks")
async def list_tasks(q: str = None, current_user: dict = Depends(get_current_user)):
    query_body = {"match": {"name": q}} if q else {"match_all": {}}
    try:
        result = es.search(index="tasks", query=query_body, size=100)
    except Exception:
        raise HTTPException(status_code=500, detail="Search error")
    hits = result.get("hits", {}).get("hits", [])
    tasks = [hit["_source"] for hit in hits]
    return tasks

@app.get("/tasks/{task_id}")
async def get_task(task_id: str, current_user: dict = Depends(get_current_user)):
    try:
        res = es.get(index="tasks", id=task_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Task not found")
    task_doc = res.get("_source")
    if not task_doc:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_doc

@app.get("/data/{task_id}")
async def download_task_data(task_id: str, current_user: dict = Depends(get_current_user)):
    try:
        res = es.get(index="tasks", id=task_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Task not found")
    task_doc = res.get("_source")
    if not task_doc:
        raise HTTPException(status_code=404, detail="Task not found")
    bucket = "tasks"
    object_name = task_doc.get("object")
    if not object_name:
        raise HTTPException(status_code=500, detail="Object name not found in metadata")
    try:
        url = minio_client.presigned_get_object(bucket, object_name, expires=3600)
    except Exception:
        raise HTTPException(status_code=500, detail="Error generating download URL")
    return {"url": url}

@app.get("/events")
async def list_events(current_user: dict = Depends(get_current_user)):
    try:
        result = es.search(index="events", sort="timestamp:desc", size=100)
    except Exception:
        raise HTTPException(status_code=500, detail="Events search error")
    hits = result.get("hits", {}).get("hits", [])
    events = [hit["_source"] for hit in hits]
    return events

@app.get("/health")
async def health():
    return {"status": "ok"}