# -*- coding: utf-8 -*-

{
    "name": "Sale Extension Latest",
    "version": "1.0",
    "depends": ['sales_team', 'account', 'portal', 'sale_stock'],
    "category": "Sales",
    "description": """
Sale Extension. This module adds:
  * Inventory adjustment (without Manufacturing).
""",
    "init_xml": [

    ],
    "demo_xml": [],
    "data": [
     'views/sale_ext_inv_adj_view.xml',
     'views/sale_requisition_view.xml',
     'data/ir_sequence_data.xml',
     'views/sale_requisition_view.xml',
     'report/quotation_report.xml',
     'report/sale_quotation_template.xml',
     'data/mail_template_date.xml',
     'report/sale_quotation_report.xml',
    ],
    'qweb': [

    ],
    # "active": False,
    "installable": True
}
