# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from itertools import groupby

from num2words import num2words
from odoo.addons.account.models import genric
from collections import Counter
from odoo.addons.sale.models.sale import SaleOrder
from odoo import api, fields, models, _, tools
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, ValidationError, AccessError
from datetime import datetime, timedelta, date
from odoo.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools import float_utils
from odoo.osv import expression


class SaleOrder(models.Model):
    _inherit = "sale.order"


    mfg_exist = fields.Boolean("Manufacturing Exist")

    inv_check = fields.Boolean("Inventory from sale")

    sale_inv_options = fields.Selection([
        ('update_stock', 'Update Stock'), ('inv_adj', 'Inventory Adjustment')
    ], default='update_stock', string='Option')

    # check_produced_qty = fields.Boolean("Check Produced", compute='compute_stock_produced_qty')
    check_produced_inv = fields.Float(string='Check INV Produced', compute='_assign_compute_produced_qty')



    @api.model
    def create(self, vals):
        result = super(SaleOrder, self).create(vals)
        mfg_installed = self.env['ir.module.module'].search([('name', '=', 'mrp')])
        print("mfg_installed.statexxxxxx", mfg_installed.state, mfg_installed)
        #
        if not mfg_installed or mfg_installed.state != 'installed':
            # when mrp uninstalled set false
            result.mfg_exist=False
        else:
            # when mrp installed set true
            result.mfg_exist=True

        return result



    # Gaurav may20 added function call on update stock
    # first check mrp installed or not then checking filtered MTO products or not, if mto products are available only then
    # inventory adjustment possible otherwise raise validation
    @api.multi
    def action_update_stock(self):
        res = super(SaleOrder,self).action_update_stock()
        # Aman 12/09/2020 Added validation, if pending quantity is zero for mto product then validation should be displayed on click of stock update button
        mto_exist = self.check_mrp_mod(self.order_line)
        count = 0
        for i in mto_exist:
            if i.pending_quantity == 0:
                count += 1
        if count == len(mto_exist):
            raise UserError(_('Pending Quantity must be available for MTO type product!!'))
        # Aman end
        print("cccccxxxxxxxxxxxxxx", mto_exist.ids)
        if len(mto_exist)>0:
            view = self.env.ref('sale_ext.sale_ext_view_inventory_form_inherit')
            return {
                'name': _('Inventory Adjustment (without manufacturing)'),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'stock.inventory',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'current',
                # 'res_id': self.id,
                'context': dict(
                    self.env.context,
                    default_sale_id= self.id,
                    default_sale_inv_options= self.sale_inv_options,
                    default_inv_check= True,
                    default_name= ("ADD : "+ self.name),
                ),
            }
        else:
            raise ValidationError("There is No MTO type product, Can't update stock")
        return res

    # mfg_installed = self.env['ir.module.module'].search([('name', '=', 'mrp')])
    # if not mfg_installed or mfg_installed.state != 'installed' or self.mfg_exist==False:
    # # if self.mfg_exist == True:
    #     if self.order_line :
    #         # for line in self.order_line:
    #         mto= self.order_line
    #         # print("xxxxcxxxccccxxxxx", line.product_id.route_ids.name)
    #         mto_exist = mto.filtered(lambda mto: mto.product_id.route_ids.name == 'Make To Order')

    #     Gaurav 29/5/20 added function for on hand quantity /available qty
    @api.depends('order_line.product_id')
    def _assign_compute_produced_qty(self):
        count = 0
        counts = 0
        for value in self.order_line:
            # Aman 12/09/2020 to update stock status and show produced_quantity when so is created from sale quotation
            mto_exist = value.filtered(lambda mto: mto.product_id.route_ids.name == 'Make To Order')
            if mto_exist:
                counts += 1
                if mto_exist.pending_quantity == 0:
                    count += 1
            if value.product_id:
                # gaurav commented
                # getting available quantity(on hand quantity) from product.template
                # update_search = self.env['product.template'].search(
                #                 [('id', '=', value.product_id.product_tmpl_id.id)])
                update_search = self.env['product.product'].search(
                    [('id', '=', value.product_id.id)])
                print("update_search.qty_availablexxxxxx",update_search.qty_available)
                value.produced_quantity = update_search.qty_available
                produced_quantity = update_search.qty_available
                if value.id:
                    res = {'produced_quantity': produced_quantity}
                    self.env['sale.order.line'].search([('id', '=', value.id)]).write(res)
        if count == counts:
            self.check_pending_qty = 'no_update'
        # Aman end

    @api.multi
    def action_assign_availability(self):
        """ Check availability of picking moves.
        This has the effect of changing the state and reserve quants on available moves, and may
        also impact the state of the picking as it is computed based on move's states.
        @return: True
        """
        print("Availablility", self.picking_ids)
        picking = self.picking_ids
        picking.filtered(lambda picking: picking.state == 'draft').action_confirm()
        moves = picking.mapped('move_lines').filtered(lambda move: move.state not in ('draft', 'cancel', 'done'))
        if not moves:
            raise UserError(_('Nothing to check the availability for.'))
        moves._action_assign()
        # calling to compute on hand qty in produced qty
        self._assign_compute_produced_qty()

        return True

    # Gaurav may20 added unreserve function, getting picking ids and call function for the same
    @api.multi
    def action_do_unreserve(self):
        picking = self.picking_ids
        for line in picking:
            line.move_lines._do_unreserve()




class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    reserved_qty = fields.Float("Reserved Qty", compute='compute_reserved_qty')
    picking_line_ids = fields.One2many(related='order_id.picking_ids')

    produced_quantity = fields.Float("Available Qty")
    pending_quantity = fields.Float(string="Pending Qty", compute='compute_pending_qty')
    # remaining_quantity = fields.Float("Manufactured Quantity", compute='compute_manufactured_qty')




    # @api.depends('reserved_qty')
    # def compute_manufactured_qty(self):
    #     for val in self:
    #         stock_search = self.env['stock.move.line'].search([('product_id','=', val.product_id.id)])
    #
    #         print("stock line xxxxxxxxxx", val.product_id, stock_search)

    # def _compute_produced_qty(self):
    #     for value in self:
    #         if value.product_id:
    #             # gaurav commented
    #             # getting available quantity(on hand quantity) from product.template
    #             update_search = self.env['product.template'].search(
    #                             [('id', '=', value.product_id.product_tmpl_id.id)])
    #             print("update_search.qty_availablexxxxxx",update_search.qty_available)
    #             self.produced_quantity = update_search.qty_available


    @api.depends('product_uom_qty', 'reserved_qty', 'move_ids.quantity_done')
    def compute_pending_qty(self):
        for val in self:
            # Aman 27/10/2020 Commented done sum since it was giving negative value in pending_quantity and added qty_delivery values to it since using this field value was diplaying correct.
            # done_sum=0
            # if val.move_ids:
            #     for data in val.move_ids:
            #         done_sum = done_sum + data.quantity_done
            pend_val = val.product_uom_qty - val.reserved_qty - val.qty_delivered
            val.pending_quantity = pend_val
            # Aman end

    # Getting reserved qty
    @api.depends('move_ids.reserved_availability')
    def compute_reserved_qty(self):
        print("reserved qty")
        # print("xxx", self.picking_line_ids)
        for val in self:
            sum =0.0
            if val.move_ids:
                for mv in val.move_ids:
                    sum= sum + mv.reserved_availability
                    print("reserved qty", sum)
            val.reserved_qty = sum

            # pick_reserved = self.picking_line_ids.move_lines
            # # reserved = pick._compute_reserved_availability()
            # for val in pick_reserved:
            #     print("xxxx", val.reserved_availability)
            #     line.reserved_qty= val.reserved_availability


    # @api.onchange('product_id')
    # def product_id_change(self):
    #     res = super(SaleOrderLine, self).product_id_change()
    #     # self.reserved_qty=0
    #     for val in self:
    #         if val.product_id:
    #             self.env.cr.execute(
    #                 """ select reserved_quantity from stock_quant where product_id='%s'""" % (
    #                 val.product_id.id,))
    #             rsd_qty = self.env.cr.dictfetchall()
    #             print("xxxxxxxxxxxxxxxx",rsd_qty)
    #             rsd_list = []
    #             if rsd_qty:
    #                 for value in rsd_qty:
    #                     rsd_id = value.get('reserved_quantity')
    #                     rsd_list.append(rsd_id)
    #                     print("listtt", rsd_list, rsd_list[-1])
                # val.reserved_qty = rsd_qty[-1]

                # main_store_location = self.env['stock.location'].search([('name', '=', 'Stock'),
                #                                                          ('company_id', '=',
                #                                                           self.env.user.company_id.id)])
                # available_quantity = self.env['stock.quant']._get_available_quantity(val.product_id, main_store_location)
                # print("available_quantityxxxxxxxxxxxxxxxxxxxxx",available_quantity)
                # # val.update({
                # #     'reserved_qty' : available_quantity
                # # })
                # val.reserved_qty = available_quantity

        # return res




class Inventory(models.Model):
    _inherit = "stock.inventory"

    sale_inv_options = fields.Selection([
        ('update_stock','Update Stock'), ('inv_adj', 'Inventory Adjustment')
    ], default='inv_adj', string='Option')

    inv_check = fields.Boolean("Inventory from sale", default=False)

    sale_id = fields.Many2one('sale.order', string='Sale Order')

    reference = fields.Char("Source Document",)
    #
    selected_sale_reference = fields.Many2many('sale.order', string='Sale Reference',
                                                       )
    check_mfg_exist = fields.Boolean("Check MFG Exist")

    # def _get_quants(self):
    #     return self.env['stock.quant'].search([
    #         ('company_id', '=', self.company_id.id),
    #         ('location_id', '=', self.location_id.id),
    #         ('lot_id', '=', self.prod_lot_id.id),
    #         ('product_id', '=', self.product_id.id),
    #         ('owner_id', '=', self.partner_id.id),
    #         ('package_id', '=', self.package_id.id)])

    # getting theroetical qty
    def _get_quants(self):
        return self.env['stock.quant'].search([
            ('company_id', '=', self.company_id.id),
            ('location_id', '=', self.location_id.id),
            ('product_id', '=', self.product_id.id),
            ])

    #  Gaurav may20 added onchange sale
    # function first filter only MTO products and get required fields dictionary and values from sale order
    #  and write the values in line ids , inventory line
    @api.onchange('sale_id')
    def _onchange_sale_sale_id(self):
        print("something happened- sale_id")
        # self.line_ids=''
        sale_line_list=[]
        sil= self.env['stock.inventory.line']
        # for val in self:
        if self.sale_id:
            for value in self.sale_id:
                # Aman 5/08/2020 Commented this line since quotation_lines donot exist in sale.order model
                # and it was giving an error
                # mto_vals= self.sale_id.quotation_lines
                # Aman 25/08/2020 Added order_line since it was not picking correct product
                mto_vals = self.sale_id.order_line
                # Aman end

                print("xxxxxxxxxxx",mto_vals, value)

                vals = mto_vals.filtered(lambda mto: mto.product_id.route_ids.name == 'Make To Order')

                # Aman 25/08/2020 Commented order_line since product is being picked through order_line directly
                # for data in vals.order_line:
                for data in vals:
                    # 15/09/2020 Aman added condition of pending quantity. If there is no pending quantity then product will not go to stock.inventory.line
                    if data.pending_quantity > 0:
                        prod = data.product_id.id
                        pending_qty = data.pending_quantity
                        prod_uom= self.env.ref('product.product_uom_unit', raise_if_not_found=True)

                        # ------
                        theoretical_qty = sum([x.quantity for x in self._get_quants()])
                        if theoretical_qty and prod_uom and prod.uom_id != prod_uom:
                            theoretical_qty =prod.uom_id._compute_quantity(theoretical_qty,
                                                                           prod_uom)
                        theor_qty = theoretical_qty
                        # ------
                        data_sale = (0, False, {
                            'product_id' : prod,
                            'product_uom_id' : prod_uom,
                            'location_id': self.location_id.id,
                            'pending_qty': pending_qty,
                            'theoretical_qty': theor_qty,
                            'product_qty': theor_qty,
                        })
                        sale_line_list.append(data_sale)
                        print('sale_line_list', sale_line_list)
            # if len(sale_line_list) > 0:
        self.line_ids = sale_line_list


    # Gaurav commented 28/4/20 after converting functionality of product qty from inventory and MFG to on hand qty
    # Gaurav 29/4/20 using function for auto update reserve and available qty
    def action_done(self):
        res = super(Inventory, self).action_done()

        for val in self:
            if val.sale_id:

                for line in val.sale_id:
                    # Aman 20/08/2020 Commented this line because quotation_lines was not present in lines and was
                    # giving error and added val.line_ids in place of it
                    # for data in line.quotation_lines:
                    for data in val.line_ids:
                        sol_id = data.id
                        print("soliddddddd",sol_id)

                        if val.move_ids:
                            for value in val.move_ids:
                                sol = self.env['sale.order.line']
                                sol_search = sol.search(
                                    [('id', '=', sol_id), ('product_id', '=', value.product_id.id)])
                                if value.product_uom_qty>0:
                                    # sol_search.write({
                                    #     'produced_quantity' : value.product_uom_qty,
                                    # })
                                    #
                                    val.sale_id.action_assign_availability()


        return res


    # computing the total many to many selected sale flag to prevent the selection of duplicate order
    # @api.depends('line_ids')
    # def compute_selected_sale_reference(self):
    #     for vals in self:
    #         if vals.line_ids:
    #             all_sale_order_ids = []
    #             for val in vals.line_ids:
    #                 if val.sale_order_id:
    #                     all_sale_order_ids.append(val.sale_order_id.id)
    #             if all_sale_order_ids:
    #                 vals.selected_sale_reference = [(6, 0, all_sale_order_ids)]

    # @api.onchange('line_ids')
    # def _onchange_sale_line_ids(self):
    #     print("something happened- line_ids")
    #     previous_selected = False
    #     if self.line_ids:
    #         for vals in self.line_ids:
    #             if vals.sale_order_id:
    #                 previous_selected = True
    #     saleorder_ids = self.line_ids.mapped('sale_order_id')
    #     if saleorder_ids:
    #         self.reference = ', '.join(saleorder_ids.mapped('name'))
    #     if not previous_selected:
    #         self.reference = ''

    @api.onchange('sale_inv_options')
    def _onchange_sale_inv_options(self):
        print("something happened- option")

        if self.sale_inv_options == 'update_stock':
            self.filter = 'partial'
        else:
            self.filter = 'none'

    # Gaurav 29/5/20 added default get function to invisible pending qty according to mrp
    @api.model
    def default_get(self, fields):
        # add default check on company gst register
        res = super(Inventory, self).default_get(fields)
        mfg_installed = self.env['ir.module.module'].search([('name', '=', 'mrp')])
        print("mfg_installed.statexxxxxx", mfg_installed.state, mfg_installed)

        if 'check_mfg_exist' in fields:
            if not mfg_installed or mfg_installed.state != 'installed':
                # when mrp uninstalled set false

                res['check_mfg_exist'] = False
            else:
                # when mrp installed set true
                res['check_mfg_exist'] = True

        return res




class InventoryLine(models.Model):
    _inherit = "stock.inventory.line"

    sale_order_id = fields.Many2one('sale.order', string='Sale Order')

    sale_inv_options = fields.Selection([
        ('update_stock', 'Update Stock'), ('inv_adj', 'Inventory Adjustment')
    ], default='inv_adj', string='Option', related='inventory_id.sale_inv_options')

    produced_qty = fields.Float("Produced Quantity")
    pending_qty = fields.Float("Pending Quantity")

    # Piyush:code for creating sale order quotation, differentiating models for quotation and sale order on 18-06-2020


class SaleQuotation(models.Model):
    _name = "sale.quotation"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Sale Quotation"
    _order = 'id desc'

    # Yash START 29/12/2020 : code for print purchase invoice
    def _get_tax_items(self):
        """
        Get tax items and aggregated amount
        :return:
        """
        taxes_dict = {}
        for line in self.quotation_lines:
            for tax in line.tax_id:
                if tax.id not in taxes_dict:
                    taxes_dict[tax.id] = []
                tax_data = {
                    'tax_amount': 0,
                    'name': tax.name,
                    'id': tax.id
                }
                if tax.amount_type == 'percent':
                    tax_data['tax_amount'] = (line.price_subtotal * tax.amount) / 100
                taxes_dict[tax.id].append(tax_data)

        taxes_list = []
        for key, value in taxes_dict.items():
            data = {
                'name': '',
                'amount': 0
            }
            for tax in value:
                data['name'] = tax['name']
                data['amount'] += tax['tax_amount']
            taxes_list.append(data)
        return taxes_list

    def _get_contact_person(self):
        """
        Method to get contac person name in print
        :return:
        """
        contact_person_name = ''
        if self.partner_id.name:
            contact_person_name = self.partner_id.name
        if contact_person_name == '' and len(self.partner_id.child_ids) > 0:
            contact_person_name = self.partner_id.child_ids[0].name
        return contact_person_name

    def _get_total_amount_in_words(self):
        """
        Get total amount in words
        :return:
        """
        # total_amount_in_words = self.currency_id.amount_to_text(self.amount_total)
        # {OverflowError}abs(24961380253) must be less than 10000000000.
        # The amount must be less than 10000000000 to convert in words in Indian currency.
        if self.amount_total < 10000000000:
            # total_amount_in_words = num2words(self.amount_total, lang='en_IN').title()
            total_amount_in_words = tools.ustr('{amt_value} {amt_word}').format(
                amt_value=num2words(self.amount_total, lang='en_IN'),
                amt_word=self.currency_id.currency_unit_label,
            )
        else:
            lang_code = self.env.context.get('lang') or self.env.user.lang
            lang = self.env['res.lang'].search([('code', '=', lang_code)])
            total_amount_in_words = tools.ustr('{amt_value} {amt_word}').format(
                amt_value=num2words(self.amount_total, lang=lang.iso_code),
                amt_word=self.currency_id.currency_unit_label,
            )
        return total_amount_in_words

    def _get_delivery_days(self):
        """
        Method to get number of delivery days
        :return:
        """
        delivery_days = 0
        if self.delivery_date:
            delivery_date = datetime.strptime(self.delivery_date, "%Y-%m-%d").date()
            order_date = datetime.strptime(self.date_order, "%Y-%m-%d %H:%M:%S").date()
            delta = delivery_date - order_date
            delivery_days = delta.days or 0
        return delivery_days

    # Yash END 29/12/2020 : code for print purchase invoice

    # Piyush: code for opening amendment wizard on 21-06-2020
    def get_current_amendment_history(self):
        """Get Current Form Agreement Ammendmend History"""
        result = {}
        all_quotation_amd_ids = []
        company_id = self.env.user.company_id.id
        all_quotation_amd = self.env['sale.quotation.amd'].search(
            [('id', 'in', self.quotation_amd_ids and self.quotation_amd_ids.ids or []),
             ('company_id', '=', company_id)])
        if all_quotation_amd:
            all_quotation_amd_ids = all_quotation_amd.ids
        action = self.env.ref('sale_ext.action_sale_quotation_amd')
        result = action.read()[0]
        res = self.env.ref('sale.ext.sale_quotation_amd_tree_view', False)
        res_form = self.env.ref('sale_ext.sale_quotation_amd_form_view', False)
        result['views'] = [(res and res.id or False, 'list'), (res_form and res_form.id or False, 'form')]
        result['domain'] = [('id', 'in', tuple(all_quotation_amd_ids))]
        result['target'] = 'current'  # Piyush: code for target = current for breadcrumb
        result['view_type'] = 'tree'
        result['view_mode'] = 'tree,form'
        return result

    # code ends here

    # Piyush: code for adding days to date on 20-06-2020
    @api.multi
    @api.onchange('no_of_days_manu')
    def onchange_no_of_days_manu(self):
        if self.no_of_days_manu > 0:
            last_sale_order_manu_date = datetime.strptime(str(self.date_order), '%Y-%m-%d %H:%M:%S').date()
            self.expiration_date = last_sale_order_manu_date + timedelta(days=self.no_of_days_manu)
        elif self.no_of_days_manu == 0:
            self.expiration_date = self.date_order

    # code ends here

    @api.model
    def _get_default_team(self):
        return self.env['crm.team']._get_default_team_id()

    @api.depends('quotation_lines')
    def _amount_all(self):
        """
        Compute the total amounts of the SO.
        """
        for order in self:
            amount_untaxed = amount_tax = 0.0
            for line in order.quotation_lines:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            order.update({
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'amount_total': amount_untaxed + amount_tax,
            })

    @api.onchange('fiscal_position_id')
    def _compute_tax_id(self):
        """
        Trigger the recompute of the taxes if the fiscal position is changed on the SO.
        """
        for order in self:
            order.quotation_lines._compute_tax_id()

    @api.depends('options_stock')
    def compute_options_stock(self):

        for data in self:
            if data.options_stock == "stock_sales_order":
                data.check_option_stock = True
            else:
                data.check_option_stock = False

    def _compute_is_expired(self):
        now = datetime.now()
        for order in self:
            if order.validity_date and fields.Datetime.from_string(order.validity_date) < now:
                order.is_expired = True
            else:
                order.is_expired = False

    @api.model
    def _default_note(self):
        return self.env['ir.config_parameter'].sudo().get_param('sale.use_sale_note') and self.env.user.company_id.sale_note or ''

    @api.model
    def default_get(self, fields):
        # add default check on company gst register
        res = super(SaleQuotation, self).default_get(fields)
        if not self.env.user.company_id.vat:
            # if GST not present, company unregistered
            if 'check_registered' in fields:
                # set tax field invisible
                res['check_registered'] = True

        return res

    # Gaurav 18/3/20 starts for readonly of customer if there is data in quotation line
    @api.onchange('quotation_lines')
    def _onchange_order_line(self):
        self.check_order_line = False
        for line in self:
            if line.quotation_lines:
                self.check_order_line=True

    # Gaurav end

    @api.multi
    def unlink(self):
        for order in self:
            if order.state not in ('draft', 'cancel'):
                raise UserError(_('You can not delete a sent quotation or a sales order! Try to cancel it before.'))
        return super(SaleQuotation, self).unlink()

    @api.multi
    def _compute_is_expired(self):
        now = datetime.now()
        for order in self:
            if order.validity_date and fields.Datetime.from_string(order.validity_date) < now:
                order.is_expired = True
            else:
                order.is_expired = False

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'state' in init_values and self.state == 'sale':
            return 'sale.mt_order_confirmed'
        elif 'state' in init_values and self.state == 'sent':
            return 'sale.mt_order_sent'
        return super(SaleQuotation, self)._track_subtype(init_values)

    @api.multi
    @api.onchange('partner_shipping_id', 'partner_id')
    def onchange_partner_shipping_id(self):
        """
        Trigger the change of fiscal position when the shipping address is modified.
        """
        self.fiscal_position_id = self.env['account.fiscal.position'].get_fiscal_position(self.partner_id.id, self.partner_shipping_id.id)
        return {}

    @api.multi
    @api.onchange('partner_id')
    def onchange_partner_id(self):
        """
        Update the following fields when the partner is changed:
        - Payment terms
        - Delivery address
        """
        if not self.partner_id:
            self.update({
                'currency_id': False,
                'partner_shipping_id': False,
                'payment_term_id': False,
                'fiscal_position_id': False,
            })
            self.currency_id = self.partner_id.property_purchase_currency_id.id or self.env.user.company_id.currency_id.id
            return
            # Gaurav 13/3/20 added customer delivery address domain
        check_custmr_state_delivery = self.env['res.partner'].search(
            [('company_id', '=', self.company_id.id),
             ('type', '=', 'delivery'), ('parent_id', '=', self.partner_id.id)])

        addr = self.partner_id.address_get(['delivery', 'invoice'])
        values = {
            'payment_term_id': self.partner_id.property_payment_term_id and self.partner_id.property_payment_term_id.id or False,
            'partner_shipping_id': addr['delivery'],
            'user_id': self.partner_id.user_id.id or self.env.uid
        }
        if self.env['ir.config_parameter'].sudo().get_param('sale.use_sale_note') and self.env.user.company_id.sale_note:
            values['note'] = self.with_context(lang=self.partner_id.lang).env.user.company_id.sale_note

        if self.partner_id.team_id:
            values['team_id'] = self.partner_id.team_id.id
        self.update(values)

        # Gaurav 13/3/20 added domain result
        # result = {'domain': {'partner_shipping_id': [('id', 'in', check_custmr_state_delivery.ids)],
        #                     'partner_invoice_id': [('id', 'in', check_custmr_state_invoice.ids)]
        #                      }}
        result = {'domain': {'partner_shipping_id': [('id', 'in', check_custmr_state_delivery.ids)]}}
        return result
        # Gaurav end

    @api.onchange('partner_id')
    def onchange_partner_id_warning(self):

        for line in self:
            if line.quotation_lines:
                self.check_order_line = True
        # setting order line field empty on change customer

        if not self.partner_id:
            return
        warning = {}
        title = False
        message = False
        partner = self.partner_id

        # If partner has no warning, check its company
        if partner.sale_warn == 'no-message' and partner.parent_id:
            partner = partner.parent_id

        if partner.sale_warn != 'no-message':
            # Block if partner only has warning but parent company is blocked
            if partner.sale_warn != 'block' and partner.parent_id and partner.parent_id.sale_warn == 'block':
                partner = partner.parent_id
            title = ("Warning for %s") % partner.name
            message = partner.sale_warn_msg
            warning = {
                    'title': title,
                    'message': message,
            }
            if partner.sale_warn == 'block':
                self.update({'partner_id': False, 'partner_shipping_id': False})
                return {'warning': warning}

        if warning:
            return {'warning': warning}

    @api.multi
    def name_get(self):
        if self._context.get('sale_show_partner_name'):
            res = []
            for order in self:
                name = order.name
                if order.partner_id.name:
                    name = '%s - %s' % (name, order.partner_id.name)
                res.append((order.id, name))
            return res
        return super(SaleQuotation, self).name_get()

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if self._context.get('sale_show_partner_name'):
            if operator in ('ilike', 'like', '=', '=like', '=ilike'):
                domain = expression.AND([
                    args or [],
                    ['|', ('name', operator, name), ('partner_id.name', operator, name)]
                ])
                return self.search(domain, limit=limit).name_get()
        return super(SaleQuotation, self).name_search(name, args, operator, limit)

    @api.multi
    def print_quotation(self):
        self.filtered(lambda s: s.state == 'draft').write({'state': 'sent'})
        return self.env.ref('sale.action_report_saleorder').report_action(self)

    @api.multi
    def action_cancel(self):
        return self.write({'state': 'cancel'})

    @api.multi
    def action_quotation_send(self):
        """This function opens a window to compose an email, with the sale quotation message loaded by default"""
        self.ensure_one()
        ir_model_data = self.env['ir.model.data']
        try:
            template_id = ir_model_data.get_object_reference('sale_ext', 'sale_quotation_email_template')[1]
        except ValueError:
            template_id = False
        try:
            compose_form_id = ir_model_data.get_object_reference('mail', 'email_compose_message_wizard_form')[1]
        except ValueError:
            compose_form_id = False
        ctx = dict(self.env.context or {})
        ctx.update({
            'default_model': 'sale.quotation',
            'default_res_id': self.ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'custom_layout': "sale.mail_template_data_notification_email_sale_order",
            'proforma': self.env.context.get('proforma', False),
            # 'mark_so_as_sent': True,
            'force_email': True
        })
        return {
            'name': _('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
        }

    @api.multi
    def force_quotation_send(self):
        for order in self:
            email_act = order.action_quotation_send()
            if email_act and email_act.get('context'):
                email_ctx = email_act['context']
                email_ctx.update(default_email_from=order.company_id.email)
                order.with_context(email_ctx).message_post_with_template(email_ctx.get('default_template_id'))
        return True

    @api.multi
    def _action_confirm(self):
        for order in self.filtered(lambda order: order.partner_id not in order.message_partner_ids):
            order.message_subscribe([order.partner_id.id])
        self.write({
            'state': 'confirmed',
            'confirmation_date': fields.Datetime.now()
        })
        if self.env.context.get('send_email'):
            self.force_quotation_send()

        # create an analytic account if at least an expense product
        for order in self:
            if any([expense_policy not in [False, 'no'] for expense_policy in
                    order.order_line.mapped('product_id.expense_policy')]):
                if not order.analytic_account_id:
                    order._create_analytic_account()
        # ravi end
        return True

    # Aman 30/09/2020 Added a function to change the state of sale quotation to confirmed
    @api.multi
    def action_confirm_sq(self):
        self.state = 'confirmed'
    # Aman end

    # Aman 09/10/2020 Added a function to change the state of sale quotation to lost
    @api.multi
    def lost_order_button(self):
        genric.state_lost(self)
    # Aman end

    # Piyush: code for items with SO, on 21-06-2020
    @api.multi
    def action_confirm(self):
        for rec in self:
            rfq_line_list = []
            count = 0
            counts = 0
            if rec.quotation_lines:
                for lines in rec.quotation_lines:
                    counts += 1
                    # checking for taxes available for SQ
                    line_tax_list = []

                    if lines.tax_id:
                        line_tax_list = [ltax.id for ltax in lines.tax_id]

                    # checking if unit price already exist or not, if yes assign it to price unit
                    # Aman 29/09/2020 When we create so from sale.quotation unit price was not displaying correct
                    price = 0.0
                    if lines.price_unit:
                        price = lines.price_unit
                    else:
                        unit_price = self.env['product.saledetail'].search([('product_id', '=', lines.product_id.id),
                                                                            ('customer_partner_id', '=',
                                                                             rec.partner_id.id),
                                                                            ('company_id', '=',
                                                                             self.env.user.company_id.id)])
                        if unit_price:
                            for up in unit_price:
                                price = up.price
                    # unit_price = self.env['product.saledetail'].search([('product_id', '=', lines.product_id.id),
                    #                                                     ('customer_partner_id', '=', rec.partner_id.id),
                    #                                                     ('company_id', '=', self.env.user.company_id.id)])
                    # price = 0.0
                    # if unit_price:
                    #     for up in unit_price:
                    #         price = up.price
                    # else:
                    #     price = lines.price_unit
                    # creating dict of rfq line data if price unit is more than 0 else raise error on 17-07-2020
                    # Aman 29/09/2020 Corrected code for partial order by subtracting total_qty_ordered_hidden by product_uom_qty so that we can get amount of qty which is left
                    # salman add hsn_id only
                    if lines.price_unit > 0.0 and lines.product_uom_qty != lines.total_qty_ordered_hidden:
                        order_line_data = (0, False, {
                            'product_id': lines.product_id and lines.product_id.id or False,
                            'hsn_id':lines.hsn_id,
                            'name': lines.product_id and lines.product_id.name or '',
                            'additional_info': lines.additional_info or '',
                            'item_code': lines.item_code or '',
                            'product_uom': lines.product_uom and lines.product_uom.id or False,
                            'product_uom_qty': lines.product_uom_qty - lines.total_qty_ordered_hidden or 0.0,
                            'price_subtotal': lines.price_subtotal or 0.0,
                            'price_total': lines.price_total or 0.0,
                            # Aman 29/09/2020 Added price tax since it was not displaying on so created from sale quotation
                            'price_tax': lines.price_tax,
                            # Aman end
                            'price_unit': price or 0.0,
                            'tax_id': [(6, 0, line_tax_list)],
                            'company_id': lines.company_id.id or self.env.user.company_id.id,
                        })
                        rfq_line_list.append(order_line_data)
                    elif lines.price_unit == 0:
                        raise ValidationError(_("Please provide unit price!"))
                    elif lines.product_uom_qty == lines.total_qty_ordered_hidden:
                        count += 1
            if count == counts:
                raise ValidationError(_("Order already placed for all quantities of this quotation!!"))
            # Aman end
            # code for opening SO form and sending default context on 17-07-2020
            if len(rfq_line_list) > 0:
                action = self.env.ref('sale.action_orders')
                result = action.read()[0]
                res = self.env.ref('sale.view_from_quotation_to_so', False)
                # res = self.env.ref('sale.view_order_form', False)
                result['views'] = [(res and res.id or False, 'form')]
                result['target'] = 'current'
                result['context'] = {
                    'default_name': 'New' or '',
                    'default_origin': rec.name or '',
                    'default_reference_quot': rec.id or False,
                    'default_date_order': rec.date_order or fields.datetime.now(),
                    'default_partner_id': rec.partner_id and rec.partner_id.id or False,
                    'default_partner_shipping_id': rec.partner_shipping_id and rec.partner_shipping_id.id or False,
                    'default_no_of_days_manu': rec.no_of_days_manu or 0,
                    'default_currency_id': rec.currency_id and rec.currency_id.id or False,
                    'default_confirmation_date': rec.expiration_date or fields.datetime.now(),
                    'default_company_id': rec.company_id and rec.company_id.id or self.env.user.company_id.id,
                    'default_payment_term_id': rec.payment_term_id and rec.payment_term_id.id or False,
                    'default_client_order_ref': rec.client_order_ref or '',
                    'default_check_scheduled': rec.check_scheduled or False,
                    'default_check_so_from_sq': True,
                    'default_so_type': 'direct',
                    'default_order_line': rfq_line_list or [],
                }
                return result
        # code ends here

    def _get_forbidden_state_confirm(self):
        return {'done', 'cancel'}

    @api.multi
    def _create_analytic_account(self, prefix=None):
        for order in self:
            name = order.name
            if prefix:
                name = prefix + ": " + order.name
            analytic = self.env['account.analytic.account'].create({
                'name': name,
                'code': order.client_order_ref,
                'company_id': order.company_id.id,
                'partner_id': order.partner_id.id
            })
            order.analytic_account_id = analytic

    @api.multi
    def order_lines_layouted(self):
        """
        Returns this order lines classified by sale_layout_category and separated in
        pages according to the category pagebreaks. Used to render the report.
        """
        self.ensure_one()
        report_pages = [[]]
        # Piyush: commented for giving quotation_lines instead of order lines
        # for category, lines in groupby(self.order_line, lambda l: l.layout_category_id):
        for category, lines in groupby(self.quotation_lines, lambda l: l.layout_category_id):
            # If last added category induced a pagebreak, this one will be on a new page
            if report_pages[-1] and report_pages[-1][-1]['pagebreak']:
                report_pages.append([])
            # Append category to current report page
            report_pages[-1].append({
                'name': category and category.name or _('Uncategorized'),
                'subtotal': category and category.subtotal,
                'pagebreak': category and category.pagebreak,
                'lines': list(lines)
            })

        return report_pages

    @api.multi
    def _get_tax_amount_by_group(self):
        self.ensure_one()
        res = {}
        # Piyush: commented for giving quotation_lines instead of order lines
        # for line in self.order_line:
        for line in self.quotation_lines:
            price_reduce = line.price_unit * (1.0 - line.discount / 100.0)
            taxes = line.tax_id.compute_all(price_reduce, quantity=line.product_uom_qty, product=line.product_id,
                                            partner=self.partner_shipping_id)['taxes']
            for tax in line.tax_id:
                group = tax.tax_group_id
                res.setdefault(group, {'amount': 0.0, 'base': 0.0})
                for t in taxes:
                    if t['id'] == tax.id or t['id'] in tax.children_tax_ids.ids:
                        res[group]['amount'] += t['amount']
                        res[group]['base'] += t['base']
        res = sorted(res.items(), key=lambda l: l[0].sequence)
        res = [(l[0].name, l[1]['amount'], l[1]['base'], len(res)) for l in res]
        return res

    @api.multi
    def get_access_action(self, access_uid=None):
        """ Instead of the classic form view, redirect to the online order for
        portal users or if force_website=True in the context. """
        # TDE note: read access on sales order to portal users granted to followed sales orders
        self.ensure_one()

        if self.state != 'cancel' and (self.state != 'draft' or self.env.context.get('mark_so_as_sent')):
            user, record = self.env.user, self
            if access_uid:
                user = self.env['res.users'].sudo().browse(access_uid)
                record = self.sudo(user)
            if user.share or self.env.context.get('force_website'):
                try:
                    record.check_access_rule('read')
                except AccessError:
                    if self.env.context.get('force_website'):
                        return {
                            'type': 'ir.actions.act_url',
                            'url': '/my/orders/%s' % self.id,
                            'target': 'self',
                            'res_id': self.id,
                        }
                    else:
                        pass
                else:
                    return {
                        'type': 'ir.actions.act_url',
                        'url': '/my/orders/%s?access_token=%s' % (self.id, self.access_token),
                        'target': 'self',
                        'res_id': self.id,
                    }
        else:
            action = self.env.ref('sale.action_quotations', False)
            if action:
                result = action.read()[0]
                result['res_id'] = self.id
                return result
        return super(SaleQuotation, self).get_access_action(access_uid)

    def get_mail_url(self):
        return self.get_share_url()

    def get_portal_confirmation_action(self):
        return self.env['ir.config_parameter'].sudo().get_param('sale.sale_portal_confirmation_options', default='none')

    @api.multi
    def _notification_recipients(self, message, groups):
        groups = super(SaleQuotation, self)._notification_recipients(message, groups)

        self.ensure_one()
        if self.state not in ('draft', 'cancel'):
            for group_name, group_method, group_data in groups:
                if group_name == 'customer':
                    continue
                group_data['has_button_access'] = True

        return groups

    # Piyush: code to count amendment when type is arc on 08-05-2020
    @api.multi
    @api.depends('quotation_amd_ids')
    def _compute_amendment_count(self):
        for amd in self:
            amd.amendment_count = len(amd.quotation_amd_ids)
    # code ends here

    name = fields.Char(string='Order Reference', required=True, copy=False, readonly=True,
                       states={'draft': [('readonly', False)]}, index=True, default=lambda self: _('New'))
    origin = fields.Char(string='Source Document',
                         help="Reference of the document that generated this sales order request.")
    enquiry_type = fields.Selection([('formal', 'Formal'),
                                     ('budgetary', 'Budgetary')],
                                    string="Enquiry Type", default="formal", required=True)
    client_order_ref = fields.Char(string='Customer Reference', copy=False)
    # Piyush: field added for amendment on 21-06-2020
    amendment_count = fields.Integer(compute='_compute_amendment_count', string='Number of Amendment')
    quotation_amd_ids = fields.One2many('sale.quotation.amd', 'quotation_amd_id',
                                        string='Requisition Amendment', readonly=True)
    state = fields.Selection([
        ('draft', 'Quotation'),
        ('sent', 'Quotation Sent'),
        ('confirmed', 'Confirmed'),
        ('lost', 'Lost Order'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
        ('partial_order', 'Partial Ordered')
    ], string='Status', readonly=True, copy=False, index=True, track_visibility='onchange', default='draft')
    currency_id = fields.Many2one('res.currency', 'Currency', required=True,
                                  default=lambda self: self.env.user.company_id.currency_id.id)
    date_order = fields.Datetime(string='Quotation Date', required=True, readonly=True, index=True,
                                 states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},
                                 copy=False, default=fields.Datetime.now)
    validity_date = fields.Date(string='Expiration Date', readonly=True, copy=False,
                                states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},
                                help="Manually set the expiration date of your quotation (offer), or it will set the date automatically based on the template if online quotation is installed.")
    is_expired = fields.Boolean(compute='_compute_is_expired', string="Is expired")
    create_date = fields.Datetime(string='Creation Date', readonly=True, index=True,
                                  help="Date on which sales order is created.")
    confirmation_date = fields.Datetime(string='Confirmation Date', readonly=True, index=True,
                                        help="Date on which the sales order is confirmed.",
                                        oldname="date_confirm", copy=False)
    user_id = fields.Many2one('res.users', string='Salesperson', index=True, track_visibility='onchange',
                              default=lambda self: self.env.user)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True,
                                 states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},
                                 required=True, change_default=True, index=True, track_visibility='always',
                                 store=True)
    partner_shipping_id = fields.Many2one('res.partner', string='Delivery Address', readonly=True,
                                          required=True, states={'draft': [('readonly', False)],
                                                                 'sent': [('readonly', False)]}, store=True,
                                          help="Delivery address for current sales order.")
    #Himanshu 02-12-2020 SO to show the address of the customer
    address = fields.Text(readonly=True)
    # End Himanshu
    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account', readonly=True,
                                          states={'draft': [('readonly', False)],
                                                  'sent': [('readonly', False)]},
                                          help="The analytic account related to a sales order.", copy=False,
                                          oldname='project_id')

    quotation_lines = fields.One2many('sale.quotation.line', 'quotation_id', string='Quotation Lines',
                                 states={'cancel': [('readonly', True)], 'done': [('readonly', True)]},
                                 copy=True, auto_join=True)

    note = fields.Text('Terms and conditions', default=_default_note)
    amount_untaxed = fields.Monetary(string='Untaxed Amount', store=True, readonly=True,
                                     compute='_amount_all', track_visibility='onchange')
    amount_tax = fields.Monetary(string='Taxes', store=True, readonly=True, compute='_amount_all')
    amount_total = fields.Monetary(string='Total', store=True, readonly=True, compute='_amount_all',
                                   track_visibility='always')

    payment_term_id = fields.Many2one('account.payment.term', string='Payment Terms',
                                      oldname='payment_term')
    fiscal_position_id = fields.Many2one('account.fiscal.position', oldname='fiscal_position',
                                         string='Fiscal Position')
    company_id = fields.Many2one('res.company', 'Company',
                                 default=lambda self: self.env['res.company']._company_default_get(
                                     'sale.order'))
    team_id = fields.Many2one('crm.team', 'Sales Channel', change_default=True, default=_get_default_team,
                              oldname='section_id')
    product_id = fields.Many2one('product.product', related='quotation_lines.product_id', string='Product')
    expiration_date = fields.Date(string='Expiration Date', default=fields.datetime.now())
    no_of_days_manu = fields.Integer(string='Validity Days')
    check_registered = fields.Boolean("Check Registered", store=True, default=False)
    check_order_line = fields.Boolean("Check Order Line", store=True, default=False)
    check_scheduled = fields.Boolean("As per scheduled", store=True, default=False)
    so_type = fields.Selection([('adhoc', 'Adhoc Order'),('arc', 'Arc'), ('open_order', 'Open Order'),
                                ('direct', 'Direct')], string="Order Type", default="direct", readonly=True)
    # Aman 29/09/2020 added this field to make partner_id readonly
    rest_cust = fields.Boolean("Check Product", store=True, default=False)
    # Aman 10/10/2020 Added field to check if SQ is duplicate or not
    check_duplicate = fields.Boolean(help='To remove amd when we create duplicate sale quotation', default=False)

    order_calculation_ids = fields.One2many('order.calculation.sale.quotation', 'quotation_id', 'Order Calculation Sale Quotation')
    # Yash Start - 18/12/2020 code for print sale quotation
    remarks = fields.Text('Remarks')
    notes = fields.Text('Notes')

    # Yash End

    # Himanshu SO 02-12-2020 function added to add the address related to the customer
    @api.onchange('partner_shipping_id')
    def change_delivery_address(self):
        data = self.env['res.partner'].search([('display_name', '=', self.partner_shipping_id.display_name)])
        street = data.street
        street2 = data.street2
        zip = data.zip
        city = data.city
        state = self.env['res.country.state'].search([('id', '=', data.state_id.id)]).name
        country = self.env['res.country'].search([('id', '=', data.country_id.id)]).name
        data_list = [street, street2, city, state, zip, country]
        val = ""
        for i in data_list:
            if i != False:
                val = val + str(i) + "\n"
        self.address = val

    # Himanshu SO 2-12-2020 function added to add the address related to the customer
    @api.onchange('partner_id')
    def add_delivery_address(self):
        data = self.env['res.partner'].search([('name', '=', self.partner_id.name)])
        street = data.street
        street2 = data.street2
        zip = data.zip
        city = data.city
        state = self.env['res.country.state'].search([('id', '=', data.state_id.id)]).name
        country = self.env['res.country'].search([('id', '=', data.country_id.id)]).name
        data_list = [street, street2, city, state, zip, country]
        val = ""
        for i in data_list:
            if i != False:
                val = val + str(i) + "\n"

        self.address = val
        self.gstin = self.env['res.partner'].search([('display_name', '=', self.partner_shipping_id.display_name)]).vat

        # end Himanshu

    # Aman 17/10/2020 Added function to calculate values to display on table below products table
    @api.multi
    @api.onchange('quotation_lines')
    def onchange_order_l(self):
        tax = {}
        amt = 0
        bamt = 0
        if self.quotation_lines:
            for line in self.quotation_lines:
                tax_dict = genric.check_line(line, line.tax_id, line.quotation_id.currency_id, line.quotation_id.partner_id,
                                             line.product_uom_qty)
                tax = Counter(tax_dict) + Counter(tax)
                # Aman 24/11/2020 Calculated discounted amount to show on table
                if line.product_id:
                    price = line.product_uom_qty * line.price_unit
                    if line.discount:
                        amt += price * (line.discount / 100)
                    bamt += price
                # Aman end
        charges_data_list = genric.detail_table(self, self.quotation_lines, tax, amt, bamt, round_off = False)
        self.order_calculation_ids = [(5, 0, 0)]
        self.order_calculation_ids = charges_data_list
    # Aman end

    # Aman 29/09/2020 added this function to make boolean field true or false when we click on order_line
    @api.onchange('quotation_lines')
    def on_change(self):
        self.rest_cust = False
        for line in self.quotation_lines:
            if line:
                self.rest_cust = True
    # Aman end

    # Aman 26/12/2020 Added validations to check if Item without HSN code is last item
    # Aman 08/01/2021 commented the below function
    # @api.onchange('quotation_lines')
    # def onchange_lines(self):
    #     genric.check_hsn_disable(self, self.quotation_lines)
    # Aman end

    @api.model
    def create(self, vals):

        if vals.get('name', _('New')) == _('New'):
            if 'company_id' in vals:
                vals['name'] = self.env['ir.sequence'].with_context(force_company=vals['company_id']).next_by_code('sale.quotation') or _('New')
            else:
                vals['name'] = self.env['ir.sequence'].next_by_code('sale.quotation') or _('New')

        # Makes sure 'partner_shipping_id' are defined
        if any(f not in vals for f in ['partner_shipping_id']):
            partner = self.env['res.partner'].browse(vals.get('partner_id'))
            addr = partner.address_get(['delivery'])
            vals['partner_shipping_id'] = vals.setdefault('partner_shipping_id', addr['delivery'])
        result = super(SaleQuotation, self).create(vals)

        # ravi start at 20/1/2019 for overwriting write method to product transaction updation
        if result.quotation_lines:
            for values in result.quotation_lines:
                if values.product_id:
                    product_tmpl_id = values.product_id.product_tmpl_id.id
                    self.env['product.template'].search([('company_id', '=', result.company_id.id),
                                                         ('id', '=', product_tmpl_id)]).write({'product_transaction': True})
        # ravi end
        return result

    @api.multi
    def copy_data(self, default=None):
        if default is None:
            default = {}
        if 'quotation_lines' not in default:
            default['quotation_lines'] = [(0, 0, line.copy_data()[0]) for line in self.quotation_lines.filtered(lambda l: not l.is_downpayment)]
            # Aman 10/10/2020 Made check_duplicate true because it is a duplicate SQ and its amd should be new
            default['check_duplicate'] = True
        return super(SaleQuotation, self).copy_data(default)

    # Piyush: code for amendment function data creation on 08-05-2020

    def _amendment_data(self, amd_name):
        line_data_list = []
        for val in self:
            if val.quotation_lines:
                for line in val.quotation_lines:
                    line_data = (0, False, {
                        'product_id': line.product_id and line.product_id.id or False,
                        'name': line.product_id and line.product_id.name or '',
                        'additional_info': line.additional_info or '',
                        'item_code': line.item_code or '',
                        'product_uom_qty': line.product_uom_qty and line.product_uom_qty or 0.0,
                        'product_uom': line.product_uom and line.product_uom.id or False,
                        'tax_id': line.tax_id or '',
                        'price_unit': line.price_unit or 0.0,
                        'discount': line.discount or 0.0,
                        'price_subtotal': line.price_subtotal or 0.0,
                        'price_total': line.price_total or 0.0,
                        'quotation_amd_id': line.quotation_id.id or False,
                        'company_id': line.company_id and line.company_id.id or False,
                    })
                    line_data_list.append(line_data)

            amd_vals = {
                'name': amd_name,
                'origin': val.origin or '',
                'so_type': val.so_type or False,
                'enquiry_type': val.enquiry_type or False,
                'quotation_amd_id': val.id or False,
                'partner_id': val.partner_id and val.partner_id.id or False,
                'partner_shipping_id': val.partner_shipping_id and val.partner_shipping_id.id or False,
                'payment_term_id': val.payment_term_id and val.payment_term_id.id or False,
                'no_of_days_manu': val.no_of_days_manu or 0,
                'amount_untaxed': val.amount_untaxed or 0.0,
                'amount_tax': val.amount_tax or 0.0,
                'amount_total': val.amount_total or 0.0,
                'client_order_ref': val.client_order_ref or '',
                'check_scheduled': val.check_scheduled,
                'date_order': val.date_order or fields.datetime.now(),
                'expiration_date': val.expiration_date or fields.datetime.now(),
                'quotation_lines': line_data_list,
            }
            return amd_vals

    # code ends here

    # Piyush: code for creating write and amd on 21-06-2020

    @api.multi
    def write(self, vals):
        # Aman 10/10/2020 Added a condition to check if sale quotation is duplicate or not
        if self.check_duplicate == False or vals.get('check_duplicate') == False:
            amd_name = ''
            if self.quotation_lines:
                amd_count = len(self.quotation_amd_ids.ids)
                amd_name = 'AMD ' + str(amd_count)
            else:
                amd_name = 'AMD '
            amd_data = self._amendment_data(amd_name)
            result = super(SaleQuotation, self).write(vals)
            if 'state' not in vals and self.state in ['draft', 'sent']:
                for item in self:
                    if 'quotation_lines' in vals or 'quotation_lines.product_uom_qty' in vals or 'quotation_lines.price_unit':
                        amd_data['product_uom_qty'] = vals.get('product_uom_qty')
                        amd_data['price_unit'] = vals.get('price_unit')
                        self.env['sale.quotation.amd'].create(amd_data)
                        # self.update({'state': 'done'})

            return result
    # code ends here


class SaleQuotationLine(models.Model):
    _name = 'sale.quotation.line'
    _description = 'Sales Quotation Line'
    _order = 'quotation_id, sequence, id'

    # Aman 9/10/2020 Added onchange function to check discount
    @api.onchange('discount')
    def check_disc(self):
        genric.check_disct(self)
    # Aman end

    # Aman 29/09/2020 Added 2 fields to compute total_qty_ordered and hidden so that we can calculate product uom qty
    total_qty_ordered = fields.Float(compute='_compute_total_qty_ordered', string="Total Ordered Qty",
                                     digits=dp.get_precision('Product Unit of Measure'))
    total_qty_ordered_hidden = fields.Float(compute='_compute_total_qty_ordered_hidden',
                                            string="Total Ordered Qty Hidden",
                                            digits=dp.get_precision('Product Unit of Measure'))

    # Aman 29/09/2020 Added function to compute total_qty_ordered so that we can calculate product uom qty
    @api.multi
    def _compute_total_qty_ordered(self):
        for items in self:
            total_qty_ordered = self.total_qty(items)
            items.total_qty_ordered = total_qty_ordered

    # Aman 29/09/2020 Added function to compute total_qty_ordered_hidden so that we can calculate product uom qty
    @api.multi
    def _compute_total_qty_ordered_hidden(self):
        for items in self:
            total_qty_ordered_hidden = self.total_qty(items)
            items.total_qty_ordered_hidden = total_qty_ordered_hidden

    def total_qty(self, items):
        total_qty = 0.0
        done = self.env['sale.order'].search(
            [('origin', '=', items.quotation_id.name), ('product_id', '=', items.product_id.id)])
        if done:
            for done in done:
                for line in done.order_line:
                    if line.state in ['draft', 'sale', 'done'] and line.product_id.id == items.product_id.id:
                        total_qty += line.product_uom_qty
            return total_qty
    # Aman end




    @api.multi
    def _analytic_compute_delivered_quantity_domain(self):
        """ Return the domain of the analytic lines to use to recompute the delivered quantity
            on SO lines. This method is a hook: since analytic line are used for timesheet,
            expense, ...  each use case should provide its part of the domain.
        """
        return ['&', ('so_line', 'in', self.ids), ('amount', '<=', 0.0)]

    @api.multi
    def _analytic_compute_delivered_quantity(self):
        """ Compute and write the delivered quantity of current SO lines, based on their related
            analytic lines.
        """
        # The delivered quantity of Sales Lines in 'manual' mode should not be erased
        self = self.filtered(lambda sol: sol.product_id.service_type != 'manual')

        # avoid recomputation if no SO lines concerned
        if not self:
            return False

        # group anaytic lines by product uom and so line
        domain = self._analytic_compute_delivered_quantity_domain()
        data = self.env['account.analytic.line'].read_group(
            domain,
            ['so_line', 'unit_amount', 'product_uom_id'], ['product_uom_id', 'so_line'], lazy=False
        )
        # Force recompute for the "unlink last line" case: if remove the last AAL link to the SO, the read_group
        # will give no value for the qty of the SOL, so we need to reset it to 0.0
        value_to_write = {}
        if self._context.get('sale_analytic_force_recompute'):
            value_to_write = dict.fromkeys([sol for sol in self], 0.0)
        # convert uom and sum all unit_amount of analytic lines to get the delivered qty of SO lines
        for item in data:
            if not item['product_uom_id']:
                continue
            so_line = self.browse(item['so_line'][0])
            value_to_write.setdefault(so_line, 0.0)
            uom = self.env['product.uom'].browse(item['product_uom_id'][0])
            if so_line.product_uom.category_id == uom.category_id:
                qty = uom._compute_quantity(item['unit_amount'], so_line.product_uom, rounding_method='HALF-UP')
            else:
                qty = item['unit_amount']
            value_to_write[so_line] += qty

        # write the delivered quantity
        for so_line, qty in value_to_write.items():
            so_line.write({'qty_delivered': qty})

        return True

    def _is_delivery(self):
        self.ensure_one()
        return False

    @api.onchange('product_uom', 'product_uom_qty')
    def product_uom_change(self):
        if not self.product_uom or not self.product_id:
            self.price_unit = 0.0
            return
        if self.quotation_id.partner_id:
            product = self.product_id.with_context(
                lang=self.quotation_id.partner_id.lang,
                partner=self.quotation_id.partner_id.id,
                quantity=self.product_uom_qty,
                date=self.quotation_id.date_order,
                uom=self.product_uom.id,
                fiscal_position=self.env.context.get('fiscal_position')
            )
            self.price_unit = 1.0
            # self.price_unit = self.env['account.tax']._fix_tax_included_price_company(self._get_display_price(product), product.taxes_id, self.tax_id, self.company_id)

    @api.multi
    def name_get(self):
        result = []
        for so_line in self:
            name = '%s - %s' % (so_line.quotation_id.name, so_line.name.split('\n')[0] or so_line.product_id.name)
            if so_line.partner_id.ref:
                name = '%s (%s)' % (name, so_line.partner_id.ref)
            result.append((so_line.id, name))
        return result

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if operator in ('ilike', 'like', '=', '=like', '=ilike'):
            args = expression.AND([
                args or [],
                ['|', ('quotation_id.name', operator, name), ('name', operator, name)]
            ])
        return super(SaleQuotationLine, self).name_search(name, args, operator, limit)

    @api.multi
    def unlink(self):
        if self.filtered(lambda x: x.state in ('sale', 'done')):
            raise UserError(_('You can not remove a sales quotation lines.\nDiscard changes and try setting the quantity to 0.'))
        return super(SaleQuotationLine, self).unlink()

    @api.multi
    def _get_delivered_qty(self):
        '''
        Intended to be overridden in sale_stock and sale_mrp
        :return: the quantity delivered
        :rtype: float
        '''
        return 0.0

    @api.multi
    def _get_real_price_currency(self):
        for cur in self:
            currency = cur.quotation_id.currency_id.id
            return currency

    @api.multi
    def _get_display_price(self, product):
        # TO DO: move me in master/saas-16 on sale.order
        product_context = dict(self.env.context, partner_id=self.quotation_id.partner_id.id, date=self.quotation_id.date_order, uom=self.product_uom.id)
        base_price = self.with_context(product_context)
        currency_id = self.quotation_id.currency_id.id
        if currency_id != self.quotation_id.currency_id.id:
            base_price = self.env['res.currency'].browse(currency_id).with_context(product_context).compute(base_price, self.quotation_id.currency_id)
        return max(base_price)

    @api.model
    def _get_customer_lead(self, product_tmpl_id):
        return False

    @api.depends('product_id.invoice_policy', 'quotation_id.state')
    def _compute_qty_delivered_updateable(self):
        for line in self:
            line.qty_delivered_updateable = (line.quotation_id.state == 'sale') and (line.product_id.service_type == 'manual') and (line.product_id.expense_policy == 'no')

    @api.depends('product_id', 'quotation_id.state', 'qty_delivered')
    def _compute_product_updatable(self):
        for line in self:
            if line.state in ['done', 'cancel'] or (line.state == 'sale' and line.qty_delivered > 0):
                line.product_updatable = False
            else:
                line.product_updatable = True

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id')
    def _compute_amount(self):
        """
        Compute the amounts of the SO line.
        """
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_id.compute_all(price, line.quotation_id.currency_id, line.product_uom_qty, product=line.product_id, partner=line.quotation_id.partner_shipping_id)
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })

    @api.depends('price_unit', 'discount')
    def _get_price_reduce(self):
        for line in self:
            line.price_reduce = line.price_unit * (1.0 - line.discount / 100.0)

    @api.depends('price_total', 'product_uom_qty')
    def _get_price_reduce_tax(self):
        for line in self:
            line.price_reduce_taxinc = line.price_total / line.product_uom_qty if line.product_uom_qty else 0.0

    @api.depends('price_subtotal', 'product_uom_qty')
    def _get_price_reduce_notax(self):
        for line in self:
            line.price_reduce_taxexcl = line.price_subtotal / line.product_uom_qty if line.product_uom_qty else 0.0

    # Gaurav 11/3/20 added check_register def for checking GST registered or not
    @api.multi
    def _check_registered_tax(self):

        check_reg = self.env['res.company'].search([('partner_id', '=', self.company_id.id)])

        if check_reg:
            for data in check_reg:
                if data.vat:
                    self.check_registered = False
                    return False
                else:
                    self.check_registered = True
                    return True
    # Gaurav end
    # Salman add Hsn field
    hsn_id = fields.Char(string='HSN code',readonly=True)
    # Salman end
    quotation_id = fields.Many2one('sale.quotation', string='Order Reference', required=True, ondelete='cascade', index=True, copy=False)
    name = fields.Text(string='Description', readonly=True, required=True, default=lambda self: self.product_id.name or '')
    sequence = fields.Integer(string='Sequence', default=10)
    price_unit = fields.Float('Unit Price', required=True, digits=dp.get_precision('Product Price'), default=0.0)
    price_subtotal = fields.Monetary(compute='_compute_amount', string='Subtotal', readonly=True, store=True)
    price_tax = fields.Float(compute='_compute_amount', string='Taxes', readonly=True, store=True)
    price_total = fields.Monetary(compute='_compute_amount', string='Total', readonly=True, store=True)
    price_reduce = fields.Float(compute='_get_price_reduce', string='Price Reduce', digits=dp.get_precision('Product Price'), readonly=True, store=True)
    tax_id = fields.Many2many('account.tax', string='Taxes')
    price_reduce_taxinc = fields.Monetary(compute='_get_price_reduce_tax', string='Price Reduce Tax inc', readonly=True, store=True)
    price_reduce_taxexcl = fields.Monetary(compute='_get_price_reduce_notax', string='Price Reduce Tax excl', readonly=True, store=True)
    discount = fields.Float(string='Discount (%)', digits=dp.get_precision('Discount'), default=0.0)
    product_id = fields.Many2one('product.product', string='Product', domain=[('sale_ok', '=', True)], change_default=True, ondelete='restrict', required=True)
    product_updatable = fields.Boolean(compute='_compute_product_updatable', string='Can Edit Product', readonly=True, default=True)
    product_uom_qty = fields.Float(string='Quantity', digits=dp.get_precision('Product Unit of Measure'), required=True, default=1.0)
    product_uom = fields.Many2one('product.uom', string='Unit of Measure', required=True, readonly=True)
    # Non-stored related field to allow portal user to see the image of the product he has ordered
    product_image = fields.Binary('Product Image', related="product_id.image", store=False)
    qty_delivered_updateable = fields.Boolean(compute='_compute_qty_delivered_updateable', string='Can Edit Delivered', readonly=True, default=True)
    qty_delivered = fields.Float(string='Delivered', copy=False, digits=dp.get_precision('Product Unit of Measure'), default=0.0)
    salesman_id = fields.Many2one(related='quotation_id.user_id', store=True, string='Salesperson', readonly=True)
    currency_id = fields.Many2one(related='quotation_id.currency_id', store=True, string='Currency', readonly=True)
    company_id = fields.Many2one(related='quotation_id.company_id', string='Company', store=True, readonly=True)
    partner_id = fields.Many2one(related='quotation_id.partner_id', store=True, string='Customer')
    additional_info = fields.Text(string="Additional Info")
    item_code = fields.Char(string="Customer Item Code")
    # Gaurav 13/3/20 added shipping address- Delivery address for order id
    order_partner_shipping_id = fields.Many2one(related='quotation_id.partner_shipping_id', store=True, string='Delivery Address')
    # Gaurav end
    analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Analytic Tags')
    is_downpayment = fields.Boolean(
        string="Is a down payment", help="Down payments are made when creating invoices from a sales order."
        " They are not copied when duplicating a sales order.")
    state = fields.Selection([
        ('draft', 'Quotation'),
        ('sent', 'Quotation Sent'),
        ('confirmed', 'Confirmed'),
        ('lost', 'Lost Order'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], related='quotation_id.state', string='Order Status', readonly=True, copy=False, store=True, default='draft')

    customer_lead = fields.Float(
        'Delivery Lead Time', default=0.0,
        help="Number of days between the order confirmation and the shipping of the products to the customer", oldname="delay")
    layout_category_id = fields.Many2one('sale.layout_category', string='Section')
    layout_category_sequence = fields.Integer(string='Layout Sequence')

    @api.multi
    def _compute_tax_id(self):
        for line in self:

            taxes = line.product_id.taxes_id.filtered(lambda r: not line.company_id or r.company_id == line.company_id).ids
            # line.tax_id = fpos.map_tax(taxes, line.product_id, line.order_id.partner_shipping_id) if fpos else taxes

            check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
            check_custmr_state = self.env['res.partner'].search([('id', '=',self.order_partner_shipping_id.id),('company_id', '=', self.company_id.id),('type','=','delivery'), ('parent_id','=',self.partner_id.id)])
            check_delivery_address= self.order_partner_shipping_id
            if check_cmpy_state.state_id == check_delivery_address.state_id:
                # if same states show taxes like CGST SGST GST
                # Getting sql query data in form of ids of taxes from account.tax
                self.env.cr.execute(""" select id from account_tax where active=True and type_tax_use='sale' AND tax_group_id not in (2,3) and company_id='%s'""" %(self.env.user.company_id.id,))
                csgst_taxes = self.env.cr.dictfetchall()
                final = [taxes.remove(val.get('id')) for val in csgst_taxes if val.get('id') in taxes if csgst_taxes]
                line.tax_id = taxes

            elif check_cmpy_state.state_id != check_delivery_address.state_id:
                # if different states show taxes like IGST
                self.env.cr.execute(""" select id from account_tax where active=True and type_tax_use='sale' AND tax_group_id!=4 and company_id='%s'""" % (self.env.user.company_id.id,))
                igst_taxes = self.env.cr.dictfetchall()
                final = [taxes.remove(val.get('id')) for val in igst_taxes if val.get('id') in taxes if igst_taxes]
                line.tax_id = taxes
            return {'domain': {'tax_id': [final]}}
    #     Gaurav end

    @api.onchange('product_id')
    def _onchange_product_id(self):
        # Aman 24/12/2020 Added condition and user error to check if product with
        # hsn_disable = True is selected in last or not
        if self.quotation_id.quotation_lines:
            if self.product_id:
                if self.quotation_id.quotation_lines[0].product_id.hsn_disable == True:
                    raise UserError(_("This item should be selected in the end!!"))
        # Aman end
        # salman add hsn_id
        self.hsn_id = self.product_id.hsn_id.hsn_code
        # salman end
        # Aman 29/09/2020 Added condition to check if customer is selected before selecting product
        if not self.quotation_id.partner_id:
            raise ValidationError(_('First select Customer!!'))
        # Aman end
        result = {}
        if not self.product_id:
            self.tax_id = ''
            return result

        vals = {}
        # Reset date, price and quantity since _onchange_quantity will provide default values
        self.price_unit = self.product_qty = 0.0
        self.product_uom = self.product_id.uom_po_id or self.product_id.uom_id
        result['domain'] = {'product_uom': [('category_id', '=', self.product_id.uom_id.category_id.id)]}

        product_lang = self.product_id.with_context(
            lang=self.partner_id.lang,
            partner_id=self.partner_id.id,
        )
        self.name = product_lang.display_name
        # Aman 27/11/2020 Added description of product on form level
        if product_lang.description:
            self.name = product_lang.description
        elif product_lang.description_sale:
            self.name += '\n' + product_lang.description_sale
        # Aman end

        # Piyush: code for picking taxes in SQ on 25-07-2020
        self.tax_id = ''
        required_taxes = []
        product = self.product_id

        if self.env.user.company_id.vat and product and self.quotation_id.partner_id:

            # GST present , company registered
            check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
            # Aman 12/12/2020 Changed partner_id with partner_shipping_id
            # check_delivery_address = self.quotation_id.partner_id
            check_delivery_address = self.quotation_id.partner_shipping_id
            # Aman end

            # checking company state and customer state is same or not
            if check_cmpy_state.state_id == check_delivery_address.state_id:
                # Aman 24/12/2020 Added condition to check if product with hsn_disable = True must pick tax
                # of the item with greatest tax
                if product.hsn_disable == True:
                    group_type = ('CGST', 'SGST')
                    taxes_cust = genric.get_taxes(self, product, group_type, sq=True)
                    for i in taxes_cust:
                        required_taxes.append(i)
                # Aman end
                else:
                    # if same states show taxes like CGST SGST GST
                    self.env.cr.execute(
                        """ select id from account_tax where active=True and type_tax_use='sale' AND tax_group_id!=4 and company_id='%s'""" % (
                            self.env.user.company_id.id,))
                    csgst_taxes = self.env.cr.dictfetchall()

                    all_sale_taxes = []
                    for val in self:
                        all_sale_taxes = val.product_id.customer_tax_lines
                    all_taxes_list = [taxes.tax_id.id for taxes in all_sale_taxes]

                    all_tax_list = [all_tax['id'] for all_tax in csgst_taxes]

                    for tax in all_tax_list:
                        for tax_id in all_taxes_list:
                            if tax == tax_id:
                                required_taxes.append(tax)

            elif check_cmpy_state.state_id != check_delivery_address.state_id:
                # Aman 24/12/2020 Added condition to check if product with hsn_disable = True must pick tax
                # of the item with greatest tax
                if product.hsn_disable == True:
                    group_type = ('IGST')
                    taxes_cust = genric.get_taxes(self, product, group_type, sq=True)
                    for i in taxes_cust:
                        required_taxes.append(i)
                # Aman end
                else:
                    # if different states show taxes like IGST
                    self.env.cr.execute(
                        """ select id from account_tax where active=True and type_tax_use='sale' AND tax_group_id not in (2,3) and company_id='%s'""" % (
                            self.env.user.company_id.id,))
                    igst_taxes = self.env.cr.dictfetchall()

                    all_sale_taxes = []
                    for val in self:
                        all_sale_taxes = val.product_id.customer_tax_lines
                    all_taxes_list = [taxes.tax_id.id for taxes in all_sale_taxes]

                    all_tax_list = [all_tax['id'] for all_tax in igst_taxes]

                    for tax in all_tax_list:
                        for tax_id in all_taxes_list:
                            if tax == tax_id:
                                required_taxes.append(tax)

            self.update({'tax_id': [(6, 0, required_taxes)]})

        return result

        # Piyush: code for amendment in quotation on 21-06-2020


class SaleQuotationAmd(models.Model):
    _name = "sale.quotation.amd"
    _description = "Sale Quotation Amendment"
    _order = "id desc"

    name = fields.Char(string='Order Reference', required=True, copy=False, readonly=True,
                       states={'draft': [('readonly', False)]}, index=True, default=lambda self: _('New'))
    quotation_amd_id = fields.Many2one('sale.quotation', string='Quotation Amd Id', index=True)
    origin = fields.Char(string='Source Document',
                         help="Reference of the document that generated this sales order request.")
    enquiry_type = fields.Selection([('formal', 'Formal'),
                                     ('budgetary', 'Budgetary')],
                                    string="Enquiry Type", default="formal", required=True)
    client_order_ref = fields.Char(string='Customer Reference', copy=False)

    state = fields.Selection([
        ('draft', 'Quotation'),
        ('sent', 'Quotation Sent'),
        ('confirmed', 'Confirmed'),
        ('lost', 'Lost Order'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True, copy=False, index=True, track_visibility='onchange', default='draft')
    currency_id = fields.Many2one('res.currency', 'Currency', required=True,
                                  default=lambda self: self.env.user.company_id.currency_id.id)
    date_order = fields.Datetime(string='Quotation Date', required=True, readonly=True, index=True,
                                 states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},
                                 copy=False, default=fields.Datetime.now)
    validity_date = fields.Date(string='Expiration Date', readonly=True, copy=False,
                                states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},
                                help="Manually set the expiration date of your quotation (offer), or it will set the date automatically based on the template if online quotation is installed.")
    is_expired = fields.Boolean(string="Is expired")
    create_date = fields.Datetime(string='Creation Date', readonly=True, index=True,
                                  help="Date on which sales order is created.")
    confirmation_date = fields.Datetime(string='Confirmation Date', readonly=True, index=True,
                                        help="Date on which the sales order is confirmed.",
                                        oldname="date_confirm", copy=False)
    user_id = fields.Many2one('res.users', string='Salesperson', index=True, track_visibility='onchange',
                              default=lambda self: self.env.user)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True,
                                 states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},
                                 required=True, change_default=True, index=True, track_visibility='always',
                                 store=True)
    partner_shipping_id = fields.Many2one('res.partner', string='Delivery Address', readonly=True,
                                          required=True, states={'draft': [('readonly', False)],
                                                                 'sent': [('readonly', False)]}, store=True,
                                          help="Delivery address for current sales order.")
    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account', readonly=True,
                                          states={'draft': [('readonly', False)],
                                                  'sent': [('readonly', False)]},
                                          help="The analytic account related to a sales order.", copy=False,
                                          oldname='project_id')

    quotation_lines = fields.One2many('sale.quotation.line.amd', 'quotation_id', string='Quotation Lines',
                                      states={'cancel': [('readonly', True)], 'done': [('readonly', True)]},
                                      copy=True, auto_join=True)

    note = fields.Text('Terms and conditions')
    amount_untaxed = fields.Monetary(string='Untaxed Amount', store=True, readonly=True,
                                     track_visibility='onchange')
    amount_tax = fields.Monetary(string='Taxes', store=True, readonly=True)
    amount_total = fields.Monetary(string='Total', store=True, readonly=True,
                                   track_visibility='always')

    payment_term_id = fields.Many2one('account.payment.term', string='Payment Terms',
                                      oldname='payment_term')
    fiscal_position_id = fields.Many2one('account.fiscal.position', oldname='fiscal_position',
                                         string='Fiscal Position')
    company_id = fields.Many2one('res.company', 'Company',
                                 default=lambda self: self.env['res.company']._company_default_get(
                                     'sale.order'))
    team_id = fields.Many2one('crm.team', 'Sales Channel', change_default=True,
                              oldname='section_id')
    product_id = fields.Many2one('product.product', related='quotation_lines.product_id', string='Product')
    expiration_date = fields.Date(string='Expiration Date', default=fields.datetime.now())
    no_of_days_manu = fields.Integer(string='Validity Days')
    check_registered = fields.Boolean("Check Registered", store=True, default=False)
    check_order_line = fields.Boolean("Check Order Line", store=True, default=False)
    check_scheduled = fields.Boolean("As per scheduled", store=True, default=False)
    so_type = fields.Selection([('adhoc', 'Adhoc Order'), ('arc', 'Arc'), ('open_order', 'Open Order'),
                                ('direct', 'Direct')], string="Order Type", default="direct", readonly=True)


class SaleQuotationLineAmd(models.Model):
    _name = "sale.quotation.line.amd"
    _description = "Sale Quotation Line Amendment"
    _order = "id desc"

    quotation_id = fields.Many2one('sale.quotation.amd', string='Order Reference', required=True, ondelete='cascade', index=True, copy=False)
    quotation_amd_id = fields.Many2one('sale.quotation', string='Quotation Amd Id', index=True)
    name = fields.Text(string='Description', readonly=True, required=True, default=lambda self: self.product_id.name or '')
    sequence = fields.Integer(string='Sequence', default=10)
    price_unit = fields.Float('Unit Price', required=True, digits=dp.get_precision('Product Price'), default=0.0)
    price_subtotal = fields.Monetary(string='Subtotal', readonly=True, store=True)
    price_tax = fields.Float(string='Taxes', readonly=True, store=True)
    price_total = fields.Monetary(string='Total', readonly=True, store=True)
    price_reduce = fields.Float(string='Price Reduce', digits=dp.get_precision('Product Price'), readonly=True, store=True)
    tax_id = fields.Many2many('account.tax', string='Taxes')
    price_reduce_taxinc = fields.Monetary(string='Price Reduce Tax inc', readonly=True, store=True)
    price_reduce_taxexcl = fields.Monetary(string='Price Reduce Tax excl', readonly=True, store=True)
    discount = fields.Float(string='Discount (%)', digits=dp.get_precision('Discount'), default=0.0)
    product_id = fields.Many2one('product.product', string='Product', domain=[('sale_ok', '=', True)], change_default=True, ondelete='restrict', required=True)
    product_updatable = fields.Boolean(string='Can Edit Product', readonly=True, default=True)
    product_uom_qty = fields.Float(string='Quantity', digits=dp.get_precision('Product Unit of Measure'), required=True, default=1.0)
    product_uom = fields.Many2one('product.uom', string='Unit of Measure', required=True, readonly=True)
    # Non-stored related field to allow portal user to see the image of the product he has ordered
    product_image = fields.Binary('Product Image', related="product_id.image", store=False)
    qty_delivered_updateable = fields.Boolean(string='Can Edit Delivered', readonly=True, default=True)
    qty_delivered = fields.Float(string='Delivered', copy=False, digits=dp.get_precision('Product Unit of Measure'), default=0.0)
    salesman_id = fields.Many2one(related='quotation_id.user_id', store=True, string='Salesperson', readonly=True)
    currency_id = fields.Many2one(related='quotation_id.currency_id', store=True, string='Currency', readonly=True)
    company_id = fields.Many2one(related='quotation_id.company_id', string='Company', store=True, readonly=True)
    partner_id = fields.Many2one(related='quotation_id.partner_id', store=True, string='Customer')
    additional_info = fields.Text(string="Additional Info")
    item_code = fields.Char(string="Customer Item Code")
    # Gaurav 13/3/20 added shipping address- Delivery address for order id
    order_partner_shipping_id = fields.Many2one(related='quotation_id.partner_shipping_id', store=True, string='Delivery Address')
    # Gaurav end
    analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Analytic Tags')
    is_downpayment = fields.Boolean(
        string="Is a down payment", help="Down payments are made when creating invoices from a sales order."
        " They are not copied when duplicating a sales order.")
    state = fields.Selection([
        ('draft', 'Quotation'),
        ('sent', 'Quotation Sent'),
        ('confirmed', 'Confirmed'),
        ('lost', 'Lost Order'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], related='quotation_id.state', string='Order Status', readonly=True, copy=False, store=True, default='draft')

    customer_lead = fields.Float(
        'Delivery Lead Time', default=0.0,
        help="Number of days between the order confirmation and the shipping of the products to the customer", oldname="delay")
    layout_category_id = fields.Many2one('sale.layout_category', string='Section')
    layout_category_sequence = fields.Integer(string='Layout Sequence')

    # code ends here

class OrderCalculationSaleQuotation(models.Model):
    _name = "order.calculation.sale.quotation"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Order Calculation Sale Quotation"
    _order = 'serial_no'

    name = fields.Char('Description')
    quotation_id = fields.Many2one('sale.quotation', 'Sale Quotation')
    category = fields.Char('Category')
    label = fields.Char('Label')
    amount = fields.Float('Amount')
    serial_no = fields.Integer('Sr No')
    company_id = fields.Many2one('res.company', 'Company', index=True,
                                 default=lambda self: self.env.user.company_id.id)
    cr_date = fields.Date(string='Create Date', required=True, readonly=True, index=True, copy=False,
                          default=fields.Datetime.now)
