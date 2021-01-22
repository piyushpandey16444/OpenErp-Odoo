# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Routing',
    'version': '1.1',
    'category': 'Inventory',
    'summary': 'Process Manager',
    'description': """
This module contains all the common features of Sales Management and eCommerce.
    """,
    'depends': ['product', 'account', 'portal'],
    'data': [
        'views/routing_views.xml',
    ],
    'demo': [
        'data/sale_demo.xml',
        'data/product_product_demo.xml',
    ],
    'uninstall_hook': "uninstall_hook",
    'installable': True,
    'auto_install': False,
}
