# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Purchase Management Extension',
    'version': '1.2',
    'category': 'Purchases',
    'sequence': 61,
    'summary': 'Purchase Orders, Request for Quotation',
    'description': "",
    'depends': ['stock_account', 'purchase','product'],
    'data': [
        'views/rfq_views.xml',
        'report/purchase_reports.xml',
        'report/rfq_report_template_view.xml',
        'report/purchase_rfq_template.xml',
        'data/ir_sequence_data.xml',
        'data/mail_template_data.xml',
        'views/purchase_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
