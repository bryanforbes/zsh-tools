# Phase 2.4.1 Planning Documentation Index

Token-sequence-centric grammar extraction redesign. **Implementation Status: Stages 0-5 COMPLETE (1 remaining: 6). 167 tests passing, 0 errors.**

---

## Quick Navigation

**New to this redesign?** Start here:

1. Read [PHASE_2_4_1_PLANNING_COMPLETE.md](#planning-complete-summary) (5 min)
2. Skim [PHASE_2_4_1_ARCHITECTURE_SHIFT.md](#architecture-shift-reference) (10 min)
3. Review [PHASE_2_4_1_QUICK_REFERENCE.md](#quick-reference-for-subagents) (5 min)

**Implementing a stage?** Go here:

1. Read [PHASE_2_4_1_QUICK_REFERENCE.md](#quick-reference-for-subagents) (full)
2. Navigate to your stage in [PHASE_2_4_1_REDESIGN_PLAN.md](#detailed-redesign-specification)
3. Reference [PHASE_2_4_1_ARCHITECTURE_SHIFT.md](#architecture-shift-reference) for context

**Reviewing the full plan?** Read in this order:

1. [PHASE_2_4_1_PLANNING_COMPLETE.md](#planning-complete-summary) - Overview
2. [PHASE_2_4_1_ARCHITECTURE_SHIFT.md](#architecture-shift-reference) - Why it's needed
3. [PHASE_2_4_1_REDESIGN_PLAN.md](#detailed-redesign-specification) - How to build it
4. [PHASE_2_4_1_QUICK_REFERENCE.md](#quick-reference-for-subagents) - How to work on it

---

## Document Descriptions

### Planning Complete (Summary)

**File**: `PHASE_2_4_1_PLANNING_COMPLETE.md`  
**Length**: ~400 lines, 13 KB  
**Read Time**: 5-10 minutes

**Contents**:

- What was delivered (4 planning documents)
- Problem addressed (current extraction can't reconstruct semantic grammar)
- Solution overview (6 stages, 2-3 months effort)
- Plan structure (stage breakdown)
- Implementation readiness checklist
- Success criteria (minimum/primary/quality)
- Risk assessment
- Timeline & resource allocation
- Next steps (immediate/this week/next week)

**Purpose**: Executive summary and planning status report. Read first if you're evaluating whether to proceed.

**Key Sections**:

- Plan Structure: One-liner for each stage
- Implementation Readiness: What's complete/not-started
- Timeline: Recommended agent assignments
- Success Criteria: What "done" looks like

---

### Architecture Shift (Reference)

**File**: `PHASE_2_4_1_ARCHITECTURE_SHIFT.md`  
**Length**: ~500 lines, 21 KB  
**Read Time**: 15-20 minutes

**Contents**:

- Current broken architecture (call graph, tokens unused)
- Target fixed architecture (token sequences, ordered items)
- What gets lost in current approach
- Side-by-side comparisons (3 examples)
- Data structure evolution (before/after)
- Processing flow changes (old vs new)
- Execution path examples with line-by-line walkthrough
- Error handling differences
- Validation & verification changes
- Summary table (aspect-by-aspect comparison)

**Purpose**: Understand the problem and solution at architectural level. Read to comprehend why redesign is necessary.

**Key Sections**:

- The Problem: What's Broken - Current extraction fails
- The Solution: Token-Sequence-Centric - How it's fixed
- Example 1-3: Detailed before/after comparisons
- Execution Path Example: par_subsh with both branches traced

---

### Detailed Redesign Specification (Implementation)

**File**: `PHASE_2_4_1_REDESIGN_PLAN.md`  
**Length**: ~2000 lines, 73 KB  
**Read Time**: 60-90 minutes (or reference by stage)

**Contents**:

- Executive summary (critical facts)
- Architecture overview (visual diagrams)
- Phase breakdown (6 stages: 0-6)
- Each stage contains:
    - Agent role & duration
    - Dependencies & deliverables
    - Detailed algorithm descriptions
    - Pseudocode implementation
    - Test cases (5-10 per stage)
    - Validation checkpoints
    - Output artifacts
- Critical success metrics
- Risk mitigation strategies
- Integration with existing code
- Sub-agent handoff protocol
- File structure after implementation
- Appendix with patterns & references

**Purpose**: Complete specification for implementation. Read your stage section before coding.

**Key Sections**:

- Stage Breakdown: Master roadmap
- Stage 0-6: Detailed specifications with pseudocode
- Validation Framework: What to test
- Sub-Agent Handoff Protocol: How to work
- Integration Points: How new code connects to old

**How to Navigate**:

- Find your stage number (0-6)
- Read all subsections for that stage
- Copy pseudocode and test cases as starting point
- Reference "Validation Checkpoints" section

---

### Quick Reference (Sub-Agent Guide)

**File**: `PHASE_2_4_1_QUICK_REFERENCE.md`  
**Length**: ~700 lines, 16 KB  
**Read Time**: 15-20 minutes (or reference while coding)

**Contents**:

- One-page overview (problem → solution)
- Stage selection guide ("I want to work on...")
- Key concepts explained simply
- Development workflow (before/during/after)
- Code patterns (copy-paste friendly)
- Common mistakes to avoid
- Testing strategy (unit/integration/regression)
- Debugging tips
- Key files reference table
- Blockers/questions format
- Success checklist per stage

**Purpose**: Day-to-day reference while implementing. Keep open while coding.

**Key Sections**:

- Stage Selection Guide: Pick your work
- Code Patterns: Reusable snippets
- Common Mistakes: What not to do
- Testing Strategy: How to validate
- Debugging Tips: How to troubleshoot
- Success Checklist: Before you commit

---

## Reading Paths by Role

### Project Manager / Tech Lead

**Goal**: Understand scope, timeline, risks, success criteria

**Read** (30 min):

1. PHASE_2_4_1_PLANNING_COMPLETE.md - Full read
2. PHASE_2_4_1_ARCHITECTURE_SHIFT.md - "Plan Structure" section only

**Sections to review**:

- What Was Delivered
- Problem Addressed
- Plan Structure (6 stages)
- Implementation Readiness
- Timeline & Resource Allocation
- Risk Assessment
- Success Criteria

---

### Architecture Reviewer

**Goal**: Understand technical approach, validate design decisions

**Read** (60 min):

1. PHASE_2_4_1_ARCHITECTURE_SHIFT.md - Full read
2. PHASE_2_4_1_REDESIGN_PLAN.md - Sections 0.1 (data structures) and "Architecture Overview"
3. PHASE_2_4_1_QUICK_REFERENCE.md - "Key Concepts" section

**Sections to review**:

- The Problem: What's Broken
- The Solution: Token-Sequence-Centric
- Side-by-Side Comparisons (Examples 1-3)
- Data Structure Evolution
- Processing Flow Changes

---

### Sub-Agent (Implementing Stage N)

**Goal**: Understand your stage, write code, pass tests

**Read** (45 min initial, 5 min per session):

**Initial Setup**:

1. PHASE_2_4_1_QUICK_REFERENCE.md - Full read
2. PHASE_2_4_1_REDESIGN_PLAN.md - Your stage section (0.1-0.3 for Stage 0, etc.)
3. PHASE_2_4_1_ARCHITECTURE_SHIFT.md - "Key Concepts" section

**During Implementation**:

1. Keep PHASE_2_4_1_QUICK_REFERENCE.md open as reference
2. Reference pseudocode in your stage section
3. Use test cases from your stage

**Sections to focus on**:

- Your stage subsections
- Test cases for your stage
- Code patterns
- Common mistakes
- Development workflow
- Testing strategy

---

### Code Reviewer (Reviewing PRs)

**Goal**: Validate implementation against plan, approve/comment

**Read** (45 min):

1. PHASE_2_4_1_QUICK_REFERENCE.md - "Success Checklist" section
2. PHASE_2_4_1_REDESIGN_PLAN.md - The implemented stage section
3. Look for in PR:
    - Test cases match stage spec
    - Code matches pseudocode
    - Validation checkpoints addressed
    - No breaking changes to existing code

**Validation Checklist**:

- [ ] All test cases pass (from stage spec)
- [ ] Type checking: 0 errors/warnings
- [ ] Linting: all rules satisfied
- [ ] Code matches pseudocode structure
- [ ] New files created as specified
- [ ] Modified files updated correctly
- [ ] Validation checkpoints documented
- [ ] No breaking changes
- [ ] PR references stage number and plan

---

## Key Concepts Quick Reference

### Token Sequence

Ordered list of tokens and function calls extracted from parser function.

Example: `par_subsh` branch has `[INPAR, par_list, OUTPAR]`

### Control Flow Branch

One execution path through a function (if/else/switch/loop).

Example: `if (tok == INPAR) { ... }` is branch 1; `else if (tok == INBRACE) { ... }` is branch 2

### Token-Sequence-Centric

Grammar extraction based on **ordered token sequences**, not just function calls.

### Function-Centric (Old)

Grammar extraction based on **call graph** (what calls what).

### Semantic Grammar

The actual BNF-style grammar documented in parse.c comments.

Example: `subsh : INPAR list OUTPAR | INBRACE list OUTBRACE`

### Synthetic Token

Token created from `tok == STRING && !strcmp(tokstr, "value")` patterns.

Example: `!strcmp(tokstr, "always")` → synthetic token `ALWAYS`

---

## File Relationships

```
PHASE_2_4_1_PLANNING_COMPLETE.md
├─ (references) PHASE_2_4_1_REDESIGN_PLAN.md
├─ (references) PHASE_2_4_1_QUICK_REFERENCE.md
└─ (references) PHASE_2_4_1_ARCHITECTURE_SHIFT.md

PHASE_2_4_1_REDESIGN_PLAN.md
├─ (detailed specs for) 6 stages
├─ (uses concepts from) PHASE_2_4_1_ARCHITECTURE_SHIFT.md
└─ (implementation resource) PHASE_2_4_1_QUICK_REFERENCE.md

PHASE_2_4_1_QUICK_REFERENCE.md
├─ (guide to) PHASE_2_4_1_REDESIGN_PLAN.md stages
├─ (illustrates) key concepts from ARCHITECTURE_SHIFT.md
└─ (implements) workflows from PLANNING_COMPLETE.md

PHASE_2_4_1_ARCHITECTURE_SHIFT.md
├─ (justifies) PHASE_2_4_1_REDESIGN_PLAN.md approach
└─ (explains) why QUICK_REFERENCE.md patterns matter
```

---

## Document Statistics

| Document           | Lines    | Size       | Focus                           |
| ------------------ | -------- | ---------- | ------------------------------- |
| PLANNING_COMPLETE  | 400      | 13 KB      | Overview, status, timeline      |
| ARCHITECTURE_SHIFT | 500      | 21 KB      | Problem/solution, examples      |
| REDESIGN_PLAN      | 2000     | 73 KB      | Stage specs, algorithms, tests  |
| QUICK_REFERENCE    | 700      | 16 KB      | Workflow, patterns, debugging   |
| **Total**          | **3600** | **123 KB** | **Comprehensive specification** |

---

## Implementation Checklist

### Before Assigning First Stage

- [ ] All four planning documents reviewed by team
- [ ] Team alignment on scope and timeline
- [ ] Stage 0 sub-agent identified
- [ ] Test infrastructure verified (pytest, basedpyright, ruff)
- [ ] CI/CD ready for test running

### Before Sub-Agent Starts

- [ ] Sub-agent reads QUICK_REFERENCE.md
- [ ] Sub-agent reads their stage section in REDESIGN_PLAN.md
- [ ] Blockers/questions clarified
- [ ] Development environment set up
- [ ] Branch created: `feat/phase-2.4.1-stage-N`

### During Implementation

- [ ] Test cases written first (TDD)
- [ ] Code follows pseudocode structure
- [ ] Validation checkpoints addressed
- [ ] Type checking clean (basedpyright)
- [ ] Linting clean (ruff)
- [ ] Formatting applied (prettier/ruff-format)

### Before PR

- [ ] All tests passing
- [ ] Code quality checks passing
- [ ] PR references plan section
- [ ] Commit messages follow conventional format
- [ ] Documentation updated (if needed)

### Before Merging

- [ ] Code review by architecture reviewer
- [ ] All PR comments addressed
- [ ] Tests verified one more time
- [ ] Stage marked complete in TODO.md
- [ ] Next stage can begin

---

## FAQ

### Q: Which document should I read first?

**A**: PHASE_2_4_1_PLANNING_COMPLETE.md (5 min overview), then PHASE_2_4_1_QUICK_REFERENCE.md (if implementing) or PHASE_2_4_1_ARCHITECTURE_SHIFT.md (if reviewing).

### Q: How detailed is the pseudocode?

**A**: Detailed enough to implement from. Each algorithm has:

- Purpose statement
- Input/output specification
- Step-by-step algorithm
- Python pseudocode
- Example usage

### Q: Can I start implementing immediately?

**A**: Stages 0-5 are COMPLETE. Stage 6 can start immediately.

### Q: What if I find a mistake in the plan?

**A**: Post in thread with:

- Document name
- Line/section number
- Issue description
- Suggested fix (if applicable)

### Q: How long does each stage take?

**A**: 1-3 sprints (about 1-3 weeks for one person). Multiple agents can work in parallel.

### Q: What are the hardest stages?

**A**: Stages 2 (token extraction ordering) and 4 (grammar generation) typically need most thought. Plan 3 sprints for those.

### Q: Can I skip any stages?

**A**: No. Stages have strict dependencies. Stage 0 → Stages 1-2 → Stage 3 → Stages 4-5 → Stage 6.

### Q: What happens if tests fail?

**A**: Debug using tips in QUICK_REFERENCE.md. If stuck >2 hours, post blocker. Don't proceed to next stage until all tests pass.

---

## Contact & Communication

### During Planning Review

Post questions in thread with:

- Document name
- Section/line reference
- Your question

### During Sub-Agent Work

Post daily progress and blockers with:

- Stage number
- Task completed
- Issues encountered (if any)
- Test coverage %

### For Architectural Questions

Reference PHASE_2_4_1_ARCHITECTURE_SHIFT.md sections and ask for clarification.

### For Implementation Questions

Reference your stage section in PHASE_2_4_1_REDESIGN_PLAN.md and pseudocode.

---

## Next Steps

1. **Stage 5 Complete** ✅ Semantic grammar validation & comparison (Nov 18, 2025)
2. **Assign** Stage 6 to documentation specialist (now)
3. **Weekly** progress reviews and blockers
4. **Estimated completion**: Week of Nov 25-29, 2025

---

## Summary

Four comprehensive planning documents guide implementation:

1. **PHASE_2_4_1_PLANNING_COMPLETE.md** — Overview and status
2. **PHASE_2_4_1_ARCHITECTURE_SHIFT.md** — Technical justification
3. **PHASE_2_4_1_REDESIGN_PLAN.md** — Detailed implementation specification
4. **PHASE_2_4_1_QUICK_REFERENCE.md** — Sub-agent workflow guide

**Implementation Progress**:

- ✅ Stages 0-5 COMPLETE (167 tests passing)
- ⏳ Stage 6 IN PROGRESS
- 0 lint errors, 0 type errors

**Next**: Assign Stage 6 (Documentation & Integration) to next sub-agent
