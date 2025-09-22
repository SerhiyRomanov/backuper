FROM python:3.13-slim AS builder

WORKDIR /app

#RUN apt-get update && \
#    apt-get install -y --no-install-recommends gcc python3-dev build-essential pkg-config

COPY ./src/requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# main image
FROM python:3.13-slim

RUN mkdir -p /app && addgroup --system app && adduser --system --group app
ENV APP_HOME=/app
WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends yq cron tar pigz && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder $APP_HOME/wheels /wheels
RUN pip install --no-cache /wheels/*
COPY ./src $APP_HOME

RUN chown -R app:app $APP_HOME

COPY ./entrypoint.sh /
RUN chmod +x /entrypoint.sh

USER app
ENTRYPOINT ["/entrypoint.sh"]
