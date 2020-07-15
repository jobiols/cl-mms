# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class AccountFiscalPosition(models.Model):
    _inherit = 'account.fiscal.position'

    no_discrimina_impuestos = fields.Boolean(string='No discrimina impuestos')


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    def digito_verificador_modulo10(self, codigo):
        "Rutina para el cálculo del dígito verificador 'módulo 10'"
        # Ver RG 1702 AFIP
        # Etapa 1: comenzar desde la izquierda, sumar todos los caracteres ubicados en las posiciones impares.
        etapa1 = sum([int(c) for i, c in enumerate(codigo) if not i % 2])
        # Etapa 2: multiplicar la suma obtenida en la etapa 1 por el número 3
        etapa2 = etapa1 * 3
        # Etapa 3: comenzar desde la izquierda, sumar todos los caracteres que están ubicados en las posiciones pares.
        etapa3 = sum([int(c) for i, c in enumerate(codigo) if i % 2])
        # Etapa 4: sumar los resultados obtenidos en las etapas 2 y 3.
        etapa4 = etapa2 + etapa3
        # Etapa 5: buscar el menor número que sumado al resultado obtenido en la etapa 4 dé un número múltiplo de 10.
        # Este será el valor del dígito verificador del módulo 10.
        digito = 10 - (etapa4 - (int(etapa4 / 10) * 10))
        if digito == 10:
            digito = 0
        return str(digito)

    def get_barcode(self):
        try:
            barcode = self.company_id.partner_id.vat.replace('-', '')
            barcode += self.document_type_id.code.zfill(3)
            barcode += self.punto_venta_afip.name.zfill(4)
            barcode += str(self.afip_auth_code_due).replace('-', '')
            barcode += self.digito_verificador_modulo10(barcode)
            return barcode
        except:
            return 0
