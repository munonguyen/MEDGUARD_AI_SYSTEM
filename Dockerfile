FROM node:22-alpine AS ui
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/medguard
COPY requirements*.txt ./
RUN pip install --no-cache-dir -r requirements-production.txt && useradd --uid 10001 --create-home medguard
COPY --chown=medguard:medguard app ./app
COPY --chown=medguard:medguard datasets ./datasets
COPY --from=ui --chown=medguard:medguard /build/app/static ./app/static
USER medguard
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-access-log"]
