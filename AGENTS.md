# AGENTS.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.



# Guidelines: What Defines a Valid Test Case

Strictly enforce this standard when writing or evaluating tests. Reject any test case exhibiting invalid anti-patterns.

---

## 1. Valid Test Case Criteria
A valid test must satisfy ALL of the following:

- **Single Concept:** Tests exactly ONE behavior per test function.
- **Black-Box Testing:** Verifies public interfaces and inputs/outputs—never internal private implementation details.
- **100% Deterministic:** Zero reliance on ambient clock (`Date.now()`), random seeds, external APIs, or dirty DB state.
- **Explicit AAA:** Structured strictly as Arrange (setup), Act (trigger), Assert (check).
- **Refactor-Resistant:** Must pass if internal code is completely refactored without breaking the public contract.
- **High Information Density:** Focuses on realistic boundaries (`0`, `null`, empty arrays, max limits) or explicit error modes.

---

## 2. Invalid Test Case Anti-Patterns (Immediate Rejection)

- ❌ **Implementation Coupling:** Asserting internal helper execution order or checking private class state.
- ❌ **Tautologies:** Re-implementing production logic inside the test setup or asserting simple pass-through getters.
- ❌ **Multi-Scenario Bloat:** Single tests containing sequential user actions, >3 independent assertions, or multiple business rules.
- ❌ **Over-Mocking:** Mocking simple domain models or internal helper classes instead of using real instances or factories.
- ❌ **Flakiness:** Relying on arbitrary `sleep()` calls, live network calls, or unordered array checks.

---

## Output Verification Checklist
Before outputting code, verify:
1. Is the test name `<Method>_<Scenario>_<ExpectedResult>`?
2. Does it test what the code DOES, not HOW it does it?
3. If the implementation changes internally, will this test still pass?