FROM python:3.12.3-slim

WORKDIR /workspace/c54

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y curl screen netcat-openbsd libpq-dev python3-dev build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Add Poetry to the PATH
ENV PATH="/root/.local/bin:$PATH"

COPY pyproject.toml poetry.lock ./

# Install dependencies without creating a virtual environment
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi --no-root


COPY . .

COPY docker/scripts/app-entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8001


# Set the entrypoint
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

