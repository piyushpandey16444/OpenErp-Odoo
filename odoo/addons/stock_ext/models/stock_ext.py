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


class Picking(models.Model):
    _inherit = "stock.picking"

    vendor_bill_ids = fields.Many2many('account.invoice', 'stock_picking_account_many2many',
                                          'picking_id', 'invoice_id', string='Add Vendor bills',
                                                                                    )

    # invoice_lines_ids = fields.One2many('account.invoice', 'picking_id', string='Invoice Lines')
    # invoice_lines_picking_ids = fields.One2many('account.invoice.line', 'picking_inv_id', string='Invoice Lines')

    # invoice_count = fields.Integer(compute="_compute_invoice_pick", string='# of Bills', copy=False, default=0, store=True)
    # invoice_ids = fields.Many2many('account.invoice', compute="_compute_invoice_pick", string='Bills', copy=False,
    #                                store=True)
    bill_available = fields.Boolean("Bill Available")
    bill_number = fields.Char("Bill Number")
    bill_date = fields.Date("Bill Date")
    # Jatin Added code for making bill available hidden in case of job_work_challan on 05-08-2020
    check_job_order=fields.Boolean(default=False,compute="_compute_hide_bill")
    #end jatin
    # invoice_status = fields.Selection([
    #     ('no', 'Nothing to Bill'),
    #     ('to invoice', 'Waiting Bills'),
    #     ('invoiced', 'No Bill to Receive'),
    # ], string='Billing Status', compute='_get_invoiced', store=True, readonly=True, copy=False, default='no')
    invoice_count = fields.Integer(compute="_compute_invoice_bill", string='# of Bills', copy=False, default=0, store=True)
    invoice_ids = fields.Many2many('account.invoice',  string='Bills', copy=False,
                                   store=True)
    receipt_invoiced = fields.Boolean("Rece")
    # invoice_status = fields.Selection([
    #     ('no', 'Nothing to Bill'),
    #     ('to invoice', 'Waiting Bills'),
    #     ('invoiced', 'No Bill to Receive'),
    # ], string='Billing Status', store=True, readonly=True, copy=False, default='no')

    # qty_invoiced = fields.Float(compute='_compute_qty_invoiced', string="Billed Qty",
    #                             digits=dp.get_precision('Product Unit of Measure'), store=True)
    #
    # @api.depends('invoice_lines.invoice_id.state', 'invoice_lines.quantity', 'invoice_lines.uom_id')
    # def _compute_qty_invoiced(self):
    #     for line in self:
    #         qty = 0.0
    #         for inv_line in line.invoice_lines:
    #             if inv_line.invoice_id.state not in ['cancel']:
    #                 if inv_line.invoice_id.type == 'in_invoice':
    #                     qty += inv_line.uom_id._compute_quantity(inv_line.quantity, line.product_uom)
    #                 elif inv_line.invoice_id.type == 'in_refund':
    #                     qty -= inv_line.uom_id._compute_quantity(inv_line.quantity, line.product_uom)
    #         line.qty_invoiced = qty

    # @api.depends('purchase_id.state', 'purchase_id.order_line.qty_invoiced', 'purchase_id.order_line.qty_received', 'purchase_id.order_line.product_qty')
    # def _get_invoiced(self):
    #     precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
    #     for order in self.purchase_id:
    #         if order.state not in ('purchase', 'done'):
    #             order.invoice_status = 'no'
    #             continue
    #
    #         if any(float_compare(line.qty_invoiced,
    #                              line.product_qty if line.product_id.purchase_method == 'purchase' else line.qty_received,
    #                              precision_digits=precision) == -1 for line in order.order_line):
    #             order.invoice_status = 'to invoice'
    #         elif all(float_compare(line.qty_invoiced,
    #                                line.product_qty if line.product_id.purchase_method == 'purchase' else line.qty_received,
    #                                precision_digits=precision) >= 0 for line in order.order_line) and order.invoice_ids:
    #             order.invoice_status = 'invoiced'
    #         else:
    #             order.invoice_status = 'no'
    #
    # JAtin added for hiding bill available on 05-08-2020
    @api.depends('purchase_id')
    def _compute_hide_bill(self):
        print(self.purchase_id.job_order)
        if self.purchase_id.job_order == True:
            self.check_job_order = True
    # jatin end

    @api.depends('vendor_bill_ids')
    def _compute_invoice_bill(self):
        print("xxxxxxx")
        #Jatin code added for vendor bills count on 15-07-2020
        for val in self:
            print(val.vendor_bill_ids.ids)
            count = len(val.vendor_bill_ids)
            print("xxxx count xx,", count)
            val.invoice_count = count
        for orders in self:
            for order in orders.purchase_id:
                invoices = self.env['account.invoice']
                for line in order.order_line:
                    invoices |= line.invoice_lines.mapped('invoice_id')
                order.invoice_ids = invoices
                order.invoice_count = len(invoices)
                print("order.invoice_idsxxxx",order.invoice_ids, order.invoice_count)
        #end Jatin


    # @api.multi
    # def button_validate(self):
    #     # Gaurav 6/3/20 adds delivery and LR date validation for receipts
    #     picking_namee = self.env['stock.picking.type'].browse(self.picking_type_id.id).name
    #     print("picking_nameeeeeeeeeee", picking_namee)
    #     # if self.env['stock.picking.type'].browse(vals.get('picking_type_id')).name == 'Receipts':
    #     if picking_namee == 'Receipts':
    #         if self.bill_available == False and self.state == 'bill_pending':
    #             raise ValidationError("You cannot validate this receipt, Bill should be Available !")
    #         elif self.bill_available == False:
    #             return self.write({'state' : 'bill_pending'})
    #
    #     res = super(Picking, self).button_validate()
    #     print("xxxxxxxxx validate", res, self)
    #
    #     # if self.bill_available == False :
    #     #     self.write({'state' : 'bill_pending'})
    #     #     raise ValidationError("You cannot validate this receipt, Bill should be Available !")
    #     return res



    @api.multi
    def action_view_invoice(self):
        '''
        This function returns an action that display existing vendor bills of given purchase order ids.
        When only one found, show the vendor bill immediately.
        '''
        # print("xxxxxxxxxxxxxxxxxxxpicking purchase", self.purchase_id.order_line)

        action = self.env.ref('account.action_invoice_tree2')
        result = action.read()[0]

        # override the context to get rid of the default filtering
        result['context'] = {'type': 'in_invoice', 'default_purchase_id': self.purchase_id.id,
                             'default_picking_id': self.id}

        if not self.vendor_bill_ids:
            # Choose a default account journal in the same currency in case a new invoice is created
            journal_domain = [
                ('type', '=', 'purchase'),
                ('company_id', '=', self.company_id.id),
                # ('currency_id', '=', self.currency_id.id),
            ]
            default_journal_id = self.env['account.journal'].search(journal_domain, limit=1)
            if default_journal_id:
                result['context']['default_journal_id'] = default_journal_id.id
        else:
            # Use the same account journal than a previous invoice
            # result['context']['default_journal_id'] = self.invoice_ids[0].journal_id.id
            result['context']['default_journal_id'] = self.vendor_bill_ids[0].journal_id.id

        # choose the view_mode accordingly
        if len(self.vendor_bill_ids) != 1:
            # result['domain'] = "[('id', 'in', " + str(self.invoice_ids.ids) + ")]"
            result['domain'] = "[('id', 'in', " + str(self.vendor_bill_ids.ids) + ")]"
        elif len(self.vendor_bill_ids) == 1:
            res = self.env.ref('account.invoice_supplier_form', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = self.vendor_bill_ids.id
        result['context']['default_origin'] = self.purchase_id.name
        # result['context']['default_reference'] = self.partner_ref
        # result['context']['default_show_receipts'] = True
        return result


class AccountInvoiceLine(models.Model):
    _inherit = "account.invoice.line"

    picking_inv_id = fields.Many2one('stock.picking', "Picking")