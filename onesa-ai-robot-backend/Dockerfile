FROM python:3.11.17-alpine3.24@sha256:d9368b3a5ac59afea7b5d4f2e2aea0941dbf9fdee9c369c5bec00b98244bc929 AS build
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=ghcr.io/astral-sh/uv:0.13.0@sha256:cdc6093146eb3ff6a40107b38f008b789e050e77ad87865e381d9917da55a168 /uv /usr/local/bin/uv
WORKDIR /build
COPY requirements.lock ./
RUN apk upgrade --no-cache && apk add --no-cache 'musl>=1.2.6-r3' 'musl-utils>=1.2.6-r3' && uv pip install --no-cache --require-hashes --prefix=/install -r requirements.lock
FROM python:3.11.17-alpine3.24@sha256:d9368b3a5ac59afea7b5d4f2e2aea0941dbf9fdee9c369c5bec00b98244bc929
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apk upgrade --no-cache && apk add --no-cache 'musl>=1.2.6-r3' 'musl-utils>=1.2.6-r3' && adduser -D -u 10001 onesa && mkdir storage && chown onesa:onesa storage
COPY --from=build /install /usr/local
COPY robot_api ./robot_api
COPY start.sh ./
RUN rm -rf /usr/local/lib/python3.11/ensurepip /usr/local/lib/python3.11/site-packages/pip* /usr/local/lib/python3.11/site-packages/setuptools* /usr/local/lib/python3.11/site-packages/wheel* /usr/local/bin/pip*
USER onesa
EXPOSE 8431
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8431')+'/api/v1/ready',timeout=3)"
CMD ["sh", "/app/start.sh"]
