Scan the repo for anything that shouldn't be committed:
1. Search all tracked and untracked files for patterns matching API keys
   (sk-ant-, sk-, AKIA, anything base64-looking after "key"/"token"/"secret")
2. Confirm .env is in .gitignore and is NOT tracked by git (git ls-files .env
   should return nothing)
3. Check git log for any commit that touched .env or hardcoded a credential
4. Check dev-logs/prompts.md and README.md for accidentally pasted secrets

Report findings as a pass/fail list. If anything fails, say exactly what
file and line, and whether it's already committed (which needs history
rewriting) or just present locally (which just needs .gitignore).
