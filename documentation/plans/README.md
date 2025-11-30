# Plexus Planning Documents

This directory contains comprehensive planning and implementation documents for major Plexus features.

## Active Plans

### [ML Training and Inference Infrastructure](./ml-training-and-inference-plan.md)
**Status:** Phase 1 Complete ✅, Phase 2 In Progress 🔄

Master plan covering:
- ✅ **Phase 1:** Unified training infrastructure (local + SageMaker)
- 🔄 **Phase 2:** SageMaker endpoint provisioning and deployment
- 📋 **Phase 3:** Production inference with auto-discovery

**Quick Start:**
```bash
# Current (works today):
plexus train --scorecard "My Scorecard" --score "My Score" --yaml

# Coming soon:
plexus train --scorecard "My Scorecard" --score "My Score" --deploy
plexus predict --scorecard "My Scorecard" --score "My Score" --item 123
```

---

## Archived Documents

The following documents have been superseded by the unified plan above:
- `training-infrastructure-status.md` → Merged into master plan (backup at `.backup`)
- `sagemaker-endpoint-provisioning.md` → Merged into master plan

---

## Document Conventions

### Status Indicators
- ✅ **Complete**: Implemented and tested
- 🔄 **In Progress**: Currently being worked on
- 📋 **Planned**: Designed but not started
- ⚠️ **Blocked**: Waiting on dependencies
- ❌ **Deprecated**: No longer relevant

### Document Types
- **Master Plans**: Comprehensive multi-phase implementation plans
- **RFC**: Request for Comments on design decisions
- **ADR**: Architectural Decision Records
- **Status**: Current state tracking documents

---

## Contributing

When creating new planning documents:

1. **Use descriptive filenames**: `feature-name-plan.md` or `feature-name-rfc.md`
2. **Include status indicators**: Make it clear what's done and what's not
3. **Keep it updated**: Plans should be living documents
4. **Link related docs**: Cross-reference relevant plans/RFCs
5. **Add to this README**: Update the Active Plans section

---

**Last Updated:** 2025-01-28
