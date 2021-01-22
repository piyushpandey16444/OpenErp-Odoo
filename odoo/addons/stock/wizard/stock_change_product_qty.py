# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields, tools, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, ValidationError



class ProductChangeQuantity(models.TransientModel):
    _name = "stock.change.product.qty"
    _description = "Change Product Quantity"

    # TDE FIXME: strange dfeault method, was present before migration ? to check
    product_id = fields.Many2one('product.product', 'Product', required=True)
    product_tmpl_id = fields.Many2one('product.template', 'Template', required=True)
    product_variant_count = fields.Integer('Variant Count', related='product_tmpl_id.product_variant_count')
    new_quantity = fields.Float(
        'New Quantity on Hand', default=1,
        digits=dp.get_precision('Product Unit of Measure'), required=True,
        help='This quantity is expressed in the Default Unit of Measure of the product.')
    lot_id = fields.Many2one('stock.production.lot', 'Lot/Serial Number', domain="[('product_id','=',product_id)]")
    location_id = fields.Many2one('stock.location', 'Location', required=True, domain="[('usage', '=', 'internal')]")
    #Himanshu 25-07-2020 check_lot field is added to make lot_id required when it is true
    check_lot=fields.Boolean()
    #End Himanshu


    @api.model
    def default_get(self, fields):
        #Himanshu product 15-08-2020 on the click of "update_qty_on_hand" button the data for that product will be added by default in the tree

        var=self.env['product.product'].search([('product_tmpl_id', '=', self.env.context['active_id'])], limit=1).id
        data=self.env['stock.quant'].search([('product_id','=',var)])
        lot_data=[]
        qty_count=0
        for i in data:
            if i.quantity >=0:
                qty_count+=i.quantity
                data_line = {'stock_production_id': i.lot_id.id ,'product_qty': i.quantity or 0.0}
                lot_data.append(data_line)
        print("lot_data...........",lot_data)

        #End Himanshu



        res = super(ProductChangeQuantity, self).default_get(fields)
        if not res.get('product_id') and self.env.context.get('active_id') and self.env.context.get('active_model') == 'product.template' and self.env.context.get('active_id'):
            res['product_id'] = self.env['product.product'].search([('product_tmpl_id', '=', self.env.context['active_id'])], limit=1).id
        elif not res.get('product_id') and self.env.context.get('active_id') and self.env.context.get('active_model') == 'product.product' and self.env.context.get('active_id'):
            res['product_id'] = self.env['product.product'].browse(self.env.context['active_id']).id
        if 'location_id' in fields and not res.get('location_id'):
            company_user = self.env.user.company_id
            warehouse = self.env['stock.warehouse'].search([('company_id', '=', company_user.id)], limit=1)
            if warehouse:
                res['location_id'] = warehouse.lot_stock_id.id


        #Himanshu product 15-09-2020 added the data in the tree view lines
        if 'stock_prod_lot_lines' in fields and not res.get('stock_prod_lot_lines'):
            res.update(stock_prod_lot_lines= [(0,0,k) for k in lot_data])
        res['new_quantity'] = qty_count

        #end Himanshu
        # res.update({'stock_prod_lot_lines': data.stock_production_id.id})
        # res.update({'new_quantity': data.product_qt

        return res

    @api.onchange('location_id', 'product_id')
    def onchange_location_id(self):
        # TDE FIXME: should'nt we use context / location ?
        if self.location_id and self.product_id:
            availability = self.product_id.with_context(compute_child=False)._product_available()
            #Himanshu product 15-09-2020 commented this line to get the on_hand qty in the smart button
            # self.new_quantity = availability[self.product_id.id]['qty_available']
            #End Himanshu

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.product_tmpl_id = self.onchange_product_id_dict(self.product_id.id)['product_tmpl_id']
        # # Himanshu 25-07-2020 from product_tmpl_id.tracking the tracking of the product is stored in val and new_qty is also getting invisible if the tracebility is of no_tracking
        # val=self.product_tmpl_id.tracking
        # if val=="lot" or val=="serial":
        #     self.check_lot=True
        # #End Himanshu

    # Himanshu product 20-09-2020  this function will run on the click of apply button in the update_qty_on_hand lot tree and will create a inventory and then in stock_quant
    #this function will only run if the tracebility is of a lot type and it could also run multiple times because the tree view can have multiple lots
    def _action_start_line_for_tree(self,data):

        product = self.product_id.with_context(location=self.location_id.id, lot_id=self.lot_id.id)
        th_qty = product.qty_available
        print("product_qty.......",data.product_qty)
        res = {
               'product_qty': data.product_qty,
               'location_id': self.location_id.id,
               'product_id': self.product_id.id,
               'product_uom_id': self.product_id.uom_id.id,
               'theoretical_qty': th_qty,
               'prod_lot_id': data.stock_production_id.id,
        }
        return res

    # End Himanshu
    def _action_start_line(self):
        product = self.product_id.with_context(location=self.location_id.id, lot_id=self.lot_id.id)
        th_qty = product.qty_available

        res = {
               'product_qty': self.new_quantity,
               'location_id': self.location_id.id,
               'product_id': self.product_id.id,
               'product_uom_id': self.product_id.uom_id.id,
               'theoretical_qty': th_qty,
               # 'prod_lot_id': data.stock_production_id.id,
                #'prod_lot_id': self.lot_id.id,
        }

        return res


    def onchange_product_id_dict(self, product_id):
        return {
            'product_tmpl_id': self.env['product.product'].browse(product_id).product_tmpl_id.id,
        }

    @api.model
    def create(self, values):
        if values.get('product_id'):
            values.update(self.onchange_product_id_dict(values['product_id']))
        return super(ProductChangeQuantity, self).create(values)

    @api.constrains('new_quantity')
    def check_new_quantity(self):
        if any(wizard.new_quantity < 0 for wizard in self):
            raise UserError(_('Quantity cannot be negative.'))

    def change_product_qty(self):
        """ Changes the Product Quantity by making a Physical Inventory. """
        # Himanshu 27-07-2020 New qty on hand and qty of lot/serial in lines should match in product
        if self.new_quantity >0: # if user does't add any quantity in the new qty on hand then we should check the condition
            count=0
            for i in self.stock_prod_lot_lines:
                count+= i.product_qty

            if count != self.new_quantity  and self.product_id.product_tmpl_id.tracking !='none':
                raise ValidationError(_('Lot/Serial Wise Qty and New Quantity on Hand Mismatch !'))
        else:
            raise ValidationError(_("Enter quantity in New Qty On Hand"))
        #End Himanshu


        #Himanshu product  20-09-2020 here below two conditions are being added if the stock_prod_lot_lines got some data then the else condtion will run otherwise if because
        #else condition will only execute when tracebility is of lot/serial type that means some lot's got added in the tree views.

        data = self.stock_prod_lot_lines
        # for i in data:
        #     self.env['stock.change.lot.line'].search([('product_id','=',self.product_id.id)]).update({'product_qty':i.product_qty})
        Inventory = self.env['stock.inventory']
        for wizard in self:
            product = wizard.product_id.with_context(location=wizard.location_id.id, lot_id=wizard.lot_id.id)
            if len(data) > 0:
                for rec in data:
                    line_data = wizard._action_start_line_for_tree(rec)
                    if wizard.product_id.id and rec.stock_production_id.id:
                        inventory_filter = 'none'
                    elif wizard.product_id.id:
                        inventory_filter = 'product'
                    else:
                        inventory_filter = 'none'
                    inventory = Inventory.create({
                        'name': _('INV: %s') % tools.ustr(wizard.product_id.display_name),
                        'filter': inventory_filter,
                        'product_id': wizard.product_id.id,
                        'location_id': wizard.location_id.id,
                        'lot_id': rec.stock_production_id.id,
                        'line_ids': [(0, 0, line_data)],
                    })
                    inventory.action_done()
            else:

                line_data = wizard._action_start_line()
                if wizard.product_id.id and wizard.lot_id.id:
                    inventory_filter = 'none'
                elif wizard.product_id.id:
                    inventory_filter = 'product'
                else:
                    inventory_filter = 'none'
                inventory = Inventory.create({
                    'name': _('INV: %s') % tools.ustr(wizard.product_id.display_name),
                    'filter': inventory_filter,
                    'product_id': wizard.product_id.id,
                    'location_id': wizard.location_id.id,
                    'lot_id': wizard.lot_id.id,
                    'line_ids': [(0, 0, line_data)],
                })
                inventory.action_done()
        return {'type': 'ir.actions.act_window_close'}
