FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt backend/
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY config/ config/
COPY demo_cache/ demo_cache/
COPY --from=web /web/dist frontend/dist

# hugging face spaces runs the container as uid 1000 and expects port 7860
ENV BLINK_CACHE=/tmp/blink-cache PORT=7860
EXPOSE 7860
CMD uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $PORT --workers 1
