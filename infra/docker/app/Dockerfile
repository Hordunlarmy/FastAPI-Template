FROM python:3.12.3-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install PostgreSQL APT repo + required packages
RUN apt-get update && \
    apt-get install -y curl wget gnupg lsb-release && \
    echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list && \
    wget -qO - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - && \
    apt-get update && \
    apt-get install -y \
        postgresql-client-17 \
        libpq-dev python3-dev build-essential cron && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi --no-root

COPY . .

COPY infra/docker/app/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY script/cronjob/backup.sh /usr/local/bin/backup.sh

RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/backup.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
