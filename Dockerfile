ARG IMAGE=python:3.11-alpine

FROM $IMAGE as builder

RUN pip install poetry==1.5.1

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

COPY . /app

RUN poetry install --without dev --without lsp

FROM $IMAGE as runtime

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}
COPY . /app

ENTRYPOINT ["keymap"]
