# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Currency BCRA Updater',
    'version': '12.0',
    'category': 'Currency',
    'sequence': 10,
    'author': 'Alesis Manzano',
    'summary': 'Cotizador del Dolar BCRA (Válido solo para Argentina)',
    'description': "",
    'website': '',
    'depends': [
    ],
    'data': [
        'views/assets.xml',
        'data/crons.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'qweb': [
        'static/src/xml/dolar.xml',
    ],
}
