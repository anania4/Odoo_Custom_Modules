from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProjectProjectStage(models.Model):
    _inherit = 'project.project.stage'

    pipeline_type = fields.Selection([
        ('both', 'Both Pipelines'),
        ('full_scope_only', 'Full Scope Only'),
    ], string='Pipeline Availability', default='both', required=True)

    allow_backward = fields.Boolean(
        string='Allow Backward Movement',
        default=True,
        help='If enabled, projects can move back to this stage from a later stage.'
    )

    allow_boq_revision = fields.Boolean(
        string='Allow BOQ Revision',
        default=False,
        help='If enabled, BOQ revisions can be created when project is in this stage.'
    )

    def _get_filtered_stage_domain(self):
        project_type = self.env.context.get('pipeline_project_type')
        if project_type == 'subcontracted_scope':
            return [('pipeline_type', '!=', 'full_scope_only')]
        return []

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        domain = (domain or []) + self._get_filtered_stage_domain()
        return super()._search(domain, offset=offset, limit=limit, order=order)


class ProjectProject(models.Model):
    _inherit = 'project.project'

    project_type = fields.Selection([
        ('full_scope', 'Full Scope'),
        ('subcontracted_scope', 'Subcontracted Scope'),
    ], string='Project Type', default='full_scope', required=True)

    def get_formview_action(self):
        res = super().get_formview_action()
        if self:
            project_type = self.project_type or 'full_scope'
            context = dict(res.get('context', {}))
            context['pipeline_project_type'] = project_type
            res['context'] = context
        return res

    def _read_group_expand_full(self, stages, domain):
        domain_for_stages = []
        # Check context first (used by form view statusbar)
        project_type = self.env.context.get('pipeline_project_type')
        if project_type == 'subcontracted_scope':
            domain_for_stages = [('pipeline_type', '!=', 'full_scope_only')]
        else:
            # Check domain (used by kanban/list grouping with search filter)
            for item in domain or []:
                if isinstance(item, (list, tuple)) and len(item) == 3:
                    if item[0] == 'project_type' and item[1] == '=' and item[2] == 'subcontracted_scope':
                        domain_for_stages = [('pipeline_type', '!=', 'full_scope_only')]
                        break
        return stages.search(domain_for_stages, order='sequence')

    @api.onchange('project_type')
    def _onchange_project_type(self):
        if self.project_type == 'subcontracted_scope':
            if self.stage_id and self.stage_id.pipeline_type == 'full_scope_only':
                self.stage_id = self.env['project.project.stage'].search([
                    ('pipeline_type', '!=', 'full_scope_only'),
                    ('company_id', 'in', [self.company_id.id, False] if self.company_id else [False]),
                ], order='sequence', limit=1)
        elif self.project_type == 'full_scope' and not self.stage_id:
            self.stage_id = self.env['project.project.stage'].search([
                ('company_id', 'in', [self.company_id.id, False] if self.company_id else [False]),
            ], order='sequence', limit=1)

    @api.constrains('stage_id', 'project_type')
    def _check_stage_project_type(self):
        for project in self:
            if (project.project_type == 'subcontracted_scope'
                    and project.stage_id
                    and project.stage_id.pipeline_type == 'full_scope_only'):
                raise ValidationError(_(
                    "Subcontracted Scope projects cannot use the stage '%s'. "
                    "This stage is only available for Full Scope projects.",
                    project.stage_id.name
                ))

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if 'project_type' in fields and 'project_type' not in res:
            res['project_type'] = 'full_scope'
        project_type = res.get('project_type', 'full_scope')
        if 'stage_id' in fields:
            stage = res.get('stage_id')
            stage = self.env['project.project.stage'].browse(stage) if stage else self.env['project.project.stage']
            if project_type == 'subcontracted_scope' and (not stage or stage.pipeline_type == 'full_scope_only'):
                stage = self.env['project.project.stage'].search([
                    ('pipeline_type', '!=', 'full_scope_only'),
                ], order='sequence', limit=1)
                if stage:
                    res['stage_id'] = stage.id
            elif project_type == 'full_scope' and not stage:
                stage = self.env['project.project.stage'].search([], order='sequence', limit=1)
                if stage:
                    res['stage_id'] = stage.id
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('project_type') == 'subcontracted_scope':
                if not vals.get('stage_id'):
                    stage = self.env['project.project.stage'].search([
                        ('pipeline_type', '!=', 'full_scope_only'),
                    ], order='sequence', limit=1)
                    if stage:
                        vals['stage_id'] = stage.id
            elif not vals.get('stage_id'):
                stage = self.env['project.project.stage'].search([], order='sequence', limit=1)
                if stage:
                    vals['stage_id'] = stage.id
        return super().create(vals_list)
