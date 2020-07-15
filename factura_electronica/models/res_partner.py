# -*- coding: utf-8 -*-

from odoo import fields, models


class Partner(models.Model):
    _inherit = 'res.partner'

    nro_iibb = fields.Char(string='Nro. IIBB')
    fecha_inicio_actividades = fields.Date(string="Inicio de actividades")
    es_proveedor_estado = fields.Boolean(string='Proveedor del Estado')
    proveedor_estado = fields.Char(string='Nro. proveedor del Estado')
