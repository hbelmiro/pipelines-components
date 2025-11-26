# Contributing to Kubeflow Pipelines Components

## Adding a Custom Base Image

Components that require specific dependencies beyond what's available in standard KFP images can use custom base images. This section explains how to add and maintain custom base images for your components.

### Overview

Custom base images are:
- Built automatically by CI on every push to `main` and on tags
- Published to `ghcr.io/kubeflow/pipelines-components-<name>`
- Tagged with `:main` for the latest main branch build, plus git SHA and ref tags

### Step 1: Create the Containerfile

Create a `Containerfile` in your component's directory:

```
components/
└── training/
    └── my_component/
        ├── Containerfile      # Your custom base image
        ├── component.py
        ├── metadata.yaml
        └── README.md
```

Example `Containerfile`:

```dockerfile
FROM python:3.11-slim

RUN pip install --no-cache-dir \
    numpy==1.26.0 \
    pandas==2.1.0 \
    scikit-learn==1.3.0

WORKDIR /app
```

**Guidelines:**
- Keep images minimal - only include dependencies your component needs
- Pin dependency versions for reproducibility
- Use official base images when possible
- Avoid including secrets or credentials

### Step 2: Add Entry to the Workflow Matrix

Edit `.github/workflows/container-build.yml` and add your image to the matrix:

```yaml
strategy:
  matrix:
    include:
      # Existing entries...
      
      # Add your new image:
      - name: my-training-component
        containerfile: components/training/my_component/Containerfile
        context: components/training/my_component
```

**Matrix fields:**

| Field           | Description                                                                                              |
|-----------------|----------------------------------------------------------------------------------------------------------|
| `name`          | Unique identifier for your image. The final image will be `ghcr.io/kubeflow/pipelines-components-<name>` |
| `containerfile` | Path to your Containerfile relative to repo root                                                         |
| `context`       | Build context directory (usually the component directory)                                                |

**Naming convention:**
- Use lowercase with hyphens: `my-training-component`
- Be descriptive: `sklearn-preprocessing`, `pytorch-training`
- The full image path will be: `ghcr.io/kubeflow/pipelines-components-my-training-component`

### Step 3: Reference the Image in Your Component

In your `component.py`, use the `base_image` parameter with the `:main` tag:

```python
from kfp import dsl

@dsl.component(
    base_image="ghcr.io/kubeflow/pipelines-components-my-training-component:main"
)
def my_component(input_path: str) -> str:
    import pandas as pd
    import sklearn
    
    # Your component logic here
    ...
```

**Important:** Always use the `:main` tag during development. This ensures:
- Your component uses the latest image from the main branch
- PR validation can override the tag to test against PR-built images

### Step 4: Update metadata.yaml (Optional)

Document the base image in your component's `metadata.yaml`:

```yaml
tier: core
name: my_component
stability: alpha
base_image: ghcr.io/kubeflow/pipelines-components-my-training-component:main
dependencies:
  kubeflow:
    - name: Pipelines
      version: '>=2.5'
```

### How CI Handles Base Images

| Event                        | Behavior                                                                           |
|------------------------------|------------------------------------------------------------------------------------|
| Pull Request                 | Images are built but **not pushed**. Validation runs against locally-built images. |
| Push to `main`               | Images are built and pushed with tags: `:main`, `:<sha>`                           |
| Push to tag (e.g., `v1.0.0`) | Images are built and pushed with tags: `:<tag>`, `:<sha>`                          |

### Image Tags

Your image will be available with these tags:

| Tag         | Description                   | Example                      |
|-------------|-------------------------------|------------------------------|
| `:main`     | Latest build from main branch | `...-my-component:main`      |
| `:<sha>`    | Specific commit (7 chars)     | `...-my-component:abc1234`   |
| `:<branch>` | Branch name                   | `...-my-component:feature-x` |
| `:<tag>`    | Git tag                       | `...-my-component:v1.0.0`    |

### Testing Your Image Locally

Before submitting a PR, test your image locally:

```bash
# Build the image
podman build -t my-component:test -f components/training/my_component/Containerfile components/training/my_component

# Test it
podman run --rm my-component:test python -c "import pandas; print(pandas.__version__)"
```
