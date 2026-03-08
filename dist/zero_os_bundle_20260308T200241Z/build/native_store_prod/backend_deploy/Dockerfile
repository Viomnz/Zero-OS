FROM python:3.12-slim
WORKDIR /app
COPY src /app/src
ENV PYTHONPATH=/app/src
CMD ["python", "-c", "from zero_os.native_store_backend import run_server; run_server('/app')"]
