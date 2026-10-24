# Equipment Timesheet Module (Timesheet)

## Overview
A custom Odoo 18 module designed specifically for tracking field equipment operations, working hours, and fuel consumption on project sites.

## Key Features & Architecture

### 1. Projects Dashboard for Everyone
* **Default Landing Page**: Visible to all employees and project managers alike.
* **Project Kanban Cards**:
  - Displays project name, client, and project manager.
  - KPI boxes:
    - ⏱ **Working Hours** (sum of all equipment working hours)
    - ⛽ **Fuel Consumed** (total liters consumed)
    - 🚜 **Active Equipments**
    - ⏳ **Pending Approvals** (highlighted badge)
  - **Quick Action Buttons on Card**:
    - `Add Timesheet`: Opens a new timesheet form page directly for this project with the project name pre-selected and locked.
    - `View Timesheets`: Opens the list of timesheets for this project.

### 2. Streamlined Timesheet Page & Locked Header
When opening or creating a Timesheet:
* **Project Name**: **Locked / Uneditable** (taken directly from the selected project).
* **Date**: **Locked / Uneditable** (automatically takes today's date).
* **Reported By**: **Locked / Uneditable** (automatically takes the logged-in user).

### 3. Equipment Lines (Product-Line Style Table)
Just like product lines on a sales order, each timesheet allows adding one or multiple equipment lines for the day:
* **Equipment**: Dropdown fetching directly from **Maintenance Equipment Registration** (`maintenance.equipment`).
* **Shift**: Dropdown badge selection: **Day** (green) and **Night** (red).
* **Working Hours Timeline**:
  - **Morning Start** (e.g., `08:00`)
  - **Morning End** (e.g., `12:00`)
  - **Afternoon Start** (e.g., `13:00` or `20:00`)
  - **Afternoon End** (e.g., `17:00` or `04:00` across midnight)
* **Single Total Hours**: Unified total at the end of each line (`Total`) auto-calculating all hours worked from Morning Start to Afternoon End.
* **Idle Tracking**:
  - **Idle Time**: Log non-productive/standby hours with float time formatting.
  - **Idle Reason**: Specify the reason for equipment downtime (e.g. Weather, Waiting for Material, Breakdown, Standby).
* **Fuel Tracking**:
  - Fuel Refueled (L)
  - Fuel Left (L)
  - Auto-calculated **Fuel Consumed (L)** = Fuel Refueled - Fuel Left.
* **Grand Totals**: Summarized automatically at the bottom of the timesheet (Total Working Hours, Total Idle Time, Total Fuel Consumed).

### 4. Mobile Responsive Layout (Like Daily Report)
* **Mobile Card View**: On screens smaller than 768px (phones & tablets), the horizontal equipment table automatically transforms into sleek, stacked vertical cards with distinct field labels (`🚜 Equipment`, `Shift`, `Morning Start`, `Morning End`, `Afternoon Start`, `Afternoon End`, `⏱ Total Hours`, `Fuel Refueled`, `Fuel Left`, `⛽ Fuel Consumed`, `Remarks`).
* **Touch-Friendly Controls**: Full-width `+ Add an Equipment Line` dashed button and clear mobile remove buttons.
* **Bottom Mobile Action Bar**: Located at the very bottom of the timesheet for effortless thumb access on mobile:
  - **Save Button**: Saves the timesheet on-the-fly with instant success notification.
  - **Submit for Approval**: Submits the timesheet directly from the bottom of the screen.

### 5. Approval Workflow
* **Submit for Approval**: Any user can report/submit their timesheet. Once submitted, lines become read-only.
* **Project Manager Approval**: Only Project Managers have permission to approve (`Approved`) or reject (`Rejected`).
* **Reset to Draft**: Project Managers can reset timesheets back to draft if changes are needed.
* Full Odoo 18 `<chatter/>` integration for tracking and logging.

### 6. Menus
* **Projects Dashboard** (Visible to all users)
* **My Timesheets** (Shows only timesheets reported/created by the logged-in user)
* **To Approve** (Visible to Project Managers)
* **Default Odoo 18 Timesheets Menu**: Automatically deactivated (`active=False`) and hidden from the navigation bar / app drawer.
