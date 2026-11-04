from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError


class TestProjectLifecycle(TransactionCase):

    def setUp(self):
        super().setUp()
        self.stage_design = self.env.ref('mefs_project_lifecycle.stage_design')
        self.stage_tendering = self.env.ref('mefs_project_lifecycle.stage_tendering')
        self.stage_permits = self.env.ref('mefs_project_lifecycle.stage_permits')
        self.stage_construction = self.env.ref('mefs_project_lifecycle.stage_construction')
        self.stage_completed = self.env.ref('mefs_project_lifecycle.stage_completed')

    def _create_project(self, project_type='full_scope', **kwargs):
        vals = {'name': 'Test Project', 'project_type': project_type}
        vals.update(kwargs)
        return self.env['project.project'].create(vals)

    def test_stage_pipeline_types(self):
        """Design/Tendering are full-scope-only; Construction allows BOQ revision."""
        self.assertEqual(self.stage_design.pipeline_type, 'full_scope_only')
        self.assertEqual(self.stage_tendering.pipeline_type, 'full_scope_only')
        self.assertEqual(self.stage_permits.pipeline_type, 'both')
        self.assertEqual(self.stage_construction.pipeline_type, 'both')
        self.assertTrue(self.stage_construction.allow_boq_revision)
        self.assertFalse(self.stage_design.allow_boq_revision)

    def test_search_filters_full_scope_stages_for_subcontracted(self):
        """Subcontracted context excludes full_scope_only stages from search."""
        Stage = self.env['project.project.stage']
        self.assertIn(self.stage_design, Stage.search([]))
        sub_stages = Stage.with_context(
            pipeline_project_type='subcontracted_scope'
        ).search([])
        self.assertNotIn(self.stage_design, sub_stages)
        self.assertNotIn(self.stage_tendering, sub_stages)
        self.assertIn(self.stage_construction, sub_stages)

    def test_default_get_full_scope_defaults(self):
        """default_get defaults to full_scope and sets the first stage by sequence."""
        defaults = self.env['project.project'].default_get(
            ['project_type', 'stage_id']
        )
        self.assertEqual(defaults['project_type'], 'full_scope')
        stage = self.env['project.project.stage'].browse(defaults['stage_id'])
        self.assertTrue(stage)

    def test_default_get_subcontracted_routes_to_valid_stage(self):
        """default_get with subcontracted default picks a non-full-scope-only stage."""
        defaults = self.env['project.project'].with_context(
            default_project_type='subcontracted_scope'
        ).default_get(['project_type', 'stage_id'])
        self.assertEqual(defaults['project_type'], 'subcontracted_scope')
        stage = self.env['project.project.stage'].browse(defaults['stage_id'])
        self.assertNotEqual(stage.pipeline_type, 'full_scope_only')

    def test_create_subcontracted_skips_full_scope_stages(self):
        """Subcontracted project creation lands in a non-full-scope-only stage."""
        project = self._create_project('subcontracted_scope')
        self.assertEqual(project.project_type, 'subcontracted_scope')
        self.assertTrue(project.stage_id)
        self.assertNotEqual(project.stage_id.pipeline_type, 'full_scope_only')
        self.assertNotIn(project.stage_id, (self.stage_design, self.stage_tendering))

    def test_create_subcontracted_with_construction_stage(self):
        """Subcontracted project can explicitly use the Construction stage."""
        project = self._create_project(
            'subcontracted_scope', stage_id=self.stage_construction.id
        )
        self.assertEqual(project.stage_id, self.stage_construction)

    def test_create_full_scope_defaults_to_first_stage(self):
        """Full scope project defaults to the earliest stage by sequence."""
        project = self._create_project('full_scope')
        self.assertEqual(project.project_type, 'full_scope')
        self.assertTrue(project.stage_id)
        first_stage = self.env['project.project.stage'].search(
            [], order='sequence', limit=1
        )
        self.assertEqual(project.stage_id, first_stage)

    def test_subcontracted_cannot_use_full_scope_stage(self):
        """Constraint blocks subcontracted projects on full_scope_only stages."""
        with self.assertRaises(ValidationError):
            self._create_project(
                'subcontracted_scope', stage_id=self.stage_design.id
            )

    def test_onchange_switching_to_subcontracted_resets_stage(self):
        """Switching a full-scope-only stage project to subcontracted resets stage."""
        project = self.env['project.project'].new({
            'project_type': 'subcontracted_scope',
            'stage_id': self.stage_design.id,
        })
        project._onchange_project_type()
        self.assertNotEqual(project.stage_id.pipeline_type, 'full_scope_only')

    def test_onchange_full_scope_without_stage_sets_first(self):
        """Switching to full_scope without a stage sets the first stage."""
        project = self.env['project.project'].new({
            'project_type': 'full_scope',
        })
        project._onchange_project_type()
        self.assertTrue(project.stage_id)

    def test_read_group_expand_full_uses_context(self):
        """_read_group_expand_full excludes full-scope-only stages via context."""
        Project = self.env['project.project']
        Stage = self.env['project.project.stage']
        stages = Project.with_context(
            pipeline_project_type='subcontracted_scope'
        )._read_group_expand_full(Stage, [])
        self.assertNotIn(self.stage_design, stages)
        self.assertIn(self.stage_construction, stages)

    def test_read_group_expand_full_uses_domain(self):
        """_read_group_expand_full excludes full-scope-only stages via domain."""
        Project = self.env['project.project']
        Stage = self.env['project.project.stage']
        stages = Project._read_group_expand_full(
            Stage, [('project_type', '=', 'subcontracted_scope')]
        )
        self.assertNotIn(self.stage_design, stages)
        self.assertIn(self.stage_construction, stages)

    def test_get_formview_action_injects_pipeline_context(self):
        """get_formview_action injects pipeline_project_type into the context."""
        project = self._create_project('subcontracted_scope')
        action = project.get_formview_action()
        self.assertEqual(
            action['context']['pipeline_project_type'], 'subcontracted_scope'
        )
