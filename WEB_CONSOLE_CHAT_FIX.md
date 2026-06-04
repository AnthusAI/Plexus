# Web Console Chat IAM Fix

## Problem

Production web console chat was failing when users attempted to invoke Plexus tools/procedures. The console chat responder Lambda function lacked necessary IAM permissions to read secrets from AWS Systems Manager Parameter Store (SSM).

## Root Cause

The `consoleRunWorker` Lambda function (ConsoleChatResponderStack) had:
- ✅ AppSync GraphQL permissions
- ✅ CloudWatch Logs permissions  
- ✅ Secrets Manager read permissions (for config secret)
- ❌ **MISSING: SSM Parameter Store permissions**

When the Lambda attempted to read JWT signing secrets or other parameters from SSM using boto3's `get_parameters()` or `get_parameter()` APIs, AWS denied the request with `AccessDeniedException`.

## The Fix

**File**: `dashboard/amplify/functions/consoleRunWorker/resource.ts`

Added SSM IAM policy to the Lambda execution role:

```typescript
// SSM Parameter Store permissions for console chat JWT and other secrets
this.responderFunction.addToRolePolicy(
  new PolicyStatement({
    effect: Effect.ALLOW,
    actions: [
      "ssm:GetParameter",   // Single parameter reads
      "ssm:GetParameters",  // Batch parameter reads
    ],
    resources: [
      `arn:aws:ssm:*:*:parameter/plexus/*`,
      `arn:aws:ssm:*:*:parameter/amplify/*`,
    ],
  }),
);
```

This grants the Lambda permission to:
1. Read individual SSM parameters (`GetParameter`)
2. Read multiple SSM parameters in batch (`GetParameters`)
3. Access parameters under `/plexus/*` and `/amplify/*` paths

## Testing Instructions

### Prerequisites
- AWS credentials configured with access to production account
- Access to CloudWatch Logs
- Access to DynamoDB console

### Test Steps

1. **Deploy the fix**:
   ```bash
   cd /workspace/dashboard
   npx ampx sandbox  # For sandbox testing
   # OR
   npx amplify deploy  # For production
   ```

2. **Verify Lambda IAM permissions**:
   ```bash
   # Get the Lambda function name from CloudFormation outputs
   aws lambda get-policy --function-name <console-responder-function-name>
   
   # Or check in AWS Console:
   # Lambda → Functions → ConsoleChatResponderFunction → Configuration → Permissions
   # Verify "ssm:GetParameter" and "ssm:GetParameters" are listed
   ```

3. **Manual test - Web console**:
   - Navigate to the dashboard (e.g., https://dashboard.plexus.example.com)
   - Open console chat interface
   - Send a message that invokes tools: "list the 5 most recent references"
   - **Expected**: Response appears within 10-60 seconds
   - **Failure**: No response or error message about JWT/secrets

4. **Check CloudWatch Logs**:
   ```bash
   # View recent Lambda invocations
   aws logs tail /aws/lambda/ConsoleChatResponderFunction --follow
   
   # Look for these success indicators:
   # - "processed": 1 (not 0)
   # - No "AccessDeniedException" errors
   # - No "Could not resolve JWT signing secret" errors
   ```

5. **Check DynamoDB**:
   - Open DynamoDB console
   - Navigate to `ChatMessage` table
   - Find recent USER messages
   - Verify corresponding ASSISTANT responses exist
   - Check `responseStatus` field is "COMPLETED" (not "FAILED")

## Expected Behavior After Fix

| Scenario | Before Fix | After Fix |
|----------|------------|-----------|
| User sends chat message | AccessDeniedException in logs | Message processes successfully |
| Lambda reads SSM params | Denied | Allowed |
| Console tools/procedures | Fail with JWT error | Execute successfully |
| Response appears in UI | ❌ Never | ✅ Within 10-60s |

## Rollback Instructions

If this fix causes issues:

1. **Quick rollback** (revert IAM permissions):
   ```bash
   cd /workspace
   git revert <commit-hash>
   cd dashboard
   npx amplify deploy
   ```

2. **Emergency console fix** (temporarily disable SSM reads):
   - This isn't recommended as it will break console chat functionality
   - Better to fix the underlying issue

## Related Files

- `dashboard/amplify/functions/consoleRunWorker/resource.ts` - IAM fix applied here
- `dashboard/amplify/functions/consoleRunWorker/app.py` - Lambda handler
- `plexus/console/chat_runtime.py` - Console chat processing logic
- `plexus/cli/procedure/service.py` - Procedure service (may call execute_tactus)

## Status

- [x] Issue identified
- [x] Fix implemented
- [ ] TypeScript validation (needs `tsc` properly installed)
- [ ] Deployed to production
- [ ] Manual testing completed
- [ ] CloudWatch logs verified
- [ ] Team notified of fix

## Notes

- This fix mirrors a similar issue resolved in the Papyrus Slack integration (see Slack thread from June 2-3, 2026)
- SSM Parameter Store is separate from Secrets Manager - both are AWS secrets services but require different IAM permissions
- The fix grants broad access to `/plexus/*` and `/amplify/*` parameter paths - consider tightening to specific parameter names if known
