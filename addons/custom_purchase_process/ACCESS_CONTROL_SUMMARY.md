# Access Control Implementation Summary

## Overview
Updated access control for Material Requests and Purchase Requests to implement company isolation and department-based security.

## Access Control Rules

### Material Requests

1. **Requesters (Users)**: 
   - Can only see their own requests
   - Company isolation: Only see requests from their own company
   - Group: `group_material_request_user`

2. **Approvers**: 
   - Can see requests from their department only
   - Company isolation: Only see requests from their own company
   - Group: `group_material_request_approver`

3. **Store Managers**: 
   - Can see requests from all departments
   - Company isolation: Only see requests from their own company
   - Group: `group_material_request_store_manager`

4. **Admins**: 
   - Can see requests from all departments
   - Company isolation: Only see requests from their own company
   - Group: `group_material_request_admin`

### Purchase Requests

1. **Requesters (Purchasers)**: 
   - Can only see their own requests
   - Company isolation: Only see requests from their own company
   - Group: `group_custom_purchase_request_purchaser`

2. **Approvers**: 
   - Can see requests from their department only
   - Company isolation: Only see requests from their own company
   - Group: `group_custom_purchase_request_approvers`

3. **Store Managers**: 
   - Can see requests from all departments
   - Company isolation: Only see requests from their own company
   - Group: `group_store_request_approver`

4. **CEOs and Super Admins**: 
   - Can see requests from all departments
   - Company isolation: Only see requests from their own company
   - Groups: `group_purchase_request_ceos`, `group_custom_purchase_request_super_admin`

### Purchase Quotations

1. **Requesters**: 
   - Can see quotations related to their own purchase requests
   - Company isolation: Only see quotations from their own company
   - Group: `group_custom_purchase_request_purchaser`

2. **Approvers**: 
   - Can see quotations from their department only
   - Company isolation: Only see quotations from their own company
   - Group: `group_custom_purchase_request_approvers`

3. **Store Managers**: 
   - Can see quotations from all departments
   - Company isolation: Only see quotations from their own company
   - Group: `group_store_request_approver`

4. **CEOs and Super Admins**: 
   - Can see quotations from all departments
   - Company isolation: Only see quotations from their own company
   - Groups: `group_purchase_request_ceos`, `group_custom_purchase_request_super_admin`

## Key Features

1. **Company Isolation**: All rules include company filtering to ensure users only see records from their own company
2. **Department-based Access**: Approvers can only see requests/quotations from their own department
3. **Hierarchical Access**: Store managers and admins can see all departments within their company
4. **Department Tracking**: Added `request_department_id` field to purchase requests to track the requester's department

## Files Modified

1. `security/material_request_rules.xml` - Updated material request access rules
2. `security/purchase_request_record_rules.xml` - Updated purchase request and quotation access rules
3. `models/purchase_request.py` - Added `request_department_id` field and compute method

## Technical Implementation

- Used Odoo record rules (ir.rule) to implement domain-based access control
- Leveraged `user.company_id.id` for company isolation
- Used `user.employee_id.department_id.id` for department-based access
- Added computed fields to track department information from the requester 