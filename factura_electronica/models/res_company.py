# -*- coding: utf-8 -*-

from odoo import fields, models


class Company(models.Model):
    _inherit = 'res.company'

    nro_iibb = fields.Char(related='partner_id.nro_iibb', string='Nro. IIBB', readonly=False)
    fecha_inicio_actividades = fields.Date(related='partner_id.fecha_inicio_actividades',
                                           string='Inicio de actividades', readonly=False)
    es_proveedor_estado = fields.Boolean(related='partner_id.es_proveedor_estado',
                                         string='Proveedor del Estado', readonly=False)
    proveedor_estado = fields.Char(related='partner_id.proveedor_estado',
                                   string='Nro. proveedor del Estado', readonly=False)
    firma_presidente = fields.Html('Firma presidente', copy=False, attachment=True)
