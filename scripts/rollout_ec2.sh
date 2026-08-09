#!/usr/bin/env bash
set -euo pipefail

# Roll out the currently checked-out CompanyAgent image to a single EC2 demo
# host. This script deliberately requires an existing root-owned env file and
# never accepts or prints secret values on the command line.

: "${EC2_HOST:?Set EC2_HOST to the target host or public DNS name}"
: "${EC2_SSH_KEY:?Set EC2_SSH_KEY to the SSH private-key path}"
EC2_USER="${EC2_USER:-ubuntu}"
REMOTE_ENV_FILE="${REMOTE_ENV_FILE:-/etc/companyagent/companyagent.env}"
IMAGE_NAME="${IMAGE_NAME:-companyagent:integration}"
CONTAINER_NAME="${CONTAINER_NAME:-companyagent}"
ARCHIVE="${ARCHIVE:-$(mktemp --suffix=.tar)}"
REMOTE_ARCHIVE="/tmp/companyagent-image-$$.tar"

cleanup() { rm -f "$ARCHIVE"; }
trap cleanup EXIT

docker build --tag "$IMAGE_NAME" .
docker save "$IMAGE_NAME" --output "$ARCHIVE"
scp -i "$EC2_SSH_KEY" -o StrictHostKeyChecking=accept-new "$ARCHIVE" \
  "$EC2_USER@$EC2_HOST:$REMOTE_ARCHIVE"

ssh -i "$EC2_SSH_KEY" -o StrictHostKeyChecking=accept-new "$EC2_USER@$EC2_HOST" \
  "REMOTE_ENV_FILE='$REMOTE_ENV_FILE' REMOTE_ARCHIVE='$REMOTE_ARCHIVE' IMAGE_NAME='$IMAGE_NAME' CONTAINER_NAME='$CONTAINER_NAME' bash -s" <<'REMOTE'
set -euo pipefail
test -r "$REMOTE_ENV_FILE" || { echo "missing root-owned env file: $REMOTE_ENV_FILE" >&2; exit 1; }
for key in BACKBOARD_API_KEY COMPANYAGENT_API_KEY CANARY_TARGET_VERIFICATION_TOKEN; do
  grep -Eq "^${key}=.+$" "$REMOTE_ENV_FILE" || {
    echo "required secret is missing from $REMOTE_ENV_FILE: $key" >&2
    exit 1
  }
done

sudo docker load --input "$REMOTE_ARCHIVE" >/dev/null
old_name="${CONTAINER_NAME}-previous"
sudo docker rm -f "$old_name" >/dev/null 2>&1 || true
if sudo docker inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
  sudo docker rename "$CONTAINER_NAME" "$old_name"
  sudo docker stop "$old_name" >/dev/null
fi

rollback() {
  sudo docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
  if sudo docker inspect "$old_name" >/dev/null 2>&1; then
    sudo docker rename "$old_name" "$CONTAINER_NAME"
    sudo docker start "$CONTAINER_NAME" >/dev/null
  fi
  exit 1
}
trap rollback ERR

sudo docker run --detach --name "$CONTAINER_NAME" --restart unless-stopped \
  --publish 80:8000 --env-file "$REMOTE_ENV_FILE" "$IMAGE_NAME" >/dev/null
for attempt in $(seq 1 30); do
  if curl --fail --silent --show-error --max-time 3 http://127.0.0.1/health >/dev/null; then
    trap - ERR
    sudo docker rm "$old_name" >/dev/null 2>&1 || true
    rm -f "$REMOTE_ARCHIVE"
    echo "CompanyAgent rollout healthy"
    exit 0
  fi
  sleep 2
done
echo "CompanyAgent did not become healthy; rolling back" >&2
rollback
REMOTE
