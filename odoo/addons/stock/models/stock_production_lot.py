# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ProductionLot(models.Model):
    _name = 'stock.production.lot'
    _inherit = ['mail.thread']
    _description = 'Lot/Serial'

    # Gaurav 2/5/20 added commented name serial for default seq generation
    # name = fields.Char(
    #     'Lot/Serial Number', default=lambda self: self.env['ir.sequence'].next_by_code('stock.lot.serial'),
    #     required=True, help="Unique Lot/Serial Number")
    name = fields.Char(
        'Lot/Serial Number',
        required=True, help="Unique Lot/Serial Number")
    # Gaurav end
    ref = fields.Char('Internal Reference', help="Internal reference number in case it differs from the manufacturer's lot/serial number")
    # Gaurav 5/5/20 added and commented to add domain for product to only show unique and by lot tracking
    # product_id = fields.Many2one(
    #     'product.product', 'Product',
    #     domain=[('type', 'in', ['product', 'consu'])], required=True)
    product_id = fields.Many2one(
        'product.product', 'Product',
        domain=[('type', 'in', ['product', 'consu']),('tracking', 'in', ['serial', 'lot'])], required=True)
    # Gaurav end
    product_uom_id = fields.Many2one(
        'product.uom', 'Unit of Measure',
        related='product_id.uom_id', store=True)
    quant_ids = fields.One2many('stock.quant', 'lot_id', 'Quants', readonly=True)
    create_date = fields.Datetime('Creation Date')
    product_qty = fields.Float('Quantity', compute='_product_qty')

    _sql_constraints = [
        ('name_ref_uniq', 'unique (name, product_id)', 'The combination of serial number and product must be unique !'),
    ]

    @api.model
    def create(self, vals):
        res = super(ProductionLot, self).create(vals)

        # self.env['mrp.workorder'].search([('final_lot_id', '=', False)]).write({'final_lot_id': res.id})

        active_picking_id = self.env.context.get('active_picking_id', False)
        if active_picking_id:
            picking_id = self.env['stock.picking'].browse(active_picking_id)
            if picking_id and not picking_id.picking_type_id.use_create_lots:
                raise UserError(_("You are not allowed to create a lot for this picking type"))
        return res

    @api.multi
    def write(self, vals):
        if 'product_id' in vals:
            move_lines = self.env['stock.move.line'].search([('lot_id', 'in', self.ids), ('product_id', '!=', vals['product_id'])])
            if move_lines:
                raise UserError(_(
                    'You are not allowed to change the product linked to a serial or lot number ' +
                    'if some stock moves have already been created with that number. ' +
                    'This would lead to inconsistencies in your stock.'
                ))
        return super(ProductionLot, self).write(vals)

    @api.one
    def _product_qty(self):
        # We only care for the quants in internal or transit locations.
        quants = self.quant_ids.filtered(lambda q: q.location_id.usage in ['internal', 'transit'])
        self.product_qty = sum(quants.mapped('quantity'))



    # onchange product id
    #     Gaurav 2/5/20 added onchange product to get manual saved sequence
    @api.onchange('product_id')
    def _onchange_product_id(self):
        self.name = ''
        print("nameeeeexx", self.product_id.product_tmpl_id.name, self.product_id.product_tmpl_id.id)
        prod_seq = str(self.product_id.product_tmpl_id.name)+'/'+str(self.product_id.product_tmpl_id.id)
        if self.product_id:
            prod_search = self.env['product.template'].search([('company_id','=', self.env.user.company_id.id),
                                                               ('id', '=', self.product_id.product_tmpl_id.id)])
            lsd_search_exist = self.env['lot.sequencedata'].search(
                [('company_id', '=', self.env.user.company_id.id), ('product_template_id', '=', self.product_id.product_tmpl_id.id)])
            if prod_search.lot_seq_gen_mode == 'manual' and lsd_search_exist.active == True:
                seq_search = self.env['ir.sequence'].search([('code','=',prod_seq),('company_id','=',self.env.user.company_id.id)])
                if seq_search:
                    self.name = self.env['ir.sequence'].next_by_code(prod_seq)
                else:
                    raise ValidationError("This product belongs to Manual Lot sequence generation category,"
                                          " Please generate the Lot sequence \nof the product first! ")
            else:
                self.name = self.env['ir.sequence'].next_by_code('stock.lot.serial')
    #             Gaurav end



