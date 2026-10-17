FROM docker.1ms.run/library/python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai \
    PLAYWRIGHT_DOWNLOAD_HOST=https://cdn.npmmirror.com/binaries/playwright

COPY backend/requirements.txt .
RUN sed -i 's@deb.debian.org@mirrors.tuna.tsinghua.edu.cn@g' \
      /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list 2>/dev/null || true \
 && pip install --no-cache-dir -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
 && playwright install --with-deps chromium

COPY backend /app/backend
COPY frontend /app/frontend

VOLUME ["/app/data"]
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "/app/backend"]
