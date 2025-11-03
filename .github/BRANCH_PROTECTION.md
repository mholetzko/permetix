# Branch Protection Configuration

To enable proper PR workflow, configure the following branch protection rules on GitHub:

## Main Branch Protection

Go to: **Settings → Branches → Add branch protection rule**

### Rule Configuration for `main`:

#### Protect matching branches
- Branch name pattern: `main`

#### Require a pull request before merging
- ✅ Require a pull request before merging
- Required number of approvals before merging: **1** (or 0 for solo dev)
- ✅ Dismiss stale pull request approvals when new commits are pushed
- ✅ Require review from Code Owners (optional)

#### Require status checks to pass before merging
- ✅ Require status checks to pass before merging
- ✅ Require branches to be up to date before merging

**Required status checks:**
- `Test Suite`
- `Code Quality`
- `Docker Build`
- `All Checks Passed`

#### Require conversation resolution before merging
- ✅ Require conversation resolution before merging

#### Require signed commits (optional)
- ✅ Require signed commits (recommended for security)

#### Require linear history
- ✅ Require linear history (keeps history clean)

#### Do not allow bypassing the above settings
- ✅ Do not allow bypassing the above settings (even for admins)

#### Restrict who can push to matching branches
- Leave unchecked if you're the only contributor
- Check if working in a team and specify allowed users/teams

## Automated Setup (using GitHub CLI)

If you have GitHub CLI installed:

```bash
# Install GitHub CLI if needed
brew install gh  # macOS
# or visit https://cli.github.com/

# Login
gh auth login

# Create branch protection rule
gh api repos/:owner/:repo/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["Test Suite","Code Quality","Docker Build","All Checks Passed"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true}' \
  --field required_linear_history=true \
  --field allow_force_pushes=false \
  --field allow_deletions=false
```

## Workflow

1. **Create a branch** for your feature/fix:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make changes and commit**:
   ```bash
   git add .
   git commit -m "feat: add new feature"
   ```

3. **Push to GitHub**:
   ```bash
   git push origin feature/your-feature-name
   ```

4. **Create Pull Request** on GitHub
   - All CI checks must pass
   - Address any review comments
   - Get required approvals

5. **Merge** once all checks pass and reviews are approved

## Commit Message Convention

Follow conventional commits:

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

Examples:
- `feat: add overage charges tracking`
- `fix: resolve cost calculation bug`
- `docs: update deployment instructions`

