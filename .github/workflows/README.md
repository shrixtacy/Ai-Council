# GitHub Workflows Documentation

This directory contains automated workflows for the AI Council Orchestrator project.

## 📋 Workflows Overview

### 1. CI/CD Pipeline (`ci.yml`)
**Trigger:** Push to main/develop, PRs to main

**Purpose:** Automated testing and building

**Features:**
- Tests across Python 3.8, 3.9, 3.10, 3.11, 3.12
- Code linting with flake8
- Code formatting check with black
- Import sorting check with isort
- Type checking with mypy
- Test coverage with pytest
- Codecov integration
- Package building and validation

---

### 2. Issue Auto-Assignment (`issue-assignment.yml`)
**Trigger:** Issue opened, issue comment created

**Purpose:** Automatically assign issues to contributors

**Features:**

#### Auto-assign to Issue Creator
When someone creates an issue, they are automatically assigned to it with a welcome message.

**Example:**
```
User creates issue #42
→ Issue #42 is assigned to the user
→ Bot posts: "🎯 Issue Auto-Assigned! Hey @user! This issue has been automatically assigned to you..."
```

#### Assign on Comment (for Repo Owner Issues)
When the repo owner creates an issue, the first person to comment with assignment keywords gets assigned.

**Assignment Keywords:**
- "assign me"
- "assign this to me"
- "i want to work on this"
- "can i work on this"

**Example:**
```
Repo owner creates issue #43
User comments: "I want to work on this"
→ Issue #43 is assigned to the user
→ Bot posts: "🎉 Issue Assigned! Congratulations @user! This issue has been assigned to you..."
```

**Protection:**
- Only works on issues created by repo owner
- Prevents double assignment
- Notifies if issue is already assigned

---

### 3. PR Issue Link Checker (`pr-issue-checker.yml`)
**Trigger:** PR opened, edited, or synchronized

**Purpose:** Ensure all PRs are linked to issues

**Features:**

#### Detects Issue Links
Searches PR title and description for:
- `Fixes #123`
- `Closes #456`
- `Resolves #789`
- Direct issue references: `#42`
- Full GitHub URLs

#### Validates Issues
- Checks if referenced issues exist
- Verifies issues are open
- Identifies closed or non-existent issues

#### Provides Feedback

**When PR has valid linked issues:**
```
✅ Issue Link Status
Great job @user! This PR is linked to the following issue(s):
- Closes #42
- Closes #123
```

**When PR has no linked issues:**
```
⚠️ Issue Link Status
Hey @user! It looks like this PR doesn't have a linked issue.

Please do one of the following:
1️⃣ Link to an existing open issue
2️⃣ Create a new issue first
3️⃣ Mark as new issue (if urgent)
```

**Smart Features:**
- Removes old bot comments to avoid clutter
- Updates on PR edits
- Provides clear instructions
- Explains why linking is important

---

### 4. Issue Welcome Message (`issue-create-automate-message.yml`)
**Trigger:** Issue opened

**Purpose:** Welcome new issue creators

**Features:**
- Thanks contributors
- Links to important documentation
- Reminds about assignment process
- Encourages proper workflow

---

### 5. PR Welcome Message (`pr-create-automate-message.yml`)
**Trigger:** PR opened

**Purpose:** Welcome PR creators and provide checklist

**Features:**
- Thanks contributors
- Provides pre-review checklist
- Explains review process
- Sets expectations

---

## 🔧 How to Use

### For Contributors

#### Creating an Issue
1. Create your issue with a clear description
2. You'll be automatically assigned
3. Read the welcome message and linked docs
4. Start working on the issue

#### Claiming a Repo Owner's Issue
1. Find an issue created by the repo owner
2. Comment: "assign me" or "I want to work on this"
3. Wait for automatic assignment
4. Start working once assigned

#### Creating a PR
1. Ensure you're assigned to an issue
2. Create your PR
3. Link it to the issue using `Fixes #<number>` in the description
4. The bot will verify the link
5. Address any feedback from the bot or reviewers

### For Repo Owners

#### Creating Issues for Others
1. Create an issue with `[Help Wanted]` or similar tag
2. Don't assign it to anyone initially
3. First person to comment with assignment keywords gets it
4. Bot handles the assignment automatically

#### Managing PRs
1. Bot automatically checks for linked issues
2. Review the bot's feedback on each PR
3. Ensure contributors link their PRs properly
4. Merge when all checks pass

---

## 🛠️ Customization

### Modifying Assignment Keywords
Edit `.github/workflows/issue-assignment.yml`:
```yaml
const assignmentKeywords = ['assign me', 'assign this to me', 'your custom keyword'];
```

### Changing Issue Link Patterns
Edit `.github/workflows/pr-issue-checker.yml`:
```yaml
const issuePatterns = [
  /your-custom-pattern/gi,
  // Add more patterns
];
```

### Adjusting Messages
All bot messages are defined in the workflow files and can be customized to match your project's tone.

---

## 🔐 Permissions

All workflows use minimal required permissions:
- `issues: write` - To assign issues and add comments
- `pull-requests: write` - To comment on PRs

---

## 🐛 Troubleshooting

### Issue not auto-assigned
- Check if the workflow has proper permissions
- Verify GitHub Actions are enabled for the repo
- Check workflow run logs in Actions tab

### PR link checker not working
- Ensure PR description contains proper keywords
- Use `Fixes #123` format (case-insensitive)
- Check if the referenced issue exists and is open

### Bot comments not appearing
- Verify `pull_request_target` is used (not `pull_request`)
- Check if bot has write permissions
- Review workflow logs for errors

---

## 📊 Workflow Status

Check the status of all workflows in the **Actions** tab of your repository.

---

## 🤝 Contributing to Workflows

To improve these workflows:
1. Test changes in a fork first
2. Document any new features
3. Update this README
4. Submit a PR with clear description

---

**Last Updated:** February 2026
**Maintained by:** AI Council Orchestrator Team
