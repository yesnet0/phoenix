FROM python:3.11-slim

WORKDIR /app

RUN pip install poetry && \
    poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-interaction --no-ansi --no-root

RUN playwright install --with-deps chromium

COPY src/ src/

RUN poetry install --no-interaction --no-ansi

CMD ["celery", "-A", "phoenix.core.tasks", "worker", "--loglevel=info", "--concurrency=2"]
