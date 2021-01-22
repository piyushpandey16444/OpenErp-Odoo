from itertools import groupby
from odoo import api, fields, models, _

class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    # Gaurav 14/3/20 added  partner_shipping_id for getting onchange delivery address
    partner_shipping_id = fields.Many2one('res.partner', string='Delivery address',
                                          related='invoice_id.partner_shipping_id', store=True, readonly=True,
                                          related_sudo=False)

    # TODO: remove layout_category_sequence in master or make it work properly
    print ("SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSS")


    # Gaurav addde14/3/20 set tax function
    def _set_taxes(self):
        # res = super(AccountInvoiceLine, self)._set_taxes()
        """ Used in on_change to set taxes and price."""
        if self.invoice_id.type in ('out_invoice', 'out_refund'):
            taxes = self.product_id.taxes_id or self.account_id.tax_ids
            account_type = 'sale'
        else:
            taxes = self.product_id.supplier_taxes_id or self.account_id.tax_ids
            account_type = 'purchase'

        # Keep only taxes of the company
        company_id = self.company_id or self.env.user.company_id
        taxes = taxes.filtered(lambda r: r.company_id == company_id)

        taxes_ids_list = taxes.ids
        print("latest partner_shipping_id",self.partner_shipping_id)


        # Gaurav 12/3/20 added code for default tax state wise
        check_cmpy_state = self.env['res.company'].search([('partner_id', '=', company_id.id)])
        check_custmr_state = self.env['res.partner'].search([('id', '=', self.partner_id.id), ('company_id', '=', company_id.id)])

        if check_cmpy_state.state_id == self.partner_shipping_id.state_id:
            print("same account_type",account_type)
            self.env.cr.execute(""" select id from account_tax where active=True and type_tax_use='%s' AND tax_group_id!=1 and company_id='%s'""" % (account_type,self.env.user.company_id.id,))
            csgst_taxes = self.env.cr.dictfetchall()
            final = [taxes_ids_list.remove(val.get('id')) for val in csgst_taxes if val.get('id') in taxes_ids_list if csgst_taxes]
            print("latest new finalvvvvvvvvvvvvvvvv",final)
            self.invoice_line_tax_ids = taxes_ids_list

        elif check_cmpy_state.state_id != self.partner_shipping_id.state_id:
            print("diff account_type", account_type)
            self.env.cr.execute(""" select id from account_tax where active=True and type_tax_use='%s' AND tax_group_id!=4 and company_id='%s'""" % (self.env.user.company_id.id,))
            igst_taxes = self.env.cr.dictfetchall()
            final = [taxes_ids_list.remove(val.get('id')) for val in igst_taxes if val.get('id') in taxes_ids_list if igst_taxes]
            print(" latest new finalvvvvvvvvvvvvvvvv",final)

            self.invoice_line_tax_ids = taxes_ids_list

        # Gaurav return domain
        res= {'domain': {'invoice_line_tax_ids': [final]}}
        print(" latest new saleeeeeeeeeeeeeeeeee",res)
        return res
    # Gaurav end


    # Gaurav added 14/3/20 onchange product id for validation for GST check
    @api.onchange('product_id')
    def _onchange_product_id(self):
        res = {}
        print ("HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHH")
        super(AccountInvoiceLine, self)._onchange_product_id()

        partner_delivery= self.partner_shipping_id
        print(" new working inAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAherit product",partner_delivery.state_id)

        # Gaurav 12/3/20 added validation for GST check (if company is unregistered then don't add taxes if registered then add taxes state wise)
        if self.env.user.company_id.vat:
            # GST present , company registered
            # Gaurav 12/3/20 added code for default tax state wise
            check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
            check_custmr_state = self.env['res.partner'].search(
                [('id', '=', self.partner_id.id), ('company_id', '=', self.env.user.company_id.id)])
            # checking company state and customer state is same or not
            if check_cmpy_state.state_id == partner_delivery.state_id:
                # if same states show taxes like CGST SGST GST
                self.env.cr.execute(
                    """select id from account_tax where active=True and type_tax_use='sale' and tax_group_id!=4 and company_id='%s'""" % (
                    self.env.user.company_id.id,))
                csgst_taxes = self.env.cr.dictfetchall()
                print("latest new csgst_taxessssss", csgst_taxes)
                self._set_taxes()
                cs_tax_list = []
                if csgst_taxes:
                    for val in csgst_taxes:
                        tax_detail_idcs = val.get('id')
                        cs_tax_list.append(tax_detail_idcs)
                        print("cs_tax_listttt", cs_tax_list)
                        # self.update({'tax_id': [(6, 0, cs_tax_list)]})
                        res = {'domain': {'invoice_line_tax_ids': [('id', 'in', cs_tax_list)]}}
            elif check_cmpy_state.state_id != partner_delivery.state_id:
                # if different states show taxes like IGST
                self.env.cr.execute(
                    """ select id from account_tax where active=True and type_tax_use='sale' and tax_group_id!=1 and company_id='%s'""" % (
                    self.env.user.company_id.id,))
                igst_taxes = self.env.cr.dictfetchall()
                self._set_taxes()
                i_tax_list = []
                if igst_taxes:
                    for val in igst_taxes:
                        tax_detail_idi = val.get('id')
                        i_tax_list.append(tax_detail_idi)
                        print("i_tax_listtttt", i_tax_list)
                        res = {'domain': {'invoice_line_tax_ids': [('id', 'in', i_tax_list)]}}

                        # Gaurav end
        print("res sale",res)
        return res

