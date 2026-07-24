param(
  [string]$StackName = "eswap-dev",
  [string]$Region = "eu-west-2"
)

$apiUrl = aws cloudformation describe-stacks `
  --stack-name $StackName `
  --region $Region `
  --query "Stacks[0].Outputs[?OutputKey=='ApiBaseUrl'].OutputValue | [0]" `
  --output text

Write-Host "Health endpoint:" -ForegroundColor Cyan
Invoke-RestMethod "$apiUrl/health" | ConvertTo-Json
Write-Host "Public items endpoint:" -ForegroundColor Cyan
Invoke-RestMethod "$apiUrl/items" | ConvertTo-Json -Depth 5
