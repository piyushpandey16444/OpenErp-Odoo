# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, SUPERUSER_ID,_
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta, date


class SaleRequisition(models.Model):
    _name = "sale.requisition"
    _description = "Sale Requisition"
    _inherit = ['mail.thread']
    _order = "id desc"



    # salman: cote to genrate a sequence no. 12/10/2020
    @api.model
    def create(self,vals):
        if self.type_id=='arc':
            if self.commitment_value==0:
                raise UserError('Commitment value should not be zero')
        if vals.get('name',_('New'))==_('New'):
            vals['name']=self.env['ir.sequence'].next_by_code('sale.agreement') or _('New')
        result=super(SaleRequisition,self).create(vals)
        return result

    @api.onchange('start_date')
    def date_compare(self):
        if self.date_end:
            if self.date_end<self.start_date:
                raise UserError('Agreement Deadline  date should not less than start date')
            

    @api.onchange('date_end')
    def date_compare(self):
        if self.start_date:
            if self.start_date:
                if self.date_end<self.start_date:
                    raise UserError('Agreement Deadline  date should not less than start date')
            else:
                raise UserError('Please Enter the start date')
    # end salman


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

    @api.onchange('date_end')
    def onchange_date_end(self):
        if self.date_end:
            if self.start_date:
                from_date = datetime.strptime(self.start_date, '%Y-%m-%d %H:%M:%S').date()
                to_date = datetime.strptime(self.start_date, '%Y-%m-%d %H:%M:%S').date()
                if to_date < from_date:
                    print("Working")
                    raise ValidationError('Deadline date should be ahead of start date!')
            else:
                raise ValidationError('Please Enter The Start Date')

    name = fields.Char(string='Agreement Reference', readonly=True, copy=False)
    order_value = fields.Float(compute="_compute_order_value_till_date", string='Order Value Till Date')
    origin = fields.Char(string='Source Document')
    order_count = fields.Integer(compute='_compute_orders_number', string='Number of Orders')
    partner_id = fields.Many2one('res.partner', string="Customer", required=True)
    type_id = fields.Selection([('open', 'Open Order'), ('arc', 'Arc')], string="Agreement Type", required=True)
    ordering_date = fields.Date(string="Ordering Date", default=fields.datetime.now())
    date_end = fields.Datetime(string='Agreement Deadline')
    schedule_date = fields.Date(string='Delivery Date', index=True,
                                help="The expected and scheduled delivery date where all the products are received")
    user_id = fields.Many2one('res.users', string='Responsible', default=lambda self: self.env.user)
    description = fields.Text()
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env['res.company']._company_default_get(
                                     'sale.requisition'))
    sale_ids = fields.One2many('sale.order', 'requisition_id', string='Sale Orders',
                               states={'done': [('readonly', True)]})
    line_ids = fields.One2many('sale.requisition.line', 'requisition_id', string='Products to Sale',
                               states={'done': [('readonly', True)]}, copy=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')
    state = fields.Selection([('draft', 'Draft'), ('in_progress', 'Confirmed'),
                              ('open', 'Bid Selection'), ('done', 'Done'),
                              ('cancel', 'Cancelled')],
                             'Status', track_visibility='onchange', required=True,
                             copy=False, default='draft')
    account_analytic_id = fields.Many2one('account.analytic.account', 'Analytic Account')
    picking_type_id = fields.Many2one('stock.picking.type', 'Operation Type', required=True, default=_get_picking_in)
    start_date = fields.Datetime(string='Start Date')
    commitment_value = fields.Float(string='Commitment Value')
    # Piysuh code for adding amd fields on 26-06-2020
    amendment_count = fields.Integer(compute='_compute_amendment_number', string='Number of Amendment')
    requisition_amd_ids = fields.One2many('sale.requisition.amd', 'requisition_amd_id',
                                          string='Requisition Amendment', readonly=True)

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

    # # Piyush: code to count amendment when type is arc on 08-05-2020
    @api.multi
    @api.depends('requisition_amd_ids')
    def _compute_amendment_number(self):
        for requisition in self:
            requisition.amendment_count = len(requisition.requisition_amd_ids)

    def get_requisition_amendment_history(self):
        """
        Get Current Form Requisition Amendment History
        """
        result = {}
        all_requisition_amd_ids = []
        company_id = self.env.user.company_id.id
        all_requisition_amd = self.env['sale.requisition.amd'].search(
            [('id', 'in', self.requisition_amd_ids and self.requisition_amd_ids.ids or []),
             ('company_id', '=', company_id)])
        if all_requisition_amd:
            all_requisition_amd_ids = all_requisition_amd.ids
        action = self.env.ref('sale_ext.sale_requisition_amd_action')
        result = action.read()[0]
        res = self.env.ref('sale_ext.sale_requisition_amd_tree_view', False)
        res_form = self.env.ref('sale_ext.sale_requisition_amd_form_view', False)
        result['views'] = [(res and res.id or False, 'list'), (res_form and res_form.id or False, 'form')]
        result['domain'] = [('id', 'in', tuple(all_requisition_amd_ids))]
        result['target'] = 'main'
        result['view_type'] = 'tree'
        result['view_mode'] = 'tree,form'
        return result

    # code ends here

    @api.multi
    @api.depends('sale_ids')
    def _compute_orders_number(self):
        for requisition in self:
            requisition.order_count = len(requisition.sale_ids)
    # salman add action_cancel func
    @api.multi
    def action_cancel(self):
        # try to set all associated quotations to cancel state
        for requisition in self:
            requisition.sale_ids.action_cancel()
            for so in requisition.sale_ids:
                so.message_post(body=_('Cancelled by the agreement associated to this quotation.'))
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
        Generate all Sale order based on selected lines, should only be called on one agreement at a time
        """
        if any(sale_order.state in ['draft', 'sent', 'to approve'] for sale_order in
               self.mapped('sale_ids')):
            raise UserError(_('You have to cancel or validate every Quotation before closing the Sale requisition.'))
        self.write({'state': 'done'})

    # Piyush: code for amendment function data creation on 26-06-2020

    def _amendment_data(self, amd_name):
        line_data_list = []
        for item in self:
            for line in item.line_ids:
                line_data = (0, False, {
                    'product_id': line.product_id and line.product_id.id or False,
                    'hsn_id':line.product_id.hsn_id.hsn_code,
                    'product_uom_id': line.product_uom_id and line.product_uom_id.id or False,
                    'product_qty': line.product_qty or 0.0,
                    'order_value': line.order_value or 0.0,
                    'receipt_qty': line.receipt_qty or 0.0,
                    'price_unit': line.price_unit or 0.0,
                    'qty_ordered': line.qty_ordered or 0.0,
                    'schedule_date': line.schedule_date or fields.datetime.now(),
                    'requisition_amd_id': line.requisition_id and line.requisition_id.id or False,
                    'company_id': line.company_id and line.company_id.id or False,
                })
                line_data_list.append(line_data)

        amd_vals = {
            'name': amd_name,
            'requisition_amd_id': self.id or False,
            'partner_id': self.partner_id and self.partner_id.id or False,
            'date_end': self.date_end,
            'order_value': self.order_value or 0.0,
            'start_date': self.start_date,
            'type_id': self.type_id or False,
            'company_id': self.company_id and self.company_id.id or False,
            'state': self.state or '',
            'commitment_value': self.commitment_value or 0.0,
            'line_ids': line_data_list,
        }
        return amd_vals

    # code ends here

    # Piyush: code for write function of sale requisition on 08-05-2020

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

        res = super(SaleRequisition, self).write(vals)
        if 'state' not in vals and self.state == 'open':
            if 'commitment_value' in vals or 'line_ids' in vals or 'start_date' in vals or 'date_end' in vals or 'line_ids.product_qty' in vals:
                self.env['sale.requisition.amd'].create(amd_data)
                self.update({'state': 'in_progress'})

        if 'priority' in vals and vals['priority']:
            for ids in self:
                if ids.line_ids:
                    for lines in ids.line_ids:
                        lines.update({'priority': vals['priority']})

        return res


class SaleRequisitionLine(models.Model):
    _name = "sale.requisition.line"
    _description = "Sale Requisition Line"
    _rec_name = 'product_id'

    # salman : code to agreement qty
    @api.onchange('price_unit')
    def price_not_zero(self):
        if self.price_unit<=0:
            raise ValidationError('Unit Price can not be 0 or Negative')


    @api.onchange('product_id')
    def same_produuct_cheking(self):
        # print('@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@', self.product_id,[i.product_id for i in self.requisition_id.line_ids][:-2])
        if self.product_id in [i.product_id for i in self.requisition_id.line_ids][:-2]:
            raise ValidationError('This product is  already exist')


    #salman: end

    product_id = fields.Many2one('product.product', string='Product', domain=[('sale_ok', '=', True)],
                                 required=True)
    # Salman add Hsn field
    hsn_id=fields.Char(string='HSN code',readonly=True)
    # Salman end                             
    product_uom_id = fields.Many2one('product.uom', string='Product Unit of Measure')
    product_qty = fields.Float(string='Quantity', digits=dp.get_precision('Product Unit of Measure'),default=1)
    quantity_hide = fields.Boolean('Hide Field', help="field to make quantity readonly for arc")
    receipt_qty = fields.Float(compute="_compute_receipt_value", string='Delivered Qty')
    order_value = fields.Float(compute='_compute_order_value', string='Order Value')
    price_unit = fields.Float(string='Unit Price', digits=dp.get_precision('Product Price'),required=True,default=1)
    qty_ordered = fields.Float(compute='_compute_ordered_qty', string='Ordered Quantities')
    requisition_id = fields.Many2one('sale.requisition', string='Purchase Agreement', ondelete='cascade')
    company_id = fields.Many2one('res.company', related='requisition_id.company_id', string='Company', store=True,
                                 readonly=True, default=lambda self: self.env['res.company']._company_default_get(
            'sale.requisition.line'))
    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    schedule_date = fields.Date(string='Scheduled Date')
    move_dest_id = fields.Many2one('stock.move', 'Downstream Move')
    type_id = fields.Selection(related="requisition_id.type_id", string="Agreement Type")
    # Piyush: code for adding taxes in SA on 24-07-2020
    tax_ids = fields.Many2many('account.tax', 'requisition_tax_rel', 'requisition_id', 'tax_id', 'Taxes')
    # code ends here

    @api.multi
    @api.depends('requisition_id.sale_ids.state')
    def _compute_ordered_qty(self):
        for line in self:
            total = 0.0
            for so in line.requisition_id.sale_ids.filtered(
                    lambda sale_order: sale_order.state in ['sale', 'done']):
                for so_line in so.order_line.filtered(lambda order_line: order_line.product_id == line.product_id):
                    if so_line.product_uom != line.product_uom_id:
                        total += so_line.product_uom._compute_quantity(so_line.product_uom_qty, line.product_uom_id)
                    else:
                        total += so_line.product_uom_qty
            line.qty_ordered = total

    # Piyush: code for calculating receipt and order value on 08-05-2020
    @api.multi
    @api.depends('requisition_id.sale_ids.state')
    def _compute_order_value(self):
        for val in self:
            order_value = 0.0
            for so in val.requisition_id.sale_ids.filtered(
                    lambda sale_order: sale_order.state in ['sale', 'done']):
                for so_line in so.order_line.filtered(lambda order_line: order_line.product_id == val.product_id):
                    if so_line.product_uom != val.product_uom_id:
                        order_value += so_line.product_uom._compute_quantity(so_line.price_subtotal, val.product_uom_id)
                    else:
                        order_value += so_line.price_subtotal
            val.order_value = order_value

    # Piyush: here code is written to take receipt qty fields in PA lines from receipts but the qty_received in the
    # PO Lines is to be changed as it is not fetching correct value that is done qty from receipt on 09-05-2020

    @api.multi
    @api.depends('requisition_id.sale_ids.picking_ids.state')
    def _compute_receipt_value(self):
        for val in self:
            receipt_value = 0.0
            for so in val.requisition_id.sale_ids.filtered(
                    lambda sale_order: sale_order.state in ['sale', 'done']):
                for ord_line in so.order_line.filtered(lambda order_line: order_line.product_id == val.product_id):
                    if ord_line.product_uom != val.product_uom_id:
                        receipt_value += ord_line.product_uom._compute_quantity(ord_line.qty_delivered, val.product_uom_id)
                    else:
                        receipt_value += ord_line.qty_delivered
            val.receipt_qty = receipt_value

    # code ends here

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom_id = self.product_id.uom_id
            self.product_uom_qty = 1.0
        if not self.account_analytic_id:
            self.account_analytic_id = self.requisition_id.account_analytic_id
        if not self.schedule_date:
            self.schedule_date = self.requisition_id.schedule_date
        # salman add hsn_id    
        self.hsn_id=self.product_id.hsn_id.hsn_code 
        # salman end
        # Piyush: code for picking taxes in SA on 24-07-2020
        self.tax_ids = ''
        required_taxes = []
        product = self.product_id

        if self.env.user.company_id.vat and product and self.requisition_id.partner_id:

            # GST present , company registered
            check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.company_id.id)])
            check_delivery_address = self.requisition_id.partner_id

            # checking company state and customer state is same or not
            if check_cmpy_state.state_id == check_delivery_address.state_id:

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

            self.update({'tax_ids': [(6, 0, required_taxes)]})

        # code ends here

    @api.multi
    def _prepare_sale_order_line(self, name, product_uom_qty=product_qty, price_unit=price_unit, taxes_ids=False):
        self.ensure_one()
        requisition = self.requisition_id
        return {
            'name': name,
            'product_id': self.product_id.id,
            'product_uom': self.product_id.uom_po_id.id,
            'product_uom_qty': product_uom_qty,
            'price_unit': price_unit,
            'tax_id': [(6, 0, taxes_ids)],
            'date_order': requisition.schedule_date or fields.Date.today(),
            'account_analytic_id': self.account_analytic_id.id,
            # 'move_dest_ids': self.move_dest_id and [(4, self.move_dest_id.id)] or []
        }

    # code ends here

    # Piyush: code for creating amd on 26-06-2020


class SaleRequisitionAmd(models.Model):
    _name = "sale.requisition.amd"
    _description = "Sale Requisition Amendment"
    _inherit = ['mail.thread']
    _order = "id desc"

    name = fields.Char(string='Agreement Reference', required=True, copy=False)
    requisition_amd_id = fields.Many2one('sale.requisition', string='Requisition Amd Id', index=True)
    order_value = fields.Float(string='Order Value Till Date')
    origin = fields.Char(string='Source Document')
    order_count = fields.Integer(string='Number of Orders')
    partner_id = fields.Many2one('res.partner', string="Customer", required=True)
    type_id = fields.Selection([('open', 'Open Order'), ('arc', 'Arc')], string="Agreement Type", required=True)
    ordering_date = fields.Date(string="Ordering Date", default=fields.datetime.now())
    date_end = fields.Datetime(string='Agreement Deadline')
    schedule_date = fields.Date(string='Delivery Date', index=True,
                                help="The expected and scheduled delivery date where all the products are received")
    user_id = fields.Many2one('res.users', string='Responsible', default=lambda self: self.env.user)
    description = fields.Text()
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env['res.company']._company_default_get(
                                     'sale.requisition'))
    sale_ids = fields.One2many('sale.order', 'requisition_id', string='Sale Orders',
                               states={'done': [('readonly', True)]})
    line_ids = fields.One2many('sale.requisition.line.amd', 'requisition_id', string='Products to Sale',
                               states={'done': [('readonly', True)]}, copy=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')
    state = fields.Selection([('draft', 'Draft'), ('in_progress', 'Confirmed'),
                              ('open', 'Bid Selection'), ('done', 'Done'),
                              ('cancel', 'Cancelled')],
                             'Status', track_visibility='onchange', required=True,
                             copy=False, default='draft')
    account_analytic_id = fields.Many2one('account.analytic.account', 'Analytic Account')
    picking_type_id = fields.Many2one('stock.picking.type', 'Operation Type')
    start_date = fields.Datetime(string='Start Date')
    commitment_value = fields.Float(string='Commitment Value')


class SaleRequisitionLineAmd(models.Model):
    _name = "sale.requisition.line.amd"
    _description = "Sale Requisition Line Amd"
    _rec_name = 'product_id'

        # Salman add Hsn field
    hsn_id=fields.Char(string='HSN code',readonly=True)
    # Salman end
    product_id = fields.Many2one('product.product', string='Product', domain=[('sale_ok', '=', True)],
                                 required=True)
    product_uom_id = fields.Many2one('product.uom', string='Product Unit of Measure')
    product_qty = fields.Float(string='Quantity', digits=dp.get_precision('Product Unit of Measure'))
    quantity_hide = fields.Boolean('Hide Field', help="field to make quantity readonly for arc")
    receipt_qty = fields.Float(tring='Delivered Qty')
    order_value = fields.Float(string='Order Value')
    price_unit = fields.Float(string='Unit Price', digits=dp.get_precision('Product Price'))
    qty_ordered = fields.Float(string='Ordered Quantities')
    requisition_id = fields.Many2one('sale.requisition.amd', string='Purchase Agreement', ondelete='cascade')
    company_id = fields.Many2one('res.company', related='requisition_id.company_id', string='Company', store=True,
                                 readonly=True, default=lambda self: self.env['res.company']._company_default_get(
            'sale.requisition.line'))
    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    schedule_date = fields.Date(string='Scheduled Date')
    move_dest_id = fields.Many2one('stock.move', 'Downstream Move')
    type_id = fields.Selection(related="requisition_id.type_id", string="Agreement Type")

    # code ends here

class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.onchange('requisition_id')
    def _onchange_requisition_id(self):
        # self.order_line = ''
        # if self.agreement_start_date <=

        if not self.requisition_id:
            # Piyush: code for taking default date when no id is there on 31-03-2020
            self.start_date = fields.Datetime.now()
            self.end_date = fields.Datetime.now()
            # code ends here



        requisition = self.requisition_id
        # print('$$$$$$$$$',datetime(str(requisition.start_date)))

        # salman: apply only if condition for comparing agreement  start_date  and today date
        if requisition.start_date != False:
            if datetime.strptime(requisition.start_date, "%Y-%m-%d %H:%M:%S") <= datetime.today():
                if self.partner_id:
                    partner = self.partner_id
                else:
                    partner = requisition.partner_id
                payment_term = partner.property_supplier_payment_term_id
                currency = partner.property_purchase_currency_id or requisition.company_id.currency_id

                FiscalPosition = self.env['account.fiscal.position']
                fpos = FiscalPosition.get_fiscal_position(partner.id)
                fpos = FiscalPosition.browse(fpos)

                self.partner_id = partner.id
                self.partner_shipping_id = partner.id
                self.fiscal_position_id = fpos.id
                self.payment_term_id = payment_term.id
                self.company_id = requisition.company_id.id
                self.currency_id = currency.id
                self.origin = ''
                if not self.origin or requisition.name not in self.origin.split(', '):
                    if self.origin:
                        if requisition.name:
                            self.origin = self.origin + ', ' + requisition.name
                    else:
                        self.origin = requisition.name
                self.notes = requisition.description

                # Piyush: code for picking correct date from purchase agreement 12-08-2020
                self.agreement_start_date = requisition.start_date or ''
                self.agreement_end_date = requisition.date_end or ''
                # Code ends here

                self.picking_type_id = requisition.picking_type_id.id

                # Create PO lines if necessary
                #salman: code change to product_uom_qty,add hsn_id and add if condition for compute qty in open_order case 
                line_data_list = [(5,0,0)]
                for line in requisition.line_ids:
                    if self.so_type=='arc':
                        product_uom_qty=1
                    else:
                        product_uom_qty=line.product_qty-line.qty_ordered

                    line_data = (0, False, {
                        'name': line.product_id.name or '',
                        'product_id': line.product_id and line.product_id.id or False,
                        'hsn_id':line.hsn_id,
                        'product_uom_qty': product_uom_qty or 0.0,
                        'product_uom': line.product_uom_id and line.product_uom_id.id or False,
                        'price_unit': line.price_unit or 0.0,
                        'tax_id': line.tax_ids or False,
                    })
                    line_data_list.append(line_data)

                self.order_line = line_data_list
            else:
                raise ValidationError(_('This Agreement will start from %s') % requisition.start_date)
