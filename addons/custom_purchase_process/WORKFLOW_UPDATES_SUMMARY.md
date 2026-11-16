# Supplier Analysis Workflow Updates Summary

## Overview
This document summarizes the changes made to the supplier analysis workflow based on the requirements:

1. Send activities to groups when approval is requested
2. Auto-mark QA inspection for selected products when QA is required
3. Rename "department approval" state to "committee approved"
4. Change "client approve" button to "committee approve"
5. Add quality inspection button during "in progress" state when QA is required
6. Manage quality inspection workflow and state transitions

## Changes Made

### 1. State Changes
- **Old State**: `department_approved` → **New State**: `committee_approved`
- Updated in both `supplier_analysis.py` and `purchase_update.py`
- Updated state selection field and all references

### 2. Field Changes
- **Old Field**: `department_remark` → **New Field**: `committee_remark`
- Updated field name and label for consistency

### 3. Method Changes
- **Old Method**: `action_department_approve()` → **New Method**: `action_committee_approve()`
- Enhanced method to automatically mark inspection for selected lines when QA is required
- Added activity notifications for next steps in workflow

### 4. New Fields Added
- `show_quality_inspection_button`: Computed field to control when quality inspection button appears
- Logic: Shows when state is 'in_progress', QA is required, and there are selected lines marked for inspection

### 5. Activity Notifications
- Added `schedule_activity_for_group_users()` method to send activities to specific user groups
- Activities are sent when:
  - Analysis moves to 'in_progress' state → Notify approvers
  - Committee approval is completed → Notify quality team (if QA required)
  - Quality inspection is generated → Notify quality team

### 6. Quality Inspection Workflow
- **Quality Inspection Button**: Now appears during 'in_progress' state when:
  - QA is required (`qa_required = True`)
  - There are selected lines marked for inspection (`chosen_for_inspection = True`)
- **Auto-marking**: When committee approves and QA is required, all selected lines are automatically marked for inspection
- **State Transitions**: Quality inspection can be generated from both 'in_progress' and 'committee_approved' states

### 7. View Updates
- Updated statusbar to show `committee_approved` instead of `department_approved`
- Changed button text from "Client Approved" to "Committee Approve"
- Repositioned quality inspection button to appear during 'in_progress' state
- Updated button visibility conditions for CEO approval (can approve from both 'quality_inspection' and 'committee_approved' states)

### 8. Enhanced GM Approval
- GM can now approve from either 'quality_inspection' or 'committee_approved' state
- Validation to ensure items marked for inspection have passed before GM approval

## Workflow Summary

### New State Flow:
1. **Draft** → **In Progress** (sends activity to approvers)
2. **In Progress** → **Committee Approved** (auto-marks QA lines, sends activity to quality team if needed)
3. **Committee Approved** → **GM Approved** (if no QA required)
4. **In Progress/Committee Approved** → **Quality Inspection** → **GM Approved** (if QA required)
5. **GM Approved** → **Done** (generate PO)

### Quality Inspection Flow:
- Quality inspection button appears in 'in_progress' state when QA is required
- Selected lines are automatically marked for inspection during committee approval
- Quality inspection records are created for each vendor
- After quality inspection completion, workflow proceeds to GM approval

### Activity Notifications:
- **In Progress**: Notifies all committee approvers
- **Committee Approved**: Notifies quality team if QA is required
- **Quality Inspection Generated**: Notifies quality team to proceed with inspection

## Files Modified
1. `models/supplier_analysis.py` - Main workflow changes
2. `models/purchase_update.py` - State and field updates
3. `views/supplier_analysis_views.xml` - Button and field updates

## Benefits
- **Improved Communication**: Automatic activity notifications keep stakeholders informed
- **Streamlined QA Process**: Auto-marking and smart button visibility
- **Consistent Naming**: "Committee" terminology aligns with business processes
- **Flexible Workflow**: GM can approve from multiple states as needed
- **Better User Experience**: Buttons appear only when relevant actions are possible 