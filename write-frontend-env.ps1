param(
  [string]$StackName = "eswap-dev",
  [string]$Region = "eu-west-2"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

$stackJson = aws cloudformation describe-stacks `
  --stack-name $StackName `
  --region $Region `
  --output json

if ($LASTEXITCODE -ne 0) {
  throw "Could not read CloudFormation stack '$StackName'. Check AWS credentials, stack name and region."
}

$stack = ($stackJson | ConvertFrom-Json).Stacks[0]
function Get-Output([string]$Key) {
  return ($stack.Outputs | Where-Object { $_.OutputKey -eq $Key }).OutputValue
}

$apiUrl = Get-Output "ApiBaseUrl"
$awsRegion = Get-Output "AwsRegion"
$userPoolId = Get-Output "CognitoUserPoolId"
$clientId = Get-Output "CognitoUserPoolClientId"

$envContent = @"
VITE_USE_MOCKS=false
VITE_API_BASE_URL=$apiUrl
VITE_AWS_REGION=$awsRegion
VITE_COGNITO_USER_POOL_ID=$userPoolId
VITE_COGNITO_APP_CLIENT_ID=$clientId
"@

$envPath = Join-Path $root "frontend\.env.local"
Set-Content -Path $envPath -Value $envContent -Encoding utf8
Write-Host "Created $envPath" -ForegroundColor Green
Write-Host $envContent
