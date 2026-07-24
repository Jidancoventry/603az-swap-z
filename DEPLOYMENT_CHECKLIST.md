# E-Swap Deployment Checklist

## Local frontend

- [ ] Node.js 22.12+ installed
- [ ] `npm install` completed
- [ ] `npm run dev` opens `http://localhost:5173`
- [ ] Mock login works
- [ ] Mock create/list/request flow works

## Amplify

- [ ] Repository connected
- [ ] App root is `frontend`
- [ ] Initial mock deployment succeeds
- [ ] Amplify domain copied
- [ ] SPA rewrite added
- [ ] Security headers applied from `customHttp.yml`

## Backend

- [ ] AWS identity checked with `aws sts get-caller-identity`
- [ ] `python -m unittest discover -s tests -v` passes
- [ ] `sam validate --lint` passes
- [ ] `sam build` passes
- [ ] `sam deploy --guided` completes
- [ ] CloudFormation outputs recorded
- [ ] `/health` returns `status: ok`

## Real frontend connection

- [ ] `.env.local` generated from stack outputs
- [ ] `VITE_USE_MOCKS=false`
- [ ] Register email arrives
- [ ] Confirmation succeeds
- [ ] Login succeeds
- [ ] Image uploads to S3
- [ ] Listing appears in DynamoDB
- [ ] Listing appears in Browse after refresh
- [ ] Edit own listing succeeds
- [ ] Delete own listing succeeds

## Security

- [ ] Anonymous POST `/items` returns 401
- [ ] User B cannot edit User A item
- [ ] S3 Block Public Access is on
- [ ] Admin page fails for normal user
- [ ] Admin user can moderate a listing
- [ ] CloudWatch logs show success and rejected requests

## Demonstration evidence

- [ ] Live Amplify URL
- [ ] Cognito user and Admin group screenshot
- [ ] API Gateway routes and JWT authorizer screenshot
- [ ] Lambda function screenshot
- [ ] DynamoDB item record screenshot
- [ ] S3 image object screenshot
- [ ] CloudWatch log screenshot
- [ ] Browser showing persistent listing
- [ ] Failed 401 or 403 security test screenshot
- [ ] GitHub commit/deployment history screenshot
