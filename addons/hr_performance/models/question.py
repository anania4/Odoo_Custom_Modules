from odoo import models, fields


class HrPerformanceQuestion(models.Model):
    _name = "hr.performance.question"
    _description = "Performance Evaluation Question"

    name = fields.Text(required=True)
    section = fields.Selection(
        [
            ("customer", "Customer"),
            ("teamwork", "Teamwork"),
            ("work", "Work"),
            ("supervisory", "Supervisory"),
            ("communication_skills","Communication Skills"),
            ("cost_consciousness","Cost Consciousness"),
            ("job_knowledge","Job_Knowledge/Technical_Skills"),
            ("quality_of_work","Quality of work"),
            ("safety","Safety"),
            ("Attendance","Attendance/ Punctuality"),
            ("process_improvement","Process Improvement"),
            ("problem_solving","Problem Solving"),
            ("supervision_motivation","Supervision/ Motivation of follow up jobs"),
            ("dependability_responsibility","Dependability/ Responsibility"),
            ("planning","Planning"),
        ],
        required=True,
    )
    max_score = fields.Integer(default=5)
    active = fields.Boolean(default=True)
