from odoo import api, fields, models, tools, SUPERUSER_ID, registry,_
# from odoo import api, fields, models, registry, _
from odoo.http import Controller, request
import time, datetime
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import ValidationError, RedirectWarning, except_orm
from odoo.addons import decimal_precision as dp
# from odoo.tools.float_utils import float_is_zero, float_compare
from odoo.tools import pycompat
# from odoo.tools.float_utils import float_round
from datetime import timedelta
import datetime
# from datetime import datetime
import dateutil.relativedelta
from datetime import datetime as dt
from lxml import etree
import math
from dateutil import parser
from dateutil.relativedelta import relativedelta
from odoo.tools.float_utils import float_round, float_compare, float_is_zero
from odoo.tools import float_utils
from num2words import num2words
from collections import OrderedDict
from psycopg2 import OperationalError

class ProductChangeQuantity(models.TransientModel):
    _inherit = 'stock.change.product.qty'

    SELECT_LOT_ID = [
        ('yes', 'Yes'),
        ('no', 'No'),
    ]
    lot_details = fields.Selection(SELECT_LOT_ID, 'Lot Details')
    lot_id_one = fields.Many2one('stock.production.lot', 'Lot/Serial Number', domain="[('product_id','=',product_id)]")
    tracking = fields.Selection([
        ('serial', 'By Unique Serial Number'),
        ('lot', 'By Lots'),
        ('none', 'No Tracking')], string="Tracking")
    # bin_line_ids = fields.One2many('wiz.bin.data.wiz.line', 'stock_change_id', string='Bin Data')
    # bin_detail = fields.Boolean('Bin Details',default=False)
    stock_prod_lot_lines = fields.One2many('stock.change.lot.line', 'prod_change_id', string='Lot/Serial Lines')
    stock_movement = fields.Boolean('Stock Movement')
    stock_movement_to_product_id = fields.Many2one('product.product', 'To Product')


#Himanshu product 20-09-2020 this default function will get executed once the update_qty_onhand button will be clicked and all the default values will be added to the fields
    @api.model
    def default_get(self,fields):
        # done=self.env['stock.change.lot.line'].search([('product_id','=',self.product)])
        res = super(ProductChangeQuantity, self).default_get(fields)
        if self.env.context.get('active_id'):
            if self._context.get('active_model') == 'product.template':
                #print ("self.env.context.get('active_id')",self.env.context.get('active_id'))
                tmpl_id = self.env['product.template'].browse(self.env.context.get('active_id'))
                #print ("tmpl idddddddddd",tmpl_id,res)
                product_id = res.get('product_id')
                product_ids = self.env['product.product'].browse(product_id)
                res['tracking'] = tmpl_id.tracking
            elif self._context.get('active_model') == 'product.product':
                #print ("self.env.context.get('active_id')", self.env.context.get('active_id'))
                product_id = self.env['product.product'].browse(self.env.context.get('active_id'))
                tmpl_id = product_id.product_tmpl_id
                product_ids = product_id
                res['tracking'] = tmpl_id.tracking
        return res
#end Himanshu

# Himanshu product 20-08-2020 Tree view added for adding the lot when update_qty_onhand is click and tracebility is lot/serial type    -->

class StockChangeLotline(models.TransientModel):
    _name = "stock.change.lot.line"
    stock_production_id = fields.Many2one('stock.production.lot','Lot/Serial')
    product_qty = fields.Float('Qty')
    move_qty = fields.Float('Move Qty')
    prod_change_id = fields.Many2one('stock.change.product.qty','Prod Change Wizard')
    stock_movement_wizard_id = fields.Many2one('stock.movement.wizard', 'Stock Movement Wizard')
    product_id = fields.Many2one('product.product','Product')
    created = fields.Boolean('Created',default=False)
    move_line_id = fields.Many2one('stock.move.line','Move Line id')
    location_id = fields.Many2one('stock.location','Location')
    location_dest_id = fields.Many2one('stock.location', 'Dest Location')
# End himanshu








