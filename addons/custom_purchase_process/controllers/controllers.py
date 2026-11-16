# -*- coding: utf-8 -*-
# from odoo import http


# class Custom/afroTemplate(http.Controller):
#     @http.route('/custom/afro_template/custom/afro_template/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/custom/afro_template/custom/afro_template/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('custom/afro_template.listing', {
#             'root': '/custom/afro_template/custom/afro_template',
#             'objects': http.request.env['custom/afro_template.custom/afro_template'].search([]),
#         })

#     @http.route('/custom/afro_template/custom/afro_template/objects/<model("custom/afro_template.custom/afro_template"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('custom/afro_template.object', {
#             'object': obj
#         })
