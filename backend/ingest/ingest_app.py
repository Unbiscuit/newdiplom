from fastapi import FastAPI, UploadFile, File, Form
from prometheus_fastapi_instrumentator import Instrumentator
from minio import Minio
from minio.error import S3Error
from confluent_kafka import Producer
from elasticsearch import Elasticsearch
import uuid, io, json, os
from datetime import datetime

# Инициализация клиентов внешних систем на старте приложения:
MINIO_URL = os.getenv("MINIO_URL", "http://minio:9000")
MINIO_ACCESS = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET = os.getenv("MINIO_SECRET_KEY", "admin12345")
ES_URL = os.getenv("ES_URL", "http://elasticsearch:9200")
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")

# Подключение к MinIO (S3)
minio_client = Minio(MINIO_URL.replace("http://", "").replace("https://", ""),
                     access_key=MINIO_ACCESS,
                     secret_key=MINIO_SECRET,
                     secure=False)
# Elasticsearch client (будет использовать REST API Elasticsearch)
es = Elasticsearch(ES_URL)

# Kafka Producer
producer = Producer({'bootstrap.servers': KAFKA_BOOTSTRAP})

# Создаём FastAPI приложение
app = FastAPI(title="Tier-1 Ingest Service")

# Подключаем инструментатор Prometheus (экспорт /metrics)
Instrumentator().instrument(app).expose(app)

@app.get("/health")
def health():
    return {"status": "ok"}

# Маршрут для приёма нового задания
@app.post("/ingest")
async def ingest_task(file: UploadFile = File(...), task_name: str = Form(...)):
    # Читаем содержимое файла (для простоты целиком в память)
    data = await file.read()
    # Создаём бакет, если не существует
    bucket_name = "tasks"
    try:
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)
    except S3Error as err:
        print("MinIO bucket error:", err)
        return {"status": "error", "error": "Storage error"}

    # Генерируем уникальный идентификатор задачи
    task_id = str(uuid.uuid4())
    # Формируем имя объекта в хранилище: <UUID>_<filename>
    object_name = f"{task_id}_{file.filename}"
    try:
        # Сохраняем файл в MinIO (через поток байтов)
        file_bytes = io.BytesIO(data)
        minio_client.put_object(bucket_name, object_name, file_bytes, length=len(data))
    except S3Error as err:
        print("Failed to save file to MinIO:", err)
        return {"status": "error", "error": "Storage error"}

    # Формируем документ метаданных
    timestamp = datetime.utcnow().isoformat() + "Z"
    task_doc = {
        "id": task_id,
        "name": task_name,
        "filename": file.filename,
        "object": object_name,
        "size": len(data),
        "timestamp": timestamp
    }
    # Индексируем метаданные задачи в Elasticsearch
    es.index(index="tasks", id=task_id, document=task_doc)
    # Индексируем событие "получена новая задача" в Elasticsearch
    event_doc = {
        "event": "INGESTED",
        "task_id": task_id,
        "timestamp": timestamp
    }
    es.index(index="events", document=event_doc)

    # Публикуем сообщение в Kafka о новой задаче
    try:
        producer.produce("tasks", json.dumps(task_doc).encode('utf-8'))
        producer.flush()  # сбрасываем, чтобы сообщение точно отправилось:contentReference[oaicite:11]{index=11}
    except Exception as e:
        print("Kafka produce error:", e)
        # (Не прерываем процесс, так как основная операция завершена успешно)

    return {"status": "success", "task_id": task_id}