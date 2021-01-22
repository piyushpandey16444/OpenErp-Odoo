# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, SUPERUSER_ID,_
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError
from datetime import datetime

class PurchaseRequisitionType(models.Model):
    _name = "purchase.requisition.type"
    _description = "Purchase Agreement Type"
    _order = "sequence"

    name = fields.Char(string='Agreement Type', required=True, translate=True)
    # shivam
    type = fields.Selection([
        ('arc', 'ARC'), ('open', 'Open Order')
    ])
    # shivam end
    sequence = fields.Integer(default=1)
    exclusive = fields.Selection([
        ('exclusive', 'Select only one RFQ (exclusive)'), ('multiple', 'Select multiple RFQ')],
        string='Agreement Selection Type', required=True, default='multiple',
        help="""Select only one RFQ (exclusive):  when a purchase order is confirmed, cancel the remaining purchase order.\n
                    Select multiple RFQ: allows multiple purchase orders. On confirmation of a purchase order it does not cancel the remaining orders""")
    quantity_copy = fields.Selection([
        ('copy', 'Use quantities of agreement'), ('none', 'Set quantities manually')],
        string='Quantities', required=True, default='none')
    line_copy = fields.Selection([
        ('copy', 'Use lines of agreement'), ('none', 'Do not create RfQ lines automatically')],
        string='Lines', required=True, default='copy')


class PurchaseRequisition(models.Model):
    _name = "purchase.requisition"
    _description = "Purchase Requisition"
    _inherit = ['mail.thread']
    _order = "id desc"

    def _get_picking_in(self):
        pick_in = self.env.ref('stock.picking_type_in', raise_if_not_found=False)
        company = self.env['res.company']._company_default_get('purchase.requisition')
        if not pick_in or pick_in.sudo().warehouse_id.company_id.id != company.id:
            pick_in = self.env['stock.picking.type'].search(
                [('warehouse_id.company_id', '=', company.id), ('code', '=', 'incoming')],
                limit=1,
            )
        return pick_in

    def _get_type_id(self):
        return self.env['purchase.requisition.type'].search([], limit=1)

    # name = fields.Char(string='Agreement Reference', required=True, copy=False, default= lambda self: self.env['ir.sequence'].next_by_code('purchase.order.requisition'))
    name = fields.Char(string='Agreement Reference', required=True, copy=False, default='New')
    # Piyush: order value field in PA related to order value in PA lines 08-05-2020
    order_value = fields.Float(compute="_compute_order_value_till_date", string='Order Value Till Date')
    # code ends here
    origin = fields.Char(string='Source Document')
    order_count = fields.Integer(compute='_compute_orders_number', string='Number of Orders')
    vendor_id = fields.Many2one('res.partner', string="Vendor", required=True)
    type_id = fields.Many2one('purchase.requisition.type', string="Agreement Type", required=True, default=_get_type_id)
    ordering_date = fields.Date(string="Ordering Date")
    date_end = fields.Datetime(string='Agreement Deadline')
    schedule_date = fields.Date(string='Delivery Date', index=True,
                                help="The expected and scheduled delivery date where all the products are received")
    user_id = fields.Many2one('res.users', string='Responsible', default=lambda self: self.env.user)
    description = fields.Text()
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env['res.company']._company_default_get(
                                     'purchase.requisition'))
    purchase_ids = fields.One2many('purchase.order', 'requisition_id', string='Purchase Orders',
                                   states={'done': [('readonly', True)]})
    line_ids = fields.One2many('purchase.requisition.line', 'requisition_id', string='Products to Purchase',
                               states={'done': [('readonly', True)]}, copy=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')
    state = fields.Selection([('draft', 'Draft'), ('in_progress', 'Confirmed'),
                              ('open', 'Bid Selection'), ('done', 'Done'),
                              ('cancel', 'Cancelled')],
                             'Status', track_visibility='onchange', required=True,
                             copy=False, default='draft')
    account_analytic_id = fields.Many2one('account.analytic.account', 'Analytic Account')
    picking_type_id = fields.Many2one('stock.picking.type', 'Operation Type', required=True, default=_get_picking_in)

    # start date field
    start_date = fields.Datetime(string='Start Date')
    commitment_value = fields.Float(string='Commitment Value')
    # Piyush: field added for amendment on 08-05-2020
    ammendmend_count = fields.Integer(compute='_compute_ammendmend_number', string='Number of Amendment')
    requisition_amd_ids = fields.One2many('purchase.requisition.amd', 'requisition_id',
                                          string='Requisition Amendment', readonly=True)


    amount_untaxed = fields.Monetary(string='Untaxed Amount', store=True, readonly=True, compute='_amount_all',
                                     track_visibility='always')
    amount_tax = fields.Monetary(string='Taxes', store=True, readonly=True, compute='_amount_all')
    amount_total = fields.Monetary(string='Total', store=True, readonly=True, compute='_amount_all')

    currency_id = fields.Many2one('res.currency', 'Currency', required=True, \
                                  default=lambda self: self.env.user.company_id.currency_id.id)

    # Shivam code for generating sequence number automatically while creation of purchase agreement 19-10-2020
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('purchase.requisition.seq1') or _('New')
        result = super(PurchaseRequisition, self).create(vals)
        return result

    # shivam code for restricting duplicate product line entry 16-10-2020
    @api.multi
    @api.constrains('line_ids')
    def _check_exist_product_in_line(self):
        for rec in self:
            exist_product_list = []
            for line in rec.line_ids:
                if line.product_id.id in exist_product_list:
                    raise UserError(_('Product should be one per line.'))
                exist_product_list.append(line.product_id.id)

    # Shivam code for checking price unit when agreement is of open order type, making product_id mandatory field 13-10-2020

    @api.multi
    @api.constrains('commitment_value', 'type_id', 'line_ids')
    def _check_values(self):
        print("shivam in _check_values", self.type_id.type)

        if self.commitment_value <= 0.0 and self.type_id.type == 'arc':
            raise UserError(_('Commitment Value should not be zero for ARC agreement type'))
        if not self.line_ids:
            raise UserError(_('At least add 1 product for creating Purchase Agreement'))

    # Shivam code to validate agreement date based on start date 14-10-2020

    @api.multi
    @api.constrains('date_end', 'start_date')
    def date_check(self):
        print("shivam on######################################################################################33")

        for rec in self:
            if rec.date_end and rec.start_date:
                print("shivam date", rec.date_end)

                end_d = rec.date_end
                start_d = rec.start_date
                if start_d > end_d:
                    raise UserError(_('You cannot select agreement deadline date before start date'))

    # Shivam code for computing total amount in purchase agreement 14-10-2020

    @api.depends('line_ids.price_total')
    def _amount_all(self):
        for order in self:
            # print("amount_tax", order.amount_tax)
            # print("price_tax am", order.line_ids.price_tax)
            amount_untaxed = amount_tax = 0.0
            for line in order.line_ids:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            order.update({
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'amount_total': amount_untaxed,
            })
            # print("amount_tax2", order.amount_tax)
            # print("amount_total", order.amount_total)

    # Shivam code ends

    # Piyush: code to compute total order value on 09-05-2020
    @api.one
    @api.depends('line_ids.order_value')
    def _compute_order_value_till_date(self):
        for value in self:
            order_value_till_date = 0.0
            for loop in value.line_ids:
                order_value_till_date += loop.order_value
            value.order_value = order_value_till_date
    # code ends here

    # Piyush: code to count amendment when type is arc on 08-05-2020
    @api.multi
    @api.depends('requisition_amd_ids')
    def _compute_ammendmend_number(self):
        for requisition in self:
            requisition.ammendmend_count = len(requisition.requisition_amd_ids)

    def get_current_ammendmend_history(self):
        """
        Get Current Form Agreement Ammendmend History
        """
        result = {}
        all_agreements_amd_ids = []
        company_id = self.env.user.company_id.id
        all_agreements_amd = self.env['purchase.requisition.amd'].search(
            [('id', 'in', self.requisition_amd_ids and self.requisition_amd_ids.ids or []),
             ('company_id', '=', company_id)])
        if all_agreements_amd:
            all_agreements_amd_ids = all_agreements_amd.ids
        action = self.env.ref('purchase_requisition.action_purchase_requisition_amd')
        result = action.read()[0]
        res = self.env.ref('purchase_requisition.view_purchase_requisition_amd_tree', False)
        res_form = self.env.ref('purchase_requisition.view_purchase_requisition_amd_form', False)
        result['views'] = [(res and res.id or False, 'list'), (res_form and res_form.id or False, 'form')]
        result['domain'] = [('id', 'in', tuple(all_agreements_amd_ids))]
        result['target'] = 'current'
        result['view_type'] = 'tree'
        result['view_mode'] = 'tree,form'
        return result

    # code ends here

    @api.multi
    @api.depends('purchase_ids')
    def _compute_orders_number(self):
        for requisition in self:
            requisition.order_count = len(requisition.purchase_ids)

    @api.multi
    def action_cancel(self):
        # try to set all associated quotations to cancel state
        for requisition in self:
            requisition.purchase_ids.button_cancel()
            for po in requisition.purchase_ids:
                po.message_post(body=_('Cancelled by the agreement associated to this quotation.'))
        self.write({'state': 'cancel'})

    @api.multi
    def action_in_progress(self):
        if not all(obj.line_ids for obj in self):
            raise UserError(_('You cannot confirm call because there is no product line.'))
        self.write({'state': 'in_progress'})

    @api.multi
    def action_open(self):
        self.write({'state': 'open'})

    @api.multi
    def action_draft(self):
        self.write({'state': 'draft'})

    @api.multi
    def action_done(self):
        """
        Generate all purchase order based on selected lines, should only be called on one agreement at a time
        """
        if any(purchase_order.state in ['draft', 'sent', 'to approve'] for purchase_order in
               self.mapped('purchase_ids')):
            raise UserError(_('You have to cancel or validate every RfQ before closing the purchase requisition.'))
        self.write({'state': 'done'})

    def _prepare_tender_values(self, product_id, product_qty, product_uom, location_id, name, origin, values):
        return {
            'origin': origin,
            'date_end': values['date_planned'],
            'warehouse_id': values.get('warehouse_id') and values['warehouse_id'].id or False,
            'company_id': values['company_id'].id,
            'line_ids': [(0, 0, {
                'product_id': product_id.id,
                'product_uom_id': product_uom.id,
                'product_qty': product_qty,
                'move_dest_id': values.get('move_dest_ids') and values['move_dest_ids'][0].id or False,
            })],
        }

    # Piyush: code for amendment function data creation on 08-05-2020

    def _amendment_data(self, amd_name):
        line_data_list = []
        if self.line_ids:
            for line in self.line_ids:
                line_data = (0, False, {
                    'product_id': line.product_id and line.product_id.id or False,
                    'hsn_id':line.hsn_id,
                    'product_uom_id': line.product_uom_id and line.product_uom_id.id or False,
                    'product_qty': line.product_qty or 0.0,
                    'price_unit': line.price_unit or 0.0,
                    'qty_ordered': line.qty_ordered or 0.0,
                    'requisition_id': line.requisition_id and line.requisition_id.id or False,
                    'company_id': line.company_id and line.company_id.id or False,
                })
                line_data_list.append(line_data)

        amd_vals = {
            'name': amd_name,
            'requisition_id': self.id or False,
            'vendor_id': self.vendor_id and self.vendor_id.id or False,
            'date_end': self.date_end,
            'start_date': self.start_date,
            'type_id': self.type_id and self.type_id.id or False,
            'company_id': self.company_id and self.company_id.id or False,
            'state': self.state or '',
            'commitment_value': self.commitment_value or 0.0,
            'line_amd_ids': line_data_list,
        }
        return amd_vals

    # code ends here

    # Piyush: code for write function of purchase requisition on 08-05-2020

    @api.multi
    def write(self, vals):

        # Preparing Ammendmend Data

        amd_name = ''
        if self.requisition_amd_ids:
            amd_count = len(self.requisition_amd_ids.ids)
            amd_name = 'AMD' + str(amd_count)
        else:
            amd_name = 'AMD'
        amd_data = self._amendment_data(amd_name)

        # Preparing Ammendmend Data

        res = super(PurchaseRequisition, self).write(vals)
        if 'state' not in vals and self.state == 'open':
            if 'commitment_value' in vals or 'line_ids' in vals or 'start_date' in vals or 'date_end' in vals or 'line_ids.product_qty' in vals:
                self.env['purchase.requisition.amd'].create(amd_data)
                self.update({'state': 'in_progress'})
        if 'priority' in vals and vals['priority']:
            for lines in self.line_ids:
                lines.update({'priority': vals['priority']})

        return res

    # code ends here


# Piyush: code for creating amendment on 08-05-2020


class PurchaseRequisitionAmd(models.Model):
    _name = "purchase.requisition.amd"
    _description = "Purchase Requisition Amendment"
    _inherit = ['mail.thread']
    _order = "id desc"

    name = fields.Char(string='Amendment No')
    requisition_id = fields.Many2one('purchase.requisition', string='Agreement No')
    origin = fields.Char(string='Source Document')
    vendor_id = fields.Many2one('res.partner', string="Vendor")
    date_end = fields.Datetime(string='Agreement Deadline')
    type_id = fields.Many2one('purchase.requisition.type', string="Agreement Type")
    description = fields.Text()
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env['res.company']._company_default_get(
                                     'purchase.requisition'))
    line_amd_ids = fields.One2many('purchase.requisition.line.amd', 'requisition_amd_id', string='Products to Purchase')
    state = fields.Selection([('draft', 'Draft'), ('in_progress', 'Confirmed'),
                              ('open', 'Bid Selection'), ('done', 'Close'),
                              ('cancel', 'Cancelled')],
                             'Status')

    product_rel_id = fields.Many2one('product.product', related='line_amd_ids.product_id', store=True)
    commitment_value = fields.Float(string='Commitment Value', track_visibility='onchange', )
    start_date = fields.Datetime(string='Start Date')
    reference_no = fields.Char(string='Reference No')
    cr_date = fields.Date(string='Create Date', required=True, readonly=True, index=True, copy=False,
                          default=fields.Datetime.now)
    assigned_id = fields.Many2one('hr.employee', 'Assigned To', help="Assigned a person for approval")


class PurchaseRequisitionLineAmd(models.Model):
    _name = "purchase.requisition.line.amd"
    _description = "Purchase Requisition Line Amendment"
    _rec_name = 'product_id'

    # Salman add Hsn field
    hsn_id=fields.Char(string='HSN code')
    # Salman end
    requisition_amd_id = fields.Many2one('purchase.requisition.amd', string='AMD No')
    product_id = fields.Many2one('product.product', string='Product')
    product_uom_id = fields.Many2one('product.uom', string='Product Unit of Measure')
    product_qty = fields.Float(string='Quantity', digits=dp.get_precision('Product Unit of Measure'))
    price_unit = fields.Float(string='Unit Price', digits=dp.get_precision('Product Price'))
    qty_ordered = fields.Float(string='Ordered Quantities')
    requisition_id = fields.Many2one('purchase.requisition', string='Purchase Agreement')
    company_id = fields.Many2one('res.company', related='requisition_id.company_id', string='Company', store=True,
                                 readonly=True, default=lambda self: self.env['res.company']._company_default_get(
            'purchase.requisition.line'))
    purchase_id = fields.Many2one('purchase.order', 'Last PO', help="Last PO of Requested Product and Supplier")
    cr_date = fields.Date(string='Create Date', required=True, readonly=True, index=True, copy=False,
                          default=fields.Datetime.now)
    taxes_id = fields.Many2many('account.tax', string='Taxes',
                                domain=['|', ('active', '=', False), ('active', '=', True)])


# code ends here


class PurchaseRequisitionLine(models.Model):
    _name = "purchase.requisition.line"
    _description = "Purchase Requisition Line"
    _rec_name = 'product_id'

        # Salman add Hsn field
    hsn_id=fields.Char(string='HSN code')
    # Salman end 
    product_id = fields.Many2one('product.product', string='Product', domain=[('purchase_ok', '=', True)],
                                 required=True)
    product_uom_id = fields.Many2one('product.uom', string='Product Unit of Measure')
    product_qty = fields.Float(string='Quantity', digits=dp.get_precision('Product Unit of Measure'), default='1')
    # Piyush: code for adding field to make quantity readonly on 07-05-2020
    quantity_hide = fields.Boolean('Hide Field', help="field to make quantity readonly for arc")
    # Piyush: two fields added for qty on 07-05-2020
    receipt_qty = fields.Float(compute="_compute_receipt_value", string='Receipt Qty')
    order_value = fields.Float(compute='_compute_order_value', string='Order Value')
    # Piyush: code for adding taxes in SA on 24-07-2020
    tax_ids = fields.Many2many('account.tax', 'requisition_tax_rel_purchase', 'requisition_id', 'tax_id', 'Taxes')
    # code ends here
    price_unit = fields.Float(string='Unit Price', digits=dp.get_precision('Product Price'))
    qty_ordered = fields.Float(compute='_compute_ordered_qty', string='Ordered Quantities')
    requisition_id = fields.Many2one('purchase.requisition', string='Purchase Agreement', ondelete='cascade')
    company_id = fields.Many2one('res.company', related='requisition_id.company_id', string='Company', store=True,
                                 readonly=True, default=lambda self: self.env['res.company']._company_default_get(
            'purchase.requisition.line'))
    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    schedule_date = fields.Date(string='Scheduled Date')
    move_dest_id = fields.Many2one('stock.move', 'Downstream Move')
    # Piyush: code for adding type_id field in PRL to make qty field readonly on 09-05-2020
    type_id = fields.Many2one(related="requisition_id.type_id", string="Agreement Type")
    # code ends here

    price_subtotal = fields.Monetary(compute='_compute_amount', string='Subtotal', store=True)
    price_total = fields.Monetary(compute='_compute_amount', string='Total', store=True)
    price_tax = fields.Float(compute='_compute_amount', string='Tax', store=True)
    currency_id = fields.Many2one(related='requisition_id.currency_id', store=True, string='Currency', readonly=True)

    # Shivam code for checking price unit when agreement is of open order type on 10-10--2020
    @api.multi
    @api.constrains('price_unit', 'type_id')
    def _check_values(self):
        print("shivam in _check_values2", self.type_id)

        if self.price_unit <= 0.0:
            raise UserError(_('Unit Price should not be zero'))

    # Shivam code for computing total amount in purchase agreement line
    @api.depends('product_qty', 'price_unit', 'tax_ids')
    def _compute_amount(self):
        for line in self:
            taxes = line.tax_ids.compute_all(line.price_unit, line.requisition_id.currency_id, line.product_qty,
                                             product=line.product_id, partner=line.requisition_id.vendor_id)
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })

    # Shivam code ends

    @api.multi
    @api.depends('requisition_id.purchase_ids.state')
    def _compute_ordered_qty(self):
        for line in self:
            total = 0.0
            for po in line.requisition_id.purchase_ids.filtered(
                    lambda purchase_order: purchase_order.state in ['purchase', 'done']):
                for po_line in po.order_line.filtered(lambda order_line: order_line.product_id == line.product_id):
                    if po_line.product_uom != line.product_uom_id:
                        total += po_line.product_uom._compute_quantity(po_line.product_qty, line.product_uom_id)
                    else:
                        total += po_line.product_qty
            line.qty_ordered = total

    # Piyush: code for calculating receipt and order value on 08-05-2020
    @api.multi
    @api.depends('requisition_id.purchase_ids.state')
    def _compute_order_value(self):
        for val in self:
            order_value = 0.0
            for po in val.requisition_id.purchase_ids.filtered(
                    lambda purchase_order: purchase_order.state in ['purchase', 'done']):
                for po_line in po.order_line.filtered(lambda order_line: order_line.product_id == val.product_id):
                    if po_line.product_uom != val.product_uom_id:
                        order_value += po_line.product_uom._compute_quantity(po_line.price_subtotal, val.product_uom_id)
                    else:
                        order_value += po_line.price_subtotal
            val.order_value = order_value

    # Piyush: here code is written to take receipt qty fields in PA lines from receipts but the qty_received in the
    # PO Lines is to me changed as it is not fetching correct value that is done qty from receipt on 09-05-2020

    @api.multi
    @api.depends('requisition_id.purchase_ids.picking_ids.state')
    def _compute_receipt_value(self):
        for val in self:
            receipt_value = 0.0
            for po in val.requisition_id.purchase_ids.filtered(
                    lambda purchase_order: purchase_order.state in ['purchase', 'done']):
                for ord_line in po.order_line.filtered(lambda order_line: order_line.product_id == val.product_id):
                    if ord_line.product_uom != val.product_uom_id:
                        receipt_value += ord_line.product_uom._compute_quantity(ord_line.qty_received, val.product_uom_id)
                    else:
                        receipt_value += ord_line.qty_received
            val.receipt_qty = receipt_value

    # code ends here

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom_id = self.product_id.uom_id
            self.product_qty = 1.0
        if not self.account_analytic_id:
            self.account_analytic_id = self.requisition_id.account_analytic_id
        if not self.schedule_date:
            self.schedule_date = self.requisition_id.schedule_date

        #salman add hsn value
        self.hsn_id=self.product_id.hsn_id.hsn_code
        #salman end
        # Piyush: code for picking taxes in PA on 24-07-2020
        self.tax_ids = ''
        required_taxes = []
        product = self.product_id

        if self.requisition_id.vendor_id and self.requisition_id.vendor_id.vat and product:

            # GST present , company registered
            check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.company_id.id)])
            check_delivery_address = self.requisition_id.vendor_id

            # checking company state and customer state is same or not
            if check_cmpy_state.state_id == check_delivery_address.state_id:

                # if same states show taxes like CGST SGST GST
                self.env.cr.execute(
                    """ select id from account_tax where active=True and type_tax_use='purchase' AND tax_group_id!=4 and company_id='%s'""" % (
                        self.env.user.company_id.id,))
                csgst_taxes = self.env.cr.dictfetchall()

                all_sale_taxes = []
                for val in self:
                    all_sale_taxes = val.product_id.vendor_tax_lines
                all_taxes_list = [taxes.tax_id.id for taxes in all_sale_taxes]

                all_tax_list = [all_tax['id'] for all_tax in csgst_taxes]

                for tax in all_tax_list:
                    for tax_id in all_taxes_list:
                        if tax == tax_id:
                            required_taxes.append(tax)

            elif check_cmpy_state.state_id != check_delivery_address.state_id:

                # if different states show taxes like IGST
                self.env.cr.execute(
                    """ select id from account_tax where active=True and type_tax_use='purchase' AND tax_group_id not in (2,3) and company_id='%s'""" % (
                        self.env.user.company_id.id,))
                igst_taxes = self.env.cr.dictfetchall()

                all_sale_taxes = []
                for val in self:
                    all_sale_taxes = val.product_id.vendor_tax_lines
                all_taxes_list = [taxes.tax_id.id for taxes in all_sale_taxes]

                all_tax_list = [all_tax['id'] for all_tax in igst_taxes]

                for tax in all_tax_list:
                    for tax_id in all_taxes_list:
                        if tax == tax_id:
                            required_taxes.append(tax)

            self.update({'tax_ids': [(6, 0, required_taxes)]})

            # code ends here
    # salman add hsn_id 
    @api.multi
    def _prepare_purchase_order_line(self, name, product_qty=0.0, price_unit=0.0):
        self.ensure_one()
        requisition = self.requisition_id
        return {
            'name': name,
            'product_id': self.product_id.id,
            'hsn_id':self.hsn_id,
            'product_uom': self.product_id.uom_po_id.id,
            'product_qty': product_qty,
            'price_unit': price_unit,
            'taxes_id': self.tax_ids or False,
            'date_planned': requisition.schedule_date or fields.Date.today(),
            'account_analytic_id': self.account_analytic_id.id,
            'move_dest_ids': self.move_dest_id and [(4, self.move_dest_id.id)] or []
        }


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if self.partner_id:
            for rec in self:
                return {'domain': {'requisition_id': [('vendor_id', '=', rec.partner_id.id), ('state', '=', 'open'),
                                                      ('date_end', '>=', datetime.today())]}}

    requisition_id = fields.Many2one('purchase.requisition', string='Purchase Agreement', copy=False,
                                     domain=[('state', '=', 'open'), ('date_end', '>=', datetime.today())])

    # Gaurav 31/3/20 added code for default tax state wise in PA to PO tax
    def _compute_purchase_tax(self):

        # Getting default taxes
        FiscalPosition = self.env['account.fiscal.position']
        fpos = FiscalPosition.get_fiscal_position(self.partner_id.id)
        fpos = FiscalPosition.browse(fpos)
        # fpos = self.order_id.fiscal_position_id
        if self.env.uid == SUPERUSER_ID:
            print("purchase super")
            company_id = self.env.user.company_id.id
            requisition= self.requisition_id
            # taxes_id = fpos.map_tax(
            #     self.product_id.supplier_taxes_id.filtered(lambda r: r.company_id.id == company_id))
            for line in requisition.line_ids:
                #Jatin code added to add taxes from vendor_tax_lines
                filter_tax = []
                for val in line:
                    check = val.product_id.vendor_tax_lines
                    for rec in check:
                        tax_check = rec.tax_id.id
                        print(tax_check)
                        filter_tax.append(tax_check)

                print_tax = self.env['account.tax'].search([('id', 'in', filter_tax)])
                print("print_tax in function", print_tax)

                taxes_id = print_tax.filtered(lambda r: r.company_id.id == company_id)
                #end Jatin

            # taxes_ids = line.product_id.supplier_taxes_id.filtered(lambda tax: tax.company_id == requisition.company_id).ids

            print("self.taxes_iddddddd", taxes_id, self.partner_id.id)
            taxes_ids_list = taxes_id.ids

            # Gaurav 12/3/20 added code for default tax state wise
            check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
            check_custmr_state = self.env['res.partner'].search(
                [('id', '=', self.partner_id.id), ('company_id', '=', self.env.user.company_id.id)])
            print("purchase checkingggggggggggg",check_custmr_state.state_id,check_cmpy_state.state_id)
            check_partner = self.env['res.partner'].search([('id', '=', self.partner_id.id)])

            if check_partner.vat:
            # GST present , vendor registered
                if check_cmpy_state.state_id == check_custmr_state.state_id:
                    print("same state")
                    self.env.cr.execute(
                        """ select id from account_tax where active=True and type_tax_use='purchase' AND tax_group_id not in (2,3) and company_id='%s'""" % (
                            self.env.user.company_id.id,))
                    csgst_taxes = self.env.cr.dictfetchall()
                    print("csgst_taxesvvvvvvvvvvvvvvvv", csgst_taxes)
                    tax_id_list = [taxes_ids_list.remove(val.get('id')) for val in csgst_taxes if
                                   val.get('id') in taxes_ids_list if csgst_taxes]

                    print("purchase finalvvvvvvvvvvvvvvvv", taxes_ids_list)

                    self.taxes_id = taxes_ids_list
                    tax_show = (taxes_ids_list)


                elif check_cmpy_state.state_id != check_custmr_state.state_id:
                    print("diff state")

                    self.env.cr.execute(
                        """ select id from account_tax where active=True and type_tax_use='purchase' AND tax_group_id!=4 and company_id='%s'""" % (
                            self.env.user.company_id.id,))
                    igst_taxes = self.env.cr.dictfetchall()
                    tax_id_list = [taxes_ids_list.remove(val.get('id')) for val in igst_taxes if
                                   val.get('id') in taxes_ids_list if igst_taxes]

                    print("purchase finalvvvvvvvvvvvvvvvv", taxes_ids_list)

                    self.taxes_id = taxes_ids_list
                    tax_show = (taxes_ids_list)

                return tax_show
                # result= {'taxes_ids': [tax_id_list]}
                # result= {'domain': {'taxes_id': [tax_id_list]}}
                # result= {'domain': {'taxes_id': [tax_id_list], 'type_tax_use': 'purchase'}}


            else:
                print("normal")
                # Jatin code added to add taxes from vendor_tax_lines
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
                taxes_id = fpos.map_tax(print_tax)
                # end Jatin

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

                    print("purchase finalvvvvvvvvvvvvvvvv", taxes_ids_list)

                    self.taxes_id = taxes_ids_list
                    tax_show = (taxes_ids_list)


                elif check_cmpy_state.state_id != check_custmr_state.state_id:
                    print("diff state")

                    self.env.cr.execute(
                        """ select id from account_tax where active=True and type_tax_use='purchase' AND tax_group_id!=4 and company_id='%s'""" % (
                            self.env.user.company_id.id,))
                    igst_taxes = self.env.cr.dictfetchall()
                    tax_id_list = [taxes_ids_list.remove(val.get('id')) for val in igst_taxes if
                                   val.get('id') in taxes_ids_list if igst_taxes]

                    print("purchase finalvvvvvvvvvvvvvvvv", taxes_ids_list)

                    self.taxes_id = taxes_ids_list
                    tax_show = (taxes_ids_list)

                return tax_show


                # result= {'domain': {'taxes_id': [tax_id_list]}}
                # result= {'domain': {'taxes_id': [tax_id_list], 'type_tax_use': 'purchase'}}




    @api.onchange('requisition_id')
    def _onchange_requisition_id(self):
        # shivam code for restricting user to select agreement of which start date is in future
        if self.requisition_id.start_date:
            date_time_str = self.requisition_id.start_date
            date_time_obj = datetime.strptime(date_time_str, '%Y-%m-%d %H:%M:%S')
            print('*********', self.requisition_id.start_date)
            if date_time_obj > datetime.today():
                raise UserError(_('You can not select the agreement before start_date of agreement'))

        # shivam code ends
        self.order_line = ''
        if not self.requisition_id:
            # Piyush: code for taking default date when no id is there on 31-03-2020
            self.start_date = fields.Datetime.now()
            self.end_date = fields.Datetime.now()
            # code ends here

            return

        requisition = self.requisition_id
        if self.partner_id:
            partner = self.partner_id
        else:
            partner = requisition.vendor_id
        payment_term = partner.property_supplier_payment_term_id
        currency = partner.property_purchase_currency_id or requisition.company_id.currency_id

        FiscalPosition = self.env['account.fiscal.position']
        fpos = FiscalPosition.get_fiscal_position(partner.id)
        fpos = FiscalPosition.browse(fpos)

        self.partner_id = partner.id
        self.fiscal_position_id = fpos.id
        self.payment_term_id = payment_term.id
        self.company_id = requisition.company_id.id
        self.currency_id = currency.id
        origin = ''
        self.origin = ''
        if not self.origin or requisition.name not in self.origin.split(', '):
            if self.origin:
                if requisition.name:
                    self.origin = self.origin + ', ' + requisition.name
            else:
                self.origin = requisition.name
        self.notes = requisition.description

        # Piyush: code for picking correct date from purchase agreement 28-03-2020
        self.date_order = requisition.ordering_date or fields.Datetime.now()
        self.start_date = requisition.start_date or ''
        self.end_date = requisition.date_end or fields.Datetime.now()
        # Code ends here

        self.picking_type_id = requisition.picking_type_id.id

        if requisition.type_id.line_copy != 'copy':
            return

        # Create PO lines if necessary
        order_lines = []
        for line in requisition.line_ids:
            # Compute name
            product_lang = line.product_id.with_context({
                'lang': partner.lang,
                'partner_id': partner.id,
            })
            name = product_lang.display_name
            if product_lang.description_purchase:
                name += '\n' + product_lang.description_purchase

            # Compute taxes
            # # Jatin code added to add taxes from vendor_tax_lines
            # filter_tax = []
            # for val in line:
            #     check = val.product_id.vendor_tax_lines
            #     print("check", check)
            #     for rec in check:
            #         tax_check = rec.tax_id.id
            #         print(tax_check)
            #         filter_tax.append(tax_check)
            #     print('filter_tax', filter_tax)
            #
            # print_tax = self.env['account.tax'].search([('id', 'in', filter_tax)])
            # print("print_tax in function", print_tax)
            # Piyush: commented function on 25-07-2020
            # tax_show=self._compute_purchase_tax()
            # taxes_ids=tax_show
            # if fpos:
            #     taxes_ids = fpos.map_tax(print_tax.filtered(
            #         lambda tax: tax.company_id == requisition.company_id)).ids
            # else:
            #     taxes_ids = print_tax.filtered(
            #         lambda tax: tax.company_id == requisition.company_id).ids

            # end Jatin
            # if fpos:
            #     taxes_ids = fpos.map_tax(line.product_id.supplier_taxes_id.filtered(
            #         lambda tax: tax.company_id == requisition.company_id)).ids
            # else:
            #     taxes_ids = line.product_id.supplier_taxes_id.filtered(
            #         lambda tax: tax.company_id == requisition.company_id).ids

            # Compute quantity and price_unit
            if line.product_uom_id != line.product_id.uom_po_id:
                product_qty = line.product_uom_id._compute_quantity(line.product_qty, line.product_id.uom_po_id)
                price_unit = line.product_uom_id._compute_price(line.price_unit, line.product_id.uom_po_id)
            else:
                product_qty = line.product_qty
                price_unit = line.price_unit

            if requisition.type_id.quantity_copy != 'copy':
                product_qty = 0

            # Compute price_unit in appropriate currency
            if requisition.company_id.currency_id != currency:
                price_unit = requisition.company_id.currency_id.compute(price_unit, currency)

            # Create PO line
            order_line_values = line._prepare_purchase_order_line(name=name, product_qty=product_qty, price_unit=price_unit)
            order_lines.append((0, 0, order_line_values))
        self.order_line = order_lines

    @api.multi
    def button_approve(self, force=False):
        res = super(PurchaseOrder, self).button_approve(force=force)
        for po in self:
            if not po.requisition_id:
                continue
            if po.requisition_id.type_id.exclusive == 'exclusive':
                others_po = po.requisition_id.mapped('purchase_ids').filtered(lambda r: r.id != po.id)
                others_po.button_cancel()
                po.requisition_id.action_done()
        return res

    @api.model
    def create(self, vals):
        purchase = super(PurchaseOrder, self).create(vals)
        if purchase.requisition_id:
            purchase.message_post_with_view('mail.message_origin_link',
                    values={'self': purchase, 'origin': purchase.requisition_id},
                    subtype_id=self.env['ir.model.data'].xmlid_to_res_id('mail.mt_note'))
        return purchase

    @api.multi
    def write(self, vals):
        result = super(PurchaseOrder, self).write(vals)
        if vals.get('requisition_id'):
            self.message_post_with_view('mail.message_origin_link',
                    values={'self': self, 'origin': self.requisition_id, 'edit': True},
                    subtype_id=self.env['ir.model.data'].xmlid_to_res_id('mail.mt_note'))
        return result


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    @api.onchange('product_qty', 'product_uom')
    def _onchange_quantity(self):
        res = super(PurchaseOrderLine, self)._onchange_quantity()
        if self.order_id.requisition_id:
            for line in self.order_id.requisition_id.line_ids:
                if line.product_id == self.product_id:
                    if line.product_uom_id != self.product_uom:
                        self.price_unit = line.product_uom_id._compute_price(
                            line.price_unit, self.product_uom)
                    else:
                        self.price_unit = line.price_unit
                    break
        return res


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    purchase_requisition = fields.Selection(
        [('rfq', 'Create a draft purchase order'),
         ('tenders', 'Propose a call for tenders')],
        string='Procurement', default='rfq')


class StockMove(models.Model):
    _inherit = "stock.move"

    requistion_line_ids = fields.One2many('purchase.requisition.line', 'move_dest_id')


class ProcurementGroup(models.Model):
    _inherit = 'procurement.group'

    @api.model
    def _get_exceptions_domain(self):
        return super(ProcurementGroup, self)._get_exceptions_domain() + [('requistion_line_ids', '=', False)]


class ProcurementRule(models.Model):
    _inherit = 'procurement.rule'

    @api.multi
    def _run_buy(self, product_id, product_qty, product_uom, location_id, name, origin, values):
        if product_id.purchase_requisition != 'tenders':
            return super(ProcurementRule, self)._run_buy(product_id, product_qty, product_uom, location_id, name, origin, values)
        values = self.env['purchase.requisition']._prepare_tender_values(product_id, product_qty, product_uom, location_id, name, origin, values)
        values['picking_type_id'] = self.picking_type_id.id
        self.env['purchase.requisition'].create(values)
        return True


class Orderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    def _quantity_in_progress(self):
        res = super(Orderpoint, self)._quantity_in_progress()
        for op in self:
            for pr in self.env['purchase.requisition'].search([('state', '=', 'draft'), ('origin', '=', op.name)]):
                for prline in pr.line_ids.filtered(lambda l: l.product_id.id == op.product_id.id):
                    res[op.id] += prline.product_uom_id._compute_quantity(prline.product_qty, op.product_uom,
                                                                          round=False)
        return res
