# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from itertools import groupby
from odoo import api, fields, models, _


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.model
    def _get_default_team(self):
        return self.env['crm.team']._get_default_team_id()

    def _default_comment(self):
        invoice_type = self.env.context.get('type', 'out_invoice')
        if invoice_type == 'out_invoice' and self.env['ir.config_parameter'].sudo().get_param('sale.use_sale_note'):
            return self.env.user.company_id.sale_note

    team_id = fields.Many2one('crm.team', string='Sales Channel', default=_get_default_team, oldname='section_id')
    comment = fields.Text(default=_default_comment)

    partner_shipping_id = fields.Many2one('res.partner',
        string='Delivery Address',
        readonly=True,
        states={'draft': [('readonly', False)]},
        help="Delivery address for current invoice.")

    #Himanshu SO 02-12-2020 function added to add the address related to the customer
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

        self.Address = val
    #end Himanshu

    # Gaurav 14/3/20 added domain and value for shipping delivery address
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        res = super(AccountInvoice, self)._onchange_partner_id()

        print("working inherit partner")

        # Gaurav 14/3/20 added customer delivery address and invoice address domain
        check_custmr_state_delivery = self.env['res.partner'].search(
            [('company_id', '=', self.company_id.id),
             ('type', '=', 'delivery'), ('parent_id', '=', self.partner_id.id)])

        check_custmr_state_invoice = self.env['res.partner'].search(
            [('company_id', '=', self.company_id.id),
             ('type', '=', 'invoice'), ('parent_id', '=', self.partner_id.id)])
        # Gaurav added domain in result

        # Gaurav 13/3/20 added domain result
        # res = {'domain': {'partner_shipping_id': [('id', 'in', check_custmr_state_delivery.ids)]}}
        res.update({'domain': {'partner_shipping_id': [('id', 'in', check_custmr_state_delivery.ids)]}})

        return res
        # Gaurav end

    @api.onchange('product_id')
    def _onchange_product_id(self):
        res = super(AccountInvoice, self)._onchange_product_id()

        print("working inherit product")
        res.update({'partner_shipping_id': [self.partner_shipping_id]})

        return res

    # Gaurav end

    @api.onchange('partner_shipping_id')
    def _onchange_partner_shipping_id(self):
        """
        Trigger the change of fiscal position when the shipping address is modified.
        """
        fiscal_position = self.env['account.fiscal.position'].get_fiscal_position(self.partner_id.id, self.partner_shipping_id.id)
        if fiscal_position:
            self.fiscal_position_id = fiscal_position

    @api.onchange('partner_id', 'company_id')
    def _onchange_delivery_address(self):
        addr = self.partner_id.address_get(['delivery'])
        self.partner_shipping_id = addr and addr.get('delivery')
        if self.env.context.get('type', 'out_invoice') == 'out_invoice':
            company = self.company_id or self.env.user.company_id
            self.comment = company.with_context(lang=self.partner_id.lang).sale_note or (self._origin.company_id == company and self.comment)

    @api.multi
    def action_invoice_paid(self):
        res = super(AccountInvoice, self).action_invoice_paid()
        todo = set()
        for invoice in self:
            for line in invoice.invoice_line_ids:
                for sale_line in line.sale_line_ids:
                    todo.add((sale_line.order_id, invoice.number))
        for (order, name) in todo:
            order.message_post(body=_("Invoice %s paid") % (name))
        return res

    @api.model
    def _refund_cleanup_lines(self, lines):
        result = super(AccountInvoice, self)._refund_cleanup_lines(lines)
        if self.env.context.get('mode') == 'modify':
            for i, line in enumerate(lines):
                for name, field in line._fields.items():
                    if name == 'sale_line_ids':
                        result[i][2][name] = [(6, 0, line[name].ids)]
                        line[name] = False
        return result

    @api.multi
    def order_lines_layouted(self):
        """
        Returns this sales order lines ordered by sale_layout_category sequence. Used to render the report.
        """
        self.ensure_one()
        report_pages = [[]]
        for category, lines in groupby(self.invoice_line_ids, lambda l: l.layout_category_id):
            # If last added category induced a pagebreak, this one will be on a new page
            if report_pages[-1] and report_pages[-1][-1]['pagebreak']:
                report_pages.append([])
            # Append category to current report page
            report_pages[-1].append({
                'name': category and category.name or 'Uncategorized',
                'subtotal': category and category.subtotal,
                'pagebreak': category and category.pagebreak,
                'lines': list(lines)
            })

        return report_pages

    @api.multi
    def get_delivery_partner_id(self):
        self.ensure_one()
        return self.partner_shipping_id.id or super(AccountInvoice, self).get_delivery_partner_id()

    def _get_refund_common_fields(self):
        return super(AccountInvoice, self)._get_refund_common_fields() + ['team_id', 'partner_shipping_id']


class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'
    _order = 'invoice_id, layout_category_id, sequence, id'

    sale_line_ids = fields.Many2many(
        'sale.order.line',
        'sale_order_line_invoice_rel',
        'invoice_line_id', 'order_line_id',
        string='Sales Order Lines', readonly=True, copy=False)
    layout_category_id = fields.Many2one('sale.layout_category', string='Section')
    layout_category_sequence = fields.Integer(string='Layout Sequence')

    # Piyush: code for adding sale line ids on invoice from sale order 13-08-2020
    # P: made changes in the function by adding checks on 11-09-2019
    @api.model
    def create(self, vals):
        if 'invoice_id' in vals:
            inv_id = vals.get('invoice_id')  # picking up the invoice id
            acc_id = self.env['account.invoice'].search([('id', '=', inv_id)])  # picking invoice on the basis of id
            if acc_id and acc_id.origin:  # if invoice and origin both exists
                origin = acc_id.origin
                req_sale_id = self.env['sale.order'].search([('name', '=', origin)])  # check item is from SO or PO
                if req_sale_id:  # if from SO
                    req_pro = vals['product_id']
                    req_list = []
                    for ids in req_sale_id.order_line:
                        if ids.product_id.id == req_pro:
                            req_list.append(ids.id)
                    vals.update({'sale_line_ids': [(6, 0, req_list)]})
        result = super(AccountInvoiceLine, self).create(vals)
        return result
        # if "origin" in vals:
        #     origin = vals['origin']
        #     req_sale_id = self.env['sale.order'].search([('name', '=', origin)])
        #     req_pro = vals['product_id']
        #     req_list = []
        #     for ids in req_sale_id.order_line:
        #         if ids.product_id.id == req_pro:
        #             req_list.append(ids.id)
        #     vals.update({'sale_line_ids': [(6, 0, req_list)]})
        # result = super(AccountInvoiceLine, self).create(vals)
        # return result


    # Gaurav 14/3/20 added  partner_shipping_id for getting onchange delivery address
    # partner_shipping_id = fields.Many2one('res.partner', string='Delivery address',
    #                                       related='invoice_id.partner_shipping_id', store=True, readonly=True,
    #                                       related_sudo=False)
    #
    # # TODO: remove layout_category_sequence in master or make it work properly
    #
    #
    # # Gaurav addde14/3/20 set tax function
    # def _set_taxes(self):
    #     # res = super(AccountInvoiceLine, self)._set_taxes()
    #     """ Used in on_change to set taxes and price."""
    #     if self.invoice_id.type in ('out_invoice', 'out_refund'):
    #         taxes = self.product_id.taxes_id or self.account_id.tax_ids
    #     else:
    #         taxes = self.product_id.supplier_taxes_id or self.account_id.tax_ids
    #
    #     # Keep only taxes of the company
    #     company_id = self.company_id or self.env.user.company_id
    #     taxes = taxes.filtered(lambda r: r.company_id == company_id)
    #
    #     taxes_ids_list = taxes.ids
    #     print("partner_shipping_id",self.partner_shipping_id)
    #
    #
    #     # Gaurav 12/3/20 added code for default tax state wise
    #     check_cmpy_state = self.env['res.company'].search([('partner_id', '=', company_id.id)])
    #     check_custmr_state = self.env['res.partner'].search([('id', '=', self.partner_id.id), ('company_id', '=', company_id.id)])
    #
    #     if check_cmpy_state.state_id == self.partner_shipping_id.state_id:
    #         self.env.cr.execute(""" select id from account_tax where active=True and type_tax_use='sale' AND tax_group_id!=1 and company_id='%s'""" % (self.env.user.company_id.id,))
    #         csgst_taxes = self.env.cr.dictfetchall()
    #         final = [taxes_ids_list.remove(val.get('id')) for val in csgst_taxes if val.get('id') in taxes_ids_list if csgst_taxes]
    #         print("sale account finalvvvvvvvvvvvvvvvv",final)
    #         self.invoice_line_tax_ids = taxes_ids_list
    #
    #     elif check_cmpy_state.state_id != self.partner_shipping_id.state_id:
    #         self.env.cr.execute(""" select id from account_tax where active=True and type_tax_use='sale' AND tax_group_id!=4 and company_id='%s'""" % (self.env.user.company_id.id,))
    #         igst_taxes = self.env.cr.dictfetchall()
    #         final = [taxes_ids_list.remove(val.get('id')) for val in igst_taxes if val.get('id') in taxes_ids_list if igst_taxes]
    #         print("sale finalvvvvvvvvvvvvvvvv",final)
    #
    #         self.invoice_line_tax_ids = taxes_ids_list
    #
    #     # Gaurav return domain
    #     res= {'domain': {'invoice_line_tax_ids': [final]}}
    #     print("sale saleeeeeeeeeeeeeeeeee",res)
    #     return res
    # # Gaurav end
    #
    #
    # # Gaurav added 14/3/20 onchange product id for validation for GST check
    # @api.onchange('product_id')
    # def _onchange_product_id(self):
    #     res = super(AccountInvoiceLine, self)._onchange_product_id()
    #
    #     partner_delivery= self.partner_shipping_id
    #     print("working inherit product",partner_delivery.state_id)
    #
    #     # Gaurav 12/3/20 added validation for GST check (if company is unregistered then don't add taxes if registered then add taxes state wise)
    #     if self.env.user.company_id.vat:
    #         # GST present , company registered
    #         # Gaurav 12/3/20 added code for default tax state wise
    #         check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
    #         check_custmr_state = self.env['res.partner'].search(
    #             [('id', '=', self.partner_id.id), ('company_id', '=', self.env.user.company_id.id)])
    #         # checking company state and customer state is same or not
    #         if check_cmpy_state.state_id == partner_delivery.state_id:
    #             # if same states show taxes like CGST SGST GST
    #             self.env.cr.execute(
    #                 """select id from account_tax where active=True and type_tax_use='sale' and tax_group_id!=4 and company_id='%s'""" % (
    #                 self.env.user.company_id.id,))
    #             csgst_taxes = self.env.cr.dictfetchall()
    #             print("sale account  csgst_taxessssss", csgst_taxes)
    #             self._set_taxes()
    #             cs_tax_list = []
    #             if csgst_taxes:
    #                 for val in csgst_taxes:
    #                     tax_detail_idcs = val.get('id')
    #                     cs_tax_list.append(tax_detail_idcs)
    #                     print("cs_tax_listttt", cs_tax_list)
    #                     # self.update({'tax_id': [(6, 0, cs_tax_list)]})
    #                     res = {'domain': {'invoice_line_tax_ids': [('id', 'in', cs_tax_list)]}}
    #         elif check_cmpy_state.state_id != partner_delivery.state_id:
    #             # if different states show taxes like IGST
    #             self.env.cr.execute(
    #                 """ select id from account_tax where active=True and type_tax_use='sale' and tax_group_id!=1 and company_id='%s'""" % (
    #                 self.env.user.company_id.id,))
    #             igst_taxes = self.env.cr.dictfetchall()
    #             self._set_taxes()
    #             i_tax_list = []
    #             if igst_taxes:
    #                 for val in igst_taxes:
    #                     tax_detail_idi = val.get('id')
    #                     i_tax_list.append(tax_detail_idi)
    #                     print("sale account i_tax_listtttt", i_tax_list)
    #                     res = {'domain': {'invoice_line_tax_ids': [('id', 'in', i_tax_list)]}}
    #
    #                     # Gaurav end
    #     print("sale account  res sale",res)
    #     return res
    #
    # Gaurav end