FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt requirements-cloud.txt ./
RUN pip install --no-cache-dir -r requirements-cloud.txt
COPY backend/ ./backend/
COPY migrations/ ./migrations/
COPY alembic.ini run.py ./
COPY --from=frontend /build/frontend/dist ./frontend/dist
RUN useradd --create-home chronosync && mkdir /app/data && chown chronosync:chronosync /app/data
USER chronosync
EXPOSE 10000
CMD ["python", "run.py"]
