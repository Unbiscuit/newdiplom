from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from elasticsearch import Elasticsearch
from minio import Minio
from jose import jwt, JWTError
from jose.exceptions import ExpiredSignatureError
from jwt import PyJWKClient
from fastapi.responses import StreamingResponse
from datetime import timedelta
import os
import logging

# --- Логгирование ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Конфигурация окружения ---
ES_URL = os.getenv("ES_URL", "http://elasticsearch:9200")
MINIO_URL = os.getenv("MINIO_URL", "http://minio:9000")
MINIO_ACCESS = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET = os.getenv("MINIO_SECRET_KEY", "admin12345")
KEYCLOAK_URL = os.getenv("KEYCLOAK_SERVER_URL", "http://keycloak:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "nica")

# --- Инициализация клиентов ---
es = Elasticsearch(ES_URL)
minio_client = Minio(MINIO_URL.replace("http://", ""), access_key=MINIO_ACCESS,
                     secret_key=MINIO_SECRET, secure=False)

app = FastAPI(title="Tier-1 API")

# --- Метрики ---
Instrumentator().instrument(app).expose(app)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- JWT ---
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
            options={"verify_exp": True, "verify_aud": False},
        )
        logger.info("Token verified successfully: %s", decoded.get("sub"))
        return decoded
    except ExpiredSignatureError:
        logger.warning("Token expired")
        raise HTTPException(status_code=401, detail="Token expired")
    except JWTError as e:
        logger.error("JWT verification failed: %s", str(e))
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    return verify_token(credentials.credentials)

# --- Endpoints ---

@app.get("/tasks")
async def list_tasks(q: str = None, current_user: dict = Depends(get_current_user)):
    query_body = {"match": {"name": q}} if q else {"match_all": {}}
    try:
        result = es.search(index="tasks", query=query_body, size=100)
        hits = result.get("hits", {}).get("hits") or []
        tasks = [hit["_source"] for hit in hits]
        return tasks
    except Exception as e:
        logger.exception("Elasticsearch task search error")
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

@app.get("/tasks/{task_id}")
async def get_task(task_id: str, current_user: dict = Depends(get_current_user)):
    try:
        res = es.get(index="tasks", id=task_id)
        task_doc = res.get("_source")
        if not task_doc:
            raise HTTPException(status_code=404, detail="Task not found")
        return task_doc
    except Exception as e:
        logger.exception("Error getting task")
        raise HTTPException(status_code=404, detail=f"Task not found: {str(e)}")

@app.get("/data/{task_id}")
async def stream_task_data(task_id: str, current_user: dict = Depends(get_current_user)):
    try:
        res = es.get(index="tasks", id=task_id)
        task_doc = res.get("_source")
        if not task_doc:
            raise HTTPException(status_code=404, detail="Task not found")

        object_name = task_doc.get("object")
        filename = task_doc.get("filename", "data.bin")

        if not object_name:
            raise HTTPException(status_code=500, detail="Missing object name in task metadata")

        stream = minio_client.get_object("tasks", object_name)
        return StreamingResponse(stream, media_type="application/octet-stream", headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        })
    except Exception as e:
        logger.exception("MinIO streaming error")
        raise HTTPException(status_code=500, detail=f"Streaming error: {str(e)}")

@app.get("/events")
async def list_events(current_user: dict = Depends(get_current_user)):
    try:
        result = es.search(index="events", sort="timestamp:desc", size=100)
        hits = result.get("hits", {}).get("hits") or []
        events = [hit["_source"] for hit in hits]
        return events
    except Exception as e:
        logger.exception("Elasticsearch events search error")
        raise HTTPException(status_code=500, detail=f"Events search error: {str(e)}")

@app.get("/health")
async def health():
    return {"status": "ok"}
