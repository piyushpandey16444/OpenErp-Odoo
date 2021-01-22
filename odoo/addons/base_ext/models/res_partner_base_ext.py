# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.



from odoo import api, fields, models, tools, SUPERUSER_ID, _
from odoo.exceptions import UserError, ValidationError


class Partner(models.Model):
    _description = 'Contact'
    _inherit = "res.partner"

    # Gaurav 30/4/20 adds saledetail_id for product.saledetail and purchasedetail
    # saledetail_partner_ids = fields.One2many('product.saledetail', 'name', 'Sale product detail')
    saledetail_customer_ids = fields.One2many('product.saledetail', 'customer_partner_id', 'Product detail')
    # purchasedetail_partner_ids = fields.One2many('product.purchasedetail', 'name', 'Purchase product detail')
    purchasedetail_vendor_ids = fields.One2many('product.purchasedetail', 'vendor_partner_id', 'Product detail')
    # Gaurav end