# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name' : 'Account Extension',
    'version' : '1.1',
    'summary': 'Send Invoices and Track Payments',
    'sequence': 30,
    'description': """
Core mechanisms for the accounting modules. To display the menuitems, install the module account_invoicing.
    """,
    'category': 'Accounting',
    'website': 'https://www.odoo.com/page/billing',
    'images' : [],
    'depends' : ['account'],
    'data': [

    ],
    'demo': [
    ],
    'qweb': [

    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
