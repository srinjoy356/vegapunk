"""Edison: proves PRs with tests that fail before the change and pass after it.

Runs on the Linux host that has Docker (the WSL Ubuntu box), from the project root:

    uv run python -m vegapunk.edison --issue 803 --matrix
    uv run python -m vegapunk.edison --all --matrix --jobs 2

For every PR it runs the PR's changed switch-core test files twice in a sandbox:
on the PR's head, and on its merge base with only those test files copied in.
A test that passes on head and fails (or cannot even be collected) on base proves
the change. The cross matrix runs each rival's tests against each PR's code.
"""
