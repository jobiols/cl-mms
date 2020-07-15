# -*- coding: utf-8 -*-
from odoo import http

# class MmsModule(http.Controller):
#     @http.route('/mms_module/mms_module/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/mms_module/mms_module/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('mms_module.listing', {
#             'root': '/mms_module/mms_module',
#             'objects': http.request.env['mms_module.mms_module'].search([]),
#         })

#     @http.route('/mms_module/mms_module/objects/<model("mms_module.mms_module"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('mms_module.object', {
#             'object': obj
#         })