FROM python:3.12-slim-bookworm

# Immutable upstream source: see UPSTREAM.md. No Docker socket or nested Docker.
ARG OPENCOOK_REF=a60375d0d73f275ec1f70b687ce89ff389c553d9
RUN pip install --no-cache-dir \
    "https://github.com/oliexdev/openCook/archive/${OPENCOOK_REF}.tar.gz#subdirectory=server" \
    && groupadd --gid 10001 opencook \
    && useradd --uid 10001 --gid opencook --no-create-home opencook

COPY rootfs/ /
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]
ENTRYPOINT ["python", "/opt/opencook/launch.py"]
