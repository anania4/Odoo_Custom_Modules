from odoo import _, api, fields, models
from collections import defaultdict
from odoo.exceptions import ValidationError, UserError
from odoo.osv.expression import AND

from datetime import datetime, timedelta


# Product types (product.template.type) allowed on the request lines for each purpose.
PURPOSE_PRODUCT_TYPES = {
    'goods': ('consu',),
    'service': ('service',),
    'maintenance': ('consu', 'service'),
}


class MaterialRequest(models.Model):
    _name = 'material.request'
    _description = 'Material Request'
    _inherit = ["mail.thread", "mail.activity.mixin", "analytic.mixin", "custom.purchase.notify.mixin"]
    _bell_only_notifications = True
    _check_company_auto = True

    state = fields.Selection([
        ('draft', 'Draft'),
        ('approval_requested', 'Approval Requested'),
        ('approved', 'Department Manager Approved'),
        ('pr', 'On Purchase Request'),
        ('siv', 'On Store Issue Voucher'),
        ('delivered', 'Delivered'),
        ('rejected', 'Rejected')
    ], string='State', default='draft', tracking=True)
    name = fields.Char(
        string="Request Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )

    current_user_department_id = fields.Many2one('hr.department', string="Current User Department", compute="_compute_current_user_department_id")

    @api.depends('requested_by_id')
    def _compute_current_user_department_id(self):
        for record in self:
            record.current_user_department_id = self.env.user.employee_id.department_id if self.env.user.employee_id else False

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('material.request') or _('New')
        return super(MaterialRequest, self).create(vals)

    def action_view_siv(self):
        self.ensure_one()
        action = self.env.ref('custom_purchase_process.action_product_siv').sudo().read()[0]
        action['domain'] = [('material_request_id', '=', self.id)]
        action['context'] = dict(self.env.context, default_material_request_id=self.id)
        return action

    purchase_request_count = fields.Integer(
        string="Purchase Request Count",
        compute="_compute_purchase_request_count",
        store=True
    )

    company_ids = fields.Many2many('res.company', string='Companies', compute='_compute_company_ids', store=True)

    @api.depends('company_id')
    def _compute_company_ids(self):
        """Compute the companies the current user has access to."""
        for record in self:
            record.company_ids = self.env.user.company_ids


    pr_ids = fields.One2many('purchase.request', 'material_request_id', string='PRs')
    
    purchase_request_status = fields.Selection(
        string="Purchase Request Status",
        selection=[
            ('draft', 'On Draft'),
            ('submitted', 'Submitted'),
            ('checked', 'Checked'),
            ('reviewed', 'Reviewed'),
            ('approved', 'Approved'),
            ('rfq', 'On RFQ'),
            ('supplier_analysis', 'On Supplier Analysis'),
            ('quality_evaluation', 'On Quality Evaluation'),
            ('purchase_order', 'Purchase Ordered'),
            ('rejected', 'Rejected'),
            ('no_pr', 'No PR Created')
        ],
        compute='_compute_purchase_request_status',
        store=True,
        help="Status of the related Purchase Request"
    )

    @api.depends('pr_ids', 'pr_ids.state')
    def _compute_purchase_request_status(self):
        """Compute the purchase request status based on related PRs."""
        allowed = {value for value, _label in self._fields['purchase_request_status'].selection}
        for record in self:
            if record.pr_ids:
                # Get the latest PR (most recent one)
                latest_pr = record.pr_ids.sorted('id', reverse=True)[:1]
                state = latest_pr.state
                # Records created before the workflow was reshaped can still carry
                # a retired state; the status badge cannot render an unknown value.
                record.purchase_request_status = state if state in allowed else 'draft'
            else:
                record.purchase_request_status = 'no_pr'

    @api.depends('pr_ids')
    def _compute_purchase_request_count(self):
        """ Compute the count of related POs. """
        for record in self:
            record.purchase_request_count = len(record.pr_ids)

    def action_view_purchase_requests(self):
        """Open related Purchase Requests."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Requests',
            'res_model': 'purchase.request',
            'view_mode': 'list,form',
            'domain': [('material_request_id', '=', self.id)],
            'context': dict(self.env.context, default_material_request_id=self.id),
        }

    date_requested = fields.Datetime(string="Date Requested", default=fields.Datetime.now)
    date_approved = fields.Datetime(string="Date Approved")

    requested_by_id = fields.Many2one('res.users', string="Requested By", default=lambda self: self.env.user, readonly=True)
    request_department_id = fields.Many2one(
        'hr.department',
        string="Request Department",
        compute="_compute_request_department",
        store=True
    )
    approved_by_id = fields.Many2one('res.users', string="Approved By")
    purpose = fields.Selection(
        selection=[
            ('goods', 'Goods'),
            ('service', 'Service'),
            ('maintenance', 'Maintenance'),
        ],
        string="Purpose",
        default='goods',
        required=True,
        help="Restricts the products selectable on the request lines: goods only, service only, "
             "or both goods and services for maintenance."
    )
    purpose_label = fields.Char(string="Purpose Label", compute='_compute_purpose_label')
    maintenance_reference = fields.Selection(
        selection='_selection_maintenance_reference',
        string="Maintenance Reference",
        help="Maintenance request number this request covers, taken from the "
             "maintenance module. Only shown when the purpose is Maintenance.",
    )

    @api.model
    def _selection_maintenance_reference(self):
        """Available maintenance reference numbers, from the maintenance module."""
        requests = self.env['maintenance.request'].sudo().search([
            ('code', '!=', '/'),
        ], order='code')
        return [(request.code, request.code) for request in requests]

    @api.depends('purpose')
    def _compute_purpose_label(self):
        labels = dict(self._fields['purpose']._description_selection(self.env))
        for record in self:
            record.purpose_label = labels.get(record.purpose) or ''

    def _get_purpose_label(self):
        self.ensure_one()
        labels = dict(self._fields['purpose']._description_selection(self.env))
        return labels.get(self.purpose) or ''

    @api.constrains('purpose')
    def _check_purpose_lines(self):
        for record in self:
            allowed = PURPOSE_PRODUCT_TYPES.get(record.purpose)
            if not allowed:
                continue
            for line in record.material_request_line_ids:
                if line.product_id and line.product_id.type not in allowed:
                    raise ValidationError(_(
                        "The product '%(product)s' cannot be added to request '%(request)s' because "
                        "its type is not allowed for the '%(purpose)s' purpose.",
                        product=line.product_id.display_name,
                        request=record.name,
                        purpose=record._get_purpose_label(),
                    ))
    reason_reset_to_draft = fields.Char(string="Reason Reset to Draft")
    reason_for_back_to_sr = fields.Text(string="Reason for Back to SR", readonly=True)
    rejection_reason = fields.Text(string="Rejection Reason", readonly=True)

    requested_by_char = fields.Char(string="Requested By (Name)", compute="_compute_requested_by_char", store=True)
    approved_by_char = fields.Char(string="Approved By (Name)", compute="_compute_approved_by_char", store=True)

    company_id = fields.Many2one(
            'res.company',
            string='Company',
            default=lambda self: self.env.company,
            required=False,
            index=True,
            tracking=True,
            readonly=True
        )
   
    user_department_id = fields.Many2one(
        'hr.department',
        string="User Department",
        compute="_compute_user_department",
        store=True
    )



    @api.depends('requested_by_id')
    def _compute_user_department(self):
        for record in self:
            employee = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)
            record.user_department_id = employee.department_id if employee else False



    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string="Warehouse",
        domain="[('company_id', '=', company_id)]",
        help="Warehouse the purchased goods are finally received into. It does not limit the Store checked for availability.",
    )

    # The Warehouse above is only where the purchased goods are finally received.
    # The Store to check is independent of it: availability may be checked in any
    # internal location of the company, whatever warehouse it belongs to.
    from_location_id = fields.Many2one(
        "stock.location",
        string="Store",
        domain="[('company_id', '=', company_id), ('usage', '=', 'internal')]",
    )

    picking_type_id = fields.Many2one(
        "stock.picking.type",
        string="SIV Voucher",
        domain="[('default_location_src_id', '=', from_location_id), ('code', '=', 'internal')]"
    )

    project_id = fields.Many2one(
        'project.project',
        string="Project",
    )

    approved_boq_id = fields.Many2one(
        'mefs.boq',
        string="Approved BOQ",
        compute='_compute_approved_boq_id',
        store=True,
        readonly=False,
        help="The BOQ of the selected project: the approved (locked) one when there is one, "
             "otherwise its latest BOQ. The BOQ descriptions offered on the request come from it.",
    )
    description_of_work_id = fields.Many2one(
        'mefs.boq.work.type',
        string="Description of Work",
        domain="[('id', 'in', boq_work_type_ids)]",
        help="Work type picked from the BOQ of the selected project.",
    )

    @api.depends('project_id')
    def _compute_approved_boq_id(self):
        Boq = self.env['mefs.boq'].sudo()
        for record in self:
            boq = Boq
            if record.project_id:
                project_boqs = Boq.search([('project_id', '=', record.project_id.id)], order='id desc')
                # Prefer the approved BOQ; otherwise the newest one that was not replaced by a revision.
                boq = (project_boqs.filtered(lambda b: b.state == 'locked')[:1]
                       or project_boqs.filtered(lambda b: b.state != 'revised')[:1]
                       or project_boqs[:1])
            record.approved_boq_id = boq

    boq_work_type_ids = fields.Many2many(
        'mefs.boq.work.type',
        string="BOQ Work Types",
        compute='_compute_boq_work_type_ids',
        help="Work types used in the BOQ of the selected project (each once).",
    )

    @api.depends('project_id')
    def _compute_boq_work_type_ids(self):
        """Work types used by the BOQ lines of the selected project, each name once."""
        Line = self.env['mefs.boq.line'].sudo()
        WorkType = self.env['mefs.boq.work.type'].sudo()
        for record in self:
            unique = WorkType.browse()
            if record.project_id:
                lines = Line.search([
                    ('boq_id.project_id', '=', record.project_id.id),
                    ('boq_id.state', '!=', 'revised'),
                ])
                work_types = lines.work_type_id
                # Lines that only carry the work type code (no work type record yet)
                for code in {line.work_type for line in lines if line.work_type and not line.work_type_id}:
                    work_types |= WorkType.search([('code', '=ilike', code)])
                seen = set()
                for work_type in work_types.sorted(lambda wt: (wt.sequence, wt.id)):
                    key = (work_type.name or '').strip().lower()
                    if key not in seen:
                        seen.add(key)
                        unique |= work_type
            record.boq_work_type_ids = unique

    @api.onchange('project_id')
    def _onchange_project_id_boq(self):
        """A new project means a new BOQ: drop the descriptions picked from the old one."""
        for record in self:
            record.description_of_work_id = False

    @api.constrains('description_of_work_id', 'project_id')
    def _check_description_of_work_in_boq(self):
        for record in self:
            if not (record.description_of_work_id and record.project_id):
                continue
            allowed = {(wt.name or '').strip().lower() for wt in record.sudo().boq_work_type_ids}
            if (record.description_of_work_id.name or '').strip().lower() not in allowed:
                raise ValidationError(_(
                    "The description of work must be a work type of the BOQ of the project."
                ))

    check_stock_done = fields.Boolean(string="Stock Checked", default=False)

    @api.onchange('from_location_id')
    def _onchange_from_location_id(self):
        for rec in self:
            if not rec.from_location_id:
                rec.picking_type_id = False
                continue
            if rec.picking_type_id.code == 'internal' and \
                    rec.picking_type_id.default_location_src_id == rec.from_location_id:
                continue
            rec.picking_type_id = self.env['stock.picking.type'].search([
                ('default_location_src_id', '=', rec.from_location_id.id),
                ('code', '=', 'internal')
            ], limit=1)

    generate_siv = fields.Boolean(string="Generate SR")
    generate_pr = fields.Boolean(string="Generate PR")

    material_request_line_ids = fields.One2many(
        'material.request.line',
        'material_request_id',
        string="Material Request Lines"
    )

    siv_count = fields.Integer(string="SIV Count", compute="_compute_siv_count")

    siv_ids = fields.One2many('product.siv', 'material_request_id', string='SRs')

    @api.depends('siv_ids')
    def _compute_siv_count(self):
        """ Compute the count of related SIV. """
        for record in self:
            record.siv_count = len(record.siv_ids)

    def check_stock(self):
        for record in self:
            if not record.from_location_id:
                raise UserError(_("Please specify a source location (Store) before checking stock."))

            # Quantities are refreshed on every check until their document exists,
            # so changed stock or edited requested quantities are always picked up.
            pr_created = bool(record.sudo().pr_ids.filtered(lambda pr: pr.state != 'rejected'))
            siv_created = bool(record.siv_ids)

            for line in record.material_request_line_ids:
                if not line.product_id:
                    continue
                available_qty = max(0.0, self.env['stock.quant']._get_available_quantity(
                    line.product_id, record.from_location_id))
                line.available_qty = available_qty

                # PR = Requested - Available (0 when enough stock is available)
                if not pr_created:
                    line.pr_qty = max(0.0, line.requested_qty - available_qty)

                # SIV = what can be issued now: Requested, capped at Available
                if not siv_created:
                    line.siv_qty = min(line.requested_qty, available_qty)

            record.check_stock_done = True
        return True

    @api.depends('requested_by_id')
    def _compute_requested_by_char(self):
        for record in self:
            record.requested_by_char = record.requested_by_id.name if record.requested_by_id else ""

    @api.depends('requested_by_id')
    def _compute_request_department(self):
        for record in self:
            employee = self.env['hr.employee'].search([('user_id', '=', record.requested_by_id.id)], limit=1)
            record.request_department_id = employee.department_id if employee else False



    @api.depends('approved_by_id')
    def _compute_approved_by_char(self):
        for record in self:
            record.approved_by_char = record.approved_by_id.name if record.approved_by_id else ""

    # def schedule_activity_for_department_manager(self, summary, note):
    #     """Schedule an activity for the manager of the request's department."""
    #     for record in self:
    #         manager = record.request_department_id.manager_id
    #         if manager and manager.user_id:
    #             record.sudo().activity_schedule(
    #                 'mail.mail_activity_data_todo',
    #                 user_id=manager.user_id.id,
    #                 summary=summary,
    #                 note=note,
    #             )


    def action_submit(self):
        """Move to 'Approval Requested' and notify department manager"""
        for request in self:
            if not request.warehouse_id:
                raise ValidationError(_("Please select the warehouse before submitting the request."))

            if not request.material_request_line_ids:
                raise ValidationError(_("You cannot submit a request without any material lines."))

            invalid_lines = request.material_request_line_ids.filtered(lambda l: l.requested_qty < 0)
            if invalid_lines:
                raise ValidationError(_("Requested quantity must be greater than 0 for all material lines."))

            request.write({'state': 'approval_requested'})
            request._notify_submitted()

            # Schedule activity for department manager  
            # request.schedule_activity_for_department_manager(
            #     summary="Material Request Submitted",
            #     note=f"The material request {request.name} has been submitted and requires your approval."
            # )

    def action_approve(self):
        """Move to 'Approved' and notify approvers via activity"""
        for request in self:
            if request.state != 'approval_requested':
                raise UserError(_("Only requests in 'Approval Requested' state can be approved."))



            request.write({
                'state': 'approved',
                'approved_by_id': self.env.user.id,
                'date_approved': fields.Datetime.now(),
            })
            request._notify_approved()


    def action_reject(self):
        """Move back to 'Draft'"""
        if self.state not in ['approval_requested', 'pr', 'siv']:
            raise UserError(_("Only certain states can be rejected."))

        self.state = 'rejected'
        self._notify_rejected()

    def action_reset_to_draft(self):
        """Move back to 'Draft'"""
        self.state = 'draft'
        self._notify_returned_to_draft()

    def action_create_pr(self):
        """Move to 'Purchase Request' and create a Purchase Request."""
        for request in self:
            # Services are not stocked, so availability is neither checked nor required.
            is_service = request.purpose == 'service'
            if not is_service and not request.check_stock_done:
                raise UserError(_("Please check stock availability before creating a Purchase Request."))
            
            # The Purchase Request and the Store Issue Voucher can be created in either
            # order, so a request that already has its SIV ('siv') may still get its PR.
            if request.state not in ('approved', 'siv'):
                raise UserError(_("Only approved requests can generate a Purchase Request."))

            if request.sudo().pr_ids.filtered(lambda pr: pr.state != 'rejected'):
                raise UserError(_("A Purchase Request has already been created for this request."))

            if not request.material_request_line_ids:
                raise UserError(_("No material request lines to create a Purchase Request."))

            # Create Purchase Request
            pr_vals = {
                'name': self.env['ir.sequence'].next_by_code('purchase.request') or _('New'),
                'material_request_id': request.id,
                'project_id': request.project_id.id,
                'approved_boq_id': request.approved_boq_id.id,
                'description_of_work_id': request.description_of_work_id.id,
                'purpose': request._get_purpose_label(),
                'date_requested': fields.Datetime.now(),
                'requested_by': self.env.user.id,
                'company_id': self.env.company.id,
                'state': 'draft',
            }
            purchase_request = self.env['purchase.request'].create(pr_vals)

            # Create Purchase Request Lines
            for line in request.material_request_line_ids:
                if is_service:
                    # No stock check runs for services, so pr_qty is unset; buy the full requested quantity.
                    line.pr_qty = line.requested_qty
                self.env['purchase.request.line'].with_context(allow_create_purchase_request_line=True).create({
                    'purchase_request_id': purchase_request.id,
                    'material_request_line_id': line.id,
                    'product_id': line.product_id.id,
                    'description': line.description or line.product_id.name,
                    'product_uom_id': line.product_uom_id.id,
                    'quantity': line.pr_qty,
                    'unit_price': 0.0,
                   
                })

            # Update Material Request. When the SIV already exists the request stays on
            # 'siv' (both documents are done) instead of stepping back to 'pr'.
            if request.state == 'approved':
                request.state = 'pr'
            request.generate_pr = True
            request._notify_purchase_request_created(purchase_request)

            # Open the created Purchase Request
            if self.env.user.has_group('custom_purchase_process.group_custom_purchase_request_approvers'):
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'purchase.request',
                    'view_mode': 'form',
                    'res_id': purchase_request.id,
                    'target': 'current',
                }
            

    def action_create_siv(self):
        """Move to 'Store Issue Voucher' and create Product SIV"""
        self.ensure_one()
        if self.state not in ('approved', 'pr', 'siv'):
            raise UserError(_("Only approved requests can generate a Store Issue Voucher."))
        self.check_stock()
        if not self.check_stock_done:
            raise UserError(_("Please check stock availability before creating a Store Issue Voucher."))
        
        if not self.material_request_line_ids:
            raise UserError(_("There are no material request lines to create a Store Issue Voucher."))
        
        # Filter lines that have available stock
        available_lines = []
        unavailable_lines = []
        
        for line in self.material_request_line_ids:
            # Ensure siv_qty doesn't exceed available quantity
            if line.siv_qty > line.available_qty:
                line.siv_qty = line.available_qty
            
            if line.available_qty > 0 and line.siv_qty > 0:
                available_lines.append(line)
            else:
                unavailable_lines.append(line)
        
        # Check if we have any lines with available stock
        if not available_lines:
            raise UserError(_("No products are available in stock to create a Store Issue Voucher."))
        
        # Create the Product SIV record
        siv = self.env['product.siv'].create({
            'material_request_id': self.id,
            'requested_by': self.requested_by_id.id,
            'state': 'draft',
            'operation_type_id': self.picking_type_id.id,  # Ensure picking_type_id exists in your model
        })

        # Create lines for Product SIV based on available Material Request lines only
        siv_lines_created = 0
        for line in available_lines:
            self.env['product.siv.line'].create({
                'product_siv_id': siv.id,
                'material_request_line_id': line.id,
                'product_id': line.product_id.id,
                'requested_qty': line.siv_qty,
                'issued_qty': 0.0,  # Set initial issued quantity to 0
            })
            siv_lines_created += 1

        # Update the state and flags
        self.state = 'siv'
        self.generate_siv = True
        self._notify_siv_created(siv)

        # Schedule activity for store request users
        # self.schedule_activity_for_group_users(
        #     group_xml_id='custom_purchase_process.group_store_request_user',
        #     summary="Store Issue Voucher Created",
        #     note=f"A Store Issue Voucher has been created from Material Request {self.name} and requires your action."
        # )

        # Show notification about partially available items
        if unavailable_lines:
            unavailable_products = [line.product_id.name for line in unavailable_lines]
            notification_message = f"SIV created for {siv_lines_created} available product(s). "
            notification_message += f"The following products were not included due to insufficient stock: {', '.join(unavailable_products)}"
            
            # Tell the person creating the SIV through the bell
            self._bell_notify(
                self.env.user, _("SIV created (partial)"), notification_message,
                notif_type='warning', icon='fa-truck', include_self=True)

        # Open the created Product SIV record in form view
        if self.env.user.has_group('custom_purchase_process.group_store_request_user'):
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'product.siv',
                'view_mode': 'form',
                'res_id': siv.id,
                'target': 'current',
            }

    # ------------------------------------------------------------------
    # Bell notifications
    # ------------------------------------------------------------------
    def _notify_context(self):
        self.ensure_one()
        label = self._notify_label()
        project = self.project_id.display_name
        return label, (_(" (project %s)", project) if project else '')

    def _notify_submitted(self):
        label, project = self._notify_context()
        approvers = self._get_group_users('custom_purchase_process.group_material_request_approver')
        self._notify_flow(
            forward=approvers,
            forward_title=_("Store Requisition awaits your approval"),
            forward_message=_("%s%s was submitted by %s and awaits your approval.",
                              label, project, self.env.user.name),
            notif_type='info', icon='fa-clipboard',
        )

    def _notify_approved(self):
        label, project = self._notify_context()
        store_managers = self._get_group_users('custom_purchase_process.group_material_request_store_manager')
        self._notify_flow(
            forward=store_managers,
            forward_title=_("Store Requisition awaits your action"),
            forward_message=_("%s%s was approved by %s. Check availability, then create the "
                              "Purchase Request and/or the Store Issue Voucher.",
                              label, project, self.env.user.name),
            backward=self.requested_by_id,
            backward_title=_("Your Store Requisition was approved"),
            backward_message=_("%s%s was approved by %s.", label, project, self.env.user.name),
            icon='fa-check-circle',
        )

    def _notify_rejected(self):
        label, project = self._notify_context()
        self._notify_flow(
            backward=self.requested_by_id,
            backward_title=_("Your Store Requisition was rejected"),
            backward_message=_("%s%s was rejected by %s.", label, project, self.env.user.name),
            icon='fa-times-circle',
        )

    def _notify_returned_to_draft(self):
        label, project = self._notify_context()
        self._notify_flow(
            forward=self.requested_by_id,
            forward_title=_("Your Store Requisition was returned"),
            forward_message=_("%s%s was sent back to draft by %s. Please review and resubmit.",
                               label, project, self.env.user.name),
            icon='fa-undo',
        )

    def _notify_purchase_request_created(self, purchase_request):
        label, project = self._notify_context()
        officers = self._get_group_users(
            'custom_purchase_process.group_custom_purchase_request_purchaser',
            ['custom_purchase_process.group_custom_purchase_request_approvers'])
        self._notify_flow(
            backward=self.requested_by_id,
            backward_title=_("Purchase Request created for your request"),
            backward_message=_("%s was created for your Store Requisition %s.", purchase_request.name, label),
            icon='fa-shopping-cart',
        )
        # Next in line: the procurement team opens the Purchase Request itself.
        purchase_request._notify_flow(
            forward=officers,
            forward_title=_("Purchase Request awaits you"),
            forward_message=_("%s%s was created from %s. Assign a procurement officer and submit it.",
                              purchase_request.name, project, label),
            icon='fa-shopping-cart',
        )

    def _notify_siv_created(self, siv):
        label, project = self._notify_context()
        store_users = self._get_group_users(
            'custom_purchase_process.group_store_request_user',
            ['custom_purchase_process.group_store_request_approver'])
        self._notify_flow(
            backward=self.requested_by_id,
            backward_title=_("Store Issue Voucher created for your request"),
            backward_message=_("%s was created for your Store Requisition %s.", siv.name, label),
            icon='fa-truck',
        )
        siv._notify_flow(
            forward=store_users,
            forward_title=_("Store Issue Voucher awaits you"),
            forward_message=_("%s was created from %s%s. Request approval for it.", siv.name, label, project),
            icon='fa-truck',
        )

    def action_deliver(self):
        """Mark as Delivered"""
        if self.state != 'siv':
            raise UserError(_("Only requests in 'Store Issue Voucher' state can be marked as delivered."))
        self.state = 'delivered'

    def reset_to_draft(self):
        for record in self:
            if not record.reason_reset_to_draft:
                raise UserError(_("Please provide a reason for Reset TO Draft."))

        self._close_flow_activities()
        self.state = 'draft'
    
    def reset_to_approved(self):
        if self.state == 'draft' or self.state == 'approval_requested' or self.state == 'approved':
            raise UserError(_("can't reset to approved"))
        self.state = 'approved'


class MaterialRequestLine(models.Model):
    _name = 'material.request.line'
    _description = 'Material Request Line'

    state = fields.Selection([
        ('draft', 'Draft'),
        ('approval_requested', 'Approval Requested'),
        ('approved', 'Approved'),
        ('pr', 'Purchase Request'),
        ('siv', 'Store Issue Voucher'),
        ('delivered', 'Delivered')
    ], string='State', related='material_request_id.state')

    material_request_id = fields.Many2one(
        'material.request',
        string="Material Request",
        ondelete='cascade'
    )

    product_id = fields.Many2one(
        'product.product',
        string="Product",
        required=True
    )

    description = fields.Char(string="Description", help="Enter the description of the product")

    product_uom_id = fields.Many2one(
        'uom.uom',
        string="Unit of Measure",
        store=True,
        readonly=True,
        compute='_compute_product_uom'
    )

    requested_qty = fields.Float(string="Requested Quantity", required=True, tracking=True)
    available_qty = fields.Float(string="Available Quantity")
    delivered_qty = fields.Float(string="Delivered Quantity", default=0.0)
    pr_qty = fields.Float(string="Purchase Request Quantity", default=0.0, readonly=True)
    siv_qty = fields.Float(string="Store Issue Voucher Quantity", default=0.0, readonly=True)

    generate_siv = fields.Boolean(string="Generate SIV", related="material_request_id.generate_siv")
    generate_pr = fields.Boolean(string="Generate PR", related="material_request_id.generate_pr")

    purpose = fields.Selection(related='material_request_id.purpose', string="Purpose")

    @api.constrains('product_id', 'material_request_id')
    def _check_product_type_matches_purpose(self):
        for line in self:
            allowed = PURPOSE_PRODUCT_TYPES.get(line.purpose)
            if not line.product_id or not allowed:
                continue
            if line.product_id.type not in allowed:
                raise ValidationError(_(
                    "The product '%(product)s' is not allowed for the '%(purpose)s' purpose. "
                    "Goods requests accept goods only, service requests accept services only, "
                    "and maintenance requests accept both.",
                    product=line.product_id.display_name,
                    purpose=line.material_request_id._get_purpose_label(),
                ))

    @api.depends('product_id')
    def _compute_product_uom(self):
        for line in self:
            line.product_uom_id = line.product_id.uom_id if line.product_id else False
