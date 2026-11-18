from collections import OrderedDict

from odoo import api, fields, models, _

# Vendor bill payment states that count as "booked" (paid). Everything else on file is "unbooked".
PAID_STATES = ('paid', 'in_payment')
# IPC states that count as earned income; "paid" also counts as collected.
EARNED_IPC_STATES = ('approved', 'paid')


class MefsProjectDashboard(models.AbstractModel):
    """Data provider for the Project Dashboard client action.

    Returns one dict per project in the shape the OWL dashboard expects
    (see static/src/project_dashboard.js). Every source is read defensively:
    a module that is not installed simply yields an empty section.
    """
    _name = 'mefs.project.dashboard'
    _description = 'Project Dashboard Data'

    # ------------------------------------------------------------------ public API
    @api.model
    def get_projects(self):
        projects = self.env['project.project'].search([], order='name')
        return [{'id': p.id, 'name': p.name, 'client': p.partner_id.name or ''} for p in projects]

    @api.model
    def get_dashboard_data(self, project_id):
        project = self.env['project.project'].browse(project_id).exists()
        if not project:
            return {}
        project.check_access('read')
        # Aggregates span documents owned by other users (bills, requests): read them as superuser,
        # after checking the user can read the project itself.
        project = project.sudo()
        env = self.env(su=True)

        boq = self._approved_boq(env, project)
        info, plan = self._budget_info(env, project)
        budget_by_categ = self._budget_by_category(info)
        ledger = self._ledger(env, project, budget_by_categ)
        boq_items = self._boq_items(boq)
        schedule = self._schedule_items(plan)
        planned_start = (plan.project_start_date if plan else False) or project.date_start
        planned_finish = (plan.project_end_date if plan else False) or project.date
        if not planned_finish and schedule:
            planned_finish = max(i['end'] for i in schedule if i['end']) or False

        return {
            'id': project.id,
            'name': project.name,
            'client': project.partner_id.name or '',
            'budgetPlan': plan.name if plan else '',
            'boq': (boq.revision_name or boq.name) if boq else '',
            'contractIncome': boq.total_amount if boq else 0.0,
            'plannedStart': fields.Date.to_string(planned_start) if planned_start else False,
            'plannedFinish': fields.Date.to_string(planned_finish) if planned_finish else False,
            'actualFinish': False,  # source still to be agreed
            'costClasses': self._cost_classes(budget_by_categ, ledger),
            'rebarCostType': self._rebar_cost_type(budget_by_categ, ledger),
            'packages': self._packages(boq),
            'boqItems': boq_items,
            'scheduleItems': schedule,
            'taskStages': self._task_stages(env, project),
            'tasks': self._task_counts(env, project),
            'ipcs': self._ipcs(env, project),
            'machines': self._machines(env, project),
            'ledger': ledger,
        }

    # ------------------------------------------------------------------ BOQ / budget
    def _approved_boq(self, env, project):
        if 'mefs.boq' not in env:
            return False
        Boq = env['mefs.boq']
        return Boq.search([('project_id', '=', project.id), ('state', '=', 'locked')],
                          order='revision_number desc, id desc', limit=1)

    def _budget_info(self, env, project):
        if 'mefs.budget.project.info' not in env:
            return False, False
        info = env['mefs.budget.project.info'].search([('project_id', '=', project.id)], limit=1)
        plan = info.budget_plan_id if info else False
        if not plan and 'mefs.budget.plan' in env:
            plan = env['mefs.budget.plan'].search([('project_id', '=', project.id)], order='id desc', limit=1)
        return info, plan or False

    @staticmethod
    def _budget_by_category(info):
        """{product.category: planned amount} from the Total Planned Expenses Summary."""
        result = OrderedDict()
        if not info:
            return result
        for line in info.expense_line_ids.sorted(lambda l: (l.sequence, l.id)):
            if line.cost_type_id:
                result[line.cost_type_id] = result.get(line.cost_type_id, 0.0) + (line.amount or 0.0)
        return result

    @staticmethod
    def _cost_type_for(categ, budget_by_categ):
        """Budget cost type a product category counts under: itself, or its nearest budgeted parent."""
        c = categ
        while c:
            if c in budget_by_categ:
                return c
            c = c.parent_id
        return categ

    @staticmethod
    def _boq_item_lines(boq):
        if not boq:
            return []
        # Every BOQ level (main line, section, sub-line) can carry its own quantity and price:
        # work items are all rows except notes and sub-totals, with a quantity.
        return boq.boq_line_ids.filtered(
            lambda l: l.display_type != 'line_note' and not l.is_subtotal
            and (l.revised_contract_qty or l.quantity or 0.0) > 0)

    def _boq_items(self, boq):
        items = []
        for line in self._boq_item_lines(boq):
            qty = line.revised_contract_qty or line.quantity or 0.0
            executed = min((line.executed_quantity or 0.0) / qty * 100.0, 100.0) if qty else 0.0
            items.append({
                'item': line.code or line.bill_no or str(line.id),
                'name': line.name or '',
                'workType': line.work_type_id.name or _('Other'),
                'value': line.subtotal or 0.0,
                'executed': executed,
            })
        return items

    def _packages(self, boq):
        """BOQ work types, in BOQ order. Income is not connected yet."""
        seen, result = set(), []
        for line in self._boq_item_lines(boq):
            name = line.work_type_id.name
            if name and name not in seen:
                seen.add(name)
                result.append({'code': line.work_type_id.code or name, 'name': name})
        return result

    @staticmethod
    def _schedule_items(plan):
        if not plan:
            return []
        items = []
        for line in plan.schedule_line_ids.sorted(lambda l: (l.sequence, l.id)):
            boq_line = line.boq_line_id
            items.append({
                'item': boq_line.code or boq_line.bill_no or str(line.id),
                'name': line.task or boq_line.name or '',
                'workType': boq_line.work_type_id.name or _('Other'),
                'start': fields.Date.to_string(line.date_start) if line.date_start else False,
                'end': fields.Date.to_string(line.date_end) if line.date_end else False,
            })
        return items

    # ------------------------------------------------------------------ cost
    def _cost_classes(self, budget_by_categ, ledger):
        """One row per budget cost type (plus any spent category that has no budget line)."""
        rows = OrderedDict((c.name, {'name': c.name, 'budget': amt, 'booked': 0.0, 'unbooked': 0.0})
                           for c, amt in budget_by_categ.items())
        for e in ledger:
            row = rows.setdefault(e['costClass'], {'name': e['costClass'], 'budget': 0.0, 'booked': 0.0, 'unbooked': 0.0})
            row['booked' if e['booked'] else 'unbooked'] += e['amount']
        return list(rows.values())

    @staticmethod
    def _rebar_cost_type(budget_by_categ, ledger):
        names = [c.name for c in budget_by_categ] + [e['costClass'] for e in ledger]
        for n in names:
            if any(k in (n or '').lower() for k in ('reinforcement', 'rebar')):
                return n
        return False

    def _project_line_domain(self, project):
        domain = [('purchase_line_id.order_id.project_id', '=', project.id)]
        if project.account_id:
            domain = ['|', ('analytic_distribution', 'in', [project.account_id.id])] + domain
        return domain

    def _ledger(self, env, project, budget_by_categ):
        """Bill lines (VAT incl.) of the project + purchase-order lines not billed yet."""
        rows = []
        if 'account.move.line' not in env:
            return rows
        company_currency = project.company_id.currency_id or env.company.currency_id
        AML = env['account.move.line']
        lines = AML.search([
            ('move_id.move_type', 'in', ('in_invoice', 'in_refund')),
            ('move_id.state', 'in', ('draft', 'posted')),
            ('display_type', '=', 'product'),
        ] + self._project_line_domain(project), order='date desc, id desc')
        for line in lines:
            move = line.move_id
            sign = -1.0 if move.move_type == 'in_refund' else 1.0
            amount = line.price_total
            if move.currency_id and move.currency_id != company_currency:
                amount = move.currency_id._convert(amount, company_currency, move.company_id, line.date or fields.Date.today())
            common = dict(
                ref=move.name if move.name and move.name != '/' else (move.ref or _('Draft bill')),
                source=_('Vendor bill') if move.state == 'posted' else _('Draft bill'),
                partner=move.partner_id.name or '',
                date=line.date or move.invoice_date or move.date,
                po_line=line.purchase_line_id,
                res_model='account.move', res_id=move.id,
            )
            if move.state == 'posted' and move.payment_state == 'partial' and move.amount_total:
                # Partly paid: each line splits by the share of the bill already paid.
                # Paid part -> booked row, unpaid part -> unbooked row (same bill number).
                paid_ratio = max(min((move.amount_total - move.amount_residual) / move.amount_total, 1.0), 0.0)
                rows.append(self._ledger_row(line, budget_by_categ, amount=sign * amount * paid_ratio,
                                             booked=True, part='paid', **common))
                rows.append(self._ledger_row(line, budget_by_categ, amount=sign * amount * (1.0 - paid_ratio),
                                             booked=False, part='unpaid', **common))
                continue
            booked = move.state == 'posted' and move.payment_state in PAID_STATES
            rows.append(self._ledger_row(line, budget_by_categ, amount=sign * amount, booked=booked, **common))
        # Purchase-order quantities not billed yet: unbooked
        if 'purchase.order.line' in env:
            pol = env['purchase.order.line'].search([
                ('order_id.project_id', '=', project.id),
                ('order_id.state', 'in', ('purchase', 'done')),
                ('display_type', '=', False),
            ])
            for line in pol:
                qty = line.product_qty or 0.0
                left = qty - (line.qty_invoiced or 0.0)
                if qty <= 0 or left <= 1e-6:
                    continue
                order = line.order_id
                amount = line.price_total * left / qty
                if order.currency_id and order.currency_id != company_currency:
                    amount = order.currency_id._convert(amount, company_currency, order.company_id,
                                                        (order.date_approve or order.date_order or fields.Datetime.now()).date())
                rows.append(self._ledger_row(
                    line, budget_by_categ,
                    ref=order.name, source=_('Purchase order'),
                    partner=order.partner_id.name or '',
                    date=(order.date_approve or order.date_order).date() if (order.date_approve or order.date_order) else fields.Date.today(),
                    amount=amount, booked=False, po_line=line,
                    res_model='purchase.order', res_id=order.id,
                ))
        # Site payroll / expense requests: added here once those modules are installed.
        return rows

    def _ledger_row(self, line, budget_by_categ, ref, source, partner, date, amount, booked, po_line,
                    res_model, res_id, part=False):
        categ = line.product_id.categ_id
        cost_type = self._cost_type_for(categ, budget_by_categ) if categ else categ
        work_type, description = self._store_request_info(po_line, line)
        return {
            'id': '%s-%s%s' % (line._name, line.id, '-' + part if part else ''),
            # 'paid' / 'unpaid' when a partly paid bill line is split in two
            'part': part,
            'date': fields.Date.to_string(date) if date else '',
            'ref': ref,
            'source': source,
            'partner': partner,
            'costClass': cost_type.name if cost_type else _('Uncategorised'),
            'productCategory': categ.complete_name if categ else _('Uncategorised'),
            'workType': work_type,
            'description': description,
            'amount': amount,
            'booked': booked,
            'resModel': res_model,
            'resId': res_id,
        }

    @staticmethod
    def _store_request_info(po_line, line):
        """(work item, description) from the store request behind the purchase order."""
        fallback = (line.name or line.product_id.display_name or '').strip()
        order = po_line.order_id if po_line else False
        request = order.purchase_request_id if order and 'purchase_request_id' in order._fields else False
        if not request:
            return None, fallback
        sr = request.material_request_id if 'material_request_id' in request._fields else False
        work = (request.description_of_work_id if 'description_of_work_id' in request._fields else False) \
            or (sr.description_of_work_id if sr and 'description_of_work_id' in sr._fields else False)
        description = fallback
        if sr and line.product_id:
            sr_lines = sr.material_request_line_ids if 'material_request_line_ids' in sr._fields else sr.browse()
            match = sr_lines.filtered(lambda l: l.product_id == line.product_id and l.description)[:1]
            if match:
                description = match.description
        return (work.name if work else None), description

    # ------------------------------------------------------------------ progress / tasks
    @staticmethod
    def _task_stages(env, project):
        """The project's own task stages (task board columns), read live so renamed, added
        or reordered stages show as they are. Each with its number of tasks (cancelled excluded)."""
        Task = env['project.task']
        stages = env['project.task.type'].search([('project_ids', 'in', project.id)], order='sequence, id')
        groups = Task._read_group(
            [('project_id', '=', project.id), ('state', '!=', '1_canceled')],
            ['stage_id', 'state'], ['__count'])
        counts, done = {}, {}
        for stage, state, count in groups:
            counts[stage.id] = counts.get(stage.id, 0) + count
            if state == '1_done':
                done[stage.id] = done.get(stage.id, 0) + count
        rows = [{
            'id': s.id,
            'name': s.name,
            'fold': bool(s.fold),
            'count': counts.get(s.id, 0),
            'done': done.get(s.id, 0),
        } for s in stages]
        # Tasks sitting in a stage that is not (or no longer) linked to the project
        orphan = sum(c for sid, c in counts.items() if sid not in {s.id for s in stages})
        if orphan:
            rows.append({'id': 0, 'name': _('No stage'), 'fold': False, 'count': orphan,
                         'done': sum(c for sid, c in done.items() if sid not in {s.id for s in stages})})
        return rows

    @staticmethod
    def _task_counts(env, project):
        Task = env['project.task']
        base = [('project_id', '=', project.id), ('state', '!=', '1_canceled')]
        total = Task.search_count(base)
        done = Task.search_count(base + [('state', '=', '1_done')])
        return {'total': total, 'done': done}

    # ------------------------------------------------------------------ income
    @staticmethod
    def _ipcs(env, project):
        if 'mefs.boq.payment' not in env:
            return []
        pays = env['mefs.boq.payment'].search(
            [('project_id', '=', project.id), ('state', 'not in', ('draft', 'cancel'))], order='date desc, id desc')
        return [{
            'id': p.id,
            'name': p.name,
            'boq': (p.boq_id.revision_name or p.boq_id.name) if p.boq_id else '',
            'date': fields.Date.to_string(p.date) if p.date else '',
            'state': p.state,
            # value of the work certified in this IPC, before VAT
            'amount': p.total_current_amount or 0.0,
        } for p in pays]

    # ------------------------------------------------------------------ machinery
    @staticmethod
    def _machines(env, project):
        if 'equipment.timesheet.line' not in env:
            return []
        lines = env['equipment.timesheet.line'].search([
            ('timesheet_id.project_id', '=', project.id),
            ('timesheet_id.state', '=', 'approved'),
        ])
        by_eq = OrderedDict()
        for l in lines:
            eq = l.equipment_id
            row = by_eq.setdefault(eq.id, {
                'id': eq.id, 'name': eq.display_name, 'hours': 0.0, 'fuel': 0.0, 'fuelBirr': None,
                'worked': set(), 'logged': set(), 'from': None, 'to': None,
            })
            row['hours'] += l.total_hours or 0.0
            row['fuel'] += l.fuel_consumed or 0.0
            day = l.timesheet_id.date
            if day:
                if (l.total_hours or 0.0) > 0:
                    row['worked'].add(day)
                if (l.total_hours or 0.0) > 0 or (l.idle_time or 0.0) > 0:
                    row['logged'].add(day)
                row['from'] = min(row['from'], day) if row['from'] else day
                row['to'] = max(row['to'], day) if row['to'] else day
        result = []
        for row in by_eq.values():
            result.append({
                'id': row['id'], 'name': row['name'], 'hours': row['hours'], 'fuel': row['fuel'],
                'fuelBirr': None,  # source still to be agreed
                'daysWorked': len(row['worked']), 'daysLogged': len(row['logged']),
                'from': fields.Date.to_string(row['from']) if row['from'] else '',
                'to': fields.Date.to_string(row['to']) if row['to'] else '',
            })
        return result
