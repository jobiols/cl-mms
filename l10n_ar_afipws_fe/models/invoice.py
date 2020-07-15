##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from .pyi25 import PyI25
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.tools import config
import base64
from io import BytesIO
import logging
import sys
import traceback
from datetime import datetime

validation_type = 'homologation'
_logger = logging.getLogger(__name__)

logging.getLogger('suds.client').setLevel(logging.DEBUG)
logging.getLogger('suds.transport').setLevel(logging.DEBUG)
logging.getLogger('suds.xsd.schema').setLevel(logging.DEBUG)
logging.getLogger('suds.wsdl').setLevel(logging.DEBUG)

try:
    from pysimplesoap.client import SoapFault
except ImportError:
    _logger.debug('Can not `from pyafipws.soap import SoapFault`.')

odoo_fiscal_position_RI = 'Responsable Inscripto'
odoo_fiscal_position_M = 'Responsable Monotributo'
odoo_fiscal_position_Ex = 'Exento'
odoo_fiscal_position_CF = 'Consumidor Final'


class Currency(models.Model):
    _inherit = 'res.currency'
    afip_code = fields.Char(
        'AFIP Code',
        size=4,
    )


class AccountTaxGroup(models.Model):
    _inherit = 'account.tax.group'

    afip_code = fields.Selection([
        ('0', 'No corresponde'),
        ('1', 'No gravado'),
        ('2', 'Exento'),
        ('3', '0%'),
        ('4', '10.50%'),
        ('5', '21%'),
        ('6', '27%'),
    ])

    type = fields.Selection([
        ('tax', 'TAX'),
        ('perception', 'Perception'),
        ('withholding', 'Withholding'),
        ('other', 'Other'),
        # ('view', 'View'),
    ],
        index=True,
    )
    tax = fields.Selection([
        ('iva', 'IVA'),
        ('profits', 'Profits'),
        ('gross_income', 'Gross Income'),
        ('other', 'Other')],
        index=True,
    )
    application = fields.Selection([
        ('national_taxes', 'National Taxes'),
        ('provincial_taxes', 'Provincial Taxes'),
        ('municipal_taxes', 'Municipal Taxes'),
        ('internal_taxes', 'Internal Taxes'),
        ('others', 'Others')],
        help='Other Taxes According AFIP',
        index=True,
    )
    application_code = fields.Char(
        'Application Code',
        compute='_compute_application_code',
    )

    @api.multi
    @api.depends('application')
    def _compute_application_code(self):
        for rec in self:
            if rec.application == 'national_taxes':
                application_code = '01'
            elif rec.application == 'provincial_taxes':
                application_code = '02'
            elif rec.application == 'municipal_taxes':
                application_code = '03'
            elif rec.application == 'internal_taxes':
                application_code = '04'
            else:
                application_code = '99'
            rec.application_code = application_code


class AccountDocumentLetter(models.Model):
    _name = 'account.document.letter'
    _description = 'Account Document Letter'

    name = fields.Char(
        'Name',
        required=True
    )

    document_type_ids = fields.One2many(
        'account.document.type',
        'document_letter_id',
        'Document Types',
        auto_join=True,
    )


class AccountDocumentType(models.Model):
    _name = 'account.document.type'

    sequence = fields.Char()

    code = fields.Char()

    name = fields.Char()

    report_name = fields.Char()

    internal_type = fields.Char()

    doc_code_prefix = fields.Char()

    document_letter_id = fields.Many2one(
        'account.document.letter',
        'Document Letter',
        auto_join=True,
        index=True,
    )


class AccountFiscalPosition(models.Model):
    _inherit = 'account.fiscal.position'

    afip_code = fields.Char(
        'AFIP Code',
        help='For eg. This code will be used on electronic invoice and citi '
             'reports',
    )


class PuntoVentaAFIP(models.Model):
    _name = 'l10n_ar_afipws_fe.punto_venta_afip'

    name = fields.Char(required=1)
    emision_tipo = fields.Selection([('cae', 'CAE'), ('caea', 'CAEA')], default='cae', required=1)
    bloqueado = fields.Selection([
        ('S', 'Si'),
        ('N', 'No'),
    ], default='N', required=1)
    fecha_baja = fields.Date()

    # TODO crear vista?


class PuntoVentaTipoComprobante(models.TransientModel):
    _name = 'l10n_ar_afipws_fe.pv_tp'
    _description = 'Punto de Venta | Tipo de Comprobante'

    punto_venta_afip = fields.Many2one('l10n_ar_afipws_fe.punto_venta_afip')

    document_type_id = fields.Many2one('account.document.type')

    invoice_number = fields.Integer('AFIP nro de comprobante')

    @api.multi
    def get_pyafipws_last_invoice(self):
        self.ensure_one()
        document_type = self.document_type_id
        company = self.env.user.company_id
        afip_ws = 'wsfe'  # TODO como lo obtengo ?

        ws = company.get_connection(afip_ws).connect()
        # call the webservice method to get the last invoice at AFIP:
        if afip_ws in ("wsfe", "wsmtxca"):
            _logger.info("CompUltimoAutorizado: document type " + str(document_type.code))
            _logger.info("CompUltimoAutorizado: punto de venta " + self.punto_venta_afip.name)
            last = ws.CompUltimoAutorizado(document_type.code, self.punto_venta_afip.name)
        # elif afip_ws in ["wsfex", 'wsbfe']:
        #     last = ws.GetLastCMP(
        #         document_type, self.journal_id.point_of_sale_number)
        else:
            return (_('AFIP WS %s not implemented') % afip_ws)
        msg = " - ".join([ws.Excepcion, ws.ErrMsg, ws.Obs])

        next_ws = int(last or 0) + 1
        last_local_invoice_approved = self.env['account.invoice'].search([
            ('punto_venta_afip', '=', self.punto_venta_afip.id),
            ('document_type_id', '=', self.document_type_id.id),
            ('afip_auth_verify_result', '=', 'A'),
        ], order='id desc')

        next_local = int(last_local_invoice_approved[0].invoice_number) + 1 if last_local_invoice_approved else 1
        if next_ws != next_local:
            msg = _(
                'ERROR! Local (%i) and remote (%i) next number '
                'mismatch!\n') % (next_local, next_ws) + msg
        else:
            msg = _('OK! Local and remote next number match!') + msg
        title = _('Last Invoice %s\n' % last)
        return {
            'msg': (title + msg),
            'result': last
        }


class AccountInvoice(models.Model):
    _inherit = "account.invoice"

    # afip_auth_verify_type = fields.Selection(
    #     related='company_id.afip_auth_verify_type',
    #     readonly=True,
    # )

    """
    RI  RI  |   A
        Ex  |   B
        M   |   B
    M   RI  |   C
        Ex  |   C
        M   |   C
    """

    invoice_number = fields.Integer('AFIP nro de comprobante')

    afip_tipo_documento_receptor = fields.Selection(related='commercial_partner_id.afip_tipo_documento',
                                                    string="Tipo Documento del Receptor", readonly=1)

    afip_service_start = fields.Date(
        string='Service Start Date',
        readonly=True,
        states={
            'draft': [('readonly', False)]
        },
    )
    afip_service_end = fields.Date(
        string='Service End Date',
        readonly=True,
        states={
            'draft': [('readonly', False)]
        },
    )

    afip_concept = fields.Selection([
        ('1', 'Producto / Exportación definitiva de bienes'),
        ('2', 'Servicios'),
        ('3', 'Productos y Servicios'),
        ('4', '4-Otros (exportación)'),
    ], default='1')

    punto_venta_afip = fields.Many2one('l10n_ar_afipws_fe.punto_venta_afip')

    document_type_id = fields.Many2one('account.document.type')

    document_type_internal_type = fields.Char(related='document_type_id.internal_type')

    document_type_id_code = fields.Char(related='document_type_id.code', string="Tipo Comprobante AFIP")

    afip_batch_number = fields.Integer(
        copy=False,
        string='Batch Number',
        readonly=True
    )
    afip_auth_verify_result = fields.Selection([
        ('A', 'Aprobado'), ('O', 'Observado'), ('R', 'Rechazado')],
        string='AFIP authorization verification result',
        copy=False,
        readonly=True,
    )
    afip_auth_verify_observation = fields.Char(
        string='AFIP authorization verification observation',
        copy=False,
        readonly=True,
    )
    afip_auth_mode = fields.Selection([
        ('CAE', 'CAE'), ('CAI', 'CAI'), ('CAEA', 'CAEA')],
        string='AFIP authorization mode',
        copy=False,
        readonly=True,
        states={
            'draft': [('readonly', False)]
        },
    )
    afip_auth_code = fields.Char(
        copy=False,
        string='CAE/CAI/CAEA Code',
        readonly=True,
        oldname='afip_cae',
        size=24,
        states={
            'draft': [('readonly', False)]
        },
    )
    afip_auth_code_due = fields.Date(
        copy=False,
        readonly=True,
        oldname='afip_cae_due',
        string='CAE/CAI/CAEA due Date',
        states={
            'draft': [('readonly', False)]
        },
    )
    # for compatibility
    afip_cae = fields.Char(
        related='afip_auth_code'
    )
    afip_cae_due = fields.Date(
        related='afip_auth_code_due'
    )

    afip_message = fields.Text(
        string='AFIP Message',
        copy=False,
    )
    afip_xml_request = fields.Text(
        string='AFIP XML Request',
        copy=False,
    )
    afip_xml_response = fields.Text(
        string='AFIP XML Response',
        copy=False,
    )
    afip_result = fields.Selection([
        ('', 'n/a'),
        ('A', 'Aceptado'),
        ('R', 'Rechazado'),
        ('O', 'Observado')],
        'Resultado',
        readonly=True,
        states={
            'draft': [('readonly', False)]
        },
        copy=False,
        help="AFIP request result"
    )

    # impuestos e importes de impuestos
    # todos los impuestos tipo iva (es un concepto mas bien interno)
    iva_impuestos_ids = fields.One2many(
        compute="compute_argentina_amounts",
        comodel_name='account.invoice.tax',
        string='IVA impuestos'
    )
    # todos los impuestos iva que componen base imponible (no se incluyen 0,
    # 1, 2 que no son impuesto en si)
    iva_imponible_ids = fields.One2many(
        compute="compute_argentina_amounts",
        comodel_name='account.invoice.tax',
        string='Impuestos IVA'
    )
    # todos los impuestos menos los tipo iva iva_impuestos_ids
    not_iva_tax_ids = fields.One2many(
        compute="compute_argentina_amounts",
        comodel_name='account.invoice.tax',
        string='Impuestos NO IVA'
    )
    # suma de base para todos los impuestos tipo iva
    iva_base_imponible = fields.Monetary(
        compute="compute_argentina_amounts",
        string='Base Imponible IVA'
    )
    # base imponible (no se incluyen no corresponde, exento y no gravado)
    impNeto = fields.Monetary(
        compute="compute_argentina_amounts",
        string='Importe Neto Gravado',
        help="""
        Importe neto gravado. Debe ser menor o igual a Importe total y no puede ser menor a cero. 
        Para comprobantes tipo C este campo corresponde al Importe del Sub Total. 
        Para comprobantes tipo Bienes Usados – Emisor Monotributista no debe informarse o debe ser igual a cero (0).
        """
    )
    # base iva exento
    impOpEx = fields.Monetary(
        compute="compute_argentina_amounts",
        string='Importe Exento',
        help="""
        Importe exento. Debe ser menor o igual a Importe total y no puede ser menor a cero.
        Para comprobantes tipo C debe ser igual a cero (0).
        Para comprobantes tipo Bienes Usados – Emisor Monotributista no debe informarse o debe ser igual a cero (0).
        """
    )
    # base iva no gravado
    impTotConc = fields.Monetary(
        compute="compute_argentina_amounts",
        string='Base no imponible',
        help="""
        Importe neto no gravado. Debe ser menor o igual a Importe total y no puede ser menor a cero.
        No puede ser mayor al Importe total de la operación ni menor a cero (0).
        Para comprobantes tipo C debe ser igual a cero (0).
        Para comprobantes tipo Bienes Usados – Emisor Monotributista este campo corresponde al importe subtotal.
        """

    )
    # importe de iva
    impIVA = fields.Monetary(
        compute="compute_argentina_amounts",
        string='Suma de impuestos IVA',
        help="""
        Para comprobantes tipo C debe ser igual a cero (0).
        Para comprobantes tipo Bienes Usados – Emisor Monotributista no debe informarse o debe ser igual a cero (0).
        """
    )
    # importe de otros impuestos
    impTrib = fields.Monetary(
        compute="compute_argentina_amounts",
        string='Otros impuestos',
    )

    currency_afip_code = fields.Char(related='currency_id.afip_code', readonly=1, string="Moneda AFIP")
    moneda_ctz = fields.Float(readonly=1, string="Cotizacion Moneda AFIP")

    @api.multi
    def compute_argentina_amounts(self):
        for rec in self:
            iva_impuestos = rec.tax_line_ids.filtered(
                lambda r: (
                        r.tax_id.tax_group_id.type == 'tax' and
                        r.tax_id.tax_group_id.tax == 'iva'))
            iva_imponibles = iva_impuestos.filtered(
                lambda r: (r.tax_id.tax_group_id.afip_code not in [0, 1, 2]) and r.base)

            impIVA = sum(iva_impuestos.mapped('amount'))
            rec.iva_impuestos_ids = iva_impuestos
            rec.iva_imponible_ids = iva_imponibles
            rec.impIVA = impIVA
            # rec.iva_base_imponible = sum(iva_imponibles.mapped('base_amount'))
            rec.iva_base_imponible = sum(iva_imponibles.mapped('base'))
            # rec.iva_base_imponible = sum(vat_taxes.mapped('base_amount'))
            rec.iva_base_imponible = sum(iva_impuestos.mapped('base'))

            # vat exempt values
            # exempt taxes are the ones with code 2
            iva_impuestos_exentos = rec.tax_line_ids.filtered(
                lambda r: (
                        r.tax_id.tax_group_id.type == 'tax' and
                        r.tax_id.tax_group_id.tax == 'iva' and
                        r.tax_id.tax_group_id.afip_code == '2'))
            rec.impOpEx = sum(iva_impuestos_exentos.mapped('amount'))

            # vat_untaxed_base_amount values (no gravado)
            # vat exempt taxes are the ones with code 1
            iva_impuestos_nogravados = rec.tax_line_ids.filtered(
                lambda r: (
                        r.tax_id.tax_group_id.type == 'tax' and
                        r.tax_id.tax_group_id.tax == 'iva' and
                        r.tax_id.tax_group_id.afip_code == '1'))
            rec.impTotConc = sum(iva_impuestos_nogravados.mapped('base'))
            # other taxes values
            otros_impuestos = rec.tax_line_ids - iva_impuestos
            otros_impuestos_monto = sum(otros_impuestos.mapped('amount'))
            rec.not_iva_tax_ids = otros_impuestos
            rec.impTrib = otros_impuestos_monto
            #todos_productos = all([line.product_id.type == 'product' for line in rec.invoice_line_ids])
            #todos_servicios = all([line.product_id.type == 'service' for line in rec.invoice_line_ids])
            # rec.afip_concept = '1' if todos_productos else '2' if todos_servicios else '3'
            rec.afip_concept = '3'

            moneda_id = rec.currency_id.afip_code
            moneda_ctz = 1
            if moneda_id == 'PES':
                moneda_ctz = 1
            elif moneda_id == 'DOL':
                moneda_ctz = self.env.ref('base.ARS').rate  # ALERT moneda ARV (lista de precios de Ventas)
            elif moneda_id == 'EUR':
                moneda_ctz = self.env.ref('base.ARS').rate / self.env.ref('base.EUR').rate
            rec.moneda_ctz = moneda_ctz

    @api.onchange('date_invoice')
    def onchange_date_invoice(self):
        self.afip_service_start = self.date_invoice
        self.afip_service_end = self.date_invoice

    def action_invoice_cancel(self):  # ALERT inestable
        if self.afip_result in ['A', 'O']:
            raise Warning("No puede anular una factura  validada por AFIP")
        else:
            super(AccountInvoice, self).action_invoice_cancel()

    @api.multi
    def get_related_invoices_data(self):
        """
        List related invoice information to fill CbtesAsoc.
        """
        self.ensure_one()
        # for now we only get related document for debit and credit notes
        # because, for eg, an invoice can not be related to an invoice and
        # that happens if you choose the modify option of the credit note
        # wizard. A mapping of which documents can be reported as related
        # documents would be a better solution
        if self.document_type_internal_type in ['debit_note', 'credit_note'] \
                and self.origin:
            return self.search([
                ('commercial_partner_id', '=', self.commercial_partner_id.id),
                ('company_id', '=', self.company_id.id),
                ('number', '=', self.origin),
                ('state', 'not in',
                 ['draft', 'proforma', 'proforma2', 'cancel'])],
                limit=1)
        else:
            return self.browse()

    @api.multi
    def invoice_validate(self):
        """
        The last thing we do is request the cae because if an error occurs
        after cae requested, the invoice has been already validated on afip
        """
        res = super(AccountInvoice, self).invoice_validate()
        for inv in self.check_afip_auth_verify_required():
            #if config.get('server_mode', 0) == 'production':
            #    inv.commercial_partner_id.consultar_estado_en_padron()
            inv.do_pyafipws_request_cae()
        return res

    @api.multi
    @api.constrains('partner_id')
    @api.onchange('partner_id')
    def _set_punto_venta(self):
        for inv in self.filtered(lambda x: (x.journal_id.type == 'sale')):
            inv.punto_venta_afip = inv.journal_id.punto_venta_afip
            if self.partner_id:

                """
                RI  RI  |   A
                    Ex  |   B
                    M   |   B
                M   RI  |   C
                    Ex  |   C
                    M   |   C
                """
                letra = False
                inv.fiscal_position_id = self.env.user.company_id.partner_id.property_account_position_id
                partner_fiscal_position = inv.partner_id.property_account_position_id.name
                _logger.info("partner_fiscal_position: %s" % partner_fiscal_position)
                if not partner_fiscal_position:
                    raise UserError(
                        "Atención: el Partner %s no tiene configurada posicion fiscal" % inv.partner_id.name)
                if not inv.fiscal_position_id:
                    raise UserError("Atención: la factura no tiene seleccionada posicion fiscal")
                if inv.fiscal_position_id.name == odoo_fiscal_position_RI:
                    if partner_fiscal_position == odoo_fiscal_position_RI:
                        letra = 'A'
                    if partner_fiscal_position in [odoo_fiscal_position_Ex, odoo_fiscal_position_M]:
                        letra = 'B'
                if inv.fiscal_position_id.name == odoo_fiscal_position_M:
                    if partner_fiscal_position in [odoo_fiscal_position_RI, odoo_fiscal_position_Ex,
                                                   odoo_fiscal_position_M]:
                        letra = 'C'
                if letra == 'A':
                    if self.type == 'out_invoice':
                        # self.tipo_comprobante = '1'
                        self.document_type_id = self.env.ref('l10n_ar_afipws_fe.dc_a_f')
                    elif self.type == 'out_refund':
                        # self.tipo_comprobante = '3'
                        self.document_type_id = self.env.ref('l10n_ar_afipws_fe.dc_a_nc')
                if letra == 'B':
                    if self.type == 'out_invoice':
                        # self.tipo_comprobante = '6'
                        self.document_type_id = self.env.ref('l10n_ar_afipws_fe.dc_b_f')
                    elif self.type == 'out_refund':
                        # self.tipo_comprobante = '8'
                        self.document_type_id = self.env.ref('l10n_ar_afipws_fe.dc_b_nc')
                if letra == 'C':
                    if self.type == 'out_invoice':
                        # self.tipo_comprobante = '11'
                        self.document_type_id = self.env.ref('l10n_ar_afipws_fe.dc_c_f')
                    elif self.type == 'out_refund':
                        # self.tipo_comprobante = '13'
                        self.document_type_id = self.env.ref('l10n_ar_afipws_fe.dc_c_nc')
                _logger.info("Tipo documento: %s" % self.document_type_id.name)

    @api.multi
    def check_afip_auth_verify_required(self):
        inv_to_validate = []
        for inv in self:
            if inv.type in ['out_invoice', 'out_refund'] and inv.document_type_internal_type in ['invoice',
                                                                                                   'debit_note',
                                                                                                   'credit_note',
                                                                                                   'receipt_invoice']:
                inv_to_validate.append(inv)
            # if self.type in ['in_invoice', 'in_refund']:
            #     return False
            # if self.afip_auth_verify_result:
            #     raise UserError("La factura ya ha sido validada")
        return inv_to_validate

    @api.multi
    def verify_on_afip(self):
        """
        cbte_modo = "CAE"                    # modalidad de emision: CAI, CAE,
        CAEA
        cuit_emisor = "20267565393"          # proveedor
        pto_vta = 4002                       # punto de venta habilitado en AFIP
        cbte_tipo = 1                        # 1: factura A (ver tabla de parametros)
        cbte_nro = 109                       # numero de factura
        cbte_fch = "20131227"                # fecha en formato aaaammdd
        imp_total = "121.0"                  # importe total
        cod_autorizacion = "63523178385550"  # numero de CAI, CAE o CAEA
        doc_tipo_receptor = 80               # CUIT (obligatorio Facturas A o M)
        doc_nro_receptor = "30628789661"     # numero de CUIT del cliente

        ok = wscdc.ConstatarComprobante(
            cbte_modo, cuit_emisor, pto_vta, cbte_tipo,
            cbte_nro, cbte_fch, imp_total, cod_autorizacion,
            doc_tipo_receptor, doc_nro_receptor)

        print "Resultado:", wscdc.Resultado
        print "Mensaje de Error:", wscdc.ErrMsg
        print "Observaciones:", wscdc.Obs
        """
        if not self.punto_venta_afip:
            raise UserError("Seleccione el punto de venta AFIP.")
        afip_ws = "wscdc"
        ws = self.company_id.get_connection(afip_ws).connect()
        _logger.info(ws)
        for inv in self:
            cbte_modo = inv.afip_auth_mode
            cod_autorizacion = inv.afip_auth_code
            if not cbte_modo or not cod_autorizacion:
                raise UserError(_(
                    'AFIP authorization mode and Code are required!'))

            # get issuer and receptor depending on supplier or customer invoice
            if inv.type in ['in_invoice', 'in_refund']:
                issuer = inv.commercial_partner_id
                receptor = inv.company_id.partner_id
            else:
                issuer = inv.company_id.partner_id
                receptor = inv.commercial_partner_id

            # cuit_emisor = issuer.cuit_required()
            cuit_emisor = issuer.vat.replace("-", "")

            receptor_doc_code = receptor.afip_tipo_documento
            doc_tipo_receptor = receptor_doc_code or '99'
            doc_nro_receptor = (receptor_doc_code and receptor.cuit or receptor.vat.replace("-","") or '0')
            doc_type = inv.document_type_id
            if (
                    doc_type.document_letter_id.name in ['A', 'M'] and
                    doc_tipo_receptor != '80' or not doc_nro_receptor):
                raise UserError(_(
                    'Para Comprobantes tipo A o tipo M:\n'
                    '*  el documento del receptor debe ser CUIT\n'
                    '*  el documento del Receptor es obligatorio\n'
                ))

            cbte_nro = inv.invoice_number
            pto_vta = inv.punto_venta_afip.name
            cbte_tipo = doc_type.code
            if not pto_vta or not cbte_nro or not cbte_tipo:
                raise UserError(_(
                    'Point of sale and document number and document type '
                    'are required!'))
            cbte_fch = inv.date_invoice
            if not cbte_fch:
                raise UserError(_('Invoice Date is required!'))
            cbte_fch = str(cbte_fch).replace("-", "")
            imp_total = str("%.2f" % inv.amount_total)

            _logger.info('Constatando Comprobante en afip')

            # atrapado de errores en afip
            msg = False
            try:
                _logger.info("cbte_modo %s " % cbte_modo)
                _logger.info("cuit_emisor %s " % cuit_emisor)
                _logger.info("pto_vta %s " % pto_vta)
                _logger.info("cbte_tipo %s " % cbte_tipo)
                _logger.info("cbte_nro %s " % cbte_nro)
                _logger.info("cbte_fch %s " % cbte_fch)
                _logger.info("imp_total %s " % imp_total)
                _logger.info("cod_autorizacion %s " % cod_autorizacion)
                _logger.info("doc_tipo_receptor %s " % doc_tipo_receptor)
                _logger.info("doc_nro_receptor %s " % doc_nro_receptor)
                ws.ConstatarComprobante(
                    cbte_modo, cuit_emisor, pto_vta, cbte_tipo, cbte_nro,
                    cbte_fch, imp_total, cod_autorizacion, doc_tipo_receptor,
                    doc_nro_receptor)
            except SoapFault as fault:
                msg = 'Falla SOAP %s: %s' % (fault.faultcode, fault.faultstring)
            except Exception as e:
                msg = e
            except Exception:
                if ws.Excepcion:
                    # get the exception already parsed by the helper
                    msg = ws.Excepcion
                else:
                    # avoid encoding problem when raising error
                    msg = traceback.format_exception_only(
                        sys.exc_type,
                        sys.exc_value)[0]
            if msg:
                raise UserError(_('AFIP Verification Error. %s' % msg))

            inv.write({
                'afip_auth_verify_result': ws.Resultado,
                'afip_auth_verify_observation': '%s%s' % (ws.Obs, ws.ErrMsg)
            })

    @api.multi
    def do_pyafipws_request_cae(self):
        "Request to AFIP the invoices' Authorization Electronic Code (CAE)"
        for inv in self:
            # Ignore invoices with cae (do not check date)
            if inv.afip_auth_code:
                continue

            if not inv.punto_venta_afip:
                raise UserError("Seleccione el punto de venta AFIP.")

            if not inv.date_invoice:
                raise UserError("Para validar, es necesario que la factura posea fecha.")
            if not inv.punto_venta_afip.emision_tipo == 'cae':
                continue
            # afip_ws = inv.punto_venta_afip.afip_ws
            afip_ws = 'wsfe'
            # Ignore invoice if not ws on point of sale
            if not afip_ws:
                raise UserError(_(
                    'If you use electronic journals (invoice id %s) you need '
                    'configure AFIP WS on the journal') % (inv.id))

            # get the electronic invoice type, point of sale and afip_ws:
            commercial_partner = inv.commercial_partner_id
            country = commercial_partner.country_id
            # journal = inv.journal_id
            # pos_number = journal.point_of_sale_number
            pos_number = inv.punto_venta_afip.name
            doc_afip_code = inv.document_type_id.code

            # authenticate against AFIP:
            ws = inv.company_id.get_connection(afip_ws).connect()

            # if afip_ws == 'wsfex':
            #     if not country:
            #         raise UserError(_(
            #             'For WS "%s" country is required on partner' % (
            #                 afip_ws)))
            #     elif not country.code:
            #         raise UserError(_(
            #             'For WS "%s" country code is mandatory'
            #             'Country: %s' % (
            #                 afip_ws, country.name)))
            #     elif not country.afip_code:
            #         raise UserError(_(
            #             'For WS "%s" country afip code is mandatory'
            #             'Country: %s' % (
            #                 afip_ws, country.name)))

            pv_tp = self.env['l10n_ar_afipws_fe.pv_tp'].create({
                'punto_venta_afip': inv.punto_venta_afip.id,
                'document_type_id': inv.document_type_id.id
            })
            ws_next_invoice_number = int(pv_tp.get_pyafipws_last_invoice()['result']) + 1
            # verify that the invoice is the next one to be registered in AFIP
            # if inv.invoice_number != ws_next_invoice_number:
            #     raise UserError(_(
            #         'Error!'
            #         'Invoice id: %i'
            #         'Next invoice number should be %i and not %i' % (
            #             inv.id,
            #             ws_next_invoice_number,
            #             inv.invoice_number)))
            inv.invoice_number = ws_next_invoice_number

            tipo_doc = self.afip_tipo_documento_receptor
            if not tipo_doc:
                raise UserError("El Cliente no tiene tipo de documento de AFIP")
            if not commercial_partner.vat:
                raise UserError("El Cliente no posee documento. Revise su posicion fiscal")
            nro_doc = tipo_doc and str(commercial_partner.vat).replace('-','')
            if not nro_doc:
                raise UserError("El Partner %s no registra numero de documento (vat) " % commercial_partner.name)
            cbt_desde = cbt_hasta = cbte_nro = inv.invoice_number
            concepto = tipo_expo = int(inv.afip_concept)

            fecha_cbte = str(inv.date_invoice)
            if afip_ws != 'wsmtxca':
                fecha_cbte = fecha_cbte.replace("-", "")

            # due date only for concept "services" and mipyme_fce
            if int(concepto) != 1:
                fecha_venc_pago = inv.date_due or inv.date_invoice
                if not fecha_venc_pago:
                    raise UserError("Ingrese fecha de la factura o vencimiento.")
                _logger.info("Fecha de Vencimiento de pago %s" % str(fecha_venc_pago))
                if afip_ws != 'wsmtxca':
                    fecha_venc_pago = str(fecha_venc_pago).replace("-", "")
            else:
                fecha_venc_pago = None

            # fecha de servicio solo si no es 1
            if int(concepto) != 1:
                fecha_serv_desde = inv.afip_service_start
                fecha_serv_hasta = inv.afip_service_end
                if afip_ws != 'wsmtxca':
                    fecha_serv_desde = str(fecha_serv_desde).replace("-", "")
                    fecha_serv_hasta = str(fecha_serv_hasta).replace("-", "")
            else:
                fecha_serv_desde = fecha_serv_hasta = None

            imp_tot_conc = str("%.2f" % inv.impTotConc)
            if inv.document_type_id.document_letter_id.name == 'C':  # ALERT lo deja aprobar pero luego no constatar
                imp_neto = str("%.2f" % inv.amount_untaxed)
            else:
                imp_neto = str("%.2f" % inv.iva_base_imponible)

            imp_iva = str("%.2f" % inv.impIVA) if inv.document_type_id.document_letter_id.name != 'C' else None
            # se usaba para wsca..
            # imp_subtotal = str("%.2f" % inv.amount_untaxed)
            imp_trib = str("%.2f" % inv.impTrib)
            imp_op_ex = 0.0 if inv.document_type_id.document_letter_id.name == 'C' else str("%.2f" % inv.impOpEx)
            if inv.document_type_id.document_letter_id.name == 'C':
                # FIXME asi dice AFIP que es pero luego no lo constata bien.
                """
                Importe total del comprobante, Debe ser igual a Importe neto no gravado + Importe exento + Importe 
                neto gravado + todos los campos de IVA al XX% + Importe de tributos.
                """
                imp_total = float(imp_neto) + inv.impTrib
            else:
                imp_total = str("%.2f" % inv.amount_total)
            moneda_id = inv.currency_id.afip_code
            moneda_ctz = self.moneda_ctz
            if moneda_id == 'PES':
                moneda_ctz = 1
            elif moneda_id == 'DOL':
                moneda_ctz = '%.2f' % self.env.ref('base.ARS').rate
            elif moneda_id == 'EUR':
                moneda_ctz = '%.2f' % self.env.ref('base.ARS').rate / self.env.ref('base.EUR').rate
            # create the invoice internally in the helper
            if afip_ws == 'wsfe':
                _logger.warning("concepto : %s" % str(concepto))
                _logger.warning("tipo_doc : %s" % str(tipo_doc))
                _logger.warning("nro_doc : %s" % str(nro_doc))
                _logger.warning("doc_afip_code : %s" % str(doc_afip_code))
                _logger.warning("pos_number : %s" % str(pos_number))
                _logger.warning("cbt_desde : %s" % str(cbt_desde))
                _logger.warning("cbt_hasta : %s" % str(cbt_hasta))
                _logger.warning("imp_total : %s" % str(imp_total))
                _logger.warning("imp_tot_conc : %s" % str(imp_tot_conc))
                _logger.warning("imp_neto : %s" % str(imp_neto))
                _logger.warning("imp_iva : %s" % str(imp_iva))
                _logger.warning("imp_trib : %s" % str(imp_trib))
                _logger.warning("imp_op_ex : %s" % str(imp_op_ex))
                _logger.warning("fecha_cbte : %s" % str(fecha_cbte))
                _logger.warning("fecha_venc_pago : %s" % str(fecha_venc_pago))
                _logger.warning("fecha_serv_desde : %s" % str(fecha_serv_desde))
                _logger.warning("fecha_serv_hasta : %s" % str(fecha_serv_hasta))
                _logger.warning("moneda_id : %s" % str(moneda_id))
                _logger.warning("moneda_ctz : %s" % str(moneda_ctz))
                ws.CrearFactura(
                    concepto, tipo_doc, nro_doc, doc_afip_code, pos_number,
                    cbt_desde, cbt_hasta, imp_total, imp_tot_conc, imp_neto,
                    imp_iva,
                    imp_trib, imp_op_ex, fecha_cbte, fecha_venc_pago,
                    fecha_serv_desde, fecha_serv_hasta,
                    moneda_id, moneda_ctz
                )

            if afip_ws not in ['wsfex', 'wsbfe']:
                if inv.document_type_id.document_letter_id.name != 'C':
                    for iva in inv.iva_imponible_ids:
                        _logger.info('Adding iva %s' % iva.tax_id.tax_group_id.name)
                        ws.AgregarIva(
                            iva.tax_id.tax_group_id.afip_code,
                            "%.2f" % iva.base,
                            # "%.2f" % abs(iva.base_amount),
                            "%.2f" % iva.amount,
                        )

                for tax in inv.not_iva_tax_ids:
                    _logger.info('Adding TAX %s' % tax.tax_id.tax_group_id.name)
                    ws.AgregarTributo(
                        tax.tax_id.tax_group_id.application_code,
                        tax.tax_id.tax_group_id.name,
                        "%.2f" % tax.base,
                        # "%.2f" % abs(tax.base_amount),
                        # TO DO pasar la alicuota
                        # como no tenemos la alicuota pasamos cero, en v9
                        # podremos pasar la alicuota
                        0,
                        "%.2f" % tax.amount,
                    )

            CbteAsoc = inv.get_related_invoices_data()  # TODO obtener las notas de credito
            # bono no tiene implementado AgregarCmpAsoc
            if CbteAsoc and afip_ws != 'wsbfe':
                ws.AgregarCmpAsoc(
                    CbteAsoc.document_type_id.code,
                    CbteAsoc.punto_venta_afip.name,
                    CbteAsoc.invoice_number,
                )

            # Request the authorization! (call the AFIP webservice method)
            vto = None
            msg = False
            try:
                if afip_ws == 'wsfe':
                    ws.CAESolicitar()
                    vto = ws.Vencimiento
                # elif afip_ws == 'wsmtxca':
                #     ws.AutorizarComprobante()
                #     vto = ws.Vencimiento
                # elif afip_ws == 'wsfex':
                #     ws.Authorize(inv.id)
                #     vto = ws.FchVencCAE
                # elif afip_ws == 'wsbfe':
                #     ws.Authorize(inv.id)
                #     vto = ws.Vencimiento
            except SoapFault as fault:
                msg = 'Falla SOAP %s: %s' % (fault.faultcode, fault.faultstring)
            except Exception as e:
                msg = e
            except Exception:
                if ws.Excepcion:
                    # get the exception already parsed by the helper
                    msg = ws.Excepcion
                else:
                    # avoid encoding problem when raising error
                    msg = traceback.format_exception_only(
                        sys.exc_type,
                        sys.exc_value)[0]
            if msg:
                raise UserError(_('AFIP Validation Error. %s' % msg))

            msg = u"\n".join([ws.Obs or "", ws.ErrMsg or ""])
            if not ws.CAE or ws.Resultado != 'A':
                raise UserError(_('AFIP Validation Error. %s' % msg))

            _logger.info('CAE solicitado con exito. CAE: %s. Resultado %s' % (
                ws.CAE, ws.Resultado))
            # if afip_ws == 'wsbfe':
            #     vto = datetime.strftime(
            #         datetime.strptime(vto, '%d/%m/%Y'), '%Y%m%d')
            number = ('%s-%s-%s' % (inv.document_type_id.doc_code_prefix, inv.punto_venta_afip.name.zfill(2),
                                    str(inv.invoice_number).zfill(5))).replace(' ', '').replace('-', '')
            inv.write({
                # 'name': name,
                'number': number,  # TODO solo dejar el number
                'afip_auth_mode': 'CAE',
                'afip_auth_code': ws.CAE,
                'afip_auth_code_due': vto,
                'afip_result': ws.Resultado,
                'afip_message': msg,
                'afip_xml_request': ws.XmlRequest,
                'afip_xml_response': ws.XmlResponse,
            })
            inv._cr.commit()
