# E-Swap Full-Stack AWS Cloud Application

This repository contains a working university prototype of E-Swap using:

- React + Vite frontend
- AWS Amplify Hosting
- Amazon Cognito registration, email confirmation, login and Admin group
- Amazon API Gateway HTTP API with JWT authorisation
- AWS Lambda Python backend
- Amazon DynamoDB for listings and requests
- Amazon S3 private image storage with presigned upload/download URLs
- Amazon CloudWatch logs, API access logs and X-Ray tracing
- AWS SAM / CloudFormation infrastructure as code

The code has two modes:

- `VITE_USE_MOCKS=true`: run locally before AWS is ready; data persists in browser local storage.
- `VITE_USE_MOCKS=false`: use the real AWS backend.

## What works

1. Register and confirm an account through Cognito.
2. Login and logout.
3. Create a listing with an image.
4. Upload the image securely to private S3.
5. Store listing data in DynamoDB.
6. Browse active listings and view details.
7. View, edit and delete your own listings.
8. Send Exchange, Purchase, Donation or Recycling requests.
9. Accept, reject or cancel requests.
10. Moderate listings as a Cognito Admin user.
11. View operations in CloudWatch.

---

# Part 1 — Run locally in mock mode

## Prerequisites

Install:

- Node.js 22.12 or newer
- Visual Studio Code
- Git

Open PowerShell in the project folder and run:

```powershell
cd frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

Keep this in `frontend/.env.local` for now:

```env
VITE_USE_MOCKS=true
```

Mock-mode tips:

- Any email/password can log in.
- An email beginning with `admin` becomes a mock Admin, for example `admin@test.com`.
- Newly created mock listings persist after browser refresh because they are stored in local storage.

Before continuing, test:

```text
Login → Create listing → My listings → Browse → Item details → Send request
```

---

# Part 2 — Push the complete project to GitHub

From the project root:

```powershell
git init
git add .
git commit -m "Initial E-Swap full-stack cloud application"
git branch -M main
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```

Do not commit `.env.local`, AWS access keys or temporary AWS Academy credentials.

---

# Part 3 — Deploy the frontend to Amplify first

Deploying it first gives you the real Amplify domain needed for API and S3 CORS.

1. Open AWS Amplify.
2. Choose **Create new app**.
3. Select GitHub and connect your repository.
4. Select branch `main`.
5. The repository is a monorepo. Use app root `frontend` if Amplify asks.
6. The root `amplify.yml` already contains the build settings.
7. Add this environment variable initially:

```text
VITE_USE_MOCKS=true
```

8. Deploy.
9. Copy the Amplify URL, for example:

```text
https://main.d123example.amplifyapp.com
```

## Add the React single-page-app rewrite

In Amplify open:

```text
Hosting → Rewrites and redirects
```

Add a `200 rewrite`:

```text
Source:
</^[^.]+$|\.(?!(css|gif|ico|jpg|jpeg|js|png|txt|svg|woff|woff2|ttf|map|webp)$)([^.]+$)/>

Target:
/index.html

Type:
200 (Rewrite)
```

This prevents a 404 when refreshing `/dashboard`, `/browse` or another React route.

---

# Part 4 — Deploy the AWS backend with SAM

## Install tools

Install:

- AWS CLI
- AWS SAM CLI
- Python 3.12 or newer for local tests

Check:

```powershell
aws --version
sam --version
python --version
```

## Configure AWS credentials

For a normal AWS account:

```powershell
aws configure
```

Use region:

```text
eu-west-2
```

For AWS Academy / university lab credentials, use the temporary CLI credentials supplied by the lab. They expire, so renew them when AWS returns an expired-token error. Never put them in frontend code.

Confirm your identity:

```powershell
aws sts get-caller-identity
```

## Run backend tests

```powershell
cd backend
python -m unittest discover -s tests -v
```

## Validate and build

```powershell
sam validate --lint
sam build
```

## Deploy

Replace the example domain with your actual Amplify URL:

```powershell
sam deploy --guided --parameter-overrides StageName=dev FrontendOrigin=https://main.d123example.amplifyapp.com AutoApproveListings=true
```

Recommended answers:

```text
Stack Name: eswap-dev
AWS Region: eu-west-2
Confirm changes before deploy: Y
Allow SAM CLI IAM role creation: Y
Disable rollback: N
Save arguments to configuration file: Y
```

`AutoApproveListings=true` makes new listings immediately visible for the first successful demo.

After the core system works, redeploy with:

```powershell
sam deploy --parameter-overrides StageName=dev FrontendOrigin=https://main.d123example.amplifyapp.com AutoApproveListings=false
```

Then new listings become `Pending` until an Admin approves them.

## If your university lab blocks deployment

The template creates IAM roles, Cognito, API Gateway, Lambda, DynamoDB, S3, CloudWatch log groups and X-Ray tracing. If the lab permission boundary blocks one of these, capture the exact CloudFormation error and ask the module team to allow that service. Do not grant yourself AdministratorAccess.

---

# Part 5 — Connect the local frontend to AWS

Return to the project root and run:

```powershell
.\scripts\write-frontend-env.ps1 -StackName eswap-dev -Region eu-west-2
```

This reads CloudFormation outputs and creates `frontend/.env.local`:

```env
VITE_USE_MOCKS=false
VITE_API_BASE_URL=https://API_ID.execute-api.eu-west-2.amazonaws.com
VITE_AWS_REGION=eu-west-2
VITE_COGNITO_USER_POOL_ID=eu-west-2_XXXXXXXXX
VITE_COGNITO_APP_CLIENT_ID=XXXXXXXXXXXXXXXXXXXXXXXXXX
```

These are application configuration values, not secret AWS credentials.

Restart Vite:

```powershell
cd frontend
npm run dev
```

Now test the real flow:

1. Register a new account.
2. Check email for the Cognito confirmation code.
3. Confirm the account.
4. Login.
5. Create a listing with a JPG, PNG or WebP image under 5 MB.
6. Open My listings.
7. Refresh the browser.
8. Open Browse and confirm the item remains visible.
9. Open DynamoDB and confirm the item record exists.
10. Open S3 and confirm the image object exists.
11. Open CloudWatch and confirm the Lambda invocation exists.

---

# Part 6 — Connect the Amplify deployment to AWS

In Amplify open:

```text
Hosting → Environment variables
```

Add the values from `frontend/.env.local`:

```text
VITE_USE_MOCKS=false
VITE_API_BASE_URL=...
VITE_AWS_REGION=eu-west-2
VITE_COGNITO_USER_POOL_ID=...
VITE_COGNITO_APP_CLIENT_ID=...
```

Redeploy the branch.

After deployment, perform the same registration and listing test using the Amplify URL.

---

# Part 7 — Create an Admin account

1. Register and confirm the intended administrator through the E-Swap UI.
2. Add the user to the Cognito `Admin` group.

PowerShell option:

```powershell
.\scripts\add-admin.ps1 -Email YOUR_EMAIL -StackName eswap-dev -Region eu-west-2
```

Console option:

```text
Cognito → User pools → eswap-users-dev → Groups → Admin → Add user
```

Log out and log in again so Cognito issues a new token containing the Admin group.

The frontend will display the Admin page, but the real security check happens again inside Lambda.

---

# Part 8 — Demonstrate two-user requests

Use two separate browsers or one normal window and one incognito window.

```text
User A → creates a listing
User B → opens the listing and sends an Exchange request
User A → opens Requests and accepts or rejects it
```

The request is stored in the `ESwapRequests-dev` DynamoDB table.

---

# AWS resources created

| Resource | Purpose |
|---|---|
| Amplify Hosting | Builds and hosts the React frontend |
| Cognito User Pool | Registration, verification, login and Admin group |
| HTTP API | Public and protected REST-style routes |
| JWT authorizer | Validates Cognito tokens before protected routes run |
| Lambda | Validation, ownership rules, CRUD and request processing |
| DynamoDB Items table | Persistent item listings |
| DynamoDB Requests table | Persistent user requests |
| Private S3 bucket | Item images |
| CloudWatch | Function logs and API access logs |
| X-Ray | Request tracing |

---

# API routes

## Public

```text
GET /health
GET /items
GET /items/{itemId}
```

## Authenticated

```text
POST   /items
GET    /my-items
PATCH  /items/{itemId}
DELETE /items/{itemId}
POST   /uploads/presign
POST   /requests
GET    /my-requests
PATCH  /requests/{requestId}
```

## Admin

```text
GET   /admin/items
PATCH /admin/items/{itemId}
```

---

# Security evidence to explain

- The frontend contains no AWS access keys.
- Cognito issues the signed JWT.
- API Gateway validates issuer, audience and expiry before protected Lambda routes run.
- Lambda takes `ownerId` from the verified JWT, not from user-submitted form data.
- Users cannot update or delete another user's listing.
- Admin actions require the Cognito `Admin` group and are checked in Lambda.
- S3 blocks all public access.
- Images use short-lived presigned PUT and GET URLs.
- File type and maximum 5 MB size are validated.
- DynamoDB point-in-time recovery and server-side encryption are enabled.
- S3 server-side encryption is enabled.
- CORS permits localhost and the configured Amplify origin.
- CloudWatch retention is configured for 14 days.

---

# Common errors

## `npm is not recognised`

Close and reopen VS Code after installing Node.js. In PowerShell, `npm.cmd` can be used if execution policy blocks `npm.ps1`.

## `NotAuthorizedException` during login

Confirm the user account using the emailed Cognito code. Check that the frontend uses the correct User Pool ID and Client ID.

## `401 Unauthorized`

Log out and log in again. Check the API URL, User Pool ID, App Client ID and region. Confirm the protected API route has the JWT authorizer.

## CORS error

Make sure `FrontendOrigin` exactly matches the Amplify origin, without a trailing slash. Redeploy the backend after changing it.

## S3 upload returns 403

Check that the browser sends the same `Content-Type` used to create the presigned URL. Confirm the image is JPG, PNG or WebP and no larger than 5 MB.

## Listing saves but does not appear in Browse

Check its DynamoDB `status`:

- `Active`: should appear publicly.
- `Pending`: approve it through the Admin page, or deploy with `AutoApproveListings=true`.

## `ExpiredToken` from AWS CLI or SAM

University lab credentials have expired. Start or refresh the lab and replace the temporary CLI credentials.

---

# Remove the backend after assessment

S3 buckets must be empty before deletion:

```powershell
aws s3 rm s3://YOUR_IMAGE_BUCKET --recursive --region eu-west-2
sam delete --stack-name eswap-dev --region eu-west-2
```

Do not delete the stack until you have collected all screenshots and completed your demonstration.
