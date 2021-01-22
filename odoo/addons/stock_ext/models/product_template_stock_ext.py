# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields
from odoo.exceptions import UserError, ValidationError


# ===Gaurav 29/4/20 added and inherit product uom for adding company id========

# class ProductUoM(models.Model):
#     _inherit = 'product.uom'
#
#
#     company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.user.company_id.id)

# ====Gaurav end ===============================================================


# avinash:05/11/20 Commented and Created new module for sequence generator
#  Gaurav 1/5/20 working on extended file in inherited model
# for lot wise sequence generation..

# class ProductTemplate(models.Model):
#
#     _inherit = 'product.template'
#
#
#     # Gaurav 1/5/20 added mode for lot auto/manual mode
#     lot_seq_gen_mode = fields.Selection([
#         ('auto', 'Automatic'),
#         ('manual', 'Manual'),
#         ], string="Lot Sequence Mode", default='auto',)
#
#     show_seq_mode = fields.Boolean("Show Sequence Mode", default=False)
#     # duplicate_product_id = fields.Many2one('product.product', 'Same Product')
#
#
#     @api.onchange('tracking')
#     def onchange_tracking(self):
#         res = super(ProductTemplate, self).onchange_tracking()
#         if self.tracking == 'serial':
#             self.lot_seq_gen_mode = 'manual'
#         else:
#             self.lot_seq_gen_mode = 'auto'
#         return res
#
#     @api.onchange('purchase_ok', 'sale_ok')
#     def onchange_purchase_ok(self):
#         res = super(ProductTemplate, self).onchange_purchase_ok()
#
#         if self.purchase_ok == True:
#
#             self.lot_seq_gen_mode = 'auto'
#
#         elif self.purchase_ok == False:
#             if self.tracking == 'serial':
#                 self.lot_seq_gen_mode = 'manual'
#
#
#
#         return res
#
#
#     @api.onchange('lot_seq_gen_mode')
#     def onchange_lot_seq_gen_mode(self):
#         if self.lot_seq_gen_mode == 'manual':
#             res = {}
#             res = {'warning': {
#                 'title': ('Information'),
#                 'message': ('Are you sure, you want to manually generate sequence for this product?')
#             }
#             }
#             if res:
#                 return res
#
#     # Gaurav start at 1/5/2020 for creating data in lot sequence table for product
#     @api.model
#     def create(self, vals):
#         res = super(ProductTemplate, self).create(vals)
#
#         if res.lot_seq_gen_mode == 'manual':
#
#             lsd = self.env['lot.sequencedata']
#
#             print("lsddddddddd",lsd, res.id, self.id, res.company_id, res.name)
#
#             lsd.create({
#                 'company_id' : res.company_id.id,
#                 'product_template_id' : res.id,
#                 'product_name' : res.name,
#                 # 'lot_wise_seq_button': False,
#             })
#
#         return res
#         # Gaurav end
#
#     @api.multi
#     def write(self, values):
#         res = super(ProductTemplate, self).write(values)
#         if 'lot_seq_gen_mode' in values:
#
#             if self.lot_seq_gen_mode == 'manual':
#
#             # if 'lot_seq_gen_mode' in values and values.get['lot_seq_gen_mode'] == 'manual':
#                 lsd = self.env['lot.sequencedata']
#                 lsd_search_exist = lsd.search([('company_id' ,'=', self.company_id.id), ('product_template_id' ,'=', self.id)])
#
#                 if not lsd_search_exist:
#                     # if self.lot_seq_gen_mode == 'manual':
#                     lsd.create({
#                         'company_id' : self.company_id.id,
#                         'product_template_id' : self.id,
#                         'product_name' : self.name,
#                         # 'lot_wise_seq_button': False,
#                     })
#
#                 if lsd_search_exist:
#                     lsd_search_exist.update({
#                         'active' : True,
#                     })
#
#             elif self.lot_seq_gen_mode == 'auto' and self.env['lot.sequencedata'].search(
#                 [('company_id', '=', self.company_id.id), ('product_template_id', '=', self.id)]):
#
#                 lsd = self.env['lot.sequencedata']
#                 lsd_search_exist = lsd.search([('company_id', '=', self.company_id.id), ('product_template_id', '=', self.id)])
#
#                 lsd_search_exist.update({
#                     'active' : False,
#                 })
#
#
#         return res
        # Gaurav end
    # end avinash

# avinash:05/11/20 Commented and Created new module for sequence generator

    # Gaurav 1/5/20 added table for collecting sequence info (Manual)

# class LotSequenceData(models.Model):
#     _name = 'lot.sequencedata'
#
#     product_name = fields.Char("Product Name", store=True)
#     company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.user.company_id.id, store=True)
#     # product_id = fields.Many2one('product.product', string='Product',)
#     product_template_id = fields.Many2one('product.template', string='Product',)
#     lot_wise_seq_button = fields.Boolean("For Lot Wise", default=False, store=True)
#     active = fields.Boolean("Active", default=True)
#
#     # Gaurav Generate button
#     def action_lot_wise_seq_button(self):
#
#         product_seq_code = str(self.product_name)+"/"+str(self.product_template_id.id)
#
#         ir_seq_search = self.env['ir.sequence'].search([('product_sequence_id','=',self.id),('company_id','=',self.company_id.id)])
#         print("xxxxxxxxxxxxxx", self.product_name, product_seq_code, ir_seq_search)
#
#         if ir_seq_search:
#
#             view = self.env.ref('stock_ext.stock_ext_sequence_view')
#             return {
#                 'name': ('Generate Sequence'),
#                 'type': 'ir.actions.act_window',
#                 'view_type': 'form',
#                 'view_mode': 'form',
#                 'res_model': 'ir.sequence',
#                 'views': [(view.id, 'form')],
#                 'view_id': view.id,
#                 'target': 'new',
#                 'res_id': ir_seq_search.id,
#
#             }
#
#         else:
#
#             view = self.env.ref('stock_ext.stock_ext_sequence_view')
#             return {
#                 'name': ('Generate Sequence'),
#                 'type': 'ir.actions.act_window',
#                 'view_type': 'form',
#                 'view_mode': 'form',
#                 'res_model': 'ir.sequence',
#                 'views': [(view.id, 'form')],
#                 'view_id': view.id,
#                 'target': 'new',
#                 # 'res_id': self.id,
#                 'context': dict(
#                     self.env.context,
#                     default_name= self.product_name,
#                     default_code= product_seq_code,
#                     default_product_sequence_id= self.id,
#
#                 ),
#             }
#
#     #     Edit button in case of sequence is saved and edit is needed
#     def action_edit_lot_wise_seq_button(self):
#
#         product_seq_code = str(self.product_name) + "/" + str(self.product_template_id.id)
#
#         ir_seq_search = self.env['ir.sequence'].search([('product_sequence_id','=',self.id),('company_id','=',self.company_id.id)])
#         print("xxxxxxxxxxxxxx", self.product_name, product_seq_code, ir_seq_search)
#
#         if ir_seq_search:
#
#             view = self.env.ref('stock_ext.stock_ext_sequence_view')
#             return {
#                 'name': ('Generate Sequence'),
#                 'type': 'ir.actions.act_window',
#                 'view_type': 'form',
#                 'view_mode': 'form',
#                 'res_model': 'ir.sequence',
#                 'views': [(view.id, 'form')],
#                 'view_id': view.id,
#                 'target': 'new',
#                 'res_id': ir_seq_search.id,
#
#             }
#
#         else:
#
#             view = self.env.ref('stock_ext.stock_ext_sequence_view')
#             return {
#                 'name': ('Generate Sequence'),
#                 'type': 'ir.actions.act_window',
#                 'view_type': 'form',
#                 'view_mode': 'form',
#                 'res_model': 'ir.sequence',
#                 'views': [(view.id, 'form')],
#                 'view_id': view.id,
#                 'target': 'new',
#                 # 'res_id': self.id,
#                 'context': dict(
#                     self.env.context,
#                     default_name= self.product_name,
#                     default_code= product_seq_code,
#                     default_product_sequence_id= self.id,
#
#                 ),
#             }

    # end avinash

# avinash:05/11/20 Commented and Created new module for sequence generator
# class IrSequence(models.Model):
#     """ Sequence model.
#
#     The sequence model allows to define and use so-called sequence objects.
#     Such objects are used to generate unique identifiers in a transaction-safe
#     way.
#
#     """
#     _inherit = 'ir.sequence'
#
#     product_sequence_id = fields.Many2one('lot.sequencedata', string='Product Sequence', )
#
#     # Gaurav start at 5/5/2020 for showing edit button on save of sequence
#     @api.model
#     def create(self, vals):
#         res = super(IrSequence, self).create(vals)
#
#         if res.product_sequence_id:
#
#             res.product_sequence_id.update({
#                 'lot_wise_seq_button' : True,
#             })
#
#         return res

# end avinash


# ======================Gaurav 5/6/20 edit for stock.picking=====================

class Picking(models.Model):
    _inherit = "stock.picking"

    @api.multi
    def write(self, vals):
        res = super(Picking, self).write(vals)
        if self.state == 'short_close' and 'state' not in vals:
            raise ValidationError("You can not make changes in Receipt, PO-Receipts has been Short Closed !")

        return res


# ======================Gaurav 5/6/20 end=====================






