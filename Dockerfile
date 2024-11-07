FROM python:3.11-slim

WORKDIR /app

COPY kotiki/entrypoints .

RUN pip install .

CMD ["python", "-m", "kotiki.entrypoints.bot"]
