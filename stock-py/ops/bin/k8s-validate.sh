#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
RAW_OUTPUT_DIR="${OUTPUT_DIR:-$ROOT_DIR/ops/reports/k8s/$(date -u +%Y%m%dT%H%M%SZ)}"
RAW_KUSTOMIZE_PATH="${KUSTOMIZE_PATH:-ops/k8s/base}"
KUBECTL_IMAGE="${KUBECTL_IMAGE:-bitnami/kubectl@sha256:f6dd048d1c14d89ede9636cd6bee0ff0238579c33ea1e51b2fb1a1cfd62ea246}"
KUBECONFORM_IMAGE="${KUBECONFORM_IMAGE:-ghcr.io/yannh/kubeconform@sha256:85dbef6b4b312b99133decc9c6fc9495e9fc5f92293d4ff3b7e1b30f5611823c}"

case "$RAW_OUTPUT_DIR" in
  /*)
    OUTPUT_DIR="$RAW_OUTPUT_DIR"
    ;;
  *)
    OUTPUT_DIR="$ROOT_DIR/$RAW_OUTPUT_DIR"
    ;;
esac

case "$RAW_KUSTOMIZE_PATH" in
  /*)
    ABS_KUSTOMIZE_PATH="$RAW_KUSTOMIZE_PATH"
    ;;
  *)
    ABS_KUSTOMIZE_PATH="$ROOT_DIR/$RAW_KUSTOMIZE_PATH"
    ;;
esac

case "$ABS_KUSTOMIZE_PATH" in
  "$ROOT_DIR"/*)
    RENDER_KUSTOMIZE_PATH="/workspace/${ABS_KUSTOMIZE_PATH#$ROOT_DIR/}"
    ;;
  *)
    echo "KUSTOMIZE_PATH must resolve inside the repository: $ABS_KUSTOMIZE_PATH" >&2
    exit 1
    ;;
esac

mkdir -p "$OUTPUT_DIR"

docker run --rm -v "$ROOT_DIR:/workspace" "$KUBECTL_IMAGE" kustomize "$RENDER_KUSTOMIZE_PATH" > "$OUTPUT_DIR/rendered.yaml"
docker run --rm -v "$OUTPUT_DIR:/output" "$KUBECONFORM_IMAGE" -summary -ignore-missing-schemas /output/rendered.yaml > "$OUTPUT_DIR/validation.txt"
grep '^kind:' "$OUTPUT_DIR/rendered.yaml" | sort | uniq -c > "$OUTPUT_DIR/resource-kinds.txt"

cat > "$OUTPUT_DIR/summary.json" <<EOF
{
  "kustomize_path": "${ABS_KUSTOMIZE_PATH}",
  "render_image": "${KUBECTL_IMAGE}",
  "validation_image": "${KUBECONFORM_IMAGE}",
  "rendered_manifest": "${OUTPUT_DIR}/rendered.yaml",
  "validation_log": "${OUTPUT_DIR}/validation.txt",
  "resource_kinds": "${OUTPUT_DIR}/resource-kinds.txt"
}
EOF

echo "K8s manifests rendered and offline-validated: $OUTPUT_DIR"