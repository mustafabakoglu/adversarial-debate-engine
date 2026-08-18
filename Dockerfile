# One image, one service, one URL: the API also serves the built frontend, which is
# what a reviewer needs to click. Node builds the UI, Python runs everything.
FROM node:22-alpine AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /srv

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STATIC_DIR=/srv/static

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/demos ./demos
COPY --from=ui /ui/dist ./static

# Hosts that inject $PORT (Render, Railway, Fly) work without changes; 8123 locally.
ENV PORT=8123
EXPOSE 8123
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
