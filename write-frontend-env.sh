#!/usr/bin/env bash
set -euo pipefail

STACK_NAME="${1:-eswap-dev}"
REGION="${2:-eu-west-2}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

value() {
  aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue | [0]" \
    --output text
}

cat > "$ROOT_DIR/frontend/.env.local" <<ENV
VITE_USE_MOCKS=false
VITE_API_BASE_URL=$(value ApiBaseUrl)
VITE_AWS_REGION=$(value AwsRegion)
VITE_COGNITO_USER_POOL_ID=$(value CognitoUserPoolId)
VITE_COGNITO_APP_CLIENT_ID=$(value CognitoUserPoolClientId)
ENV

echo "Created frontend/.env.local"
cat "$ROOT_DIR/frontend/.env.local"
