> **⚠️ Important: Before submitting this PR, please ensure:**
> - Your code follows the project's style guidelines
> - You have performed a self-review of your changes
> - Related issues are linked (if applicable)
> - You have run `./dev/code-style.sh --check` to verify code style, and `./dev/pytest.sh` to ensure all tests pass


## Description

<!-- 
Provide a high-level overview of what this PR does and why it's needed.
Focus on the problem being solved, the motivation, and the overall impact.
Brief description (2-3 sentences).
Examples:
  - This PR adds a new agent capability for SQL query optimization, allowing the agent to automatically suggest and apply performance improvements to user queries.
  - This PR fixes a critical bug where agent context was lost during multi-turn conversations, causing the agent to forget previous interactions and user preferences.
  - This PR refactors the agent loop to improve error handling and make it more resilient to failures, ensuring better user experience during agent execution.
-->


## Type of Change

- [ ] 🐛 Bug fix
- [ ] ✨ New feature
- [ ] 💥 Breaking change
- [ ] 📚 Documentation
- [ ] 🔧 Refactoring

## Related Issues

<!-- 
Link related GitHub issues here. Use the format: #issue_number
Examples:
  - Fixes #123        (This PR fixes issue #123)
  - Related to #789   (This PR is related to issue #789)
  
If no related issue exists, please create one first or leave this section empty.
-->

- Fixes #<!-- Issue number that this PR fixes -->

## Changes Made

<!-- 
List the specific technical changes made in this PR. Be concrete and actionable.
Focus on "what" was changed, not "why" (that's in Description).
Examples:
  - Added SQLOptimizationTool class to tools/mysql/optimization.py
  - Extended NeoLoop with new tool registration method for dynamic tool loading
  - Refactored agent context management to use persistent storage instead of in-memory cache
  - Added unit tests for agent tool execution and error handling scenarios
-->

## Checklist

- [x] I understand that this PR may be closed in case there was no previous discussion or issues.
- [ ] I've added unit tests for each change that was introduced, and I tried as much as possible to make a single atomic change.
- [ ] I've performed manual testing and verified the changes work as expected.
- [ ] I ran `./dev/code-style.sh --check` to verify code style compliance.
- [ ] I ran `./dev/pytest.sh` and all tests pass.
- [ ] This change requires a documentation update <!-- Yes/No, if Yes, please specify which docs need updating -->

