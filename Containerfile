# Stage 1: Build React dashboard
FROM registry.access.redhat.com/ubi9/nodejs-22-minimal:latest AS frontend
WORKDIR /opt/app-root/src
COPY --chown=1001:0 src/dfd/dashboard/package*.json ./
RUN npm ci
COPY --chown=1001:0 src/dfd/dashboard/ ./
RUN npm run build

# Stage 2: Python runtime
FROM registry.access.redhat.com/ubi9/python-312:latest

USER 1001

WORKDIR /opt/app-root/src
COPY --chown=1001:0 pyproject.toml .
COPY --chown=1001:0 src/ src/
COPY --chown=1001:0 scripts/ scripts/
COPY --chown=1001:0 migrations/ migrations/

# Install Python dependencies
RUN pip install --no-cache-dir .

# Copy built dashboard into the installed package's static directory
COPY --from=frontend --chown=1001:0 /opt/app-root/api/static/ /tmp/static/
RUN cp -r /tmp/static/ "$(python -c 'from pathlib import Path; import dfd.api.main; print(Path(dfd.api.main.__file__).parent)')/static/" \
    && rm -rf /tmp/static

EXPOSE 8080

CMD ["uvicorn", "dfd.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
