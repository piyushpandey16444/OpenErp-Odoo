# -*- coding: utf-8 -*-

{
    "name" : "Tally odoo integration extension",
    "version" : "1.0",
    "depends" : ['base', 'purchase','sale','stock','account','purchase_extension','product_ext','product'],
    "category" : "account",
    "description": """
Tally odoo integration  User.
""",
    "init_xml": [],
    "demo_xml": [],
    "data": [
            "security/ir.model.access.csv",
            # "security/security_views.xml",
            "views/tally_odoo_ext_view.xml",
            ],
'qweb': [
    ],
    "active": False,
    "installable": True
}
