#!/bin/bash
# Check that base_image references to pipelines-components images use :main tag
# This ensures components reference the latest images rather than specific SHAs or versions

set -euo pipefail

IMAGE_PREFIX="${1:-ghcr.io/kubeflow/pipelines-components}"
EXIT_CODE=0

echo "Checking that base_image references use :main tag..."

for dir in components pipelines; do
    if [ ! -d "$dir" ]; then
        continue
    fi

    while IFS= read -r -d '' file; do
        # Find lines with base_image referencing our images
        while IFS= read -r line; do
            if [ -z "$line" ]; then
                continue
            fi

            # Check if the line uses :main tag
            if echo "$line" | grep -q "${IMAGE_PREFIX}-[^:]*:main"; then
                echo "  ✓ $file: uses :main tag"
            else
                # Extract the actual tag being used
                tag=$(echo "$line" | grep -oE "${IMAGE_PREFIX}-[^\"']*" | head -1)
                echo "  ✗ $file: does not use :main tag"
                echo "    Found: $tag"
                echo "    Expected: ${IMAGE_PREFIX}-<name>:main"
                EXIT_CODE=1
            fi
        done < <(grep -n "base_image.*${IMAGE_PREFIX}" "$file" 2>/dev/null || true)
    done < <(find "$dir" -name "*.py" -type f -print0)
done

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✓ All base_image references use :main tag (or no references found)"
else
    echo ""
    echo "✗ Some base_image references do not use :main tag"
    echo "  Components should reference :main to use the latest images."
    echo "  The CI will override these with PR-specific tags during validation."
fi

exit $EXIT_CODE

