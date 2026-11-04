from odoo.tests import TransactionCase
from odoo.exceptions import UserError, ValidationError


class TestMefsBoq(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.project = self.env['project.project'].create({
            'name': 'Test Construction Project',
            'company_id': self.company.id,
        })
        self.stage_construction = self.env.ref(
            'mefs_project_lifecycle.stage_construction'
        )
        self.product = self.env['product.product'].create({
            'name': 'Cement',
            'type': 'consu',
            'list_price': 100.0,
        })
        self.tax_vat = self.env['account.tax'].create({
            'name': 'VAT 15%',
            'amount': 15.0,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'company_id': self.company.id,
        })
        self.company.account_sale_tax_id = self.tax_vat

    def _line(self, **kwargs):
        vals = {'name': 'Work Item'}
        vals.update(kwargs)
        return (0, 0, vals)

    def _create_boq(self, lines=None, **kwargs):
        vals = {'project_id': self.project.id}
        if lines is not None:
            vals['boq_line_ids'] = lines
        vals.update(kwargs)
        return self.env['mefs.boq'].create(vals)

    def _locked_boq(self, lines=None):
        boq = self._create_boq(lines=lines)
        boq.action_confirm()
        boq.action_approve()
        return boq

    def test_create_auto_name_from_sequence(self):
        boq = self._create_boq()
        self.assertTrue(boq.name.startswith('BOQ/'))
        self.assertEqual(boq.state, 'draft')
        self.assertEqual(boq.revision_number, 0)

    def test_create_preserves_explicit_name(self):
        boq = self._create_boq(name='BOQ/MASTER')
        self.assertEqual(boq.name, 'BOQ/MASTER')

    def test_compute_revision_name(self):
        boq = self._create_boq()
        self.assertEqual(boq.revision_name, f"{boq.name} REV0")

    def test_compute_totals_basic(self):
        # By default, new lines get default 15% VAT
        boq = self._create_boq(lines=[
            self._line(revised_contract_qty=10.0, unit_price=100.0),
            self._line(revised_contract_qty=5.0, unit_price=200.0),
        ])
        self.assertEqual(boq.total_amount, 2000.0)
        self.assertEqual(boq.vat_amount, 300.0)
        self.assertEqual(boq.grand_total, 2300.0)

        # If user removes VAT
        boq_no_vat = self._create_boq(lines=[
            self._line(revised_contract_qty=10.0, unit_price=100.0, taxes_id=[(5, 0, 0)]),
            self._line(revised_contract_qty=5.0, unit_price=200.0, taxes_id=[(5, 0, 0)]),
        ])
        self.assertEqual(boq_no_vat.total_amount, 2000.0)
        self.assertEqual(boq_no_vat.vat_amount, 0.0)
        self.assertEqual(boq_no_vat.grand_total, 2000.0)

    def test_compute_totals_with_vat(self):
        boq = self._create_boq(lines=[
            self._line(
                revised_contract_qty=10.0, unit_price=100.0,
                taxes_id=[(6, 0, [self.tax_vat.id])],
            ),
        ])
        self.assertEqual(boq.total_amount, 1000.0)
        self.assertEqual(boq.vat_amount, 150.0)
        self.assertEqual(boq.grand_total, 1150.0)

    def test_compute_totals_skips_sections_and_subtotals(self):
        boq = self._create_boq(lines=[
            self._line(name='Section One', display_type='line_section'),
            self._line(revised_contract_qty=2.0, unit_price=100.0),
            self._line(revised_contract_qty=3.0, unit_price=50.0),
        ])
        subtotal = self.env['mefs.boq.line'].create({
            'boq_id': boq.id,
            'name': 'Sub-Total Bill No. 1',
            'is_subtotal': True,
            'unit_price': 350.0,
            'quantity': 1.0,
        })
        self.assertEqual(boq.total_amount, 350.0)
        self.assertEqual(subtotal.subtotal, 350.0)
        self.assertEqual(boq.grand_total, 350.0)

    def test_recompute_bill_numbers(self):
        boq = self._create_boq(lines=[
            self._line(name='1 Section One', display_type='line_section', sequence=10),
            self._line(name='Excavate', display_type='line_sub_section', sequence=20, revised_contract_qty=2.0, unit_price=100.0),
            self._line(name='Haul', display_type='line_sub_section', sequence=30, revised_contract_qty=3.0, unit_price=50.0),
            self._line(name='2 Section Two', display_type='line_section', sequence=40),
            self._line(name='Piles', display_type='line_sub_section', sequence=50, revised_contract_qty=1.0, unit_price=1000.0),
        ])
        lines = boq.boq_line_ids

        self.assertEqual(
            lines.filtered(lambda l: l.name == 'Section One').bill_no, '1'
        )
        self.assertEqual(
            lines.filtered(lambda l: l.name == 'Excavate').bill_no, '1.1'
        )
        self.assertEqual(
            lines.filtered(lambda l: l.name == 'Haul').bill_no, '1.2'
        )
        self.assertEqual(
            lines.filtered(lambda l: l.name == 'Section Two').bill_no, '2'
        )
        self.assertEqual(
            lines.filtered(lambda l: l.name == 'Piles').bill_no, '2.1'
        )

        # In draft, transitioning 1 to 2 calculates Sub-Total Bill No. 1
        subtotals = lines.filtered('is_subtotal')
        self.assertEqual(len(subtotals), 1)
        self.assertEqual(subtotals[0].unit_price, 350.0)

        # When confirmed, final family 2 is also closed
        boq.action_confirm()
        lines = boq.boq_line_ids
        subtotals = lines.filtered('is_subtotal')
        self.assertEqual(len(subtotals), 2)
        self.assertEqual(subtotals[0].unit_price, 350.0)
        self.assertEqual(subtotals[1].unit_price, 1000.0)
        self.assertEqual(boq.total_amount, 1350.0)

    def test_recompute_subtotals_placed_after_section(self):
        boq = self._create_boq(lines=[
            self._line(name='Section One', display_type='line_section'),
            self._line(name='Item', display_type='line_sub_section', revised_contract_qty=2.0, unit_price=50.0),
            self._line(name='Section Two', display_type='line_section'),
        ])
        self.assertEqual(
            boq.boq_line_ids.sorted().mapped('name'),
            ['Section One', 'Item', 'Sub-Total Bill No. 1', 'Section Two'],
        )
        boq.action_confirm()
        self.assertEqual(
            boq.boq_line_ids.sorted().mapped('name'),
            ['Section One', 'Item', 'Sub-Total Bill No. 1', 'Section Two', 'Sub-Total Bill No. 2'],
        )

    def test_recompute_subsection_hierarchy(self):
        boq = self._create_boq(lines=[
            self._line(name='Section One', display_type='line_section'),
            self._line(name='Sub Section', display_type='line_sub_section'),
            self._line(name='Sub Sub Section', display_type='line_sub'),
            self._line(name='Item', display_type='line_sub2', revised_contract_qty=1.0, unit_price=100.0),
        ])
        lines = boq.boq_line_ids
        self.assertEqual(lines.filtered(lambda l: l.name == 'Section One').bill_no, '1')
        self.assertEqual(lines.filtered(lambda l: l.name == 'Sub Section').bill_no, '1.1')
        self.assertEqual(lines.filtered(lambda l: l.name == 'Sub Sub Section').bill_no, '1.1.1')
        self.assertEqual(lines.filtered(lambda l: l.name == 'Item').bill_no, '1.1.1.1')
        self.assertEqual(boq.total_amount, 100.0)

    def test_boq_renumbers_after_section_delete(self):
        boq = self._create_boq(lines=[
            self._line(name='Section One', display_type='line_section'),
            self._line(name='Item 1', display_type='line_sub_section', revised_contract_qty=1.0, unit_price=100.0),
            self._line(name='Section Two', display_type='line_section'),
            self._line(name='Item 2', display_type='line_sub_section', revised_contract_qty=1.0, unit_price=200.0),
        ])
        section_one = boq.boq_line_ids.filtered(
            lambda l: l.display_type == 'line_section'
        )[0]
        boq.write({'boq_line_ids': [(2, section_one.id)]})

        lines = boq.boq_line_ids
        self.assertFalse(section_one.exists())
        self.assertFalse(lines.filtered(lambda l: l.name == 'Item 1'))
        self.assertEqual(lines.filtered(lambda l: l.name == 'Section Two').bill_no, '1')
        self.assertEqual(lines.filtered(lambda l: l.name == 'Item 2').bill_no, '1.1')
        self.assertEqual(len(lines.filtered('is_subtotal')), 0)
        self.assertEqual(boq.total_amount, 200.0)

    def test_boq_renumbers_after_line_delete(self):
        boq = self._create_boq(lines=[
            self._line(name='Section One', display_type='line_section'),
            self._line(name='Item 1', display_type='line_sub_section', revised_contract_qty=1.0, unit_price=100.0),
            self._line(name='Item 2', display_type='line_sub_section', revised_contract_qty=1.0, unit_price=200.0),
        ])
        item_one = boq.boq_line_ids.filtered(lambda l: l.name == 'Item 1')
        boq.write({'boq_line_ids': [(2, item_one.id)]})
        lines = boq.boq_line_ids
        self.assertEqual(lines.filtered(lambda l: l.name == 'Item 2').bill_no, '1.1')
        self.assertEqual(len(lines.filtered('is_subtotal')), 0)

    def test_boq_regenerates_deleted_subtotal_on_transition(self):
        boq = self._create_boq(lines=[
            self._line(name='Section One', display_type='line_section'),
            self._line(name='Item', display_type='line_sub_section', revised_contract_qty=2.0, unit_price=50.0),
            self._line(name='Section Two', display_type='line_section'),
        ])
        subtotal = boq.boq_line_ids.filtered('is_subtotal')
        self.assertEqual(len(subtotal), 1)
        boq.write({'boq_line_ids': [(2, subtotal.id)]})
        lines = boq.boq_line_ids
        self.assertEqual(len(lines.filtered('is_subtotal')), 1)
        self.assertEqual(lines.filtered('is_subtotal').unit_price, 100.0)

    def test_action_confirm(self):
        boq = self._create_boq()
        boq.action_confirm()
        self.assertEqual(boq.state, 'waiting_approval')

    def test_action_approve_sets_original_qty(self):
        boq = self._create_boq(lines=[
            self._line(revised_contract_qty=10.0, unit_price=100.0),
        ])
        boq.action_confirm()
        boq.action_approve()
        self.assertEqual(boq.state, 'locked')
        state_dict = dict(boq._fields['state'].selection)
        self.assertEqual(state_dict.get('locked'), 'Approved')
        self.assertEqual(boq.boq_line_ids.original_contract_qty, 10.0)

    def test_only_one_locked_boq_per_project(self):
        first = self._locked_boq(lines=[self._line(revised_contract_qty=10.0)])
        second = self._create_boq(lines=[self._line(revised_contract_qty=5.0)])
        second.action_confirm()
        with self.assertRaises(ValidationError):
            second.action_approve()
        self.assertEqual(second.state, 'waiting_approval')
        self.assertEqual(first.state, 'locked')

    def test_approve_revision_after_original_revised(self):
        self.project.stage_id = self.stage_construction
        boq = self._locked_boq(lines=[self._line(revised_contract_qty=10.0)])
        action = boq.action_create_revision()
        new_boq = self.env['mefs.boq'].browse(action['res_id'])
        self.assertEqual(boq.state, 'revised')
        new_boq.action_confirm()
        new_boq.action_approve()
        self.assertEqual(new_boq.state, 'locked')

    def test_multiple_sequential_revisions_allowed(self):
        self.project.stage_id = self.stage_construction
        boq = self._locked_boq(lines=[self._line(revised_contract_qty=10.0)])
        for expected_rev in (1, 2, 3):
            action = boq.action_create_revision()
            new_boq = self.env['mefs.boq'].browse(action['res_id'])
            self.assertEqual(boq.state, 'revised')
            new_boq.action_confirm()
            new_boq.action_approve()
            self.assertEqual(new_boq.state, 'locked')
            self.assertEqual(new_boq.revision_number, expected_rev)
            boq = new_boq
        self.assertEqual(
            self.env['mefs.boq'].search_count([
                ('project_id', '=', self.project.id),
                ('state', '=', 'locked'),
            ]),
            1,
        )

    def test_action_unlock(self):
        boq = self._locked_boq()
        boq.action_unlock()
        self.assertEqual(boq.state, 'draft')

    def test_action_unlock_requires_locked(self):
        boq = self._create_boq()
        with self.assertRaises(UserError):
            boq.action_unlock()

    def test_action_unlock_blocked_with_revisions(self):
        boq = self._locked_boq()
        self.project.stage_id = self.stage_construction
        boq.with_context(boq_revision_copy=True).copy({
            'parent_boq_id': boq.id,
        })
        with self.assertRaises(UserError):
            boq.action_unlock()

    def test_action_create_revision_requires_locked(self):
        boq = self._create_boq()
        with self.assertRaises(UserError):
            boq.action_create_revision()

    def test_action_create_revision_requires_construction_stage(self):
        boq = self._locked_boq(lines=[self._line(revised_contract_qty=10.0)])
        with self.assertRaises(UserError):
            boq.action_create_revision()

    def test_action_create_revision_success(self):
        self.project.stage_id = self.stage_construction
        boq = self._locked_boq(lines=[
            self._line(revised_contract_qty=10.0, unit_price=100.0),
        ])
        original_line = boq.boq_line_ids

        action = boq.action_create_revision()
        new_boq = self.env['mefs.boq'].browse(action['res_id'])

        self.assertEqual(new_boq.name, boq.name)
        self.assertEqual(new_boq.parent_boq_id, boq)
        self.assertEqual(new_boq.revision_number, 1)
        self.assertEqual(new_boq.revision_name, f"{boq.name} REV1")
        self.assertEqual(new_boq.state, 'draft')
        self.assertEqual(boq.state, 'revised')
        self.assertEqual(boq.revision_count, 1)

        new_line = new_boq.boq_line_ids
        self.assertTrue(new_line)
        self.assertEqual(new_line.revised_contract_qty, 0.0)
        self.assertEqual(new_line.original_contract_qty, 10.0)
        self.assertTrue(new_line.code)
        self.assertNotEqual(new_line.code, original_line.code)

    def test_action_view_revisions(self):
        boq = self._create_boq()
        action = boq.action_view_revisions()
        self.assertEqual(action['res_model'], 'mefs.boq')
        self.assertEqual(action['domain'], [('name', '=', boq.name)])

    def test_project_boq_data_compute(self):
        self._create_boq(lines=[self._line(revised_contract_qty=1.0, unit_price=100.0)])
        self._create_boq(lines=[self._line(revised_contract_qty=1.0, unit_price=50.0)])
        self.project._compute_boq_data()
        self.assertEqual(self.project.boq_count, 2)
        self.assertEqual(self.project.boq_total, 150.0)

    def test_get_boq_report_data_original_and_current(self):
        boq = self._create_boq(lines=[
            self._line(name='Mobilization', display_type='line_section', sequence=10),
            self._line(name='Mobilization Item', display_type='line_sub_section', sequence=20, revised_contract_qty=1.0, unit_price=500000.0),
            self._line(name='Piling Works', display_type='line_section', sequence=30),
            self._line(name='Drilling Works', display_type='line_sub_section', sequence=40, revised_contract_qty=280.0, unit_price=4000.0),
        ])
        # Lock so original_contract_qty is set
        boq.action_confirm()
        boq.action_approve()

        # Test Original Report
        orig_data = boq._get_boq_report_data('original')
        self.assertEqual(orig_data['mode'], 'original')
        self.assertIn('ORIGINAL CONTRACT', orig_data['subtitle'])
        self.assertEqual(orig_data['total_before_vat'], '1,620,000.00')

        # Simulate execution on line 2 (drilled 80 units)
        drill_line = boq.boq_line_ids.filtered(lambda l: l.name == 'Drilling Works')
        drill_line.executed_quantity = 80.0
        drill_line._compute_remaining_quantity()
        self.assertEqual(drill_line.remaining_quantity, 200.0)

        # Test Current Report (remaining: 500,000 + 200*4000 = 1,300,000)
        curr_data = boq._get_boq_report_data('current')
        self.assertEqual(curr_data['mode'], 'current')
        self.assertIn('CURRENT REMAINING WORK', curr_data['subtitle'])
        self.assertEqual(curr_data['total_before_vat'], '1,300,000.00')

    def test_boq_unlink_draft_and_non_draft(self):
        boq = self._create_boq()
        self.assertEqual(boq.state, 'draft')
        # Draft BOQ can be deleted
        boq.unlink()
        self.assertFalse(boq.exists())

        # Non-draft BOQ cannot be deleted
        boq2 = self._create_boq()
        boq2.action_confirm()
        self.assertEqual(boq2.state, 'waiting_approval')
        with self.assertRaises(UserError):
            boq2.unlink()

        boq2.action_approve()
        self.assertEqual(boq2.state, 'locked')
        with self.assertRaises(UserError):
            boq2.unlink()

    def test_boq_print_action_binding(self):
        rep_orig = self.env.ref('mefs_bill_of_quantity.action_report_mefs_boq_original')
        rep_curr = self.env.ref('mefs_bill_of_quantity.action_report_mefs_boq_current')
        self.assertEqual(rep_orig.name, 'Print BOQ')
        self.assertTrue(rep_orig.binding_model_id)
        self.assertFalse(rep_curr.binding_model_id)


class TestMefsBoqLine(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.project = self.env['project.project'].create({
            'name': 'Test Construction Project',
            'company_id': self.company.id,
        })
        self.product = self.env['product.product'].create({
            'name': 'Cement',
            'type': 'consu',
            'list_price': 100.0,
        })
        self.tax_vat = self.env['account.tax'].create({
            'name': 'VAT 15%',
            'amount': 15.0,
            'amount_type': 'percent',
            'company_id': self.company.id,
        })
        self.boq = self.env['mefs.boq'].create({
            'project_id': self.project.id,
        })

    def _create_line(self, **kwargs):
        vals = {'boq_id': self.boq.id, 'name': 'Work Item'}
        vals.update(kwargs)
        return self.env['mefs.boq.line'].create(vals)

    def test_line_code_generation(self):
        anchor = self._create_line(work_type='anchor')
        generic = self._create_line()
        self.assertTrue(anchor.code.startswith('BOQ-ANCHOR-'))
        self.assertTrue(generic.code.startswith('BOQ-GEN-'))

    def test_line_work_type_codes(self):
        codes = {
            'grout': 'GROUT',
            'pile': 'PILE',
            'excavation': 'EXCAV',
            'soil_nail': 'SNAIL',
            'shotcrete': 'SHOT',
        }
        for work_type, expected in codes.items():
            line = self._create_line(work_type=work_type)
            self.assertTrue(line.code.startswith(f"BOQ-{expected}-"))

    def test_line_code_preserved_when_provided(self):
        line = self._create_line(code='MY-CODE')
        self.assertEqual(line.code, 'MY-CODE')

    def test_line_code_skipped_for_section_and_subtotal(self):
        section = self._create_line(display_type='line_section')
        subtotal = self._create_line(is_subtotal=True, unit_price=100.0)
        self.assertFalse(section.code)
        self.assertFalse(subtotal.code)

    def test_line_compute_quantity(self):
        line = self._create_line(revised_contract_qty=7.0)
        self.assertEqual(line.quantity, 7.0)

    def test_line_compute_subtotal(self):
        section = self._create_line(display_type='line_section', unit_price=500.0)
        item = self._create_line(revised_contract_qty=4.0, unit_price=25.0)
        subtotal = self._create_line(is_subtotal=True, unit_price=350.0)
        self.assertEqual(section.subtotal, 0.0)
        self.assertEqual(section.unit_price, 0.0)
        self.assertEqual(item.subtotal, 100.0)
        self.assertEqual(subtotal.subtotal, 350.0)

    def test_line_copy_on_revision_resets(self):
        line = self._create_line(work_type='anchor', revised_contract_qty=10.0)
        copied = line.with_context(boq_revision_copy=True).copy()
        self.assertEqual(copied.revised_contract_qty, 0.0)
        self.assertTrue(copied.code)
        self.assertNotEqual(copied.code, line.code)

    def test_line_unlink_regular_line(self):
        line = self._create_line(revised_contract_qty=5.0)
        line.unlink()
        self.assertFalse(line.exists())

    def test_line_unlink_section_without_children(self):
        section = self._create_line(display_type='line_section')
        section.unlink()
        self.assertFalse(section.exists())

    def test_line_unlink_section_cascades_children(self):
        section = self._create_line(display_type='line_section', sequence=10)
        item = self._create_line(sequence=20, revised_contract_qty=2.0, unit_price=100.0)
        subtotal = self._create_line(sequence=30, is_subtotal=True, unit_price=200.0)
        section.unlink()
        self.assertFalse(section.exists())
        self.assertFalse(item.exists())
        self.assertFalse(subtotal.exists())

    def test_line_unlink_subsection_cascades_only_sublines(self):
        section = self._create_line(display_type='line_section', sequence=10)
        sub = self._create_line(display_type='line_sub_section', sequence=20)
        sub_line = self._create_line(
            display_type='line_sub', sequence=30,
            revised_contract_qty=1.0, unit_price=50.0,
        )
        item = self._create_line(sequence=40, revised_contract_qty=1.0, unit_price=25.0)
        sub.unlink()
        self.assertFalse(sub.exists())
        self.assertFalse(sub_line.exists())
        self.assertTrue(item.exists())

    def test_line_unlink_subtotal(self):
        subtotal = self._create_line(is_subtotal=True, unit_price=100.0)
        subtotal.unlink()
        self.assertFalse(subtotal.exists())

    def test_line_onchange_product(self):
        product = self.env['product.product'].create({
            'name': 'Reinforced Steel',
            'type': 'consu',
            'list_price': 250.0,
            'taxes_id': [(6, 0, [self.tax_vat.id])],
        })
        line = self._create_line(product_id=product.id)
        line._onchange_product_id()
        self.assertEqual(line.name, product.display_name)
        self.assertEqual(line.uom_id, product.uom_id)
        self.assertEqual(line.unit_price, 250.0)
        self.assertEqual(line.taxes_id, product.taxes_id)

    def test_line_onchange_role(self):
        role = self.env['hr.job'].create({'name': 'Carpenter'})
        line = self._create_line(role_id=role.id)
        line._onchange_role_id()
        self.assertEqual(line.name, 'Carpenter')

    def test_line_default_vat_and_removal(self):
        # Line with default VAT
        line = self._create_line(revised_contract_qty=10.0, unit_price=100.0)
        self.assertTrue(line.taxes_id, "Default VAT should be applied to new work lines")
        self.assertIn(self.tax_vat, line.taxes_id)

        # Line where user removes VAT
        line.taxes_id = [(5, 0, 0)]
        self.assertFalse(line.taxes_id, "User should be able to remove VAT if desired")

    def test_line_negative_quantity_constraint(self):
        with self.assertRaises(ValidationError):
            self._create_line(revised_contract_qty=-5.0)

    def test_line_negative_executed_quantity_constraint(self):
        with self.assertRaises(ValidationError):
            self._create_line(revised_contract_qty=10.0, executed_quantity=-2.0)

    def test_line_remaining_quantity_cannot_be_negative(self):
        with self.assertRaises(ValidationError):
            self._create_line(revised_contract_qty=10.0, executed_quantity=15.0)

    def test_work_type_model_and_sync(self):
        work_type_model = self.env['mefs.boq.work.type']
        wt = work_type_model.create({
            'name': 'Bored Piling',
            'code': 'BPIL',
            'sequence': 5,
        })
        line = self._create_line(work_type_id=wt.id)
        self.assertTrue(line.code.startswith('BOQ-BPIL-'))

    def test_section_line_default_vat_preserved_after_confirm(self):
        # Section lines created with display_type should preserve VAT
        boq = self._create_boq(lines=[
            self._line(name='Main Heading', display_type='line_section', revised_contract_qty=10.0, unit_price=100.0),
            self._line(name='Sub Item', display_type='line_sub_section', revised_contract_qty=5.0, unit_price=200.0),
        ])
        for line in boq.boq_line_ids.filtered(lambda l: not l.is_subtotal):
            self.assertTrue(line.taxes_id, "Work item lines should keep default VAT")
            self.assertIn(self.tax_vat, line.taxes_id)

        # Confirming BOQ should not wipe taxes
        boq.action_confirm()
        for line in boq.boq_line_ids.filtered(lambda l: not l.is_subtotal):
            self.assertTrue(line.taxes_id, "Taxes must not be erased on confirm")
            self.assertIn(self.tax_vat, line.taxes_id)
        self.assertEqual(boq.total_amount, 2000.0)
        self.assertEqual(boq.vat_amount, 300.0)
        self.assertEqual(boq.grand_total, 2300.0)

    def test_action_reset_draft(self):
        boq = self._create_boq()
        # Cannot reset to draft from draft
        with self.assertRaises(UserError):
            boq.action_reset_draft()

        boq.action_confirm()
        self.assertEqual(boq.state, 'waiting_approval')

        boq.action_reset_draft()
        self.assertEqual(boq.state, 'draft')

        # Test reset from locked/approved stage
        boq.action_confirm()
        boq.action_approve()
        self.assertEqual(boq.state, 'locked')

        # A non-project-manager user cannot reset from locked
        non_pm_user = self.env['res.users'].create({
            'name': 'Regular User',
            'login': 'regular_user_boq',
            'email': 'reg@example.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        with self.assertRaises(UserError):
            boq.with_user(non_pm_user).action_reset_draft()

        # A project manager can reset from locked
        pm_group = self.env.ref('project.group_project_manager')
        pm_user = self.env['res.users'].create({
            'name': 'Project Manager',
            'login': 'pm_user_boq',
            'email': 'pm@example.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, pm_group.id])],
        })
        boq.with_user(pm_user).action_reset_draft()
        self.assertEqual(boq.state, 'draft')

    def test_generic_bell_notification_dispatch(self):
        """Bell goes only to the submitter and the Project Manager."""
        Notif = self.env['generic.notification']
        group_user = self.env.ref('base.group_user')
        boq_group = self.env.ref('mefs_bill_of_quantity.group_mefs_boq_user')
        pm_group = self.env.ref('project.group_project_manager')
        submitter = self.env['res.users'].create({
            'name': 'BOQ Submitter', 'login': 'boq_submitter', 'email': 'sub@example.com',
            'groups_id': [(6, 0, [group_user.id, boq_group.id])],
        })
        pm = self.env['res.users'].create({
            'name': 'Site PM', 'login': 'boq_pm', 'email': 'pm2@example.com',
            'groups_id': [(6, 0, [group_user.id, boq_group.id, pm_group.id])],
        })
        other_pm = self.env['res.users'].create({
            'name': 'Other PM', 'login': 'boq_other_pm', 'email': 'opm@example.com',
            'groups_id': [(6, 0, [group_user.id, boq_group.id, pm_group.id])],
        })
        self.project.user_id = pm

        boq = self._create_boq()
        boq.with_user(submitter).action_confirm()
        notifs = Notif.search([('res_model', '=', 'mefs.boq'), ('res_id', '=', boq.id)])
        self.assertEqual(notifs.mapped('user_id'), pm,
                         "Only the Project Manager gets the bell on submit (submitter gets an instant pop-up)")

        # No native Odoo notifications: no chatter inbox message, no activity
        self.assertFalse(boq.activity_ids)
        self.assertFalse(boq.message_ids.filtered(lambda m: m.message_type == 'notification'
                                                  and m.subtype_id == self.env.ref('mail.mt_comment')))

        boq.with_user(pm).action_approve()
        approve_notif = Notif.search([
            ('res_model', '=', 'mefs.boq'), ('res_id', '=', boq.id), ('name', 'ilike', 'Approved'),
        ])
        self.assertEqual(approve_notif.user_id, submitter,
                         "Submitter gets the bell on approval (the approver gets an instant pop-up)")
        self.assertNotIn(other_pm, Notif.search([('res_id', '=', boq.id)]).mapped('user_id'))

    def test_submitter_cannot_approve_own_boq(self):
        group_user = self.env.ref('base.group_user')
        boq_group = self.env.ref('mefs_bill_of_quantity.group_mefs_boq_user')
        pm_group = self.env.ref('project.group_project_manager')
        user = self.env['res.users'].create({
            'name': 'Self Approver', 'login': 'boq_self', 'email': 'self@example.com',
            'groups_id': [(6, 0, [group_user.id, boq_group.id, pm_group.id])],
        })
        self.project.user_id = user
        boq = self._create_boq()
        boq.with_user(user).action_confirm()
        with self.assertRaises(UserError):
            boq.with_user(user).action_approve()

    def test_only_project_manager_can_approve_reset_and_pay(self):
        group_user = self.env.ref('base.group_user')
        boq_group = self.env.ref('mefs_bill_of_quantity.group_mefs_boq_user')
        pm_group = self.env.ref('project.group_project_manager')
        mk = lambda n, grps: self.env['res.users'].create({
            'name': n, 'login': n, 'email': n + '@example.com',
            'groups_id': [(6, 0, [group_user.id, boq_group.id] + grps)],
        })
        employee = mk('boq_emp', [])
        pm = mk('boq_pm_only', [pm_group.id])
        other_pm = mk('boq_other_pm2', [pm_group.id])
        self.project.user_id = pm
        boq = self._create_boq()
        boq.with_user(employee).action_confirm()
        for user in (employee, other_pm):
            with self.assertRaises(UserError):
                boq.with_user(user).action_approve()
        boq.with_user(pm).action_approve()
        for user in (employee, other_pm):
            with self.assertRaises(UserError):
                boq.with_user(user).action_reset_draft()
            with self.assertRaises(UserError):
                boq.with_user(user).action_create_payment()
        boq.with_user(pm).action_reset_draft()
        self.assertEqual(boq.state, 'draft')

    def test_confirm_requires_project_manager(self):
        self.project.user_id = False
        boq = self._create_boq()
        with self.assertRaises(UserError):
            boq.action_confirm()
