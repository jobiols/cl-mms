# -*- coding: utf-8 -*-
{
    'name': "Factura Electrónica",

    'summary': """
        Factura Electrónica
    """,

    'description': """
        Factura Electrónica
    """,

    'author': "Mario Murua",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/12.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Invoice',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['sale', 'stock'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'security/ir.model.access.csv',
        'views/account.xml',
        'views/res_partner.xml',
        'views/res_company.xml',
        'views/sale.xml',
        'report/document_template.xml',
        #'report/factura_electronica_layout.xml',
        'report/report_deliveryslip.xml',
        'report/report_invoice.xml',
        'report/sale_report_templates.xml',
        'report/sale_portal_templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [],
}