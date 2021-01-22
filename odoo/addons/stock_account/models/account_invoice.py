# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import namedtuple
import json
import time
import math

from itertools import groupby

#import dp as dp

from odoo import api, fields, models, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.exceptions import UserError, ValidationError
from odoo.addons.stock.models.stock_move import PROCUREMENT_PRIORITIES
from operator import itemgetter

import logging

_logger = logging.getLogger(__name__)


class AccountInvoice(models.Model):
    _inherit = "account.invoice"


    # Gaurav modified 12/6/20 added default receipt as PO for invoice
    @api.model
    def _default_picking_receipt(self):

        purchase = self._context.get('default_purchase_id')
        search_receipt=''
        if purchase:
            print("purchase,", purchase)
            search_po_origin = self.env['purchase.order'].search([('id', '=', purchase),])
            # search_receipt = self.env['stock.picking'].search([
            #                                                    ('purchase_id', '=', purchase),
            #                                                    ])
            search_receipt = self.env['stock.picking'].search([
                ('origin', '=', search_po_origin.name), ('state','in', ('done','bill_pending')),
                ('receipt_invoiced', '=', False)])

            # search_receipt = self.env['stock.picking'].search([('origin', '=', search_po_origin.name), ('state', '=', 'bill_pending')])

            print("search_receiptxxx", search_receipt)
        return search_receipt


    # Gaurav modified 8/6/20 added default context on picking_type_ for invoice
    @api.model
    def _default_picking_type(self):
        picking_type_code = ''
        picking_type_id_name = ''
        type_obj = self.env['stock.picking.type']
        company_id = self.env.user.company_id.id
        if 'default_picking_type_code' in self._context:
            picking_type_code = self._context.get('default_picking_type_code')
            print('picking codeeeeeeeeeeeeeeeeeeee', picking_type_code)
        if 'default_picking_type_name' in self._context:
            picking_type_id_name = self._context.get('default_picking_type_name')
            print('picking codeeeeeeeeeeeeeeeeeeee', picking_type_id_name)
        if picking_type_code == 'internal':
            if picking_type_id_name == 'transfer':
                types = type_obj.search([('code', '=', 'internal'), ('name', '=', 'Transfer'),
                                         ('warehouse_id.company_id', '=', company_id)])
                if not types:
                    types = type_obj.search(
                        [('code', '=', 'internal'), ('name', '=', 'Transfer'), ('warehouse_id', '=', False)])
            else:
                types = type_obj.search([('code', '=', 'internal'), ('warehouse_id.company_id', '=', company_id)])
                if not types:
                    types = type_obj.search([('code', '=', 'internal'), ('warehouse_id', '=', False)])

        elif picking_type_code == 'outgoing':
            # avinash:27/11/20 Added to pass 'default_picking_type' on sales return form
            if picking_type_id_name == 'Sales Return':
                types = type_obj.search([('name', '=', 'Sales Return'), ('warehouse_id.company_id', '=', company_id)])
                if not types:
                    types = type_obj.search(
                        [('code', '=', 'outgoing'), ('name', '=', 'Sales Return'), ('warehouse_id', '=', False)])

            else:
                types = type_obj.search([('code', '=', 'outgoing'), ('name', '=', 'Delivery Orders'),('warehouse_id.company_id', '=', company_id)])

                if not types:
                    types = type_obj.search([('code', '=', 'outgoing'),('name', '=', 'Delivery Orders'), ('warehouse_id', '=', False)])
            # end avinash
        else:
            # avinash:27/11/20 Added to pass 'default_picking_type' on 'purchase return' form
            if picking_type_id_name == 'Purchase Return':
                types = type_obj.search([('code', '=', 'incoming'), ('name', '=', 'Purchase Return'),
                                         ('warehouse_id.company_id', '=', company_id)])
                if not types:
                    types = type_obj.search(
                        [('code', '=', 'incoming'), ('name', '=', 'Purchase Return'), ('warehouse_id', '=', False)])
            # end avinash
            else:
                types = type_obj.search([('code', '=', 'incoming'),('name', '=', 'Receipts'), ('warehouse_id.company_id', '=', company_id)])
                if not types:
                    types = type_obj.search([('code', '=', 'incoming'),('name', '=', 'Receipts'),  ('warehouse_id', '=', False)])

        return types[:1]

        # Gaurav end

    # --------Gaurav 6/6/20 added fields for vendor bills relation stock picking receipts------
    show_receipts = fields.Boolean("Show Receipts", default=False)
    picking_id = fields.Many2one('stock.picking', "Picking")
    picking_receipt_id = fields.Many2many('stock.picking', 'stock_picking_account_many2many',
                                          'invoice_id', 'picking_id', string='Add Receipts',
                                          domain="[('picking_type_code', '=', 'incoming')]",
                                          default=_default_picking_receipt)
    dispatch_ids = fields.Many2many('stock.picking', 'sale_picking_rel', 'invoice_id', 'dispatch_id',
                                    string="Related Dispatches")

    # Gaurav 8/6/20 edit for setting option stock up on vendon bills

    stock_invoice = fields.Boolean(string='Stock Up- Vendor Bills')

    # Gaurav ends

    move_lines = fields.One2many('stock.move', 'picking_id', string="Stock Moves", copy=True)

    picking_type_id = fields.Many2one(
        'stock.picking.type', 'Operation Type',
        default=_default_picking_type)
    picking_type_code = fields.Selection([
        ('incoming', 'Vendors'),
        ('outgoing', 'Customers'),
        ('internal', 'Internal')], related='picking_type_id.code',
        readonly=True)

    location_id = fields.Many2one(
        'stock.location', "Source Location",
        default=lambda self: self.env['stock.picking.type'].browse(
            self._context.get('default_picking_type_id')).default_location_src_id,
    )

    location_dest_id = fields.Many2one(
        'stock.location', "Destination Location",
        default=lambda self: self.env['stock.picking.type'].browse(
            self._context.get('default_picking_type_id')).default_location_dest_id,
        readonly=True,
        states={'draft': [('readonly', False)]})

    @api.multi
    def action_invoice_open(self):
        # ------ Gaurav 19/6/20 for 0 qty validation----
        if self.invoice_line_ids:
            lines = self.invoice_line_ids
            qty_lines = lines.filtered(lambda qty: qty.quantity == 0)
            if len(qty_lines)>0:
                raise ValidationError('Cannot Validate lines with 0 quantity!')
        #     -------------------
        # ------ Validate all receipt with bill pending state-------
        res = super(AccountInvoice, self).action_invoice_open()
        print("picking idxxxxxxxxxxxxxx", self.picking_receipt_id, self.picking_type_id.default_location_src_id,
              self.picking_type_id.default_location_dest_id)
        # if self.stock_invoice == True:
        if self.picking_receipt_id:
            pending = self.picking_receipt_id
            print("pending..xx", pending)
            if len(pending)>0:
                for recpt in pending:
                    recpt.receipt_invoiced = True # setting --> receipt is now invoiced -> do not show again (domain)
            pending_exist = pending.filtered(lambda bill: bill.state == 'bill_pending')
            print("cccccxxxxxxxxxxxxxx", pending_exist.ids)
            if len(pending_exist)>0:
                for data in pending_exist:
                    data.receipt_invoiced = True # setting --> receipt is now invoiced -> do not show again
                    data.bill_available = True
                    data.invoice_no = self.reference
                    data.delivery_invoice_date = self.date_invoice
                    data.button_validate() # validating pending receipts
        return res
    # -------- Gaurav end------

    # Gaurav 16/6/20 added this function - when multiple receipts are available, get quantity according to receipts
    # done quantity and fill lines every picking..
    @api.onchange('picking_receipt_id')
    def onchange_picking_receipt_id(self):
        print("xxxxxxxxxxxxxxxxx receipt")
        invoice_list = []
        info_list = []
        invoice_data = ()
        service_list=[]

        if self.picking_receipt_id:
            print("self.picking_receipt_id xxx", self.picking_receipt_id)
            picking_list = list(set(self.picking_receipt_id))
            # avinash
            for value in picking_list:
                if value.receipt_invoiced == True:
                    picking_list.remove(value)

            # end avinash
            print("picking_listxxx,",picking_list)
            self.invoice_line_ids=''
            for data in picking_list:

                self.invoice_line_ids=''
                for line in data.move_lines:
                    # print("stock move, invoice_dict.get('product_id')", line.product_id.id,)
                    print("stock move info list,", line.product_id.id, [val.get('product_id') for val in info_list])
                    print("pol", line.purchase_line_id.id, [val.get('purchase_line_id') for val in info_list])
                    print("price", line.purchase_line_id.price_unit, [val.get('price_unit') for val in info_list])
                    # invoice_list=[]
                    if info_list and line.product_id.id in [val.get('product_id') for val in info_list] \
                            and line.purchase_line_id.id in [val.get('purchase_line_id') for val in info_list]:
                        for val in info_list:
                            if val.get('product_id') == line.product_id.id:
                                if line.purchase_line_id.id == val.get('purchase_line_id'):
                                    print("pol", line.purchase_line_id.id, val.get('purchase_line_id'))
                                    qty = val.get('quantity') + line.quantity_done
                                    val['quantity'] = qty
                                    # val['price_unit'] = line.purchase_line_id.product_qty
                                    # avinash:16/09/20 Added lot detail when vendor bill generated from receipt.
                                    tract_type = self.check_product_tracking(line)
                                    if tract_type == ['lot', 'serial']:
                                        lot_list = val.get('lot_idss')
                                        lot_details = self.prepare_lot_detail(line)
                                        for lot in lot_details:
                                            lot_list.append(lot)
                                        val['lot_idss'] = lot_list
                                    # end avinash

                    else:
                        # taxes = line.taxes_id
                        # invoice_line_tax_ids = line.order_id.fiscal_position_id.map_tax(taxes)
                        invoice_line = self.env['account.invoice.line']
                        print("stock move, purchase line", line.purchase_line_id.product_qty)
                        po_line = line.purchase_line_id
                        invoice_dict = {
                            'purchase_line_id': line.purchase_line_id.id,
                            'name': line.origin + ': ' + line.name,
                            'origin': line.origin,
                            'uom_id': line.product_uom.id,
                            'product_id': line.product_id.id,
                            # salman add hsn_id 
                            'hsn_id': line.hsn_id,
                            # Aman 22/08/2020 income or expense account must be picked from product or journal
                            'account_id': invoice_line.get_invoice_line_account1('in_invoice', line.product_id, self.partner_id, self.env.user.company_id, po_line=po_line) or invoice_line.with_context({'journal_id': self.journal_id.id, 'type': 'in_invoice'})._default_account(),
                            'price_unit': line.purchase_line_id.price_unit,
                            'quantity': line.quantity_done,
                            'discount': line.purchase_line_id.discount or 0.0,
                            # 'account_analytic_id': line.account_analytic_id.id,
                            # 'analytic_tag_ids': line.analytic_tag_ids.ids,
                            'invoice_line_tax_ids': line.purchase_line_id.taxes_id.ids,
                            'state': line.state,
                            # avinash:22/10/20 Added so that we when vendor bill is created from receipt we cannot edit quantity field
                            'freeze_qty': True,
                            # end avinash
                        }
                        # avinash:16/09/20 Added lot detail when vendor bill generated from receipt.
                        tract_type = self.check_product_tracking(line)
                        if tract_type == ['lot', 'serial']:
                            # Add condition to show lot detail button if product type is in lot serial no
                            lot_available = True
                            lot_details = self.prepare_lot_detail(line)
                            invoice_dict.update({'lot_idss': [lot for lot in lot_details], 'check_lot_available': lot_available})
                        # end avinash

                        info_list.append(invoice_dict)
                        print("info_listxxx, ", info_list)

            last_list=[]
            for info in info_list:
                last_list.append((0, False, info))
            print("invoice_dataxxxxx", invoice_data, last_list, len(last_list))
            self.invoice_line_ids = ''
            self.invoice_line_ids = last_list
            # -------------------------- to get service type product----

            for pos in self.purchase_many_invoice_ids:
                for line in pos.order_line - self.invoice_line_ids.mapped('purchase_line_id'):
                    #Jatin added if to get only service type from po on 10-07-2020
                    print("line.product_id.type",line.product_id.type)
                    if(line.product_id.type== 'service'):
                    #end Jatin
                        print("linexxxxxx", line)
                        invoice_line = self.env['account.invoice.line']
                        data = {
                            'purchase_line_id': line.id,
                            'name': line.order_id.name + ': ' + line.name,
                            'origin': line.order_id.origin,
                            'uom_id': line.product_uom.id,
                            'product_id': line.product_id.id,
                            # Aman 22/08/2020 income or expense account must be picked from product or journal
                            'account_id': invoice_line.get_invoice_line_account1('in_invoice', line.product_id, self.partner_id, self.env.user.company_id, po_line=line) or invoice_line.with_context({'journal_id': self.journal_id.id, 'type': 'in_invoice'})._default_account(),
                            'price_unit': line.order_id.currency_id.with_context(date=self.date_invoice).compute(
                                line.price_unit, self.currency_id, round=False),
                            'quantity': line.product_qty,
                            'discount': line.discount or 0.0,
                            'account_analytic_id': line.account_analytic_id.id,
                            'analytic_tag_ids': line.analytic_tag_ids.ids,
                            'invoice_line_tax_ids': line.taxes_id.ids
                        }
                        service_list.append(data)
                        print("service_list_listxxx, ", service_list)
            self.invoice_line_ids = ''
            self.invoice_line_ids = last_list + service_list

            print("self.invoice_line_idsxxx", self.invoice_line_ids)

        else:
            self.invoice_line_ids=''
            self.get_service_product()
        return {}


    # Gaurav 19/6/20 added ths function in case of service product are there and no receipts are available
    def get_service_product(self):
        if self.purchase_many_invoice_ids:
            service_list=[]
            for pos in self.purchase_many_invoice_ids:
                for line in pos.order_line - self.invoice_line_ids.mapped('purchase_line_id'):
                    po_line = line
                    #Jatin added if to get only service type from po on 10--07-2020
                    print("line.product_id.type", line.product_id.type)
                    if (line.product_id.type == 'service'):
                    #end Jatin
                        print("linexxxxxx", line)
                        invoice_line = self.env['account.invoice.line']
                        data = {
                            'purchase_line_id': line.id,
                            'name': line.order_id.name + ': ' + line.name,
                            'origin': line.order_id.origin,
                            'uom_id': line.product_uom.id,
                            'product_id': line.product_id.id,
                            # Aman 22/08/2020 income or expense account must be picked from product or journal
                            'account_id': invoice_line.get_invoice_line_account1('in_invoice', line.product_id, self.partner_id, self.env.user.company_id, po_line=po_line) or invoice_line.with_context({'journal_id': self.journal_id.id, 'type': 'in_invoice'})._default_account(),
                            'price_unit': line.order_id.currency_id.with_context(date=self.date_invoice).compute(
                                line.price_unit, self.currency_id, round=False),
                            'quantity': line.product_qty,
                            'discount': 0.0,
                            'account_analytic_id': line.account_analytic_id.id,
                            'analytic_tag_ids': line.analytic_tag_ids.ids,
                            'invoice_line_tax_ids': line.taxes_id.ids
                        }
                        service_list.append(data)
                        print("service_list_listxxx, ", service_list)
            self.invoice_line_ids = ''
            self.invoice_line_ids = service_list

            print("self.invoice_line_idsxxx", self.invoice_line_ids)


    # --------Gaurav end -------------------------------------------------------------------

    @api.model
    def invoice_line_move_line_get(self):
        res = super(AccountInvoice, self).invoice_line_move_line_get()
        if self.company_id.anglo_saxon_accounting and self.type in ('out_invoice', 'out_refund'):
            for i_line in self.invoice_line_ids:
                res.extend(self._anglo_saxon_sale_move_lines(i_line))
        return res

    @api.model
    def _anglo_saxon_sale_move_lines(self, i_line):
        """Return the additional move lines for sales invoices and refunds.

        i_line: An account.invoice.line object.
        res: The move line entries produced so far by the parent move_line_get.
        """
        inv = i_line.invoice_id
        company_currency = inv.company_id.currency_id
        price_unit = i_line._get_anglo_saxon_price_unit()
        if inv.currency_id != company_currency:
            currency = inv.currency_id
            amount_currency = i_line._get_price(company_currency, price_unit)
        else:
            currency = False
            amount_currency = False

        return self.env['product.product']._anglo_saxon_sale_move_lines(i_line.name, i_line.product_id, i_line.uom_id, i_line.quantity, price_unit, currency=currency, amount_currency=amount_currency, fiscal_position=inv.fiscal_position_id, account_analytic=i_line.account_analytic_id, analytic_tags=i_line.analytic_tag_ids)


class AccountInvoiceLine(models.Model):
    _inherit = "account.invoice.line"

    def _get_anglo_saxon_price_unit(self):
        self.ensure_one()
        if not self.product_id:
            return self.price_unit
        return self.product_id._get_anglo_saxon_price_unit(uom=self.uom_id)

    def _get_price(self, company_currency, price_unit):
        if self.invoice_id.currency_id.id != company_currency.id:
            price = company_currency.with_context(date=self.invoice_id.date_invoice).compute(price_unit * self.quantity, self.invoice_id.currency_id)
        else:
            price = price_unit * self.quantity
        return self.invoice_id.currency_id.round(price)

    def get_invoice_line_account(self, type, product, fpos, company):
        if company.anglo_saxon_accounting and type in ('in_invoice', 'in_refund') and product and product.type == 'product':
            accounts = product.product_tmpl_id.get_product_accounts(fiscal_pos=fpos)
            if accounts['stock_input']:
                return accounts['stock_input']
        return super(AccountInvoiceLine, self).get_invoice_line_account(type, product, fpos, company)

    # Gaurav 19/5/20 added unlink function for 0 qty validation
    # @api.multi
    # def unlink(self):
    #     res= super(AccountInvoiceLine, self).unlink()
    #     if self.quantity > 0:
    #         raise UserError(_('You can only delete an invoice line if the quantity of product is 0.'))
    #     return res
    #     Gaurav end
