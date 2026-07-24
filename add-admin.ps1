param(
  [Parameter(Mandatory=$true)][string]$Email,
  [string]$StackName = "eswap-dev",
  [string]$Region = "eu-west-2"
)

$ErrorActionPreference = "Stop"
$userPoolId = aws cloudformation describe-stacks `
  --stack-name $StackName `
  --region $Region `
  --query "Stacks[0].Outputs[?OutputKey=='CognitoUserPoolId'].OutputValue | [0]" `
  --output text

aws cognito-idp admin-add-user-to-group `
  --user-pool-id $userPoolId `
  --username $Email `
  --group-name Admin `
  --region $Region

if ($LASTEXITCODE -ne 0) { throw "Could not add the user to the Admin group." }
Write-Host "Added $Email to the Cognito Admin group. Log out and log in again to obtain a new token." -ForegroundColor Green
