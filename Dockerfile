FROM python:3.6-slim-stretch
EXPOSE 8000
RUN apt update && apt install -y curl
HEALTHCHECK --interval=5m --timeout=3s CMD curl --fail http://127.0.0.1:8000/ || exit 1

ENV PYTHONUNBUFFERED 1
RUN /usr/local/bin/pip install --upgrade pip setuptools wheel
RUN /usr/local/bin/pip install aiohttp

COPY . /app
WORKDIR /app
CMD ["/usr/local/bin/python", "-m", "aiohttp.web", "-H", "0.0.0.0", "-P", "8000", "mancala:main_web"]

