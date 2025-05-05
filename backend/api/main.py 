from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from elasticsearch import Elasticsearch
from minio import Minio
import os, requests

# Конфигурация из переменных окружения
ES_URL = os.getenv("ES_URL", "http://elasticsearch:9200")
MINIO_URL = os.getenv("MINIO_URL", "http://minio:9000")
MINIO_ACCESS = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET = os.getenv("MINIO_SECRET_KEY", "admin12345")
KEYCLOAK_URL = os.getenv("KEYCLOAK_SERVER_URL", "http://keycloak:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "nica")

# Инициализация клиентов
es = Elasticsearch(ES_URL)
minio_client = Minio(MINIO_URL.replace("http://",""), access_key=MINIO_ACCESS,
                     secret_key=MINIO_SECRET, secure=False)

app = FastAPI(title="Tier-1 API")

# Подключаем сбор метрик Prometheus
Instrumentator().instrument(app).expose(app)

# Настраиваем CORS, чтобы фронтенд (http://localhost:3000) мог обращаться к API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ "http://localhost:3000" ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Определяем схему аутентификации Bearer
bearer_scheme = HTTPBearer()

# Зависимость для проверки JWT через Keycloak
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    token = credentials.credentials
    # Запрос к Keycloak UserInfo endpoint для проверки токена
    resp = requests.get(f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/userinfo",
                        headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        # Не удалось подтвердить токен
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user_info = resp.json()
    # Здесь можно извлечь информацию о пользователе (например, username)
    return user_info

# Endpoint: список задач (с поиском)
@app.get("/tasks")
async def list_tasks(q: str = None, current_user: dict = Depends(get_current_user)):
    # Если задан параметр q, ищем по имени (full-text search)
    if q:
        # match по полю name
        query_body = { "match": { "name": q } }
    else:
        query_body = { "match_all": {} }
    try:
        result = es.search(index="tasks", query=query_body, size=100)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Search error")
    hits = result.get("hits", {}).get("hits", [])
    tasks = [ hit["_source"] for hit in hits ]
    return tasks

# Endpoint: получить информацию о конкретной задаче
@app.get("/tasks/{task_id}")
async def get_task(task_id: str, current_user: dict = Depends(get_current_user)):
    try:
        res = es.get(index="tasks", id=task_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail="Task not found")
    task_doc = res.get("_source")
    if not task_doc:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_doc

# Endpoint: получить данные/файл задачи
@app.get("/data/{task_id}")
async def download_task_data(task_id: str, current_user: dict = Depends(get_current_user)):
    # Получаем информацию о задаче, чтобы узнать имя объекта в MinIO
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
    # Генерируем presigned URL для скачивания
    try:
        url = minio_client.presigned_get_object(bucket, object_name, expires=3600)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error generating download URL")
    return { "url": url }

# Endpoint: получить список событий
@app.get("/events")
async def list_events(current_user: dict = Depends(get_current_user)):
    try:
        result = es.search(index="events", sort="timestamp:desc", size=100)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Events search error")
    hits = result.get("hits", {}).get("hits", [])
    events = [ hit["_source"] for hit in hits ]
    return events

# Endpoint: проверка здоровья (доступен без токена)
@app.get("/health")
async def health():
    return {"status": "ok"}