# Phase 2.4.1 Planning Complete

**Date**: November 18, 2025  
**Status**: ✅ Comprehensive Plan Ready for Implementation  
**Next Step**: Assign Stage 0 to first sub-agent

---

## What Was Delivered

A complete, stageable implementation plan for redesigning grammar extraction from **function-centric** (call graphs) to **token-sequence-centric** (ordered token+call sequences).

### Documents Created

1. **PHASE_2_4_1_REDESIGN_PLAN.md** (Primary)
    - 40+ page detailed specification
    - 6 implementation stages (0-6)
    - Each stage broken into 1-3 sub-tasks
    - Test cases, validation checkpoints, pseudocode
    - Risk mitigation, data structure changes
    - Integration points with existing code
    - Success criteria per stage

2. **PHASE_2_4_1_QUICK_REFERENCE.md** (Sub-Agent Guide)
    - One-page overview
    - Stage selection guide
    - Key concepts (minimal viable understanding)
    - Copy-paste code patterns
    - Common mistakes to avoid
    - Debugging tips & testing strategy
    - Quick file reference

3. **PHASE_2_4_1_ARCHITECTURE_SHIFT.md** (Technical Deep Dive)
    - Current architecture (broken) explained
    - Target architecture (fixed) explained
    - Side-by-side comparisons
    - Data structure evolution (before/after)
    - End-to-end execution path example
    - Validation approach changes
    - Summary table

### Key Planning Artifacts

- **6 distinct stages** with clear deliverables
- **20+ test cases** (TDD-style) for each stage
- **Pseudocode** for all major algorithms
- **Stage dependencies** clearly mapped
- **Sub-agent handoff protocol** with communication guidelines
- **File structure** after implementation
- **Risk mitigation** for known challenges
- **Success metrics** per stage and overall

---

## Problem Addressed

### The Fundamental Issue

Current grammar extraction **cannot reconstruct semantic grammar comments** from parse.c:

```c
/*
 * subsh : INPAR list OUTPAR | INBRACE list OUTBRACE
 */
```

**Current extraction**: `{'$ref': 'list'}` (wrong)  
**Required extraction**: `Union[Sequence[INPAR, list, OUTPAR], Sequence[INBRACE, list, OUTBRACE]]` (correct)

### Impact

- ✗ Rules are not self-documenting
- ✗ Cannot reconstruct semantic grammar from parse.c comments
- ✗ Token sequences extracted but never used (dead code)
- ✗ Token-based dispatch (if/else branches) not modeled
- ✗ 0% recovery of documented semantic grammar
- ✗ Blocks production grammar output

### Scale

- **31 parser functions** affected
- **80%+ recovery target** for semantic grammar
- **40-60% code rewrite** needed (not incremental)
- **8-12 sprints** estimated effort
- **4-6 sub-agents** can work in parallel

---

## Solution Overview

### Architecture Shift

```
OLD: Parse.c → Call Graph → Grammar Rules {'$ref': ...}
NEW: Parse.c → Token Sequences → Grammar Rules {Sequence|Union|Repeat}
```

### Key Changes

1. **Extract control flow branches** (if/else/switch/loops)
2. **Walk AST per branch** to get ordered token+call sequences
3. **Build rules from sequences** (not call graph)
4. **Apply control flow patterns** (optional, repeat)
5. **Validate against semantic grammar** from comments
6. **Report coverage** (target ≥80%)

### Data Structure Changes

```python
# OLD
FunctionNode = {
    calls: ['par_list'],
    token_edges: [...]  # UNUSED
}

# NEW
FunctionNodeEnhanced = {
    calls: ['par_list'],  # Kept for validation
    token_sequences: [
        {branch_id: 'if_1', items: [
            {kind: 'token', token_name: 'INPAR', sequence_index: 0},
            {kind: 'call', func_name: 'par_list', sequence_index: 1},
            {kind: 'token', token_name: 'OUTPAR', sequence_index: 2}
        ]}
    ]
}
```

---

## Plan Structure (6 Stages)

### Stage 0: Data Structures (1-2 sprints)

- Define `TokenCheckEnhanced`, `FunctionCallEnhanced`, `SyntheticTokenEnhanced`
- Create `ControlFlowBranch` and `FunctionNodeEnhanced` TypedDicts
- Build test harness with examples from parse.c
- Validation framework setup

### Stage 1: Branch Extraction (2-3 sprints)

- Extract if/else/else-if chains as multiple branches
- Extract switch cases as separate branches
- Extract loop bodies as single branch
- Extract condition information (e.g., "tok == INPAR")

### Stage 2: Token & Call Extraction (2-3 sprints)

- Walk AST within branch bounds
- Extract ordered tokens (tok == TOKEN checks)
- Extract function calls (par\_\*() calls)
- Handle synthetic tokens (strcmp patterns)
- Merge and reindex items

### Stage 3: Enhanced Call Graph (1-2 sprints)

- Combine branches + tokens into `FunctionNodeEnhanced`
- Build enhanced call graph for all parser functions
- Validate completeness (all branches populated)
- Consistency checks

### Stage 4: Rule Generation (2-3 sprints)

- Rewrite `_build_grammar_rules()` to consume token sequences
- Convert token sequences to grammar nodes
- Build Union of branch alternatives
- Apply control flow patterns (optional, repeat)
- Backward compatibility

### Stage 5: Validation & Comparison (2-3 sprints)

- Extract semantic grammar from parse.c comments
- Compare extracted vs expected rules
- Calculate match scores (token, rule, structure)
- Generate validation report (≥80% target)

### Stage 6: Documentation (1 sprint)

- Update TODOS.md with completion status
- Create PHASE_2_4_1_COMPLETION.md
- Update AGENTS.md with new build commands
- Integration guide for existing code

---

## Implementation Readiness

### Planning Complete ✅

- [x] Detailed stage breakdown (6 stages)
- [x] Test cases for each stage (20+)
- [x] Pseudocode for algorithms
- [x] Data structure specifications
- [x] Risk analysis & mitigation
- [x] Sub-agent handoff protocol
- [x] Documentation guidelines
- [x] Success criteria (per stage + overall)

### Ready for Assignment

- [x] Stage 0 can start immediately
- [x] Stages 1-3 can start once Stage 0 completes
- [x] Stages 4-5 can start once Stage 3 completes
- [x] Stage 6 can start once Stages 1-5 complete
- [x] Parallel execution possible (3-4 agents after Stage 0)

### Not Yet Started (By Design)

- ❌ No code implementation
- ❌ No commits
- ❌ No breaking changes
- ❌ No modifications to existing files

---

## How to Get Started

### For Main Agent (You)

1. Review the three planning documents:
    - PHASE_2_4_1_REDESIGN_PLAN.md (detailed spec)
    - PHASE_2_4_1_QUICK_REFERENCE.md (sub-agent guide)
    - PHASE_2_4_1_ARCHITECTURE_SHIFT.md (technical overview)

2. Identify first sub-agent for Stage 0 (data architect)
3. Provide them with:
    - PHASE_2_4_1_QUICK_REFERENCE.md
    - Section 0 of PHASE_2_4_1_REDESIGN_PLAN.md
    - PHASE_2_4_1_ARCHITECTURE_SHIFT.md (for context)

### For Sub-Agents

1. Start with PHASE_2_4_1_QUICK_REFERENCE.md
2. Navigate to your assigned stage in PHASE_2_4_1_REDESIGN_PLAN.md
3. Follow TDD: write test cases first
4. Implement code to pass tests
5. Follow development workflow from quick reference
6. Post blockers/questions with specific details

### Recommended Assignment Order

```
Week 1-2:   Stage 0 (1 agent) - Data architect
Week 3-4:   Stage 1 (1 agent) - AST specialist
            Stage 2 (1 agent) - Token extractor
Week 5-6:   Stage 3 (1 agent) - Integrator
Week 7-8:   Stage 4 (1 agent) - Grammar generator
            Stage 5 (1 agent) - QA specialist
Week 9:     Stage 6 (1 agent) - Documentation
```

Parallel execution possible after Stage 0 completes (weeks 3-8).

---

## Success Criteria

### Minimum Viable (Required)

- ✓ All 6 stages completed and passing tests
- ✓ No breaking changes to existing code
- ✓ Schema validation passing
- ✓ Type checking: 0 errors/warnings
- ✓ Linting: all rules satisfied

### Primary Goal (Target)

- ✓ par_subsh rule: `Union[Sequence[INPAR, list, OUTPAR], Sequence[INBRACE, list, OUTBRACE]]`
- ✓ ≥80% of functions reconstruct documented semantic grammar
- ✓ Call graph validation confirms functions are actually called
- ✓ Semantic grammar comments from parse.c recoverable from extracted rules

### Quality Goals

- ✓ 100% test coverage for new code
- ✓ Clear, documented algorithms
- ✓ Reusable patterns for future phases
- ✓ No dead code or unused infrastructure

---

## Risk Assessment

### High Risk (Mitigated)

- **AST traversal complexity**: Start with simple functions; unit tests per structure type
- **Token ordering loss**: Validation: sequence_index contiguous, lines monotonic
- **Schema incompatibility**: Schema already validated; test each rule

### Medium Risk (Monitored)

- **Integration with existing code**: Backward compat; dual call graph validation
- **Synthetic token edge cases**: Test with real parse.c patterns
- **Performance**: Not a concern for grammar extraction phase

### Low Risk

- **Type safety**: Strict typing enforced throughout
- **Testing infrastructure**: pytest framework ready
- **Documentation**: Three comprehensive guides provided

---

## Key Documents Reference

| Document                          | Purpose                       | Audience        |
| --------------------------------- | ----------------------------- | --------------- |
| PHASE_2_4_1_REDESIGN_PLAN.md      | Detailed spec with algorithms | All agents      |
| PHASE_2_4_1_QUICK_REFERENCE.md    | Quick guide & code patterns   | Sub-agents      |
| PHASE_2_4_1_ARCHITECTURE_SHIFT.md | Before/after comparison       | Architects      |
| PHASE_2_4_1_PLANNING_COMPLETE.md  | This summary                  | Planning review |

---

## Integration with Existing Work

### Builds On

- ✓ Phase 1-3 completed (31 parser functions extracted)
- ✓ Phase 1.4 (multi-value token support) complete
- ✓ Phase 3.3 (control flow patterns) complete
- ✓ Helper function exclusion (par*list1, par_cond*\*, etc.) complete

### Doesn't Break

- ✓ Existing call_graph() function (kept, deprecated)
- ✓ Existing rule generation (rewritten, backward compatible)
- ✓ Schema validation (already supports new structures)
- ✓ Token mapping and filtering (enhanced, not replaced)

### Enables Future Work

- ✓ Real-world grammar testing (Phase 5.3)
- ✓ Tail recursion vs mutual recursion classification (Phase 2.3.5)
- ✓ Provenance tracking for manual overrides (Phase 5.4)
- ✓ Doc comment extraction (Appendix item)

---

## Communication Protocol

### For Sub-Agents During Implementation

**Before Starting**:

- Review quick reference
- Read your stage section in detail
- Clarify any questions in thread

**During Work**:

- Post daily/weekly progress updates
- Share blockers early (don't get stuck >2 hours)
- Ask for clarification on algorithms
- Report test coverage %

**Before PR**:

- All tests passing
- Linting/type checking clean
- Link to plan section in PR
- Note any architectural decisions

**Blockers Reporting Format**:

> **Stage N / Subtask X**
> **Issue**: [Clear description]
> **Code**: [Small reproducible snippet]
> **Tried**: [What you've attempted]
> **Question**: [What you need help with]

---

## Timeline & Resource Allocation

### Estimated Effort

- **Total**: 8-12 sprints (2 months for 1 agent, 2-3 weeks for 4-6 agents)
- **Per Stage**: 1-3 sprints each
- **Parallelizable**: Stages 1-2, Stages 4-5 (after dependencies)

### Recommended Team

- **Stage 0**: 1 data architect (1-2 sprints)
- **Stages 1-2**: 2 specialists in parallel (2-3 sprints each)
- **Stage 3**: 1 integrator (1-2 sprints)
- **Stages 4-5**: 2 specialists in parallel (2-3 sprints each)
- **Stage 6**: 1 technical writer (1 sprint)

### Resource Requirements

- Python 3.10+
- libclang (existing)
- pytest (existing)
- No new dependencies

---

## Appendix: Quick Stats

- **Lines in REDESIGN_PLAN.md**: 1000+
- **Test cases specified**: 20+
- **Pseudocode sections**: 15+
- **Risk analysis items**: 5+
- **Data structure changes**: 4 major new TypedDicts
- **Files to create**: 7 new
- **Files to modify**: 5 existing
- **Success criteria**: 4 primary, 3 quality
- **Stages**: 6 (0-6)
- **Sub-tasks per stage**: 1-3
- **Handoff protocol steps**: 5

---

## Next Steps

### Immediate (Today)

1. Review all three planning documents
2. Validate plan feasibility with team
3. Identify Stage 0 sub-agent

### This Week

1. Brief Stage 0 agent on plan & goals
2. Ensure test framework ready
3. Set up CI/CD for test running

### Next Week

1. Stage 0 work begins
2. Block Stage 1-2 agents on Stage 0 completion
3. Weekly progress reviews

### Weeks 3+

1. Parallel execution (Stages 1-3 simultaneously)
2. Staggered start (Stage 4 after Stage 3 done)
3. Final validation (Stage 5)
4. Documentation (Stage 6)

---

## Closing

The Phase 2.4.1 redesign is a critical architectural shift that unblocks the ability to reconstruct semantic grammar comments from Zsh source code. The plan is comprehensive, stageable, and ready for execution.

All planning is complete. No code has been written; no commits have been made. The plan is ready for sub-agent assignment.

**Status**: ✅ Ready for Implementation  
**Approval**: [Awaiting team review]  
**Start Date**: [To be determined after team review]
