#check=skip=SecretsUsedInArgOrEnv
# Stage 1: Build React frontend
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ARG VITE_RECAPTCHA_SITE_KEY
# Write to .env file before building
RUN echo "VITE_RECAPTCHA_SITE_KEY=$VITE_RECAPTCHA_SITE_KEY" > .env
RUN npm run build

# Stage 2: Python app
FROM python:3.12-slim
WORKDIR /tracker
RUN apt-get update && apt-get install -y pkg-config build-essential libmariadb-dev
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
RUN pip install . gunicorn
COPY --from=frontend-build /frontend/dist /tracker/frontend/dist
EXPOSE 3001 3443
ENV HTTP_PORT=3001
ENV HTTPS_PORT=3443
ENTRYPOINT ["/tracker/start.sh"]
# CMD ["bash", "start.sh"]
