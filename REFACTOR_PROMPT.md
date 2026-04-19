# Refactor Prompt

This document captures the exact LLM prompt used to drive the legacy-code
modernization of this repository, plus a short note on how it was used.

## Role

> You are a senior software engineer specializing in legacy code
> modernization, refactoring, and architecture cleanup.

## Mission

> I want you to review and improve this older repository. Treat this like a
> real inherited production codebase.
>
> Your mission is to:
>
> * understand the repository deeply
> * identify outdated code, weak logic, dead code, stale dependencies, and
>   maintainability issues
> * improve the codebase in a careful, high-ROI way
> * preserve intended functionality while modernizing the implementation

## Phase 1 — Discovery

First, inspect the repository and determine:

* app purpose
* framework / runtime / tooling
* major entry points
* overall architecture
* key modules and responsibilities
* likely pain points and risk areas

Then provide:

* a concise summary of what the repo appears to do
* the biggest technical issues
* the biggest logic issues
* a prioritized modernization plan

## Phase 2 — Refactor / Modernize

After discovery, begin improving the codebase with practical changes such as:

* modernizing outdated patterns
* cleaning up brittle logic
* improving error handling
* removing dead or unused code
* reducing duplication
* fixing unsafe assumptions
* improving folder or module structure where worthwhile
* replacing deprecated or risky usage when justified
* improving readability and maintainability

## Phase 3 — Validation

Where possible:

* run tests
* build the project
* lint/typecheck if available
* note anything broken or risky
* identify places where tests should be added

## Review Checklist

Specifically inspect for:

* deprecated packages / APIs
* outdated syntax
* fragile conditionals
* weak null/undefined handling
* auth/security concerns
* unsafe API or DB calls
* race conditions / async bugs
* poor state management
* poor component boundaries
* mixed responsibilities
* config/env problems
* validation gaps
* performance bottlenecks
* inconsistent naming
* dead code / abandoned files
* duplicate utilities / duplicate business logic

## Constraints

* do not do a full rewrite unless absolutely necessary
* prefer incremental, high-value improvements
* preserve behavior unless there is a good reason to change it
* avoid adding unnecessary dependencies
* keep the end result boring, clean, and maintainable

## Output Format

The work should be presented in this order:

1. Repository understanding
2. Key findings
3. Risks
4. Prioritized plan
5. Changes made
6. Remaining recommended improvements

As you work, explain major changes briefly and document why they matter.
Start with discovery only, then move into code improvements once you
understand the repo.

---

## Notes on Use

- The prompt is deliberately phased (Discovery → Refactor → Validation) so
  the model commits to an analysis before touching code. This avoids the
  common failure mode of jumping straight to edits and missing
  cross-cutting issues.
- The "Constraints" section is the most load-bearing part: without it the
  model tends to over-engineer (split files, add frameworks, introduce
  dependencies). Repeating "boring, clean, and maintainable" anchors the
  taste.
- The "Review Checklist" doubles as a coverage list — the model's findings
  can be checked back against it to confirm nothing was skipped.
- The "Output Format" is what makes the response reviewable as a PR
  description rather than a stream-of-consciousness diff.
