import logging
import time

from fastapi import FastAPI, Request

from app.routers import tasks, users

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger("app.requests")

app = FastAPI(title="Task Manager API", version="1.0.0")


@app.middleware("http")
async def process_time_middleware(request: Request, call_next):
    """Добавляет заголовок X-Process-Time и логирует метод, путь, статус и время."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    response.headers["X-Process-Time"] = f"{elapsed:.4f}"
    logger.info(
        "%s %s -> %d (%.2f ms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed * 1000,
    )
    return response


app.include_router(users.router)
app.include_router(tasks.router)
