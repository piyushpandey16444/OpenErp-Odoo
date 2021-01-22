# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models,SUPERUSER_ID
from odoo.addons.base.res.res_partner import WARNING_MESSAGE, WARNING_HELP
from odoo.exceptions import AccessDenied, AccessError, UserError, ValidationError
from odoo.http import request
from odoo import http
import werkzeug
import werkzeug.utils
import werkzeug.wrappers
import werkzeug.wsgi
from collections import OrderedDict
from werkzeug.urls import url_decode, iri_to_uri
from odoo.addons.web.controllers.main import Session
import re


class res_partner(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'



#Himanshu COA 22-09-2020  Added a new create function to make a chart of account on the creation of vendors and customers
    @api.model
    def create(self, vals):
        new = super(res_partner, self).create(vals)
        #Query to get the last code added corresponding to a vendor/customer
        if vals.get('customer') == True and vals.get('parent_id') == False:
            self._cr.execute(
                """select max(CAST(code AS INT)) from account_account where code like '100%' """)
            code = str(self._cr.fetchall()[0][0])
            print("code_customer..................1",code)
            if code != "None":
                #First check if there is no code present in the database then add a new one with prefix and if a code is present then increment 1  to it add to the database.
                x = str(int(code[3:]) + 1)
                if len(x) >= 1:
                    code = str("100" + x.zfill(3))

                data = {'name': vals.get('name'), 'code': code, 'Type': 'Customer', 'user_type_id': '1',
                        'reconcile': 'True', 'partner_id': new.id,'group_id':1}
                self.env['account.account'].create(data)

            else:
                data = {'name': vals.get('name'), 'code': 100001, 'Type': 'Customer', 'user_type_id': '1',
                        'reconcile': 'True', 'partner_id': new.id, 'group_id':1}
                self.env['account.account'].create(data)

        elif vals.get('supplier') == True and vals.get('parent_id') == False:
            self._cr.execute(
                "select max(CAST(code AS INT)) from account_account where code like '200%' ")
            code = str(self._cr.fetchall()[0][0])
            if code != "None":
                x = str(int(code[3:]) + 1)
                print("x.......... ",x)
                if len(x) >= 1:
                    code = str("200" + x.zfill(3))

                data = {'name': vals.get('name'), 'code': code, 'Type': 'Vendor', 'user_type_id': '2',
                        'reconcile': 'True', 'partner_id': new.id,'group_id':2}
                self.env['account.account'].create(data)

            else:
                data = {'name': vals.get('name'), 'code': 200001, 'Type': 'Vendor', 'user_type_id': '2',
                        'reconcile': 'True', 'partner_id': new.id,'group_id':2}
                self.env['account.account'].create(data)

        return new
    # End Himanshu

    # Himanshu COA 15-10-2020 Added the write funtion to change the chart_of_account whenever the customer and vendor is being edited.
    @api.multi
    def write(self, vals):
        var = self.name
        new = super(res_partner, self).write(vals)
        if vals.get('name') != None:
            data = {'name': vals.get('name')}
            self.env['account.account'].search([('name', '=', var)]).write(data)
        return new
    # End Himanshu

    @api.multi
    def _purchase_invoice_count(self):
        # retrieve all children partners and prefetch 'parent_id' on them
        all_partners = self.search([('id', 'child_of', self.ids)])
        all_partners.read(['parent_id'])

        purchase_order_groups = self.env['purchase.order'].read_group(
            domain=[('partner_id', 'in', all_partners.ids)],
            fields=['partner_id'], groupby=['partner_id']
        )
        for group in purchase_order_groups:
            partner = self.browse(group['partner_id'][0])
            while partner:
                if partner in self:
                    partner.purchase_order_count += group['partner_id_count']
                partner = partner.parent_id

        supplier_invoice_groups = self.env['account.invoice'].read_group(
            domain=[('partner_id', 'in', all_partners.ids),
                    ('type', 'in', ['in_invoice', 'in_refund'])],
            fields=['partner_id'], groupby=['partner_id']
        )
        for group in supplier_invoice_groups:
            partner = self.browse(group['partner_id'][0])
            while partner:
                if partner in self:
                    partner.supplier_invoice_count += group['partner_id_count']
                partner = partner.parent_id

    # Gaurav 17/3/20 GST validation
    @api.constrains('vat','state_id')
    def _validate_gstin(self):
        for val in self:
            if self.vat:
                if not re.search("\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}", self.vat):
                    raise ValidationError('Invalid Entry of GSTIN.\n'
                                            'It should contain first 2 digits as state code, next 10 digits will be PAN number of taxpayer !!\n'
                                            'e.g. 07AAFFD3743A1ZY')
            if val.vat:
                gst = val.vat
                # Aman 30/12/2020 Added conditions since vat was giving error
                if val.parent_id.state_id:
                    if val.parent_id.state_id.l10n_in_tin != gst[:2] or len(gst) != 15:
                        raise ValidationError('GST number is not valid!!')
                elif val.state_id:
                    if val.state_id.l10n_in_tin != gst[:2] or len(gst) != 15:
                        raise ValidationError('GST number is not valid!!')
                else:
                    raise ValidationError('Please Select valid State')
                # Aman end
                # Gaurav end

    # Piyush: commented code for making migration of customer when created in hoitymoppet # ecom integration installation check
    # Gaurav 3march20 for unique name of product
    @api.multi
    @api.constrains('name')
    def _check_unique_name(self):
        """
        Check Name should be unique
        """
        ecom_installed = self.env['ir.module.module'].search([('name','=', 'ecom_integration'), ('state', '=', 'installed')])
        if not ecom_installed:
            for line in self:
                all_temp_list = []
                all_temp = line.env['res.partner'].search(
                    [('company_id', '=', line.env.user.company_id.id)])
                if all_temp:
                    all_temp_list = [temp_val.name.lower().lstrip().rstrip() for temp_val in all_temp]
                if line.name:
                    name = line.name.lower().lstrip().rstrip()
                    print("name................", name, all_temp_list.count(name))
                    if name in all_temp_list:
                        if all_temp_list.count(name) > 1:
                            raise ValidationError('Vendor already exist !')

    # Gaurav end

    @api.model
    def _commercial_fields(self):
        return super(res_partner, self)._commercial_fields()

    property_purchase_currency_id = fields.Many2one(
        'res.currency', string="Supplier Currency", company_dependent=True,
        help="This currency will be used, instead of the default one, for purchases from the current partner")
    purchase_order_count = fields.Integer(compute='_purchase_invoice_count', string='# of Purchase Order')
    supplier_invoice_count = fields.Integer(compute='_purchase_invoice_count', string='# Vendor Bills')
    purchase_warn = fields.Selection(WARNING_MESSAGE, 'Purchase Order', help=WARNING_HELP, required=True, default="no-message")
    purchase_warn_msg = fields.Text('Message for Purchase Order')








class Users(models.Model):
    _inherit = "res.users"

    user_login_details = fields.Boolean(string='User Login Details')

    def log_out_session(self):
        print("Schedular is running........................")
        obj = Session()
        obj.logout()
        # self.logout()
        # request.session.logout(keep_db=True)
        # if request.session.uid:
        #     # ravi start
        #     request.env.cr.execute(""" update res_users set user_login_details = False where id = %s """ % (request.session.uid))
        #
        # request.session.logout(keep_db=True)

    # @http.route('/web/session/logout', type='http', auth="none")
    # def logout(self, redirect='/web'):
    #     # if request.session.uid:
    #     # ravi start
    #     #     request.env.cr.execute(
    #     #         """ update res_users set user_login_details = False where id = %s """ % (request.session.uid))
    #
    #     request.session.logout(keep_db=True)
        # return werkzeug.utils.redirect(redirect, 303)



