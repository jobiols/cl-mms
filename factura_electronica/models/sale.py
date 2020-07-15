# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class TiempoEntrega(models.Model):
    _name = "sale.tiempo_entrega"

    name = fields.Char('Nombre', required=True)


class OrdenVenta(models.Model):
    _inherit = "sale.order"

    expediente_estado = fields.Char('Expediente Estado')
    tiempo_entrega = fields.Many2one('sale.tiempo_entrega', string='Tiempo de Entrega')
