# DFD Deployment Guide

## Prerequisites

- OpenShift cluster with `oc` CLI configured
- `podman` or `buildah` for local image builds
- Quay.io account (or other container registry) with push access
- GCP service account credentials (JSON key file) for Vertex AI / Claude
- AWS S3 bucket with IAM user access
- KubeArchive API token

## 1. Build the Container Image

Single image used for both API and Collector:

```bash
podman build -f Containerfile -t YOUR_REGISTRY/dfd:latest .
podman push YOUR_REGISTRY/dfd:latest
```

## 2. Create the Namespace

```bash
oc apply -f manifests/namespace/namespace.yaml
oc apply -f manifests/namespace/serviceaccount.yaml
```

## 3. Create Secrets

### a) Database — generate a random password

```bash
DB_PASS=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 24)
oc create secret generic dfd-database -n dfd \
  --from-literal=username=dfd \
  --from-literal=password="$DB_PASS" \
  --from-literal=database=dfd \
  --from-literal=url="postgresql://dfd:${DB_PASS}@dfd-postgresql:5432/dfd"
```

### b) KubeArchive

```bash
oc create secret generic dfd-kubearchive -n dfd \
  --from-literal=base-url="$KUBEARCHIVE_URL" \
  --from-literal=token="$KUBEARCHIVE_TOKEN"
```

### c) Vertex AI

```bash
oc create secret generic dfd-vertex-ai -n dfd \
  --from-literal=project-id="$GOOGLE_CLOUD_PROJECT" \
  --from-literal=region="$GOOGLE_CLOUD_REGION"
```

### d) AWS credentials — copy from existing namespace or create new

```bash
oc create secret generic dfd-aws-credentials -n dfd \
  --from-literal=access-key-id="$AWS_ACCESS_KEY_ID" \
  --from-literal=secret-access-key="$AWS_SECRET_ACCESS_KEY"
```

### e) AWS S3

```bash
oc create secret generic dfd-aws-s3 -n dfd \
  --from-literal=bucket="$S3_BUCKET" \
  --from-literal=region="$AWS_REGION"
```

### f) GCP credentials

```bash
oc create secret generic dfd-gcp-credentials -n dfd \
  --from-file=credentials.json=/path/to/your/credentials.json
```

### g) OAuth proxy cookie

```bash
oc create secret generic dfd-oauth-proxy-cookie -n dfd \
  --from-literal=cookie-secret=$(openssl rand -base64 32)
```

## 4. Create ConfigMap

```bash
oc apply -f manifests/configmaps/dfd-config.yaml
```

## 5. Deploy PostgreSQL

```bash
oc apply -f manifests/postgresql/pvc.yaml
oc apply -f manifests/postgresql/service.yaml
oc apply -f manifests/postgresql/statefulset.yaml
oc apply -f manifests/postgresql/backup-cronjob.yaml
```

Wait for PostgreSQL to be ready:

```bash
oc wait --for=condition=Ready pod/dfd-postgresql-0 -n dfd --timeout=120s
```

## 6. Run Database Migrations

```bash
DB_PASS=$(oc get secret dfd-database -n dfd -o jsonpath='{.data.password}' | base64 -d)
oc port-forward svc/dfd-postgresql 15432:5432 -n dfd &
sleep 5
DATABASE_URL="postgresql://dfd:${DB_PASS}@localhost:15432/dfd" python scripts/migrate.py
kill %1
```

## 7. Deploy API

```bash
oc apply -f manifests/api/service.yaml
oc apply -f manifests/api/deployment.yaml
oc apply -f manifests/api/route.yaml
```

The API deployment includes an OAuth proxy sidecar (port 8443) with TLS reencrypt
route. Users authenticate via OpenShift OAuth.

```bash
oc rollout status deployment/dfd-api -n dfd
oc get route dfd-api -n dfd -o jsonpath='{.spec.host}'
```

## 8. Deploy Collector

```bash
oc apply -f manifests/collector/deployment.yaml
oc rollout status deployment/dfd-collector -n dfd
```

## 9. Verify

```bash
# All pods should be Running
oc get pods -n dfd

# API route (will return 403 without OAuth — use browser for login)
oc get route dfd-api -n dfd -o jsonpath='https://{.spec.host}{"\n"}'

# Collector should be fetching pipeline runs
oc logs deployment/dfd-collector -n dfd --tail=30
```

## Architecture

```
┌─────────────────────────────────────┐
│ OpenShift Namespace: dfd           │
│                                     │
│  ┌───────────┐   ┌───────────────┐  │
│  │ dfd-api  │   │ dfd-collector│  │
│  │ (uvicorn) │   │ (poller loop) │  │
│  │ :8080     │   │               │  │
│  │           │   │               │  │
│  │ + oauth   │   │               │  │
│  │   proxy   │   │               │  │
│  │   :8443   │   │               │  │
│  └─────┬─────┘   └───────┬───────┘  │
│        │                  │          │
│  ┌─────┴──────────────────┴───────┐  │
│  │     dfd-postgresql :5432      │  │
│  │     (StatefulSet + 10Gi PVC)   │  │
│  └────────────────────────────────┘  │
│                                     │
│  External: AWS S3,                   │
│            Vertex AI, KubeArchive   │
└─────────────────────────────────────┘
```

Both `dfd-api` and `dfd-collector` use the same container image
with different entry points.
