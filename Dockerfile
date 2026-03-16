# Stage 1: Build frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend + serve frontend static files
FROM python:3.12-slim
WORKDIR /app

# Install Python deps
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend code
COPY backend/ backend/

# Copy frontend build from stage 1
COPY --from=frontend-build /app/frontend/dist frontend/dist

# Railway sets PORT env var
ENV PORT=8000
EXPOSE $PORT

CMD ["sh", "-c", "python -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT"]
