from vegapunk.ingest import link, linked_issues, maintainer_comments


def pr(number, body="", refs=(), created="2026-11-04T00:00:00Z"):
    return {"number": number, "body": body, "createdAt": created,
            "closingIssuesReferences": {"nodes": [{"number": n} for n in refs]}}


def test_linked_issues_merges_recorded_links_and_body_keywords():
    p = pr(1, body="Closes #803, also fixes: #771 and resolved #5. See #900.", refs=[802])
    assert linked_issues(p) == {802, 803, 771, 5}


def test_linked_issues_ignores_plain_mentions_and_missing_body():
    assert linked_issues(pr(1, body="Related to #803")) == set()
    assert linked_issues({**pr(1), "body": None}) == set()


def test_link_keeps_only_target_issues_oldest_first():
    prs = [
        pr(20, body="Closes #803", created="2026-11-05T00:00:00Z"),
        pr(10, refs=[803], created="2026-11-04T00:00:00Z"),
        pr(30, body="Closes #1"),
    ]
    assert link({803, 771}, prs) == {803: [10, 20], 771: []}


def test_maintainer_comments_keeps_collaborators_only():
    issue = {"comments": {"nodes": [
        {"author": {"login": "petr-sandbox"}, "authorAssociation": "COLLABORATOR", "body": "make it opt-in",
         "createdAt": "t", "url": "u"},
        {"author": {"login": "someone"}, "authorAssociation": "CONTRIBUTOR", "body": "I'll do it",
         "createdAt": "t", "url": "u"},
        {"author": None, "authorAssociation": "OWNER", "body": "ghost", "createdAt": "t", "url": "u"},
    ]}}
    assert [c["body"] for c in maintainer_comments(issue)] == ["make it opt-in", "ghost"]
