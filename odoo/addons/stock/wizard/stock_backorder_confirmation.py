# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class StockBackorderConfirmation(models.TransientModel):
    _name = 'stock.backorder.confirmation'
    _description = 'Backorder Confirmation'

    pick_ids = fields.Many2many('stock.picking', 'stock_picking_backorder_rel')

    @api.one
    def _process(self, cancel_backorder=False):
        self.pick_ids.action_done()

        # Piyush: code for making move of individual item in backorder on 25-06-2020

        for vals in self:
            for item in vals.pick_ids:

                for mv in item.move_lines:
                    for line in mv.move_line_ids:

                        if line.individual_box:

                            stlc = line.move_id and line.move_id.location_id and line.move_id.location_id.id or False
                            stds = line.move_id and line.move_id.location_dest_id and line.move_id.location_dest_id.id or False

                            # making dictionary of required item for individual box
                            stock_dict = {
                                'name': item.name or '',
                                'product_id': line.individual_box.id,
                                'product_uom_qty': line.individual_box_item_qty,
                                'quantity_done': line.individual_box_item_qty,
                                'location_id': stlc,
                                'location_dest_id': stds,
                                'state': 'draft',
                                'product_uom': line.individual_box.uom_id.id,
                                'company_id': self.env.user.company_id.id,
                            }

                            # creating stock_dict values in environment of stock.move

                            stock_move_id = self.env['stock.move'].create(stock_dict)

                            if stock_move_id:
                                # code for comparing on hand qty of individual box and master box on 25-06-2020
                                if line.individual_box and line.individual_box_item_qty and line.env.user.company_id.default_positive_stock:
                                    if line.individual_box_item_qty > line.individual_box.qty_available:
                                        raise ValidationError(
                                            'Cannot issue quantity more than available. For {} available quantity '
                                            'is {} '.format(line.individual_box.name,
                                                            line.individual_box.qty_available))
                                    elif line.individual_box_item_qty == 0:
                                        raise ValidationError(
                                            'Individual Box quantity can not be 0, please provide sufficient quantity! '
                                        )
                                var = stock_move_id._action_confirm()._action_done()
                                # var = stock_move_id.action_done()

                # creating stock move for master box item 25-06-2020

                # code for creating qty of master box 25-06-2020

                comp_dict = {}
                for ml in item.move_lines:
                    for line_ids in ml.move_line_ids:
                        if line_ids.master_box_item_id:
                            if line_ids.master_box_item_id.id not in comp_dict:
                                comp_dict[line_ids.master_box_item_id.id] = [line_ids.result_package_id.id]
                            elif line_ids.master_box_item_id.id in comp_dict:
                                if line_ids.result_package_id.id not in comp_dict.get(line_ids.master_box_item_id.id):
                                    values_of_key = comp_dict.get(line_ids.master_box_item_id.id)
                                    creating_values_of_key = values_of_key
                                    creating_values_of_key.append(line_ids.result_package_id.id)
                                    comp_dict[line_ids.master_box_item_id.id] = creating_values_of_key

                # creating dict of master box for stock move

                if comp_dict:

                    for data in comp_dict:
                        product_id = self.env['product.product'].browse(data)
                        stock_dict_master = {
                            'name': item.name or '',
                            'product_id': data,
                            'product_uom_qty': len(comp_dict[data]),
                            'quantity_done': len(comp_dict[data]),
                            'location_id': mv.location_id and mv.location_id.id or False,
                            'location_dest_id': mv.location_dest_id and mv.location_dest_id.id or False,
                            'state': 'draft',
                            'product_uom': product_id.uom_id.id or False,
                            'company_id': self.env.user.company_id.id,
                        }

                        # creating stock_move_id_new values in environment of stock.move

                        stock_move_id_new = self.env['stock.move'].create(stock_dict_master)
                        if stock_move_id_new:
                            # code for comparing on hand qty of master box and master box on 07-05-2020
                            if product_id and product_id.env.user.company_id.default_positive_stock:
                                if len(comp_dict[data]) > product_id.qty_available:
                                    raise ValidationError(
                                        'Cannot issue quantity more than available. For {} available quantity '
                                        'is {} '.format(product_id.name, product_id.qty_available))
                                elif len(comp_dict[data]) == 0:
                                    raise ValidationError(
                                        'Master Box quantity can not be 0, please provide sufficient quantity! '
                                    )
                            var_new = stock_move_id_new._action_confirm()._action_done()

                            # code ends here

            if cancel_backorder:
                for pick_id in vals.pick_ids:
                    backorder_pick = self.env['stock.picking'].search([('backorder_id', '=', pick_id.id)])
                    backorder_pick.action_cancel()
                    pick_id.message_post(body=_("Back order <em>%s</em> <b>cancelled</b>.") % (",".join([b.name or '' for b in backorder_pick])))

    def process(self):
        self._process()

    def process_cancel_backorder(self):
        self._process(cancel_backorder=True)
