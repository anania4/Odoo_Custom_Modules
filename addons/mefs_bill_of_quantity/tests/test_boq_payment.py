from odoo.tests import TransactionCase
from odoo.exceptions import UserError


class TestMefsBoqPayment(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.project = self.env['project.project'].create({
            'name': 'Shoring Design & Construction Work',
            'company_id': self.company.id,
        })
        self.uom_unit = self.env.ref('uom.product_uom_unit', raise_if_not_found=False)
        self.uom_meter = self.env.ref('uom.product_uom_meter', raise_if_not_found=False)

        # Create baseline BOQ
        self.boq = self.env['mefs.boq'].create({
            'project_id': self.project.id,
            'boq_line_ids': [
                (0, 0, {
                    'name': 'Mobilization',
                    'display_type': 'line_section',
                    'sequence': 10,
                }),
                (0, 0, {
                    'name': 'Mobilization of staff and equipment',
                    'display_type': 'line_sub_section',
                    'revised_contract_qty': 1.0,
                    'unit_price': 700000.0,
                    'sequence': 20,
                }),
                (0, 0, {
                    'name': 'Shoring Works',
                    'display_type': 'line_section',
                    'sequence': 30,
                }),
                (0, 0, {
                    'name': 'Drilling works in soil formation',
                    'display_type': 'line_sub_section',
                    'revised_contract_qty': 1213.614,
                    'unit_price': 5500.0,
                    'sequence': 40,
                }),
                (0, 0, {
                    'name': 'Drilling works in rock formation',
                    'display_type': False,
                    'revised_contract_qty': 904.386,
                    'unit_price': 9000.0,
                    'sequence': 50,
                }),
            ]
        })
        # Confirm and approve BOQ
        self.boq.action_confirm()
        self.boq.action_approve()

    def test_payment_creation_and_smart_button(self):
        self.assertEqual(self.boq.payment_count, 0)
        action = self.boq.action_create_payment()
        payment_id = action.get('res_id')
        self.assertTrue(payment_id)

        payment = self.env['mefs.boq.payment'].browse(payment_id)
        self.assertEqual(self.boq.payment_count, 1)
        self.assertTrue(payment.name.startswith('IPC-'))
        self.assertEqual(payment.state, 'draft')
        self.assertEqual(payment.boq_id.id, self.boq.id)

        # Verify action_view_payments
        view_action = self.boq.action_view_payments()
        self.assertEqual(view_action['res_id'], payment.id)

    def test_payment_lines_loaded_from_boq(self):
        payment = self.env['mefs.boq.payment'].create({
            'boq_id': self.boq.id,
        })
        payment.action_load_boq_lines()

        # Should load all lines from the BOQ
        self.assertEqual(len(payment.line_ids), len(self.boq.boq_line_ids))

        line_mobi = payment.line_ids.filtered(lambda l: 'Mobilization of staff' in l.name)
        self.assertTrue(line_mobi)
        self.assertEqual(line_mobi.contract_qty, 1.0)
        self.assertEqual(line_mobi.unit_price, 700000.0)
        self.assertEqual(line_mobi.contract_amount, 700000.0)
        self.assertEqual(line_mobi.previously_executed_qty, 0.0)
        self.assertEqual(line_mobi.previous_amount, 0.0)

    def test_payment_calculation_and_subsequent_payment(self):
        # 1. Create First Payment (IPC-01)
        payment1 = self.env['mefs.boq.payment'].create({
            'boq_id': self.boq.id,
        })
        payment1.action_load_boq_lines()

        line_mobi = payment1.line_ids.filtered(lambda l: 'Mobilization of staff' in l.name)
        line_soil = payment1.line_ids.filtered(lambda l: 'soil formation' in l.name)
        line_rock = payment1.line_ids.filtered(lambda l: 'rock formation' in l.name)

        # Mobilization: 50% executed (0.5)
        line_mobi.currently_executed_qty = 0.5
        line_mobi._onchange_currently_executed_qty()
        self.assertEqual(line_mobi.current_amount, 350000.0)
        self.assertEqual(line_mobi.todate_executed_qty, 0.5)
        self.assertEqual(line_mobi.todate_amount, 350000.0)

        # Soil drilling: 1170.1 executed
        line_soil.currently_executed_qty = 1170.1
        line_soil._onchange_currently_executed_qty()
        self.assertEqual(line_soil.current_amount, round(1170.1 * 5500.0, 2))
        self.assertEqual(line_soil.todate_executed_qty, 1170.1)

        # Rock drilling: 834 executed
        line_rock.currently_executed_qty = 834.0
        line_rock._onchange_currently_executed_qty()
        self.assertEqual(line_rock.current_amount, round(834.0 * 9000.0, 2))
        self.assertEqual(line_rock.todate_executed_qty, 834.0)

        payment1._compute_line_totals()
        payment1._compute_financial_summary()

        expected_executed = 350000.0 + (1170.1 * 5500.0) + (834.0 * 9000.0)
        self.assertEqual(payment1.total_current_amount, round(expected_executed, 2))

        # Retention 5%
        expected_retention = round(expected_executed * 0.05, 2)
        self.assertEqual(payment1.retention_amount, expected_retention)

        # Net before VAT
        expected_net_before_vat = round(expected_executed - expected_retention, 2)
        self.assertEqual(payment1.net_amount_before_vat, expected_net_before_vat)

        # VAT 15% on executed work
        expected_vat = round(expected_executed * 0.15, 2)
        self.assertEqual(payment1.vat_amount, expected_vat)

        # Net due contractor
        expected_due = round(expected_net_before_vat + expected_vat, 2)
        self.assertEqual(payment1.net_amount_due, expected_due)

        # Check amount words generated
        payment1._compute_amount_words()
        self.assertTrue(payment1.amount_words)


        # Submit and Approve IPC-01
        payment1.action_submit()
        self.assertEqual(payment1.state, 'submitted')
        payment1.action_approve()
        self.assertEqual(payment1.state, 'approved')

        # 2. Create Second Payment (IPC-02)
        payment2 = self.env['mefs.boq.payment'].create({
            'boq_id': self.boq.id,
        })
        payment2.action_load_boq_lines()

        p2_mobi = payment2.line_ids.filtered(lambda l: 'Mobilization of staff' in l.name)
        p2_soil = payment2.line_ids.filtered(lambda l: 'soil formation' in l.name)

        # In Payment 2, Previously Executed should equal Payment 1 Todate Executed
        self.assertEqual(p2_mobi.previously_executed_qty, 0.5)
        self.assertEqual(p2_mobi.previous_amount, 350000.0)
        self.assertEqual(p2_mobi.currently_executed_qty, 0.0)
        self.assertEqual(p2_mobi.todate_executed_qty, 0.5)
        self.assertEqual(p2_mobi.todate_amount, 350000.0)

        self.assertEqual(p2_soil.previously_executed_qty, 1170.1)
        self.assertEqual(p2_soil.previous_amount, round(1170.1 * 5500.0, 2))

        # Execute remaining 0.5 of Mobilization in IPC-02
        p2_mobi.currently_executed_qty = 0.5
        p2_mobi._onchange_currently_executed_qty()
        self.assertEqual(p2_mobi.current_amount, 350000.0)
        self.assertEqual(p2_mobi.todate_executed_qty, 1.0)
        self.assertEqual(p2_mobi.todate_amount, 700000.0)

    def test_editable_fields_preserve_manual_overrides(self):
        payment = self.env['mefs.boq.payment'].create({
            'boq_id': self.boq.id,
        })
        payment.action_load_boq_lines()

        line = payment.line_ids.filtered(lambda l: 'Mobilization of staff' in l.name)
        # Manually override amounts and quantities
        line.write({
            'currently_executed_qty': 0.3,
            'current_amount': 220000.0,  # User manually adjusted the amount
            'todate_amount': 220000.0,
        })

        self.assertEqual(line.currently_executed_qty, 0.3)
        self.assertEqual(line.current_amount, 220000.0)
        self.assertEqual(line.todate_amount, 220000.0)

    def test_payment_workflow_and_cancel(self):
        payment = self.env['mefs.boq.payment'].create({
            'boq_id': self.boq.id,
        })
        payment.action_load_boq_lines()
        self.assertEqual(payment.state, 'draft')

        payment.action_submit()
        self.assertEqual(payment.state, 'submitted')

        payment.action_approve()
        self.assertEqual(payment.state, 'approved')
        self.assertTrue(payment.approved_date)

        payment.action_mark_paid()
        self.assertEqual(payment.state, 'paid')
        self.assertTrue(payment.paid_date)

    def test_payment_report_generation(self):
        payment = self.env['mefs.boq.payment'].create({
            'boq_id': self.boq.id,
            'advance_payment_net': 31825175.08,
            'advance_payment_vat': 4773776.26,
        })
        payment.action_load_boq_lines()

        line_mobi = payment.line_ids.filtered(lambda l: 'Mobilization of staff' in l.name)
        line_mobi.currently_executed_qty = 0.5
        line_mobi._onchange_currently_executed_qty()

        payment._compute_line_totals()
        payment._compute_financial_summary()

        report_data = payment._get_payment_report_data()
        self.assertEqual(report_data['ipc_number'], '1')
        self.assertEqual(report_data['payment_no'], payment.name)
        self.assertTrue(report_data['rows'])
        self.assertTrue(report_data['section_summaries'])
        self.assertTrue(report_data['advance_payment_list'])
        self.assertEqual(report_data['advance_payment_list'][0]['no'], 'Adva. 1')
        self.assertTrue(report_data['summary_total_before_vat'])
        self.assertTrue(report_data['vat_15'])
        self.assertTrue(report_data['grand_total'])

        # Test report action QWeb HTML rendering
        report = self.env.ref('mefs_bill_of_quantity.action_report_mefs_boq_payment')
        html_bytes = report._render_qweb_html(report.id, [payment.id])[0]
        html = html_bytes.decode('utf-8') if isinstance(html_bytes, bytes) else html_bytes
        self.assertIn('INTERIM PAYMENT CERTIFICATE - 1', html)
        self.assertIn('Summary for Advance Payment', html)
        self.assertIn('Summary Total Before VAT', html)

