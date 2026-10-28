# Build only from the context emitted by scripts/prepare-ollama-runtime.py.
# A cached app image may be supplied on the CT to avoid another base download.
ARG RUNTIME_BASE_IMAGE=python:3.13-slim
FROM ${RUNTIME_BASE_IMAGE}
USER root
LABEL org.opencontainers.image.version="ollama-0.40.11-cpu"
LABEL org.opencontainers.image.source="https://github.com/ollama/ollama/releases/tag/v0.40.11"
LABEL runtime.sha256="7bedab90dd122661be78798e9f0edf37fccf0cccf2699d2c58ea1a3afdc04b6d"
COPY runtime/bin/ollama /usr/bin/ollama
COPY runtime/lib/ollama/ /usr/lib/ollama/
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && ldconfig && /usr/bin/ollama --help >/dev/null
ENV OLLAMA_HOST=127.0.0.1:11434 OLLAMA_NO_CLOUD=1
ENTRYPOINT ["/usr/bin/ollama"]
CMD ["serve"]
