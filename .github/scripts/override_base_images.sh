#!/bin/bash
# Override base_image references from :main to PR-specific SHA tags
# Usage: ./override_base_images.sh <commit_sha> [image_prefix]

set -euo pipefail

COMMIT_SHA="${1:-}"
IMAGE_PREFIX="${2:-ghcr.io/kubeflow/pipelines-components}"

if [ -z "$COMMIT_SHA" ]; then
    echo "Usage: $0 <commit_sha> [image_prefix]"
    exit 1
fi

SHORT_SHA="${COMMIT_SHA:0:7}"

echo "Overriding base_image references from :main to :${SHORT_SHA}"

if [ -d "components" ]; then
    find components -name "*.py" -type f | while read -r file; do
        if grep -q "${IMAGE_PREFIX}.*:main" "$file"; then
            echo "Updating: $file"
            sed -i "s|${IMAGE_PREFIX}-\([^:]*\):main|${IMAGE_PREFIX}-\1:${SHORT_SHA}|g" "$file"
        fi
    done
else
    echo "No components directory found"
fi

