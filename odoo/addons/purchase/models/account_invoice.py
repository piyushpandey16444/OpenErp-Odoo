# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models,SUPERUSER_ID, _
from odoo.tools.float_utils import float_compare


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'


    purchase_id = fields.Many2one(
        comodel_name='purchase.order',
        string='Add Purchase Order',
        readonly=True, states={'draft': [('readonly', False)]},
        help='Encoding help. When selected, the associated purchase order lines are added to the vendor bill. Several PO can be selected.'
    )


    # Gaurav 14/3/20 added default check on company gst register
    check_registered = fields.Boolean("Check Registered", store=True, default=False)

    # Gaurav 19/6/20 added many2many field for purchase
    purchase_many_invoice_ids = fields.Many2many('purchase.order', 'purchase_many_account_many2many',
                                          'invoice_id', 'purchase_id',string='Add Many PO')


    #avinash: 06/09/20 Added so only those purchase order visible whose receipt have no vendor
    @api.onchange('partner_id')
    def default_po_with_bill(self):
        po_list = []
        all_po = self.env['purchase.order'].search([('name', 'like', 'PO%'), ('state', '=', 'purchase')])
        for po in all_po:
            all_receipt = self.env['stock.picking'].search([('purchase_id', '=', po.id),('state', 'in', ('done', 'bill_pending')),
                                                            ('receipt_invoiced', '=', False)])
            if all_receipt:
                po_list.append(po.id)

        if po_list and self.partner_id:
            res = {
                'domain': {
                    'purchase_id': [('id', '=', [po for po in po_list]), ('partner_id','=',self.partner_id.id)],
                }
            }
            return res

    # end avinash


    # @api.model
    # def default_get(self, fields):
    #     # add default check on company gst register
    #     res = super(AccountInvoice, self).default_get(fields)
    #     if not self.env.user.company_id.vat:
    #         # if GST not present, company unregistered
    #         if 'check_registered' in fields:
    #             # set tax field invisible
    #             res['check_registered'] = True
    #     return res
        # Gaurav end

    @api.onchange('state', 'partner_id', 'invoice_line_ids')
    def _onchange_allowed_purchase_ids(self):
        '''
        The purpose of the method is to define a domain for the available
        purchase orders.
        '''
        result = {}

        # A PO can be selected only if at least one PO line is not already in the invoice
        purchase_line_ids = self.invoice_line_ids.mapped('purchase_line_id')
        purchase_ids = self.invoice_line_ids.mapped('purchase_id').filtered(lambda r: r.order_line <= purchase_line_ids)

        # Gaurav 4/7/20 added and commented domain to invoice to show all po
        # domain = [('invoice_status', '=', 'to invoice')]
        domain=[]
        # Gaurav end
        if self.partner_id:
            domain += [('partner_id', 'child_of', self.partner_id.id)]
        if purchase_ids:
            domain += [('id', 'not in', purchase_ids.ids)]
        result['domain'] = {'purchase_id': domain}
        return result

    def _prepare_invoice_line_from_po_line(self, line):
        po_line = line
        if line.product_id.purchase_method == 'purchase':
            qty = line.product_qty - line.qty_invoiced
        else:
            qty = line.qty_received - line.qty_invoiced
        if float_compare(qty, 0.0, precision_rounding=line.product_uom.rounding) <= 0:
            qty = 0.0
        taxes = line.taxes_id
        invoice_line_tax_ids = line.order_id.fiscal_position_id.map_tax(taxes)
        invoice_line = self.env['account.invoice.line']

        data = {
            'purchase_line_id': line.id,
            'name': line.order_id.name+': '+line.name,
            'origin': line.order_id.origin,
            'uom_id': line.product_uom.id,
            'product_id': line.product_id.id,
            # Aman 22/08/2020 income or expense account must be picked from product or journal
            'account_id': invoice_line.get_invoice_line_account1('in_invoice', line.product_id, line.partner_id, self.env.user.company_id, po_line=po_line) or invoice_line.with_context({'journal_id': self.journal_id.id, 'type': 'in_invoice'})._default_account(),
            'price_unit': line.order_id.currency_id.with_context(date=self.date_invoice).compute(line.price_unit, self.currency_id, round=False),
            'quantity': qty,
            'discount': line.discount or 0.0,
            'account_analytic_id': line.account_analytic_id.id,
            'analytic_tag_ids': line.analytic_tag_ids.ids,
            'invoice_line_tax_ids': invoice_line_tax_ids.ids
        }
        # Aman 22/08/2020 Commented account because income or expense account must be picked from product or journal are defined above
        # account = invoice_line.get_invoice_line_account('in_invoice', line.product_id, line.order_id.fiscal_position_id, self.env.user.company_id)
        # if account:
        #     data['account_id'] = account.id
        return data

    def _onchange_product_id(self):
        domain = super(AccountInvoice, self)._onchange_product_id()
        if self.purchase_id:
            # Use the purchase uom by default
            self.uom_id = self.product_id.uom_po_id
        return domain

    # Load all unsold PO lines
    @api.onchange('purchase_id')
    def purchase_order_change(self):
        print("purchase onchange xxxxx", self.purchase_id, self.purchase_id.name)
        if not self.purchase_id:
            return {}
        if not self.partner_id:
            self.partner_id = self.purchase_id.partner_id.id

        vendor_ref = self.purchase_id.partner_ref
        if vendor_ref and (not self.reference or (
                vendor_ref + ", " not in self.reference and not self.reference.endswith(vendor_ref))):
            self.reference = ", ".join([self.reference, vendor_ref]) if self.reference else vendor_ref

        new_lines = self.env['account.invoice.line']
        for line in self.purchase_id.order_line - self.invoice_line_ids.mapped('purchase_line_id'):
            data = self._prepare_invoice_line_from_po_line(line)
            new_line = new_lines.new(data)
            new_line._set_additional_fields(self)
            new_lines += new_line

        self.invoice_line_ids += new_lines
        self.payment_term_id = self.purchase_id.payment_term_id
        self.env.context = dict(self.env.context, from_purchase_order_change=True)

        # --------------Gaurav 19/6/20 adding all po in add many po field----
        self.purchase_many_invoice_ids += self.purchase_id
        # ----- Gaurav 19/6/20 adding all receipt of po
        search_receipt=''
        if self.purchase_id:
            search_receipt = self.env['stock.picking'].search([
                ('origin', '=', self.purchase_id.name), ('state','in', ('done','bill_pending')),('receipt_invoiced', '=', False)])
            print("search_receiptxxx onchng", search_receipt, self.picking_receipt_id)
        self.picking_receipt_id += search_receipt
        # --------------- Gaurav end
        if self.picking_receipt_id:
            self.reference = self.picking_receipt_id[0].invoice_no
            self.date_invoice = self.picking_receipt_id[0].delivery_invoice_date
        self.purchase_id = False
        return {}

    @api.onchange('currency_id')
    def _onchange_currency_id(self):
        if self.currency_id:
            for line in self.invoice_line_ids.filtered(lambda r: r.purchase_line_id):
                line.price_unit = line.purchase_id.currency_id.with_context(date=self.date_invoice).compute(line.purchase_line_id.price_unit, self.currency_id, round=False)

    @api.onchange('invoice_line_ids')
    def _onchange_origin(self):
        purchase_ids = self.invoice_line_ids.mapped('purchase_id')
     
        if purchase_ids:
            self.origin = ', '.join(purchase_ids.mapped('name'))

    @api.onchange('partner_id', 'company_id')
    def _onchange_partner_id(self):
        payment_term_id = self.env.context.get('from_purchase_order_change') and self.payment_term_id or False
        res = super(AccountInvoice, self)._onchange_partner_id()
        if payment_term_id:
            self.payment_term_id = payment_term_id
        if not self.env.context.get('default_journal_id') and self.partner_id and self.currency_id and\
                self.type in ['in_invoice', 'in_refund'] and\
                self.currency_id != self.partner_id.property_purchase_currency_id:
            journal_domain = [
                ('type', '=', 'purchase'),
                ('company_id', '=', self.company_id.id),
                ('currency_id', '=', self.partner_id.property_purchase_currency_id.id),
            ]
            default_journal_id = self.env['account.journal'].search(journal_domain, limit=1)
            if default_journal_id:
                self.journal_id = default_journal_id
        return res

    @api.model
    def invoice_line_move_line_get(self):
        res = super(AccountInvoice, self).invoice_line_move_line_get()

        if self.env.user.company_id.anglo_saxon_accounting:
            if self.type in ['in_invoice', 'in_refund']:
                for i_line in self.invoice_line_ids:
                    res.extend(self._anglo_saxon_purchase_move_lines(i_line, res))
        return res

    @api.model
    def _anglo_saxon_purchase_move_lines(self, i_line, res):
        """Return the additional move lines for purchase invoices and refunds.

        i_line: An account.invoice.line object.
        res: The move line entries produced so far by the parent move_line_get.
        """
        inv = i_line.invoice_id
        company_currency = inv.company_id.currency_id
        invoice_currency = inv.currency_id
        if i_line.product_id and i_line.product_id.valuation == 'real_time' and i_line.product_id.type == 'product':
            # get the fiscal position
            fpos = i_line.invoice_id.fiscal_position_id
            # get the price difference account at the product
            acc = i_line.product_id.property_account_creditor_price_difference
            if not acc:
                # if not found on the product get the price difference account at the category
                acc = i_line.product_id.categ_id.property_account_creditor_price_difference_categ
            acc = fpos.map_account(acc).id
            # reference_account_id is the stock input account
            reference_account_id = i_line.product_id.product_tmpl_id.get_product_accounts(fiscal_pos=fpos)['stock_input'].id
            diff_res = []
            # calculate and write down the possible price difference between invoice price and product price
            for line in res:
                if line.get('invl_id', 0) == i_line.id and reference_account_id == line['account_id']:
                    # Do not forward port in >= saas-11.3. PR #32616 takes care of it
                    # Standard price is in company currency
                    valuation_price_unit = i_line.product_id.uom_id._compute_price(i_line.product_id.standard_price, i_line.uom_id)
                    currency_valuation_price_unit = company_currency
                    if i_line.product_id.cost_method != 'standard' and i_line.purchase_line_id:
                        #for average/fifo/lifo costing method, fetch real cost price from incomming moves
                        stock_move_obj = self.env['stock.move']
                        valuation_stock_move = stock_move_obj.search([
                            ('purchase_line_id', '=', i_line.purchase_line_id.id),
                            ('state', '=', 'done'), ('product_qty', '!=', 0.0)
                        ])
                        if self.type == 'in_refund':
                            valuation_stock_move = valuation_stock_move.filtered(lambda m: m._is_out())
                        elif self.type == 'in_invoice':
                            valuation_stock_move = valuation_stock_move.filtered(lambda m: m._is_in())

                        if valuation_stock_move:
                            valuation_price_unit_total = 0
                            valuation_total_qty = 0
                            for val_stock_move in valuation_stock_move:
                                valuation_price_unit_total += abs(val_stock_move.price_unit) * val_stock_move.product_qty
                                valuation_total_qty += val_stock_move.product_qty

                            # in Stock Move, price unit is in company_currency
                            valuation_price_unit = valuation_price_unit_total / valuation_total_qty
                            valuation_price_unit = i_line.product_id.uom_id._compute_price(valuation_price_unit, i_line.uom_id)
                        else:
                            # PO unit price might be in another currency
                            valuation_price_unit = i_line.purchase_line_id.product_uom._compute_price(i_line.purchase_line_id.price_unit, i_line.uom_id)
                            currency_valuation_price_unit = i_line.purchase_line_id.order_id.currency_id

                    # Put the valuation price unit in the invoice currency
                    if invoice_currency != currency_valuation_price_unit:
                        valuation_price_unit_invoice_currency = (
                            currency_valuation_price_unit
                            .with_context(date=inv.date_invoice)
                            .compute(valuation_price_unit, invoice_currency, round=False)
                        )
                    else:
                        valuation_price_unit_invoice_currency = valuation_price_unit

                    # Valuation price unit and i_line.price_unit in invoice currency
                    # A safe assumption is that line['price_unit'] and i_line.price_unit both in the currency of the invoice, foreign or not
                    if (
                        acc and
                        float_compare(line['price_unit'], i_line.price_unit, precision_rounding=invoice_currency.rounding) == 0 and
                        float_compare(valuation_price_unit_invoice_currency, i_line.price_unit, precision_rounding=invoice_currency.rounding) != 0
                    ):
                        # price with discount and without tax included
                        price_unit = i_line.price_unit * (1 - (i_line.discount or 0.0) / 100.0)
                        tax_ids = []
                        if line['tax_ids']:
                            #line['tax_ids'] is like [(4, tax_id, None), (4, tax_id2, None)...]
                            taxes = self.env['account.tax'].browse([x[1] for x in line['tax_ids']])
                            price_unit = taxes.compute_all(price_unit, currency=invoice_currency, quantity=1.0)['total_excluded']
                            for tax in taxes:
                                tax_ids.append((4, tax.id, None))
                                for child in tax.children_tax_ids:
                                    if child.type_tax_use != 'none':
                                        tax_ids.append((4, child.id, None))

                        price_before = line.get('price', 0.0)
                        line.update({'price': invoice_currency.round(valuation_price_unit_invoice_currency * line['quantity'])})
                        diff_res.append({
                            'type': 'src',
                            'name': i_line.name[:64],
                            'price_unit': invoice_currency.round(price_unit - valuation_price_unit_invoice_currency),
                            'quantity': line['quantity'],
                            'price': invoice_currency.round(price_before - line.get('price', 0.0)),
                            'account_id': acc,
                            'product_id': line['product_id'],
                            'uom_id': line['uom_id'],
                            'account_analytic_id': line['account_analytic_id'],
                            'tax_ids': tax_ids,
                            })
            return diff_res
        return []

    @api.model
    def create(self, vals):
        # avinash: 01/10/20 Added to so that if vendor bill is created for a receipt it do not so again
        receipts = vals.get('picking_receipt_id')
        if receipts:
            for recept in receipts[-1][-1]:
                pick = self.env['stock.picking'].search([('id', '=', recept)])
                pick.update({'receipt_invoiced': True})
        # end avinash
        invoice = super(AccountInvoice, self).create(vals)
        purchase = invoice.invoice_line_ids.mapped('purchase_line_id.order_id')
        if purchase and not invoice.refund_invoice_id:
            message = _("This vendor bill has been created from: %s") % (",".join(["<a href=# data-oe-model=purchase.order data-oe-id="+str(order.id)+">"+order.name+"</a>" for order in purchase]))
            invoice.message_post(body=message)
        return invoice

    @api.multi
    def write(self, vals):
        result = True
        for invoice in self:
            purchase_old = invoice.invoice_line_ids.mapped('purchase_line_id.order_id')
            result = result and super(AccountInvoice, invoice).write(vals)
            purchase_new = invoice.invoice_line_ids.mapped('purchase_line_id.order_id')
            #To get all po reference when updating invoice line or adding purchase order reference from vendor bill.
            purchase = (purchase_old | purchase_new) - (purchase_old & purchase_new)
            if purchase:
                message = _("This vendor bill has been modified from: %s") % (",".join(["<a href=# data-oe-model=purchase.order data-oe-id="+str(order.id)+">"+order.name+"</a>" for order in purchase]))
                invoice.message_post(body=message)
        return result



class AccountInvoiceLine(models.Model):
    """ Override AccountInvoice_line to add the link to the purchase order line it is related to"""
    _inherit = 'account.invoice.line'

    purchase_line_id = fields.Many2one('purchase.order.line', 'Purchase Order Line', ondelete='set null', index=True, readonly=True)
    purchase_id = fields.Many2one('purchase.order', related='purchase_line_id.order_id',
                                  string='Purchase Order', store=False, readonly=True, related_sudo=False,
                                  help='Associated Purchase Order. Filled in automatically when a PO is chosen on the vendor bill.')
    invoice_line_tax_ids = fields.Many2many('account.tax',
                                            'account_invoice_line_tax', 'invoice_line_id', 'tax_id',
                                            string='Taxes',
                                            domain=[('type_tax_use', '!=', 'none'), '|', ('active', '=', False),
                                                    ('active', '=', True)], oldname='invoice_line_tax_id')



    # Gaurav 13/3/20 commented and added GST validation code for RFQ and purchase order

    # def _compute_purchase_tax(self):
    #
    #     # Getting default taxes
    #     fpos = self.purchase_id.fiscal_position_id
    #     if self.env.uid == SUPERUSER_ID:
    #         print("super")
    #         if self.invoice_id.type in ('out_invoice', 'out_refund'):
    #             taxes_id = self.product_id.taxes_id or self.account_id.tax_ids
    #             print("if out invoice refund tax id")
    #             account_type='sale'
    #         else:
    #             taxes_id = self.product_id.supplier_taxes_id or self.account_id.tax_ids
    #             print("else supplier")
    #             account_type = 'purchase'
    #         company_id = self.env.user.company_id.id
    #         # taxes_id = fpos.map_tax(
    #         #     self.product_id.supplier_taxes_id.filtered(lambda r: r.company_id.id == company_id))
    #
    #         print("self.taxes_iddddddd", taxes_id, self.partner_id.id)
    #         taxes_ids_list = taxes_id.ids
    #
    #         # Gaurav 12/3/20 added code for default tax state wise
    #         check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
    #         check_custmr_state = self.env['res.partner'].search(
    #             [('id', '=', self.partner_id.id), ('company_id', '=', self.env.user.company_id.id)])
    #         print("checkingggggggggggg", check_custmr_state.state_id, check_cmpy_state.state_id)
    #
    #         if check_cmpy_state.state_id == check_custmr_state.state_id:
    #             print("same state inherit")
    #             self.env.cr.execute(
    #                 """ select id from account_tax where active=True and type_tax_use='%s' AND tax_group_id not in (2,3) and company_id='%s'""" % (account_type,self.env.user.company_id.id,))
    #             csgst_taxes = self.env.cr.dictfetchall()
    #             print("purchase account csgst_taxesvvvvvvvvvvvvvvvv inherit ..", csgst_taxes)
    #             # final = [taxes_ids_list.remove(val.get('id')) for val in csgst_taxes if val.get('id') in taxes_ids_list if csgst_taxes]
    #             tax_list = []
    #             tax_id_list = [tax.id for tax in taxes_id]
    #             if csgst_taxes:
    #                 for val in csgst_taxes:
    #                     tax_detail_id = val.get('id')
    #                     tax_list.append(tax_detail_id)
    #                     print("tax_list",tax_list)
    #
    #             for value in tax_id_list:
    #                 if value in tax_list:
    #                     tax_id_list.remove(value)
    #                     print("tax", tax_id_list)
    #             print("tax_id_list same ...", tax_id_list)
    #             self.invoice_line_tax_ids = tax_id_list
    #             print("self.invoice_line_tax_ids same ...", self.invoice_line_tax_ids)
    #             # print("finalvvvvvvvvvvvvvvvv", final)
    #             # self.taxes_id = taxes_ids_list
    #
    #         elif check_cmpy_state.state_id != check_custmr_state.state_id:
    #             print("diff state")
    #             self.env.cr.execute(
    #                 """ select id from account_tax where active=True and type_tax_use='purchase' AND tax_group_id!=4 and company_id='%s'""" % (
    #                     self.env.user.company_id.id,))
    #             igst_taxes = self.env.cr.dictfetchall()
    #             # final = [taxes_ids_list.remove(val.get('id')) for val in igst_taxes if val.get('id') in taxes_ids_list if igst_taxes]
    #             tax_list = []
    #             tax_id_list = [tax.id for tax in taxes_id]
    #             if igst_taxes:
    #                 for val in igst_taxes:
    #                     tax_detail_id = val.get('id')
    #                     tax_list.append(tax_detail_id)
    #
    #             for value in tax_id_list:
    #                 if value in tax_list:
    #                     tax_id_list.remove(value)
    #                     print(tax_id_list)
    #             print("purchase accountt finalvvvvvvvvvvvvvvvv", tax_id_list)
    #
    #             self.invoice_line_tax_ids = tax_id_list
    #
    #         result = {'domain': {'invoice_line_tax_ids': [tax_id_list]}}
    #
    #
    #     else:
    #         print("normal")
    #         taxes_id = fpos.map_tax(self.product_id.supplier_taxes_id)
    #
    #         print("self.taxes_iddddddd", taxes_id)
    #         taxes_ids_list = taxes_id.ids
    #
    #         # Gaurav 12/3/20 added code for default tax state wise
    #         check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
    #         check_custmr_state = self.env['res.partner'].search(
    #             [('id', '=', self.partner_id.id), ('company_id', '=', self.env.user.company_id.id)])
    #         print("checkingggggggggggg", check_custmr_state.state_id, check_cmpy_state.state_id)
    #
    #         if check_cmpy_state.state_id == check_custmr_state.state_id:
    #             print("same state inherit")
    #             self.env.cr.execute(
    #                 """ select id from account_tax where active=True and type_tax_use='purchase' AND tax_group_id not in (2,3) and company_id='%s'""" % (
    #                     self.env.user.company_id.id,))
    #             csgst_taxes = self.env.cr.dictfetchall()
    #             print("csgst_taxesvvvvvvvvvvvvvvvv", csgst_taxes)
    #             # final = [taxes_ids_list.remove(val.get('id')) for val in csgst_taxes if val.get('id') in taxes_ids_list if csgst_taxes]
    #             tax_list = []
    #             tax_id_list = [tax.id for tax in taxes_id]
    #             if csgst_taxes:
    #                 for val in csgst_taxes:
    #                     tax_detail_id = val.get('id')
    #                     tax_list.append(tax_detail_id)
    #
    #             for value in tax_id_list:
    #                 if value in tax_list:
    #                     tax_id_list.remove(value)
    #                     print("tax", tax_id_list)
    #             print("tax id list remaining inhrit", tax_id_list)
    #             self.invoice_line_tax_ids = tax_id_list
    #             print("self.invoice_line_tax_ids",self.invoice_line_tax_ids)
    #             # print("finalvvvvvvvvvvvvvvvv", final)
    #             self.taxes_id = taxes_ids_list
    #             result = {'domain': {'invoice_line_tax_ids': [tax_id_list]}}
    #
    #         elif check_cmpy_state.state_id != check_custmr_state.state_id:
    #             print("diff state inherit")
    #             self.env.cr.execute(
    #                 """ select id from account_tax where active=True and type_tax_use='purchase' AND tax_group_id!=4 and company_id='%s'""" % (
    #                     self.env.user.company_id.id,))
    #             igst_taxes = self.env.cr.dictfetchall()
    #             # final = [taxes_ids_list.remove(val.get('id')) for val in igst_taxes if val.get('id') in taxes_ids_list if igst_taxes]
    #             tax_list = []
    #             tax_id_list = [tax.id for tax in taxes_id]
    #             if igst_taxes:
    #                 for val in igst_taxes:
    #                     tax_detail_id = val.get('id')
    #                     tax_list.append(tax_detail_id)
    #
    #             for value in tax_id_list:
    #                 if value in tax_list:
    #                     tax_id_list.remove(value)
    #                     print(tax_id_list)
    #             print("purchase account tax id list remaining", tax_id_list)
    #
    #             self.invoice_line_tax_ids = tax_id_list
    #
    #             result = {'domain': {'invoice_line_tax_ids': [tax_id_list]}}
    #     return result
    #
    # # Gaurav starts
    # @api.onchange('product_id')
    # def _onchange_product(self):
    #     # result = super(AccountInvoiceLine, self)._onchange_product_id()
    #     result={}
    #     if not self.product_id:
    #         return result
    #
    #     print("self.partner_id.id", self.partner_id.id)
    #
    #     # Gaurav 13/3/20 added validation for GST check (if company is unregistered then don't add taxes if registered then add taxes state wise)
    #     if self.env.user.company_id.vat:
    #         # GST present , company registered
    #         # Gaurav 12/3/20 added code for default tax state wise
    #         check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
    #         check_custmr_state = self.env['res.partner'].search(
    #             [('id', '=', self.partner_id.id), ('company_id', '=', self.env.user.company_id.id)])
    #         # checking company state and customer state is same or not
    #         if check_cmpy_state.state_id == check_custmr_state.state_id:
    #             print("same state inherit....")
    #             # if same states show taxes like CGST SGST GST
    #             self.env.cr.execute(
    #                 """select id from account_tax where active=True and type_tax_use='sale' and tax_group_id!=4 and company_id='%s'""" % (
    #                     self.env.user.company_id.id,))
    #             csgst_taxes = self.env.cr.dictfetchall()
    #             print("purchase account csgst_taxessssss inherit working same", csgst_taxes)
    #             # self._set_taxes()
    #             self._compute_purchase_tax()
    #             cs_tax_list = []
    #             if csgst_taxes:
    #                 for val in csgst_taxes:
    #                     tax_detail_idcs = val.get('id')
    #                     cs_tax_list.append(tax_detail_idcs)
    #                     print("purchase account cs_tax_listttt same inherit", cs_tax_list)
    #                     # self.update({'tax_id': [(6, 0, cs_tax_list)]})
    #                     result = {'domain': {'invoice_line_tax_ids': [('id', 'in', cs_tax_list)]}}
    #
    #
    #         elif check_cmpy_state.state_id != check_custmr_state.state_id:
    #             # if different states show taxes like IGST
    #             self.env.cr.execute(
    #                 """  select id from account_tax where active=True and type_tax_use='sale' and tax_group_id not in (2,3) and company_id='%s'""" % (
    #                     self.env.user.company_id.id,))
    #             igst_taxes = self.env.cr.dictfetchall()
    #             # self._set_taxes()
    #             self._compute_purchase_tax()
    #             i_tax_list = []
    #             if igst_taxes:
    #                 for val in igst_taxes:
    #                     tax_detail_idi = val.get('id')
    #                     i_tax_list.append(tax_detail_idi)
    #                     print("i_tax_listtttt inherit diff", i_tax_list)
    #                     result = {'domain': {'invoice_line_tax_ids': [('id', 'in', i_tax_list)]}}
    #
    #     # self._suggest_quantity()
    #     # self._onchange_quantity()
    #     print("purchase account result",result)
    #     # result = {'domain': {'invoice_line_tax_ids': [('id', '=', 1)]}}
    #     # print ("return after settttttttt",result)
    #     return result
    # Gaurav end