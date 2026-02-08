# Multi-Account Snapshot Command

Take snapshots across multiple AWS accounts in sequence.

## Task

You are helping the user take AWS inventory snapshots across multiple AWS accounts.

## Steps

1. **Read the account configuration** from `~/.aws/config` to identify all configured AWS profiles
   - Use `grep -E "^\[profile " ~/.aws/config | sed 's/\[profile //g' | sed 's/\]//g'` to list profiles
   - Or ask the user which profiles they want to snapshot

2. **Ask the user for configuration:**
   - Which AWS profiles to include (or use all profiles)
   - Which regions to scan (default: us-east-1,us-west-2)
   - Snapshot naming pattern (default: snapshot-YYYYMMDD)
   - Whether to run in parallel or sequence (recommend sequence for safety)

3. **For each AWS profile**, execute these commands in sequence:
   ```bash
   # Validate credentials
   aws sts get-caller-identity --profile <profile-name>

   # Create inventory (if it doesn't exist, ignore error if exists)
   awsinv --profile <profile-name> inventory create <profile-name>-baseline \
     --description "Baseline snapshot for <profile-name> account"

   # Take snapshot
   awsinv --profile <profile-name> snapshot create "snapshot-$(date +%Y%m%d)" \
     --region <regions> \
     --inventory <profile-name>-baseline
   ```

4. **Track progress** using the TodoWrite tool:
   - Create a todo for each account
   - Mark completed as you finish each account
   - Show progress indicator

5. **Handle errors gracefully**:
   - If credentials fail for an account, skip and continue
   - If inventory creation fails (already exists), continue
   - If snapshot fails, log error and continue to next account
   - Keep track of successes and failures

6. **Generate summary report** at the end:
   ```
   📊 Multi-Account Snapshot Summary

   ✅ Successfully snapshotted:
      - account1 (123456789012) - 245 resources
      - account2 (234567890123) - 189 resources
      - account3 (345678901234) - 312 resources

   ❌ Failed accounts:
      - account4: credential error
      - account5: network timeout

   📈 Total: 5 accounts, 3 succeeded (746 resources), 2 failed
   ⏱️  Duration: 12 minutes
   ```

## Configuration

User can customize:
- Which AWS profiles to include/exclude
- Which regions to scan (default: us-east-1, us-west-2)
- Snapshot naming pattern (default: snapshot-YYYYMMDD)
- Whether to create inventories automatically (default: yes)
- Parallel vs sequential execution (default: sequential for safety)

## Examples

**Basic usage:**
```
/snapshot-all-accounts
```

**Advanced usage (in conversation):**
```
/snapshot-all-accounts

User: Only snapshot dev-*, staging-*, and prod-* profiles
User: Use regions us-east-1 and eu-west-1
User: Name snapshots "weekly-baseline-YYYYMMDD"
```

## Notes

- This can take 5-15 minutes depending on number of accounts and resources
- Sequential execution is safer to avoid rate limiting
- Parallel execution is faster but may hit AWS API rate limits
- Always validate credentials before starting snapshot
- Store results in account-specific inventories for isolation
- Show real-time progress using Rich progress bars or simple status updates

## Safety

- Always confirm with user before starting multi-account operations
- Show which accounts will be scanned before starting
- Allow user to review and approve the account list
- Provide option to dry-run (show what would be done without doing it)
