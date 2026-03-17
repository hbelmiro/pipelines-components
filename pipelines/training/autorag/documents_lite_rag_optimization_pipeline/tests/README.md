# Documents Lite RAG Optimization Pipeline – Tests

This directory contains unit and integration tests for the Documents Lite RAG Optimization pipeline.

## Test types

| Test file | Type | Description |
| --------- | ------ | ------------- |
| `test_pipeline_unit.py` | Unit | Pipeline structure and interface (no cluster). |
| `test_pipeline_local.py` | Local | Skipped; pipeline requires secrets and model URLs (run via integration test). |
| `test_pipeline_integration.py` | Integration | Runs the Lite pipeline on a RHOAI cluster and validates success (and optional S3 artifacts). |

Unit tests run with the default test suite. Integration tests are **skipped** unless the required environment variables are set (see below).

## Running tests

From the repository root:

```bash
# Unit tests only
uv run python -m pytest pipelines/training/autorag/documents_lite_rag_optimization_pipeline/tests/test_pipeline_unit.py -v

# All tests (integration skipped if env not set)
uv run python -m pytest pipelines/training/autorag/documents_lite_rag_optimization_pipeline/tests/ -v

# Integration tests only (skip when env not set)
uv run python -m pytest pipelines/training/autorag/documents_lite_rag_optimization_pipeline/tests/test_pipeline_integration.py -v
```

Or via the repo test runner:

```bash
uv run python -m scripts.tests.run_component_tests pipelines/training/autorag/documents_lite_rag_optimization_pipeline
```

## Integration test setup

Integration tests require:

- A **Red Hat OpenShift AI (RHOAI)** cluster with **Data Science Pipelines** enabled.
- **Environment variables** for the KFP API URL, token, namespace, and pipeline parameters. The **Lite** pipeline uses **chat and embedding model URLs and tokens** (OpenAI-compatible endpoints), not llama-stack secrets. Secrets for test/input data must exist in the cluster.

### 1. Configure environment

Copy the template and fill in your values:

```bash
cp .env.example .env
# Edit .env with your RHOAI URL, token, project name, and pipeline parameters.
```

Variables are loaded from a `.env` file in this directory (or from the current working directory). See `integration_config.py` for the exact keys and logic.

### 2. Required environment variables

| Variable | Description |
| -------- | ----------- |
| `RHOAI_KFP_URL` | KFP API base URL. Alternative: `KFP_HOST`. |
| `RHOAI_TOKEN` | Bearer token for API auth (e.g. `oc whoami -t`). Alternative: `KFP_TOKEN`. |
| `RHOAI_PROJECT_NAME` | KFP namespace / project. Alternative: `KFP_NAMESPACE`. |
| `TEST_DATA_SECRET_NAME` | Kubernetes secret name for test data S3 credentials. |
| `TEST_DATA_BUCKET_NAME` | S3 bucket for the test data JSON file. |
| `TEST_DATA_KEY` | Object key (path) of the test data file in the bucket. |
| `INPUT_DATA_SECRET_NAME` | Kubernetes secret name for input documents S3 credentials. |
| `INPUT_DATA_BUCKET_NAME` | S3 bucket for input documents. |
| `INPUT_DATA_KEY` | Object key (path) of the input documents in the bucket. |
| `CHAT_MODEL_URL` | Inference endpoint URL for the chat/generation model (OpenAI-compatible). |
| `CHAT_MODEL_TOKEN` | API token for the chat model endpoint. |
| `EMBEDDING_MODEL_URL` | Inference endpoint URL for the embedding model. |
| `EMBEDDING_MODEL_TOKEN` | API token for the embedding model endpoint. |

### 3. Optional: artifact validation in S3

To assert that run artifacts are present in object storage, set:

| Variable | Description |
| -------- | ----------- |
| `AWS_S3_ENDPOINT` | S3-compatible endpoint (e.g. MinIO). |
| `AWS_ACCESS_KEY_ID` | Access key for artifact bucket. |
| `AWS_SECRET_ACCESS_KEY` | Secret key. |
| `AWS_DEFAULT_REGION` | Region (default `us-east-1`). |
| `RHOAI_TEST_ARTIFACTS_BUCKET` | Bucket where pipeline artifacts are stored. |

### 4. Optional: test behavior

| Variable | Description |
| -------- | ----------- |
| `RHOAI_PIPELINE_RUN_TIMEOUT` | Timeout in seconds for waiting on a run (default `3600`). |
| `KFP_VERIFY_SSL` | Set to `false` to skip TLS verification for self-signed certs. |

## Test layout

- **`integration_config.py`** – Loads `.env` and builds `DOCRAG_LITE_INTEGRATION_CONFIG`; used by `conftest.py` and the integration test for skip logic and config.
- **`conftest.py`** – Pytest fixtures: `docrag_lite_integration_config`, `kfp_client`, `compiled_pipeline_path`, `pipeline_run_timeout`, `s3_client`. The compiled pipeline is sanitized to ASCII to avoid backend MySQL "Incorrect string value" for non-ASCII in the manifest.
- **`test_pipeline_integration.py`** – Submits the compiled Lite pipeline with arguments from config, waits for completion, asserts success, and optionally checks for artifacts in S3.
- **`.env.example`** – Template for required and optional env vars; copy to `.env` and fill in (committable; `.env` is gitignored).

## Pipeline parameters in integration tests

The integration test passes the **required** Lite pipeline parameters only (secret names, bucket names, keys, chat/embedding URLs and tokens).
Optional parameters (`optimization_metric`, `optimization_max_rag_patterns`) can be added to `integration_config.py` and `_pipeline_arguments_from_config()` if needed.

## Troubleshooting

### 500 Internal Server Error / "Incorrect string value" for `PipelineRuntimeManifest`

If the run fails with a 500 and a message like `Incorrect string value: '...' for column ... PipelineRuntimeManifest`, the KFP backend is storing the workflow manifest in a MySQL (or MariaDB) column that does not support the full UTF-8 range.
The `compiled_pipeline_path` fixture sanitizes the compiled pipeline YAML to ASCII before submitting. If the error persists, the cluster database may need to use `utf8mb4` (see the main Documents RAG Optimization pipeline tests README for links and details).
