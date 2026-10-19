FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/
COPY migrations/ migrations/
COPY scripts/ scripts/
COPY alembic.ini init_demo.py administrar.py ./
COPY data/ data/
COPY static/ static/
RUN mkdir -p /app/storage/uploads && chown -R 10001:10001 /app/storage
USER 10001
EXPOSE 8000
CMD ["sh","-c","exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --no-access-log --no-proxy-headers --limit-concurrency 8 --timeout-keep-alive 5"]
