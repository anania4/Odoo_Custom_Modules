# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError


class TestEquipmentTimesheet(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.user_group = cls.env.ref('equipment_timesheet.group_equipment_timesheet_user')
        cls.manager_group = cls.env.ref('equipment_timesheet.group_equipment_timesheet_manager')

        cls.test_user = cls.env['res.users'].create({
            'name': 'Field Operator',
            'login': 'operator_test',
            'groups_id': [(6, 0, [cls.user_group.id])],
        })

        cls.test_manager = cls.env['res.users'].create({
            'name': 'Project Manager Test',
            'login': 'pm_test',
            'groups_id': [(6, 0, [cls.manager_group.id])],
        })

        cls.project = cls.env['project.project'].create({
            'name': 'Highway Construction Site A',
            'user_id': cls.test_manager.id,
        })

        cls.equipment_category = cls.env['maintenance.equipment.category'].create({
            'name': 'Excavators',
        })

        cls.equipment = cls.env['maintenance.equipment'].create({
            'name': 'CAT 320D Excavator',
            'category_id': cls.equipment_category.id,
            'model': '320D-2024',
            'serial_no': 'CAT320D-9988',
        })

    def test_01_lines_and_fuel_calculation(self):
        """Test calculation of morning and afternoon hours, single total, and fuel consumed on lines."""
        timesheet = self.env['equipment.timesheet'].with_user(self.test_user).create({
            'project_id': self.project.id,
            'line_ids': [
                (0, 0, {
                    'equipment_id': self.equipment.id,
                    'shift_type': 'day',
                    'day_start_time': 8.0,
                    'day_end_time': 12.0,          # 4.0 hours
                    'night_start_time': 13.0,
                    'night_end_time': 17.5,        # 4.5 hours
                    'fuel_refueled': 100.0,
                    'fuel_left': 35.0,
                    'idle_time': 1.5,
                    'idle_reason': 'Waiting for Material',
                }),
                (0, 0, {
                    'equipment_id': self.equipment.id,
                    'shift_type': 'night',
                    'night_start_time': 20.0,
                    'night_end_time': 4.0,         # 8.0 hours across midnight
                    'fuel_refueled': 50.0,
                    'fuel_left': 10.0,             # 40.0 consumed
                    'idle_time': 0.5,
                    'idle_reason': 'Refueling',
                })
            ]
        })

        line1 = timesheet.line_ids[0]
        self.assertEqual(line1.shift_type, 'day')
        # Total adds starting from Morning Start (8:00) to Afternoon End (17:30) = 4.0 + 4.5 = 8.5
        self.assertEqual(line1.total_hours, 8.5, "Total hours should be 8.5")
        self.assertEqual(line1.idle_time, 1.5, "Idle time should be 1.5")
        self.assertEqual(line1.idle_reason, 'Waiting for Material')
        self.assertEqual(line1.fuel_consumed, 65.0, "Fuel consumed should be 100 - 35 = 65.0")
        self.assertEqual(line1.equipment_category_id, self.equipment_category)

        line2 = timesheet.line_ids[1]
        self.assertEqual(line2.shift_type, 'night')
        self.assertEqual(line2.total_hours, 8.0, "Overnight hours should be 8.0")
        self.assertEqual(line2.idle_time, 0.5, "Idle time should be 0.5")
        self.assertEqual(line2.idle_reason, 'Refueling')
        self.assertEqual(line2.fuel_consumed, 40.0, "Fuel consumed should be 40.0")

        # Single Grand Total Hours adding all lines
        self.assertEqual(timesheet.total_hours, 16.5, "Total hours sum should be 16.5")
        self.assertEqual(timesheet.total_idle_time, 2.0, "Total idle time sum should be 2.0")
        self.assertEqual(timesheet.total_fuel_consumed, 105.0, "Total fuel consumed sum should be 105.0")
        self.assertEqual(timesheet.equipment_count, 2)
        self.assertEqual(timesheet.state, 'draft')

    def test_02_approval_workflow(self):
        """Test submit by user and approve by manager."""
        timesheet = self.env['equipment.timesheet'].with_user(self.test_user).create({
            'project_id': self.project.id,
            'line_ids': [
                (0, 0, {
                    'equipment_id': self.equipment.id,
                    'shift_type': 'day',
                    'day_start_time': 8.0,
                    'night_end_time': 14.0,
                    'fuel_refueled': 50.0,
                    'fuel_left': 20.0,
                })
            ]
        })

        # Save action (like mobile view)
        save_res = timesheet.with_user(self.test_user).action_save()
        self.assertEqual(save_res['tag'], 'display_notification')

        # Submit
        timesheet.with_user(self.test_user).action_submit()
        self.assertEqual(timesheet.state, 'submitted')

        # Approve by manager
        timesheet.with_user(self.test_manager).action_approve()
        self.assertEqual(timesheet.state, 'approved')
        self.assertEqual(timesheet.approved_by_id, self.test_manager)

    def test_03_project_statistics(self):
        """Test computed statistics on the project."""
        timesheet = self.env['equipment.timesheet'].with_user(self.test_manager).create({
            'project_id': self.project.id,
            'line_ids': [
                (0, 0, {
                    'equipment_id': self.equipment.id,
                    'shift_type': 'day',
                    'day_start_time': 8.0,
                    'night_end_time': 16.0,
                    'fuel_refueled': 80.0,
                    'fuel_left': 30.0,
                })
            ],
            'state': 'submitted',
        })

        self.project._compute_equipment_timesheet_stats()
        self.assertGreaterEqual(self.project.equipment_timesheet_count, 1)
        self.assertGreaterEqual(self.project.equipment_total_hours, 8.0)
        self.assertGreaterEqual(self.project.equipment_total_fuel_consumed, 50.0)

    def test_04_hr_timesheet_menu_hidden(self):
        """Test that the default hr_timesheet menu is hidden/deactivated."""
        menu = self.env.ref('hr_timesheet.timesheet_menu_root', raise_if_not_found=False)
        if menu:
            self.assertFalse(menu.active, "Default hr_timesheet menu should be deactivated (active=False)")

    def test_05_fuel_running_balance_and_distinct_equipment(self):
        """Test fuel consumed = opening + refueled - left, and project distinct equipment calculation."""
        # Create a second distinct equipment
        equipment2 = self.env['maintenance.equipment'].create({
            'name': 'Komatsu Bulldozer D65',
            'category_id': self.equipment_category.id,
            'model': 'D65EX-16',
            'serial_no': 'KOM-D65-102',
        })

        timesheet = self.env['equipment.timesheet'].with_user(self.test_user).create({
            'project_id': self.project.id,
            'date': '2026-10-20', # Test custom date
            'line_ids': [
                (0, 0, {
                    'equipment_id': self.equipment.id,
                    'fuel_opening': 50.0,
                    'fuel_refueled': 100.0,
                    'fuel_left': 40.0, # consumed = 50 + 100 - 40 = 110.0
                }),
                (0, 0, {
                    'equipment_id': self.equipment.id, # Same equipment repeated
                    'fuel_opening': 40.0,
                    'fuel_refueled': 60.0,
                    'fuel_left': 20.0, # consumed = 40 + 60 - 20 = 80.0
                }),
                (0, 0, {
                    'equipment_id': equipment2.id, # Different equipment
                    'fuel_opening': 10.0,
                    'fuel_refueled': 50.0,
                    'fuel_left': 15.0, # consumed = 10 + 50 - 15 = 45.0
                }),
            ]
        })

        # Verify date
        self.assertEqual(str(timesheet.date), '2026-10-20')

        # Line 1: 50 + 100 - 40 = 110.0
        self.assertEqual(timesheet.line_ids[0].fuel_consumed, 110.0)
        # Line 2: 40 + 60 - 20 = 80.0
        self.assertEqual(timesheet.line_ids[1].fuel_consumed, 80.0)
        # Line 3: 10 + 50 - 15 = 45.0
        self.assertEqual(timesheet.line_ids[2].fuel_consumed, 45.0)

        # Check project distinct equipment
        self.project._compute_equipment_timesheet_stats()
        # Even though there are 3 lines in this timesheet + 1 line in test_03,
        # distinct equipment count should only be the unique equipment IDs used (2 machines: CAT + Komatsu)
        self.assertEqual(self.project.equipment_count_distinct, 2, "Distinct equipment count should be 2 unique machines, not line count")

    def test_06_export_wizard(self):
        """Test export wizard generates both XLSX and CSV data."""
        # 1. Test Project level export
        wizard = self.env['equipment.timesheet.export.wizard'].create({
            'export_scope': 'project',
            'project_id': self.project.id,
            'filter_shift': 'all',
            'export_format': 'csv',
        })
        res = wizard.action_export()
        self.assertEqual(wizard.state, 'get')
        self.assertTrue(wizard.file_data)
        self.assertTrue(wizard.file_name.endswith('.csv'))

        # 2. Test XLSX export
        wizard_xlsx = self.env['equipment.timesheet.export.wizard'].create({
            'export_scope': 'all',
            'filter_shift': 'all',
            'export_format': 'xlsx',
        })
        res_xlsx = wizard_xlsx.action_export()
        self.assertEqual(wizard_xlsx.state, 'get')
        self.assertTrue(wizard_xlsx.file_data)
        self.assertTrue(wizard_xlsx.file_name.endswith('.xlsx'))

        # 3. Test default_get with timesheet context
        timesheet = self.project.equipment_timesheet_ids[0]
        wizard_ts = self.env['equipment.timesheet.export.wizard'].with_context(
            active_model='equipment.timesheet',
            active_id=timesheet.id,
        ).create({'filter_shift': 'all', 'export_format': 'csv'})
        self.assertEqual(wizard_ts.export_scope, 'timesheet')
        self.assertEqual(wizard_ts.timesheet_id, timesheet)
        self.assertIn(timesheet.name, wizard_ts.scope_display)

        # 4. Test default_get with project context
        wizard_proj = self.env['equipment.timesheet.export.wizard'].with_context(
            active_model='project.project',
            active_id=self.project.id,
            active_ids=[self.project.id],
        ).create({'filter_shift': 'all', 'export_format': 'csv'})
        self.assertEqual(wizard_proj.export_scope, 'project')
        self.assertEqual(wizard_proj.project_id, self.project)
        self.assertIn(self.project.name, wizard_proj.scope_display)
