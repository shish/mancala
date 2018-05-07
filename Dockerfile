FROM python:3.6-stretch
EXPOSE 8000

ENV PYTHONUNBUFFERED 1
RUN apt update
RUN /usr/local/bin/pip install --upgrade pip setuptools wheel
RUN /usr/local/bin/pip install aiohttp

COPY . /app
WORKDIR /app
CMD ["/usr/local/bin/python", "-m", "aiohttp.web", "-H", "localhost", "-P", "8000", "mancala:main_web"]

