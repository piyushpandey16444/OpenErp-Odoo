# -*- coding: utf-8 -*-

{
    "name": "Product Extension",
    "version": "1.0",
    "depends": ['product', 'account', ],
    "category": "Product",
    "description": """
Product Extension. This module adds:
  * Tax Master
  * Customer and Vendor Tax - Invoicing
  * HSN code.
""",
    "init_xml": [

    ],
    "demo_xml": [],
    "data": [
     'views/tax_master_views.xml',
     'views/product_ext_views.xml',

    ],
    'qweb': [

    ],
    # "active": False,
    "installable": True
}
