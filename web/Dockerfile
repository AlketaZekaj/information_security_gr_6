# Image for the keys, evaluation and web services in docker-compose.yml: Python plus the
# generator's dependencies. The repository is mounted at /repo, so code and data stay on the host.
FROM python:3.13.15-slim-bookworm@sha256:2325bb286ec344af3e5898cc224b5844e2707ac6e26b1632516fd3edc84a5e26
# git lets the harness record the measured commit in run.json.
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip pip install -r /tmp/requirements.txt
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /repo
EXPOSE 8765
CMD ["python", "web/server.py", "--host", "0.0.0.0"]
