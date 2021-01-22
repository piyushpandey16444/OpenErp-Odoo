# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from collections import Counter
from odoo.addons.account.models import genric

from num2words import num2words
from odoo import api, fields, models, SUPERUSER_ID, _, tools
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_is_zero, float_compare
from odoo.exceptions import UserError, AccessError, ValidationError, RedirectWarning, except_orm
from odoo.tools.misc import formatLang
from odoo.addons.base.res.res_partner import WARNING_MESSAGE, WARNING_HELP
from odoo.addons import decimal_precision as dp


class PurchaseOrder(models.Model):
    _name = "purchase.order"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Purchase Order"
    _order = 'date_order desc, id desc'

    # Yash START 16/12/2020 : code for print purchase invoice
    def _get_tax_items(self):
        """
        Get tax items and aggregated amount
        :return:
        """
        taxes_dict = {}
        for line in self.order_line:
            for tax in line.taxes_id:
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
    # Yash END 16/12/2020 : code for print purchase invoice

    # Piyush: code for check mrp installed or not, PM on its basis from mrp or inventory on 16-06-2020

    @api.onchange('process_master_check')
    def process_check(self):
        mrp_check = self.env['ir.module.module'].search([('name', '=', 'mrp'), ('state', '=', 'installed')])
        if mrp_check:
            process_check = True
        else:
            process_check = False
        self.process_master_check = process_check

    # @api.multi
    # def compute_process_master_check(self):
    #     if self.job_order:
    #     mrp_check = self.env['ir.module.module'].search([('name', '=', 'mrp'), ('state', '=', 'installed')])
    #     if mrp_check:
    #         process_check = True
    #     else:
    #         process_check = False
    #     self.process_master_check = process_check

    # code ends here

    # Piyush: code for preventing PO creation without order lines 15-04-2020
    # @api.multi
    # @api.constrains('order_line')
    # def _check_order_line(self):
    #     if not self.order_line:
    #         raise ValidationError(_('Cannot proceed further without Products!'))
    # code ends here

    @api.depends('order_line.price_total')
    def _amount_all(self):
        for order in self:
            amount_untaxed = amount_tax = 0.0
            for line in order.order_line:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            order.update({
                'amount_untaxed': order.currency_id.round(amount_untaxed),
                'amount_tax': order.currency_id.round(amount_tax),
                'amount_total': amount_untaxed + amount_tax,
            })

    @api.depends('order_line.date_planned')
    def _compute_date_planned(self):
        for order in self:
            min_date = False
            for line in order.order_line:
                if not min_date or line.date_planned < min_date:
                    min_date = line.date_planned
            if min_date:
                order.date_planned = min_date

    @api.depends('state', 'order_line.qty_invoiced', 'order_line.qty_received', 'order_line.product_qty')
    def _get_invoiced(self):
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for order in self:
            if order.state not in ('purchase', 'done'):
                order.invoice_status = 'no'
                continue

            if any(float_compare(line.qty_invoiced,
                                 line.product_qty if line.product_id.purchase_method == 'purchase' else line.qty_received,
                                 precision_digits=precision) == -1 for line in order.order_line):
                order.invoice_status = 'to invoice'
            elif all(float_compare(line.qty_invoiced,
                                   line.product_qty if line.product_id.purchase_method == 'purchase' else line.qty_received,
                                   precision_digits=precision) >= 0 for line in order.order_line) and order.invoice_ids:
                order.invoice_status = 'invoiced'
            else:
                order.invoice_status = 'no'

    @api.depends('order_line.invoice_lines.invoice_id')
    def _compute_invoice(self):
        for order in self:
            invoices = self.env['account.invoice']
            for line in order.order_line:
                invoices |= line.invoice_lines.mapped('invoice_id')
            order.invoice_ids = invoices
            order.invoice_count = len(invoices)

    # Piyush: code for taking default operation type in job order on 11-06-2020

    @api.model
    def _default_picking_type_jo(self):
        type_obj = self.env['stock.picking.type']
        company_id = self.env.context.get('company_id') or self.env.user.company_id.id
        types = type_obj.search([('code', '=', 'outgoing'), ('warehouse_id.company_id', '=', company_id)])
        if not types:
            types = type_obj.search([('code', '=', 'outgoing'), ('warehouse_id', '=', False)])
        return types[:1]

    #  code ends here

    @api.model
    def _default_picking_type(self):
        type_obj = self.env['stock.picking.type']
        company_id = self.env.context.get('company_id') or self.env.user.company_id.id
        types = type_obj.search([('code', '=', 'incoming'), ('warehouse_id.company_id', '=', company_id)])
        print("xxxtype present", types)
        if not types:
            types = type_obj.search([('code', '=', 'incoming'), ('warehouse_id', '=', False)])
            print("xxxtype Not present", types)
        return types[:1]

    @api.depends('order_line.move_ids.returned_move_ids',
                 'order_line.move_ids.state',
                 'order_line.move_ids.picking_id')
    def _compute_picking(self):
        for order in self:
            pickings = self.env['stock.picking']
            for line in order.order_line:
                # We keep a limited scope on purpose. Ideally, we should also use move_orig_ids and
                # do some recursive search, but that could be prohibitive if not done correctly.
                moves = line.move_ids | line.move_ids.mapped('returned_move_ids')
                pickings |= moves.mapped('picking_id')
            order.picking_ids = pickings
            order.picking_count = len(pickings)

    @api.depends('picking_ids', 'picking_ids.state')
    def _compute_is_shipped(self):
        for order in self:
            if order.picking_ids and all([x.state in ['done', 'cancel'] for x in order.picking_ids]):
                order.is_shipped = True

    READONLY_STATES = {
        'purchase': [('readonly', True)],
        'done': [('readonly', True)],
        'cancel': [('readonly', True)],
    }

    name = fields.Char('Order Reference', required=True, index=True, copy=False, default='New')
    origin = fields.Char('Source Document', copy=False,
                         help="Reference of the document that generated this purchase order "
                              "request (e.g. a sales order)")
    # Piyush: code for adding rfq_id to connect p.o and r.f.q.l on 15-05-2020
    rfq_id = fields.Many2one('request.for.quotation', string='RFQ', index=True)
    # code ends here
    partner_ref = fields.Char('Vendor Reference', copy=False,
                              help="Reference of the sales order or bid sent by the vendor. "
                                   "It's used to do the matching when you receive the "
                                   "products as this reference is usually written on the "
                                   "delivery order sent by your vendor.")
    # Piyush: code for related fields to make changes in PO document level on 20-05-2020
    ref_rfq_line_id_check = fields.Boolean(string="check", default=False, help="check for value of ref_rfq_line_id on"
                                                                               " its basis ordertype and vendor will be made readonly")
    # code ends here

    # Piyush code for adding process master field from mrp and inventory on 16-06-2020
    process = fields.Many2one('mrp.routing', "Process Name")
    process_master_check = fields.Boolean(string="MRP Check", store=True,
                                          help="Field to check mrp is installed or not, If mrp installed then mrp PM "
                                               "is visible else inventory PM is visible")
    process_new = fields.Many2one('routing', "Process Name")
    # code ends here
    date_order = fields.Datetime('Order Date', required=True, states=READONLY_STATES, index=True, copy=False,
                                 default=fields.Datetime.now,
                                 help="Depicts the date where the Quotation should be validated and converted into a purchase order.")
    date_approve = fields.Date('Approval Date', readonly=1, index=True, copy=False)
    partner_id = fields.Many2one('res.partner', string='Vendor', required=True, states=READONLY_STATES,
                                 change_default=True, track_visibility='always')
    dest_address_id = fields.Many2one('res.partner', string='Drop Ship Address', states=READONLY_STATES, \
                                      help="Put an address if you want to deliver directly from the vendor to the customer. " \
                                           "Otherwise, keep empty to deliver to your own company.")
    currency_id = fields.Many2one('res.currency', 'Currency', required=True, states=READONLY_STATES, \
                                  default=lambda self: self.env.user.company_id.currency_id.id)

    # Piyush: code for adding new stage unawarded on 12-05-2020

    # state = fields.Selection([
    #     ('draft', 'Draft'),
    #     ('confirmed', 'Confirmed'),
    #     ('material_in', 'Material In'),
    #     ('to approve', 'To Approve'),
    #     ('short_close', 'Short Close'),
    #     ('to approve', 'To Approve'),
    #     ('purchase', 'Purchase Order'),
    #     ('done', 'Locked'),
    #     ('cancel', 'Cancelled')
    # ], string='Status', readonly=True, index=True, copy=False, default='draft', track_visibility='onchange')

    # Gaurav 5/6/20 changed the states and added short close
    state = fields.Selection([
        ('draft', 'Draft'),
        ('to approve', 'To Approve'),
        ('purchase', 'Purchase Order'),
        ('short_close', 'Short Close'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled')
    ], string='Status', readonly=True, index=True, copy=False, default='draft', track_visibility='onchange')
    # Gaurav end

    # code ends here

    order_line = fields.One2many('purchase.order.line', 'order_id', string='Order Lines',
                                 states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}, copy=True)
    notes = fields.Text('Terms and Conditions')

    # Piyush: fields added for job order menu on 30-05-2020

    copy_items = fields.Boolean(string="Copy Items", default=False)
    job_order = fields.Boolean("job order flag", default=False, help="Flag that differentiate JO and PO, True for JO")
    dispatch_through = fields.Text("Dispatch Through")
    expected_return_date = fields.Datetime("Expected Return Date")
    date_and_time_of_issue = fields.Datetime("Date and Time of Issue")
    material_line_ids = fields.One2many('material.out.line', 'material_line_id', string='Material Line')

    # code ends here

    invoice_count = fields.Integer(compute="_compute_invoice", string='# of Bills', copy=False, default=0, store=True)
    invoice_ids = fields.Many2many('account.invoice', compute="_compute_invoice", string='Bills', copy=False,
                                   store=True)
    invoice_status = fields.Selection([
        ('no', 'Nothing to Bill'),
        ('to invoice', 'Waiting Bills'),
        ('invoiced', 'No Bill to Receive'),
    ], string='Billing Status', compute='_get_invoiced', store=True, readonly=True, copy=False, default='no')

    picking_count = fields.Integer(compute='_compute_picking', string='Receptions', default=0, store=True,
                                   compute_sudo=True)
    picking_ids = fields.Many2many('stock.picking', compute='_compute_picking', string='Receptions', copy=False,
                                   store=True, compute_sudo=True)

    # There is no inverse function on purpose since the date may be different on each line
    date_planned = fields.Datetime(string='Scheduled Date', compute='_compute_date_planned', store=True, index=True)

    amount_untaxed = fields.Monetary(string='Untaxed Amount', store=True, readonly=True, compute='_amount_all',
                                     track_visibility='always')
    amount_tax = fields.Monetary(string='Taxes', store=True, readonly=True, compute='_amount_all')
    amount_total = fields.Monetary(string='Total', store=True, readonly=True, compute='_amount_all')

    fiscal_position_id = fields.Many2one('account.fiscal.position', string='Fiscal Position', oldname='fiscal_position')
    payment_term_id = fields.Many2one('account.payment.term', 'Payment Terms')
    incoterm_id = fields.Many2one('stock.incoterms', 'Incoterm', states={'done': [('readonly', True)]},
                                  help="International Commercial Terms are a series of predefined commercial terms used in international transactions.")

    product_id = fields.Many2one('product.product', related='order_line.product_id', string='Product')
    # Piyush: code added for making reference rfq new many2one from rfq model on 15-05-2020
    reference_rfq_new = fields.Many2one('request.for.quotation', string="Reference RFQ")

    # code ends here
    create_uid = fields.Many2one('res.users', 'Responsible')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, states=READONLY_STATES,
                                 default=lambda self: self.env.user.company_id.id)

    # Piyush: code for creating operation type for job_order menu on 11-06-2020

    picking_type_id_jo = fields.Many2one('stock.picking.type', 'Deliver To', states=READONLY_STATES, required=True,
                                         default=_default_picking_type_jo,
                                         help="This will determine operation type of outgoing shipment")

    default_location_dest_jo = fields.Many2one(related='picking_type_id_jo.default_location_dest_id',
                                               string='Destination Location',
                                               help="Technical field used to display the Drop Address",
                                               readonly=True)

    location_id_jo = fields.Many2one(related='picking_type_id_jo.default_location_src_id', string="Source Location",
                                     readonly=True, help="Technical field used to display the Ship Address")

    # code ends here

    picking_type_id = fields.Many2one('stock.picking.type', 'Deliver To', states=READONLY_STATES, required=True,
                                      default=_default_picking_type,
                                      help="This will determine operation type of incoming shipment")

    default_location_dest_id_usage = fields.Selection(related='picking_type_id.default_location_dest_id.usage',
                                                      string='Destination Location Type', \
                                                      help="Technical field used to display the Drop Ship Address",
                                                      readonly=True)
    group_id = fields.Many2one('procurement.group', string="Procurement Group", copy=False)
    is_shipped = fields.Boolean(compute="_compute_is_shipped")

    website_url = fields.Char(
        'Website URL', compute='_website_url',
        help='The full URL to access the document through the website.')

    # ravi at 14/2/2020 for adding a new field of order type
    order_type = fields.Selection([
        ('direct', 'Direct'),
        ('open', 'Open'),
        ('arc', 'Arc'),
    ], string='Order Type', copy=False, default='direct', track_visibility='onchange')

    start_date = fields.Date('Start Date', required=True, default=fields.Datetime.now,
                             help="Used for Order Scheduling Start Date in case of Open Order")
    end_date = fields.Date('End Date', required=True, default=fields.Datetime.now,
                           help="Used for Order Scheduling End Date in case of Open Order")
    # ravi end
    # Aman 30/07/2020 added delivery date field in purchase order form
    delivery_date = fields.Date('Delivery Date', help="Used to set delivery date manually")
    # Aman end
    # Gaurav 14/3/20 added default check on company gst register
    check_registered = fields.Boolean("Check Registered", store=True, default=False)
    check_order_line = fields.Boolean("Check Order Line", store=True, default=False)
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

    # Piyush: end date should be same as Agreement Deadline Date of PA 17-03-2020

    start_date = fields.Date('Start Date', required=True, default=fields.Datetime.now,
                             help="Used for Order Scheduling Start Date in case of Open Order")
    end_date = fields.Date('End Date', required=True, default=fields.Datetime.now,
                           help="Used for Order Scheduling End Date in case of Open Order")
    as_per_schedule = fields.Boolean('As Per Schedule', default=False)

    # piyush: code for adding rfq_reference and rfq_date on 12-05-2020
    date_rfq = fields.Datetime(string="RFQ Date", default=fields.Datetime.now, readonly=True)
    reference_rfq = fields.Many2one('purchase.order', string="Reference RFQ")
    # code ends here

    # Piyush: code for adding po_from_so on 04-07-2020
    po_from_so = fields.Boolean(string="Order from SO", default=False)
    # code ends here

    order_calculation_ids = fields.One2many('order.calculation', 'order_id', 'Order Calculation', compute='_compute_lines', store=True)
    
    # Yash Start - 18/12/2020 code for print purchase order
    remarks = fields.Text('Remarks')
    note = fields.Text('Notes')
    # Yash End

    # @api.multi
    # @api.onchange('order_line')
    # def onchange_order_l(self):
    @api.depends('order_line', 'order_line.taxes_id')
    def _compute_lines(self):
        self._amount_all()
        self.order_line._compute_amount()
        tax_dict = {}
        tax = {}
        amt = 0
        bamt = 0
        if self.order_line:
            for line in self.order_line:
                tax_dict = genric.check_line(line, line.taxes_id, line.order_id.currency_id, line.order_id.partner_id, line.product_qty)
                tax = Counter(tax_dict) + Counter(tax)
                print(tax)
                # Aman 24/11/2020 Calculated discounted amount to show on table
                if line.product_id:
                    price = line.product_qty * line.price_unit
                    if line.discount:
                        amt += price * (line.discount / 100)
                    bamt += price
                # Aman end
        charges_data_list = genric.detail_table(self, self.order_line, tax, amt, bamt, round_off = False)
        self.order_calculation_ids = [(5, 0, 0)]
        self.order_calculation_ids = charges_data_list


    # Piyush: code to copy material out items to material in on 30-05-2020
    # @api.onchange('copy_items')
    # def copy_item_values(self):
    #     self.order_line = ''
    #     for items in self:
    #         lines_list = []
    #         if items.material_line_ids:
    #             for lines in items.material_line_ids:
    #                 lines_dict = (0, False, {
    #                     'product_id': lines.product_id and lines.product_id.id or False,
    #                     'name': lines.product_id.name or '',
    #                     'product_qty': lines.product_qty or 0.0,
    #                     'qty_received': lines.qty_received or 0.0,
    #                     'product_uom': lines.product_uom and lines.product_uom.id or False,
    #                     'price_unit': lines.price_unit or 0.0,
    #                     'price_subtotal': lines.price_subtotal or 0.0,
    #                     'date_planned': lines.date_planned or fields.datetime.now(),
    #                 })
    #                 lines_list.append(lines_dict)
    #         items.order_line = lines_list

            # code ends here
# salman add hsn field
    @api.onchange('copy_items')
    def onchange_copy_to_in(self):
        self.order_line = ''
        lines_list = []
        if self.copy_items:
            if self.material_line_ids:
                for lines in self.material_line_ids:
                    lines_dict = (0, False, {
                        'product_id': lines.product_id and lines.product_id.id or False,
                        'hsn_id':lines.hsn_id,
                        'name': lines.product_id.name or '',
                        'product_qty': lines.product_qty or 0.0,
                        'qty_received': lines.qty_received or 0.0,
                        'product_uom': lines.product_uom and lines.product_uom.id or False,
                        'price_unit': lines.price_unit or 0.0,
                        'price_subtotal': lines.price_subtotal or 0.0,
                        'date_planned': lines.date_planned or fields.datetime.now(),
                    })
                    lines_list.append(lines_dict)
            self.order_line = lines_list

    # code ends here

    @api.onchange('reference_rfq')
    def _onchange_reference_rfq(self):
        self.order_line = ''
        for vals in self:
            if vals.reference_rfq:
                reference_rfq = vals.reference_rfq
                if vals.partner_id:
                    partner = vals.partner_id
                else:
                    partner = reference_rfq.partner_id
                payment_term = partner.property_supplier_payment_term_id
                currency = partner.property_purchase_currency_id or reference_rfq.company_id.currency_id
                FiscalPosition = self.env['account.fiscal.position']
                fpos = FiscalPosition.get_fiscal_position(partner.id)
                fpos = FiscalPosition.browse(fpos)

                vals.currency_id = currency.id

                origin = ''
                vals.origin = ''
                if not vals.origin or reference_rfq.name not in vals.origin.split(', '):
                    if vals.origin:
                        if reference_rfq.name:
                            vals.origin = vals.origin + ', ' + reference_rfq.name
                    else:
                        vals.origin = reference_rfq.name

                vals.start_date = reference_rfq.start_date or ''

                vals.picking_type_id = reference_rfq.picking_type_id.id

                # creating PO item lines

                order_lines = []
                for line in reference_rfq.order_line:
                    # Compute name
                    product_lang = line.product_id.with_context({
                        'lang': partner.lang,
                        'partner_id': partner.id,
                    })
                    name = product_lang.display_name
                    if product_lang.description_purchase:
                        name += '\n' + product_lang.description_purchase

                    # Compute taxes
                    # Jatin for vendor_tax_lines taxes 30-06-20
                    filter_tax = []
                    for val in line:
                        check = val.product_id.vendor_tax_lines
                        print("check", check)
                        for rec in check:
                            tax_check = rec.tax_id.id
                            print(tax_check)
                            filter_tax.append(tax_check)
                        print('filter_tax1', filter_tax)

                    print_tax = self.env['account.tax'].search([('id', 'in', filter_tax)])
                    print("print_tax", print_tax)
                    if fpos:
                        taxes_ids = fpos.map_tax(print_tax.filtered(
                            lambda tax: tax.company_id == reference_rfq.company_id)).ids
                    else:
                        taxes_ids = print_tax.filtered(
                            lambda tax: tax.company_id == reference_rfq.company_id).ids
                    # end jatin

                    # if fpos:
                    #     taxes_ids = fpos.map_tax(line.product_id.supplier_taxes_id.filtered(
                    #         lambda tax: tax.company_id == reference_rfq.company_id)).ids
                    # else:
                    #     taxes_ids = line.product_id.supplier_taxes_id.filtered(
                    #         lambda tax: tax.company_id == reference_rfq.company_id).ids

                    # Compute quantity and price_unit
                    if line.product_uom != line.product_id.uom_po_id:
                        product_qty = line.product_uom_id._compute_quantity(line.product_qty, line.product_id.uom_po_id)
                        price_unit = line.product_uom_id._compute_price(line.price_unit, line.product_id.uom_po_id)
                    else:
                        product_qty = line.product_qty
                        price_unit = line.price_unit

                    # Compute price_unit in appropriate currency
                    if reference_rfq.company_id.currency_id != currency:
                        price_unit = reference_rfq.company_id.currency_id.compute(price_unit, currency)

                    # Create PO line
                    order_line_values = line._prepare_purchase_order_line_rfq(
                        name=name, product_qty=product_qty, price_unit=price_unit,
                        taxes_ids=taxes_ids)
                    order_lines.append((0, 0, order_line_values))
                vals.order_line = order_lines

    # code ends here

    # code ends here


    def _website_url(self):
        for order in self:
            order.website_url = '/my/purchase/%s' % (order.id)

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('name', operator, name), ('partner_ref', operator, name)]
        pos = self.search(domain + args, limit=limit)
        return pos.name_get()

    @api.multi
    @api.depends('name', 'partner_ref')
    def name_get(self):
        result = []
        for po in self:
            name = po.name
            if po.partner_ref:
                name += ' (' + po.partner_ref + ')'
            if self.env.context.get('show_total_amount') and po.amount_total:
                name += ': ' + formatLang(self.env, po.amount_total, currency_obj=po.currency_id)
            result.append((po.id, name))
        return result

    # Aman 8/10/2020 Added function to add validation to check unit price and product quantity
    def check_price_qty(self, vals, price, quantity):
        list_len = len(vals['order_line'])
        for i in range(list_len):
            unit_price = vals['order_line'][i][2][price]
            product_qty = vals['order_line'][i][2][quantity]
            if unit_price == 0 or product_qty == 0:
                raise ValidationError(_("Unit Price and Product Quantity must be greater than zero!!"))
    # Aman end

    # Aman 26/12/2020 Added validations to check if Item without HSN code is last item
    # Aman 08/01/2021 commented the below function
    # @api.onchange('order_line')
    # def onchange_lines(self):
    #     genric.check_hsn_disable(self, self.order_line)
    # Aman end

    @api.model
    def create(self, vals):

        # Piyush: code for adding different sequence and checking for item in PO and JO on 02-05-2020
        # Aman 8/10/2020 Added a validation to check unit price and product quantity
        if 'order_line' in vals:
            quantity = 'product_qty'
            price = 'price_unit'
            self.check_price_qty(vals, price, quantity)
        # Aman end
        if 'job_order' in vals and vals.get('job_order'):
            if 'name' not in vals or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('job.order') or _('New')
            if 'order_line' not in vals or 'material_line_ids' not in vals:
                raise ValidationError(_("Cannot proceed without products at the item level!"))
        else:
            if 'name' not in vals or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('purchase.order') or '/'
            if 'order_line' not in vals and not vals.get('po_from_so'):
                raise ValidationError(_("Cannot proceed without products at the item level!"))
        # code ends here

        # ravi start at 29/1/2019 for creating vendors line in product form
        # if vals.get('order_line'):
        #     for line in vals.get('order_line'):
        #         print('linne product')
        #         supplier_info_line = self.env['product.supplierinfo'].search(('name', '=', vals.get('partner_id')), ('product_tmpl_id', '=', line.product_id.product_tmpl_id))
        #         if not supplier_info_line:
        #            self.env['product.supplierinfo'].create({'name' : vals.get('partner_id'),'product_tmpl_id':line.product_id.product_tmpl_id})
        # ravi end

        # return super(PurchaseOrder, self).create(vals)

        res = super(PurchaseOrder, self).create(vals)

        if res.order_line:
            for values in res.order_line:
                if values.product_id:
                    product_tmpl_id = values.product_id.product_tmpl_id.id
                    print('product_tmpl_id', product_tmpl_id)
                    self.env['product.template'].search(
                        [('company_id', '=', res.company_id.id), ('id', '=', product_tmpl_id)]).write(
                        {'product_transaction': True})

        # Piyush: code for preventing creation of PO without PO Lines 08-4-2020
        # if not res.order_line:
        #     raise UserError('Cannot proceed further without Products!')
        # code ends here

        # Piyush: code for validation of inhand qty while saving in job work challan on 13-06-2020
        # if res.material_line_ids:
        #     for val in res.material_line_ids:
        #         if val and val.product_id and val.product_id.tracking == 'none' and self.env.user.company_id.default_positive_stock:
        #             if val.product_qty > val.product_id.qty_available:
        #                 raise ValidationError(
        #                     'Cannot issue quantity more than available. For {} available quantity '
        #                     'is {} '.format(val.product_id.name, val.product_id.qty_available))
        #
        #     for val in res.material_line_ids:
        #         if val and val.product_id and val.product_id.tracking != 'none' and self.env.user.company_id.default_positive_stock:
        #             if val.lots_wise_ids.qty_done > val.lots_wise_ids.available_qty_lot:
        #                 raise ValidationError(
        #                     'Cannot issue quantity more than available. For {} the available quantity in the lot {} '
        #                     'is {} '.format(val.product_id.name, val.lots_wise_ids.lot_id.name, val.lots_wise_ids.available_qty_lot))
        # code ends here

        return res

    # ravi start at 20/1/2019 for overwriting write method to product transaction updation
    @api.multi
    def write(self, vals):
        result = super(PurchaseOrder, self).write(vals)

        # Piyush: code for order line check in PO and JO on 26-06-2020
        if self.job_order:
            if 'order_line' in vals or 'material_line_ids' in vals:
                if not self.order_line or not self.material_line_ids:
                    raise ValidationError(_("Cannot proceed without products at the item level!"))
        else:
            if 'order_line' in vals:
                if not self.order_line:
                    raise ValidationError(_("Cannot proceed without products at the item level!"))
        # code ends here

        if self.order_line:
            for values in self.order_line:
                if values.product_id:
                    product_tmpl_id = values.product_id.product_tmpl_id.id
                    print('product_tmpl_id', product_tmpl_id)
                    self.env['product.template'].search([('company_id', '=', self.company_id.id), ('id', '=', product_tmpl_id)]).write({'product_transaction': True})

            # Piyush: code for validation of inhand qty while saving in job work challan on 13-06-2020

        # if self.material_line_ids:
        #     for val in self.material_line_ids:
        #         if val and val.product_id and val.product_id.tracking == 'none' and self.env.user.company_id.default_positive_stock:
        #             if val.product_qty > val.product_id.qty_available:
        #                 raise ValidationError(
        #                     'Cannot issue quantity more than available. For {} available quantity '
        #                     'is {} '.format(val.product_id.name, val.product_id.qty_available))
        #
        #     for val in self.material_line_ids:
        #         if val and val.product_id and val.product_id.tracking != 'none' and self.env.user.company_id.default_positive_stock:
        #             if val.lots_wise_ids.qty_done > val.lots_wise_ids.available_qty_lot:
        #                 raise ValidationError(
        #                     'Cannot issue quantity more than available. For {} the available quantity in the lot {} '
        #                     'is {} '.format(val.product_id.name, val.lots_wise_ids.lot_id.name,
        #                                     val.lots_wise_ids.available_qty_lot))
                        # code ends here

        return result

    # ravi end

    @api.multi
    def unlink(self):
        for order in self:
            if not order.state == 'cancel':
                raise UserError(_('In order to delete a purchase order, you must cancel it first.'))
        return super(PurchaseOrder, self).unlink()

    @api.multi
    def copy(self, default=None):
        new_po = super(PurchaseOrder, self).copy(default=default)
        for line in new_po.order_line:
            seller = line.product_id._select_seller(
                partner_id=line.partner_id, quantity=line.product_qty,
                date=line.order_id.date_order and line.order_id.date_order[:10], uom_id=line.product_uom)
            line.date_planned = line._get_date_planned(seller)
        return new_po

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'state' in init_values and self.state == 'purchase':
            return 'purchase.mt_rfq_approved'
        elif 'state' in init_values and self.state == 'to approve':
            return 'purchase.mt_rfq_confirmed'
        elif 'state' in init_values and self.state == 'done':
            return 'purchase.mt_rfq_done'
        return super(PurchaseOrder, self)._track_subtype(init_values)

    @api.onchange('partner_id', 'company_id')
    def onchange_partner_id(self):
        if not self.partner_id:
            self.fiscal_position_id = False
            self.payment_term_id = False
            # Aman 30/07/2020 commented this line because currency id is changing on selection of vendor but we don't want it
            # self.currency_id = False
        else:
            self.fiscal_position_id = self.env['account.fiscal.position'].with_context(company_id=self.company_id.id).get_fiscal_position(self.partner_id.id)
            self.payment_term_id = self.partner_id.property_supplier_payment_term_id.id
            # Aman 30/07/2020 commented this line because currency id is changing on selection of vendor but we don't want it
            # self.currency_id = self.partner_id.property_purchase_currency_id.id or self.env.user.company_id.currency_id.id
        return {}

    @api.onchange('fiscal_position_id')
    def _compute_tax_id(self):
        """
        Trigger the recompute of the taxes if the fiscal position is changed on the PO.
        """
        #Jatin --this below line is removed because the _compute_tax_id() is giving default taxes to product without checking for the state on 06-07-2020
        for order in self:
            print("this below line is removed because the _compute_tax_id() is giving default taxes to product without checking for the state ")
            #order.order_line._compute_tax_id()

    @api.onchange('partner_id')
    def onchange_partner_id_warning(self):
        if not self.partner_id:
            return
        warning = {}
        title = False
        message = False

        partner = self.partner_id

        # If partner has no warning, check its company
        if partner.purchase_warn == 'no-message' and partner.parent_id:
            partner = partner.parent_id

        if partner.purchase_warn != 'no-message':
            # Block if partner only has warning but parent company is blocked
            if partner.purchase_warn != 'block' and partner.parent_id and partner.parent_id.purchase_warn == 'block':
                partner = partner.parent_id
            title = _("Warning for %s") % partner.name
            message = partner.purchase_warn_msg
            warning = {
                'title': title,
                'message': message
                }
            if partner.purchase_warn == 'block':
                self.update({'partner_id': False})
            return {'warning': warning}
        return {}

    @api.onchange('picking_type_id')
    def _onchange_picking_type_id(self):
        if self.picking_type_id.default_location_dest_id.usage != 'customer':
            self.dest_address_id = False

    @api.multi
    def action_rfq_send(self):
        '''
        This function opens a window to compose an email, with the edi purchase template message loaded by default
        '''
        self.ensure_one()
        ir_model_data = self.env['ir.model.data']
        try:
            if self.env.context.get('send_rfq', False):
                template_id = ir_model_data.get_object_reference('purchase', 'email_template_edi_purchase')[1]
            else:
                template_id = ir_model_data.get_object_reference('purchase', 'email_template_edi_purchase_done')[1]
        except ValueError:
            template_id = False
        try:
            compose_form_id = ir_model_data.get_object_reference('mail', 'email_compose_message_wizard_form')[1]
        except ValueError:
            compose_form_id = False
        ctx = dict(self.env.context or {})
        ctx.update({
            'default_model': 'purchase.order',
            'default_res_id': self.ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'custom_layout': "purchase.mail_template_data_notification_email_purchase_order",
            'purchase_mark_rfq_sent': True,
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
    def print_quotation(self):
        self.write({'state': "sent"})
        return self.env.ref('purchase.report_purchase_quotation').report_action(self)

    @api.multi
    def button_approve(self, force=False):
        self.write({'state': 'purchase', 'date_approve': fields.Date.context_today(self)})
        self._create_picking()
        self.filtered(
            lambda p: p.company_id.po_lock == 'lock').write({'state': 'done'})
        return {}

    @api.multi
    def button_draft(self):
        self.write({'state': 'draft'})
        return {}

    # Piyush: code for creating stock move dict on 11-06-2020

    #avinash: 26/09/20 Commentted becasue now I created small functions for this code

    # Piyush: code for creating stock move dict on 11-06-2020
    # @api.multi
    # # def _prepare_stock_move_out(self, line, picking):
    #     mov_list = []
    #     variant_id = line.product_id
    #
    #     # code for location_id
    #
    #     location_id_required = ''
    #     if self.location_id_jo:
    #         location_id_required = self.location_id_jo.id
    #     else:
    #         location_ids = self.env['stock.location'].search(
    #             [('name', '=', 'NewStock'), ('company_id', '=', self.env.user.company_id.id)])
    #         if location_ids:
    #             location_id_required = location_ids.id
    #
    #     # code for destination location
    #
    #     dest_location_id = ''
    #     if self.default_location_dest_jo:
    #         dest_location_id = self.default_location_dest_jo.id
    #     else:
    #         # avinash:05/09/20 Change name from 'issues' to 'Vendor' because because it creates problem in stock move.
    #         # Due to mismatch of name it do not get any destination location.
    #         # location_ids = self.env['stock.location'].search(
    #         #     [('name', '=', 'Issues'), ('company_id', '=', self.env.user.company_id.id)])
    #         location_ids = self.env['stock.location'].search(
    #             [('name', '=', 'Vendors')])
    #         #end avinash
    #         if location_ids:
    #             dest_location_id = location_ids.id
    #
    #         # stock for lot wise products
    #
    #     # print("loc = ",location_id_required, dest_location_id)
    #     if line.product_id.tracking in ['lot', 'serial']:
    #         print(line, line.product_id)
    #         res = {
    #             'product_id': variant_id.id or False,
    #             'name': line.product_id and line.product_id.name or '',
    #             'product_uom': variant_id.uom_id and variant_id.uom_id.id or False,
    #             'quantity_done': line.product_qty or 0.0,
    #             'location_id': location_id_required or False,
    #             'location_dest_id': dest_location_id or False,
    #             'picking_id': picking.id,
    #             'picking_type_id': picking.picking_type_id and picking.picking_type_id.id or False,
    #             'origin': line.product_id and line.product_id.name or '',
    #             'warehouse_id': picking.picking_type_id and picking.picking_type_id.warehouse_id and picking.picking_type_id.warehouse_id.id or False,
    #             'state': 'draft',
    #             #avinash -04/08/20 (Added)Passing this value to send stock move in done state otherwise it is in waiting sate
    #             'from_job_work': 'True',
    #             #end avinash
    #         }
    #
    #         if line:
    #             trk_line_list = []
    #             ret_qty_total = 0.0
    #             for trk_line in line:
    #                 # avinash - 04/08/20 Added for loop here so if a product have more than 1 lot then it also work
    #                 for lot in trk_line.lots_wise_ids:
    #                     each_lot_id = lot.lot_id.id
    #                   # end avinash
    #                 if trk_line.product_qty > 0.0:
    #                     trk_line_data = (0, False, {
    #                         'product_id': line.product_id and line.product_id.id or False,
    #                         'product_uom_id': line.product_uom and line.product_uom.id or False,
    #                         'location_dest_id': dest_location_id or False,
    #                         'location_id': location_id_required or False,
    #                         # avinash - 04/08/20 Updated the lot_id for each lot
    #                         # 'lot_id': trk_line.lots_wise_ids.lot_id and trk_line.lots_wise_ids.lot_id.id or False,
    #                         'lot_id': each_lot_id or False,
    #                         #end avinash
    #                         'product_uom_qty': 0.0,
    #                         'ordered_qty': 0.0,
    #                         'qty_done': trk_line.product_qty or 0.0,
    #                         'picking_id': picking.id or False,
    #                     })
    #                     trk_line_list.append(trk_line_data)
    #                     ret_qty_total += trk_line.product_qty
    #
    #             if trk_line_list:
    #                 res['move_line_ids'] = trk_line_list
    #                 res['product_uom_qty'] = ret_qty_total
    #                 res['quantity_done'] = ret_qty_total
    #                 mov_list.append(res)
    #
    #     if line.product_id.tracking == 'none':
    #
    #         res = {
    #             'product_id': variant_id.id or False,
    #             'name': line.product_id and line.product_id.name or '',
    #             'product_uom': variant_id.uom_id and variant_id.uom_id.id or False,
    #             'product_uom_qty': line.product_qty or 0.0,
    #             'quantity_done': line.product_qty or 0.0,
    #             'location_id': location_id_required or False,
    #             'location_dest_id': dest_location_id or False,
    #             'picking_id': picking.id,
    #             'picking_type_id': picking.picking_type_id and picking.picking_type_id.id or False,
    #             'origin': line.product_id and line.product_id.name or '',
    #             'warehouse_id': self.picking_type_id_jo and self.picking_type_id_jo.warehouse_id and self.picking_type_id.warehouse_id.id or False,
    #             'state': 'draft',
    #             # avinash -04/08/20 Passing this value to send stock move in done state otherwise it is in waiting sate
    #             'from_job_work': 'True',
    #             #end avinash
    #         }
    #         mov_list.append(res)
    #
    #     return mov_list

    # code ends here

    # avinash: 26/09/20 To get location id and location destination id
    def fetch_location_ids(self):
        location_id_required = ''

        if self.location_id_jo:
            location_id_required = self.location_id_jo.id
        else:
            location_ids = self.env['stock.location'].search([('name', '=', 'NewStock'), ('company_id', '=', self.env.user.company_id.id)])
            if location_ids:
                location_id_required = location_ids.id

        # code for destination location

        dest_location_id = ''
        if self.default_location_dest_jo:
            dest_location_id = self.default_location_dest_jo.id
        else:
            dest_ids = self.env['stock.location'].search([('name', '=', 'Vendors')])
            if dest_ids:
                dest_location_id = dest_ids.id

        return location_id_required, dest_location_id


    # avinash: 26/09/20 Prepare lot detail and create in stock move lines
    def create_lot_detail(self, product_line, move_id):
        location_id_required, dest_location_id = self.fetch_location_ids()
        if product_line.product_qty > 0.0:
            for lot_line in product_line.lots_wise_ids:
                each_lot_id = lot_line.lot_id.id
                lot_data = {
                    'product_id': product_line.product_id and product_line.product_id.id or False,
                    'product_uom_id': product_line.product_uom and product_line.product_uom.id or False,
                    'location_dest_id': dest_location_id or False,
                    'location_id': location_id_required or False,
                    'lot_id': each_lot_id or False,
                    'product_uom_qty': 0.0,
                    'ordered_qty': 0.0,
                    'qty_done': lot_line.qty_done or 0.0,
                }

                if move_id.move_line_ids[-1] and not move_id.move_line_ids[-1].lot_id:
                    move_id.move_line_ids[-1].write({'qty_done': lot_line.qty_done, 'lot_id': each_lot_id})
                else:
                    new = move_id.move_line_ids.create(lot_data)
                    new.update({'move_id': move_id.id})
        return {}

    # avinash: 26/09/20 Prepare product detail and return
    def prepare_product_detail(self, line, picking):
        variant_id = line.product_id
        location_id_required, dest_location_id = self.fetch_location_ids()

        res = {
            'product_id': variant_id.id or False,
            'name': line.product_id and line.product_id.name or '',
            'product_uom': variant_id.uom_id and variant_id.uom_id.id or False,
            'quantity_done': line.product_qty or 0.0,
            'location_id': location_id_required or False,
            'location_dest_id': dest_location_id or False,
            'picking_id': picking.id,
            'picking_type_id': picking.picking_type_id and picking.picking_type_id.id or False,
            # 'origin': line.product_id and line.product_id.name or '',
            'warehouse_id': picking.picking_type_id and picking.picking_type_id.warehouse_id and picking.picking_type_id.warehouse_id.id or False,
            'state': 'draft',
            # avinash -04/08/20 (Added)Passing this value to send stock move in done state otherwise it is in waiting sate
            'from_job_work': 'True',
            # end avinash
        }
        return res

    # avinash: 26/09/20 Calling all the related function for stock move out and return move id
    @api.multi
    def _prepare_stock_move_out(self, line, picking):
        val = self.prepare_product_detail(line, picking)
        move_id = self.env['stock.move'].create(val)
        track_type = self.env['account.invoice'].check_product_tracking(line)

        if track_type == ['lot', 'serial']:
            self.create_lot_detail(line, move_id)
        return move_id

    # end avinash

    # avinash: 15/10/20 Added so that same lot cannot be added again. To avoid negative stock
    def check_lot_detail_repeat(self, prod_line_ids):
        for each_prod_line in prod_line_ids:
            if self.env.context.get('active_model') == 'sale.order':
                all_lot = self.env['stock.move.line'].search([('move_id', '=', each_prod_line.id), ('product_id', '=', each_prod_line.product_id.id)])
            elif self.env.context.get('type') == 'out_invoice' and each_prod_line.invoice_id:
                all_lot = self.env['account.invoice.lot'].search([('invoice_no', '=', each_prod_line.invoice_id.id), ('product_id', '=', each_prod_line.product_id.id)])
            else:
                all_lot = self.env['lot.wise.item'].search([('lot_wise_id', '=', each_prod_line.id), ('product_id', '=', each_prod_line.product_id.id)])
            # print(all_lot)
            lot_list = []
            for each_lot in all_lot:
                if each_lot.lot_id.id not in lot_list:
                    lot_list.append(each_lot.lot_id.id)
                else:
                    raise ValidationError('{0} is added many times. For product {1}'.format(each_lot.lot_id.name, each_prod_line.product_id.name))

    # end avinash

    @api.multi
    def button_confirm(self):
        for order in self:
            if order.state not in ['draft', 'sent']:
                continue
            # Gaurav 6/5/20 commented function for overriding new created function in create(purchasedetail)
            # order._add_supplier_to_product()
            # Gaurav end
            # Deal with double validation process
            if order.company_id.po_double_validation == 'one_step'\
                    or (order.company_id.po_double_validation == 'two_step'\
                        and order.amount_total < self.env.user.company_id.currency_id.compute(order.company_id.po_double_validation_amount, order.currency_id))\
                    or order.user_has_groups('purchase.group_purchase_manager'):
                order.button_approve()
            else:
                order.write({'state': 'to approve'})
        if self.order_line:
            for line in self.order_line:
                supplier_info_line = self.env['product.supplierinfo'].search(
                    [('name', '=', self.partner_id.id), ('product_tmpl_id', '=', line.product_id.product_tmpl_id.id)])
                if not supplier_info_line:
                    self.env['product.supplierinfo'].create(
                        {'name': self.partner_id.id, 'product_tmpl_id': line.product_id.product_tmpl_id.id,
                         'price': line.price_unit})

        # Piyush: code for creating awarded function on 02-06-2020
        for chance in self:
            if chance.order_line:
                rfq_ids = self.env['request.for.quotation'].search([
                    ('id', '=', chance.reference_rfq_new.id),
                ])
                if rfq_ids:
                    for id_in in rfq_ids:
                        id_in.update({'rfq_state': 'purchase'})
        # code ends here

        # Piyush: code for creating stock move of job work challan on 10-06-2020

        for lot in self:
            if lot.state not in ['draft', 'sent']:
                print("state = ",lot.state)
                # avinash: 15/10/20 Added so that same lot cannot be added again. To avoid negative stock.
                self.check_lot_detail_repeat(lot.material_line_ids)
                # end avinash
                for line in lot.material_line_ids:
                    # print("JO picking_id = ",self.picking_type_id_jo)
                    picking = self.env['stock.picking']
                    if line.product_qty > 0.0:
                        res_move = self._prepare_stock_move_out(line, picking)
                        if res_move:
                            for val in res_move:
                                # avinash:27/09/20 Commented becasue now we take functional approach here and call action confirm
                                # and action done on the basis of move_id
                                # self.env['stock.move'].create(val)._action_confirm()._action_done()
                                res_move._action_confirm()._action_done()
                                # end avinash


        # code ends here

        # Piyush: code for creating unawarded function on 23-05-2020

        for change in self:
            if change.order_line:
                for awd in change.order_line:
                    linked_rfq = self.env['request.for.quotation.line'].search([
                        ('ref_rfq_line_id', '=', awd.ref_rfq_line_id.id),
                        ('product_id', '=', awd.product_id.id)])
                    rfq_ids_list = [rfq.rfq_id for rfq in linked_rfq]
                    if rfq_ids_list:
                        for true in rfq_ids_list:
                            qty_satisfied = all([ids.total_qty_ordered >= ids.product_qty for ids in true.rfq_line_ids])
                            if qty_satisfied:
                                if true.rfq_state != 'purchase':
                                    true.update({'rfq_state': 'unawarded'})
            # code ends here
        # Shivam code for changing state of purchase agreement to done(after order quantity meet agreement quantity)
        if self.requisition_id.type_id.type == 'open':
            n = 0

            for line in self.requisition_id.line_ids:
                print("req_q", line.product_qty)
                if line.qty_ordered == line.product_qty and line.product_qty != 0:
                    n = n + 1
                    print("#######shivam#######1")
                if n == len(self.requisition_id.line_ids):
                    self.requisition_id.write({'state': 'done'})
            # shivam code ends
            return True
        else:
            if self.requisition_id.order_value >= self.requisition_id.commitment_value:
                self.requisition_id.write({'state': 'done'})

        return True

    @api.multi
    def button_cancel(self):
        for order in self:
            for pick in order.picking_ids:
                if pick.state == 'done':
                    raise UserError(
                        _('Unable to cancel purchase order %s as some receptions have already been done.') % (
                            order.name))
            for inv in order.invoice_ids:
                if inv and inv.state not in ('cancel', 'draft'):
                    raise UserError(
                        _("Unable to cancel this purchase order. You must first cancel related vendor bills."))

            # If the product is MTO, change the procure_method of the the closest move to purchase to MTS.
            # The purpose is to link the po that the user will manually generate to the existing moves's chain.
            if order.state in ('draft', 'sent', 'to approve'):
                for order_line in order.order_line:
                    if order_line.move_dest_ids:
                        move_dest_ids = order_line.move_dest_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
                        siblings_states = (move_dest_ids.mapped('move_orig_ids')).mapped('state')
                        if all(state in ('done', 'cancel') for state in siblings_states):
                            move_dest_ids.write({'procure_method': 'make_to_stock'})
                            move_dest_ids._recompute_state()

            for pick in order.picking_ids.filtered(lambda r: r.state != 'cancel'):
                pick.action_cancel()

            order.order_line.write({'move_dest_ids': [(5, 0, 0)]})

        self.write({'state': 'cancel'})

    @api.multi
    def button_unlock(self):
        self.write({'state': 'purchase'})

    @api.multi
    def button_done(self):
        self.write({'state': 'done'})

    @api.multi
    def _get_destination_location(self):
        self.ensure_one()
        # avinash : 23/08/20 commented and add condition for destination location of PO generated from SO
        # When PO generate from SO By default it get destination location of customer from SO
        # if self.dest_address_id:
        #     return self.dest_address_id.property_stock_customer.id
        # return self.picking_type_id.default_location_dest_id.id
        if self.po_from_so:
            return self.picking_type_id.default_location_dest_id.id

        elif self.dest_address_id:
            return self.dest_address_id.property_stock_customer.id
        return self.picking_type_id.default_location_dest_id.id

    # end avinash

    @api.model
    def _prepare_picking(self):
        if not self.group_id:
            self.group_id = self.group_id.create({
                'name': self.name,
                'partner_id': self.partner_id.id
            })
        if not self.partner_id.property_stock_supplier.id:
            raise UserError(_("You must set a Vendor Location for this partner %s") % self.partner_id.name)
        return {
            'name':'New',
            'picking_type_id': self.picking_type_id.id,
            'partner_id': self.partner_id.id,
            'date': self.date_order,
            # Aman 07/11/2020 Added delivery date to receipt form
            'delivery_date': self.delivery_date,
            'origin': self.name,
            # Piyush: code for as_per_schedule and order_type field 23-04-2020
            'as_per_schedule': self.as_per_schedule,
            'order_type': self.order_type,
            # code ends here
            'purchase_id': self.id,
            'location_dest_id': self._get_destination_location(),
            'location_id': self.partner_id.property_stock_supplier.id,
            'company_id': self.company_id.id,
        }

    @api.multi
    def _create_picking(self):
        StockPicking = self.env['stock.picking']
        for order in self:
            if any([ptype in ['product', 'consu'] for ptype in order.order_line.mapped('product_id.type')]):
                pickings = order.picking_ids.filtered(lambda x: x.state not in ('done', 'cancel'))
                if not pickings:
                    res = order._prepare_picking()
                    picking = StockPicking.create(res)
                else:
                    picking = pickings[0]
                moves = order.order_line._create_stock_moves(picking)
                moves = moves.filtered(lambda x: x.state not in ('done', 'cancel'))._action_confirm()
                seq = 0
                for move in sorted(moves, key=lambda move: move.date_expected):
                    seq += 5
                    move.sequence = seq
                moves._action_assign()
                picking.message_post_with_view('mail.message_origin_link',
                                               values={'self': picking, 'origin': order},
                                               subtype_id=self.env.ref('mail.mt_note').id)
        return True

    @api.multi
    def _add_supplier_to_product(self):
        # Add the partner in the supplier list of the product if the supplier is not registered for
        # this product. We limit to 10 the number of suppliers for a product to avoid the mess that
        # could be caused for some generic products ("Miscellaneous").
        for line in self.order_line:
            # Do not add a contact as a supplier
            partner = self.partner_id if not self.partner_id.parent_id else self.partner_id.parent_id
            if partner not in line.product_id.seller_ids.mapped('name') and len(line.product_id.seller_ids) <= 10:
                # Convert the price in the right currency.
                currency = partner.property_purchase_currency_id or self.env.user.company_id.currency_id
                price = self.currency_id.compute(line.price_unit, currency, round=False)
                # Compute the price for the template's UoM, because the supplier's UoM is related to that UoM.
                if line.product_id.product_tmpl_id.uom_po_id != line.product_uom:
                    default_uom = line.product_id.product_tmpl_id.uom_po_id
                    price = line.product_uom._compute_price(price, default_uom)

                supplierinfo = {
                    'name': partner.id,
                    'sequence': max(
                        line.product_id.seller_ids.mapped('sequence')) + 1 if line.product_id.seller_ids else 1,
                    'min_qty': 0.0,
                    'price': price,
                    'currency_id': currency.id,
                    'delay': 0,
                }
                # In case the order partner is a contact address, a new supplierinfo is created on
                # the parent company. In this case, we keep the product name and code.
                seller = line.product_id._select_seller(
                    partner_id=line.partner_id,
                    quantity=line.product_qty,
                    date=line.order_id.date_order and line.order_id.date_order[:10],
                    uom_id=line.product_uom)
                if seller:
                    supplierinfo['product_name'] = seller.product_name
                    supplierinfo['product_code'] = seller.product_code
                vals = {
                    'seller_ids': [(0, 0, supplierinfo)],
                }
                try:
                    line.product_id.write(vals)
                except AccessError:  # no write access rights -> just ignore
                    break

    @api.multi
    def action_view_picking(self):
        '''
        This function returns an action that display existing picking orders of given purchase order ids.
        When only one found, show the picking immediately.
        '''
        # Gaurav 4/3/20 commenting and edit action of shipment button to show receipt not transfer
        # action = self.env.ref('stock.action_picking_tree_all')
        action = self.env.ref('stock.action_view_stock_reciept_picking_form')
        # Gaurav end
        result = action.read()[0]

        #override the context to get rid of the default filtering on operation type
        result['context'] = {}
        pick_ids = self.mapped('picking_ids')
        #choose the view_mode accordingly
        if not pick_ids or len(pick_ids) > 1:
            result['domain'] = "[('id','in',%s)]" % (pick_ids.ids)
        elif len(pick_ids) == 1:
            # Gaurav 4/3/20 commenting and edit form view of receipt of shipment button to show receipt not transfer
            # res = self.env.ref('stock.view_picking_form', False)
            res = self.env.ref('stock.view_reciept_picking_form', False)
            # Gaurav end

            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = pick_ids.id
        return result

    @api.multi
    def action_view_invoice(self):
        '''
        This function returns an action that display existing vendor bills of given purchase order ids.
        When only one found, show the vendor bill immediately.
        '''
        action = self.env.ref('account.action_invoice_tree2')
        result = action.read()[0]

        #override the context to get rid of the default filtering
        result['context'] = {'type': 'in_invoice', 'default_purchase_id': self.id}

        if not self.invoice_ids:
            # Choose a default account journal in the same currency in case a new invoice is created
            journal_domain = [
                ('type', '=', 'purchase'),
                ('company_id', '=', self.company_id.id),
                ('currency_id', '=', self.currency_id.id),
            ]
            default_journal_id = self.env['account.journal'].search(journal_domain, limit=1)
            if default_journal_id:
                result['context']['default_journal_id'] = default_journal_id.id
        else:
            # Use the same account journal than a previous invoice
            result['context']['default_journal_id'] = self.invoice_ids[0].journal_id.id

        #choose the view_mode accordingly
        if len(self.invoice_ids) != 1:
            result['domain'] = "[('id', 'in', " + str(self.invoice_ids.ids) + ")]"
        elif len(self.invoice_ids) == 1:
            res = self.env.ref('account.invoice_supplier_form', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = self.invoice_ids.id
        result['context']['default_origin'] = self.name
        result['context']['default_reference'] = self.partner_ref
        return result

    @api.multi
    def action_set_date_planned(self):
        for order in self:
            order.order_line.update({'date_planned': order.date_planned})


class PurchaseOrderLine(models.Model):
    _name = 'purchase.order.line'
    _description = 'Purchase Order Line'
    _order = 'order_id, sequence, id'

    # Shivam code for checking order quantity with agreement quantity
    @api.onchange('product_qty')
    def check_quant(self):
        print("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@", self.order_id.requisition_id.type_id)
        if self.order_id.requisition_id.type_id.type == 'Open Order':
            for line in self.order_id.requisition_id.line_ids:
                if self.product_id == line.product_id:
                    print("req_q", line.product_qty)
                    print("product_q", line.product_qty, line.qty_ordered)
                    balance_quantity = line.product_qty - line.qty_ordered
                    if self.product_qty > balance_quantity:
                        raise UserError(_('You can not order quantities more than the agreement quantities'))

    # Shivam Code Ends

    # Piyush: code for sending vals in RFQ on basis of RFQ reference on 12-05-2020
    @api.multi
    def _prepare_purchase_order_line_rfq(self, name, product_qty=0.0, price_unit=0.0, taxes_ids=False):
        self.ensure_one()
        order_id = self.order_id
        return {
            'name': name,
            'product_id': self.product_id.id,
            'product_uom': self.product_id.uom_po_id.id,
            'product_qty': product_qty,
            'price_unit': price_unit,
            'taxes_id': [(6, 0, taxes_ids)],
            'date_planned': order_id.date_planned or fields.Date.today(),
            'account_analytic_id': self.account_analytic_id.id,
            'move_dest_ids': self.move_dest_ids and [(4, self.move_dest_id.id)] or []
        }
    # code ends here

    @api.depends('product_qty', 'price_unit', 'taxes_id')
    def _compute_amount(self):
        for line in self:
            price_unit = line.price_unit * (1.0 - line.discount / 100.0)
            taxes = line.taxes_id.compute_all(price_unit, line.order_id.currency_id, line.product_qty,
                                              product=line.product_id, partner=line.order_id.partner_id)
            # taxes = line.taxes_id.compute_all(line.price_unit, line.order_id.currency_id, line.product_qty,
            #                                   product=line.product_id, partner=line.order_id.partner_id)
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })

    @api.multi
    def _compute_tax_id(self):
        for line in self:
            fpos = line.order_id.fiscal_position_id or line.order_id.partner_id.property_account_position_id
            # If company_id is set, always filter taxes by the company
            # by jatin for hsn taxes 30-06-20
            filter_tax = []
            for val in line:
                check = val.product_id.vendor_tax_lines
                print("check", check)
                for rec in check:
                    tax_check = rec.tax_id.id
                    print(tax_check)
                    filter_tax.append(tax_check)
                print('filter_tax2', filter_tax)

            print_tax = self.env['account.tax'].search([('id', 'in', filter_tax)])
            print("print_tax", print_tax)
            # end jatin
            taxes = print_tax.filtered(
                lambda r: not line.company_id or r.company_id == line.company_id)
            line.taxes_id = fpos.map_tax(taxes, line.product_id, line.order_id.partner_id) if fpos else taxes

    @api.depends('invoice_lines.invoice_id.state', 'invoice_lines.quantity', 'invoice_lines.uom_id')
    def _compute_qty_invoiced(self):
        for line in self:
            qty = 0.0
            for inv_line in line.invoice_lines:
                if inv_line.invoice_id.state not in ['cancel']:
                    if inv_line.invoice_id.type == 'in_invoice':
                        qty += inv_line.uom_id._compute_quantity(inv_line.quantity, line.product_uom)
                    elif inv_line.invoice_id.type == 'in_refund':
                        qty -= inv_line.uom_id._compute_quantity(inv_line.quantity, line.product_uom)
            line.qty_invoiced = qty

    @api.depends('order_id.state', 'move_ids.state', 'move_ids.product_uom_qty')
    def _compute_qty_received(self):
        for line in self:
            if line.order_id.state not in ['purchase', 'done']:
                line.qty_received = 0.0
                continue
            if line.product_id.type not in ['consu', 'product']:
                line.qty_received = line.product_qty
                continue
            total = 0.0
            for move in line.move_ids:
                if move.state == 'done':
                    if move.location_dest_id.usage == "supplier":
                        if move.to_refund:
                            total -= move.product_uom._compute_quantity(move.product_uom_qty, line.product_uom)
                    elif move.origin_returned_move_id._is_dropshipped() and not move._is_dropshipped_returned():
                        # Edge case: the dropship is returned to the stock, no to the supplier.
                        # In this case, the received quantity on the PO is set although we didn't
                        # receive the product physically in our stock. To avoid counting the
                        # quantity twice, we do nothing.
                        pass
                    else:
                        total += move.product_uom._compute_quantity(move.product_uom_qty, line.product_uom)
            line.qty_received = total

    @api.model
    def create(self, values):
        line = super(PurchaseOrderLine, self).create(values)

        # Aman 1/08/2020 Commented this line so that item could not get saved in receipt form on save
        if line.order_id.state == 'purchase':
            # line._create_or_update_picking()
            msg = _("Extra line with %s ") % (line.product_id.display_name,)
            line.order_id.message_post(body=msg)
            # Aman end

        #  Gaurav 24/4/20 added code for updating the product / variant detail (product/variant master)
        # pol = self.env['purchase.order.line']
        for product in line:
            if product.product_id:
                purchasedetail = self.env['product.supplierinfo']

                ppd = purchasedetail.search([('name', '=', product.order_id.partner_id.id),
                                             ('product_id', '=', product.product_id.id),
                                             ('company_id', '=', self.env.user.company_id.id)])
                # print("saledetail---", saledetail, saledetail.product_id, ppd)
                if ppd:
                    diff_price = product.price_unit - ppd.price
                    ppd.update({'sequence_ref': product.order_id.name,
                                'date': product.order_id.date_order,
                                'name': product.order_id.partner_id.id,
                                'product_quantity': product.product_qty,
                                'price': product.price_unit,
                                'price_diff': diff_price,
                                })
                else:
                    purchasedetail.create({'sequence_ref': product.order_id.name,
                                           'date': product.order_id.date_order,
                                           'name': product.order_id.partner_id.id,
                                           'product_id': product.product_id.id,
                                           'product_tmpl_id': product.product_id.product_tmpl_id.id,
                                           'product_quantity': product.product_qty,
                                           'price': product.price_unit,
                                           'price_diff': 0.0,
                                           })
                    #             Gaurav end
        return line

    @api.multi
    def write(self, values):
        if 'product_qty' in values:
            for line in self:
                if line.order_id.state == 'purchase':
                    line.order_id.message_post_with_view('purchase.track_po_line_template',
                                                         values={'line': line, 'product_qty': values['product_qty']},
                                                         subtype_id=self.env.ref('mail.mt_note').id)
        result = super(PurchaseOrderLine, self).write(values)
        # Update expected date of corresponding moves
        if 'date_planned' in values:
            self.env['stock.move'].search([
                ('purchase_line_id', 'in', self.ids), ('state', '!=', 'done')
            ]).write({'date_expected': values['date_planned']})
        # Aman 30/07/2020 Commented these lines Since move line was creating on save button
        # if 'product_qty' in values:
        #     self.filtered(lambda l: l.order_id.state == 'purchase')._create_or_update_picking()
        # Aman end

        #  Gaurav 24/4/20 added code for updating the product / variant detail (product/variant master)
        # pol = self.env['purchase.order.line']
        for product in self:
            print("product-----", product, product.id, product.state)
            diff_price = 0
            if product.product_id:
                purchasedetail = self.env['product.supplierinfo']

                ppd = purchasedetail.search([('name', '=', product.order_id.partner_id.id),
                                             ('product_id', '=', product.product_id.id),
                                             ('company_id', '=', self.env.user.company_id.id)])
                # print("saledetail---", saledetail, saledetail.product_id, ppd)
                if ppd:
                    if 'price_unit' in values:
                        diff_price = product.price_unit - ppd.price
                        ppd.update({'sequence_ref': product.order_id.name,
                                    'date': product.order_id.date_order,
                                    'name': product.order_id.partner_id.id,
                                    'product_quantity': product.product_qty,
                                    'price': product.price_unit,
                                    'price_diff': diff_price,
                                    })
                    elif 'product_qty' in values:

                        ppd.update({'sequence_ref': product.order_id.name,
                                    'date': product.order_id.date_order,
                                    'name': product.order_id.partner_id.id,
                                    'product_quantity': product.product_qty,
                                    'price': product.price_unit,

                                    })
                else:
                    purchasedetail.create({'sequence_ref': product.order_id.name,
                                           'date': product.order_id.date_order,
                                           'name': product.order_id.partner_id.id,
                                           'product_id': product.product_id.id,
                                           'product_tmpl_id': product.product_id.product_tmpl_id.id,
                                           'product_quantity': product.product_qty,
                                           'price': product.price_unit,
                                           'price_diff': 0.0,
                                           })
        #             Gaurav end

        return result
        # Salman add Hsn field
    hsn_id=fields.Char(string='HSN code')
    # Salman end
    name = fields.Text(string='Description', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    product_qty = fields.Float(string='Quantity', digits=dp.get_precision('Product Unit of Measure'), required=True)
    date_planned = fields.Datetime(string='Scheduled Date', index=True)
    taxes_id = fields.Many2many('account.tax', string='Taxes',
                                domain=['|', ('active', '=', False), ('active', '=', True)])
    product_uom = fields.Many2one('product.uom', string='Product Unit of Measure', required=True)
    product_id = fields.Many2one('product.product', string='Product', domain=[('purchase_ok', '=', True)],
                                 change_default=True, required=True)
    product_image = fields.Binary(
        'Product Image', related="product_id.image",
        help="Non-stored related field to allow portal user to see the image of the product he has ordered")
    move_ids = fields.One2many('stock.move', 'purchase_line_id', string='Reservation', readonly=True,
                               ondelete='set null', copy=False)
    price_unit = fields.Float(string='Unit Price', required=True, digits=dp.get_precision('Product Price'))

    price_subtotal = fields.Monetary(compute='_compute_amount', string='Subtotal', store=True)
    price_total = fields.Monetary(compute='_compute_amount', string='Total', store=True)
    price_tax = fields.Float(compute='_compute_amount', string='Tax', store=True)

    order_id = fields.Many2one('purchase.order', string='Order Reference', index=True, required=True,
                               ondelete='cascade')
    # Piyush: code for adding rfq_id to connect p.o.l and r.f.q.l on 15-05-2020
    ref_rfq_line_id = fields.Many2one('request.for.quotation.line', string="REF RFQ line",  store=True)
    rfq_id = fields.Many2one(related="order_id.reference_rfq_new", string="RFQ ID",  store=True)

    # code ends here
    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Analytic Tags')
    company_id = fields.Many2one('res.company', related='order_id.company_id', string='Company', store=True,
                                 readonly=True)
    state = fields.Selection(related='order_id.state', store=True)

    invoice_lines = fields.One2many('account.invoice.line', 'purchase_line_id', string="Bill Lines", readonly=True,
                                    copy=False)

    # Replace by invoiced Qty
    qty_invoiced = fields.Float(compute='_compute_qty_invoiced', string="Billed Qty",
                                digits=dp.get_precision('Product Unit of Measure'), store=True)
    qty_received = fields.Float(compute='_compute_qty_received', string="Received Qty",
                                digits=dp.get_precision('Product Unit of Measure'), store=True, compute_sudo=True)

    # Piyush: code for adding ordered qty field on 12-05-2020
    qty_ordered = fields.Float(string="Ordered Qty",
                               digits=dp.get_precision('Product Unit of Measure'), store=True)
    # code ends here

    partner_id = fields.Many2one('res.partner', related='order_id.partner_id', string='Partner', readonly=True,
                                 store=True)
    currency_id = fields.Many2one(related='order_id.currency_id', store=True, string='Currency', readonly=True)
    date_order = fields.Datetime(related='order_id.date_order', string='Order Date', readonly=True)

    orderpoint_id = fields.Many2one('stock.warehouse.orderpoint', 'Orderpoint')
    move_dest_ids = fields.One2many('stock.move', 'created_purchase_line_id', 'Downstream Moves')
    # Aman 24/11/2020 Added discount field
    discount = fields.Float(string='Discount (%)', digits=dp.get_precision('Discount'), default=0.0)

    @api.multi
    def _create_or_update_picking(self):
        for line in self:
            if line.product_id.type in ('product', 'consu'):
                # Prevent decreasing below received quantity
                if float_compare(line.product_qty, line.qty_received, line.product_uom.rounding) < 0:
                    raise UserError('You cannot decrease the ordered quantity below the received quantity.\n'
                                    'Create a return first.')

                if float_compare(line.product_qty, line.qty_invoiced, line.product_uom.rounding) == -1:
                    # If the quantity is now below the invoiced quantity, create an activity on the vendor bill
                    # inviting the user to create a refund.
                    activity = self.env['mail.activity'].sudo().create({
                        'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                        'note': _(
                            'The quantities on your purchase order indicate less than billed. You should ask for a refund. '),
                        'res_id': line.invoice_lines[0].invoice_id.id,
                        'res_model_id': self.env.ref('account.model_account_invoice').id,
                    })
                    activity._onchange_activity_type_id()

                # If the user increased quantity of existing line or created a new line
                pickings = line.order_id.picking_ids.filtered(
                    lambda x: x.state not in ('done', 'cancel') and x.location_dest_id.usage in ('internal', 'transit'))
                # Aman 30/07/2020 picking should be latest so that product selected should go to New BO receipt
                print('-------------------:', pickings[-1], pickings[0])
                # picking = pickings and pickings[0] or False
                picking = pickings and pickings[-1] or False
                # Aman end
                if not picking:
                    res = line.order_id._prepare_picking()
                    picking = self.env['stock.picking'].create(res)
                move_vals = line._prepare_stock_moves(picking)
                for move_val in move_vals:
                    self.env['stock.move']\
                        .create(move_val)\
                        ._action_confirm()\
                        ._action_assign()

    @api.multi
    def _get_stock_move_price_unit(self):
        self.ensure_one()
        line = self[0]
        order = line.order_id
        price_unit = line.price_unit
        if line.taxes_id:
            price_unit = line.taxes_id.with_context(round=False).compute_all(
                price_unit, currency=line.order_id.currency_id, quantity=1.0, product=line.product_id,
                partner=line.order_id.partner_id
            )['total_excluded']
        if line.product_uom.id != line.product_id.uom_id.id:
            price_unit *= line.product_uom.factor / line.product_id.uom_id.factor
        if order.currency_id != order.company_id.currency_id:
            price_unit = order.currency_id.with_context(date=order.date_approve).compute(price_unit,
                                                                                         order.company_id.currency_id,
                                                                                         round=False)
        return price_unit

    @api.multi
    def _prepare_stock_moves(self, picking):
        """ Prepare the stock moves data for one order line. This function returns a list of
        dictionary ready to be used in stock.move's create()
        """
        self.ensure_one()
        res = []
        if self.product_id.type not in ['product', 'consu']:
            return res
        qty = 0.0
        price_unit = self._get_stock_move_price_unit()
        for move in self.move_ids.filtered(lambda x: x.state != 'cancel' and not x.location_dest_id.usage == "supplier"):
            qty += move.product_uom._compute_quantity(move.product_uom_qty, self.product_uom, rounding_method='HALF-UP')
        template = {
            # truncate to 2000 to avoid triggering index limit error
            # TODO: remove index in master?
            'name': (self.name or '')[:2000],
            'product_id': self.product_id.id,
            'product_uom': self.product_uom.id,
            'date': self.order_id.date_approve,
            'date_expected': self.date_planned,
            'location_id': self.order_id.partner_id.property_stock_supplier.id,
            'location_dest_id': self.order_id._get_destination_location(),
            'picking_id': picking.id,
            'partner_id': self.order_id.dest_address_id.id,
            'move_dest_ids': [(4, x) for x in self.move_dest_ids.ids],
            'state': 'draft',
            'purchase_line_id': self.id,
            'company_id': self.order_id.company_id.id,
            'price_unit': price_unit,
            'picking_type_id': self.order_id.picking_type_id.id,
            'group_id': self.order_id.group_id.id,
            'origin': self.order_id.name,
            'route_ids': self.order_id.picking_type_id.warehouse_id and [(6, 0, [x.id for x in self.order_id.picking_type_id.warehouse_id.route_ids])] or [],
            'warehouse_id': self.order_id.picking_type_id.warehouse_id.id,
        }
        diff_quantity = self.product_qty - qty
        if float_compare(diff_quantity, 0.0,  precision_rounding=self.product_uom.rounding) > 0:
            quant_uom = self.product_id.uom_id
            get_param = self.env['ir.config_parameter'].sudo().get_param
            if self.product_uom.id != quant_uom.id and get_param('stock.propagate_uom') != '1':
                product_qty = self.product_uom._compute_quantity(diff_quantity, quant_uom, rounding_method='HALF-UP')
                template['product_uom'] = quant_uom.id
                template['product_uom_qty'] = product_qty
            else:
                template['product_uom_qty'] = diff_quantity
            res.append(template)
        return res

    @api.multi
    def _create_stock_moves(self, picking):
        moves = self.env['stock.move']
        done = self.env['stock.move'].browse()
        with self.env.norecompute():
            for line in self:
                for val in line._prepare_stock_moves(picking):
                    done += moves.create(val)
        self.recompute()
        return done

    @api.multi
    def unlink(self):
        for line in self:
            if line.order_id.state in ['purchase', 'done']:
                raise UserError(_('Cannot delete a purchase order line which is in state \'%s\'.') %(line.state,))
        return super(PurchaseOrderLine, self).unlink()

    @api.model
    def _get_date_planned(self, seller, po=False):
        """Return the datetime value to use as Schedule Date (``date_planned``) for
           PO Lines that correspond to the given product.seller_ids,
           when ordered at `date_order_str`.

           :param Model seller: used to fetch the delivery delay (if no seller
                                is provided, the delay is 0)
           :param Model po: purchase.order, necessary only if the PO line is 
                            not yet attached to a PO.
           :rtype: datetime
           :return: desired Schedule Date for the PO line
        """
        date_order = po.date_order if po else self.order_id.date_order
        if date_order:
            return datetime.strptime(date_order, DEFAULT_SERVER_DATETIME_FORMAT) + relativedelta(days=seller.delay if seller else 0)
        else:
            return datetime.today() + relativedelta(days=seller.delay if seller else 0)

    def _merge_in_existing_line(self, product_id, product_qty, product_uom, location_id, name, origin, values):
        """ This function purpose is to be override with the purpose to forbide _run_buy  method
        to merge a new po line in an existing one.
        """
        return True

    # Jatin to get taxes based on vendor_tax_lines 30-06-2020
    def taxes_of_vendor_tax_lines(self):
        filter_tax = []
        for val in self:
            check = val.product_id.vendor_tax_lines
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

    # Gaurav 13/3/20 commented and added GST validation code for RFQ and purchase order

    def _compute_purchase_tax(self):

        # Getting default taxes
        fpos = self.order_id.fiscal_position_id
        if self.env.uid == SUPERUSER_ID:
            print("purchase super")
            company_id = self.env.user.company_id.id
            # by jatin to get taxes based on hsn 30-06-2020
            print_tax = self.taxes_of_vendor_tax_lines()
            taxes_id = fpos.map_tax(
                print_tax.filtered(lambda r: r.company_id.id == company_id))
            # end jatin

            # taxes_id = fpos.map_tax(
            #     self.product_id.supplier_taxes_id.filtered(lambda r: r.company_id.id == company_id))

            print("self.taxes_iddddddd", taxes_id, self.partner_id.id)
            taxes_ids_list = taxes_id.ids


            # Gaurav 12/3/20 added code for default tax state wise
            check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
            check_custmr_state = self.env['res.partner'].search(
                [('id', '=', self.partner_id.id), ('company_id', '=', self.env.user.company_id.id)])
            print("purchase checkingggggggggggg",check_custmr_state.state_id,check_cmpy_state.state_id)

            if check_cmpy_state.state_id == check_custmr_state.state_id:
                print("same state")
                self.env.cr.execute(
                    """ select id from account_tax where active=True and type_tax_use='purchase' AND tax_group_id not in (2,3) and company_id='%s'""" % (
                        self.env.user.company_id.id,))
                csgst_taxes = self.env.cr.dictfetchall()
                print("csgst_taxesvvvvvvvvvvvvvvvv", csgst_taxes)
                tax_id_list = [taxes_ids_list.remove(val.get('id')) for val in csgst_taxes if
                               val.get('id') in taxes_ids_list if csgst_taxes]
                # tax_list = []
                # tax_id_list = [tax.id for tax in taxes_id]
                # if igst_taxes:
                #     for val in igst_taxes:
                #         tax_detail_id = val.get('id')
                #         tax_list.append(tax_detail_id)
                #
                # for value in tax_id_list:
                #     if value in tax_list:
                #         tax_id_list.remove(value)
                #         print(tax_id_list)
                print("purchase finalvvvvvvvvvvvvvvvv", taxes_ids_list)

                self.taxes_id = taxes_ids_list

            elif check_cmpy_state.state_id != check_custmr_state.state_id:
                print("diff state")

                self.env.cr.execute(
                    """ select id from account_tax where active=True and type_tax_use='purchase' AND tax_group_id!=4 and company_id='%s'""" % (
                        self.env.user.company_id.id,))
                igst_taxes = self.env.cr.dictfetchall()
                tax_id_list = [taxes_ids_list.remove(val.get('id')) for val in igst_taxes if val.get('id') in taxes_ids_list if igst_taxes]
                # tax_list = []
                # tax_id_list = [tax.id for tax in taxes_id]
                # if igst_taxes:
                #     for val in igst_taxes:
                #         tax_detail_id = val.get('id')
                #         tax_list.append(tax_detail_id)
                #
                # for value in tax_id_list:
                #     if value in tax_list:
                #         tax_id_list.remove(value)
                #         print(tax_id_list)
                print("purchase finalvvvvvvvvvvvvvvvv", taxes_ids_list)

                self.taxes_id = taxes_ids_list

            result= {'domain': {'taxes_id': [tax_id_list]}}
            # result= {'domain': {'taxes_id': [tax_id_list], 'type_tax_use': 'purchase'}}


        else:
            print("normal")
            # JAtin for vendor_tax_lines taxes on 02-07-2020
            print_tax = self.taxes_of_vendor_tax_lines()
            taxes_id = fpos.map_tax(print_tax)
            # end jatin
            #taxes_id = fpos.map_tax(self.product_id.supplier_taxes_id)

            print(" purchase self.taxes_iddddddd", taxes_id)
            taxes_ids_list = taxes_id.ids

            # Gaurav 12/3/20 added code for default tax state wise
            check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
            check_custmr_state = self.env['res.partner'].search(
                [('id', '=', self.partner_id.id), ('company_id', '=', self.env.user.company_id.id)])
            print("purchase checkingggggggggggg", check_custmr_state.state_id, check_cmpy_state.state_id)

            if check_cmpy_state.state_id == check_custmr_state.state_id:
                print("same state")
                self.env.cr.execute(
                    """ select id from account_tax where active=True and type_tax_use='purchase' AND tax_group_id not in (2,3) and company_id='%s'""" % (
                        self.env.user.company_id.id,))
                csgst_taxes = self.env.cr.dictfetchall()
                print("csgst_taxesvvvvvvvvvvvvvvvv", csgst_taxes)
                tax_id_list = [taxes_ids_list.remove(val.get('id')) for val in csgst_taxes if
                               val.get('id') in taxes_ids_list if csgst_taxes]
                # tax_list = []
                # tax_id_list = [tax.id for tax in taxes_id]
                # if igst_taxes:
                #     for val in igst_taxes:
                #         tax_detail_id = val.get('id')
                #         tax_list.append(tax_detail_id)
                #
                # for value in tax_id_list:
                #     if value in tax_list:
                #         tax_id_list.remove(value)
                #         print(tax_id_list)
                print("purchase finalvvvvvvvvvvvvvvvv", taxes_ids_list)

                self.taxes_id = taxes_ids_list

            elif check_cmpy_state.state_id != check_custmr_state.state_id:
                print("diff state")

                self.env.cr.execute(
                    """ select id from account_tax where active=True and type_tax_use='purchase' AND tax_group_id!=4 and company_id='%s'""" % (
                        self.env.user.company_id.id,))
                igst_taxes = self.env.cr.dictfetchall()
                tax_id_list = [taxes_ids_list.remove(val.get('id')) for val in igst_taxes if val.get('id') in taxes_ids_list if igst_taxes]
                # tax_list = []
                # tax_id_list = [tax.id for tax in taxes_id]
                # if igst_taxes:
                #     for val in igst_taxes:
                #         tax_detail_id = val.get('id')
                #         tax_list.append(tax_detail_id)
                #
                # for value in tax_id_list:
                #     if value in tax_list:
                #         tax_id_list.remove(value)
                #         print(tax_id_list)
                print("purchase finalvvvvvvvvvvvvvvvv", taxes_ids_list)

                self.taxes_id = taxes_ids_list

            result= {'domain': {'taxes_id': [tax_id_list]}}
            # result= {'domain': {'taxes_id': [tax_id_list], 'type_tax_use': 'purchase'}}
        return result

    # @api.onchange('product_id')
    # def onchange_product_id(self):
    #     result = {}
    #     if not self.product_id:
    #         return result
    #
    #     # Reset date, price and quantity since _onchange_quantity will provide default values
    #     self.date_planned = datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
    #     self.price_unit = self.product_qty = 0.0
    #     self.product_uom = self.product_id.uom_po_id or self.product_id.uom_id
    #     result['domain'] = {'product_uom': [('category_id', '=', self.product_id.uom_id.category_id.id)]}
    #
    #     product_lang = self.product_id.with_context(
    #         lang=self.partner_id.lang,
    #         partner_id=self.partner_id.id,
    #     )
    #     self.name = product_lang.display_name
    #     if product_lang.description_purchase:
    #         self.name += '\n' + product_lang.description_purchase
    #
    #     fpos = self.order_id.fiscal_position_id
    #     if self.env.uid == SUPERUSER_ID:
    #         company_id = self.env.user.company_id.id
    #         self.taxes_id = fpos.map_tax(self.product_id.supplier_taxes_id.filtered(lambda r: r.company_id.id == company_id))
    #     else:
    #         self.taxes_id = fpos.map_tax(self.product_id.supplier_taxes_id)
    #
    #     self._suggest_quantity()
    #     self._onchange_quantity()
    #
    #     return result
    # Gaurav starts


    # Aman 30/07/2020 Warning for user to select vendor before selecting product
    @api.onchange('product_id')
    def onchange_product(self):
        part = self.partner_id
        print('part: ', part);
        if not part:
            warning = {
                'title': _('Warning!!'),
                'message': _('You must select Vendor first!!'),
            }
            return {'warning': warning}
       #salman add hsn_id value
        self.hsn_id=self.product_id.hsn_id.hsn_code
       #salman end     
    # Aman end --------------------------
    @api.onchange('product_id')
    def _onchange_product_id(self):
        # Aman 24/12/2020 Added condition and user error to check if product with
        # hsn_disable = True is selected in last or not
        if self.order_id.order_line:
            if self.product_id:
                if self.order_id.order_line[0].product_id.hsn_disable == True:
                    raise UserError(_("This item should be selected in the end!!"))
        # Aman end
        check_partner = self.env['res.partner'].search([('id', '=', self.partner_id.id)])

        print("self.env.user.company_id.vattttttttttttttttttttttt",check_partner.name,check_partner.vat)

        self.taxes_id=''
        result = {}
        if not self.product_id:
            return result

        # Reset date, price and quantity since _onchange_quantity will provide default values
        self.date_planned = datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        self.price_unit = self.product_qty = 0.0
        self.product_uom = self.product_id.uom_po_id or self.product_id.uom_id
        result['domain'] = {'product_uom': [('category_id', '=', self.product_id.uom_id.category_id.id)]}

        product_lang = self.product_id.with_context(
            lang=self.partner_id.lang,
            partner_id=self.partner_id.id,
        )
        self.name = product_lang.display_name
        # Aman 28/11/2020 Added description of product on form level
        if product_lang.description:
            self.name = product_lang.description
        elif product_lang.description_purchase:
            self.name += '\n' + product_lang.description_purchase
        # Getting default taxes
        # fpos = self.order_id.fiscal_position_id
        # if self.env.uid == SUPERUSER_ID:
        #     company_id = self.env.user.company_id.id
        #     taxes_id = fpos.map_tax(
        #         self.product_id.supplier_taxes_id.filtered(lambda r: r.company_id.id == company_id))
        # else:
        #     taxes_id = fpos.map_tax(self.product_id.supplier_taxes_id)
        # print("self.taxes_iddddddd",taxes_id)

        # # Gaurav starts:
        # taxes_ids_list = taxes_id.ids
        # # Gaurav 12/3/20 added code for default tax state wise
        # check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
        # check_vendor_state = self.env['res.partner'].search([('id', '=', self.partner_id.id), ('company_id', '=', self.env.user.company_id.id)])
        #
        # if check_cmpy_state.state_id == check_vendor_state.state_id:
        #     self.env.cr.execute(""" select id from account_tax where active=True and type_tax_use='sale' AND tax_group_id!=1 and company_id='%s'""" % (self.env.user.company_id.id,))
        #     csgst_taxes = self.env.cr.dictfetchall()
        #     final = [taxes_ids_list.remove(val.get('id')) for val in csgst_taxes if val.get('id') in taxes_ids_list if csgst_taxes]
        #     print("finalvvvvvvvvvvvvvvvv", final)
        #     self.taxes_id = taxes_ids_list
        #
        # elif check_cmpy_state.state_id != check_vendor_state.state_id:
        #     self.env.cr.execute(""" select id from account_tax where active=True and type_tax_use='sale' AND tax_group_id!=4 and company_id='%s'""" % (self.env.user.company_id.id,))
        #     igst_taxes = self.env.cr.dictfetchall()
        #     final = [taxes_ids_list.remove(val.get('id')) for val in igst_taxes if val.get('id') in taxes_ids_list if igst_taxes]
        #     print("finalvvvvvvvvvvvvvvvv", final)
        #     self.taxes_id = taxes_ids_list
        #
        # result= {'domain': {'taxes_id': [final]}}

        # End: Default taxes on state wise with domain
        # Start: on change product : show state wise list of gst..

        # Gaurav 12/3/20 added code for default tax state wise
        check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
        check_custmr_state = self.env['res.partner'].search(
            [('id', '=', self.partner_id.id), ('company_id', '=', self.env.user.company_id.id)])

        # Gaurav 13/3/20 added validation for GST check (if vendor is unregistered then don't add taxes if registered then add taxes state wise)
        if check_partner.vat:
            # GST present , vendor registered

            # checking company state and customer state is same or not
            if check_cmpy_state.state_id == check_custmr_state.state_id:
                # Aman 24/12/2020 Added condition to check if product with hsn_disable = True must pick tax
                # of the item with greatest tax
                if self.product_id.hsn_disable == True:
                    group_type = ('CGST', 'SGST')
                    taxes_cust = genric.get_taxes(self, self.product_id, group_type, po=True)
                    self.taxes_id = taxes_cust
                # Aman end
                else:
                    # if same states show taxes like CGST SGST GST
                    self.env.cr.execute(
                        """select id from account_tax where active=True and type_tax_use='purchase' and tax_group_id!=4 and company_id='%s'""" % (
                        self.env.user.company_id.id,))
                    csgst_taxes = self.env.cr.dictfetchall()
                    print("purchase csgst_taxessssss", csgst_taxes)
                    # self._set_taxes()
                    self._compute_purchase_tax()
                    cs_tax_list = []
                    if csgst_taxes:
                        for val in csgst_taxes:
                            tax_detail_idcs = val.get('id')
                            cs_tax_list.append(tax_detail_idcs)
                            print("cs_tax_listttt", cs_tax_list)
                            # self.update({'tax_id': [(6, 0, cs_tax_list)]})
                            result = {'domain': {'taxes_id': [('id', 'in', cs_tax_list)]}}


            elif check_cmpy_state.state_id != check_custmr_state.state_id:
                # Aman 24/12/2020 Added condition to check if product with hsn_disable = True must pick tax
                # of the item with greatest tax
                if self.product_id.hsn_disable == True:
                    group_type = ('IGST')
                    taxes_cust = genric.get_taxes(self, self.product_id, group_type, po=True)
                    self.taxes_id = taxes_cust
                # Aman end
                else:
                    # if different states show taxes like IGST
                    self.env.cr.execute(
                        """ select id from account_tax where active=True and type_tax_use='purchase' and tax_group_id not in (2,3) and company_id='%s'""" % (
                        self.env.user.company_id.id,))
                    igst_taxes = self.env.cr.dictfetchall()
                    # self._set_taxes()
                    self._compute_purchase_tax()
                    i_tax_list = []
                    if igst_taxes:
                        for val in igst_taxes:
                            tax_detail_idi = val.get('id')
                            i_tax_list.append(tax_detail_idi)
                            print("purchase i_tax_listtttt", i_tax_list)
                            result = {'domain': {'taxes_id': [('id', 'in', i_tax_list)]}}

        else:
            # checking company state and customer state is same or not
            if check_cmpy_state.state_id == check_custmr_state.state_id:
                # if same states show taxes like CGST SGST GST
                self.env.cr.execute(
                    """select id from account_tax where active=True and type_tax_use='purchase' and tax_group_id!=4 and company_id='%s'""" % (
                        self.env.user.company_id.id,))
                csgst_taxes = self.env.cr.dictfetchall()
                print("purchase csgst_taxessssss", csgst_taxes)
                # self._set_taxes()
                # self._compute_purchase_tax()
                cs_tax_list = []
                if csgst_taxes:
                    for val in csgst_taxes:
                        tax_detail_idcs = val.get('id')
                        cs_tax_list.append(tax_detail_idcs)
                        print("cs_tax_listttt", cs_tax_list)
                        # self.update({'tax_id': [(6, 0, cs_tax_list)]})
                        result = {'domain': {'taxes_id': [('id', 'in', cs_tax_list)]}}


            elif check_cmpy_state.state_id != check_custmr_state.state_id:
                # if different states show taxes like IGST
                self.env.cr.execute(
                    """ select id from account_tax where active=True and type_tax_use='purchase' and tax_group_id not in (2,3) and company_id='%s'""" % (
                        self.env.user.company_id.id,))
                igst_taxes = self.env.cr.dictfetchall()
                # self._set_taxes()
                # self._compute_purchase_tax()
                i_tax_list = []
                if igst_taxes:
                    for val in igst_taxes:
                        tax_detail_idi = val.get('id')
                        i_tax_list.append(tax_detail_idi)
                        print("purchase i_tax_listtttt", i_tax_list)
                        result = {'domain': {'taxes_id': [('id', 'in', i_tax_list)]}}


        self._suggest_quantity()
        self._onchange_quantity()

        return result

    # Gaurav end

    @api.onchange('product_id')
    def onchange_product_id_warning(self):
        if not self.product_id:
            return
        warning = {}
        title = False
        message = False

        product_info = self.product_id

        if product_info.purchase_line_warn != 'no-message':
            title = _("Warning for %s") % product_info.name
            message = product_info.purchase_line_warn_msg
            warning['title'] = title
            warning['message'] = message
            if product_info.purchase_line_warn == 'block':
                self.product_id = False
            return {'warning': warning}
        return {}

    @api.onchange('product_qty', 'product_uom')
    def _onchange_quantity(self):
        if not self.product_id:
            return

        seller = self.product_id._select_seller(
            partner_id=self.partner_id,
            quantity=self.product_qty,
            date=self.order_id.date_order and self.order_id.date_order[:10],
            uom_id=self.product_uom)

        if seller or not self.date_planned:
            self.date_planned = self._get_date_planned(seller).strftime(DEFAULT_SERVER_DATETIME_FORMAT)

        if not seller:
            return
        # jatin for vedor_tax_lines taxes on 02-07-2020
        print_tax = self.taxes_of_vendor_tax_lines()
        # changes

        price_unit = self.env['account.tax']._fix_tax_included_price_company(seller.price,
                                                                             print_tax,
                                                                             self.taxes_id,
                                                                             self.company_id) if seller else 0.0
        #end Jatin
        if price_unit and seller and self.order_id.currency_id and seller.currency_id != self.order_id.currency_id:
            price_unit = seller.currency_id.compute(price_unit, self.order_id.currency_id)

        if seller and self.product_uom and seller.product_uom != self.product_uom:
            price_unit = seller.product_uom._compute_price(price_unit, self.product_uom)

        self.price_unit = price_unit

    def _suggest_quantity(self):
        '''
        Suggest a minimal quantity based on the seller
        '''
        if not self.product_id:
            return
        seller_min_qty = self.product_id.seller_ids \
            .filtered(
            lambda r: r.name == self.order_id.partner_id and (not r.product_id or r.product_id == self.product_id)) \
            .sorted(key=lambda r: r.min_qty)
        if seller_min_qty:
            # avinash:12/11/20 Set default product quantity to zero
            # self.product_qty = seller_min_qty[0].min_qty or 1.0
            self.product_qty = seller_min_qty[0].min_qty or 0.0
            self.product_uom = seller_min_qty[0].product_uom
            # end avinash
        else:
            # avinash:12/11/20 Set default product quantity to zero
            # self.product_qty = 1.0
            self.product_qty = 0.0
            # end avinash

    # Piyush: code for adding class for material out on 30-05-2020


class MaterialOutLine(models.Model):
    _name = "material.out.line"
    _description = 'Material Out Line'
    _order = 'id desc'


    def _get_similar_move_lines(self):
        self.ensure_one()
        lines = self.env['stock.move.line']
        picking_id = self.move_id.picking_id if self.move_id else self.picking_id
        if picking_id:
            lines |= picking_id.move_line_ids.filtered(lambda ml: ml.product_id == self.product_id and (ml.lot_id or ml.lot_name))
        return lines


    @api.model
    def _get_date_planned(self, seller, po=False):
        """Return the datetime value to use as Schedule Date (``date_planned``) for
           PO Lines that correspond to the given product.seller_ids,
           when ordered at `date_order_str`.

           :param Model seller: used to fetch the delivery delay (if no seller
                                is provided, the delay is 0)
           :param Model po: purchase.order, necessary only if the PO line is
                            not yet attached to a PO.
           :rtype: datetime
           :return: desired Schedule Date for the PO line
        """
        date_order = po.date_order if po else self.material_line_id.date_order
        if date_order:
            return datetime.strptime(date_order, DEFAULT_SERVER_DATETIME_FORMAT) + relativedelta(days=seller.delay if seller else 0)
        else:
            return datetime.today() + relativedelta(days=seller.delay if seller else 0)

    @api.onchange('product_qty', 'product_uom')
    def _onchange_quantity(self):
        if not self.product_id:
            return

        seller = self.product_id._select_seller(
            partner_id=self.partner_id,
            quantity=self.product_qty,
            date=self.material_line_id.date_order and self.material_line_id.date_order[:10],
            uom_id=self.product_uom)

        if seller or not self.date_planned:
            self.date_planned = self._get_date_planned(seller).strftime(DEFAULT_SERVER_DATETIME_FORMAT)

        if not seller:
            return

        # Jatin for vendor_tax_lines 02-07-2020
        filter_tax = []
        for val in self:
            check = val.product_id.vendor_tax_lines
            print("check", check)
            for rec in check:
                tax_check = rec.tax_id.id
                print(tax_check)
                filter_tax.append(tax_check)
            print('filter_tax6', filter_tax)

        print_tax = self.env['account.tax'].search([('id', 'in', filter_tax)])
        print("print_tax", print_tax)

        price_unit = self.env['account.tax']._fix_tax_included_price_company(seller.price,
                                                                             print_tax,
                                                                             self.taxes_id,
                                                                             self.company_id) if seller else 0.0
        # end jatin
        if price_unit and seller and self.material_line_id.currency_id and seller.currency_id != self.material_line_id.currency_id:
            price_unit = seller.currency_id.compute(price_unit, self.material_line_id.currency_id)

        if seller and self.product_uom and seller.product_uom != self.product_uom:
            price_unit = seller.product_uom._compute_price(price_unit, self.product_uom)

        self.price_unit = price_unit

    def _suggest_quantity(self):
        '''
        Suggest a minimal quantity based on the seller
        '''
        if not self.product_id:
            return
        seller_min_qty = self.product_id.seller_ids \
            .filtered(
            lambda r: r.name == self.material_line_id.partner_id and (not r.product_id or r.product_id == self.product_id)) \
            .sorted(key=lambda r: r.min_qty)
        if seller_min_qty:
            # avinash:12/11/20 Set default product quantity to zero
            # self.product_qty = seller_min_qty[0].min_qty or 1.0
            self.product_qty = seller_min_qty[0].min_qty or 0.0
            # end avinash
            self.product_uom = seller_min_qty[0].product_uom
        else:
            # avinash:12/11/20 Set default product quantity to zero
            # self.product_qty = 1.0
            self.product_qty = 0.0
            # end avinash

    @api.onchange('product_id')
    def _onchange_product_id(self):

        #salman add hsn value
        self.hsn_id=self.product_id.hsn_id.hsn_code
        #salman end
        check_partner = self.env['res.partner'].search([('id', '=', self.partner_id.id)])
        self.taxes_id=''
        result = {}
        if not self.product_id:
            return result

        # Reset date, price and quantity since _onchange_quantity will provide default values
        self.date_planned = datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        self.price_unit = self.product_qty = 0.0
        self.product_uom = self.product_id.uom_po_id or self.product_id.uom_id
        result['domain'] = {'product_uom': [('category_id', '=', self.product_id.uom_id.category_id.id)]}

        product_lang = self.product_id.with_context(
            lang=self.partner_id.lang,
            partner_id=self.partner_id.id,
        )
        self.name = product_lang.display_name
        # Aman 28/11/2020 Added description of product on form level
        if product_lang.description:
            self.name = product_lang.description
        elif product_lang.description_purchase:
            self.name += '\n' + product_lang.description_purchase
        # Gaurav 12/3/20 added code for default tax state wise
        check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
        check_custmr_state = self.env['res.partner'].search(
            [('id', '=', self.partner_id.id), ('company_id', '=', self.env.user.company_id.id)])

        # Gaurav 13/3/20 added validation for GST check (if vendor is unregistered then don't add taxes if registered then add taxes state wise)
        if check_partner.vat:
            # GST present , vendor registered

            # checking company state and customer state is same or not
            if check_cmpy_state.state_id == check_custmr_state.state_id:
                # if same states show taxes like CGST SGST GST
                self.env.cr.execute(
                    """select id from account_tax where active=True and type_tax_use='purchase' and tax_group_id!=4 and company_id='%s'""" % (
                    self.env.user.company_id.id,))
                csgst_taxes = self.env.cr.dictfetchall()
                print("purchase csgst_taxessssss", csgst_taxes)
                # self._set_taxes()
                self._compute_purchase_tax()
                cs_tax_list = []
                if csgst_taxes:
                    for val in csgst_taxes:
                        tax_detail_idcs = val.get('id')
                        cs_tax_list.append(tax_detail_idcs)
                        print("cs_tax_listttt", cs_tax_list)
                        # self.update({'tax_id': [(6, 0, cs_tax_list)]})
                        result = {'domain': {'taxes_id': [('id', 'in', cs_tax_list)]}}


            elif check_cmpy_state.state_id != check_custmr_state.state_id:
                # if different states show taxes like IGST
                self.env.cr.execute(
                    """ select id from account_tax where active=True and type_tax_use='purchase' and tax_group_id not in (2,3) and company_id='%s'""" % (
                    self.env.user.company_id.id,))
                igst_taxes = self.env.cr.dictfetchall()
                # self._set_taxes()
                self._compute_purchase_tax()
                i_tax_list = []
                if igst_taxes:
                    for val in igst_taxes:
                        tax_detail_idi = val.get('id')
                        i_tax_list.append(tax_detail_idi)
                        print("purchase i_tax_listtttt", i_tax_list)
                        result = {'domain': {'taxes_id': [('id', 'in', i_tax_list)]}}

        else:
            # checking company state and customer state is same or not
            if check_cmpy_state.state_id == check_custmr_state.state_id:
                # if same states show taxes like CGST SGST GST
                self.env.cr.execute(
                    """select id from account_tax where active=True and type_tax_use='purchase' and tax_group_id!=4 and company_id='%s'""" % (
                        self.env.user.company_id.id,))
                csgst_taxes = self.env.cr.dictfetchall()
                print("purchase csgst_taxessssss", csgst_taxes)
                # self._set_taxes()
                # self._compute_purchase_tax()
                cs_tax_list = []
                if csgst_taxes:
                    for val in csgst_taxes:
                        tax_detail_idcs = val.get('id')
                        cs_tax_list.append(tax_detail_idcs)
                        print("cs_tax_listttt", cs_tax_list)
                        # self.update({'tax_id': [(6, 0, cs_tax_list)]})
                        result = {'domain': {'taxes_id': [('id', 'in', cs_tax_list)]}}


            elif check_cmpy_state.state_id != check_custmr_state.state_id:
                # if different states show taxes like IGST
                self.env.cr.execute(
                    """ select id from account_tax where active=True and type_tax_use='purchase' and tax_group_id not in (2,3) and company_id='%s'""" % (
                        self.env.user.company_id.id,))
                igst_taxes = self.env.cr.dictfetchall()
                # self._set_taxes()
                # self._compute_purchase_tax()
                i_tax_list = []
                if igst_taxes:
                    for val in igst_taxes:
                        tax_detail_idi = val.get('id')
                        i_tax_list.append(tax_detail_idi)
                        print("purchase i_tax_listtttt", i_tax_list)
                        result = {'domain': {'taxes_id': [('id', 'in', i_tax_list)]}}


        self._suggest_quantity()
        self._onchange_quantity()

        return result

    # Gaurav 13/3/20 commented and added GST validation code for RFQ and purchase order

    def _compute_purchase_tax(self):

        # Getting default taxes
        fpos = self.material_line_id.fiscal_position_id
        if self.env.uid == SUPERUSER_ID:
            print("purchase super")
            company_id = self.env.user.company_id.id
            # Jatin for vendor_tax_lines taxes on 02-07-2020
            filter_tax = []
            for val in self:
                check = val.product_id.vendor_tax_lines
                print("check", check)
                for rec in check:
                    tax_check = rec.tax_id.id
                    print(tax_check)
                    filter_tax.append(tax_check)
                print('filter_tax7', filter_tax)

            print_tax = self.env['account.tax'].search([('id', 'in', filter_tax)])
            print("print_tax", print_tax)

            # print("supplier",self.product_id.supplier_taxes_id)
            taxes_id = fpos.map_tax(
                print_tax.filtered(lambda r: r.company_id.id == company_id))
            # end jatin
            # taxes_id = fpos.map_tax(
            #     self.product_id.supplier_taxes_id.filtered(lambda r: r.company_id.id == company_id))

            print("self.taxes_iddddddd", taxes_id, self.partner_id.id)
            taxes_ids_list = taxes_id.ids


            # Gaurav 12/3/20 added code for default tax state wise
            check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
            check_custmr_state = self.env['res.partner'].search(
                [('id', '=', self.partner_id.id), ('company_id', '=', self.env.user.company_id.id)])
            print("purchase checkingggggggggggg",check_custmr_state.state_id,check_cmpy_state.state_id)

            if check_cmpy_state.state_id == check_custmr_state.state_id:
                print("same state")
                self.env.cr.execute(
                    """ select id from account_tax where active=True and type_tax_use='purchase' AND tax_group_id not in (2,3) and company_id='%s'""" % (
                        self.env.user.company_id.id,))
                csgst_taxes = self.env.cr.dictfetchall()
                print("csgst_taxesvvvvvvvvvvvvvvvv", csgst_taxes)
                tax_id_list = [taxes_ids_list.remove(val.get('id')) for val in csgst_taxes if
                               val.get('id') in taxes_ids_list if csgst_taxes]
                # tax_list = []
                # tax_id_list = [tax.id for tax in taxes_id]
                # if igst_taxes:
                #     for val in igst_taxes:
                #         tax_detail_id = val.get('id')
                #         tax_list.append(tax_detail_id)
                #
                # for value in tax_id_list:
                #     if value in tax_list:
                #         tax_id_list.remove(value)
                #         print(tax_id_list)

                self.taxes_id = taxes_ids_list

            elif check_cmpy_state.state_id != check_custmr_state.state_id:
                print("diff state")

                self.env.cr.execute(
                    """ select id from account_tax where active=True and type_tax_use='purchase' AND tax_group_id!=4 and company_id='%s'""" % (
                        self.env.user.company_id.id,))
                igst_taxes = self.env.cr.dictfetchall()
                tax_id_list = [taxes_ids_list.remove(val.get('id')) for val in igst_taxes if val.get('id') in taxes_ids_list if igst_taxes]
                # tax_list = []
                # tax_id_list = [tax.id for tax in taxes_id]
                # if igst_taxes:
                #     for val in igst_taxes:
                #         tax_detail_id = val.get('id')
                #         tax_list.append(tax_detail_id)
                #
                # for value in tax_id_list:
                #     if value in tax_list:
                #         tax_id_list.remove(value)
                #         print(tax_id_list)
                print("purchase finalvvvvvvvvvvvvvvvv", taxes_ids_list)

                self.taxes_id = taxes_ids_list

            result= {'domain': {'taxes_id': [tax_id_list]}}
            # result= {'domain': {'taxes_id': [tax_id_list], 'type_tax_use': 'purchase'}}


        else:
            print("normal")
            # Jatin for vendor_tax_lines taxes on 02-07-2020
            filter_tax = []
            for val in self:
                check = val.product_id.vendor_tax_lines
                print("check", check)
                for rec in check:
                    tax_check = rec.tax_id.id
                    print(tax_check)
                    filter_tax.append(tax_check)
                print('filter_tax8', filter_tax)

            print_tax = self.env['account.tax'].search([('id', 'in', filter_tax)])
            print("print_tax", print_tax)
            taxes_id = fpos.map_tax(print_tax)
            # end JAtin
            #taxes_id = fpos.map_tax(self.product_id.supplier_taxes_id)

            print(" purchase self.taxes_iddddddd", taxes_id)
            taxes_ids_list = taxes_id.ids

            # Gaurav 12/3/20 added code for default tax state wise
            check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
            check_custmr_state = self.env['res.partner'].search(
                [('id', '=', self.partner_id.id), ('company_id', '=', self.env.user.company_id.id)])

            if check_cmpy_state.state_id == check_custmr_state.state_id:
                print("same state")
                self.env.cr.execute(
                    """ select id from account_tax where active=True and type_tax_use='purchase' AND tax_group_id not in (2,3) and company_id='%s'""" % (
                        self.env.user.company_id.id,))
                csgst_taxes = self.env.cr.dictfetchall()
                tax_id_list = [taxes_ids_list.remove(val.get('id')) for val in csgst_taxes if
                               val.get('id') in taxes_ids_list if csgst_taxes]

                self.taxes_id = taxes_ids_list

            elif check_cmpy_state.state_id != check_custmr_state.state_id:
                print("diff state")

                self.env.cr.execute(
                    """ select id from account_tax where active=True and type_tax_use='purchase' AND tax_group_id!=4 and company_id='%s'""" % (
                        self.env.user.company_id.id,))
                igst_taxes = self.env.cr.dictfetchall()
                tax_id_list = [taxes_ids_list.remove(val.get('id')) for val in igst_taxes if val.get('id') in taxes_ids_list if igst_taxes]

                self.taxes_id = taxes_ids_list

            result= {'domain': {'taxes_id': [tax_id_list]}}
            # result= {'domain': {'taxes_id': [tax_id_list], 'type_tax_use': 'purchase'}}
        return result

    # Piyush code for qty check in job order challan on 13-06-2020

    @api.onchange('product_qty')
    def _onchange_product_qty(self):
        for val in self:
            if val and val.product_id and val.product_id.type == 'product' and val.product_id.tracking == 'none' and self.env.user.company_id.default_positive_stock:
                if val.product_qty > val.product_id.qty_available:
                    raise ValidationError(
                        'Cannot issue quantity more than available. For {} available quantity '
                        'is {} '.format(val.product_id.name, val.product_id.qty_available))

    # code ends here

    @api.depends('material_line_id.state', 'move_ids.state', 'move_ids.product_uom_qty')
    def _compute_qty_received(self):
        for line in self:
            if line.material_line_id.state not in ['purchase', 'done']:
                line.qty_received = 0.0
                continue
            if line.product_id.type not in ['consu', 'product']:
                line.qty_received = line.product_qty
                continue
            total = 0.0
            for move in line.move_ids:
                if move.state == 'done':
                    if move.location_dest_id.usage == "supplier":
                        if move.to_refund:
                            total -= move.product_uom._compute_quantity(move.product_uom_qty, line.product_uom)
                    elif move.origin_returned_move_id._is_dropshipped() and not move._is_dropshipped_returned():
                        # Edge case: the dropship is returned to the stock, no to the supplier.
                        # In this case, the received quantity on the PO is set although we didn't
                        # receive the product physically in our stock. To avoid counting the
                        # quantity twice, we do nothing.
                        pass
                    else:
                        total += move.product_uom._compute_quantity(move.product_uom_qty, line.product_uom)
            line.qty_received = total

    @api.depends('invoice_lines.invoice_id.state', 'invoice_lines.quantity', 'invoice_lines.uom_id')
    def _compute_qty_invoiced(self):
        for line in self:
            qty = 0.0
            for inv_line in line.invoice_lines:
                if inv_line.invoice_id.state not in ['cancel']:
                    if inv_line.invoice_id.type == 'in_invoice':
                        qty += inv_line.uom_id._compute_quantity(inv_line.quantity, line.product_uom)
                    elif inv_line.invoice_id.type == 'in_refund':
                        qty -= inv_line.uom_id._compute_quantity(inv_line.quantity, line.product_uom)
            line.qty_invoiced = qty

    @api.depends('product_qty', 'price_unit', 'taxes_id')
    def _compute_amount(self):
        for line in self:
            taxes = line.taxes_id.compute_all(line.price_unit, line.material_line_id.currency_id, line.product_qty,
                                              product=line.product_id, partner=line.material_line_id.partner_id)
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })

    @api.depends('lots_wise_ids.qty_done')
    def _compute_total_qty(self):
        product_qty = 0.0
        for qty in self:
            if qty.product_id.tracking in ['lot', 'serial'] and qty.lots_wise_ids:
                for item in qty.lots_wise_ids:
                    product_qty += item.qty_done
            qty.product_qty = product_qty

    def _total_qty_set(self):
        product_qty = self[0].product_qty

        # Piyush: code for getting qty lot wise on 12-06-2020

    @api.multi
    def _compute_available_qty(self):
        for val in self:
            dest_location_req = ''
            location_ids = self.env['stock.location'].search(
                [('name', '=', 'Issue'), ('company_id', '=', self.env.user.company_id.id)])
            if location_ids:
                dest_location_req = location_ids.id

            self.env.cr.execute("""SELECT T1.lot_id, (T1.sum_qty1 - coalesce(T2.sum_qty2,0)) as current_stock FROM
                                    (SELECT lot_id, SUM(qty_done) as sum_qty1 FROM stock_move_line WHERE product_id = %s
                                                    AND state = 'done' AND location_dest_id = %s GROUP BY lot_id ORDER BY lot_id) as T1
                                                    LEFT JOIN (SELECT lot_id, SUM(qty_done) as sum_qty2 FROM stock_move_line WHERE product_id = %s
                                                    AND state = 'done' AND location_id = %s GROUP BY lot_id ORDER BY lot_id) as T2
                                                     ON (T1.lot_id = T2.lot_id) WHERE T1.lot_id is not null""",

                                (tuple([val.product_id.id]),
                                 tuple([dest_location_req or False]),
                                 tuple([val.product_id.id]),
                                 tuple([dest_location_req or False])))
            match_recs = self.env.cr.dictfetchall()

            if not match_recs:
                self.env.cr.execute("""SELECT lot_id, SUM(qty_done) as current_stock FROM stock_move_line WHERE product_id = %s
                                                AND state = 'done' AND location_dest_id = %s AND lot_id is not null GROUP BY lot_id ORDER BY lot_id """,
                                    (tuple([val.product_id.id]),
                                     tuple([dest_location_req or False])))
                match_recs = self.env.cr.dictfetchall()

        # code ends here
     # Salman add Hsn field
    hsn_id=fields.Char(string='HSN code')
    # Salman end
    name = fields.Text(string='Description', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    Available_qty = fields.Float(compute='_compute_available_qty', string="Available Qty", store=True)
    product_qty = fields.Float(compute='_compute_total_qty', inverse='_total_qty_set', store=True, string='Quantity', digits=dp.get_precision('Product Unit of Measure'), required=True)
    date_planned = fields.Datetime(string='Scheduled Date', index=True)
    taxes_id = fields.Many2many('account.tax', string='Taxes',
                                domain=['|', ('active', '=', False), ('active', '=', True)])
    product_uom = fields.Many2one('product.uom', string='Product Unit of Measure', required=True)
    product_id = fields.Many2one('product.product', string='Product', domain=[('purchase_ok', '=', True)],
                                 change_default=True, required=True)
    product_image = fields.Binary(
        'Product Image', related="product_id.image",
        help="Non-stored related field to allow portal user to see the image of the product he has ordered")
    move_ids = fields.One2many('stock.move', 'material_out_line_id', string='Reservation', readonly=True,
                               ondelete='set null', copy=False)
    price_unit = fields.Float(string='Unit Price', required=True, digits=dp.get_precision('Product Price'))

    price_subtotal = fields.Monetary(compute='_compute_amount', string='Subtotal', store=True)
    price_total = fields.Monetary(compute='_compute_amount', string='Total', store=True)
    price_tax = fields.Float(compute='_compute_amount', string='Tax', store=True)

    # code ends here
    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Analytic Tags')
    material_line_id = fields.Many2one('purchase.order', string="Material Id")
    company_id = fields.Many2one('res.company', related='material_line_id.company_id', string='Company', store=True,
                                 readonly=True)
    state = fields.Selection(related='material_line_id.state', store=True)

    invoice_lines = fields.One2many('account.invoice.line', 'purchase_line_id', string="Bill Lines", readonly=True,
                                    copy=False)

    # Replace by invoiced Qty
    qty_invoiced = fields.Float(compute='_compute_qty_invoiced', string="Billed Qty",
                                digits=dp.get_precision('Product Unit of Measure'), store=True)
    qty_received = fields.Float(compute='_compute_qty_received', string="Received Qty",
                                digits=dp.get_precision('Product Unit of Measure'), store=True, compute_sudo=True)

    partner_id = fields.Many2one('res.partner', related='material_line_id.partner_id', string='Partner', readonly=True,
                                 store=True)
    currency_id = fields.Many2one(related='material_line_id.currency_id', store=True, string='Currency', readonly=True)
    date_order = fields.Datetime(related='material_line_id.date_order', string='Order Date', readonly=True)

    orderpoint_id = fields.Many2one('stock.warehouse.orderpoint', 'Orderpoint')
    lots_wise_ids = fields.One2many('lot.wise.item', 'lot_wise_id', string='Lot Wise')
    tracking = fields.Selection(related='product_id.product_tmpl_id.tracking', store=True)
    unit = fields.Many2one('product.uom', 'Unit')
    show_details_visible = fields.Boolean('Details Visible', compute='_compute_show_details_visible')

    @api.depends('product_id')
    def _compute_show_details_visible(self):
        """ According to this field, the button that calls `action_show_details` will be displayed
        to work on a move from its picking form view, or not.
        """
        for move in self:
            if not move.product_id:
                move.show_details_visible = False
                continue
            if move.product_id:
                if move.product_id.tracking == "none":
                    move.show_details_visible = False
                else:
                    move.show_details_visible = True

    def issue_lot_wise_form(self):
        """
        Show Issue MRS LIne Form for Issuing the Quantity.
        """
        self.ensure_one()
        view = self.env.ref('purchase.lot_wise_challan_lines_form')
        return {
            'name': _('Challan Detail'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'material.out.line',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'res_id': self.id,
        }

    # code ends here


class LotWiseItem(models.Model):
    _name = 'lot.wise.item'

    lot_wise_id = fields.Many2one('material.out.line', 'Lot Wise')

    product_id = fields.Many2one(related="lot_wise_id.product_id", string='Product')
    lot_id = fields.Many2one('stock.production.lot', 'Lot/Serial No')
    lot_name = fields.Char('Lot/Serial Number')
    product_uom_qty = fields.Float('Reserved', readonly=True, default=0.0, digits=dp.get_precision('MRS Quantity'))
    available_qty_lot = fields.Float('Available Qty', readonly=True, default=0.0)
    product_qty = fields.Float('Qty', digits=dp.get_precision('MRS Quantity'))
    product_uom = fields.Many2one('product.uom', related='lot_wise_id.product_id.uom_id', string='Unit of Measure')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.user.company_id.id)
    qty_done = fields.Float('Done', default=0.0, digits=dp.get_precision('Product Unit of Measure'), copy=False)

    # Piyush: code for qty check in the lot on 12-06-2020

    @api.onchange('qty_done')
    def _qty_done_comparision(self):
        for val in self:
            if val and val.product_id and val.product_id.type == 'product' and val.product_id.tracking not in ['none'] and self.env.user.company_id.default_positive_stock:
                if val.qty_done > val.available_qty_lot:
                    raise ValidationError(
                        'Cannot issue quantity more than available. For {} the available quantity in the lot {} '
                        'is {} '.format(val.product_id.name, val.lot_id.name, val.available_qty_lot))

                # code ends here


    # Piyush: code for getting qty lot wise on 12-06-2020

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        for val in self:
            # avinash:06/11/20 Update available quantity only for stockable product
            if val.product_id.type == 'product':
            # end avinash
                dest_location_req = ''
                location_ids = self.env['stock.location'].search(
                    [('name', '=', 'Stock'),
                     ('company_id', '=', self.env.user.company_id.id)])

                if location_ids:
                    dest_location_req = location_ids.id
                    print("Destination loooooooooooooooooooooooooooooooo = ", dest_location_req)

                self.env.cr.execute("""SELECT T1.lot_id, (T1.sum_qty1 - coalesce(T2.sum_qty2,0)) as current_stock FROM
                                        (SELECT lot_id, SUM(qty_done) as sum_qty1 FROM stock_move_line WHERE product_id = %s
                                                        AND state = 'done' AND location_dest_id = %s GROUP BY lot_id ORDER BY lot_id) as T1
                                                        LEFT JOIN (SELECT lot_id, SUM(qty_done) as sum_qty2 FROM stock_move_line WHERE product_id = %s
                                                        AND state = 'done' AND location_id = %s GROUP BY lot_id ORDER BY lot_id) as T2
                                                         ON (T1.lot_id = T2.lot_id) WHERE T1.lot_id is not null""",

                                    (tuple([val.product_id.id or False]),
                                     # tuple([self.env.user.company_id and self.env.user.company_id.id or False]),
                                     tuple([dest_location_req or False]),
                                     tuple([val.product_id.id or False]),
                                     # tuple([self.env.user.company_id and self.env.user.company_id.id or False]),
                                     tuple([dest_location_req or False])))
                match_recs = self.env.cr.dictfetchall()

                if not match_recs:
                    self.env.cr.execute("""SELECT lot_id, SUM(qty_done) as current_stock FROM stock_move_line WHERE product_id = %s
                                                    AND location_id = %s AND lot_id is not null GROUP BY lot_id ORDER BY lot_id """,
                                        (tuple([val.product_id.id]),
                                         tuple([dest_location_req or False])))
                    match_recs = self.env.cr.dictfetchall()
                    print("match recssssssssssssssssssssssssss2 = ", match_recs, val.product_id.id)

                if val.lot_id:
                    available_qty_lot = 0.0
                    for req_lot_id in match_recs:
                        if req_lot_id.get('lot_id') == val.lot_id.id:
                            available_qty_lot = req_lot_id.get('current_stock')
                    val.available_qty_lot = available_qty_lot
                else:
                    val.available_qty_lot = 0.0

        #end piyush



    @api.onchange('lot_name', 'lot_id')
    def onchange_serial_number(self):
        """ When the user is encoding a move line for a tracked product, we apply some logic to
        help him. This includes:
            - automatically switch `qty_done` to 1.0
            - warn if he has already encoded `lot_name` in another move line
        """
        res = {}
        # avinash:13/10/20 So that when stock move from JOb work challan it do not check unique lot id
        if not 'material.out.line' == self.env.context.get('active_model'):
        # end avinash
            if self.product_id.tracking == 'serial':
                if not self.qty_done:
                    self.qty_done = 1

                message = None
                if self.lot_name or self.lot_id:
                    move_lines_to_check = self._get_similar_move_lines() - self
                    if self.lot_name:
                        counter = Counter(move_lines_to_check.mapped('lot_name'))
                        if counter.get(self.lot_name) and counter[self.lot_name] > 1:
                            message = _('You cannot use the same serial number twice. Please correct the serial numbers encoded.')
                    elif self.lot_id:
                        counter = Counter(move_lines_to_check.mapped('lot_id.id'))
                        if counter.get(self.lot_id.id) and counter[self.lot_id.id] > 1:
                            message = _('You cannot use the same serial number twice. Please correct the serial numbers encoded.')

                if message:
                    res['warning'] = {'title': _('Warning'), 'message': message}
            return res

    @api.onchange('qty_done')
    def _onchange_qty_done(self):
        """ When the user is encoding a move line for a tracked product, we apply some logic to
        help him. This onchange will warn him if he set `qty_done` to a non-supported value.
        """
        res = {}
        if self.qty_done and self.product_id.tracking == 'serial':
            if float_compare(self.qty_done, 1.0, precision_rounding=self.product_id.uom_id.rounding) != 0:
                message = _('You can only process 1.0 %s for products with unique serial number.') % self.product_id.uom_id.name
                res['warning'] = {'title': _('Warning'), 'message': message}
        return res

    @api.constrains('qty_done')
    def _check_positive_qty_done(self):
        if any([ml.qty_done < 0 for ml in self]):
            raise ValidationError(_('You can not enter negative quantities!'))


# Gaurav 9/5/20 added supplier class
class SupplierInfo(models.Model):
    _inherit = "product.supplierinfo"


    date = fields.Date('Date', help="Date for this customer price")
    sequence_ref = fields.Char('Reference No.', help="Reference number")
    price_diff = fields.Float('Price Difference')
    product_quantity = fields.Float('Quantity')


class ProcurementGroup(models.Model):
    _inherit = 'procurement.group'

    @api.model
    def _get_exceptions_domain(self):
        return super(ProcurementGroup, self)._get_exceptions_domain() + [('created_purchase_line_id', '=', False)]


class ProcurementRule(models.Model):
    _inherit = 'procurement.rule'
    action = fields.Selection(selection_add=[('buy', 'Buy')])

    @api.multi
    def _run_buy(self, product_id, product_qty, product_uom, location_id, name, origin, values):
        cache = {}
        suppliers = product_id.seller_ids\
            .filtered(lambda r: (not r.company_id or r.company_id == values['company_id']) and (not r.product_id or r.product_id == product_id))
        if not suppliers:
            msg = _('There is no vendor associated to the product %s. Please define a vendor for this product.') % (product_id.display_name,)
            raise UserError(msg)

        supplier = self._make_po_select_supplier(values, suppliers)
        partner = supplier.name

        domain = self._make_po_get_domain(values, partner)

        if domain in cache:
            po = cache[domain]
        else:
            po = self.env['purchase.order'].sudo().search([dom for dom in domain])
            po = po[0] if po else False
            cache[domain] = po
        if not po:
            # Piyush: added po_from_so to remove order line validation on 04-07-2020
            po_from_so = True
            vals = self._prepare_purchase_order(product_id, product_qty, product_uom, origin, values, partner, po_from_so)
            company_id = values.get('company_id') and values['company_id'].id or self.env.user.company_id.id
            po = self.env['purchase.order'].with_context(force_company=company_id).sudo().create(vals)
            cache[domain] = po
        elif not po.origin or origin not in po.origin.split(', '):
            if po.origin:
                if origin:
                    po.write({'origin': po.origin + ', ' + origin})
                else:
                    po.write({'origin': po.origin})
            else:
                po.write({'origin': origin})

        # Create Line
        po_line = False
        for line in po.order_line:
            if line.product_id == product_id and line.product_uom == product_id.uom_po_id:
                if line._merge_in_existing_line(product_id, product_qty, product_uom, location_id, name, origin, values):
                    vals = self._update_purchase_order_line(product_id, product_qty, product_uom, values, line, partner)
                    po_line = line.write(vals)
                    break
        if not po_line:
            vals = self._prepare_purchase_order_line(product_id, product_qty, product_uom, values, po, supplier)
            self.env['purchase.order.line'].sudo().create(vals)


    def _get_purchase_schedule_date(self, values):
        """Return the datetime value to use as Schedule Date (``date_planned``) for the
           Purchase Order Lines created to satisfy the given procurement. """
        procurement_date_planned = fields.Datetime.from_string(values['date_planned'])
        schedule_date = (procurement_date_planned - relativedelta(days=values['company_id'].po_lead))
        return schedule_date

    def _get_purchase_order_date(self, product_id, product_qty, product_uom, values, partner, schedule_date):
        """Return the datetime value to use as Order Date (``date_order``) for the
           Purchase Order created to satisfy the given procurement. """
        seller = product_id.with_context(force_company=values['company_id'].id)._select_seller(
            partner_id=partner,
            quantity=product_qty,
            date=fields.Date.to_string(schedule_date),
            uom_id=product_uom)
        # Aman 31/07/2020 Since we required date_planned greater than order_date
        return schedule_date
        # return schedule_date - relativedelta(days=int(seller.delay))
        # Aman end

    def _update_purchase_order_line(self, product_id, product_qty, product_uom, values, line, partner):
        procurement_uom_po_qty = product_uom._compute_quantity(product_qty, product_id.uom_po_id)
        seller = product_id.with_context(force_company=values['company_id'].id)._select_seller(
            partner_id=partner,
            quantity=line.product_qty + procurement_uom_po_qty,
            date=line.order_id.date_order and line.order_id.date_order[:10],
            uom_id=product_id.uom_po_id)
        # Jatin for vendor_tax_lines on 02-07-2020
        filter_tax = []

        check = product_id.vendor_tax_lines
        print("check", check)
        for rec in check:
            tax_check = rec.tax_id.id
            print(tax_check)
            filter_tax.append(tax_check)
        print('filter_tax9', filter_tax)

        print_tax = self.env['account.tax'].search([('id', 'in', filter_tax)])
        print("print_tax", print_tax)

        price_unit = self.env['account.tax']._fix_tax_included_price_company(seller.price, print_tax, line.taxes_id,
                                                                             values['company_id']) if seller else 0.0
        # end jatin

        #price_unit = self.env['account.tax']._fix_tax_included_price_company(seller.price, line.product_id.supplier_taxes_id, line.taxes_id, values['company_id']) if seller else 0.0
        if price_unit and seller and line.order_id.currency_id and seller.currency_id != line.order_id.currency_id:
            price_unit = seller.currency_id.compute(price_unit, line.order_id.currency_id)

        res = {
            'product_qty': line.product_qty + procurement_uom_po_qty,
            'price_unit': price_unit,
            'move_dest_ids': [(4, x.id) for x in values.get('move_dest_ids', [])]
        }
        orderpoint_id = values.get('orderpoint_id')
        if orderpoint_id:
            res['orderpoint_id'] = orderpoint_id.id
        return res

    @api.multi
    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom, values, po, supplier):
        suppliers = product_id.seller_ids \
            .filtered(lambda r: (not r.company_id or r.company_id == values['company_id']) and (
                    not r.product_id or r.product_id == product_id))
        supplier = self._make_po_select_supplier(values, suppliers)
        partner = supplier.name
        procurement_uom_po_qty = product_uom._compute_quantity(product_qty, product_id.uom_po_id)
        seller = product_id._select_seller(
            partner_id=supplier.name,
            quantity=procurement_uom_po_qty,
            date=po.date_order and po.date_order[:10],
            uom_id=product_id.uom_po_id)
        # Jatin for vendor_tax_lines on 02-07-2020
        filter_tax = []
        check = product_id.vendor_tax_lines
        print("check", check)
        for rec in check:
            tax_check = rec.tax_id.id
            print(tax_check)
            filter_tax.append(tax_check)
        print('filter_tax10', filter_tax)

        print_tax = self.env['account.tax'].search([('id', 'in', filter_tax)])
        print("print_tax", print_tax)

        taxes = print_tax
        # end jatin

        #taxes = product_id.supplier_taxes_id
        fpos = po.fiscal_position_id
        taxes_id = fpos.map_tax(taxes) if fpos else taxes
        if taxes_id:
            taxes_id = taxes_id.filtered(lambda x: x.company_id.id == values['company_id'].id)

        # Aman 31/07/2020 Check whether partner is local or central. On the basis of partner taxes will be selected
        # Aman 27/07/2020 stored partner selected in product form
        check_partner = self.env['res.partner'].search([('id', '=', partner.id)])
        check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
        check_custmr_state = self.env['res.partner'].search(
            [('id', '=', partner.id), ('company_id', '=', self.env.user.company_id.id)])
        # Aman 27/07/2020 Check whether partner selected in product form has vat or not
        if check_partner.vat:
            if check_cmpy_state.state_id == check_custmr_state.state_id:
                self.env.cr.execute(
                    """ select id from account_tax where active=True and type_tax_use='purchase' AND tax_group_id not in (2,3) and company_id='%s'""" % (
                        self.env.user.company_id.id,))
                csgst_taxes = self.env.cr.dictfetchall()
                # final = [taxes_ids_list.remove(val.get('id')) for val in csgst_taxes if val.get('id') in taxes_ids_list if csgst_taxes]
                tax_list = []
                # tax_id_list = [tax.id for tax in taxes_id]
                tax_id_list = taxes_id.ids
                if csgst_taxes:
                    for val in csgst_taxes:
                        tax_detail_id = val.get('id')
                        tax_list.append(tax_detail_id)
                for value in tax_list:
                    if value in tax_id_list:
                        tax_id_list.remove(value)
                        print("tax", tax_id_list)

            elif check_cmpy_state.state_id != check_custmr_state.state_id:
                print("diff state")
                self.env.cr.execute(
                    """ select id from account_tax where active=True and type_tax_use='purchase' AND tax_group_id!=4 and company_id='%s'""" % (
                        self.env.user.company_id.id,))
                igst_taxes = self.env.cr.dictfetchall()
                # final = [taxes_ids_list.remove(val.get('id')) for val in igst_taxes if val.get('id') in taxes_ids_list if igst_taxes]
                tax_list = []
                tax_id_list = [tax.id for tax in taxes_id]
                if igst_taxes:
                    for val in igst_taxes:
                        tax_detail_id = val.get('id')
                        tax_list.append(tax_detail_id)
                for value in tax_list:
                    if value in tax_id_list:
                        tax_id_list.remove(value)
                        print(tax_id_list)
        else:
            tax_id_list = []
        # Aman end

        price_unit = self.env['account.tax']._fix_tax_included_price_company(seller.price, taxes, taxes_id, values['company_id']) if seller else 0.0
        if price_unit and seller and po.currency_id and seller.currency_id != po.currency_id:
            price_unit = seller.currency_id.compute(price_unit, po.currency_id)

        product_lang = product_id.with_context({
            'lang': supplier.name.lang,
            'partner_id': supplier.name.id,
        })
        name = product_lang.display_name
        if product_lang.description_purchase:
            name += '\n' + product_lang.description_purchase

        date_planned = self.env['purchase.order.line']._get_date_planned(seller, po=po).strftime(DEFAULT_SERVER_DATETIME_FORMAT)

        return {
            'name': name,
            'product_qty': procurement_uom_po_qty,
            'product_id': product_id.id,
            'product_uom': product_id.uom_po_id.id,
            'price_unit': price_unit,
            'date_planned': date_planned,
            'orderpoint_id': values.get('orderpoint_id', False) and values.get('orderpoint_id').id,
            'taxes_id': [(6, 0, tax_id_list)],
            'order_id': po.id,
            'move_dest_ids': [(4, x.id) for x in values.get('move_dest_ids', [])],
        }

    def _prepare_purchase_order(self, product_id, product_qty, product_uom, origin, values, partner, po_from_so):
        schedule_date = self._get_purchase_schedule_date(values)
        purchase_date = self._get_purchase_order_date(product_id, product_qty, product_uom, values, partner, schedule_date)
        fpos = self.env['account.fiscal.position'].with_context(force_company=values['company_id'].id).get_fiscal_position(partner.id)

        gpo = self.group_propagation_option
        group = (gpo == 'fixed' and self.group_id.id) or \
                (gpo == 'propagate' and values.get('group_id') and values['group_id'].id) or False

        return {
            'partner_id': partner.id,
            'picking_type_id': self.picking_type_id.id,
            'company_id': values['company_id'].id,
            'currency_id': partner.with_context(force_company=values['company_id'].id).property_purchase_currency_id.id or self.env.user.company_id.currency_id.id,
            'dest_address_id': values.get('partner_dest_id', False) and values['partner_dest_id'].id,
            'origin': origin,
            'payment_term_id': partner.with_context(force_company=values['company_id'].id).property_supplier_payment_term_id.id,
            'date_order': purchase_date.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
            'fiscal_position_id': fpos,
            'group_id': group,
            'po_from_so': True,
        }

    def _make_po_select_supplier(self, values, suppliers):
        """ Method intended to be overridden by customized modules to implement any logic in the
            selection of supplier.
        """
        return suppliers[0]

    def _make_po_get_domain(self, values, partner):
        domain = super(ProcurementRule, self)._make_po_get_domain(values, partner)
        gpo = self.group_propagation_option
        group = (gpo == 'fixed' and self.group_id) or \
                (gpo == 'propagate' and 'group_id' in values and values['group_id']) or False
    # Piyush: code for adding job 0rder in domain to send item in PO not JO on 17-06-2020
        domain += (
            ('partner_id', '=', partner.id),
            ('state', '=', 'draft'),
            ('picking_type_id', '=', self.picking_type_id.id),
            ('company_id', '=', values['company_id'].id),
            ('job_order', '=', False)
            )
        if group:
            domain += (('group_id', '=', group.id),)
        return domain


class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit = 'product.template'

    @api.model
    def _get_buy_route(self):
        buy_route = self.env.ref('purchase.route_warehouse0_buy', raise_if_not_found=False)
        if buy_route:
            return buy_route.ids
        return []

    @api.multi
    def _purchase_count(self):
        for template in self:
            template.purchase_count = sum([p.purchase_count for p in template.product_variant_ids])
        return True

    #Himanshu product 30-08-2020 if the route is of buy type and can_be_purchased is checked then only it save will work otherwise it will throw an validation error.
    @api.constrains('route_ids','purchase_ok')
    def change_id(self):
        for rec in self.route_ids:
            if rec.name=='Buy' and self.purchase_ok==False:
                raise ValidationError(_("When route is of buy type then can be purchased should be checked"))
    #End Himanshu

    property_account_creditor_price_difference = fields.Many2one(
        'account.account', string="Price Difference Account", company_dependent=True,
        help="This account will be used to value price difference between purchase price and cost price.")
    purchase_count = fields.Integer(compute='_purchase_count', string='# Purchases')
    purchase_method = fields.Selection([
        ('purchase', 'On ordered quantities'),
        ('receive', 'On received quantities'),
        ], string="Control Policy",
        help="On ordered quantities: control bills based on ordered quantities.\n"
        "On received quantities: control bills based on received quantity.", default="receive")
    route_ids = fields.Many2many(default=lambda self: self._get_buy_route())
    purchase_line_warn = fields.Selection(WARNING_MESSAGE, 'Purchase Order Line', help=WARNING_HELP, required=True, default="no-message")
    purchase_line_warn_msg = fields.Text('Message for Purchase Order Line')
    check_route = fields.Boolean(store=True, default=True)


class ProductProduct(models.Model):
    _name = 'product.product'
    _inherit = 'product.product'

    @api.multi
    def _purchase_count(self):
        domain = [
            ('state', 'in', ['purchase', 'done']),
            ('product_id', 'in', self.mapped('id')),
        ]
        PurchaseOrderLines = self.env['purchase.order.line'].search(domain)
        for product in self:
            product.purchase_count = len(PurchaseOrderLines.filtered(lambda r: r.product_id == product).mapped('order_id'))

    purchase_count = fields.Integer(compute='_purchase_count', string='# Purchases')


class ProductCategory(models.Model):
    _inherit = "product.category"

    property_account_creditor_price_difference_categ = fields.Many2one(
        'account.account', string="Price Difference Account",
        company_dependent=True,
        help="This account will be used to value price difference between purchase price and accounting cost.")


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    @api.multi
    def mail_purchase_order_on_send(self):
        if self._context.get('purchase_mark_rfq_sent'):
            order = self.env['purchase.order'].browse(self._context['default_res_id'])
            if order.state == 'draft':
                order.state = 'sent'

    @api.multi
    def send_mail(self, auto_commit=False):
        if self._context.get('default_model') == 'purchase.order' and self._context.get('default_res_id'):
            order = self.env['purchase.order'].browse(self._context['default_res_id'])
            self = self.with_context(mail_post_autofollow=True, lang=order.partner_id.lang)
            self.mail_purchase_order_on_send()
        return super(MailComposeMessage, self).send_mail(auto_commit=auto_commit)





########################### Order Scheduling start ###################

class OrderScheduling(models.Model):
    """
    Order Scheduling for Open Order
    """
    _name = 'order.scheduling'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'id desc'

    name = fields.Char('Name', required=True, default='New')
    purchase_id = fields.Many2one('purchase.order', clickable=True, string='Purchase Order', required=True, copy=False)
    partner_id = fields.Many2one('res.partner', clickable=True, required=True, string='Vendor', )
    po_date = fields.Datetime('PO Date')
    start_date = fields.Date('Start Date', default=fields.Datetime.now)
    end_date = fields.Date('End Date', default=fields.Datetime.now)
    order_scheduling_line_ids = fields.One2many('order.scheduling.line', 'order_scheduling_id',
                                                string='Scheduling Lines')
    # Piyush: added field in tree 27-03-2020
    as_per_schedule = fields.Boolean('As Per Schedule')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Confirm'),
        ('approve', 'Approved'),
        ('cancel', 'Cancelled'),
        ('close', 'Closed'),
    ], "State", track_visibility='onchange', default='draft')

    company_id = fields.Many2one('res.company', 'Company', clickable=True, required=True, index=True,
                                 default=lambda self: self.env.user.company_id.id)

    @api.onchange('purchase_id')
    def onchange_purchase_id(self):
        # Piyush: code for making line ids null on cleaning PO
        self.order_scheduling_line_ids = ''
        # code ends here
        if self.purchase_id:
            self.partner_id = self.purchase_id.partner_id.id
            self.po_date = self.purchase_id.date_order or ''
            start_date = self.purchase_id.start_date or ''
            end_date = self.purchase_id.end_date or ''
            self.start_date = start_date
            self.end_date = end_date
            data = []
            if self.purchase_id.order_line:
                for line in self.purchase_id.order_line:
                    already_sch_qty = self.check_sch_created(line, line.product_id)
                    if already_sch_qty > 0.0:
                        pending_qty = line.product_qty - already_sch_qty
                    else:
                        pending_qty = line.product_qty
                    if pending_qty > 0:
                        val_data = (0, False, {
                            'product_id': line.product_id.id,
                            'product_uom': line.product_uom.id,
                            'purchase_id': self.purchase_id.id,
                            'purchase_line_id': line.id,
                            'po_qty': line.product_qty,
                            'start_date': start_date,
                            'end_date': end_date,
                            'already_scheduled_qty':already_sch_qty,
                            'pending_qty':pending_qty,
                            'company_id':self.company_id.id or False,
                        })
                        data.append(val_data)
            if len(data) > 0:
                self.order_scheduling_line_ids = data
            else:
                raise ValidationError(_('No Pending Qty!'))

    @api.model
    def create(self, vals):

        # Piyush: code for getting value of field from PO 03-03-2020
        check = self.env['purchase.order'].search([('id', '=', self.purchase_id.id)])
        for val in check:
            self.as_per_schedule = val.check.as_per_schedule

        # code ends  here

        if 'purchase_id' in vals and vals.get('purchase_id'):
            count = 1

            po = self.env['purchase.order'].browse(vals.get('purchase_id'))
            all_po_scheduling_rec = self.env['order.scheduling'].search(
                [('purchase_id', '=', po.id), ('company_id', '=', self.env.user.company_id.id)])
            if all_po_scheduling_rec:
                count = len(all_po_scheduling_rec.ids) + 1
            name = po.name + '/' + 'SCH-' + str(count)
            vals['name'] = name
        res = super(OrderScheduling, self).create(vals)

        ##### Update field order_scheduling_id in order_schedule_detail_line table
        if res.order_scheduling_line_ids:
            for line in res.order_scheduling_line_ids:
                if line.order_scheduling_detail_line_ids:
                    for dline in line.order_scheduling_detail_line_ids:
                        dline.update({'order_scheduling_id': res.id})

        # validating the schedule quantity

        if res.order_scheduling_line_ids:
            for line in res.order_scheduling_line_ids:

                # Piyush: code for preventing to save without creating order schedule 15-04-2020
                if line.product_qty <= 0:
                    raise ValidationError(_("Cannot proceed without creating order schedule."))
                # code ends here

                total_product_ammount = 0.0
                if line.order_scheduling_detail_line_ids:
                    for dline in line.order_scheduling_detail_line_ids:
                        total_product_ammount += dline.product_qty
                # if total_product_ammount > line.po_qty:
                #     raise ValidationError(_('Schedule Qty cannot greater than  po quantity'))

                # Piyush: code for validations qty check for pending qty 02-04-2020
                if total_product_ammount > line.pending_qty:
                    raise ValidationError(_('Schedule Qty cannot greater than  pending quantity'))
                # code ends here

        return res

    # abhishek
    @api.multi
    def write(self, vals):
        if 'purchase_id' in vals and vals.get('purchase_id'):
            po = self.env['purchase.order'].browse(vals.get('purchase_id'))
            all_po_scheduling_rec = self.env['order.scheduling'].search(
                [('purchase_id', '=', po.id), ('company_id', '=', self.env.user.company_id.id)])
            if all_po_scheduling_rec:
                count = len(all_po_scheduling_rec.ids) + 1
                name = po.name + '/' + 'SCH-' + str(count)
                vals['name'] = name
        res = super(OrderScheduling, self).write(vals)

        # validating the schedule quantity
        if self.order_scheduling_line_ids:
            for line in self.order_scheduling_line_ids:
                total_product_ammount = 0.0
                if line.order_scheduling_detail_line_ids:
                    for dline in line.order_scheduling_detail_line_ids:
                        total_product_ammount += dline.product_qty
                if total_product_ammount > line.po_qty:
                    raise ValidationError(_('Schedule Qty cannot greater than  po quantity'))

                # Piyush: code for validations qty check for pending qty 02-04-2020
                if total_product_ammount > line.pending_qty:
                    raise ValidationError(_('Schedule Qty cannot greater than  pending quantity'))
                # code ends here

        return res

    def check_sch_created(self, po_line_id, product_id):
        qty = 0.0
        sch_ids = self.env['order.scheduling.line'].search(
            [('purchase_line_id', '=', po_line_id.id), ('state', '!=', 'cancel')])
        print("sch idssssssssss", sch_ids)
        if len(sch_ids) > 0:
            for val in sch_ids:
                qty = qty + val.product_qty
        return qty

    @api.multi
    def action_state(self):
        state = ''
        state = self.env.context.get('state', '')
        total_schedule_qty = 0.0

        if state != '':

            ##### Can not Confirm or Approve if no Schedule Qty exist
            if state != 'cancel':
                self.env.cr.execute(
                    """SELECT SUM(product_qty) FROM order_scheduling_line WHERE company_id = %s AND order_scheduling_id = %s""",
                    (self.env.user.company_id.id, self.id))
                match_recs = self.env.cr.dictfetchall()
                if match_recs[0].get('sum', 0.0):
                    total_schedule_qty = match_recs[0].get('sum', 0.0)
                if total_schedule_qty <= 0.0:
                    raise ValidationError(_('Schedule Qty can not be 0 !'))
            ##### Can not Confirm or Approve if no Schedule Qty exist

            self.write({'state': state})




class OrderSchedulingLine(models.Model):
    """
    Order Scheduling Lines for Open Order
    """
    _name = 'order.scheduling.line'

    order_scheduling_id = fields.Many2one('order.scheduling', 'Order Scheduling')
    purchase_id = fields.Many2one('purchase.order', string='Purchase Order', required=True, copy=False)
    purchase_line_id = fields.Many2one('purchase.order.line', string='PO Line', required=True, copy=False)
    product_id = fields.Many2one('product.product', 'Product', clickable=True, required=True)
    product_uom = fields.Many2one('product.uom', string='UOM', required=True)
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    product_qty = fields.Float(compute='_compute_detail_product_qty', string='Total Schedule Qty', store=True)
    already_scheduled_qty = fields.Float('Already Schedued Qty')
    po_qty = fields.Float(string='PO Qty')
    order_scheduling_detail_ids = fields.One2many('order.scheduling.detail', 'order_scheduling_line_id',string='Scheduling Detail')
    order_scheduling_detail_line_ids = fields.One2many('order.scheduling.detail.line', 'order_scheduling_line_id',string="Scheduling Detail Lines")
    schedule_state = fields.Selection(related='order_scheduling_id.state', string='Schedule Status', store=True)
    company_id = fields.Many2one('res.company', 'Company', clickable=True, required=True, index=True,default=lambda self: self.env.user.company_id.id)
    cr_date = fields.Date(string='Create Date', required=True, readonly=True, index=True, copy=False,default=fields.Datetime.now)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Confirm'),
        ('approve', 'Approved'),
        ('cancel', 'Cancelled'),
        ('close', 'Closed'),
    ], "State", track_visibility='onchange', related="order_scheduling_id.state", store=True)
    pending_qty = fields.Float('Pending Qty')
    is_schedule_done = fields.Boolean('is Schedule Done', default=False)

    @api.multi
    @api.depends('order_scheduling_detail_line_ids.product_qty')
    def _compute_detail_product_qty(self):
        for line in self:
            total_product_qty = 0.0
            # match_recs = []
            if line.order_scheduling_detail_line_ids:
                for detail_line in line.order_scheduling_detail_line_ids:
                    total_product_qty = total_product_qty + detail_line.product_qty
                line.product_qty = total_product_qty


class OrderSchedulingDetail(models.Model):
    _description = 'Order Scheduling Detail'
    _name = "order.scheduling.detail"
    _inherit = ['mail.thread']

    name = fields.Char('Name')
    order_scheduling_id = fields.Many2one('order.scheduling', 'Order Scheduling')
    order_scheduling_line_id = fields.Many2one('order.scheduling.line', 'Order Scheduling Line')
    product_id = fields.Many2one('product.product', 'Product')
    product_uom = fields.Many2one('product.uom', string='UOM', required=True)
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    order_scheduling_detail_line_ids = fields.Many2many('order.scheduling.detail.line',
                                                        string="Scheduling Detail Lines")
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.user.company_id.id)
    cr_date = fields.Date(string='Create Date', required=True, readonly=True, index=True, copy=False,
                          default=fields.Datetime.now)

    @api.model
    def default_get(self, fields):
        res = super(OrderSchedulingDetail, self).default_get(fields)
        params = self.env.context.get('params')
        if params:
            if params.get('model') == 'order.scheduling':
                order_scheduling_id = params.get('id')
                if 'order_scheduling_id' in fields and 'order_scheduling_id' not in res:
                    ##### Update Order Scheduling Id when Detail button clickable before Line Save....because
                    ##### button default context on line level gives error when set it
                    res['order_scheduling_id'] = order_scheduling_id
        return res

    @api.onchange('product_id')
    def onchange_product_id(self):
        #salman add hsn value
        self.hsn_id=self.product_id.hsn_id.hsn_code
        #salman end
        result = {}
        if not self.product_id:
            return result
        ##### Set the values from session on change of product when the form opened from one2many button only when one2many line is not saved
        if not self.order_scheduling_line_id:
            scheduling_detail_session_id = request.session.session_token + self.env.context.get('active_model') + str(
                self.product_id.id)
            scheduling_detail_session = request.session.get(scheduling_detail_session_id, '')
            if scheduling_detail_session:
                self.name = scheduling_detail_session.get('name', '')
                self.company_id = scheduling_detail_session.get('company_id', False)
                self.cr_date = scheduling_detail_session.get('cr_date', '')
                self.order_scheduling_detail_line_ids = scheduling_detail_session.get('order_scheduling_detail_line',
                                                                                      [])
        return result

    @api.multi
    def scheduling_detail_data_save_on_session(self):
        order_scheduling_detail = {}
        order_scheduling_detail_line = []

        order_scheduling_detail['name'] = self.name or ''
        order_scheduling_detail[
            'order_scheduling_id'] = self.order_scheduling_id and self.order_scheduling_id.id or False
        order_scheduling_detail[
            'order_scheduling_line_id'] = self.order_scheduling_line_id and self.order_scheduling_line_id.id or False
        order_scheduling_detail['product_id'] = self.product_id and self.product_id.id or False
        order_scheduling_detail['product_uom'] = self.product_uom and self.product_uom.id or False
        order_scheduling_detail['start_date'] = self.start_date or ''
        order_scheduling_detail['end_date'] = self.end_date or ''
        order_scheduling_detail['company_id'] = self.company_id and self.company_id.id or False
        order_scheduling_detail['cr_date'] = self.cr_date or ''

        if self.order_scheduling_detail_line_ids:
            for line in self.order_scheduling_detail_line_ids:
                val_data = (0, False, {
                    'order_scheduling_detail_id': line.order_scheduling_detail_id and line.order_scheduling_detail_id.id or False,
                    'order_scheduling_id': line.order_scheduling_id and line.order_scheduling_id.id or False,
                    'order_scheduling_line_id': line.order_scheduling_line_id and line.order_scheduling_line_id.id or False,
                    'product_id': line.product_id and line.product_id.id or False,
                    'product_uom': line.product_uom and line.product_uom.id or False,
                    'product_qty': line.product_qty or 0.0,
                    'received_qty': line.received_qty or 0.0,
                    'date': line.date or '',
                    'start_date': line.start_date or '',
                    'end_date': line.end_date or '',
                    'remarks': line.remarks or '',
                    'picking_id': line.picking_id and line.picking_id.id or False,
                    'picking_date': line.picking_date or '',
                    'company_id': line.company_id and line.company_id.id or False,
                    'cr_date': line.cr_date or '',

                })
                order_scheduling_detail_line.append(val_data)
        order_scheduling_detail['order_scheduling_detail_line'] = order_scheduling_detail_line

        ##### Creating session key by concatenating session_toke, model object and product id
        scheduling_detail_session = request.session.session_token + self.env.context.get('active_model') + str(
            self.product_id.id)
        request.session[scheduling_detail_session] = order_scheduling_detail

        return {'type': 'ir.actions.do_nothing'}




class OrderSchedulingDetailLine(models.Model):
    _description = 'Order Scheduling Detail Line'
    _name = "order.scheduling.detail.line"
    _inherit = ['mail.thread']
    _order = 'date'

    order_scheduling_detail_id = fields.Many2one('order.scheduling.detail', 'Scheduling Detail')
    order_scheduling_line_id = fields.Many2one('order.scheduling.line', 'Order Scheduling Line')
    order_scheduling_id = fields.Many2one('order.scheduling', string='Order Scheduling')
    product_id = fields.Many2one('product.product', 'Product')
    product_uom = fields.Many2one('product.uom', string='UOM', required=True)
    product_qty = fields.Float(string="Schedule Qty", required=True)
    received_qty = fields.Float(string="Received Qty")
    pending_qty = fields.Float(compute='_compute_pending_qty', string="Pending Qty", store=True)
    rejected_qty = fields.Float(string="Rejected Qty")
    qc_pass_qty = fields.Float(string="QC Pass Qty")
    date = fields.Date('Date', required=True)
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    remarks = fields.Char('Remarks')
    picking_id = fields.Many2one('stock.picking', 'Receipt No')
    picking_date = fields.Date('Receipt Date')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,default=lambda self: self.env.user.company_id.id)
    cr_date = fields.Date(string='Create Date', required=True, readonly=True, index=True, copy=False,
                          default=fields.Datetime.now)
    state = fields.Selection([('draft', 'Draft'),
                              ('in_progress', 'In Progress'),
                              ('done', 'Done'),
                              ('cancel', 'Cancelled')],
                             'Status', track_visibility='onchange',
                             copy=False, default='draft')

    @api.onchange('date')
    def onchange_date(self):
        result = {}
        if not self.date:
            return result
        if self.start_date or self.end_date:
            if self.date < self.start_date or self.date > self.end_date:
                raise ValidationError(_('Date should be in between %s and %s !') % (self.start_date, self.end_date))
        return result

    @api.onchange('received_qty')
    def onchange_received_qty(self):
        result = {}
        if self.received_qty > 0.0:
            picking_id = self.env.context.get('default_picking_id', False)
            if picking_id:
                picking_id_browse = self.env['stock.picking'].browse(picking_id)
                self.picking_id = picking_id
                self.picking_date = picking_id_browse.cr_date
        else:
            self.picking_id = False
            self.picking_date = ''
        return result

    @api.multi
    @api.depends('product_qty', 'received_qty', 'state')
    def _compute_pending_qty(self):
        """
        Pending Qty = Schedule Qty - Received Qty
        """
        for line in self:
            if line.received_qty > 0:
                if line.state != 'done':
                    if line.received_qty > line.product_qty:
                        line.pending_qty = 0
                    else:
                        line.pending_qty = line.product_qty - line.received_qty
                else:
                    line.pending_qty = 0
            else:
                line.pending_qty = line.product_qty - line.received_qty

    @api.multi
    def unlink(self):
        for detail_line in self:
            if detail_line.received_qty > 0:
                raise ValidationError(
                    _('Cannot delete a line whose Received Quantity is greater then zero or not in Draft State!'))
            if detail_line.rejected_qty > 0:
                raise ValidationError(_('Cannot delete a line whose have Rejected Qty!'))
        return super(OrderSchedulingDetailLine, self).unlink()


class OrderCalculation(models.Model):
    _name = "order.calculation"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Order Calculation"
    _order = 'serial_no'

    name = fields.Char('Description')
    order_id = fields.Many2one('purchase.order', 'PO')
    category = fields.Char('Category')
    label = fields.Char('Label')
    amount = fields.Float('Amount')
    serial_no = fields.Integer('Sr No')
    company_id = fields.Many2one('res.company', 'Company', index=True,
                                 default=lambda self: self.env.user.company_id.id)
    cr_date = fields.Date(string='Create Date', required=True, readonly=True, index=True, copy=False,
                          default=fields.Datetime.now)
