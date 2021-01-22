#     "SHREE GANESHAY NAMAH"
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd. (<http://www.devintellecs.com>).
#
##############################################################################


{
    'name': 'Tally Integration',
    'icon': "/tally_integration/static/src/img/icon1.png",
    'version': '1.0',
    'sequence':1,
    'category': 'Generic Modules/Accounting',
    'description': """
    
    This module will load the Chart Of account from Tally.\n
    A Module support the following integration capabilities:
    
    ********** Accounting Information ***********\n
    1. Vouchers Information\n
    2. Ledgers Information\n
    3. Groups Information\n
    
    ********** Inventory Information ***********\n
    4. All Inventory Masters Information\n
    5. Stock Items Information\n
    6. Stock Groups Information\n
    7. Unit Of Measure Information\n
    8. Godowns Information\n
    
    ********** Employee Information ***********\n
    9. Employee Information\n
    
        """,
    'author': 'AJAY KHANNA',
    'summary': 'Integrate Tally With Odoo.',
     'images': ['images/main_screenshot.jpg'],
    'depends': ["base","account_voucher",'hr','stock','sale','account','tally_odoo_extension','tally_validations'],
    'data': [
        'data/tally_data.xml',
        'wizard/tally_connection_view.xml',
        'wizard/test_view.xml',
        'views/sync_log.xml',
        
    ],
    'demo': [],
    'test': [],
    'css': [],
    'qweb': [],
    'js': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

