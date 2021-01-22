# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import uuid

from num2words import num2words
from odoo.addons.purchase.models.purchase import PurchaseOrder
from odoo.addons.account.models import genric
from collections import Counter
from itertools import groupby
from datetime import datetime, timedelta, date
from werkzeug.urls import url_encode

from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError, AccessError, ValidationError
from odoo.osv import expression
from odoo.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT

from odoo.tools.misc import formatLang

from odoo.addons import decimal_precision as dp
from odoo.addons.sale_ext.models import sale_ext_inv_adj

class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Quotation"
    _order = 'id desc'

    # Yash START 29/12/2020 : code for print purchase invoice
    def _get_tax_items(self):
        """
        Get tax items and aggregated amount
        :return:
        """
        taxes_dict = {}
        for line in self.order_line:
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
        if self.manufacturnig_end_date:
            delivery_date = datetime.strptime(self.manufacturnig_end_date, "%Y-%m-%d").date()
            order_date = datetime.strptime(self.date_order, "%Y-%m-%d %H:%M:%S").date()
            delta = delivery_date - order_date
            delivery_days = delta.days or 0
        return delivery_days

    # Yash END 29/12/2020 : code for print purchase invoice

    # @api.depends('order_line.price_total')
    @api.depends('order_line')
    def _amount_all(self):
        """
        Compute the total amounts of the SO.
        """
        for order in self:
            amount_untaxed = amount_tax = 0.0
            for line in order.order_line:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            order.update({
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'amount_total': amount_untaxed + amount_tax,
            })

    @api.depends('state', 'order_line.invoice_status')
    def _get_invoiced(self):
        """
        Compute the invoice status of a SO. Possible statuses:
        - no: if the SO is not in status 'sale' or 'done', we consider that there is nothing to
          invoice. This is also hte default value if the conditions of no other status is met.
        - to invoice: if any SO line is 'to invoice', the whole SO is 'to invoice'
        - invoiced: if all SO lines are invoiced, the SO is invoiced.
        - upselling: if all SO lines are invoiced or upselling, the status is upselling.

        The invoice_ids are obtained thanks to the invoice lines of the SO lines, and we also search
        for possible refunds created directly from existing invoices. This is necessary since such a
        refund is not directly linked to the SO.
        """
        # Ignore the status of the deposit product
        deposit_product_id = self.env['sale.advance.payment.inv']._default_product_id()
        line_invoice_status_all = [(d['order_id'][0], d['invoice_status']) for d in self.env['sale.order.line'].read_group([('order_id', 'in', self.ids), ('product_id', '!=', deposit_product_id.id)], ['order_id', 'invoice_status'], ['order_id', 'invoice_status'], lazy=False)]
        for order in self:
            invoice_ids = order.order_line.mapped('invoice_lines').mapped('invoice_id').filtered(lambda r: r.type in ['out_invoice', 'out_refund'])
            # Search for invoices which have been 'cancelled' (filter_refund = 'modify' in
            # 'account.invoice.refund')
            # use like as origin may contains multiple references (e.g. 'SO01, SO02')
            refunds = invoice_ids.search([('origin', 'like', order.name), ('company_id', '=', order.company_id.id), ('type', 'in', ('out_invoice', 'out_refund'))])
            invoice_ids |= refunds.filtered(lambda r: order.name in [origin.strip() for origin in r.origin.split(',')])

            # Search for refunds as well
            domain_inv = expression.OR([
                ['&', ('origin', '=', inv.number), ('journal_id', '=', inv.journal_id.id)]
                for inv in invoice_ids if inv.number
            ])
            if domain_inv:
                refund_ids = self.env['account.invoice'].search(expression.AND([
                    ['&', ('type', '=', 'out_refund'), ('origin', '!=', False)], 
                    domain_inv
                ]))
            else:
                refund_ids = self.env['account.invoice'].browse()

            line_invoice_status = [d[1] for d in line_invoice_status_all if d[0] == order.id]

            if order.state not in ('sale', 'done'):
                invoice_status = 'no'
            elif any(invoice_status == 'to invoice' for invoice_status in line_invoice_status):
                invoice_status = 'to invoice'
            elif all(invoice_status == 'invoiced' for invoice_status in line_invoice_status):
                invoice_status = 'invoiced'
            elif all(invoice_status in ['invoiced', 'upselling'] for invoice_status in line_invoice_status):
                invoice_status = 'upselling'
            else:
                invoice_status = 'no'

            order.update({
                'invoice_count': len(set(invoice_ids.ids + refund_ids.ids)),
                'invoice_ids': invoice_ids.ids + refund_ids.ids,
                'invoice_status': invoice_status
            })

    @api.model
    def get_empty_list_help(self, help):
        if help and help.find("oe_view_nocontent_create") == -1:
            return '<p class="oe_view_nocontent_create">%s</p>' % (help)
        return super(SaleOrder, self).get_empty_list_help(help)

    def _get_default_access_token(self):
        return str(uuid.uuid4())

    @api.model
    def _default_note(self):
        return self.env['ir.config_parameter'].sudo().get_param('sale.use_sale_note') and self.env.user.company_id.sale_note or ''

    @api.model
    def _get_default_team(self):
        return self.env['crm.team']._get_default_team_id()

    @api.onchange('fiscal_position_id')
    def _compute_tax_id(self):
        """
        Trigger the recompute of the taxes if the fiscal position is changed on the SO.
        """
        for order in self:
            order.order_line._compute_tax_id()

    @api.multi
    def _get_payment_type(self):
        self.ensure_one()
        return 'form'

    # Gaurav 19feb20 edit for Options:stock to increase on sales order

    @api.depends('options_stock')
    def compute_options_stock(self):

        for data in self:
            if data.options_stock == "stock_sales_order":
                print("oprion_check-------", self.options_stock)

                data.check_option_stock = True

            else:

                data.check_option_stock = False

    # Gaurav end

    # Piyush: code to count amendment when type is arc on 08-05-2020
    @api.multi
    @api.depends('order_amd_ids')
    def _compute_amendment_count(self):
        for amd in self:
            amd.amendment_count = len(amd.order_amd_ids)
    # code ends here

        # Piyush: code for opening amendment wizard on 21-06-2020

    def get_current_amendment_history(self):
        """Get Current Form Agreement Ammendmend History"""
        result = {}
        all_order_amd_ids = []
        company_id = self.env.user.company_id.id
        all_order_amd = self.env['sale.order.amd'].search(
            [('id', 'in', self.order_amd_ids and self.order_amd_ids.ids or []),
             ('company_id', '=', company_id)])
        if all_order_amd:
            all_order_amd_ids = all_order_amd.ids
        action = self.env.ref('sale.action_sale_order_amd')
        result = action.read()[0]
        res = self.env.ref('sale.sale_order_amd_tree_view', False)
        res_form = self.env.ref('sale.sale_order_amd_form_view', False)
        result['views'] = [(res and res.id or False, 'list'), (res_form and res_form.id or False, 'form')]
        result['domain'] = [('id', 'in', tuple(all_order_amd_ids))]
        result['target'] = 'current'
        result['view_type'] = 'tree'
        result['view_mode'] = 'tree,form'
        return result

        # code ends here

    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        if self.warehouse_id.company_id:
            self.company_id = self.warehouse_id.company_id.id

    @api.multi
    def action_view_scheduling(self):
        """This function returns an action that display existing scheduling orders
        of given sales order ids. It can either be a in a list or in a form
        view, if there is only one Scheduled order to show."""
        action = self.env.ref('sale.action_sale_order_scheduling_new').read()[0]
        scheduling = self.mapped('scheduling_ids')
        if len(scheduling) > 1:
            action['context'] = {
                'default_sale_id': self.id
            }
            action['domain'] = [('id', 'in', scheduling.ids)]
        elif scheduling:
            action['context'] = {
                'default_sale_id': self.id
            }
            action['domain'] = [('id', 'in', scheduling.ids)]
            action['views'] = [(self.env.ref('sale.sale_order_scheduling_form').id, 'form')]
            action['res_id'] = scheduling.id
        elif len(scheduling) < 1:
            action['context'] = {
                'default_sale_id': self.id
            }
            action['domain'] = [('id', 'in', scheduling.ids)]
        return action

    #avinash:05/09/20 Commented because need to hide scheduling smart button (invisible while scheduling button is not checked
    # or sale order type is not open)
    # @api.multi
    # def scheduling_button_visibility(self):
    #     show_visible = False
    #     if self.check_scheduled or self.so_type == 'open_order':
    #         show_visible = True
    #     self.show_visible = show_visible

    @api.onchange('check_scheduled', 'so_type')
    def scheduling_button_visibility(self):
        show_visible = False
        if self.check_scheduled or self.so_type == 'open_order':
            show_visible = True
        self.show_visible = show_visible
    # end avinash

    @api.depends('scheduling_ids')
    def _compute_scheduling_ids(self):
        for order in self:
            order.scheduling_count = len(order.scheduling_ids)
    # code ends here

    # Aman 15/09/2020 Created this function to check mto products
    def check_mrp_mod(self, line):
        mfg_installed = self.env['ir.module.module'].search([('name', '=', 'mrp')])
        if not mfg_installed or mfg_installed.state != 'installed' or self.mfg_exist == False:
            if line:
                mto = line
                mto_exist = mto.filtered(lambda mto: mto.product_id.route_ids.name == 'Make To Order')
                return mto_exist

    # Aman 16/09/2020 Created this function to check stock status
    def check_stock_status(self, mto_exist):
        if mto_exist:
            for i in mto_exist:
                if i.pending_quantity > 0:
                    status = 'update'        # Update Pending
                else:
                    status = 'no_update'     # Updated
                return status

    # Aman 12/09/2020 added onchange function to set check_pending_qty value to update or not update on basis of pending qty
    @api.onchange('order_line')
    def _compute_pending_qty(self):
        mto_exist = self.check_mrp_mod(self.order_line)
        status = self.check_stock_status(mto_exist)
        self.check_pending_qty = status
    # Aman end

    # Aman 16/09/2020 Added this function because it is called when we open main tree view
    def get_tree_view(self):
        """
        Used to return tree view for mrp or no mrp database
        """
        mfg_installed = self.env['ir.module.module'].search([('name', '=', 'mrp')])
        if not mfg_installed or mfg_installed.state != 'installed':
            tree_view = self.env.ref('sale.view_order_tree_no_mrp', False)
        else:
            tree_view = self.env.ref('sale.view_order_tree', False)
        action = self.env.ref('sale.action_orders')
        result = action.read()[0]
        res = tree_view
        res_form = self.env.ref('sale.view_order_form', False)
        result['type'] = 'ir.actions.act_window'
        result['views'] = [(res and res.id or False, 'list'), (res_form and res_form.id or False, 'form')]
        result['target'] = 'main'
        return result
    # Aman end


    name = fields.Char(string='Order Reference', required=True, copy=False, readonly=True, states={'draft': [('readonly', False)]}, index=True, default=lambda self: _('New'))
    origin = fields.Char(string='Source Document', help="Reference of the document that generated this sales order request.")
    client_order_ref = fields.Char(string='Customer Reference', copy=False)
    #avinash:05/09/20 Commented because compute field is not working properly so use onchange instead of compute
    # Piyush: code for adding show_visible to make scheduling smart button visible and invisible on 14-07-2020
    # show_visible = fields.Boolean(compute='scheduling_button_visibility', string="Schedule button visibility", default=False)
    show_visible = fields.Boolean(string="Schedule button visibility", default=False)
    # end avinash
    #requisition_id = fields.Many2one('sale.requisition', string='Agreement No')
    # Piyush: code for adding new fields on 23-06-2020
    scheduling_ids = fields.One2many('sale.order.scheduling', 'sale_id', string='Scheduling')
    scheduling_count = fields.Integer(string='Scheduled Orders', compute='_compute_scheduling_ids')
    dispatch_ids = fields.One2many('stock.picking', 'sale_id', string="Dispatch Id")
    # Piyush: code for adding agreement start and end date on 14-07-2020
    agreement_start_date = fields.Date(string="Agreement Start Date", readonly=True, index=True,
                                       help="Date on which agreement started.")
    agreement_end_date = fields.Date(string="Agreement End Date", readonly=True, index=True,
                                     help="Date on which agreement ends.")
    # Piyush: code added for making reference quotation new many2one from sale quotation model on 20-06-2020
    reference_quot = fields.Many2one('sale.quotation', string="Reference Quotation")
    # Piyush: field added for amendment on 21-06-2020
    amendment_count = fields.Integer(compute='_compute_amendment_count', string='Number of Amendment')
    order_amd_ids = fields.One2many('sale.order.amd', 'order_amd_id',
                                    string='Sale Order Amendment', readonly=True)
    # code ends here
    access_token = fields.Char(
        'Security Token', copy=False,
        default=_get_default_access_token)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('sale', 'Sales Order'),
        ('done', 'Locked'),
        ('closed', 'Short Close'),
        ('cancel', 'Cancelled'),
        ('lost', 'Lost Order'),
        ], string='Status', readonly=True, copy=False, index=True, track_visibility='onchange', default='draft')
    date_order = fields.Datetime(string='Order Date', required=True, readonly=True, index=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, copy=False, default=fields.Datetime.now)
    validity_date = fields.Date(string='Expiration Date', readonly=True, copy=False, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},
        help="Manually set the expiration date of your quotation (offer), or it will set the date automatically based on the template if online quotation is installed.")
    is_expired = fields.Boolean(compute='_compute_is_expired', string="Is expired")
    create_date = fields.Datetime(string='Creation Date', readonly=True, index=True, help="Date on which sales order is created.")
    confirmation_date = fields.Datetime(string='Confirmation Date', readonly=True, index=True, help="Date on which the sales order is confirmed.", oldname="date_confirm", copy=False)
    user_id = fields.Many2one('res.users', string='Salesperson', index=True, track_visibility='onchange', default=lambda self: self.env.user)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, required=True, change_default=True, index=True, track_visibility='always', store=True)
    partner_invoice_id = fields.Many2one('res.partner', string='Invoice Address', readonly=True, required=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, store=True, help="Invoice address for current sales order.")
    partner_shipping_id = fields.Many2one('res.partner', string='Delivery Address', readonly=True, required=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, store=True, help="Delivery address for current sales order.")
    # Himanshu SO 2-12-2020 added the address field to show the address of the customer
    address = fields.Text(string="Address", readonly=True)
    # End Himanshu
    # Piyush: code for making pricelist required = False on 22-06-2020
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist', readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, help="Pricelist for current sales order.")
    currency_id = fields.Many2one("res.currency", related='pricelist_id.currency_id', string="Currency", readonly=True, required=True)
    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account', readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, help="The analytic account related to a sales order.", copy=False, oldname='project_id')

    order_line = fields.One2many('sale.order.line', 'order_id', string='Order Lines', states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}, copy=True, auto_join=True)

    invoice_count = fields.Integer(string='# of Invoices', compute='_get_invoiced', readonly=True)
    invoice_ids = fields.Many2many("account.invoice", string='Invoices', compute="_get_invoiced", readonly=True, copy=False)
    invoice_status = fields.Selection([
        ('upselling', 'Upselling Opportunity'),
        ('invoiced', 'Fully Invoiced'),
        ('to invoice', 'To Invoice'),
        ('no', 'Nothing to Invoice')
        ], string='Invoice Status', compute='_get_invoiced', store=True, readonly=True)

    note = fields.Text('Terms and conditions', default=_default_note)

    amount_untaxed = fields.Monetary(string='Untaxed Amount', store=True, readonly=True, compute='_amount_all', track_visibility='onchange')
    amount_tax = fields.Monetary(string='Taxes', store=True, readonly=True, compute='_amount_all')
    amount_total = fields.Monetary(string='Total', store=True, readonly=True, compute='_amount_all', track_visibility='always')

    payment_term_id = fields.Many2one('account.payment.term', string='Payment Terms', oldname='payment_term')
    fiscal_position_id = fields.Many2one('account.fiscal.position', oldname='fiscal_position', string='Fiscal Position')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('sale.order'))
    team_id = fields.Many2one('crm.team', 'Sales Channel', change_default=True, default=_get_default_team, oldname='section_id')

    product_id = fields.Many2one('product.product', related='order_line.product_id', string='Product')

    # ravi start at 6/2/2020 for adding a new field for duration end date
    manufacturnig_end_date = fields.Date(string='Manufacturing Date')
    no_of_days_manu = fields.Float(string='No Of Days')
    # ravi end

    # Gaurav 19feb20 edit for Options:stock to increase on sales order

    options_stock = fields.Selection([
        ('stock_sales_order', 'Stocks to increase on sales order'),
        ('xyz', 'XYZ'),
    ], string='Stock Options')


    check_option_stock = fields.Boolean("Check Option Stock", compute="compute_options_stock", default=False)
    # Gaurav 11/3/20 added check register for checking and show tax field
    # check_registered = fields.Boolean("Check Registered", compute="_check_registered_tax")
    # produced_quantity = fields.Integer("Produced Quantity")
    # pending_quantity = fields.Integer("Pending Quantity")

    # Gaurav end

    # Gaurav 11/3/20 edit for check register for tax
    check_registered = fields.Boolean("Check Registered", store=True, default=False)
    check_order_line = fields.Boolean("Check Order Line", store=True, default=False)
    # Gaurav end

    # Gaurav 7/4/20 edit for check of as per scheduled
    check_scheduled = fields.Boolean("As per scheduled", store=True, default=False)
    # Gaurav end

    # ravi at 18/4/2019 start
    so_type = fields.Selection([('adhoc', 'Adhoc Order'),('arc', 'Arc'), ('open_order', 'Open Order'),
                                ('direct', 'Direct')], string="Order Type", default="adhoc")
    # salman add domain
    requisition_id = fields.Many2one('sale.requisition', string='Agreement No',
                                     domain=[('state', 'in', ['open', 'done']), ('date_end', '>=', datetime.today())])
    # salman end

    # Aman 12/09/2020 Added field to show stock status at main tree view
    check_pending_qty = fields.Selection([('update', 'Update Pending'), ('no_update', 'Updated')],
                                         help="Use to check pending status", store=True)
    # Aman 29/09/2020 This field is used to make fields readonly when so is created from sale quotation
    check_so_from_sq = fields.Boolean(help="This field is used to make fields readonly when so is created from sale quotation", default=False)
    # Aman end

    order_calculation_ids = fields.One2many('order.calculation.sale', 'order_id', 'Order Calculation Sale Order',
                                            compute='_compute_lines', store=True)
    
    # Yash Start - 18/12/2020 code for print sale order
    remarks = fields.Text('Remarks')
    notes = fields.Text('Notes')
    # Yash End

    #Himanshu So 2-12-2020 function added to add the address related to the customer
    @api.onchange('partner_shipping_id')
    def call_change_delivery_address(self):
        sale_ext_inv_adj.SaleQuotation.change_delivery_address(self)
    #End Himanshu

    #Himanshu SO 2-12-2020 function added to add the address related to the customer
    @api.onchange('partner_id')
    def call_add_delivery_address(self):
        sale_ext_inv_adj.SaleQuotation.add_delivery_address(self)
    #End himanshu


    # Aman 17/10/2020 Added function to calculate values to display on table below products table
    @api.depends('order_line', 'order_line.tax_id')
    def _compute_lines(self):
        tax_dict = {}
        tax = {}
        amt = 0
        bamt = 0
        if self.order_line:
            for line in self.order_line:
                tax_dict = genric.check_line(line, line.tax_id, line.order_id.currency_id, line.order_id.partner_id,
                                             line.product_uom_qty)
                tax = Counter(tax_dict) + Counter(tax)
                # Aman 24/11/2020 Calculated discounted amount to show on table
                if line.product_id:
                    price = line.product_uom_qty * line.price_unit
                    if line.discount:
                        amt += price * (line.discount / 100)
                    bamt += price
                # Aman end
        charges_data_list = genric.detail_table(self, self.order_line, tax, amt, bamt, round_off = False)
        if charges_data_list:
            val = charges_data_list[-1][-1]
            serial_no = val.get('serial_no')
        for mar in self:
            if mar.margin:
                charges_data = (0, False, {
                    "serial_no": serial_no + 1,
                    "label": "Margin",
                    "amount": mar.margin,
                })
                charges_data_list.append(charges_data)
        self.order_calculation_ids = [(5, 0, 0)]
        self.order_calculation_ids = charges_data_list
        for rec in self.order_calculation_ids:
            rec.order_id = self.id
    # @api.multi
    # @api.onchange('order_line')
    # def onchange_order_l(self):
    #     tax_dict = {}
    #     tax = {}
    #     if self.order_line:
    #         for line in self.order_line:
    #             tax_dict = genric.check_line(line, line.tax_id, line.order_id.currency_id, line.order_id.partner_id, line.product_uom_qty)
    #             tax = Counter(tax_dict) + Counter(tax)
    #             print(tax)
    #     charges_data_list = genric.detail_table(self, self.order_line, tax)
    #     self.order_calculation_ids = [(5, 0, 0)]
    #     self.order_calculation_ids = charges_data_list
    # Aman end

    # Gaurav 11/3/20 add default check on company gst register
    # @api.onchange("partner_id")
    # @api.multi
    # def _check_registered_tax(self):
    #     check_reg = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
    #     if check_reg:
    #         if check_reg.vat:
    #             self.check_registered = False
    #         else:
    #             self.check_registered = True

    @api.multi
    def action_lost_order(self):
        genric.state_lost(self)
        # Aman 14/10/2020 Added condition for receptions in state bill pending
        genric.check_dispatch(self)
        # Aman end
        self.mapped('picking_ids').action_cancel()

    @api.model
    def default_get(self, fields):
        # add default check on company gst register
        res = super(SaleOrder, self).default_get(fields)
        if not self.env.user.company_id.vat:
            # if GST not present, company unregistered
            if 'check_registered' in fields:
                # set tax field invisible
                res['check_registered'] = True

        return res
    # Gaurav end
    # check_order_line = fields.Boolean("Check Order Line", store=True, default=False)
    # Gaurav 18/3/20 starts for readonly of customer if there is data in order line
    @api.onchange('order_line')
    def _onchange_order_line(self):
        print("something happened on order line")
        print("There is no line in order line")
        self.check_order_line = False
        for line in self.order_line:
            if line:
                print("There is line in order line")
                self.check_order_line = True

    # Gaurav end

    def _compute_portal_url(self):
        super(SaleOrder, self)._compute_portal_url()
        for order in self:
            order.portal_url = '/my/orders/%s' % (order.id)

    def _compute_is_expired(self):
        now = datetime.now()
        for order in self:
            if order.validity_date and fields.Datetime.from_string(order.validity_date) < now:
                order.is_expired = True
            else:
                order.is_expired = False

    @api.model
    def _get_customer_lead(self, product_tmpl_id):
        return False

    @api.multi
    def unlink(self):
        for order in self:
            if order.state not in ('draft', 'cancel'):
                raise UserError(_('You can not delete a sent quotation or a sales order! Try to cancel it before.'))
        return super(SaleOrder, self).unlink()

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'state' in init_values and self.state == 'sale':
            return 'sale.mt_order_confirmed'
        elif 'state' in init_values and self.state == 'sent':
            return 'sale.mt_order_sent'
        return super(SaleOrder, self)._track_subtype(init_values)

    # Gaurav starts 7/5/20 for Update stock for inventory adjustment
    @api.multi
    def action_update_stock(self):
        # call function inherit sale_ext
        print("mfg_exist")

    # Gaurav starts 19feb20 for Update stock on qty_available (On Hand)
    @api.multi
    def action_update_stock_old(self):
        for value in self.order_line:
            prod_id=value.product_id
            if value.produced_quantity:
                # gaurav commented
                # getting available quantity(on hand quantity) from product.template
                # update_search = self.env['product.template'].search(
                #                 [('id', '=', value.product_id.product_tmpl_id.id)])                #
                # on_hand_quantity = update_search.qty_available + value.produced_quantity

                on_hand_quantity = value.produced_quantity
                print("up111============", on_hand_quantity)
                # getting stock location
                stock_location = self.env['stock.location'].search(
                                   [('name', '=', 'Inventory adjustment')])
                # getting stock destination
                stock_destination = self.env['stock.location'].search(
                    [('name', '=', "Stock"), ('company_id', '=', self.env.user.company_id.id)])
                stlc = stock_location.id
                print("stock_location.location_iddddddddddd",stlc)
                stds = stock_destination.id
                print("stock_location.destinationnnnnnnnnn", stds)
                # making dictionary of required item
                stock_dict = {
                    'product_id':prod_id.id,
                    'product_uom_qty':on_hand_quantity,
                    'quantity_done':on_hand_quantity,
                    'location_id':stlc,
                    'location_dest_id':stds,
                    'state':'draft',
                    'company_id':self.env.user.company_id.id,
                    'name':'inv',
                    'product_uom':prod_id.uom_id.id
                }
                # creating stock_dict values in environment of stock.move.
                move_id=self.env['stock.move'].create(stock_dict)
                if move_id:
                    # if there is value in move_id then call action done function to update stock
                    move_id._action_done()
                    # initialize the produed quantity
                    value.produced_quantity=0
            else:
                # if produced quantity is not entered raise user error
                raise UserError(
                    'Please Enter some Produced Quantity before Updating Stock!!')

    # Gaurav ends



    # Piyush: code for calulating delivery date on 21-06-2020
    @api.multi
    @api.onchange('no_of_days_manu')
    def onchange_no_of_days_manu(self):
        if self.no_of_days_manu > 0:
            last_sale_order_manu_date = datetime.strptime(str(self.date_order), '%Y-%m-%d %H:%M:%S').date()
            self.manufacturnig_end_date = last_sale_order_manu_date + timedelta(days=self.no_of_days_manu)
        elif self.no_of_days_manu == 0:
            self.manufacturnig_end_date = self.date_order

            # code ends here



    @api.multi
    @api.onchange('partner_shipping_id', 'partner_id')
    def onchange_partner_shipping_id(self):
        """
        Trigger the change of fiscal position when the shipping address is modified.
        """
        self.fiscal_position_id = self.env['account.fiscal.position'].get_fiscal_position(self.partner_id.id, self.partner_shipping_id.id)
        return {}

    # Piyush: code for passing default currency for the partner on 23-06-2020
    @api.onchange('partner_id', 'company_id')
    def onchange_partner_id(self):
        if not self.partner_id:
            self.currency_id = False
        else:
            self.currency_id = self.partner_id.property_purchase_currency_id.id or self.env.user.company_id.currency_id.id
    # code ends here

    @api.multi
    @api.onchange('partner_id')
    def onchange_partner_id(self):
        """
        Update the following fields when the partner is changed:
        - Pricelist
        - Payment terms
        - Invoice address
        - Delivery address
        """
        if not self.partner_id:
            self.update({
                'partner_invoice_id': False,
                'partner_shipping_id': False,
                'payment_term_id': False,
                'fiscal_position_id': False,
            })
            return
        # Gaurav 13/3/20 added customer delivery address and invoice address domain
        check_custmr_state_delivery = self.env['res.partner'].search(
            [ ('company_id', '=', self.company_id.id),
             ('type', '=', 'delivery'), ('parent_id', '=', self.partner_id.id)])

        check_custmr_state_invoice = self.env['res.partner'].search(
            [('company_id', '=', self.company_id.id),
             ('type', '=', 'invoice'), ('parent_id', '=', self.partner_id.id)])
        # Gaurav added domain in result

        addr = self.partner_id.address_get(['delivery', 'invoice'])
        values = {
            'pricelist_id': self.partner_id.property_product_pricelist and self.partner_id.property_product_pricelist.id or False,
            'payment_term_id': self.partner_id.property_payment_term_id and self.partner_id.property_payment_term_id.id or False,
            'partner_invoice_id': addr['invoice'],
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
        result = {'domain': {'partner_shipping_id': [('id', 'in', check_custmr_state_delivery.ids)],
                             'partner_invoice_id': [('id', 'in', check_custmr_state_invoice.ids)]
                             }}
        return result
        # Gaurav end

    @api.onchange('partner_id')
    def onchange_partner_id_warning(self):

        for line in self.order_line:
            if line:
                self.check_order_line=True
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
                self.update({'partner_id': False, 'partner_invoice_id': False, 'partner_shipping_id': False, 'pricelist_id': False})
                return {'warning': warning}

        if warning:
            return {'warning': warning}

    # Aman 26/12/2020 Added validations to check if Item without HSN code is last item
    # Aman 08/01/2021 commented the below function
    # @api.onchange('order_line')
    # def onchange_lines(self):
    #     genric.check_hsn_disable(self, self.order_line)
    # Aman end

    @api.model
    def create(self, vals):
        # Aman 8/10/2020 Added a validation to check unit price and product quantity
        if 'order_line' in vals:
            quantity = 'product_uom_qty'
            price = 'price_unit'
            PurchaseOrder.check_price_qty(self, vals, price, quantity)
        # Aman end
        if vals.get('name', _('New')) == _('New'):
            if 'company_id' in vals:
                vals['name'] = self.env['ir.sequence'].with_context(force_company=vals['company_id']).next_by_code('sale.order') or _('New')
            else:
                vals['name'] = self.env['ir.sequence'].next_by_code('sale.order') or _('New')

        # Makes sure partner_invoice_id', 'partner_shipping_id' and 'pricelist_id' are defined
        if any(f not in vals for f in ['partner_invoice_id', 'partner_shipping_id', 'pricelist_id']):
            partner = self.env['res.partner'].browse(vals.get('partner_id'))
            addr = partner.address_get(['delivery', 'invoice'])
            vals['partner_invoice_id'] = vals.setdefault('partner_invoice_id', addr['invoice'])
            vals['partner_shipping_id'] = vals.setdefault('partner_shipping_id', addr['delivery'])
            vals['pricelist_id'] = vals.setdefault('pricelist_id', partner.property_product_pricelist and partner.property_product_pricelist.id)

        # Piyush: code for checking product at the item in SO on 24-06-2020
        ecom_installed = self.env['ir.module.module'].search(
            [('name', '=', 'ecom_integration'), ('state', '=', 'installed')])
        if not ecom_installed:
            if 'order_line' not in vals:
                raise ValidationError(_("Cannot proceed without products at the item level!"))
        # code ends here
        result = super(SaleOrder, self).create(vals)

        # ravi start at 20/1/2019 for overwriting write method to product transaction updation
        # if result.order_line:
        #     for values in result.order_line:
        #         if values.product_id:
        #             product_tmpl_id = values.product_id.product_tmpl_id.id
        #             print('product_tmpl_id', product_tmpl_id)
        #             self.env['product.template'].search([('company_id', '=', result.company_id.id),
        #                                                  ('id', '=', product_tmpl_id)]).write({'product_transaction': True})
        # # ravi end

        return result

    # Piyush: code for amendment function data creation on 21-06-2020

    def _amendment_data(self, amd_name):
        line_data_list = []
        for val in self:
            if val.order_line:
                for line in val.order_line:
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
                        'order_amd_id': line.order_id.id or False,
                        'company_id': line.company_id and line.company_id.id or False,
                    })
                    line_data_list.append(line_data)

            amd_vals = {
                'name': amd_name,
                'origin': val.origin or '',
                'so_type': val.so_type or False,
                # 'enquiry_type': val.enquiry_type or False,
                'order_amd_id': val.id or False,
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
                'expiration_date': val.manufacturnig_end_date or fields.datetime.now(),
                'confirmation_date': val.confirmation_date or fields.datetime.now(),
                'order_line': line_data_list,
            }
            return amd_vals

            # code ends here

    # ravi start at 20/1/2019 for overwriting write method to product transaction updation
    @api.multi
    def write(self, vals):

        # Piyush: code for not allowing to make changes confirmed sale order and mO is in progress state on 27-06-2020
        # Can be modified further if editing of qty field is only to be prohibited in above case
        mfg_installed = self.env['ir.module.module'].search([('name', '=', 'mrp')])
        if mfg_installed.state == 'installed':
            if 'order_line' in vals and self.state == 'sale':
                already_created_mo = self.env['mrp.production'].search([('origin', '=', self.name), ('state', '=', 'progress')])
                if already_created_mo:
                    raise ValidationError(_("Cannot make changes as MO is in progress state!"))
        # code ends here

        # piyush: code for making amd data on 21-06-2020
        amd_name = ''
        if self.order_line:
            amd_count = len(self.order_amd_ids.ids)
            amd_name = 'AMD ' + str(amd_count)
        else:
            amd_name = 'AMD '
        amd_data = self._amendment_data(amd_name)

        result = super(SaleOrder, self).write(vals)

        # Piyush: code for order line check in PO and JO on 26-06-2020
        if 'order_line' in vals:
            if not self.order_line:
                raise ValidationError(_("Cannot proceed without products at the item level!"))
                # code ends here

        # Piyush: code for creating amd on 21-06-2020
        if 'state' not in vals and self.state == 'sale':
            if 'order_line' in vals or 'order_line.product_uom_qty' in vals or 'order_line.price_unit' in vals:
                amd_data['product_uom_qty'] = vals.get('product_uom_qty')
                amd_data['price_unit'] = vals.get('price_unit')
                self.env['sale.order.amd'].create(amd_data)
                # Aman 4/08/2020 State is changed to draft after making changes in SO
                self.update({'state': 'draft'})
                # Aman end
        # code ends here

        if self.order_line:
            for values in self.order_line:
                if values.product_id:

                    product_tmpl_id = values.product_id.product_tmpl_id.id
                    print('product_tmpl_id', product_tmpl_id)
                    self.env['product.template'].search([('company_id', '=', self.company_id.id), ('id', '=', product_tmpl_id)]).write({'product_transaction': True})
        return result
    # ravi end



    @api.multi
    def copy_data(self, default=None):
        if default is None:
            default = {}
        if 'order_line' not in default:
            default['order_line'] = [(0, 0, line.copy_data()[0]) for line in self.order_line.filtered(lambda l: not l.is_downpayment)]
        return super(SaleOrder, self).copy_data(default)

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
        return super(SaleOrder, self).name_get()

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if self._context.get('sale_show_partner_name'):
            if operator in ('ilike', 'like', '=', '=like', '=ilike'):
                domain = expression.AND([
                    args or [],
                    ['|', ('name', operator, name), ('partner_id.name', operator, name)]
                ])
                return self.search(domain, limit=limit).name_get()
        return super(SaleOrder, self).name_search(name, args, operator, limit)

    @api.model_cr_context
    def _init_column(self, column_name):
        """ Initialize the value of the given column for existing rows.

            Overridden here because we need to generate different access tokens
            and by default _init_column calls the default method once and applies
            it for every record.
        """
        if column_name != 'access_token':
            super(SaleOrder, self)._init_column(column_name)
        else:
            query = """UPDATE %(table_name)s
                          SET %(column_name)s = md5(md5(random()::varchar || id::varchar) || clock_timestamp()::varchar)::uuid::varchar
                        WHERE %(column_name)s IS NULL
                    """ % {'table_name': self._table, 'column_name': column_name}
            self.env.cr.execute(query)

    def _generate_access_token(self):
        for order in self:
            order.access_token = self._get_default_access_token()

    @api.multi
    def _prepare_invoice(self):
        """
        Prepare the dict of values to create the new invoice for a sales order. This method may be
        overridden to implement custom invoice generation (making sure to call super() to establish
        a clean extension chain).
        """
        self.ensure_one()
        company_id = self.company_id.id
        journal_id = (self.env['account.invoice'].with_context(company_id=company_id or self.env.user.company_id.id)
            .default_get(['journal_id'])['journal_id'])
        # Piyush: code for adding picking related to dispatch to the invoices so that can be confirmed on 17-07-2020
        # added freeze_account_item_lines, sale id also for making readonly to invoices created from SO
        dispatches_list = []
        dispatches = self.env['stock.picking'].search([('sale_id', '=', self.id), ('state', '=', 'bill_pending')])
        for picking in dispatches:
            dispatches_list.append(picking.id)
        # code ends here
        if not journal_id:
            raise UserError(_('Please define an accounting sales journal for this company.'))
        # Aman 3/11/2020 Get account_id from account.account table using partner_id
        account_id = self.env['account.account'].search([('partner_id', '=', self.partner_id.id)])
        invoice_vals = {
            'name': self.client_order_ref or '',
            'origin': self.name,
            'type': 'out_invoice',
            # 'account_id': self.partner_invoice_id.property_account_receivable_id.id,
            'account_id': account_id.id,
            'partner_id': self.partner_invoice_id.id,
            'partner_shipping_id': self.partner_shipping_id.id,
            'journal_id': journal_id,
            'currency_id': self.pricelist_id.currency_id.id,
            'comment': self.note,
            'payment_term_id': self.payment_term_id.id,
            'fiscal_position_id': self.fiscal_position_id.id or self.partner_invoice_id.property_account_position_id.id,
            'company_id': company_id,
            'user_id': self.user_id and self.user_id.id,
            'team_id': self.team_id.id,
            'dispatch_ids': [(6, 0, dispatches_list)] or [],
            'freeze_account_item_lines': True,
            'sale_id': self.id or False,
            # avinash:02/01/21 Added to send operation type delivery on invoice form
            'picking_type_id': self.env['stock.picking.type'].search(
                [('warehouse_id.company_id', '=', self.env.user.company_id.id), ('name', '=', 'Delivery Orders')]).id,
            # end avinash
        }
        return invoice_vals

    @api.multi
    def print_quotation(self):
        self.filtered(lambda s: s.state == 'draft').write({'state': 'sent'})
        return self.env.ref('sale.action_report_saleorder').report_action(self)

    @api.multi
    def action_view_invoice(self):
        invoices = self.mapped('invoice_ids')
        action = self.env.ref('account.action_invoice_tree1').read()[0]
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', invoices.ids)]
        elif len(invoices) == 1:
            action['views'] = [(self.env.ref('account.invoice_form').id, 'form')]
            action['res_id'] = invoices.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.multi
    def action_invoice_create(self, grouped=False, final=False):
        """
        Create the invoice associated to the SO.
        :param grouped: if True, invoices are grouped by SO id. If False, invoices are grouped by
                        (partner_invoice_id, currency)
        :param final: if True, refunds will be generated if necessary
        :returns: list of created invoices
        """
        inv_obj = self.env['account.invoice']
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        invoices = {}
        references = {}
        invoices_origin = {}
        invoices_name = {}

        for order in self:
            group_key = order.id if grouped else (order.partner_invoice_id.id, order.currency_id.id)
            for line in order.order_line.sorted(key=lambda l: l.qty_to_invoice < 0):
                if float_is_zero(line.qty_to_invoice, precision_digits=precision):
                    continue
                if group_key not in invoices:
                    inv_data = order._prepare_invoice()

                    # dispatch_id = inv_data.get('dispatch_ids')
                    # print(dispatch_id)
                    # for item in dispatch_id:
                    #     print("item", item[2])
                    # print(dispatch_idd)
                    sale_id = inv_data.get('sale_id')

                    invoice_created = self.env['account.invoice'].search([('sale_id', '=', sale_id),
                                                                          ('state', '=', 'draft')])
                    if invoice_created:
                        raise UserError(_("First validate draft invoices for this SO, then create new invoices!"))
                        # raise UserError(_("No pending quantity available for invoice!"))

                    else:
                        invoice = inv_obj.create(inv_data)
                        references[invoice] = order
                        invoices[group_key] = invoice
                        invoices_origin[group_key] = [invoice.origin]
                        invoices_name[group_key] = [invoice.name]
                elif group_key in invoices:
                    if order.name not in invoices_origin[group_key]:
                        invoices_origin[group_key].append(order.name)
                    if order.client_order_ref and order.client_order_ref not in invoices_name[group_key]:
                        invoices_name[group_key].append(order.client_order_ref)

                if line.qty_to_invoice > 0:
                    line.invoice_line_create(invoices[group_key].id, line.qty_to_invoice)
                elif line.qty_to_invoice < 0 and final:
                    line.invoice_line_create(invoices[group_key].id, line.qty_to_invoice)

            if references.get(invoices.get(group_key)):
                if order not in references[invoices[group_key]]:
                    references[invoices[group_key]] |= order

        for group_key in invoices:
            invoices[group_key].write({'name': ', '.join(invoices_name[group_key]),
                                       'origin': ', '.join(invoices_origin[group_key])})

        if not invoices:
            raise UserError(_('There is no invoiceable line.'))

        for invoice in invoices.values():
            invoice.compute_taxes()
            if not invoice.invoice_line_ids:
                raise UserError(_('There is no invoiceable line.'))
            # If invoice is negative, do a refund invoice instead
            if invoice.amount_total < 0:
                invoice.type = 'out_refund'
                for line in invoice.invoice_line_ids:
                    line.quantity = -line.quantity
            # Use additional field helper function (for account extensions)
            for line in invoice.invoice_line_ids:
                line._set_additional_fields(invoice)
            # Necessary to force computation of taxes and cash rounding. In account_invoice, they are triggered
            # by onchanges, which are not triggered when doing a create.
            invoice.compute_taxes()
            invoice._onchange_cash_rounding()
            invoice.message_post_with_view('mail.message_origin_link',
                values={'self': invoice, 'origin': references[invoice]},
                subtype_id=self.env.ref('mail.mt_note').id)
        return [inv.id for inv in invoices.values()]

    @api.multi
    def action_draft(self):
        orders = self.filtered(lambda s: s.state in ['cancel', 'sent'])
        return orders.write({
            'state': 'draft',
        })

    @api.multi
    def action_cancel(self):
        # Piyush: code for checking MO created or not if yes can't cancel without cancelling MO for order on 23-06-2020
        mo_created = self.env['mrp.production'].search([('origin', '=', self.name),
                                                        ('company_id', '=', self.env.user.company_id.id)])
        if mo_created:
            for mo in mo_created:
                if mo.state not in ['cancel']:
                    raise ValidationError(_("Manufacturing Order is created, can not cancel the order! "
                                            "If you want to cancel this Sale Order please cancel the related Manufacturing Order first!"))
                else:
                    return self.write({'state': 'cancel'})
        else:
            return self.write({'state': 'cancel'})
        # code ends here

    @api.multi
    def action_quotation_send(self):
        '''
        This function opens a window to compose an email, with the edi sale template message loaded by default
        '''
        self.ensure_one()
        ir_model_data = self.env['ir.model.data']
        try:
            template_id = ir_model_data.get_object_reference('sale', 'email_template_edi_sale')[1]
        except ValueError:
            template_id = False
        try:
            compose_form_id = ir_model_data.get_object_reference('mail', 'email_compose_message_wizard_form')[1]
        except ValueError:
            compose_form_id = False
        ctx = {
            'default_model': 'sale.order',
            'default_res_id': self.ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'mark_so_as_sent': True,
            'custom_layout': "sale.mail_template_data_notification_email_sale_order",
            'proforma': self.env.context.get('proforma', False),
            'force_email': True
        }
        return {
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
    def action_done(self):
        return self.write({'state': 'done'})

    @api.multi
    def action_unlock(self):
        self.write({'state': 'sale'})

    @api.multi
    def _action_confirm(self):
        for order in self.filtered(lambda order: order.partner_id not in order.message_partner_ids):
            order.message_subscribe([order.partner_id.id])
        # Aman 12/09/2020 added code to set check_pending_qty value to update or not update on basis of pending qty
        mto_exist = self.check_mrp_mod(self.order_line)
        status = self.check_stock_status(mto_exist)
        self.check_pending_qty = status
        self.write({
            'state': 'sale',
            'confirmation_date': fields.Datetime.now()
        })
        # Aman end
        if self.env.context.get('send_email'):
            self.force_quotation_send()

        # create an analytic account if at least an expense product
        for order in self:
            if any([expense_policy not in [False, 'no'] for expense_policy in order.order_line.mapped('product_id.expense_policy')]):
                if not order.analytic_account_id:
                    order._create_analytic_account()

        # ravi start at 29/12/2019 for creating new lines in product tab for insertibg new lines in  customer wise code
        if self.order_line:
            for single_line in self.order_line:
                if single_line.product_id:
                    line_customer_id = self.partner_id.id
                    line_product_id = single_line.product_id.id
                    line_product_template_id = single_line.product_id.product_tmpl_id.id
                    line_product_template_cat = single_line.product_id.product_tmpl_id.categ_id.id
                    # line_customer_product_code = single_line.customer_code or ''
                    # line_customer_description = single_line.customer_specific_description_quotation or ''

                    # if line_customer_id and line_product_id and line_product_template_id and line_customer_product_code and not single_line.is_a_suggested_product:
                    #     all_customer_code_lines = self.env['product.customer.info'].search(
                    #         [('name', '=', line_customer_id), ('product_id', '=', line_product_id),
                    #          ('product_tmpl_id', '=', line_product_template_id),
                    #          ('product_code', '=', line_customer_product_code)])
                    #     print('all_customer_code_lines', all_customer_code_lines)
                    #     if not all_customer_code_lines:
                    #         self.env['product.customer.info'].create({
                    #             'name': line_customer_id,
                    #             'product_id': line_product_id,
                    #             'product_tmpl_id': line_product_template_id,
                    #             'product_code': line_customer_product_code,
                    #             'descrep': line_customer_description,
                    #             'categ_id': line_product_template_cat,
                    #         })


                    self.env['product.customer.info'].create({
                        'name': line_customer_id,
                        'product_id': line_product_id,
                        'product_tmpl_id': line_product_template_id,
                        # 'product_code': line_customer_product_code,
                        # 'descrep': line_customer_description,
                        # 'categ_id': line_product_template_cat,
                    })
        # ravi end
         # salman: code to change state autometically
        if self.so_type in ['arc','open_order']:
            n=0
            if self.so_type=='open_order':
                for i in range(len(self.order_line)):
                    if self.order_line[i].product_uom_qty==self.requisition_id.line_ids[i].product_qty-(self.requisition_id.line_ids[i].qty_ordered-self.order_line[i].product_uom_qty):
                        n += 1
            elif self.so_type=='arc':
                for i in range(len(self.order_line)):
                    n += self.requisition_id.line_ids[i].order_value
                                 
            if n==len(self.order_line) and self.so_type=='open_order':
                self.requisition_id.state='done'
            elif n>=self.requisition_id.commitment_value and self.so_type=='arc':
                self.requisition_id.state='done'

        # salman end
        

        return True

    @api.multi
    def action_confirm(self):
        if self._get_forbidden_state_confirm() & set(self.mapped('state')):
            raise UserError(_(
                'It is not allowed to confirm an order in the following states: %s'
            ) % (', '.join(self._get_forbidden_state_confirm())))
        # Aman 30/09/2020 code for changing the state of SQ depend on the quantity left
        for items in self:
            sale_quot = self.env['sale.quotation'].search(
                [('id', '=', items.reference_quot.id), ('product_id', '=', items.product_id.id)])
            if sale_quot:
                count = 0
                for lines in sale_quot.quotation_lines:
                    if lines.product_uom_qty == lines.total_qty_ordered:
                        count += 1
                if count == len(sale_quot.quotation_lines):
                    sale_quot.write({'state': 'done'})
                else:
                    sale_quot.write({'state': 'partial_order'})
        # Aman code ends here
        self._action_confirm()
        # Aman 07/08/2020 Commented calling of action_done function because there is no need of lock and unlock
        # functionality
        # if self.env['ir.config_parameter'].sudo().get_param('sale.auto_done_setting'):
        #     self.action_done()
        # Aman end
        return True

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
        for category, lines in groupby(self.order_line, lambda l: l.layout_category_id):
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
        for line in self.order_line:
            price_reduce = line.price_unit * (1.0 - line.discount / 100.0)
            taxes = line.tax_id.compute_all(price_reduce, quantity=line.product_uom_qty, product=line.product_id, partner=self.partner_shipping_id)['taxes']
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
        return super(SaleOrder, self).get_access_action(access_uid)

    def get_mail_url(self):
        return self.get_share_url()

    def get_portal_confirmation_action(self):
        return self.env['ir.config_parameter'].sudo().get_param('sale.sale_portal_confirmation_options', default='none')

    @api.multi
    def _notification_recipients(self, message, groups):
        groups = super(SaleOrder, self)._notification_recipients(message, groups)

        self.ensure_one()
        if self.state not in ('draft', 'cancel'):
            for group_name, group_method, group_data in groups:
                if group_name == 'customer':
                    continue
                group_data['has_button_access'] = True

        return groups


class SaleOrderLine(models.Model):
    _name = 'sale.order.line'
    _description = 'Sales Order Line'
    _order = 'order_id, layout_category_id, sequence, id'


     #salman : code to check qty
    
    @api.onchange('product_uom_qty')
    def check_qty(self):
        if self.order_id.so_type=='open_order':
            for i in self.order_id.requisition_id.line_ids:
                if self.product_id==i.product_id:

                    if (i.product_qty-i.qty_ordered)>=self.product_uom_qty:
                        pass
                    else:
                        total_qty=i.product_qty-i.qty_ordered
                        raise ValidationError(_('You have only %s quantity to order') % total_qty)

    # salman end

    # Aman 9/10/2020 Added onchange function to check discount
    @api.onchange('discount')
    def check_discount(self):
        genric.check_disct(self)
    # Aman end

    @api.depends('state', 'product_uom_qty', 'qty_delivered', 'qty_to_invoice', 'qty_invoiced')
    def _compute_invoice_status(self):
        """
        Compute the invoice status of a SO line. Possible statuses:
        - no: if the SO is not in status 'sale' or 'done', we consider that there is nothing to
          invoice. This is also hte default value if the conditions of no other status is met.
        - to invoice: we refer to the quantity to invoice of the line. Refer to method
          `_get_to_invoice_qty()` for more information on how this quantity is calculated.
        - upselling: this is possible only for a product invoiced on ordered quantities for which
          we delivered more than expected. The could arise if, for example, a project took more
          time than expected but we decided not to invoice the extra cost to the client. This
          occurs onyl in state 'sale', so that when a SO is set to done, the upselling opportunity
          is removed from the list.
        - invoiced: the quantity invoiced is larger or equal to the quantity ordered.
        """
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for line in self:
            if line.state not in ('sale', 'done'):
                line.invoice_status = 'no'
            elif not float_is_zero(line.qty_to_invoice, precision_digits=precision):
                line.invoice_status = 'to invoice'
            elif line.state == 'sale' and line.product_id.invoice_policy == 'order' and\
                    float_compare(line.qty_delivered, line.product_uom_qty, precision_digits=precision) == 1:
                line.invoice_status = 'upselling'
            elif float_compare(line.qty_invoiced, line.product_uom_qty, precision_digits=precision) >= 0:
                line.invoice_status = 'invoiced'
            else:
                line.invoice_status = 'no'

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id')
    def _compute_amount(self):
        """
        Compute the amounts of the SO line.
        """
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=line.order_id.partner_shipping_id)
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })

    @api.depends('product_id', 'order_id.state', 'qty_invoiced', 'qty_delivered')
    def _compute_product_updatable(self):
        for line in self:
            if line.state in ['done', 'cancel'] or (line.state == 'sale' and (line.qty_invoiced > 0 or line.qty_delivered > 0)):
                line.product_updatable = False
            else:
                line.product_updatable = True

    @api.depends('product_id.invoice_policy', 'order_id.state')
    def _compute_qty_delivered_updateable(self):
        for line in self:
            line.qty_delivered_updateable = (line.order_id.state == 'sale') and (line.product_id.service_type == 'manual') and (line.product_id.expense_policy == 'no')

    @api.depends('state',
                 'price_reduce_taxinc',
                 'qty_delivered',
                 'invoice_lines',
                 'invoice_lines.price_total',
                 'invoice_lines.invoice_id',
                 'invoice_lines.invoice_id.state',
                 'invoice_lines.invoice_id.refund_invoice_ids',
                 'invoice_lines.invoice_id.refund_invoice_ids.state',
                 'invoice_lines.invoice_id.refund_invoice_ids.amount_total')
    def _compute_invoice_amount(self):
        refund_lines_product = self.env['account.invoice.line']
        for line in self:
            # Invoice lines referenced by this line
            invoice_lines = line.invoice_lines.filtered(lambda l: l.invoice_id.state in ('open', 'paid') and l.invoice_id.type == 'out_invoice')
            refund_lines = line.invoice_lines.filtered(lambda l: l.invoice_id.state in ('open', 'paid') and l.invoice_id.type == 'out_refund')
            # Refund invoices linked to invoice_lines
            refund_invoices = invoice_lines.mapped('invoice_id.refund_invoice_ids').filtered(lambda inv: inv.state in ('open', 'paid'))
            refund_invoice_lines = (refund_invoices.mapped('invoice_line_ids') + refund_lines - refund_lines_product).filtered(lambda l: l.product_id == line.product_id)
            if refund_invoice_lines:
                refund_lines_product |= refund_invoice_lines
            # If the currency of the invoice differs from the sale order, we need to convert the values
            if line.invoice_lines and line.invoice_lines[0].currency_id \
                    and line.invoice_lines[0].currency_id != line.currency_id:
                invoiced_amount_total = sum([inv_line.currency_id.with_context({'date': inv_line.invoice_id.date}).compute(inv_line.price_total, line.currency_id)
                                             for inv_line in invoice_lines])
                refund_amount_total = sum([inv_line.currency_id.with_context({'date': inv_line.invoice_id.date}).compute(inv_line.price_total, line.currency_id)
                                           for inv_line in refund_invoice_lines])
            else:
                invoiced_amount_total = sum(invoice_lines.mapped('price_total'))
                refund_amount_total = sum(refund_invoice_lines.mapped('price_total'))
            # Total of remaining amount to invoice on the sale ordered (and draft invoice included) to support upsell (when
            # delivered quantity is higher than ordered one). Draft invoice are ignored on purpose, the 'to invoice' should
            # come only from the SO lines.
            total_sale_line = line.price_total
            if line.product_id.invoice_policy == 'delivery':
                total_sale_line = line.price_reduce_taxinc * line.qty_delivered

            line.amt_invoiced = invoiced_amount_total - refund_amount_total
            line.amt_to_invoice = (total_sale_line - invoiced_amount_total) if line.state in ['sale', 'done'] else 0.0

    @api.depends('qty_invoiced', 'qty_delivered', 'to_invoice', 'product_uom_qty', 'order_id.state')
    def _get_to_invoice_qty(self):
        """
        Compute the quantity to invoice. If the invoice policy is order, the quantity to invoice is
        calculated from the ordered quantity. Otherwise, the quantity delivered is used.
        """
        for line in self:
            if line.order_id.state in ['sale', 'done']:
                if line.product_id.invoice_policy == 'order':
                    line.qty_to_invoice = line.product_uom_qty - line.qty_invoiced
                else:
                    if line.product_id.type in ['consu', 'product']:
                        # Piyush: code for checking invoices qty on 15-07-2020
                        for so in self:
                            done_invoices = self.env['account.invoice'].search([('sale_id', '=', so.order_id.id)])
                            if done_invoices:
                                # line.qty_to_invoice = line.qty_delivered
                                line.qty_to_invoice = line.to_invoice - line.qty_invoiced
                            else:
                                # commented line and given new value
                                # line.qty_to_invoice = line.qty_delivered - line.qty_invoiced
                                line.qty_to_invoice = line.to_invoice - line.qty_invoiced

                    else:
                        for so in self:
                            done_invoices = self.env['account.invoice'].search([('sale_id', '=', so.order_id.id)])  # check for created invoices
                            if done_invoices:
                                line.qty_to_invoice = line.product_uom_qty - line.qty_invoiced
                            else:
                                line.qty_to_invoice = line.product_uom_qty
                        # code ends here
            else:
                line.qty_to_invoice = 0

    @api.depends('invoice_lines.invoice_id.state', 'invoice_lines.quantity')
    def _get_invoice_qty(self):
        """
        Compute the quantity invoiced. If case of a refund, the quantity invoiced is decreased. Note
        that this is the case only if the refund is generated from the SO and that is intentional: if
        a refund made would automatically decrease the invoiced quantity, then there is a risk of reinvoicing
        it automatically, which may not be wanted at all. That's why the refund has to be created from the SO
        """
        for line in self:
            qty_invoiced = 0.0
            for invoice_line in line.invoice_lines:
                if invoice_line.invoice_id.state != 'cancel':
                    if invoice_line.invoice_id.type == 'out_invoice':
                        qty_invoiced += invoice_line.uom_id._compute_quantity(invoice_line.quantity, line.product_uom)
                    elif invoice_line.invoice_id.type == 'out_refund':
                        qty_invoiced -= invoice_line.uom_id._compute_quantity(invoice_line.quantity, line.product_uom)
            line.qty_invoiced = qty_invoiced

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

    # Jatin for customer_tax_lines taxes on 03-07-2020
    def taxes_of_customer_tax_lines(self):
        filter_tax = []
        for val in self:
            check = val.product_id.customer_tax_lines
            print("check", check)
            for rec in check:
                tax_check = rec.tax_id.id
                print(tax_check)
                filter_tax.append(tax_check)
            print('filter_tax', filter_tax)

        print_tax = self.env['account.tax'].search([('id', 'in', filter_tax)])
        print("print_tax in function", print_tax)
        return print_tax
    # end jatin
    @api.multi
    def _compute_tax_id(self):
        for line in self:
            # by Jatin to get taxes based on customer_tax_lines 02-07-2020
            print_tax = self.taxes_of_customer_tax_lines()
            taxes = print_tax.filtered(
                lambda r: not line.company_id or r.company_id == line.company_id).ids
            print("taxes", taxes)
            # end jatin

            #taxes = line.product_id.taxes_id.filtered(lambda r: not line.company_id or r.company_id == line.company_id).ids
            # line.tax_id = fpos.map_tax(taxes, line.product_id, line.order_id.partner_shipping_id) if fpos else taxes

            check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
            check_custmr_state = self.env['res.partner'].search([('id', '=',self.order_partner_shipping_id.id),('company_id', '=', self.company_id.id),('type','=','delivery'), ('parent_id','=',self.order_partner_id.id)])
            check_delivery_address= self.order_partner_shipping_id
            print("sale check_delivery_address",check_delivery_address.state_id,check_cmpy_state.state_id,check_delivery_address.id)
            if check_cmpy_state.state_id == check_delivery_address.state_id:
                # if same states show taxes like CGST SGST GST
                # Getting sql query data in form of ids of taxes from account.tax
                self.env.cr.execute(""" select id from account_tax where active=True and type_tax_use='sale' AND tax_group_id not in (2,3) and company_id='%s'""" %(self.env.user.company_id.id,))
                csgst_taxes = self.env.cr.dictfetchall()
                final = [taxes.remove(val.get('id')) for val in csgst_taxes if val.get('id') in taxes if csgst_taxes]
                # tax_list = []
                # tax_id_list = [tax.id for tax in taxes]
                # if igst_taxes:
                #     for val in igst_taxes:
                #         tax_detail_id = val.get('id')
                #         tax_list.append(tax_detail_id)
                #
                # for value in tax_id_list:
                #     if value in tax_list:
                #         tax_id_list.remove(value)
                #         print(tax_id_list)
                line.tax_id = taxes

            elif check_cmpy_state.state_id != check_delivery_address.state_id:
                # if different states show taxes like IGST
                self.env.cr.execute(""" select id from account_tax where active=True and type_tax_use='sale' AND tax_group_id!=4 and company_id='%s'""" % (self.env.user.company_id.id,))
                igst_taxes = self.env.cr.dictfetchall()
                final = [taxes.remove(val.get('id')) for val in igst_taxes if val.get('id') in taxes if igst_taxes]
                line.tax_id = taxes
            return {'domain': {'tax_id': [final]}}
    #     Gaurav end

    @api.model
    def _get_purchase_price(self, pricelist, product, product_uom, date):
        return {}

    @api.model
    def _prepare_add_missing_fields(self, values):
        """ Deduce missing required fields from the onchange """
        res = {}
        onchange_fields = ['name', 'price_unit', 'product_uom', 'tax_id']
        if values.get('order_id') and values.get('product_id') and any(f not in values for f in onchange_fields):
            with self.env.do_in_onchange():
                line = self.new(values)
                line.product_id_change()
                for field in onchange_fields:
                    if field not in values:
                        res[field] = line._fields[field].convert_to_write(line[field], line)
        return res

    @api.model
    def create(self, values):

        values.update(self._prepare_add_missing_fields(values))
        line = super(SaleOrderLine, self).create(values)
        if line.order_id.state == 'sale':
            msg = _("Extra line with %s ") % (line.product_id.display_name,)
            line.order_id.message_post(body=msg)
            # create an analytic account if at least an expense product
            if line.product_id.expense_policy not in [False, 'no'] and not self.order_id.analytic_account_id:
                self.order_id._create_analytic_account()

        #  Gaurav 24/4/20 added code for updating the product / variant detail (product/variant master)

        for product in line:
            print("product-----", product, product.id, product.state)

            if product.product_id:
                saledetail = self.env['product.saledetail']

                ppd = saledetail.search([('customer_partner_id', '=', product.order_id.partner_id.id),
                                         ('product_id', '=', product.product_id.id),
                                             ('company_id', '=', self.env.user.company_id.id)])
                print("saledetail---", saledetail, saledetail.product_id, ppd)
                if ppd:
                    diff_price = product.price_unit - ppd.price
                    # Piyush: added two new files and updating them on 17-07-2020
                    # added additional_info, item_code
                    ppd.update({'sequence': product.order_id.name,
                                'additional_info': product.additional_info or '',
                                'item_code': product.item_code or '',
                                'date': product.order_id.date_order,
                                'customer_partner_id': product.order_id.partner_id.id,
                                'product_quantity': product.product_uom_qty,
                                'price': product.price_unit,
                                'price_diff': diff_price,
                                })
                else:
                    saledetail.create({'sequence': product.order_id.name,
                                       'date': product.order_id.date_order,
                                       'additional_info': product.additional_info or '',
                                       'item_code': product.item_code or '',
                                       'customer_partner_id': product.order_id.partner_id.id,
                                       'product_id': product.product_id.id,
                                       'product_detail_tmpl_id': product.product_id.product_tmpl_id.id,
                                       'product_quantity': product.product_uom_qty,
                                       'price': product.price_unit,
                                       'price_diff': 0.0,
                                       })

        #             Gaurav end

        return line

    def _update_line_quantity(self, values):
        orders = self.mapped('order_id')
        for order in orders:
            order_lines = self.filtered(lambda x: x.order_id == order)
            msg = "<b>The ordered quantity has been updated.</b><ul>"
            for line in order_lines:
                msg += "<li> %s:" % (line.product_id.display_name,)
                msg += "<br/>" + _("Ordered Quantity") + ": %s -> %s <br/>" % (
                line.product_uom_qty, float(values['product_uom_qty']),)
                if line.product_id.type in ('consu', 'product'):
                    msg += _("Delivered Quantity") + ": %s <br/>" % (line.qty_delivered,)
                msg += _("Invoiced Quantity") + ": %s <br/>" % (line.qty_invoiced,)
            msg += "</ul>"
            order.message_post(body=msg)

    @api.multi
    def write(self, values):

        if 'product_uom_qty' in values:
            precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
            self.filtered(
                lambda r: r.state == 'sale' and float_compare(r.product_uom_qty, values['product_uom_qty'], precision_digits=precision) != 0)._update_line_quantity(values)

        # Prevent writing on a locked SO.
        protected_fields = self._get_protected_fields()
        if 'done' in self.mapped('order_id.state') and any(f in values.keys() for f in protected_fields):
            protected_fields_modified = list(set(protected_fields) & set(values.keys()))
            fields = self.env['ir.model.fields'].search([
                ('name', 'in', protected_fields_modified), ('model', '=', self._name)
            ])
            raise UserError(
                _('It is forbidden to modify the following fields in a locked order:\n%s')
                % '\n'.join(fields.mapped('field_description'))
            )
        # self.product_id_change()
        result = super(SaleOrderLine, self).write(values)

        for product in self:
            print("product-----", product, product.id, product.state)

            if product.product_id:
                saledetail = self.env['product.saledetail']

                ppd = saledetail.search([('customer_partner_id', '=', product.order_id.partner_id.id),
                                         ('product_id', '=', product.product_id.id),
                                             ('company_id', '=', self.env.user.company_id.id)])
                print("saledetail---", saledetail, saledetail.product_id, ppd)
                if ppd:
                    diff_price = product.price_unit - ppd.price
                    # if there is change in price only then update the values of old records
                    if 'price_unit' in values and values.get('price_unit'):
                        ppd.update({'sequence': product.order_id.name,
                                    'date': product.order_id.date_order,
                                    'customer_partner_id': product.order_id.partner_id.id,
                                    'product_quantity': product.product_uom_qty,
                                    'price': product.price_unit,
                                    'price_diff': diff_price,
                                    })
                    else:
                        return result

                else:
                    saledetail.create({'sequence': product.order_id.name,
                                       'date': product.order_id.date_order,
                                       'customer_partner_id': product.order_id.partner_id.id,
                                       'product_id': product.product_id.id,
                                       'product_detail_tmpl_id': product.product_id.product_tmpl_id.id,
                                       'product_quantity': product.product_uom_qty,
                                       'price': product.price_unit,
                                       'price_diff': 0.0,
                                       })
        #             Gaurav end

        return result

    # Gaurav end





    order_id = fields.Many2one('sale.order', string='Order Reference', required=True, ondelete='cascade', index=True, copy=False)
    name = fields.Text(string='Description', required=True)
    # Salman add Hsn field
    hsn_id=fields.Char(string='HSN code')
    # Salman end
    sequence = fields.Integer(string='Sequence', default=10)

    invoice_lines = fields.Many2many('account.invoice.line', 'sale_order_line_invoice_rel', 'order_line_id', 'invoice_line_id', string='Invoice Lines', copy=False)
    invoice_status = fields.Selection([
        ('upselling', 'Upselling Opportunity'),
        ('invoiced', 'Fully Invoiced'),
        ('to invoice', 'To Invoice'),
        ('no', 'Nothing to Invoice')
        ], string='Invoice Status', compute='_compute_invoice_status', store=True, readonly=True, default='no')
    price_unit = fields.Float('Unit Price', required=True, digits=dp.get_precision('Product Price'), default=0.0)

    price_subtotal = fields.Monetary(compute='_compute_amount', string='Subtotal', readonly=True, store=True)
    price_tax = fields.Float(compute='_compute_amount', string='Taxes', readonly=True, store=True)
    price_total = fields.Monetary(compute='_compute_amount', string='Total', readonly=True, store=True)

    price_reduce = fields.Float(compute='_get_price_reduce', string='Price Reduce', digits=dp.get_precision('Product Price'), readonly=True, store=True)
    # tax_id = fields.Many2many('account.tax', string='Taxes', domain=['|', ('active', '=', False), ('active', '=', True)])
    tax_id = fields.Many2many('account.tax', string='Taxes')
    price_reduce_taxinc = fields.Monetary(compute='_get_price_reduce_tax', string='Price Reduce Tax inc', readonly=True, store=True)
    price_reduce_taxexcl = fields.Monetary(compute='_get_price_reduce_notax', string='Price Reduce Tax excl', readonly=True, store=True)

    discount = fields.Float(string='Discount (%)', digits=dp.get_precision('Discount'), default=0.0)

    product_id = fields.Many2one('product.product', string='Product', domain=[('sale_ok', '=', True)], change_default=True, ondelete='restrict', required=True)
    product_updatable = fields.Boolean(compute='_compute_product_updatable', string='Can Edit Product', readonly=True, default=True)
    product_uom_qty = fields.Float(string='Quantity', digits=dp.get_precision('Product Unit of Measure'), required=True, default=1.0)
    product_uom = fields.Many2one('product.uom', string='Unit of Measure', required=True)
    # Non-stored related field to allow portal user to see the image of the product he has ordered
    product_image = fields.Binary('Product Image', related="product_id.image", store=False)
    # Piyush: for adding new field on 07-07-2020
    to_invoice = fields.Float(compute="_compute_to_invoice", string='To Invoice', copy=False,
                              digits=dp.get_precision('Product Unit of Measure'))
    to_invoice_qty = fields.Float(string="To Invoice Qty")
    # ends here
    qty_delivered_updateable = fields.Boolean(compute='_compute_qty_delivered_updateable', string='Can Edit Delivered', readonly=True, default=True)
    qty_delivered = fields.Float(string='Delivered', copy=False, digits=dp.get_precision('Product Unit of Measure'), default=0.0)
    qty_to_invoice = fields.Float(
        compute='_get_to_invoice_qty', string='To Invoice', store=True, readonly=True,
        digits=dp.get_precision('Product Unit of Measure'))
    qty_invoiced = fields.Float(
        compute='_get_invoice_qty', string='Invoiced', store=True, readonly=True,
        digits=dp.get_precision('Product Unit of Measure'))

    salesman_id = fields.Many2one(related='order_id.user_id', store=True, string='Salesperson', readonly=True)
    currency_id = fields.Many2one(related='order_id.currency_id', store=True, string='Currency', readonly=True)
    company_id = fields.Many2one(related='order_id.company_id', string='Company', store=True, readonly=True)
    order_partner_id = fields.Many2one(related='order_id.partner_id', store=True, string='Customer')
    # Gaurav 13/3/20 added shipping address- Delivery address for order id
    order_partner_shipping_id = fields.Many2one(related='order_id.partner_shipping_id', store=True, string='Delivery Address')
    # Gaurav end
    analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Analytic Tags')
    is_downpayment = fields.Boolean(
        string="Is a down payment", help="Down payments are made when creating invoices from a sales order."
        " They are not copied when duplicating a sales order.")

    state = fields.Selection([
        ('draft', 'Quotation'),
        ('sent', 'Quotation Sent'),
        ('sale', 'Sales Order'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], related='order_id.state', string='Order Status', readonly=True, copy=False, store=True, default='draft')
    # Piyush: code for making field not mandetory on 21-06-2020
    customer_lead = fields.Float(
        'Delivery Lead Time', default=0.0,
        help="Number of days between the order confirmation and the shipping of the products to the customer", oldname="delay")
    amt_to_invoice = fields.Monetary(string='Amount To Invoice', compute='_compute_invoice_amount', compute_sudo=True, store=True)
    amt_invoiced = fields.Monetary(string='Amount Invoiced', compute='_compute_invoice_amount', compute_sudo=True, store=True)

    layout_category_id = fields.Many2one('sale.layout_category', string='Section')
    # Piyush: code for creating two new fields on 21-06-2020
    additional_info = fields.Text(string="Additional Info")
    item_code = fields.Char(string="Customer Item Code")
    # code ends here
    layout_category_sequence = fields.Integer(string='Layout Sequence')

    # Gaurav 19feb20 edit for Options:stock to increase on sales order

    # options_stock = fields.Selection([
    #     ('stock_sales_order', 'Stocks to increase on sales order'),
    #     ('xyz', 'XYZ'),
    # ], string='Stock Options')
    #
    # check_option_stock = fields.Boolean("Check Option Stock", compute="compute_options_stock", default=False)
    


    # TODO: remove layout_category_sequence in master or make it work properly

    sale_order_schedule_lines = fields.One2many('scheduling.sale.order', 'schedule_order_id', 'Schedule Order')
    schedule_order_id = fields.Many2one('sale.order.scheduling', 'SO Scheduling')

    # Piyush: code for getting dispatched qty for creating invoice on 07-07-2020
    @api.multi
    def _compute_to_invoice(self):
        # to_invoice = 0.0
        for item in self:
            item_req_line = self.env['stock.move'].search([('sale_line_id', '=', item.id)])
            if item_req_line:
                for qty in item_req_line:
                    if qty.picking_id.state in ['bill_pending', 'done']:
                        item.to_invoice += qty.quantity_done
            # item.to_invoice = to_invoice
    # code ends here

    # @api.depends('tax_id')
    # def compute_tax_get(self):
    #
    #     print("working default gettttttttttttttttttttttttttttttttttttttttttttttttttttttttt")
    #     if self.env.user.company_id.vat:
    #         check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
    #         check_delivery_address = self.order_partner_shipping_id
    #         print("self.order_partner_shipping_id", check_delivery_address.state_id, check_cmpy_state.state_id)
    #         # checking company state and customer state is same or not
    #         if check_cmpy_state.state_id == check_delivery_address.state_id:
    #             # if same states show taxes like CGST SGST GST
    #             self.env.cr.execute(
    #                 """ select id from account_tax where active=True and type_tax_use='sale' AND tax_group_id!=4 and company_id='%s'""" % (
    #                     self.env.user.company_id.id,))
    #             csgst_taxes = self.env.cr.dictfetchall()
    #             cs_tax_list = []
    #             if csgst_taxes:
    #                 for val in csgst_taxes:
    #                     tax_detail_id = val.get('id')
    #                     cs_tax_list.append(tax_detail_id)
    #                     print("sale cs_tax_listtt", cs_tax_list)
    #                     # self.update({'tax_id': [(6, 0, cs_tax_list)]})
    #                     # result = {'domain': {'tax_id': [('id', 'in', cs_tax_list)]}}
    #                     # domain = [('id', 'in', cs_tax_list)]
    #                     result = {'domain': {'tax_id': [('id', 'in', cs_tax_list)]}}
    #
    #         elif check_cmpy_state.state_id != check_delivery_address.state_id:
    #             print("the vlaue in the dict-------------------------------------- else part=================")
    #             # if different states show taxes like IGST
    #             self.env.cr.execute(
    #                 """ select id from account_tax where active=True and type_tax_use='sale' AND tax_group_id not in (2,3) and company_id='%s'""" % (
    #                     self.env.user.company_id.id,))
    #             igst_taxes = self.env.cr.dictfetchall()
    #             i_tax_list = []
    #             if igst_taxes:
    #                 for val in igst_taxes:
    #                     tax_detail_id = val.get('id')
    #                     i_tax_list.append(tax_detail_id)
    #                     # self.update({'tax_id': [(6, 0, i_tax_list)]})
    #                     # Setting domain in tax_id to show taxes in list view/ update show whole list
    #                     # result = {'domain': {'tax_id': [('id', 'in', i_tax_list)]}}
    #                     result = {'domain': {'tax_id': [('id', 'in', i_tax_list)]}}
    #     print("the val in the domain", result)
    #     return result




    # Gaurav 11/3/20 added check_register def for checking GST registered or not
    @api.multi
    def _check_registered_tax(self):

        check_reg = self.env['res.company'].search([('partner_id', '=', self.company_id.id)])
        print("check_reg....", check_reg, check_reg.name)

        if check_reg:
            for data in check_reg:
                print("DATA REG",data)
                if data.vat:
                    print("REG")
                    self.check_registered = False
                    print("Check REG Update Multi - FALSE")
                    return False
                else:
                    print("Not REG")
                    self.check_registered = True
                    print("Check REG Update Multi - TRUE")
                    return True
    # Gaurav end

    # @api.onchange('produced_quantity')
    # def compute_pending_quantity_stock(self):
    #
    #     for data in self:
    #         if data.produced_quantity:
    #             print("remqtyyyyyyyyyyyyy2if")
    #             if data.remaining_quantity > 0:
    #                 remqty = data.remaining_quantity - data.produced_quantity
    #                 print("Remainremqtyyyyyyyyyyyyy", remqty)
    #                 data.pending_quantity = remqty
    #                 data.remaining_quantity = remqty
    #                 print('data.pending_quantity',data.pending_quantity)
    #                 print('data.pending_quantity',data.remaining_quantity)
    #                 # print(a)
    #             else:
    #                 remqty = data.product_uom_qty - data.produced_quantity
    #                 print("producedremqtyyyyyyyyyyyyy", remqty)
    #                 data.pending_quantity=remqty
    #                 data.remaining_quantity=remqty
    # Gaurav end

    @api.multi
    def _prepare_invoice_line(self, qty, shipping_partner=False):
        """
        Prepare the dict of values to create the new invoice line for a sales order line.

        :param qty: float quantity to invoice
        """
        self.ensure_one()
        res = {}
        product = self.product_id.with_context(force_company=self.company_id.id)
        # Aman 5/9/2020 added type which will get the current type of invoice, then call get_invoice_line_account1
        # function to get account from product form
        # account = product.property_account_income_id or product.categ_id.property_account_income_categ_id
        for rec in self.order_id.invoice_ids:
            type = rec.type
            invoice_line = self.env['account.invoice.line']
            so_line = self
            # acct = invoice_line.get_invoice_line_account1(type, product, self.order_id.partner_id, self.company_id) or invoice_line.with_context({'journal_id': rec.journal_id.id, 'type': 'in_invoice'})._default_account()
            acct = invoice_line.get_invoice_line_account1(type, product, self.order_id.partner_id, self.company_id, shipping_partner, so_line)
            if acct != False:
                account = acct.id
            else:
                account = invoice_line.with_context({'journal_id': rec.journal_id.id, 'type': 'in_invoice'})._default_account()
        # Aman end
        if not account:
            raise UserError(_('Please define income account for this product: "%s" (id:%d) - or for its category: "%s".') %
                (self.product_id.name, self.product_id.id, self.product_id.categ_id.name))

        fpos = self.order_id.fiscal_position_id or self.order_id.partner_id.property_account_position_id
        if fpos:
            account = fpos.map_account(account)
        # mfg_installed = self.env['ir.module.module'].search([('name', '=', 'mrp')])
        # if mfg_installed.state == 'installed':
        #     account = account.id

        res = {
            'name': self.name,
            'sequence': self.sequence,
            'origin': self.order_id.name,
            'account_id': account,
            'price_unit': self.price_unit,
            'quantity': qty,
            'freeze_qty': True,
            'discount': self.discount,
            'uom_id': self.product_uom.id,
            'product_id': self.product_id.id or False,
            'layout_category_id': self.layout_category_id and self.layout_category_id.id or False,
            'invoice_line_tax_ids': [(6, 0, self.tax_id.ids)],
            'account_analytic_id': self.order_id.analytic_account_id.id,
            'analytic_tag_ids': [(6, 0, self.analytic_tag_ids.ids)],
        }
        return res

    @api.multi
    def invoice_line_create(self, invoice_id, qty):
        """ Create an invoice line. The quantity to invoice can be positive (invoice) or negative (refund).
            :param invoice_id: integer
            :param qty: float quantity to invoice
            :returns recordset of account.invoice.line created
        """
        invoice_lines = self.env['account.invoice.line']
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        # Aman 12/12/2020 Get partner's shipping_id to get account_id
        invoice = self.env['account.invoice'].search([('id', '=', invoice_id)])
        shipping_partner = invoice.sale_id.partner_shipping_id
        for line in self:
            if not float_is_zero(qty, precision_digits=precision):
                vals = line._prepare_invoice_line(qty=qty, shipping_partner=shipping_partner)
                vals.update({'invoice_id': invoice_id, 'sale_line_ids': [(6, 0, [line.id])]})
                invoice_lines |= self.env['account.invoice.line'].create(vals)
        return invoice_lines
        # Aman end

    @api.multi
    def _prepare_procurement_values(self, group_id=False):
        """ Prepare specific key for moves or other components that will be created from a procurement rule
        comming from a sale order line. This method could be override in order to add other custom key that could
        be used in move/po creation.
        """
        return {}

    @api.multi
    def _get_display_price(self, product):
        # TO DO: move me in master/saas-16 on sale.order
        if self.order_id.pricelist_id.discount_policy == 'with_discount':
            return product.with_context(pricelist=self.order_id.pricelist_id.id).price
        product_context = dict(self.env.context, partner_id=self.order_id.partner_id.id, date=self.order_id.date_order, uom=self.product_uom.id)
        final_price, rule_id = self.order_id.pricelist_id.with_context(product_context).get_product_price_rule(self.product_id, self.product_uom_qty or 1.0, self.order_id.partner_id)
        base_price, currency_id = self.with_context(product_context)._get_real_price_currency(product, rule_id, self.product_uom_qty, self.product_uom, self.order_id.pricelist_id.id)
        if currency_id != self.order_id.pricelist_id.currency_id.id:
            base_price = self.env['res.currency'].browse(currency_id).with_context(product_context).compute(base_price, self.order_id.pricelist_id.currency_id)
        # negative discounts (= surcharge) are included in the display price
        return max(base_price, final_price)

    # Aman 06/08/2020 Customer must be selected before selecting product
    # salman 29/11/2020  add hsn_id
    @api.onchange('product_id')
    def onchan_cust(self):
        part = self.order_id.partner_id
        if not part and self.product_id:
            raise UserError(_("You must select Customer First!!"))

        self.hsn_id=self.product_id.hsn_id.hsn_code    
    # Salman end
    # Aman end

    @api.multi
    @api.onchange('product_id')
    def product_id_change(self):
        # Aman 23/12/2020 Added condition and user error to check if product with
        # hsn_disable = True is selected in last or not
        if self.order_id.order_line:
            if self.product_id:
                if self.order_id.order_line[0].product_id.hsn_disable == True:
                    raise UserError(_("This item should be selected in the end!!"))
        # Aman end
        self.tax_id=''
        result = {}
        print("working product id onchange")

        if not self.product_id:
            return {'domain': {'product_uom': []}}

        vals = {}
        domain = {'product_uom': [('category_id', '=', self.product_id.uom_id.category_id.id)]}
        if not self.product_uom or (self.product_id.uom_id.id != self.product_uom.id):
            vals['product_uom'] = self.product_id.uom_id
            vals['product_uom_qty'] = 1.0

        product = self.product_id.with_context(
            lang=self.order_id.partner_id.lang,
            partner=self.order_id.partner_id.id,
            quantity=vals.get('product_uom_qty') or self.product_uom_qty,
            date=self.order_id.date_order,
            pricelist=self.order_id.pricelist_id.id,
            uom=self.product_uom.id
        )

        result = {'domain': domain}

        title = False
        message = False
        warning = {}
        if product.sale_line_warn != 'no-message':
            title = _("Warning for %s") % product.name
            message = product.sale_line_warn_msg
            warning['title'] = title
            warning['message'] = message
            result = {'warning': warning}
            if product.sale_line_warn == 'block':
                self.product_id = False
                return result

        name = product.name_get()[0][1]
        # Aman 28/11/2020 Added description of product on form level
        if product.description:
            name = product.description
        elif product.description_sale:
            name += '\n' + product.description_sale
        vals['name'] = name

        # Gaurav 11/3/20 added validation for GST check (if company is unregistered then don't add taxes if registered then add taxes state wise)
        if self.env.user.company_id.vat:
            # GST present , company registered
            # function _compute_tax_id give the tax applied to particular product
            # self._compute_tax_id()
            check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.company_id.id)])
            check_delivery_address = self.order_partner_shipping_id
            # checking company state and customer state is same or not
            if check_cmpy_state.state_id == check_delivery_address.state_id:
                # Aman 23/12/2020 Added condition to check if product with hsn_disable = True must pick tax
                # of the item with greatest tax
                if product.hsn_disable == True:
                    group_type = ('CGST', 'SGST')
                    taxes_cust = genric.get_taxes(self, product, group_type, so=True)
                    self.tax_id = taxes_cust
                # Aman end
                else:
                    # if same states show taxes like CGST SGST GST
                    self.env.cr.execute(""" select id from account_tax where active=True and type_tax_use='sale' AND tax_group_id!=4 and company_id='%s'""" % (self.env.user.company_id.id,))
                    csgst_taxes = self.env.cr.dictfetchall()
                    self._compute_tax_id()
                    cs_tax_list=[]
                    if csgst_taxes:
                        for val in csgst_taxes:
                            tax_detail_id = val.get('id')
                            cs_tax_list.append(tax_detail_id)
                            print("sale cs_tax_listtt",cs_tax_list)
                            # self.update({'tax_id': [(6, 0, cs_tax_list)]})
                            result = {'domain': {'tax_id':[('id','in',cs_tax_list)]}}
            elif check_cmpy_state.state_id != check_delivery_address.state_id:
                # Aman 23/12/2020 Added condition to check if product with hsn_disable = True must pick tax
                # of the item with greatest tax
                if product.hsn_disable == True:
                    group_type = ('IGST')
                    taxes_cust = genric.get_taxes(self, product, group_type, so=True)
                    self.tax_id = taxes_cust
                # Aman end
                else:
                    # if different states show taxes like IGST
                    self.env.cr.execute(""" select id from account_tax where active=True and type_tax_use='sale' AND tax_group_id not in (2,3) and company_id='%s'""" % (self.env.user.company_id.id,))
                    igst_taxes = self.env.cr.dictfetchall()
                    self._compute_tax_id()
                    i_tax_list = []
                    if igst_taxes:
                        for val in igst_taxes:
                            tax_detail_id = val.get('id')
                            i_tax_list.append(tax_detail_id)
                            # self.update({'tax_id': [(6, 0, i_tax_list)]})
                            # Setting domain in tax_id to show taxes in list view/ update show whole list
                            result = {'domain': {'tax_id': [('id', 'in', i_tax_list)]}}
        # Gaurav end
        # Jatin for customer_tax_lines taxes 03-07-2020
        filter_tax = []
        check = product.customer_tax_lines
        print("check", check)
        for rec in check:
            tax_check = rec.tax_id.id
            print(tax_check)
            filter_tax.append(tax_check)
        print('filter_tax', filter_tax)

        print_tax = self.env['account.tax'].search([('id', 'in', filter_tax)])
        print("print_tax in function", print_tax)

        if self.order_id.pricelist_id and self.order_id.partner_id:
            vals['price_unit'] = self.env['account.tax']._fix_tax_included_price_company(
                self._get_display_price(product), print_tax, self.tax_id, self.company_id)
        # end jatin


        # if self.order_id.pricelist_id and self.order_id.partner_id:
        #     vals['price_unit'] = self.env['account.tax']._fix_tax_included_price_company(self._get_display_price(product), product.taxes_id, self.tax_id, self.company_id)
        self.update(vals)

        return result

    @api.onchange('product_uom', 'product_uom_qty')
    def product_uom_change(self):
        if not self.product_uom or not self.product_id:
            self.price_unit = 0.0
            return
        if self.order_id.pricelist_id and self.order_id.partner_id:
            product = self.product_id.with_context(
                lang=self.order_id.partner_id.lang,
                partner=self.order_id.partner_id.id,
                quantity=self.product_uom_qty,
                date=self.order_id.date_order,
                pricelist=self.order_id.pricelist_id.id,
                uom=self.product_uom.id,
                fiscal_position=self.env.context.get('fiscal_position')
            )

            # Jatin for customer_tax_lines taxes 03-07-2020
            filter_tax = []
            check = product.customer_tax_lines
            print("check", check)
            for rec in check:
                tax_check = rec.tax_id.id
                print(tax_check)
                filter_tax.append(tax_check)
            print('filter_tax', filter_tax)


            print_tax = self.env['account.tax'].search([('id', 'in', filter_tax)])
            print("print_tax in function", print_tax)
            # Aman 8/10/2020 added self.price_unit since price was getting changed when we change product qty
            # self.price_unit = self.env['account.tax']._fix_tax_included_price_company(self._get_display_price(product),
            #                                                                           print_tax, self.tax_id,
            #                                                                           self.company_id)
            self.price_unit = self.env['account.tax']._fix_tax_included_price_company(self.price_unit,
                                                                                      print_tax, self.tax_id,
                                                                                      self.company_id)
            # Aman end
            # end jatin

    @api.multi
    def name_get(self):
        result = []
        for so_line in self:
            name = '%s - %s' % (so_line.order_id.name, so_line.name.split('\n')[0] or so_line.product_id.name)
            if so_line.order_partner_id.ref:
                name = '%s (%s)' % (name, so_line.order_partner_id.ref)
            result.append((so_line.id, name))
        return result

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if operator in ('ilike', 'like', '=', '=like', '=ilike'):
            args = expression.AND([
                args or [],
                ['|', ('order_id.name', operator, name), ('name', operator, name)]
            ])
        return super(SaleOrderLine, self).name_search(name, args, operator, limit)

    @api.multi
    def unlink(self):
        if self.filtered(lambda x: x.state in ('sale', 'done')):
            raise UserError(_('You can not remove a sales order line.\nDiscard changes and try setting the quantity to 0.'))
        return super(SaleOrderLine, self).unlink()

    @api.multi
    def _get_delivered_qty(self):
        '''
        Intended to be overridden in sale_stock and sale_mrp
        :return: the quantity delivered
        :rtype: float
        '''
        return 0.0

    def _get_real_price_currency(self, product, rule_id, qty, uom, pricelist_id):
        """Retrieve the price before applying the pricelist
            :param obj product: object of current product record
            :parem float qty: total quentity of product
            :param tuple price_and_rule: tuple(price, suitable_rule) coming from pricelist computation
            :param obj uom: unit of measure of current order line
            :param integer pricelist_id: pricelist id of sales order"""
        PricelistItem = self.env['product.pricelist.item']
        field_name = 'lst_price'
        currency_id = None
        product_currency = None
        if rule_id:
            pricelist_item = PricelistItem.browse(rule_id)
            if pricelist_item.pricelist_id.discount_policy == 'without_discount':
                while pricelist_item.base == 'pricelist' and pricelist_item.base_pricelist_id and pricelist_item.base_pricelist_id.discount_policy == 'without_discount':
                    price, rule_id = pricelist_item.base_pricelist_id.with_context(uom=uom.id).get_product_price_rule(product, qty, self.order_id.partner_id)
                    pricelist_item = PricelistItem.browse(rule_id)

            if pricelist_item.base == 'standard_price':
                field_name = 'standard_price'
            if pricelist_item.base == 'pricelist' and pricelist_item.base_pricelist_id:
                field_name = 'price'
                product = product.with_context(pricelist=pricelist_item.base_pricelist_id.id)
                product_currency = pricelist_item.base_pricelist_id.currency_id
            currency_id = pricelist_item.pricelist_id.currency_id

        product_currency = product_currency or(product.company_id and product.company_id.currency_id) or self.env.user.company_id.currency_id
        if not currency_id:
            currency_id = product_currency
            cur_factor = 1.0
        else:
            if currency_id.id == product_currency.id:
                cur_factor = 1.0
            else:
                cur_factor = currency_id._get_conversion_rate(product_currency, currency_id)

        product_uom = self.env.context.get('uom') or product.uom_id.id
        if uom and uom.id != product_uom:
            # the unit price is in a different uom
            uom_factor = uom._compute_price(1.0, product.uom_id)
        else:
            uom_factor = 1.0

        return product[field_name] * uom_factor * cur_factor, currency_id.id

    def _get_protected_fields(self):
        return [
            'product_id', 'name', 'price_unit', 'product_uom', 'product_uom_qty',
            'tax_id', 'analytic_tag_ids'
        ]

    @api.onchange('product_id', 'product_uom', 'product_uom_qty', 'tax_id')
    def _onchange_discount(self):
        if not (self.product_id and self.product_uom and
                self.order_id.partner_id and self.order_id.pricelist_id and
                self.order_id.pricelist_id.discount_policy == 'without_discount' and
                self.env.user.has_group('sale.group_discount_per_so_line')):
            return

        self.discount = 0.0
        product = self.product_id.with_context(
            lang=self.order_id.partner_id.lang,
            partner=self.order_id.partner_id.id,
            quantity=self.product_uom_qty,
            date=self.order_id.date_order,
            pricelist=self.order_id.pricelist_id.id,
            uom=self.product_uom.id,
            fiscal_position=self.env.context.get('fiscal_position')
        )

        product_context = dict(self.env.context, partner_id=self.order_id.partner_id.id, date=self.order_id.date_order, uom=self.product_uom.id)

        price, rule_id = self.order_id.pricelist_id.with_context(product_context).get_product_price_rule(self.product_id, self.product_uom_qty or 1.0, self.order_id.partner_id)
        new_list_price, currency_id = self.with_context(product_context)._get_real_price_currency(product, rule_id, self.product_uom_qty, self.product_uom, self.order_id.pricelist_id.id)

        if new_list_price != 0:
            if self.order_id.pricelist_id.currency_id.id != currency_id:
                # we need new_list_price in the same currency as price, which is in the SO's pricelist's currency
                new_list_price = self.env['res.currency'].browse(currency_id).with_context(product_context).compute(new_list_price, self.order_id.pricelist_id.currency_id)
            discount = (new_list_price - price) / new_list_price * 100
            if discount > 0:
                self.discount = discount

    ###########################
    # Analytic Methods
    ###########################

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

        # Piyush: code for amendment in quotation on 21-06-2020


class SaleOrderAmd(models.Model):
    _name = "sale.order.amd"
    _description = "Sale Order Amendment"
    _order = "id desc"

    order_amd_id = fields.Many2one('sale.order', string='Quotation Amd Id', index=True)
    name = fields.Char(string='Order Reference', copy=False, readonly=True, states={'draft': [('readonly', False)]}, index=True, default=lambda self: _('New'))
    origin = fields.Char(string='Source Document', help="Reference of the document that generated this sales order request.")
    client_order_ref = fields.Char(string='Customer Reference', copy=False)
    reference_quot = fields.Many2one('sale.quotation', string="Reference Quotation")
    state = fields.Selection([
        ('draft', 'Quotation'),
        ('sent', 'Quotation Sent'),
        ('sale', 'Sales Order'),
        ('done', 'Locked'),
        ('closed', 'Short Close'),
        ('cancel', 'Cancelled'),
        ], string='Status', readonly=True, copy=False, index=True, track_visibility='onchange', default='draft')
    date_order = fields.Datetime(string='Order Date', readonly=True, index=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, copy=False, default=fields.Datetime.now)
    validity_date = fields.Date(string='Expiration Date', readonly=True, copy=False, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},
        help="Manually set the expiration date of your quotation (offer), or it will set the date automatically based on the template if online quotation is installed.")
    is_expired = fields.Boolean(string="Is expired")
    create_date = fields.Datetime(string='Creation Date', readonly=True, index=True, help="Date on which sales order is created.")
    confirmation_date = fields.Datetime(string='Confirmation Date', readonly=True, index=True, help="Date on which the sales order is confirmed.", oldname="date_confirm", copy=False)
    user_id = fields.Many2one('res.users', string='Salesperson', index=True, track_visibility='onchange', default=lambda self: self.env.user)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, change_default=True, index=True, track_visibility='always', store=True)
    partner_invoice_id = fields.Many2one('res.partner', string='Invoice Address', readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, store=True, help="Invoice address for current sales order.")
    partner_shipping_id = fields.Many2one('res.partner', string='Delivery Address', readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, store=True, help="Delivery address for current sales order.")
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist', readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, help="Pricelist for current sales order.")
    currency_id = fields.Many2one("res.currency", related='pricelist_id.currency_id', string="Currency", readonly=True)
    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account', readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, help="The analytic account related to a sales order.", copy=False, oldname='project_id')
    order_line = fields.One2many('sale.order.line.amd', 'order_id', string='Order Lines', states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}, copy=True, auto_join=True)
    invoice_count = fields.Integer(string='# of Invoices', readonly=True)
    invoice_ids = fields.Many2many("account.invoice", string='Invoices', readonly=True, copy=False)
    invoice_status = fields.Selection([
        ('upselling', 'Upselling Opportunity'),
        ('invoiced', 'Fully Invoiced'),
        ('to invoice', 'To Invoice'),
        ('no', 'Nothing to Invoice')
        ], string='Invoice Status', store=True, readonly=True)

    note = fields.Text('Terms and conditions')

    amount_untaxed = fields.Monetary(string='Untaxed Amount', store=True, readonly=True, track_visibility='onchange')
    amount_tax = fields.Monetary(string='Taxes', store=True, readonly=True)
    amount_total = fields.Monetary(string='Total', store=True, readonly=True, track_visibility='always')
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Terms', oldname='payment_term')
    fiscal_position_id = fields.Many2one('account.fiscal.position', oldname='fiscal_position', string='Fiscal Position')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('sale.order'))
    team_id = fields.Many2one('crm.team', 'Sales Channel', change_default=True, oldname='section_id')
    product_id = fields.Many2one('product.product', related='order_line.product_id', string='Product')
    manufacturnig_end_date = fields.Date(string='Manufacturing Date')
    no_of_days_manu = fields.Float(string='No Of Days')
    options_stock = fields.Selection([
        ('stock_sales_order', 'Stocks to increase on sales order'),
        ('xyz', 'XYZ'),
    ], string='Stock Options')
    check_option_stock = fields.Boolean("Check Option Stock", default=False)
    check_registered = fields.Boolean("Check Registered", store=True, default=False)
    check_order_line = fields.Boolean("Check Order Line", store=True, default=False)
    check_scheduled = fields.Boolean("As per scheduled", store=True, default=False)
    so_type = fields.Selection([('adhoc', 'Adhoc Order'),('arc', 'Arc'), ('open_order', 'Open Order'), ('direct', 'Direct')], string="Order Type", default="adhoc")


class SaleOrderLineAmd(models.Model):
    _name = "sale.order.line.amd"
    _description = "Sale Order Line Amendment"
    _order = "id desc"

    order_id = fields.Many2one('sale.order.amd', string='Order Reference', required=True, ondelete='cascade', index=True, copy=False)
    order_amd_id = fields.Many2one('sale.order', string='Quotation Amd Id', index=True)
    name = fields.Text(string='Description', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    invoice_lines = fields.Many2many('account.invoice.line', 'sale_order_line_invoice_rel', 'order_line_id', 'invoice_line_id', string='Invoice Lines', copy=False)
    invoice_status = fields.Selection([
        ('upselling', 'Upselling Opportunity'),
        ('invoiced', 'Fully Invoiced'),
        ('to invoice', 'To Invoice'),
        ('no', 'Nothing to Invoice')
        ], string='Invoice Status', store=True, readonly=True, default='no')
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
    product_uom = fields.Many2one('product.uom', string='Unit of Measure', required=True)
    product_image = fields.Binary('Product Image', related="product_id.image", store=False)
    qty_delivered_updateable = fields.Boolean(string='Can Edit Delivered', readonly=True, default=True)
    qty_delivered = fields.Float(string='Delivered', copy=False, digits=dp.get_precision('Product Unit of Measure'), default=0.0)
    qty_to_invoice = fields.Float(string='To Invoice', store=True, readonly=True,
        digits=dp.get_precision('Product Unit of Measure'))
    qty_invoiced = fields.Float(string='Invoiced', store=True, readonly=True,
        digits=dp.get_precision('Product Unit of Measure'))
    salesman_id = fields.Many2one(related='order_id.user_id', store=True, string='Salesperson', readonly=True)
    currency_id = fields.Many2one(related='order_id.currency_id', store=True, string='Currency', readonly=True)
    company_id = fields.Many2one(related='order_id.company_id', string='Company', store=True, readonly=True)
    order_partner_id = fields.Many2one(related='order_id.partner_id', store=True, string='Customer')
    order_partner_shipping_id = fields.Many2one(related='order_id.partner_shipping_id', store=True, string='Delivery Address')
    analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Analytic Tags')
    is_downpayment = fields.Boolean(
        string="Is a down payment", help="Down payments are made when creating invoices from a sales order."
        " They are not copied when duplicating a sales order.")
    state = fields.Selection([
        ('draft', 'Quotation'),
        ('sent', 'Quotation Sent'),
        ('sale', 'Sales Order'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], related='order_id.state', string='Order Status', readonly=True, copy=False, store=True, default='draft')
    customer_lead = fields.Float(
        'Delivery Lead Time', default=0.0,
        help="Number of days between the order confirmation and the shipping of the products to the customer", oldname="delay")
    amt_to_invoice = fields.Monetary(string='Amount To Invoice', store=True)
    amt_invoiced = fields.Monetary(string='Amount Invoiced', store=True)
    layout_category_id = fields.Many2one('sale.layout_category', string='Section')
    additional_info = fields.Text(string="Additional Info")
    item_code = fields.Char(string="Customer Item Code")
    layout_category_sequence = fields.Integer(string='Layout Sequence')
    sale_order_schedule_lines = fields.One2many('scheduling.sale.order', 'schedule_order_id', 'Schedule Order')
    schedule_order_id = fields.Many2one('sale.order.scheduling', 'SO Scheduling')

    # code ends here


class SaleOrderScheduling(models.Model):
    _name = "sale.order.scheduling"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Sale Order Scheduling"
    _order = "id desc"

    # def get_so_domain(self):
    #     so_list=[]
    #     so_ids = self.env['sale.order'].search([('state','=','sale')])
    #     if len(so_ids) > 0:
    #         for val in so_ids:
    #             if val.so_type in ('arc','open_order','scheduled'):
    #                 so_list.append(val.id)
    #     domain=[('id','in',so_list)]
    #     return domain

    name = fields.Char('Name', default='New')
    schedule_lines = fields.One2many('sale.order.line', 'schedule_order_id', 'Schedule Lines')
    sale_schedule_line = fields.One2many('scheduling.sale.order', 'order_scheduling_id', 'Schedule Lines')
    so_schedule_lines = fields.One2many('sale.order.scheduling.line', 'schedule_ord_id', 'SO Schedule Lines')
    so_date = fields.Datetime('SO Date')
    # avinash:05/09/20 Commented because Need to show only those sale order which is confirm
    # and scheduling is true or sale order is of type 'open order'.
    # Gaurav 7/4/20 edit for setting domain as per sceduled
    # sale_id = fields.Many2one('sale.order','Sale Order', domain=[('so_type', '=', 'open_order')])
    # sale_idsale_id = fields.Many2one('sale.order', 'Sale Order', domain=['|',('so_type', '=', 'open_order'),('state', '=', 'sale'),('check_scheduled', '=', True),('state', '=', 'sale')])
    sale_id = fields.Many2one('sale.order', 'Sale Order',
                              domain=['&', '|', '&', ('state', '=', 'sale'), ('check_scheduled', '=', True),('so_type', '=', 'open_order'),('state', '=', 'sale')])
    # Gaurav end
    # avinash end
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Sent For Approval'),
        ('approve', 'Approve'),
        ('amend', 'Amendment'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True, copy=False, index=True, track_visibility='onchange', default='draft')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.user.company_id.id)
    remarks= fields.Text('Remarks')
    approval_need = fields.Boolean("Approval Need")
    assign_id = fields.Many2one('hr.employee','Assign for Approval')
    show_approve_btn = fields.Boolean('Show Approve Button', default=False, compute="show_approved_button")

    partner_id = fields.Many2one('res.partner', 'Customer')
    # Piyush: code for adding freeze_schedule to allow no changes in scchedule after dispatch is done on 27-06-2020
    freeze_schedule = fields.Boolean(string="Freeze Schedule", compute="compute_freeze_lines", help="If this field is true no changes in schedule if dispatch created!")
    # Gaurav 7/4/20 edit for check of as per scheduled
    # check_scheduled = fields.Boolean("As per scheduled", store=True, default=False)

    # Gaurav end

    @api.multi
    def compute_freeze_lines(self):
        for order in self:
            freeze_lines = False
            values_check = self.env['stock.picking'].search([('sale_order_scheduling_id', '=', order.id),
                                                             ('state', '=', 'done')])
            if len(values_check) > 0:
                freeze_lines = True
            else:
                freeze_lines = False
            order.freeze_schedule = freeze_lines

    # Piyush: code for getting schedule qty from scheduling lines on 25-06-2020
    def check_sch_created(self, so_line_id, product_id):
        qty = 0.0
        sch_ids = self.env['sale.order.scheduling.line'].search(
            [('sale_line_id', '=', so_line_id.id), ('state', '!=', 'cancel')])
        if len(sch_ids) > 0:
            for val in sch_ids:
                qty = qty + val.schedule_qty
        return qty
    # code ends here

    # Piyush: code for onchange of the sale id on 26-06-2020

    @api.multi
    @api.onchange('sale_id')
    def onchange_sale_order(self):
        self.so_schedule_line = []
        # Gaurav 8/4/20 added for refreshing lines before creating
        self.so_schedule_lines = ''
        # Gaurav end
        # salman add hsn_id
        if self.sale_id:
            self.partner_id = self.sale_id.partner_id.id
            self.so_date = self.sale_id.date_order or ''
            self.company_id = self.sale_id.company_id.id
            data = []
            if self.sale_id.order_line:
                for line in self.sale_id.order_line:
                    already_sch_qty = self.check_sch_created(line, line.product_id)
                    if already_sch_qty > 0.0:
                        pending_qty = line.product_uom_qty - already_sch_qty
                    else:
                        pending_qty = line.product_uom_qty
                    if pending_qty > 0:
                        val_data = (0, False, {
                            'product_id': line.product_id.id,
                            'hsn_id':line.hsn_id,
                            'product_uom': line.product_uom.id,
                            'sale_id': self.sale_id.id,
                            'sale_line_id': line.id,
                            'so_qty': line.product_uom_qty,
                            'already_scheduled_qty': already_sch_qty,
                            'pending_qty': pending_qty,
                            'company_id': self.company_id.id or False,
                        })
                        data.append(val_data)
                if len(data) > 0:
                    self.so_schedule_lines = data
                else:
                    raise ValidationError(_('No Pending Qty!'))
        # code ends here

    # @api.onchange('sale_id')
    # def onchange_sale_order(self):
    #     if self.sale_id:
    #         line_list=[]
    #         if self.sale_id.order_line:
    #             for val in self.sale_id.order_line:
    #                 print ("vallllllllllll",val)
    #                 line_tup=(0,False,{'product_id':val.product_id and val.product_id.id or False})
    #                 line_list.append(line_tup)
    #             self.so_schedule_lines = line_list

    def check_schedule_line(self):
        for order in self:
            if order.state == 'draft':
                if order.so_schedule_lines:
                    for val in order.so_schedule_lines:
                        if not val.schedules_product_lines:
                            raise ValidationError(_('Please Define the Scheduling Lines!'))
                else:
                    raise ValidationError(_('Please Define the product for Scheduling!'))

    def update_schedule_line(self):
        for order in self:
            if order.so_schedule_lines:
                for val in order.so_schedule_lines:
                    for line in val.schedules_product_lines:
                        line.write({'scheduling_state': 'confirm','state': 'confirm'})
                    val.write({'state': 'confirm'})

    @api.multi
    def action_sent_for_review_main(self):
        manager_id=False
        self.check_schedule_line()
        self.update_schedule_line()
        if self.env.user:
            emp_id = self.env['hr.employee'].search([('user_id','=',self.env.user.id)])
            if len(emp_id) > 0:
                if emp_id[0].parent_id:
                    manager_id = emp_id[0].parent_id
                else:
                    manager_id = emp_id[0]

        name = self.env['ir.sequence'].with_context(force_company=self.company_id.id).next_by_code(
            'sale.order.scheduling') or _('New')
        self.write({
            'state': 'confirm',
            'assign_id': manager_id and manager_id.id or False,
        #     Gaurav removed name ref
        })
        return True

    def show_approved_button(self):
        print("show aproved button",self)
        for val in self:
            if val.state == 'confirm':
                val.show_approve_btn = True

    @api.model
    def create(self, vals):

        # Gaurav 7/4/20 add for reference sequence for scheduling

        if 'sale_id' in vals and vals.get('sale_id'):
            count = 1
            so = self.env['sale.order'].browse(vals.get('sale_id'))
            all_so_scheduling_rec = self.env['sale.order.scheduling'].search(
                [('sale_id', '=', so.id), ('company_id', '=', self.env.user.company_id.id)])
            if all_so_scheduling_rec:
                count = len(all_so_scheduling_rec.ids) + 1
            name = so.name + '/' + 'SCH-' + str(count)
            vals['name'] = name


        if vals.get('so_schedule_lines'):
            print("vals.get('so_schedule_lines')---",vals.get('so_schedule_lines')[0])
            for list in vals.get('so_schedule_lines'):
                print("listttttt",list)
                # dup_so_qty = list[2]['so_qty']
                # dup_so_qty = 0
                # dup_pending_qty = list[2]['pending_qty']
            #     print("pending==",val.pending_qty,val.so_qty)
            # print(a)

        # Gaurav end
        # Gaurav 15/4/20 added code for validations in scheduling and updation of so and pending quantity

        result = super(SaleOrderScheduling, self).create(vals)

        # Piyush: code for sale order scheduling on 26-06-2020

        if result.sale_id.order_line:
            if result.so_schedule_lines:
                for schedule_line in result.so_schedule_lines:
                    pending_qty = 0.0
                    dispatch_qty = 0.0

                    sch_line_id = self.env['sale.order.scheduling.line'].search(
                        [('sale_line_id', '=', schedule_line.sale_line_id.id), ('state', '!=', 'cancel')])

                    if len(sch_line_id) > 0:
                        ord_qty = 0.0
                        for cr_qty in sch_line_id:
                            ord_qty = ord_qty + cr_qty.schedule_qty

                            # P: code for pending qty
                        if ord_qty > 0:
                            pending_qty = schedule_line.sale_line_id.product_uom_qty - ord_qty + schedule_line.schedule_qty
                        else:
                            pending_qty = schedule_line.sale_line_id.product_uom_qty + schedule_line.schedule_qty

                            # P: code for scheduling qty
                    if schedule_line.schedules_product_lines:
                        for detail_line in schedule_line.schedules_product_lines:
                            dispatch_qty += detail_line.qty_to_dispatch

                            # P: code for validations
                        if dispatch_qty > pending_qty:
                            raise ValidationError(_('Schedule Qty cannot be greater than  Pending quantity!'))
                        elif dispatch_qty <= 0:
                                raise ValidationError(_('Schedule Qty cannot be less or equal to 0!'))

                        # P: code for update_value in result.so_schedule_lines:
                        schedule_line.write({'so_qty': schedule_line.sale_line_id.product_uom_qty,
                                             'pending_qty': pending_qty,
                                             'schedule_qty': dispatch_qty})

                    else:
                        raise ValidationError(_('Please Enter Scheduling for all the items!'))
                    # code ends here

        return result

    # Gaurav end


    # avinash : 14/10/20 Adde so that total schedule quantity cannot be greater then sale order quantity

    def compare_schedule_and_so_qty(self):
        for line in self.so_schedule_lines:
            sch_line_id = self.env['scheduling.sale.order'].search([('sale_order_id', '=', self.sale_id.id), ('product_id', '=', line.product_id.id), ('state', '!=', 'cancel')])
            total_disp_qty = 0
            if len(sch_line_id) > 0:
                for prod_line in sch_line_id:
                    total_disp_qty += prod_line.qty_to_dispatch
                if total_disp_qty > line.so_qty:
                    raise ValidationError(
                        "Your total dispatch quantity is {0} more than order quantity. Your sale order quantity {1}, {2}".format(total_disp_qty, line.so_qty, line.product_id.name))

    # end avinashacko


    @api.multi
    def write(self, vals):

        if 'state' in vals and vals['state'] == 'approve':
            if vals.get('name', _('New')) == _('New'):
                if 'company_id' in vals:
                    vals['name'] = self.env['ir.sequence'].with_context(force_company=vals['company_id']).next_by_code(
                        'sale.order.scheduling') or _('New')
                else:
                    vals['name'] = self.env['ir.sequence'].next_by_code('sale.order.scheduling') or _('New')
        # avinash : 14/10/20 Adde so that total schedule quantity cannot be greater then sale order quantity
        self.compare_schedule_and_so_qty()
        # end avinash

        result = super(SaleOrderScheduling, self).write(vals)

        # Piyush: code for sale order scheduling on 26-06-2020

        for change in self:
            if change.so_schedule_lines:
                for line in change.so_schedule_lines:
                    dispatch_qty = 0.0
                    if line.schedules_product_lines:
                        for detail_line in line.schedules_product_lines:
                            dispatch_qty = dispatch_qty + detail_line.qty_to_dispatch
                            if dispatch_qty > line.so_qty:
                                raise ValidationError(_('Schedule Qty cannot be greater than  SO quantity!'))
                            elif dispatch_qty > line.pending_qty:
                                raise ValidationError(_('Schedule Qty cannot be greater than  pending quantity!'))
                            elif dispatch_qty <= 0:
                                raise ValidationError(_('Schedule Qty cannot be less or equal to 0!'))

                        line.write({'so_qty': line.so_qty,
                                    'pending_qty': line.pending_qty,
                                    'schedule_qty': dispatch_qty})

                    else:
                        raise ValidationError(_('Please Enter Scheduling for all the items!'))
        # code ends here

        if 'state' not in vals and self.state == 'approve':
            self.update({'state': 'confirm'})
        return result

    # Piyush: code for creating scheduling dict in dispatch on 01-07-2020
    def _prepare_stock_move_schedule_line(self, schedule_line):
        sch_list = []
        if schedule_line.schedules_product_lines:
            for val in schedule_line.schedules_product_lines:
                #avinash:08/09/20 So that we can only show those scheduling whose shipped quantity is empty.
                if val.qty_to_dispatch > val.qty_shipped:
                # end avinash
                    dict_sch = (0, False, {
                        'product_id': val.product_id and val.product_id.id or False,
                        'prod_tmpl_id': val.product_id and val.product_id.product_tmpl_id.id or False,
                        'date': val.schedule_date or fields.datetime.now(),
                        'dispatch_date': val.dispatch_date or fields.datetime.now(),
                        'schedule_document': self.name or '',
                        'product_qty': val.qty_to_dispatch or 0.0,
                        'pending_qty': val.qty_to_dispatch or 0.0,
                        'order_scheduling_id': val.id,
                        'product_uom': val.product_uom.id or val.product_id.uom_id.id,
                        'remarks': val.remarks,
                        'sale_order_id': val.sale_order_id and val.sale_order_id.id or False,
                        'schedule_order_id': schedule_line.sale_line_id and schedule_line.sale_line_id.id or False,
                            })
                    sch_list.append(dict_sch)
        return sch_list
    # code ends here

    # Piyush: code for updating scheduling in dispatch on 01-07-2020
    def update_so_scheduling(self, schedule_line, sale_line_id, count):
        move_ids = self.env['stock.move'].search([('sale_line_id', '=', sale_line_id.id),
                                                  ('state', 'not in', ('done', 'cancel'))])
        if len(move_ids) > 0:
            move_schedule_lines = self._prepare_stock_move_schedule_line(schedule_line)
            for val in move_ids:
                # avinash:03/09/20 Commenting because we need to show all scheduling line on dispatch
                # val.move_sale_order_schedule_lines = ''  # Piyush: for refreshing the lines so that data f

                # if not val.move_sale_order_schedule_lines:
                #     val.write({'move_sale_order_schedule_lines': move_schedule_lines})
                # else:
                #     val.move_sale_order_schedule_lines = ''
                #     val.update({'move_sale_order_schedule_lines': move_schedule_lines})

                if not val.move_sale_order_schedule_lines:
                    val.write({'move_sale_order_schedule_lines': move_schedule_lines})

                else:
                    if count == 1:
                        stock_move_sch = self.env['stock.move.schedule.line'].search([('schedule_document', '=', self.name)])
                        for ml in stock_move_sch:
                            ml.update({'move_id': False, 'state': 'cancel'})

                    val.write({'move_sale_order_schedule_lines': move_schedule_lines})

        # avinash end


    # code ends here

    @api.multi
    def action_approve_scheduling(self):
        if self.state == 'confirm':
            count =1
            for order in self:
                if order.so_schedule_lines:
                    for val in order.so_schedule_lines:
                        if not val.schedules_product_lines:
                            raise ValidationError(_('Please Define the Order Scheduling!'))
                        for line in val.schedules_product_lines:
                            line.update({'scheduling_state': 'approve'})
                        order.update_so_scheduling(val, val.sale_line_id, count)
                        count += 1
        self.write({'state': 'approve', 'name': self.name})


class SaleOrderSchedulingLine(models.Model):
    _name = "sale.order.scheduling.line"
    _description = "Sale Order Scheduling Line"

    schedule_ord_id = fields.Many2one('sale.order.scheduling','SO Schedule')
    freeze_schedule = fields.Boolean(related='schedule_ord_id.freeze_schedule', string="Freeze Schedule")
    already_scheduled_qty = fields.Float('Already Schedued Qty', store=True)
    product_id = fields.Many2one('product.product','Product')
    so_qty = fields.Float('SO Qty')
    product_uom = fields.Many2one('product.uom','UOM')
    schedule_qty = fields.Float('Schedule Qty', compute='get_schedule_qty', store=True)
    schedules_product_lines = fields.One2many('scheduling.sale.order','schedule_line_id','Schedule Product Wise Lines')
    sale_line_id = fields.Many2one('sale.order.line','SO Line')
    sale_id = fields.Many2one('sale.order','Sale Order')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Confirm'),
        ('approve', 'Approve'),
        ('amend', 'Amendment'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True, copy=False, index=True, track_visibility='onchange', default='draft')
    pending_sch_qty = fields.Float('Pending Sche Qty',compute='_get_pending_qty')
    pending_qty = fields.Float('Pending Qty')

    @api.model
    def create(self, vals):



        # vals.write({'so_qty':vals.get('so_qty'),
        #             'pending_qty': vals.get('pending_qty')})
        print("valsssssssssssssssssssssssss------", vals, self.so_qty, self.pending_qty)

        # print("hello this is change", vals.schedules_product_lines.qty_to_dispatch)
        result = super(SaleOrderSchedulingLine, self).create(vals)

        print("valsssssssssssssssssssssssss------", vals,self.so_qty, self.pending_qty)

        # result.write({'so_qty': self.so_qty,
        #             'pending_qty': self.pending_qty})
        if self.sale_line_id:
            print("selffffffffffffffffff------", self.sale_line_id)
        print("selffffffffffffffffff------", self.sale_line_id)
        print("selffffffffffffffffff------", self.sale_line_id)
        # if 'schedules_product_lines' in vals and vals['schedules_product_lines']:
        #     # print("hello this is change",vals['sale_order_schedule_lines'])
        #     qty = 0
        #     for sch_lines in result.schedules_product_lines:
        #         print("sch_linesssssssssssssssssssssssssssssssss",sch_lines.qty_to_dispatch)
        #         qty = qty + sch_lines.qty_to_dispatch
        #
        #     if qty > result.schedule_qty:
        #         print("sch_linesssssssssssssssssssssssssssssssss", result.schedule_qty, qty)
        #         raise ValidationError("Scheduled quantity should be less than or equal to the total quantity")
        return result

    @api.multi
    def write(self, vals):
        print ("sSaleOrderSchedulingLinee2222222222222222_thiss is the one", self, vals)
        d_so_qty = vals.get('so_qty')
        d_pend_qty= vals.get('pending_qty')


        res = super(SaleOrderSchedulingLine, self).write(vals)


        if 'schedules_product_lines' in vals and vals['schedules_product_lines']:
            # print("hello this is change",vals['sale_order_schedule_lines'])
            qty = 0
            for sch_lines in self.schedules_product_lines:
                # print("sch_lines",sch_lines.qty_to_dispatch)
                qty = qty + sch_lines.qty_to_dispatch

            if qty > self.pending_qty:
                raise ValidationError("Scheduled quantity should be less than or equal to the Pending quantity")
        return res

    @api.depends('so_qty', 'schedule_qty')
    def _get_pending_qty(self):
        for val in self:
            pending_sch_qty = val.so_qty - val.schedule_qty
            val.pending_sch_qty = pending_sch_qty

    # Piyush: code for getting total qty scheduled on lines on 26-06-2020

    @api.depends('schedules_product_lines.qty_to_dispatch')
    def get_schedule_qty(self):
        for line in self:
            total_schedule_qty = 0.0
            if line.schedules_product_lines:
                for detail_line in line.schedules_product_lines:
                    total_schedule_qty += detail_line.qty_to_dispatch
            line.schedule_qty = total_schedule_qty

    # code ends here

    @api.onchange('schedules_product_lines.qty_to_dispatch')
    def onchange_dispatch_qty(self):
        if self.schedules_product_lines :
            if self.schedules_product_lines.qty_to_dispatch:
                print("hello this is change latest----",self)
                # print(a)
            # qty = 0
            # for sch_lines in self.schedules_product_lines:
            #     # print("sch_lines",sch_lines.qty_to_dispatch)
            #     qty = qty + sch_lines.qty_to_dispatch
            #
            # if qty > self.pending_qty:
            #     raise ValidationError("Scheduled quantity should be less than or equal to the Pending quantity")






class SchedulingSaleOrder(models.Model):
    _name = "scheduling.sale.order"
    _description = 'Order Scheduling Details'


    schedule_order_id = fields.Many2one('sale.order.line', 'Order')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True
                                 , default=lambda self: self.env.user.company_id.id)
    order_scheduling_id = fields.Many2one('sale.order.scheduling', 'Order Scheduling')
    sale_order_id = fields.Many2one('sale.order', 'Order Number')
    product_id = fields.Many2one('product.product', 'Product')
    schedule_date = fields.Date(string='Schedule Date')
    old_schedule_date = fields.Date(string='Schedule Date')

    product_uom = fields.Many2one('product.uom','UOM')
    dispatch_date = fields.Date(string='Dispatch Date')
    qty_to_dispatch = fields.Float(string='Quantity to Dispatch')
    qty_pick = fields.Float(string="Pick Quantity")
    qty_pack = fields.Float(string="Pack Quantity")
    qty_shipped = fields.Float(string='Shipped Quantity')
    pending_qty = fields.Float(string="Pending Qty")
    remarks = fields.Char(string='Remarks')
    schedule_number = fields.Char(string='Schedule Number')
    stock_qty =fields.Float(string='Stock Quantity')
    req_qty = fields.Float(string='Req Quantity')
    mo_created = fields.Boolean('MO Created', default=False)
    scheduling_state = fields.Selection([('draft', 'draft'), ('confirm', 'Confirm'), ('approve', 'Approved')],
                                        string="Scheduling State", default="draft")
    schedule_line_id = fields.Many2one('sale.order.scheduling.line', 'Schedule Line ID')
    old_qty = fields.Float(string='Old Quantity')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Confirm'),
        ('approve', 'Approve'),
        ('amend', 'Amendment'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True, copy=False, index=True, track_visibility='onchange', default='draft')

    @api.onchange('schedule_date')
    def _onchange_schedule_date(self):
        today_date = date.today()
        if self.schedule_date:
            date_temp = datetime.strptime(self.schedule_date, '%Y-%m-%d')
            if date_temp.date() < today_date:
                raise ValidationError("Please Select Date Later than Today")
        if self.schedule_date:
        #     print ("self schedule order idddddd",self.schedule_order_id,self.schedule_line_id,self.schedule_line_id.sale_line_id)
        #     if self.schedule_line_id.sale_line_id:
        #         day_list = []
        #         if self.schedule_line_id.sale_line_id.order_id.dispatch_lag_time:
        #             max_day = 1
        #             max_day = self.schedule_line_id.sale_line_id.order_id.dispatch_lag_time
        #             print("min dayyyyyyyyyyyyyy", max_day, self.schedule_date)
        #             if self.schedule_date:
        #                 datetime_object = datetime.strptime(self.schedule_date, '%Y-%m-%d')
        #                 print("datetime_objectdatetime_object", datetime_object, type(datetime_object))
        #                 prod_deadline_date = datetime_object - timedelta(days=max_day)
        #                 print("prod deadline dateeeeeeeeeeee", prod_deadline_date)
        #                 today_date = datetime.strptime(str(date.today()), '%Y-%m-%d')
        #                 if prod_deadline_date < today_date:
        #                     raise ValidationError("Dispatch Deadline Date cannot be less then today !")
        #                 self.dispatch_date = prod_deadline_date
        #     else:
        #         self.dispatch_date = self.schedule_date
        # else:
            self.dispatch_date = self.schedule_date

    # avinash:03/09/20 Commented because When user add dispatch quantity more than
    # sale order quantity then user get error message

    # @api.onchange('qty_to_dispatch')
    # def onchange_dispatch_qty(self):
        # for val in self:
        #     if val.qty_to_dispatch:
        #         sch_line_id = self.env['sale.order.scheduling.line'].search(
        #             [('sale_line_id', '=', val.schedule_order_id.id), ('state', '!=', 'cancel')
        #              ])
        #         print("sch_line_id===",sch_line_id)
        #         if len(sch_line_id) > 0:
        #             sch_line_id.update({'schedule_qty': val.qty_to_dispatch})

    @api.onchange('qty_to_dispatch')
    def onchange_dispatch_qty(self):
        for val in self:
            if val.qty_to_dispatch:
                sch_line_id = self.env['sale.order.scheduling.line'].search(
                    [('sale_line_id', '=', val.schedule_order_id.id), ('state', '!=', 'cancel')
                     ])
                print("sch_line_id===", sch_line_id)
                total_disp_qty = val.qty_to_dispatch

                if len(sch_line_id) > 0:
                    for line in sch_line_id:
                        # print(line.schedules_product_lines.qty_to_dispatch)
                        for product_line in line.schedules_product_lines:
                            total_disp_qty += product_line.qty_to_dispatch
                    if total_disp_qty > line.so_qty:
                        raise ValidationError("Your total dispatch quantity is {0} more than order quantity. Your sale order quantity {1}".format(total_disp_qty,line.so_qty))
                    else:
                        sch_line_id.update({'schedule_qty': val.qty_to_dispatch})
    #end avinash

    @api.model
    def create(self, vals):
        # print ("scheduling saleeeee orderrrrrrrrrrr lineeeeee2222222222222222", self, vals)
        print('valsssssssssssssssgggggggggggggggg', vals)
        # print('self', self)
        schedule_date = vals.get('schedule_date')
        number = vals.get('sale_order_id')
        sale_order_object = self.env['sale.order'].browse(number)
        # print('number',type(schedule_date))
        # print('schedule_date',schedule_date)
        # print('schedule_date type', type(schedule_date))
        # print('schedule_date',sale_order_object)
        print('schedule_date',sale_order_object)



        sob= sale_order_object
        print(sob)
        if schedule_date and number:
            # self.schedule_number = sale_order_object.name + schedule_date
            # vals.update({'schedule_number': sale_order_object.name + ' ' + schedule_date})
            vals.update({'schedule_number': sale_order_object.name + ' ' + schedule_date})
            # print('vals4444',vals)
            # print (A)
        # result = super(SchedulingSaleOrder, self).create(vals)
        result = super(SchedulingSaleOrder, self).create(vals)
        # if 'schedules_product_lines' in vals and vals['schedules_product_lines']:
        # if self.qty_to_dispatch:
        #     # print("hello this is change",vals['sale_order_schedule_lines'])
        #     qty = 0
        #     for sch_lines in result.schedules_product_lines:
        #         print("sch_linesssssssssssssssssssssssssssssssss", sch_lines.qty_to_dispatch)
        #         qty = qty + sch_lines.qty_to_dispatch
        #
        #     if qty > result.schedule_qty:
        #         print("sch_linesssssssssssssssssssssssssssssssss", result.schedule_qty, qty)
        #         raise ValidationError("Scheduled quantity should be less than or equal to the total quantity")
        # return result
        return result

    @api.multi
    def write(self, vals):
        if 'qty_to_dispatch' in vals and vals['qty_to_dispatch'] and self.scheduling_state == 'approve':
            vals['old_qty'] = self.qty_to_dispatch
        if 'schedule_date' in vals and vals['schedule_date'] and self.scheduling_state == 'approve':
            vals['old_schedule_date'] = self.schedule_date
        res = super(SchedulingSaleOrder, self).write(vals)
        return res

    # def _get_qty_procurement(self):
    #     self.ensure_one()
    #     qty = 0.0
    #     for move in self.move_ids.filtered(lambda r: r.state != 'cancel'):
    #         if move.picking_code == 'outgoing':
    #             qty += move.product_uom._compute_quantity(move.product_uom_qty, self.product_uom, rounding_method='HALF-UP')
    #         elif move.picking_code == 'incoming':
    #             qty -= move.product_uom._compute_quantity(move.product_uom_qty, self.product_uom, rounding_method='HALF-UP')
    #     return qty

    @api.multi
    def _prepare_procurement_values(self, group_id=False):
        self.ensure_one()
        date_planned = datetime.strptime(self.schedule_order_id.order_id.confirmation_date,
                                         DEFAULT_SERVER_DATETIME_FORMAT) \
                       + timedelta(days=self.schedule_order_id.customer_lead or 0.0) - timedelta(
            days=self.schedule_order_id.order_id.company_id.security_lead)
        values = ({
            'company_id': self.schedule_order_id.order_id.company_id,
            'group_id': group_id,
            'sale_line_id': self.schedule_order_id.id,
            'date_planned': date_planned.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
            'route_ids': self.schedule_order_id.route_id,
            'warehouse_id': self.schedule_order_id.order_id.warehouse_id or False,
            'partner_dest_id': self.schedule_order_id.order_id.partner_shipping_id,
            'remarks': self.schedule_order_id.order_id.special_remarks_production,
            'so_type': self.schedule_order_id.order_id.so_type,
            'from_so': True,
            'order_id': self.schedule_order_id.order_id.id,
            'order_line_id': self.schedule_order_id.id

        })
        return values

    @api.multi
    def _action_launch_procurement_rule_scheduling(self):
        """
        Launch procurement group run method with required/custom fields genrated by a
        sale order line. procurement group will launch '_run_move', '_run_buy' or '_run_manufacture'
        depending on the sale order line product rule.
        """
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        errors = []
        print ("action launch procurement ruleeeeeeeeeee", self)
        for line in self:
            # if line.state != 'sale' or not line.product_id.type in ('consu', 'product'):
            #     continue
            qty = line.qty_to_dispatch
            # if float_compare(qty, line.schedule_order_id.product_uom_qty, precision_digits=precision) >= 0:
            #     continue

            group_id = line.schedule_order_id.order_id.procurement_group_id
            if not group_id:
                group_id = self.env['procurement.group'].create({
                    'name': line.schedule_order_id.order_id.name,
                    'move_type': line.schedule_order_id.order_id.picking_policy,
                    'sale_id': line.schedule_order_id.order_id.id,
                    'partner_id': line.schedule_order_id.order_id.partner_shipping_id.id,
                })
                line.schedule_order_id.order_id.procurement_group_id = group_id
            else:
                # In case the procurement group is already created and the order was
                # cancelled, we need to update certain values of the group.
                updated_vals = {}
                if group_id.partner_id != line.schedule_order_id.order_id.partner_shipping_id:
                    updated_vals.update({'partner_id': line.schedule_order_id.order_id.partner_shipping_id.id})
                if group_id.move_type != line.schedule_order_id.order_id.picking_policy:
                    updated_vals.update({'move_type': line.schedule_order_id.order_id.picking_policy})
                if updated_vals:
                    group_id.write(updated_vals)

            values = line._prepare_procurement_values(group_id=group_id)
            product_qty = line.qty_to_dispatch

            procurement_uom = line.schedule_order_id.product_uom
            quant_uom = line.product_id.uom_id
            get_param = self.env['ir.config_parameter'].sudo().get_param
            if procurement_uom.id != quant_uom.id and get_param('stock.propagate_uom') != '1':
                product_qty = line.schedule_order_id.product_uom._compute_quantity(product_qty, quant_uom,
                                                                                   rounding_method='HALF-UP')
                procurement_uom = quant_uom
            # print ("before launch procurement group functionnnnnnnnnnnn tryyyyyy",line.order_id.warehouse_id.delivery_flow)
            #  added new condition for standard flow change location id by Pushkal on 15 May 19 and 31 may 19
            route_list = []
            if line.product_id.route_ids:
                for route in line.product_id.route_ids:
                    # print ("route nameeeeeeee", route, route.name)
                    route_list.append(route.name)
            # print ("line.order_id.warehouse_id.delivery_flow",line,line.order_id,line.order_id.warehouse_id.delivery_flow,)
            # if line.order_id.warehouse_id.delivery_flow == 'standard' or 'Make To Order' not in route_list :
            if line.schedule_order_id.order_id.warehouse_id.delivery_flow == 'standard':
                try:
                    self.env['procurement.group'].run(line.product_id, product_qty, procurement_uom,
                                                      line.schedule_order_id.order_id.partner_shipping_id.property_stock_customer,
                                                      line.schedule_order_id.name, line.schedule_order_id.order_id.name,
                                                      values, 'standard')
                except UserError as error:
                    errors.append(error.name)
            else:
                location_id = ''
                # print ("product route idsssssssss",line.product_id,line.product_id.route_ids)
                rule_type = ''
                print ("route listttttttttttt", route_list)
                if 'Make To Order' in route_list and 'Manufacture' in route_list:
                    # print ("company iddddddddddddd",self.env.user.company_id)
                    rule_type = 'manufacture'
                    location_id = self.env['stock.location'].search(
                        [('company_id', '=', self.env.user.company_id.id), ('name', '=', 'Stock')],
                        order="create_date desc", limit=1)
                    # print ("location iddddddddddddd",location_id)
                elif 'Make To Order' in route_list and 'Buy' in route_list:
                    location_id = self.env['stock.location'].search(
                        [('company_id', '=', self.env.user.company_id.id), ('name', '=', 'Input')],
                        order="create_date desc", limit=1)
                    rule_type = 'buy'
                elif 'Make To Order' not in route_list and 'Manufacture' in route_list:
                    rule_type = 'manufacture'
                    location_id = self.env['stock.location'].search(
                        [('company_id', '=', self.env.user.company_id.id), ('name', '=', 'Stock')],
                        order="create_date desc", limit=1)
                    route_id = self.env['stock.location.route'].search(
                        [('name', '=', 'Manufacture'), ('company_id', '=', self.env.user.company_id.id)])
                    print ("route idddddddddddddddddd", route_id)
                    if len(route_id) > 0:
                        values.update({'route_ids': route_id})
                    else:
                        route_id_new = self.env['stock.location.route'].search(
                            [('name', '=', 'Manufacture')])
                        if len(route_id_new) > 0:
                            values.update({'route_ids': route_id_new})
                        print ("route route_id_new", route_id_new)
                elif 'Make To Order' not in route_list and 'Buy' in route_list:
                    location_id = self.env['stock.location'].search(
                        [('company_id', '=', self.env.user.company_id.id), ('name', '=', 'Input')],
                        order="create_date desc", limit=1)
                    rule_type = 'buy'
                elif 'Make To Order' in route_list:
                    # print ("company iddddddddddddd",self.env.user.company_id)
                    rule_type = 'manufacture'
                    location_id = self.env['stock.location'].search(
                        [('company_id', '=', self.env.user.company_id.id), ('name', '=', 'Stock')],
                        order="create_date desc", limit=1)
                    route_id = self.env['stock.location.route'].search(
                        [('name', '=', 'Manufacture'), ('company_id', '=', self.env.user.company_id.id)])
                    print ("route idddddddddddddddddd", route_id)
                    if len(route_id) > 0:
                        values.update({'route_ids': route_id})
                    else:
                        route_id_new = self.env['stock.location.route'].search(
                            [('name', '=', 'Manufacture')])
                        if len(route_id_new) > 0:
                            values.update({'route_ids': route_id_new})
                if location_id:
                    try:
                        self.env['procurement.group'].run(line.product_id, product_qty, procurement_uom, location_id,
                                                          line.schedule_order_id.name,
                                                          line.schedule_order_id.order_id.name, values, rule_type)
                    except UserError as error:
                        errors.append(error.name)
        if errors:
            raise UserError('\n'.join(errors))
        return True

class OrderCalculationSale(models.Model):
    _name = "order.calculation.sale"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Order Calculation Sale Order"
    _order = 'serial_no'

    name = fields.Char('Description')
    order_id = fields.Many2one('sale.order', 'SO')
    category = fields.Char('Category')
    label = fields.Char('Label')
    amount = fields.Float('Amount')
    serial_no = fields.Integer('Sr No')
    company_id = fields.Many2one('res.company', 'Company', index=True,
                                 default=lambda self: self.env.user.company_id.id)
    cr_date = fields.Date(string='Create Date', required=True, readonly=True, index=True, copy=False,
                          default=fields.Datetime.now)
