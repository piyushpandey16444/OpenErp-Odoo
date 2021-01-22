# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from collections import Counter
from datetime import timedelta
import time
from dateutil.relativedelta import relativedelta
from odoo.addons.account.models import genric
from num2words import num2words

from odoo import api, fields, models, SUPERUSER_ID, _, tools
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_is_zero, float_compare
from odoo.exceptions import UserError, AccessError, ValidationError, RedirectWarning, except_orm
from odoo.tools.misc import formatLang
from odoo.addons.base.res.res_partner import WARNING_MESSAGE, WARNING_HELP
from odoo.addons import decimal_precision as dp


class RequestForQuotation(models.Model):
    _name = "request.for.quotation"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "RFQ"
    _order = 'id desc'

    # Yash START 26/12/2020 : code for print purchase invoice
    def _get_tax_items(self):
        """
        Get tax items and aggregated amount
        :return:
        """
        taxes_dict = {}
        for line in self.rfq_line_ids:
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
        # if self.delivery_date:
        #     delivery_date = datetime.strptime(self.delivery_date, "%Y-%m-%d").date()
        #     order_date = datetime.strptime(self.date_order, "%Y-%m-%d %H:%M:%S").date()
        #     delta = delivery_date - order_date
        #     delivery_days = delta.days or 0
        return delivery_days

    # Yash END 26/12/2020 : code for print purchase invoice

    # Aman 4/08/2020 Vender must be selected before selecting rfq number
    @api.onchange('reference_rfq')
    def onchangeRFQ(self):
        if not self.partner_id and self.reference_rfq:
            raise UserError(_('You must select Vendor first!!'))
    # Aman end


    @api.onchange('reference_rfq')
    def _onchange_reference_rfq(self):
        self.rfq_line_ids = ''
        for vals in self:
            if vals.reference_rfq:
                reference_rfq = vals.reference_rfq
                print("reference_rfq", reference_rfq)
                if vals.partner_id:
                    partner = vals.partner_id
                else:
                    partner = reference_rfq.partner_id
                    print("partner_id", partner)
                payment_term = partner.property_supplier_payment_term_id
                currency = partner.property_purchase_currency_id or reference_rfq.company_id.currency_id
                FiscalPosition = self.env['account.fiscal.position']
                fpos = FiscalPosition.get_fiscal_position(partner.id)
                fpos = FiscalPosition.browse(fpos)

                vals.currency_id = currency.id

                #             creating rfq item lines

                rfq_lines = []
                if reference_rfq.rfq_line_ids:
                    print("already haiiii")
                    for line in reference_rfq.rfq_line_ids:
                        print("Dekh loooooo", line)

                            # Compute name

                        product_lang = line.product_id.with_context({
                            'lang': partner.lang,
                            'partner_id': partner.id,
                        })
                        name = product_lang.display_name
                        if product_lang.description_purchase:
                            name += '\n' + product_lang.description_purchase

                        # Compute taxes
                        # Jatin for vendor_tax_line  taxes 30-06-20
                        if self.partner_id.vat:
                            filter_tax = []
                            for val in line:
                                check = val.product_id.vendor_tax_lines
                                print("check", check)
                                for rec in check:
                                    tax_check = rec.tax_id.id
                                    print(tax_check)
                                    filter_tax.append(tax_check)
                                print('filter_tax', filter_tax)

                            print_tax = self.env['account.tax'].search([('id', 'in', filter_tax)])
                            print("print_tax", print_tax)
                            # Jatin commented on 02-07-2020
                            # if fpos:
                            #     print("in if")
                            #     taxes_ids = fpos.map_tax(print_tax.filtered(
                            #         lambda tax: tax.company_id == reference_rfq.company_id)).ids
                            # else:
                            #     print("in else")
                            #     taxes_ids = print_tax.filtered(
                            #         lambda tax: tax.company_id == reference_rfq.company_id).ids
                            # print('taxes_ids',taxes_ids)
                            taxes_id = fpos.map_tax(
                                print_tax.filtered(lambda tax: tax.company_id == reference_rfq.company_id))
                            print('taxes_id', taxes_id)

                            # taxes_id = fpos.map_tax(
                            #     self.product_id.supplier_taxes_id.filtered(lambda r: r.company_id.id == company_id))

                            print("self.taxes_iddddddd", taxes_id, self.partner_id.id)
                            taxes_ids_list = taxes_id.ids
                            check_cmpy_state = self.env['res.company'].search(
                                [('partner_id', '=', self.env.user.company_id.id)])
                            check_custmr_state = self.env['res.partner'].search(
                                [('id', '=', self.partner_id.id), ('company_id', '=', self.env.user.company_id.id)])

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
                                # self.taxes_id = tax_id_list

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
                        # end Jatin
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

                        # Create rfq line
                        rfq_line_values = line._prepare_rfq_line_(
                            name=name, product_qty=product_qty, price_unit=price_unit,
                            taxes_ids=tax_id_list)
                        rfq_lines.append((0, False, rfq_line_values))
                    vals.rfq_line_ids = rfq_lines
    # code ends here


    # Piyush: code for preventing PO creation without order lines 15-04-2020
    @api.multi
    @api.constrains('rfq_line_ids')
    def _check_rfq_line_ids(self):
        for val in self:
            if not val.rfq_line_ids:
                raise ValidationError(_('Cannot create Purchase Order without Product'))

    # code ends here

    @api.depends('rfq_line_ids.price_total')
    def _amount_all(self):
        for order in self:
            amount_untaxed = amount_tax = 0.0
            for line in order.rfq_line_ids:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            order.update({
                'amount_untaxed': order.currency_id.round(amount_untaxed),
                'amount_tax': order.currency_id.round(amount_tax),
                'amount_total': amount_untaxed + amount_tax,
            })

    # Aman 26/12/2020 Added validations to check if Item without HSN code is last item
    # Aman 08/01/2021 commented the below function
    # @api.onchange('rfq_line_ids')
    # def onchange_lines(self):
    #     genric.check_hsn_disable(self, self.rfq_line_ids)
    # Aman end

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('request.for.quotation') or 'New'
        res = super(RequestForQuotation, self).create(vals)

        if res.rfq_line_ids:
            for ref_rfq in res.rfq_line_ids:
                if not ref_rfq.ref_rfq_line_id:
                    ref_rfq.ref_rfq_line_id = ref_rfq

        if res.rfq_line_ids:
            for values in res.rfq_line_ids:
                if values.product_id:
                    product_tmpl_id = values.product_id.product_tmpl_id.id
                    self.env['product.template'].search(
                        [('company_id', '=', res.company_id.id), ('id', '=', product_tmpl_id)]).write(
                        {'product_transaction': True})
        # Piyush: code for preventing creation of PO without PO Lines 08-4-2020
        if not res.rfq_line_ids:
            raise UserError('Cannot create Purchase Order without Product')
        # code ends here
        if not res.reference_rfq:
            res.reference_rfq = res.id

        return res

    @api.multi
    def write(self, vals):
        result = super(RequestForQuotation, self).write(vals)
        if 'rfq_line_ids' in vals and vals.get('rfq_line_ids'):
            if self.rfq_state == 'draft' or self.rfq_state == 'partial_quo' or self.rfq_state == 'sent':
                for line_ids in self:
                    if line_ids.rfq_line_ids:
                        check = all([ids.price_unit > 0 for ids in line_ids.rfq_line_ids])
                        zero_check = all([ids.price_unit == 0 for ids in line_ids.rfq_line_ids])
                        if check:
                            self.update({'rfq_state': 'quo'})
                        elif zero_check:
                            self.update({'rfq_state': 'draft'})
                        elif not check and not zero_check:
                            self.update({'rfq_state': 'partial_quo'})

            if self.rfq_line_ids:
                for ref_rfq in self.rfq_line_ids:
                    if not ref_rfq.ref_rfq_line_id:
                        ref_rfq.ref_rfq_line_id = ref_rfq

                for values in self.rfq_line_ids:
                    if values.product_id:
                        product_tmpl_id = values.product_id.product_tmpl_id.id
                        self.env['product.template'].search(
                            [('company_id', '=', self.company_id.id), ('id', '=', product_tmpl_id)]).write(
                            {'product_transaction': True})

        return result

    @api.multi
    def unlink(self):
        for order in self:
            if not order.rfq_state == 'cancel':
                raise UserError(_('In order to delete a purchase order, you must cancel it first.'))
        return super(RequestForQuotation, self).unlink()

    @api.onchange('partner_id', 'company_id')
    def onchange_partner_id(self):
        if not self.partner_id:
            # Aman 23/07/2020 commented this line because currency id is changing on selection of vendor but we don't want it
            # self.currency_id = False
            pass
        else:
            # Aman 23/07/2020 commented this line because currency id is changing on selection of vendor but we don't want it
            # self.currency_id = self.partner_id.property_purchase_currency_id.id or self.env.user.company_id.currency_id.id
            pass
        return {}

    @api.multi
    def action_sent_for_quotation(self):
        for vals in self:
            if vals.rfq_state == 'draft' or vals.rfq_state == 'sent' or vals.rfq_state == 'partial_quo':
                for line_ids in self:
                    if line_ids.rfq_line_ids:
                        check = all([ids.price_unit > 0 for ids in line_ids.rfq_line_ids])
                        zero_check = all([ids.price_unit == 0 for ids in line_ids.rfq_line_ids])
                        if check:
                            vals.write({'rfq_state': 'quo'})
                            break
                        elif zero_check:
                            raise ValidationError(_("Please enter unit price and then proceed forward!"))
                        else:
                            vals.write({'rfq_state': 'partial_quo'})


    @api.multi
    def action_rfq_send(self):
        """
        This function opens a window to compose an email, with the edi purchase template message loaded by default
        """
        self.ensure_one()
        ir_model_data = self.env['ir.model.data']
        try:
            if self.env.context.get('send_rfq', False):
                template_id = ir_model_data.get_object_reference('purchase_extension', 'email_template_rfq_to_vendor')[
                    1]
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
            'default_model': 'request.for.quotation',
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
    def button_cancel(self):
        for order in self:
            if order.rfq_state in ('draft', 'sent', 'quo', 'partial_quo', 'unawarded'):
                self.write({'rfq_state': 'cancel'})
            elif order.rfq_state in 'cancel':
                raise UserError(_("RFQ is already cancelled."))
            else:
                raise UserError(
                    _('Unable to cancel %s as some receptions have already been done.') % (
                        order.name))
            # If the product is MTO, change the procure_method of the the closest move to purchase to MTS.
            # The purpose is to link the po that the user will manually generate to the existing moves's chain.
            if order.rfq_state in ('draft', 'sent', 'quo', 'partial_quo', 'unawarded'):
                res = super(RequestForQuotation, self).action_cancel()
                res.write({'state': 'cancel'})

    # Piyush: commented as created a new function below on 13-06-2020

    # def function_create_po(self):
    #     for value in self:
    #         data = []
    #         for line_ids in value.rfq_line_ids:
    #             if line_ids.price_unit > 0.0:
    #                 val_data = (0, False, {
    #                     'name': line_ids.name,
    #                     'ref_rfq_line_id': line_ids.ref_rfq_line_id and line_ids.ref_rfq_line_id.id or '',
    #                     'product_id': line_ids.product_id and line_ids.product_id.id or False,
    #                     'date_planned': fields.datetime.now(),
    #                     'product_qty': line_ids.product_qty or 0.0,
    #                     'product_uom': line_ids.product_uom and line_ids.product_uom.id or False,
    #                     'price_unit': line_ids.price_unit or 0.0,
    #                     'taxes_id': [(6, 0, line_ids.taxes_id.ids)] or False,
    #                     'price_subtotal': line_ids.price_subtotal or False,
    #                     'company_id': line_ids.company_id and line_ids.company_id.id,
    #                 })
    #                 data.append(val_data)
    #         if len(data) > 0:
    #             res = self.env['purchase.order']
    #
    #             res.create({
    #                 'name': 'New' or '',
    #                 'origin': value.name or '',
    #                 'ref_rfq_line_id_check': True,
    #                 'order_type': value.order_type or '',
    #                 'partner_id': value.partner_id and value.partner_id.id or False,
    #                 'currency_id': value.currency_id and value.currency_id.id or False,
    #                 'date_order': fields.datetime.now(),
    #                 'company_id': value.company_id and value.company_id.id or self.env.user.company_id.id,
    #                 'reference_rfq_new': value.id or False,
    #                 'order_line': data or [],
    #             })
    #             value.update({'rfq_state': 'purchase'})

    # code ends here

    def _prepare_dict(self):
        rfq_line_list = []
        line_tax_list = []
        for value in self:
            data = []
            for line_ids in value.rfq_line_ids:
                print("line_ids.taxes_id.ids,", line_ids.taxes_id.ids, )
                # if line_ids.taxes_id:
                #     line_tax_list = [ltax.id for ltax in line_ids.taxes_id]
                if line_ids.price_unit > 0.0:
                    order_line_data = (0, False, {
                        'product_id': line_ids.product_id and line_ids.product_id.id or False,
                        # salman add hsn_id
                        'hsn_id':line_ids.hsn_id,
                        # salman end
                        'name': line_ids.product_id and line_ids.product_id.name or '',
                        'product_uom': line_ids.product_uom and line_ids.product_uom.id or False,
                        'product_qty': line_ids.product_qty or 0.0,
                        'qty_ordered': line_ids.qty_ordered or 0.0,
                        'price_subtotal': line_ids.price_subtotal or 0.0,
                        'date_planned': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                        'ref_rfq_line_id': line_ids.ref_rfq_line_id and line_ids.ref_rfq_line_id.id or '',
                        'price_unit': line_ids.price_unit or 0.0,
                        'taxes_id': line_ids.taxes_id.ids,
                        'company_id': line_ids.company_id.id or self.env.user.company_id.id,
                    })
                    rfq_line_list.append(order_line_data)

        return rfq_line_list

    @api.multi
    def button_confirm(self):
        for value in self:
            items = self.env['purchase.order'].search([('reference_rfq_new', '=', value.name)])
            less_list = []
            # Aman 26/7/2020 Fixed partial dependency bugs
            count = 0
            a = 0
            list_po = []
            for i in value.rfq_line_ids:
                for stat in items:
                    if stat.state in ['draft'] and i.total_qty_ordered_hidden < i.product_qty:
                        less_list.append(i)
                    elif stat.state not in ['draft'] and i.total_qty_ordered < i.product_qty:
                        if i.price_unit > 0:
                            list_po.append(i)
                    elif stat.state not in ['draft'] and i.total_qty_ordered >= i.product_qty:
                        count += 1
            rfq_line_list = []
            # for i in list_po:
            print(list_po)
            req_list = set(list_po)
            print(req_list)
            for line_ids in req_list:
                if line_ids.product_qty != line_ids.total_qty_ordered_hidden:
                    if line_ids.price_unit > 0.0:
                        order_line_data = (0, False, {
                            'product_id': line_ids.product_id and line_ids.product_id.id or False,
                            # salman add hsn_id
                            'hsn_id':line_ids.hsn_id,
                            # salman end
                            'name': line_ids.product_id and line_ids.product_id.name or '',
                            'product_uom': line_ids.product_uom and line_ids.product_uom.id or False,
                            'product_qty': line_ids.product_qty - line_ids.total_qty_ordered_hidden or 0.0,
                            'qty_ordered': line_ids.qty_ordered or 0.0,
                            # 'price_subtotal': line_ids.price_subtotal or 0.0,
                            'date_planned': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                            'ref_rfq_line_id': line_ids.ref_rfq_line_id and line_ids.ref_rfq_line_id.id or '',
                            'price_unit': line_ids.price_unit or 0.0,
                            'discount': line_ids.discount or 0.0,
                            # 'taxes_id': [(6, 0, line_tax_list)],
                            'taxes_id': line_ids.taxes_id.ids,
                            'company_id': line_ids.company_id.id or self.env.user.company_id.id,
                        })
                        rfq_line_list.append(order_line_data)
            print('rfq_line_list(1)', rfq_line_list)
            if len(rfq_line_list) > 0:
                action = self.env.ref('purchase.purchase_form_action')
                result = action.read()[0]
                res = self.env.ref('purchase.po_from_rfq_form_view', False)
                result['views'] = [(res and res.id or False, 'form')]
                result['target'] = 'current'
                result['context'] = {
                    'default_name': 'New' or '',
                    'default_origin': value.name or '',
                    'default_ref_rfq_line_id_check': True,
                    'default_reference_rfq_new': value.id or False,
                    'default_date_order': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                    'default_partner_id': value.partner_id and value.partner_id.id or False,
                    'default_currency_id': value.currency_id and value.currency_id.id or False,
                    'default_date_planned': datetime.now() + timedelta(days=1),
                    'default_company_id': value.company_id and value.company_id.id or self.env.user.company_id.id,
                    'default_order_type': 'direct',
                    'default_order_line': rfq_line_list or [],
                }
                return result
            if count > 1:
                raise UserError(_("PO requirements already satisfied for this RFQ as PO created for all items!!"))
            # if a > 1:
            #     raise UserError(_("PO is already created in draft mode for this RFQ or its related RFQ!!"))
            # print('less_list: ', less_list)
            negative_list = []
            for m in value.rfq_line_ids:
                if m.product_qty - m.total_qty_ordered_hidden > 0:
                    negative_list.append(m)
            if items and less_list and negative_list:
                item_list = []
                for line in value.rfq_line_ids:
                    if line.product_qty != line.total_qty_ordered_hidden:
                        item_list.append(line)

                    # Piyush: code for items with PO, but qty not fullfilled on 10-06-2020

                if item_list:
                    rfq_line_list = []
                    line_tax_list = []
                    for line_ids in item_list:
                        # if line_ids.taxes_id:
                        #     line_tax_list = [ltax.id for ltax in line_ids.taxes_id]
                        if line_ids.price_unit > 0.0:
                            order_line_data = (0, False, {
                                'product_id': line_ids.product_id and line_ids.product_id.id or False,
                                # salman add hsn_id
                                'hsn_id': line_ids.hsn_id,
                                # salman end
                                'name': line_ids.product_id and line_ids.product_id.name or '',
                                'product_uom': line_ids.product_uom and line_ids.product_uom.id or False,
                                'product_qty': line_ids.product_qty - line_ids.total_qty_ordered_hidden or 0.0,
                                'qty_ordered': line_ids.qty_ordered or 0.0,
                                'price_subtotal': line_ids.price_subtotal or 0.0,
                                'date_planned': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                                'ref_rfq_line_id': line_ids.ref_rfq_line_id and line_ids.ref_rfq_line_id.id or '',
                                'price_unit': line_ids.price_unit or 0.0,
                                'discount': line_ids.discount or 0.0,
                                # 'taxes_id': [(6, 0, line_tax_list)],
                                'taxes_id': line_ids.taxes_id.ids,
                                'company_id': line_ids.company_id.id or self.env.user.company_id.id,
                            })
                            rfq_line_list.append(order_line_data)

                    if len(rfq_line_list) > 0:
                        action = self.env.ref('purchase.purchase_form_action')
                        result = action.read()[0]
                        res = self.env.ref('purchase.po_from_rfq_form_view', False)
                        result['views'] = [(res and res.id or False, 'form')]
                        result['target'] = 'current'
                        result['context'] = {
                            'default_name': 'New' or '',
                            'default_origin': value.name or '',
                            'default_ref_rfq_line_id_check': True,
                            'default_reference_rfq_new': value.id or False,
                            'default_date_order': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                            'default_partner_id': value.partner_id and value.partner_id.id or False,
                            'default_currency_id': value.currency_id and value.currency_id.id or False,
                            'default_date_planned': datetime.now() + timedelta(days=1),
                            'default_company_id': value.company_id and value.company_id.id or self.env.user.company_id.id,
                            'default_order_type': 'direct',
                            'default_order_line': rfq_line_list or [],
                        }
                        return result

            if items and less_list and not negative_list:
                no_list = []
                po_list = []
                rfq_list = []
                for item in items:
                    for pol in item.order_line:
                        po_list.append(pol.product_id.id)
                for item in value:
                    for rfql in item.rfq_line_ids:
                        rfq_list.append(rfql.product_id.id)
                for notin in rfq_list:
                    if notin not in po_list:
                        no_list.append(notin)
                new_list = []
                for i in no_list:
                    for y in value.rfq_line_ids:
                        if i == y.product_id.id:
                            new_list.append(y)
                if len(new_list) > 0:
                    rfq_line_list = []
                    line_tax_list = []
                    for line_ids in new_list:
                        # if line_ids.taxes_id:
                        #     line_tax_list = [ltax.id for ltax in line_ids.taxes_id]
                        if line_ids.price_unit > 0.0:
                            order_line_data = (0, False, {
                                'product_id': line_ids.product_id and line_ids.product_id.id or False,
                                # salman add hsn_id
                                'hsn_id':line_ids.hsn_id,
                                # salman end
                                'name': line_ids.product_id and line_ids.product_id.name or '',
                                'product_uom': line_ids.product_uom and line_ids.product_uom.id or False,
                                'product_qty': line_ids.product_qty - line_ids.total_qty_ordered_hidden or 0.0,
                                'qty_ordered': line_ids.qty_ordered or 0.0,
                                'price_subtotal': line_ids.price_subtotal or 0.0,
                                'date_planned': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                                'ref_rfq_line_id': line_ids.ref_rfq_line_id and line_ids.ref_rfq_line_id.id or '',
                                'price_unit': line_ids.price_unit or 0.0,
                                'discount': line_ids.discount or 0.0,
                                # 'taxes_id': [(6, 0, line_tax_list)],
                                'taxes_id': line_ids.taxes_id.ids,
                                'company_id': line_ids.company_id.id or self.env.user.company_id.id,
                            })
                            rfq_line_list.append(order_line_data)

                    if len(rfq_line_list) > 0:
                        action = self.env.ref('purchase.purchase_form_action')
                        result = action.read()[0]
                        res = self.env.ref('purchase.po_from_rfq_form_view', False)
                        result['views'] = [(res and res.id or False, 'form')]
                        result['target'] = 'current'
                        result['context'] = {
                            'default_name': 'New' or '',
                            'default_origin': value.name or '',
                            'default_ref_rfq_line_id_check': True,
                            'default_reference_rfq_new': value.id or False,
                            'default_date_order': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                            'default_partner_id': value.partner_id and value.partner_id.id or False,
                            'default_currency_id': value.currency_id and value.currency_id.id or False,
                            'default_date_planned': datetime.now() + timedelta(days=1),
                            'default_company_id': value.company_id and value.company_id.id or self.env.user.company_id.id,
                            'default_order_type': 'direct',
                            'default_order_line': rfq_line_list or [],
                        }
                        return result

            if items:
                no_list = []
                po_list = []
                rfq_list = []
                for item in items:
                    for pol in item.order_line:
                        po_list.append(pol.product_id.id)
                for item in value:
                    for rfql in item.rfq_line_ids:
                        rfq_list.append(rfql.product_id.id)
                for notin in rfq_list:
                    if notin not in po_list:
                        no_list.append(notin)
                new_list = []
                for i in no_list:
                    for y in value.rfq_line_ids:
                        if i == y.product_id.id:
                            new_list.append(y)
                if len(new_list) > 0:
                    rfq_line_list = []
                    line_tax_list = []
                    for line_ids in new_list:
                        # if line_ids.taxes_id:
                        #     line_tax_list = [ltax.id for ltax in line_ids.taxes_id]
                        if line_ids.product_qty != line_ids.total_qty_ordered_hidden:
                            if line_ids.price_unit > 0.0:
                                order_line_data = (0, False, {
                                    'product_id': line_ids.product_id and line_ids.product_id.id or False,
                                    # salman add hsn_id
                                    'hsn_id':line_ids.hsn_id,
                                    # salman end
                                    'name': line_ids.product_id and line_ids.product_id.name or '',
                                    'product_uom': line_ids.product_uom and line_ids.product_uom.id or False,
                                    'product_qty': line_ids.product_qty - line_ids.total_qty_ordered_hidden or 0.0,
                                    'qty_ordered': line_ids.qty_ordered or 0.0,
                                    'price_subtotal': line_ids.price_subtotal or 0.0,
                                    'date_planned': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                                    'ref_rfq_line_id': line_ids.ref_rfq_line_id and line_ids.ref_rfq_line_id.id or '',
                                    'price_unit': line_ids.price_unit or 0.0,
                                    'discount': line_ids.discount or 0.0,
                                    # 'taxes_id': [(6, 0, line_tax_list)],
                                    'taxes_id': line_ids.taxes_id.ids,
                                    'company_id': line_ids.company_id.id or self.env.user.company_id.id,
                                })
                                rfq_line_list.append(order_line_data)
                            else:
                                message = _("Please provide unit price for items!")
                                mess = {
                                    'title': _('Warning: Provide price unit!'),
                                    'message': message
                                }
                                return {'warning': mess}
                        # Check whether the po of reference rfq is created or not
                        else:
                            raise UserError(_("PO requirements already satisfied for this RFQ as PO created for all items!!"))
                    
                    if len(rfq_line_list) > 0:
                        action = self.env.ref('purchase.purchase_form_action')
                        result = action.read()[0]
                        res = self.env.ref('purchase.po_from_rfq_form_view', False)
                        result['views'] = [(res and res.id or False, 'form')]
                        result['target'] = 'current'
                        result['context'] = {
                            'default_name': 'New' or '',
                            'default_origin': value.name or '',
                            'default_ref_rfq_line_id_check': True,
                            'default_reference_rfq_new': value.id or False,
                            'default_date_order': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                            'default_partner_id': value.partner_id and value.partner_id.id or False,
                            'default_currency_id': value.currency_id and value.currency_id.id or False,
                            'default_date_planned': datetime.now() + timedelta(days=1),
                            'default_company_id': value.company_id and value.company_id.id or self.env.user.company_id.id,
                            'default_order_type': 'direct',
                            'default_order_line': rfq_line_list or [],
                        }
                        return result
                else:
                    # message = _("PO requirements already satisfied for this RFQ as PO created for all items!")
                    # mess = {
                    #     'title': _('Warning: PO already created!'),
                    #     'message': message
                    # }
                    # return {'warning': mess}
                    raise UserError(_("PO requirements already satisfied for this RFQ as PO created for all items!"))

            else:
                rfq_line_list = []
                prods = len(value.rfq_line_ids) - 1
                print('-----------abc---------', prods)
                for line_ids in value.rfq_line_ids:
                    if line_ids.total_qty_ordered_hidden >= line_ids.product_qty:
                        a += 1
                        
                    if line_ids.product_qty != line_ids.total_qty_ordered_hidden:
                        if line_ids.price_unit > 0.0:
                            order_line_data = (0, False, {
                                'product_id': line_ids.product_id and line_ids.product_id.id or False,
                                # salman add hsn_id
                                'hsn_id':line_ids.hsn_id,
                                # salman end
                                'name': line_ids.product_id and line_ids.product_id.name or '',
                                'product_uom': line_ids.product_uom and line_ids.product_uom.id or False,
                                'product_qty': line_ids.product_qty - line_ids.total_qty_ordered_hidden or 0.0,
                                'qty_ordered': line_ids.qty_ordered or 0.0,
                                'price_subtotal': line_ids.price_subtotal or 0.0,
                                'date_planned': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                                'ref_rfq_line_id': line_ids.ref_rfq_line_id and line_ids.ref_rfq_line_id.id or '',
                                'price_unit': line_ids.price_unit or 0.0,
                                'discount': line_ids.discount or 0.0,
                                # 'taxes_id': [(6, 0, line_tax_list)],
                                'taxes_id': line_ids.taxes_id.ids,
                                'company_id': line_ids.company_id.id or self.env.user.company_id.id,
                            })
                            rfq_line_list.append(order_line_data)
                if a > prods:
                    raise UserError(_("PO is already created in draft mode for this RFQ or its related RFQ!!"))
                
                # rfq_line_list = self._prepare_dict()
                # Aman 1/08/2020 value of date_order is assigned to server date
                if len(rfq_line_list) > 0:
                    action = self.env.ref('purchase.purchase_form_action')
                    result = action.read()[0]
                    res = self.env.ref('purchase.po_from_rfq_form_view', False)
                    result['views'] = [(res and res.id or False, 'form')]
                    result['target'] = 'current'
                    result['context'] = {
                        'default_name': 'New' or '',
                        'default_origin': value.name or '',
                        'default_ref_rfq_line_id_check': True,
                        'default_reference_rfq_new': value.id or False,
                        'default_date_order': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                        'default_partner_id': value.partner_id and value.partner_id.id or False,
                        'default_currency_id': value.currency_id and value.currency_id.id or False,
                        'default_date_planned': datetime.now() + timedelta(days=1),
                        'default_company_id': value.company_id and value.company_id.id or self.env.user.company_id.id,
                        'default_order_type': 'direct',
                        'default_order_line': rfq_line_list or [],
                    }
                    return result
                # Aman end

            # check = all([ids.price_unit > 0 for ids in value.rfq_line_ids])
            # if check:
            #     self.function_create_po()
            # else:
            #     self.function_create_po()

    name = fields.Char('RFQ', required=True, index=True, copy=False, default=lambda self: _('New'))
    origin = fields.Char('Source Document', copy=False,
                         help="Reference of the document that generated this purchase order "
                              "request (e.g. a sales order)")
    rfq_date = fields.Datetime(string='RFQ Date', required=True, readonly=True, index=True, copy=False,
                               default=fields.Datetime.now)
    fiscal_position_id = fields.Many2one('account.fiscal.position', string='Fiscal Position', oldname='fiscal_position')
    partner_id = fields.Many2one('res.partner', string='Vendor', clickable=True,
                                 track_visibility='always')
    currency_id = fields.Many2one('res.currency', 'Currency', required=True,
                                  default=lambda self: self.env.user.company_id.currency_id.id)
    product_id = fields.Many2one('product.product', string='Product', domain=[('purchase_ok', '=', True)],
                                 change_default=True)
    rfq_line_ids = fields.One2many('request.for.quotation.line', 'rfq_id', 'RFQ Lines')
    amount_untaxed = fields.Monetary(string='Untaxed Amount', store=True, readonly=True, compute='_amount_all',
                                     track_visibility='always')
    amount_tax = fields.Monetary(string='Taxes', store=True, readonly=True, compute='_amount_all')
    amount_total = fields.Monetary(string='Total', store=True, readonly=True, compute='_amount_all')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.user.company_id.id)
    cr_date = fields.Date(string='Create Date', required=True, readonly=True, index=True, copy=False,
                          default=fields.Datetime.now)
    order_type = fields.Selection([('direct', 'Direct')], string='Order Type', copy=False, readonly=True,
                                  default='direct', track_visibility='onchange')
    rfq_state = fields.Selection([
        ('draft', 'RFQ'),
        ('sent', 'RFQ Sent'),
        ('quo', 'Quotation'),
        ('partial_quo', 'Partial Quotation'),
        ('purchase', 'Awarded'),
        ('partial_purchase', 'Partially Awarded'),
        ('unawarded', 'Unawarded'),
        ('cancel', 'Cancelled'),
    ], "RFQ State", track_visibility='onchange', default='draft')
    reference_rfq = fields.Many2one('request.for.quotation', string="Reference RFQ")
    # Aman 25/07/2020 added this field to make partner_id readonly
    rest_vend = fields.Boolean("Check Product", store=True, default=False)
    # Aman 25/07/2020 added this function to make boolean field true or false when we click on rfq_line_ids
    # Yash Start - 26/12/2020 code for print request for quotation
    remarks = fields.Text('Remarks')
    note = fields.Text('Notes')
    notes = fields.Text('Terms and Conditions')

    # Yash End
    @api.onchange('rfq_line_ids')
    def on_change(self):
        self.rest_vend = False
        for line in self.rfq_line_ids:
            if line:
                self.rest_vend = True

    
    # Aman end
    order_calculation_ids = fields.One2many('order.rfq.calculation', 'rfq_id', 'Order Calculation')

    @api.multi
    @api.onchange('rfq_line_ids')
    def onchange_order_l(self):
        self._amount_all()
        self.rfq_line_ids._compute_amount()
        tax_dict = {}
        tax = {}
        amt = 0
        bamt = 0
        if self.rfq_line_ids:
            for line in self.rfq_line_ids:
                tax_dict = genric.check_line(line, line.taxes_id, line.rfq_id.currency_id, line.rfq_id.partner_id, line.product_qty)
                tax = Counter(tax_dict) + Counter(tax)
                print(tax)
                # Aman 24/11/2020 Calculated discounted amount to show on table
                if line.product_id:
                    price = line.product_qty * line.price_unit
                    if line.discount:
                        amt += price * (line.discount / 100)
                    bamt += price
                # Aman end
        charges_data_list = genric.detail_table(self, self.rfq_line_ids, tax, amt, bamt, round_off = False)
        self.order_calculation_ids = [(5, 0, 0)]
        self.order_calculation_ids = charges_data_list


class RequestForQuotationLine(models.Model):
    _name = "request.for.quotation.line"
    _description = "RFQ Line"
    _order = 'id desc'

    @api.multi
    def get_po_action(self):
        """
        Return Last 5 Purchase Order for that item
        """
        list1 = []
        po = self.env['purchase.order']
        all_po = po.search(
            [('state', 'in', (['purchase', 'done'])), ('order_line.product_id', '=', self.product_id.id)],
            order="date_order desc", limit=5)
        if all_po:
            list1 = all_po.ids

        action = self.env.ref('purchase.purchase_form_action')
        result = action.read()[0]
        if list1:
            result['domain'] = "[('id', 'in', " + str(list1) + ")]"
        else:
            raise ValidationError(_('Purchase Order does not exist  !'))

        return result

    # Piyush: code for sending vals in RFQ on basis of RFQ reference on 12-05-2020
    @api.multi
    def _prepare_rfq_line_(self, name, product_qty=0.0, price_unit=0.0, taxes_ids=False):
        self.ensure_one()
        for val in self:
            if val.ref_rfq_line_id:
                new_id = val.ref_rfq_line_id.id
            else:
                new_id = val
            return {
                'name': self.name or '',
                'ref_rfq_line_id': new_id,
                'product_id': self.product_id.id,
                'product_uom': self.product_id.uom_po_id.id,
                'product_qty': self.product_qty,
                'price_unit': 0.0,
                'taxes_id': [(6, 0, taxes_ids)],
            }

    # code ends here

    @api.depends('product_qty', 'price_unit', 'taxes_id')
    def _compute_amount(self):
        for line in self:
            price_unit = line.price_unit * (1.0 - line.discount / 100.0)
            taxes = line.taxes_id.compute_all(price_unit, line.rfq_id.currency_id, line.product_qty,
                                              product=line.product_id, partner=line.rfq_id.partner_id)
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })

    @api.model
    def create(self, values):
        line = super(RequestForQuotationLine, self).create(values)
        #  Gaurav 2/6/20 added code for updating the product / variant detail (product/variant master)
        # pol = self.env['purchase.order.line']
        for product in line:
            if product.product_id:
                purchasedetail = self.env['product.supplierinfo']
                ppd = purchasedetail.search([('name', '=', product.partner_id.id),
                                         ('product_id', '=', product.product_id.id),
                                         ('company_id', '=', self.env.user.company_id.id)])
                print("ppdxxxx", ppd, product.rfq_id.rfq_date, product.rfq_id.name)
                if ppd:
                    print("ppdxxxxif", ppd,product.price_unit,ppd.price)
                    diff = product.price_unit - ppd.price
                    print("ppdxxxxif", diff)

                    ppd.update({'sequence_ref': product.rfq_id.name,
                                'date': product.rfq_id.rfq_date,
                                'name': product.partner_id.id,
                                'product_quantity': product.product_qty,
                                'price': product.price_unit,
                                'price_diff': diff,
                                })
                    print("if end")
                else:
                    print("ppdxxxxelse", ppd, product.partner_id.id)
                    purchasedetail.create({'sequence_ref': product.rfq_id.name,
                                       'date': product.rfq_id.rfq_date,
                                       'name': product.partner_id.id,
                                       'product_id': product.product_id.id,
                                       'product_tmpl_id': product.product_id.product_tmpl_id.id,
                                       'product_quantity': product.product_qty,
                                       'price': product.price_unit,
                                       'price_diff': 0.0,
                                       })
            #             Gaurav end
        return line

    @api.multi
    def write(self, vals):
        result = super(RequestForQuotationLine, self).write(vals)
        #  Gaurav 24/4/20 added code for updating the product / variant detail (product/variant master)
        # pol = self.env['purchase.order.line']
        print("xxxvals" , vals)
        for product in self:
            if product.product_id:
                purchasedetail = self.env['product.supplierinfo']

                ppd = purchasedetail.search([('name', '=', product.partner_id.id),
                                             ('product_id', '=', product.product_id.id),
                                             ('company_id', '=', self.env.user.company_id.id)])
                print("ppdxxxx", ppd)

                if ppd:
                    print("ppdxxxxif write", ppd)
                    if 'price_unit' in vals:
                        # when price is edited update price and difference
                        print("ppdxxxxif", ppd, product.price_unit, ppd.price)
                        diff = product.price_unit - ppd.price
                        print("xxxxxx write price", diff)
                        ppd.update({'sequence_ref': product.rfq_id.name,
                                    'date': product.rfq_id.rfq_date,
                                    'name': product.partner_id.id,
                                    'product_quantity': product.product_qty,
                                    'price': product.price_unit,
                                    'price_diff': diff,
                                    })
                    elif 'product_qty' in vals:
                        # when product qty is edited update only product qty not price difference
                        print("xxxxxx writexx qty")
                        ppd.update({'sequence_ref': product.rfq_id.name,
                                    'date': product.rfq_id.rfq_date,
                                    'name': product.partner_id.id,
                                    'product_quantity': product.product_qty,
                                    'price': product.price_unit,
                                    })

                else:
                    print("ppdxxxxelse", ppd, product.partner_id.id)
                    purchasedetail.create({'sequence_ref': product.rfq_id.name,
                                           'date': product.rfq_line_id.rfq_date,
                                           'name': product.partner_id.id,
                                           'product_id': product.product_id.id,
                                           'product_tmpl_id': product.product_id.product_tmpl_id.id,
                                           'product_quantity': product.product_qty,
                                           'price': product.price_unit,
                                           'price_diff': 0.0,
                                           })
                    #             Gaurav end
        return result


    # salman add a hsn_id field
    hsn_id = fields.Char(string='HSN code')
    # salman end
    name = fields.Text(string='Description', required=True)
    rfq_id = fields.Many2one('request.for.quotation', string='RFQ', index=True,
                             ondelete='cascade')
    rfq_line_id = fields.Many2one('request.for.quotation', string='RFQ Line', index=True)
    ref_rfq_line_id = fields.Many2one('request.for.quotation.line', string='REF RFQ Line', index=True)
    product_qty = fields.Float(string='Requested Qty', digits=dp.get_precision('Product Unit of Measure'),
                               required=True)
    taxes_id = fields.Many2many('account.tax', string='Taxes',
                                domain=['|', ('active', '=', False), ('active', '=', True)])
    product_uom = fields.Many2one('product.uom', string='Product Unit of Measure', required=True)
    product_id = fields.Many2one('product.product', string='Product', domain=[('purchase_ok', '=', True)],
                                 change_default=True)
    price_unit = fields.Float(string='Unit Price', required=True, digits=dp.get_precision('Product Price'))

    price_subtotal = fields.Monetary(compute='_compute_amount', string='Subtotal', store=True)
    price_total = fields.Monetary(compute='_compute_amount', string='Total', store=True)
    price_tax = fields.Float(compute='_compute_amount', string='Tax', store=True)

    company_id = fields.Many2one('res.company', related='rfq_id.company_id', string='Company', store=True,
                                 readonly=True)
    rfq_state = fields.Selection(related='rfq_id.rfq_state', store=True)

    # Piyush: code for adding Received qty field on 12-05-2020
    total_qty_ordered = fields.Float(compute='_compute_total_qty_ordered', string="Total Ordered Qty",
                                     digits=dp.get_precision('Product Unit of Measure'))
    total_qty_ordered_hidden = fields.Float(compute='_compute_total_qty_ordered_hidden', string="Total Ordered Qty Hidden",
                                            digits=dp.get_precision('Product Unit of Measure'))
    qty_ordered = fields.Float(compute='_compute_qty_ordered', string="Ordered Qty", default=0.0,
                               digits=dp.get_precision('Product Unit of Measure'))
    # code ends here

    partner_id = fields.Many2one('res.partner', related='rfq_id.partner_id', string='Partner', readonly=True,
                                 store=True)
    currency_id = fields.Many2one(related='rfq_id.currency_id', store=True, string='Currency', readonly=True)
    rfq_date = fields.Datetime(related='rfq_id.rfq_date', string='RFQ Date', readonly=True)

    # Aman 24/11/2020 Added discount field
    discount = fields.Float(string='Discount (%)', digits=dp.get_precision('Discount'), default=0.0)

    # Piyush: code for computing qty_ordered and total ordered

    @api.multi
    @api.onchange("qty_ordered")
    def _compute_qty_ordered(self):
        for qty in self:
            qty_ordered = 0.0
            products_list = self.env['purchase.order.line'].search(
                [('rfq_id', '=', qty.rfq_id.id),
                 ('product_id', '=', qty.product_id.id)])
            if products_list:
                for line in products_list:
                    if line.state == 'purchase':
                        qty_ordered += line.product_qty
            qty.qty_ordered = qty_ordered

    @api.multi
    def _compute_total_qty_ordered(self):
        for items in self:
            total_qty_ordered = 0.0
            done = self.env['request.for.quotation.line'].search(
                [('ref_rfq_line_id', '=', items.ref_rfq_line_id.id),
                 ('product_id', '=', items.product_id.id)])
            if done:
                linkage_data = self.env['purchase.order.line']
                linkage_data = linkage_data.search([("ref_rfq_line_id", 'in', done.ids),
                                                    ('product_id', '=', items.product_id.id)])
                if linkage_data:
                    for line in linkage_data:
                        if line.state not in 'draft':
                            total_qty_ordered += line.product_qty
            items.total_qty_ordered = total_qty_ordered

    @api.multi
    def _compute_total_qty_ordered_hidden(self):
        for items in self:
            total_qty_ordered_hidden = 0.0
            done = self.env['request.for.quotation.line'].search(
                [('ref_rfq_line_id', '=', items.ref_rfq_line_id.id),
                 ('product_id', '=', items.product_id.id)])
            if done:
                linkage_data = self.env['purchase.order.line']
                linkage_data = linkage_data.search([("ref_rfq_line_id", 'in', done.ids),
                                                    ('product_id', '=', items.product_id.id)])
                if linkage_data:
                    for line in linkage_data:
                        if line.state in ('draft', 'purchase'):
                            total_qty_ordered_hidden += line.product_qty
            items.total_qty_ordered_hidden = total_qty_ordered_hidden

        # code ends here

    # Gaurav 13/3/20 commented and added GST validation code for RFQ and purchase order
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
    # end

    def _compute_purchase_tax(self):

        # Getting default taxes
        fpos = self.rfq_id.fiscal_position_id
        if self.env.uid == SUPERUSER_ID:
            print("purchase super")
            company_id = self.env.user.company_id.id
            # by Jatin to get taxes based on vendor_tax_lines 30-06-2020
            print_tax = self.taxes_of_vendor_tax_lines()
            print('through function', print_tax)

            # print("supplier",self.product_id.supplier_taxes_id)
            taxes_id = fpos.map_tax(
                print_tax.filtered(lambda r: r.company_id.id == company_id))
            print('taxes_id', taxes_id)
            # end Jatin
            # taxes_id = fpos.map_tax(
            #     self.product_id.supplier_taxes_id.filtered(lambda r: r.company_id.id == company_id))

            print("self.taxes_iddddddd", taxes_id, self.partner_id.id)
            taxes_ids_list = taxes_id.ids

            # Gaurav 12/3/20 added code for default tax state wise
            check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
            check_custmr_state = self.env['res.partner'].search(
                [('id', '=', self.partner_id.id), ('company_id', '=', self.env.user.company_id.id)])

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
                self.taxes_id = tax_id_list

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

                # Jatin code changed in for and if on 02-07-2020
                for value in tax_list:
                    if value in tax_id_list:
                        tax_id_list.remove(value)
                        print(tax_id_list)

                self.taxes_id = tax_id_list

            result = {'domain': {'taxes_id': [tax_id_list]}}

        else:
            print("normal")
            # Jatin 02-07-2020 for adding taxes from vendor_tax_lines
            print_tax = self.taxes_of_vendor_tax_lines()
            taxes_id = fpos.map_tax(print_tax)
            # taxes_id = fpos.map_tax(self.product_id.supplier_taxes_id)
            #end

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
                # final = [taxes_ids_list.remove(val.get('id')) for val in csgst_taxes if val.get('id') in taxes_ids_list if csgst_taxes]
                tax_list = []
                tax_id_list = [tax.id for tax in taxes_id]
                if csgst_taxes:
                    for val in csgst_taxes:
                        tax_detail_id = val.get('id')
                        tax_list.append(tax_detail_id)

                for value in tax_list:
                    if value in tax_id_list:
                        tax_id_list.remove(value)
                        print("tax", tax_id_list)
                self.taxes_id = tax_id_list

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

                self.taxes_id = tax_id_list

            result = {'domain': {'taxes_id': [tax_id_list]}}
        return result

    # ----------------------------------
    # Aman 24/07/2020 Warning for user to select vendor before selecting product
    # salman put hsn_code value into hsn_id only
    @api.onchange('product_id')
    def onchange_product(self):
        self.hsn_id = self.product_id.hsn_id.hsn_code
        part = self.rfq_id.partner_id
        if not part:
            warning = {
                'title': _('Warning!!'),
                'message': _('You must select Vendor first!!'),
            }
            return {'warning': warning}
    # salman end        
    # Aman end --------------------------

    @api.onchange('product_id')
    def _onchange_product_id(self):
        # Aman 24/12/2020 Added condition and user error to check if product with
        # hsn_disable = True is selected in last or not
        if self.rfq_id.rfq_line_ids:
            if self.product_id:
                if self.rfq_id.rfq_line_ids[0].product_id.hsn_disable == True:
                    raise UserError(_("This item should be selected in the end!!"))
        # Aman end
        result = {}
        if not self.product_id:
            self.taxes_id = ''
            return result

        # Reset date, price and quantity since _onchange_quantity will provide default values
        self.price_unit = self.product_qty = 0.0
        self.product_uom = self.product_id.uom_po_id or self.product_id.uom_id
        result['domain'] = {'product_uom': [('category_id', '=', self.product_id.uom_id.category_id.id)]}

        product_lang = self.product_id.with_context(
            lang=self.partner_id.lang,
            partner_id=self.partner_id.id,
        )
        self.name = product_lang.display_name
        # Aman 27/11/2020 Added description of product on form level
        if product_lang.description:
            self.name = product_lang.description
        elif product_lang.description_purchase:
            self.name += '\n' + product_lang.description_purchase
        # Aman end

        # Piyush: code for picking taxes in SA on 24-07-2020
        self.taxes_id = ''
        required_taxes = []
        product = self.product_id

        if self.partner_id and self.partner_id.vat and product:

            # GST present , company registered
            check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.company_id.id)])
            check_delivery_address = self.partner_id

            # checking company state and customer state is same or not
            if check_cmpy_state.state_id == check_delivery_address.state_id:
                # Aman 24/12/2020 Added condition to check if product with hsn_disable = True must pick tax
                # of the item with greatest tax
                if product.hsn_disable == True:
                    group_type = ('CGST', 'SGST')
                    taxes_cust = genric.get_taxes(self, product, group_type, rfq=True)
                    for i in taxes_cust:
                        required_taxes.append(i)
                # Aman end
                else:
                    # if same states show taxes like CGST SGST GST
                    self.env.cr.execute(
                        """ select id from account_tax where active=True and type_tax_use='purchase' AND tax_group_id!=4 and company_id='%s'""" % (
                            self.env.user.company_id.id,))
                    csgst_taxes = self.env.cr.dictfetchall()

                    all_purchase_taxes = []
                    for val in self:
                        all_purchase_taxes = val.product_id.vendor_tax_lines
                    all_taxes_list = [taxes.tax_id.id for taxes in all_purchase_taxes]

                    all_tax_list = [all_tax['id'] for all_tax in csgst_taxes]

                    for tax in all_tax_list:
                        for tax_id in all_taxes_list:
                            if tax == tax_id:
                                required_taxes.append(tax)

            elif check_cmpy_state.state_id != check_delivery_address.state_id:
                # Aman 24/12/2020 Added condition to check if product with hsn_disable = True must pick tax
                # of the item with greatest tax
                if product.hsn_disable == True:
                    group_type = ('IGST')
                    taxes_cust = genric.get_taxes(self, product, group_type, rfq=True)
                    for i in taxes_cust:
                        required_taxes.append(i)
                # Aman end
                else:
                    # if different states show taxes like IGST
                    self.env.cr.execute(
                        """ select id from account_tax where active=True and type_tax_use='purchase' AND tax_group_id not in (2,3) and company_id='%s'""" % (
                            self.env.user.company_id.id,))
                    igst_taxes = self.env.cr.dictfetchall()

                    all_purchase_taxes = []
                    for val in self:
                        all_purchase_taxes = val.product_id.vendor_tax_lines
                    all_taxes_list = [taxes.tax_id.id for taxes in all_purchase_taxes]

                    all_tax_list = [all_tax['id'] for all_tax in igst_taxes]

                    for tax in all_tax_list:
                        for tax_id in all_taxes_list:
                            if tax == tax_id:
                                required_taxes.append(tax)

            self.update({'taxes_id': [(6, 0, required_taxes)]})

            # code ends here

        # # Gaurav 20/6/20 added code for rfq tax
        # check_partner = self.env['res.partner'].search([('id', '=', self.partner_id.id)])
        # print("self.env.user.company_id.vattttttttttttttttttttttt", check_partner.name, check_partner.vat)
        #
        # # company_vat = self.env.user.company_id
        # # print("cccxxxx,", company_vat.vat)
        # # if self.env.user.company_id.vat:
        # if check_partner.vat:
        #     # GST present , company registered
        #     # Gaurav 12/3/20 added code for default tax state wise
        #     check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
        #     check_custmr_state = self.env['res.partner'].search(
        #         [('id', '=', self.partner_id.id), ('company_id', '=', self.env.user.company_id.id)])
        #     # checking company state and customer state is same or not
        #     if check_cmpy_state.state_id == check_custmr_state.state_id:
        #         # if same states show taxes like CGST SGST GST
        #         self.env.cr.execute(
        #             """select id from account_tax where active=True and type_tax_use='purchase' and tax_group_id!=4 and company_id='%s'""" % (
        #                 self.env.user.company_id.id,))
        #         csgst_taxes = self.env.cr.dictfetchall()
        #         print("purchase csgst_taxessssss", csgst_taxes)
        #         # self._set_taxes()
        #         self._compute_purchase_tax()
        #         cs_tax_list = []
        #         if csgst_taxes:
        #             for val in csgst_taxes:
        #                 tax_detail_idcs = val.get('id')
        #                 cs_tax_list.append(tax_detail_idcs)
        #                 print("cs_tax_listttt", cs_tax_list)
        #                 # self.update({'tax_id': [(6, 0, cs_tax_list)]})
        #                 result = {'domain': {'taxes_id': [('id', 'in', cs_tax_list)]}}
        #
        #     elif check_cmpy_state.state_id != check_custmr_state.state_id:
        #         # if different states show taxes like IGST
        #         self.env.cr.execute(
        #             """select id from account_tax where active=True and type_tax_use='purchase' and tax_group_id not
        #             in (2,3) and company_id='%s'""" % (
        #                 self.env.user.company_id.id,))
        #         igst_taxes = self.env.cr.dictfetchall()
        #         # self._set_taxes()
        #         self._compute_purchase_tax()
        #         i_tax_list = []
        #         if igst_taxes:
        #             for val in igst_taxes:
        #                 tax_detail_idi = val.get('id')
        #                 i_tax_list.append(tax_detail_idi)
        #                 result = {'domain': {'taxes_id': [('id', 'in', i_tax_list)]}}

        # self._suggest_quantity()
        # self._onchange_quantity()

        return result

    @api.onchange('product_qty', 'product_uom')
    def _onchange_quantity(self):
        if not self.product_id:
            return

        seller = self.product_id._select_seller(
            partner_id=self.partner_id,
            quantity=self.product_qty,
            date=self.rfq_id.rfq_date and self.rfq_id.rfq_date[:10],
            uom_id=self.product_uom)

        if not seller:
            return

        # Jatin 02-07-2020 for taxes fron vendor_tax_lines
        print_tax = self.taxes_of_vendor_tax_lines()

        price_unit = self.env['account.tax']._fix_tax_included_price_company(seller.price,
                                                                             print_tax,
                                                                             self.taxes_id,
                                                                             self.company_id) if seller else 0.0
        # end Jatin
        if price_unit and seller and self.rfq_id.currency_id and seller.currency_id != self.rfq_id.currency_id:
            price_unit = seller.currency_id.compute(price_unit, self.rfq_id.currency_id)

        if seller and self.product_uom and seller.product_uom != self.product_uom:
            price_unit = seller.product_uom._compute_price(price_unit, self.product_uom)

        # self.price_unit = price_unit

    def _suggest_quantity(self):
        """
        Suggest a minimal quantity based on the seller
        """
        if not self.product_id:
            return
        seller_min_qty = self.product_id.seller_ids \
            .filtered(
            lambda r: r.name == self.rfq_id.partner_id and (not r.product_id or r.product_id == self.product_id)) \
            .sorted(key=lambda r: r.min_qty)
        if seller_min_qty:
            self.product_qty = seller_min_qty[0].min_qty or 1.0
            self.product_uom = seller_min_qty[0].product_uom
        else:
            self.product_qty = 1.0


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    @api.multi
    def mail_rfq_on_send(self):
        if self._context.get('purchase_mark_rfq_sent'):
            order = self.env['request.for.quotation'].browse(self._context['default_res_id'])
            if order.rfq_state == 'draft':
                order.rfq_state = 'sent'

    @api.multi
    def send_mail(self, auto_commit=False):
        if self._context.get('default_model') == 'request.for.quotation' and self._context.get('default_res_id'):
            order = self.env['request.for.quotation'].browse(self._context['default_res_id'])
            self = self.with_context(mail_post_autofollow=True, lang=order.partner_id.lang)
            self.mail_rfq_on_send()
        return super(MailComposeMessage, self).send_mail(auto_commit=auto_commit)



#==================== Gaurav 5/6/20 added and inherit for short close and amendment===============

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    short_closed = fields.Boolean("Short Close")
    ammendmend_count = fields.Integer(compute='_compute_ammendmend_number', string='Number of Amendment')
    po_amd_ids = fields.One2many('purchase.order.amd', 'purchase_id',
                                          string='PO Amendment', readonly=True)

    # Gaurav 5/6/20 added compute to get no of AMD
    @api.multi
    @api.depends('po_amd_ids')
    def _compute_ammendmend_number(self):
        for amd in self:
            amd.ammendmend_count = len(amd.po_amd_ids)

    # Gaurav 5/6/20 added onchange for shortclose
    @api.onchange('short_closed')
    def _onchange_short_closed(self):
        print("short_closed")
        res={}
        if self.short_closed == True:

            res = {'warning': {
                'title': ('Information'),
                'message': ('Are you sure, you want to Short Close the Purchase order!')
            }
            }
        if res:
            return res
    # Gaurav 5/6/20 added for create to short close and set state to short close
    @api.model
    def create(self, vals):
        res = super(PurchaseOrder, self).create(vals)
        if res.short_closed == True:
            res.write({'state': "short_close"})
        return res

    # Gaurav 5/6/20 added for write to short close and set state to short close for PO as well as receipts
    @api.multi
    def write(self, vals):

        # ----------------------
        # Gaurav 6/6/20 Preparing Ammendmend Data / setting reference

        amd_name = ''
        if self.po_amd_ids:
            amd_count = len(self.po_amd_ids.ids) + 1
            amd_name = 'PO AMD' + str(amd_count)
        else:
            amd_name = 'PO AMD' + str(1)
        amd_data = self._amendment_data(amd_name)

        # ----------------

        result = super(PurchaseOrder, self).write(vals)
        # -------------------
        # Gaurav 6/6/20 checking for state and confirm order to create data in amd if any changes happens
        if 'state' not in vals and self.state == 'purchase':
            if 'order_line' in vals or 'order_line.product_qty' in vals or 'order_line.price_unit' in vals:
                self.env['purchase.order.amd'].create(amd_data)
                self.update({'state': 'to approve'})

        # ---------------------------------------------
        # Gaurav 19/6/20 updated short close funcnlty acc to state
        print("xxxxxxvals",vals, self.picking_ids)
        if 'short_closed' in vals and self.short_closed==True:
            self.write({'state': "short_close"})
            # getting picking ids(receipts related to PO) and setting state short close
            pick = self.picking_ids
            short_pick = pick.filtered(lambda shcd: shcd.state not in ('done','bill_pending','cancel'))
            if len(short_pick)>0:
                for picking in short_pick:
                    picking.update({'state': "short_close"})
        elif self.state == 'short_close' and 'state' not in vals:
            raise ValidationError("You can not make changes in PO, This PO has been Short Closed !")
        # ------------------------------------------------


        return result

    # Gaurav 6/6/20 amendment function data creation

    def _amendment_data(self, amd_name):
        line_data_list = []

        if self.order_line:
            for line in self.order_line:
                line_data = (0, False, {
                    'product_id': line.product_id and line.product_id.id or False,
                    'name': line.name or False,
                    'product_uom': line.product_uom and line.product_uom.id or False,
                    'product_qty': line.product_qty or 0.0,
                    'price_unit': line.price_unit or 0.0,
                    'qty_ordered': line.qty_ordered or 0.0,
                    'purchase_id': line.order_id and line.order_id.id or False,
                    'company_id': line.company_id and line.company_id.id or False,
                    'date_planned' : line.date_planned,
                    'qty_invoiced' : line.qty_ordered or 0.0,
                    # 'taxes_id' : line.taxes_id.id or False,
                    'price_subtotal' : line.price_subtotal or 0.0,
                })
                line_data_list.append(line_data)

        amd_vals = {
            'name': amd_name,
            'purchase_id': self.id or False,
            'partner_id': self.partner_id and self.partner_id.id or False,
            'date_order': self.date_order,
            'date_planned': self.date_planned,
            'company_id': self.company_id and self.company_id.id or False,
            'state': self.state or '',
            'picking_type_id': self.picking_type_id.id,
            'order_amd_line': line_data_list,
            'invoice_status': self.invoice_status,
            'date_approve' : self.date_approve,
        }
        return amd_vals

    # Gaurav 6/6/20 for opening reference from smart button(AMD) for AMD tree and AMD form

    def get_current_ammendmend_history(self):
        """
        Get Current Form Agreement Ammendmend History
        """
        result = {}
        all_agreements_amd_ids = []
        company_id = self.env.user.company_id.id
        all_agreements_amd = self.env['purchase.order.amd'].search(
            [('id', 'in', self.po_amd_ids and self.po_amd_ids.ids or []),
             ('company_id', '=', company_id)])
        if all_agreements_amd:
            all_agreements_amd_ids = all_agreements_amd.ids
        action = self.env.ref('purchase_extension.action_purchase_order_amd')
        result = action.read()[0]
        res = self.env.ref('purchase_extension.view_purchase_order_amd_tree', False)
        res_form = self.env.ref('purchase_extension.view_purchase_order_amd_form', False)
        result['views'] = [(res and res.id or False, 'list'), (res_form and res_form.id or False, 'form')]
        result['domain'] = [('id', 'in', tuple(all_agreements_amd_ids))]
        result['target'] = 'current'
        result['view_type'] = 'tree'
        result['view_mode'] = 'tree,form'
        return result

    # Gaurav end


# Gaurav 5/6/20 added and creating amendmend and amd lines


class PurchaseOrderAmd(models.Model):
    _name = "purchase.order.amd"
    _description = "Purchase Order Amendmend"
    _inherit = ['mail.thread']
    _order = "id desc"


    # -----------------------------------
    purchase_id= fields.Many2one('purchase.order', "Purchase order")
    # -----
    READONLY_STATES = {
        'purchase': [('readonly', True)],
        'done': [('readonly', True)],
        'cancel': [('readonly', True)],
    }
    name = fields.Char('Order Reference', required=True, index=True, copy=False, default='New')
    origin = fields.Char('Source Document', copy=False,
                         help="Reference of the document that generated this purchase order "
                              "request (e.g. a sales order)")
    rfq_id = fields.Many2one('request.for.quotation', string='RFQ', index=True)
    partner_ref = fields.Char('Vendor Reference', copy=False,
                              help="Reference of the sales order or bid sent by the vendor. "
                                   "It's used to do the matching when you receive the "
                                   "products as this reference is usually written on the "
                                   "delivery order sent by your vendor.")
    ref_rfq_line_id_check = fields.Boolean(string="check", default=False, help="check for value of ref_rfq_line_id on"
                                                                               " its basis ordertype and vendor will be made readonly")

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
    state = fields.Selection([
        ('draft', 'Draft'),
        ('to approve', 'To Approve'),
        ('purchase', 'Purchase Order'),
        ('short_close', 'Short Close'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled')
    ], string='Status', readonly=True, index=True, copy=False, default='draft', track_visibility='onchange')

    order_amd_line = fields.One2many('purchase.order.line.amd', 'order_amd_id', string='Order AMD Lines',
                                 states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}, copy=True)
    notes = fields.Text('Terms and Conditions')

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

    product_id = fields.Many2one('product.product', related='order_amd_line.product_id', string='Product')

    reference_rfq_new = fields.Many2one('request.for.quotation', string="Reference RFQ")
    create_uid = fields.Many2one('res.users', 'Responsible')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, states=READONLY_STATES,
                                 default=lambda self: self.env.user.company_id.id)

    picking_type_id = fields.Many2one('stock.picking.type', 'Deliver To', states=READONLY_STATES, required=True,
                                      help="This will determine operation type of incoming shipment")
    default_location_dest_id_usage = fields.Selection(related='picking_type_id.default_location_dest_id.usage',
                                                      string='Destination Location Type',
                                                      help="Technical field used to display the Drop Ship Address",
                                                      readonly=True)
    group_id = fields.Many2one('procurement.group', string="Procurement Group", copy=False)
    is_shipped = fields.Boolean()
    # is_shipped = fields.Boolean(compute="_compute_is_shipped")
    # website_url = fields.Char(
    #     'Website URL', compute='_website_url',
    #     help='The full URL to access the document through the website.')

    order_type = fields.Selection([
        ('direct', 'Direct'),
        ('open', 'Open'),
        ('arc', 'Arc'),
    ], string='Order Type', copy=False, default='direct', track_visibility='onchange')

    start_date = fields.Date('Start Date', required=True, default=fields.Datetime.now,
                             help="Used for Order Scheduling Start Date in case of Open Order")
    end_date = fields.Date('End Date', required=True, default=fields.Datetime.now,
                           help="Used for Order Scheduling End Date in case of Open Order")

    check_registered = fields.Boolean("Check Registered", store=True, default=False)
    check_order_line = fields.Boolean("Check Order Line", store=True, default=False)

    # start_date = fields.Date('Start Date', required=True, default=fields.Datetime.now,
    #                          help="Used for Order Scheduling Start Date in case of Open Order")
    # end_date = fields.Date('End Date', required=True, default=fields.Datetime.now,
    #                        help="Used for Order Scheduling End Date in case of Open Order")
    as_per_schedule = fields.Boolean('As Per Schedule', default=False)

    date_rfq = fields.Datetime(string="RFQ Date", default=fields.Datetime.now, readonly=True)
    reference_rfq = fields.Many2one('purchase.order', string="Reference RFQ")


class PurchaseOrderLineAmd(models.Model):
    _name = "purchase.order.line.amd"
    _description = "Purchase Order Line Amendment"
    # _rec_name = 'product_id'

    order_amd_id = fields.Many2one('purchase.order.amd', string='AMD No')
    purchase_id = fields.Many2one('purchase.order', "Purchase order")
    #

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


    ref_rfq_line_id = fields.Many2one('request.for.quotation.line', string="REF RFQ line", store=True)
    rfq_id = fields.Many2one(related="order_amd_id.reference_rfq_new", string="RFQ ID", store=True)

    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Analytic Tags')
    company_id = fields.Many2one('res.company', related='order_amd_id.company_id', string='Company', store=True,
                                 readonly=True)
    state = fields.Selection(related='order_amd_id.state', store=True)

    invoice_lines = fields.One2many('account.invoice.line', 'purchase_line_id', string="Bill Lines", readonly=True,
                                    copy=False)

    qty_invoiced = fields.Float(compute='_compute_qty_invoiced', string="Billed Qty",
                                digits=dp.get_precision('Product Unit of Measure'), store=True)
    qty_received = fields.Float(compute='_compute_qty_received', string="Received Qty",
                                digits=dp.get_precision('Product Unit of Measure'), store=True, compute_sudo=True)

    qty_ordered = fields.Float(string="Ordered Qty",
                               digits=dp.get_precision('Product Unit of Measure'), store=True)

    partner_id = fields.Many2one('res.partner', related='order_amd_id.partner_id', string='Partner', readonly=True,
                                 store=True)
    currency_id = fields.Many2one(related='order_amd_id.currency_id', store=True, string='Currency', readonly=True)
    date_order = fields.Datetime(related='order_amd_id.date_order', string='Order Date', readonly=True)

    orderpoint_id = fields.Many2one('stock.warehouse.orderpoint', 'Orderpoint')
    move_dest_ids = fields.One2many('stock.move', 'created_purchase_line_id', 'Downstream Moves')



# -------------------------Gaurav end amd-------------------------

class OrderRfqCalculation(models.Model):
    _name = "order.rfq.calculation"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Order RFQ Calculation"
    _order = 'serial_no'

    name = fields.Char('Description')
    rfq_id = fields.Many2one('request.for.quotation', 'RFQ')
    category = fields.Char('Category')
    label = fields.Char('Label')
    amount = fields.Float('Amount')
    serial_no = fields.Integer('Sr No')
    company_id = fields.Many2one('res.company', 'Company', index=True,
                                 default=lambda self: self.env.user.company_id.id)
    cr_date = fields.Date(string='Create Date', required=True, readonly=True, index=True, copy=False,
                          default=fields.Datetime.now)
