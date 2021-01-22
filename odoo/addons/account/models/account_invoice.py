# -*- coding: utf-8 -*-
from num2words import num2words
from odoo.addons.account.models import genric
import json
import re
import uuid
from functools import partial
from datetime import datetime
from datetime import timedelta
from datetime import datetime
from collections import Counter
import time
from lxml import etree
from dateutil.relativedelta import relativedelta
from werkzeug.urls import url_encode

from odoo import api, exceptions, fields, models, _, tools
from odoo.tools import float_is_zero, float_compare, pycompat, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.misc import formatLang

from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError, Warning

from odoo.addons import decimal_precision as dp
import logging
from odoo.addons.sale_ext.models import sale_ext_inv_adj


_logger = logging.getLogger(__name__)

# avinash:02/11/20 Added condition for sale and purchase return
# mapping invoice type to journal type
TYPE2JOURNAL = {
    'out_invoice': 'sale',
    'in_invoice': 'purchase',
    # 'out_refund': 'sale',
    'out_refund': 'credit_note',
    # 'in_refund': 'purchase',
    'in_refund': 'debit_note',
}
# end avinash
# mapping invoice type to refund type
TYPE2REFUND = {
    'out_invoice': 'out_refund',        # Customer Invoice
    'in_invoice': 'in_refund',          # Vendor Bill
    'out_refund': 'out_invoice',        # Customer Credit Note
    'in_refund': 'in_invoice',          # Vendor Credit Note
}

MAGIC_COLUMNS = ('id', 'create_uid', 'create_date', 'write_uid', 'write_date')
TAX_SGST = 'SGST'
TAX_CGST = 'CGST'
TAX_IGST = 'IGST'

PRINT_COPIES_NUMBER = 4


# Yash - Start 10/11/2020 : Print account invoice pdf report
# To get tax line data
def get_inline_tax_data(tax_data, order_tax_details, order):
    """
    Get tax details name, amount, tax group
    :param tax_data: The tax data object contains tax data
    :param order_tax_details: tax details from inline items
    :param order: order item
    :return:
    """
    type = ''
    tax_id = ''
    tax_group_name = ''
    if tax_data.tax_id:
        tax_id = tax_data.tax_id.id
    if tax_data.tax_id.amount_type == 'percent':
        type = '%'
    if tax_data.tax_id.tax_group_id.name:
        tax_group_name = tax_data.tax_id.tax_group_id.name
    name = str(tax_data.tax_id.amount) + type
    if tax_data.tax_id:
        tax_amount = tax_data.tax_id.amount
    else:
        tax_amount = order_tax_details.amount
    amount = (order.price_subtotal * tax_amount) / 100
    return {
        'tax_id': tax_id,
        'name': name,
        'amount': amount,
        'tax_group_name': tax_group_name
    }


def get_tax_line_data(tax_line_data, tax_detail):
    """
    Method to get tax line and add same tax amount
    :param tax_line_data: The inline tax data dict
    :param tax_detail: the line item contains tax data
    :return:
    """
    if 'tax_group_name' in tax_detail and tax_detail['tax_group_name'] == TAX_IGST:
        tax_line_data['igst_tax_name'] = tax_detail['name']
        tax_line_data['igst_tax_group'] = TAX_IGST
        tax_line_data['igst_tax_price'] += tax_detail['amount']
    if 'tax_group_name' in tax_detail and tax_detail['tax_group_name'] == TAX_SGST:
        tax_line_data['sgst_tax_name'] = tax_detail['name']
        tax_line_data['sgst_tax_group'] = TAX_SGST
        tax_line_data['sgst_tax_price'] += tax_detail['amount']
    if 'tax_group_name' in tax_detail and tax_detail['tax_group_name'] == TAX_CGST:
        tax_line_data['cgst_tax_name'] = tax_detail['name']
        tax_line_data['cgst_tax_group'] = TAX_CGST
        tax_line_data['cgst_tax_price'] += tax_detail['amount']
# Yash - End 10/11/2020 : Print account invoice pdf report


class AccountInvoice(models.Model):
    _name = "account.invoice"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Invoice"
    _order = "date_invoice desc, number desc, id desc"

    # shivam
    @api.multi
    def action_view_voucher(self):
        action = self.env.ref('account.action_move_journal_line')
        result = action.read()[0]
        # override the context to get rid of the default filtering on operation type
        result['context'] = {}
        move_id = self.mapped('move_id')
        res = self.env.ref('account.view_move_form', False)
        result['views'] = [(res and res.id or False, 'form')]
        result['res_id'] = move_id.id
        return result


    #salman : 23/11/2020 code written for voucher function
    @api.multi
    def action_view_sale_voucher(self): 
        action = self.env.ref('account.action_move_journal_line')
        result = action.read()[0]
        # override the context to get rid of the default filtering on operation type
        result['context'] = {}
        ref_id = self.env['account.move'].search([('id', '=', self.move_id.id)])
        if not ref_id and len(ref_id) > 1:
            result['domain'] = ref_id
        elif len(ref_id) == 1:
            res = self.env.ref('account.view_move_form', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = ref_id.id
        return result


    voucher_sale_count = fields.Integer(compute='get_voucher_sale_count')
    voucher_sale_return_count = fields.Integer(compute='get_voucher_sale_count')

    def get_voucher_sale_count(self):
        count = self.env['account.move'].search_count([('id', '=', self.move_id.id)])
        self.voucher_sale_count = count
        self.voucher_sale_return_count=count
    #end salman
    


    voucher_count = fields.Integer(string='Appointment', compute='get_voucher_count')

    def get_voucher_count(self):
        count = self.env['account.move'].search_count([('id', '=', self.move_id.id)])
        self.voucher_count = count

    # shivam code end


    def _get_default_access_token(self):
        return str(uuid.uuid4())

    @api.one
    @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'tax_line_ids.amount_rounding',
                 'currency_id', 'company_id', 'date_invoice', 'type')
    def _compute_amount(self):
        round_curr = self.currency_id.round
        self.amount_untaxed = sum(line.price_subtotal for line in self.invoice_line_ids)
        self.amount_tax = sum(round_curr(line.amount_total) for line in self.tax_line_ids)
        self.amount_total = self.amount_untaxed + self.amount_tax
        amount_total_company_signed = self.amount_total
        amount_untaxed_signed = self.amount_untaxed
        if self.currency_id and self.company_id and self.currency_id != self.company_id.currency_id:
            currency_id = self.currency_id.with_context(date=self.date_invoice)
            amount_total_company_signed = currency_id.compute(self.amount_total, self.company_id.currency_id)
            amount_untaxed_signed = currency_id.compute(self.amount_untaxed, self.company_id.currency_id)
        sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
        self.amount_total_company_signed = amount_total_company_signed * sign
        self.amount_total_signed = self.amount_total * sign
        self.amount_untaxed_signed = amount_untaxed_signed * sign

    # Yash - Start 10/11/2020 : Print account invoice pdf report
    def _get_print_page_number(self):
        return PRINT_COPIES_NUMBER
        # return 1

    def _get_copy_name(self, n):
        if n == 0:
            return 'Original Copy'
        if n == 1:
            return "Duplicate Copy"
        if n == 2:
            return "Triplicate Copy"
        if n == 3:
            return "Extra Copy"

    @api.multi
    def _get_tax_type(self):
        """
        Check tax type in invoice to create aggregate tax amount on hsn code.
        For Integrated Tax, Center and State tax table
        :return:
        """
        igst = False
        for line in self.tax_line_ids:
            if line.tax_id.tax_group_id.name == TAX_IGST:
                igst = True
                break
        return igst

    @api.multi
    def _get_order_line_taxes(self):
        """
        Method to get line rate and taxes for each hsn code
        Table number 2
        :return:
        """
        order_line_list = []
        tax_line_dict = dict((tax.tax_id.id, tax) for tax in self.tax_line_ids)
        for order in self.invoice_line_ids:
            if order.product_id.id:
                data = {
                    'hsn_code': order.product_id.hsn_id.hsn_code,
                    'price_subtotal': order.price_subtotal,
                    'tax_data': [],
                    'total': 0,
                }
                if order.invoice_line_tax_ids:
                    for tax_details in order.invoice_line_tax_ids:
                        tax_data = tax_line_dict.get(tax_details.id, None)
                        if tax_data:
                            data_dict = get_inline_tax_data(tax_data, tax_details, order)
                            data['tax_data'].append(data_dict)
                            data['total'] += data_dict['amount']
                data['total'] += order.price_subtotal
                order_line_list.append(data)
                if len(data['tax_data']) == 0:
                    data['tax_data'].append({'name': '', 'amount': ''})

        order_line_dict = {}
        # Convert list into dict with key as hsn_code and tax list
        for line in order_line_list:
            if line['hsn_code'] not in order_line_dict:
                order_line_dict[line['hsn_code']] = []
            order_line_dict[line['hsn_code']].append(line)
        tax_line_list = []
        for key, value in order_line_dict.items():
            tax_line_data = {
                'hsn_code': key,
                'igst_tax_name': '',
                'igst_tax_price': 0,
                'igst_tax_group': '',
                'sgst_tax_name': '',
                'sgst_tax_price': 0,
                'sgst_tax_group': '',
                'cgst_tax_name': '',
                'cgst_tax_price': 0,
                'cgst_tax_group': '',
                'price_subtotal': 0,
                'total': 0,
            }
            for v in value:
                for line in v['tax_data']:
                    get_tax_line_data(tax_line_data, line)
                tax_line_data['price_subtotal'] += v['price_subtotal']
                # tax_line_data['total'] += v['total']
            tax_line_data['total'] = tax_line_data['igst_tax_price'] + tax_line_data['cgst_tax_price'] + \
                                     tax_line_data['sgst_tax_price']
            tax_line_list.append(tax_line_data)

        return tax_line_list

    @api.multi
    def _get_all_applied_taxes(self):
        """
        Method to create all output tax line
        In table no. 1
        :return:
        """
        order_line_list = []
        tax_line_dict = dict((tax.tax_id.id, tax) for tax in self.tax_line_ids)
        # Create a list of all taxes and ther amount
        for order in self.invoice_line_ids:
            if order.invoice_line_tax_ids:
                for tax_details in order.invoice_line_tax_ids:
                    tax_data = tax_line_dict.get(tax_details.id, False)
                    if tax_data:
                        data_dict = {
                            'tax_group': tax_data.tax_id.tax_group_id.name,
                            'tax_id': tax_data.tax_id.id,
                            'name': tax_data.name,
                            'amount': tax_data.amount
                        }
                        order_line_list.append(data_dict)

        tax_data_dict = {}
        # Create dict of taxes -tax id as key and tax details as values-
        # for each tax their will be its total tax amount
        for line in order_line_list:
            if line['tax_id'] not in tax_data_dict:
                tax_data_dict[line['tax_id']] = {}
            if not bool(tax_data_dict[line['tax_id']]):
                tax_data_dict[line['tax_id']] = line
        tax_line_list = []
        # Run loop in tax dict and add tax details in the list
        for key, value in tax_data_dict.items():
            tax_line_list.append(value)

        return tax_line_list

    def _get_cash_round_item(self):
        """
        Method to get cash round items
        :return:
        """
        cash_round_item = []
        for invoice_line in self.invoice_line_ids:
            if invoice_line.product_id.id is False:
                data = {
                    'name': invoice_line.account_id.name if invoice_line.account_id else '',
                    'price_subtotal': invoice_line.price_subtotal if invoice_line.price_subtotal else '',
                }
                cash_round_item.append(data)
        return cash_round_item

    def _get_print_inline_items(self):
        """
        Method to get invoice inline items and description for the print
        :return:
        """
        discount_applied = self.env['res.config.settings'].search(
            [('company_id', '=', self.company_id.id)]).sorted(lambda x: x.id, reverse=True)
        if len(discount_applied) > 0:
            discount_applied = discount_applied[0]
        invoice_line_items = []
        for line in self.invoice_line_ids:
            data = {
                'product_id': line.product_id.id or '',
                'product_name': line.product_id.name or '',
                'product_default_code': line.product_id.default_code or '',
                'product_id_hsn_id': line.product_id.hsn_id.hsn_code or '',
                'quantity': line.quantity or 0,
                'price_unit': line.price_unit or '',
                'uom_id': line.uom_id.name or '',
                'price_subtotal': line.price_subtotal,
                'discount_applied': discount_applied.group_discount_per_so_line or False
            }
            if discount_applied and discount_applied.group_discount_per_so_line:
                data['discount'] = line.discount or 0
                data['discount_value'] = line.price_unit * line.discount * line.quantity * 0.01
                data['discount_unit_price'] = line.price_unit - (line.price_unit * line.discount * 0.01)

            invoice_line_items.append(data)
        return invoice_line_items

    def check_is_discount_applied(self):
        """
        Check is discount is applied true/false in configuration settings
        :return:
        """
        discount_applied = self.env['res.config.settings'].search(
            [('company_id', '=', self.company_id.id)]).sorted(lambda x: x.id, reverse=True)
        if len(discount_applied) > 0:
            discount_applied = discount_applied[0]
            return discount_applied[0].group_discount_per_so_line
        else:
            return False

    def get_sub_total_amount(self):
        """
        Method to get sub total amount
        :return:
        """
        sub_total_amount = 0
        if self.order_calculation_ids:
            for line in self.order_calculation_ids:
                if line.category == 'Subtotal':
                    sub_total_amount = line.amount
        else:
            for line in self.invoice_line_ids:
                sub_total_amount += line.price_subtotal

        return sub_total_amount

    def _get_hsn_code_total_taxes(self):
        """
        Method to aggregate the taxes(CGST and SGST) on the base of same hsn code
        :return:
        """
        taxes_line = []
        tax_line_dict = {}
        for tax in self.tax_line_ids:
            if tax.tax_id.tax_group_id.name not in tax_line_dict:
                tax_line_dict[tax.tax_id.tax_group_id.name] = []
            tax_line_dict[tax.tax_id.tax_group_id.name].append(tax)

        for key, values in tax_line_dict.items():
            data = {
                'name': key,
                'amount': 0
            }
            for tax in values:
                data['amount'] += tax.amount
            taxes_line.append(data)
        return taxes_line

    def _get_total_amount_in_words(self, amount_text):
        """
        Get total amount in words
        :return:
        """
        if amount_text == 'amount_total':
            convert_amount = self.amount_total
        elif amount_text == 'amount_tax':
            convert_amount = self.amount_tax
        else:
            convert_amount = 0

        # total_amount_in_words = self.currency_id.amount_to_text(self.amount_total)
        # {OverflowError}abs(24961380253) must be less than 10000000000.
        # The amount must be less than 10000000000 to convert in words in Indian currency.
        if convert_amount < 10000000000:
            # total_amount_in_words = num2words(self.amount_total, lang='en_IN').title()
            total_amount_in_words = tools.ustr('{amt_value} {amt_word}').format(
                amt_value=num2words(convert_amount, lang='en_IN'),
                amt_word=self.currency_id.currency_unit_label,
            )
        else:
            lang_code = self.env.context.get('lang') or self.env.user.lang
            lang = self.env['res.lang'].search([('code', '=', lang_code)])
            total_amount_in_words = tools.ustr('{amt_value} {amt_word}').format(
                amt_value=num2words(convert_amount, lang=lang.iso_code),
                amt_word=self.currency_id.currency_unit_label,
            )
        return total_amount_in_words
    # Yash - End : Print account invoice pdf report

    @api.onchange('amount_total')
    def _onchange_amount_total(self):
        for inv in self:
            if float_compare(inv.amount_total, 0.0, precision_rounding=inv.currency_id.rounding) == -1:
                raise Warning(_('You cannot validate an invoice with a negative total amount. You should create a credit note instead.'))

    @api.model
    def _default_journal(self):
        if self._context.get('default_journal_id', False):
            return self.env['account.journal'].browse(self._context.get('default_journal_id'))
        inv_type = self._context.get('type', 'out_invoice')
        inv_types = inv_type if isinstance(inv_type, list) else [inv_type]
        company_id = self._context.get('company_id', self.env.user.company_id.id)
        domain = [
            ('type', 'in', [TYPE2JOURNAL[ty] for ty in inv_types if ty in TYPE2JOURNAL]),
            ('company_id', '=', company_id),
        ]
        return self.env['account.journal'].search(domain, limit=1)

    @api.model
    def _default_currency(self):
        journal = self._default_journal()
        return journal.currency_id or journal.company_id.currency_id or self.env.user.company_id.currency_id

    @api.model
    def _get_reference_type(self):
        return [('none', _('Free Reference'))]

    def _get_aml_for_amount_residual(self):
        """ Get the aml to consider to compute the amount residual of invoices """
        self.ensure_one()
        return self.sudo().move_id.line_ids.filtered(lambda l: l.account_id == self.account_id)

    @api.one
    @api.depends(
        'state', 'currency_id', 'invoice_line_ids.price_subtotal',
        'move_id.line_ids.amount_residual',
        'move_id.line_ids.currency_id')
    def _compute_residual(self):
        residual = 0.0
        residual_company_signed = 0.0
        sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
        for line in self._get_aml_for_amount_residual():
            residual_company_signed += line.amount_residual
            if line.currency_id == self.currency_id:
                residual += line.amount_residual_currency if line.currency_id else line.amount_residual
            else:
                if line.currency_id:
                    residual += line.currency_id.with_context(date=line.date).compute(line.amount_residual_currency, self.currency_id)
                else:
                    residual += line.company_id.currency_id.with_context(date=line.date).compute(line.amount_residual, self.currency_id)
        self.residual_company_signed = abs(residual_company_signed) * sign
        self.residual_signed = abs(residual) * sign
        self.residual = abs(residual)
        digits_rounding_precision = self.currency_id.rounding
        if float_is_zero(self.residual, precision_rounding=digits_rounding_precision):
            self.reconciled = True
        else:
            self.reconciled = False

    @api.one
    def _get_outstanding_info_JSON(self):
        self.outstanding_credits_debits_widget = json.dumps(False)
        if self.state == 'open':
            domain = [('account_id', '=', self.account_id.id),
                      ('partner_id', '=', self.env['res.partner']._find_accounting_partner(self.partner_id).id),
                      ('reconciled', '=', False),
                      ('move_id.state', '=', 'posted'),
                      '|',
                        '&', ('amount_residual_currency', '!=', 0.0), ('currency_id','!=', None),
                        '&', ('amount_residual_currency', '=', 0.0), '&', ('currency_id','=', None), ('amount_residual', '!=', 0.0)]
            if self.type in ('out_invoice', 'in_refund'):
                domain.extend([('credit', '>', 0), ('debit', '=', 0)])
                type_payment = _('Outstanding credits')
            else:
                domain.extend([('credit', '=', 0), ('debit', '>', 0)])
                type_payment = _('Outstanding debits')
            info = {'title': '', 'outstanding': True, 'content': [], 'invoice_id': self.id}
            lines = self.env['account.move.line'].search(domain)
            currency_id = self.currency_id
            if len(lines) != 0:
                for line in lines:
                    # get the outstanding residual value in invoice currency
                    if line.currency_id and line.currency_id == self.currency_id:
                        amount_to_show = abs(line.amount_residual_currency)
                    else:
                        amount_to_show = line.company_id.currency_id.with_context(date=line.date).compute(abs(line.amount_residual), self.currency_id)
                    if float_is_zero(amount_to_show, precision_rounding=self.currency_id.rounding):
                        continue
                    if line.ref:
                        title = '%s : %s' % (line.move_id.name, line.ref)
                    else:
                        title = line.move_id.name
                    info['content'].append({
                        'journal_name': line.ref or line.move_id.name,
                        'title': title,
                        'amount': amount_to_show,
                        'currency': currency_id.symbol,
                        'id': line.id,
                        'position': currency_id.position,
                        'digits': [69, self.currency_id.decimal_places],
                    })
                info['title'] = type_payment
                self.outstanding_credits_debits_widget = json.dumps(info)
                self.has_outstanding = True

    @api.model
    def _get_payments_vals(self):
        if not self.payment_move_line_ids:
            return []
        payment_vals = []
        currency_id = self.currency_id
        for payment in self.payment_move_line_ids:
            payment_currency_id = False
            if self.type in ('out_invoice', 'in_refund'):
                amount = sum([p.amount for p in payment.matched_debit_ids if p.debit_move_id in self.move_id.line_ids])
                amount_currency = sum(
                    [p.amount_currency for p in payment.matched_debit_ids if p.debit_move_id in self.move_id.line_ids])
                if payment.matched_debit_ids:
                    payment_currency_id = all([p.currency_id == payment.matched_debit_ids[0].currency_id for p in
                                               payment.matched_debit_ids]) and payment.matched_debit_ids[
                                              0].currency_id or False
            elif self.type in ('in_invoice', 'out_refund'):
                amount = sum(
                    [p.amount for p in payment.matched_credit_ids if p.credit_move_id in self.move_id.line_ids])
                amount_currency = sum([p.amount_currency for p in payment.matched_credit_ids if
                                       p.credit_move_id in self.move_id.line_ids])
                if payment.matched_credit_ids:
                    payment_currency_id = all([p.currency_id == payment.matched_credit_ids[0].currency_id for p in
                                               payment.matched_credit_ids]) and payment.matched_credit_ids[
                                              0].currency_id or False
            # get the payment value in invoice currency
            if payment_currency_id and payment_currency_id == self.currency_id:
                amount_to_show = amount_currency
            else:
                amount_to_show = payment.company_id.currency_id.with_context(date=payment.date).compute(amount,
                                                                                                        self.currency_id)
            if float_is_zero(amount_to_show, precision_rounding=self.currency_id.rounding):
                continue
            payment_ref = payment.move_id.name
            if payment.move_id.ref:
                payment_ref += ' (' + payment.move_id.ref + ')'
            payment_vals.append({
                'name': payment.name,
                'journal_name': payment.journal_id.name,
                'amount': amount_to_show,
                'currency': currency_id.symbol,
                'digits': [69, currency_id.decimal_places],
                'position': currency_id.position,
                'date': payment.date,
                'payment_id': payment.id,
                'account_payment_id': payment.payment_id.id,
                'invoice_id': payment.invoice_id.id,
                'move_id': payment.move_id.id,
                'ref': payment_ref,
            })
        return payment_vals

    @api.one
    @api.depends('payment_move_line_ids.amount_residual')
    def _get_payment_info_JSON(self):
        self.payments_widget = json.dumps(False)
        if self.payment_move_line_ids:
            info = {'title': _('Less Payment'), 'outstanding': False, 'content': self._get_payments_vals()}
            self.payments_widget = json.dumps(info)

    @api.one
    @api.depends('move_id.line_ids.amount_residual')
    def _compute_payments(self):
        payment_lines = set()
        for line in self.move_id.line_ids.filtered(lambda l: l.account_id.id == self.account_id.id):
            payment_lines.update(line.mapped('matched_credit_ids.credit_move_id.id'))
            payment_lines.update(line.mapped('matched_debit_ids.debit_move_id.id'))
        self.payment_move_line_ids = self.env['account.move.line'].browse(list(payment_lines)).sorted()

        # Piyush: code for creating invoices values on 10-07-2020

    @api.multi
    def _prepare_invoice(self, sale_order):
        """
        Prepare the dict of values to create the new invoice for a sales order. This method may be
        overridden to implement custom invoice generation (making sure to call super() to establish
        a clean extension chain).
        """
        self.ensure_one()
        company_id = sale_order.company_id.id
        journal_id = (self.env['account.invoice'].with_context(company_id=company_id or self.env.user.company_id.id)
                      .default_get(['journal_id'])['journal_id'])
        dispatches_list = []
        dispatches = self.env['stock.picking'].search([('sale_id', '=', sale_order.id), ('state', '=', 'bill_pending')])
        for picking in dispatches:
            dispatches_list.append(picking.id)
        if not journal_id:
            raise UserError(_('Please define an accounting sales journal for this company.'))
        # Aman 3/11/2020 Get account_id from account.account table using partner_id
        account_id = self.env['account.account'].search([('partner_id', '=', self.partner_id.id)])
        invoice_vals = {
            'name': sale_order.client_order_ref or '',
            'origin': sale_order.name,
            'type': 'out_invoice',
            # 'account_id': sale_order.partner_invoice_id.property_account_receivable_id.id,
            'account_id': account_id.id,
            'partner_id': sale_order.partner_invoice_id.id,
            'partner_shipping_id': sale_order.partner_shipping_id.id,
            'journal_id': journal_id,
            'currency_id': sale_order.pricelist_id.currency_id.id,
            'comment': sale_order.note,
            'payment_term_id': sale_order.payment_term_id.id,
            'fiscal_position_id': sale_order.fiscal_position_id.id or sale_order.partner_invoice_id.property_account_position_id.id,
            'company_id': company_id,
            'user_id': sale_order.user_id and sale_order.user_id.id,
            'team_id': sale_order.team_id.id,
            'dispatch_ids': [(6, 0, dispatches_list)],
        }
        return invoice_vals

    # avinash:16/09/20 Check product tracking type
    def check_product_tracking(self, tracking_line):
        if tracking_line and tracking_line.product_id.tracking in ['lot', 'serial']:
            return ['lot', 'serial']
        else:
            return 'no tracking'

    # avinash:16/09/20 Prepare lot details customer credit note from dispatch
    def prepare_lot_detail(self, move_line):
        trk_line_list = []
        for lot_line in move_line.move_line_ids:
            if move_line.product_qty > 0.0:
                trk_line_data = (0, False, {
                    'product_id': move_line.product_id and move_line.product_id.id,
                    'product_uom_id': move_line.product_uom and move_line.product_uom.id,
                    'lot_id': lot_line.lot_id and lot_line.lot_id.id,
                    'product_uom_qty': 0.0,
                    'ordered_qty': 0.0,
                    'available_qty_lot': lot_line.available_qty_lot or 0.0,
                    'qty_done': lot_line.qty_done or 0.0,
                })
                trk_line_list.append(trk_line_data)
        return trk_line_list

    #end avinash

    # Piyush: code for creating invoices lines

    @api.multi
    def invoice_line_create(self, so_line):
        """ Create an invoice line. The quantity to invoice can be positive (invoice) or negative (refund).
            :param so_line: sale_order_lines
            :param qty: float quantity to invoice
            :returns recordset of account.invoice.line created
        """
        # invoice_lines = self.env['account.invoice.line']
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        # Aman 12/12/2020 Get partner's shipping_id to get account_id
        shipping_partner = self.sale_id.partner_shipping_id
        for line in so_line:
            # if not float_is_zero(qty, precision_digits=precision):
            vals = self._prepare_invoice_line(so_line, shipping_partner)
            # vals.update({'sale_line_ids': [(6, 0, [line.id])]})
            return vals
        # Aman end

    # Piyush: code for preparing invoice lines on 09-07-2020
    # P: changed the qty fields value on 12-08-2020

    @api.multi
    def _prepare_invoice_line(self, so_line, shipping_partner=False):
        """
        Prepare the dict of values to create the new invoice line for a sales order line.

        :param qty: float quantity to invoice
        """
        self.ensure_one()
        res = {}
        product = so_line.product_id.with_context(force_company=so_line.company_id.id)
        # Aman 2/9/2020 added type which will get the current type of invoice, then call get_invoice_line_account1
        # function to get account from product form
        # account = product.property_account_income_id or product.categ_id.property_account_income_categ_id
        type = self.type
        invoice_line = self.env['account.invoice.line']
        account = invoice_line.get_invoice_line_account1(type, product, self.partner_id, self.company_id, shipping_partner, so_line) or invoice_line.with_context({'journal_id': self.journal_id.id, 'type': 'in_invoice'})._default_account()
        # Aman end
        if not account:
            raise UserError(
                _('Please define income account for this product: "%s" (id:%d) - or for its category: "%s".') %
                (so_line.product_id.name, so_line.product_id.id, so_line.product_id.categ_id.name))

        sale_order_lines = [line.id for line in so_line]
        fpos = so_line.order_id.fiscal_position_id or so_line.order_id.partner_id.property_account_position_id
        if fpos:
            account = fpos.map_account(account)
        # salman add hsn_id
        res = {
            'name': so_line.name,
            'hsn_id':so_line.hsn_id,
            'sequence': so_line.sequence,
            'origin': so_line.order_id.name,
            'account_id': account,
            'price_unit': so_line.price_unit,
            'quantity': so_line.to_invoice_qty or 0.0,
            'freeze_qty': True,
            'discount': so_line.discount,
            'uom_id': so_line.product_uom.id,
            'product_id': so_line.product_id.id or False,
            'layout_category_id': so_line.layout_category_id and so_line.layout_category_id.id or False,
            'invoice_line_tax_ids': [(6, 0, so_line.tax_id.ids)],
            'account_analytic_id': so_line.order_id.analytic_account_id.id,
            'analytic_tag_ids': [(6, 0, so_line.analytic_tag_ids.ids)],
            # 'sale_line_ids': [6, 0, sale_order_lines]
        }
        # avinash:16/09/20 Added lot detail when invoice created from dispatch.
        tract_type = self.check_product_tracking(so_line)
        if tract_type == ['lot', 'serial']:
            for ml in self.dispatch_ids.move_lines:
                if ml.product_id.id == so_line.product_id.id:
                    lot_details = self.prepare_lot_detail(ml)
                    res.update({'lot_idss': [lot for lot in lot_details]})
        # end avinash
        return res

    # code ends here

    # Piyush: code for giving values to the invoices on 10-07-2020
    @api.multi
    def invoice_values_assigned(self, inv_data):
        self.partner_shipping_id = inv_data['partner_shipping_id']
        self.name = inv_data['name']
        self.account_id = inv_data['account_id']
        self.type = inv_data['type']
        self.journal_id = inv_data['journal_id']
        self.payment_term_id = inv_data['payment_term_id']
        self.team_id = inv_data['team_id']
        self.dispatch_ids = inv_data['dispatch_ids']
        self.user_id = inv_data['user_id']
        self.comment = inv_data['comment']
        self.company_id = inv_data['company_id']
        self.origin = inv_data['origin']
        self.partner_id = inv_data['partner_id']
        self.currency_id = inv_data['currency_id']
        self.fiscal_position_id = inv_data['fiscal_position_id']

    # code ends here

    # Piyush: code for domain on sale order based on partner on 03-10-2020
    @api.onchange('partner_shipping_id')
    def onchange_partner_id(self):
        sale_ids = []
        for rec in self:
            if rec.partner_shipping_id:
                pending_dispatches = self.env['stock.picking'].search([('partner_id', '=', rec.partner_shipping_id.id),
                                                                       ('state', '=', 'bill_pending')])
                # avinash:04/11/20 Commented and added domain to show only those sale order whose invoice is not created.
                # if pending_dispatches:
                #     for ids in pending_dispatches:
                #         if ids.sale_id:
                #               sale_ids.append(ids.sale_id.id)
                #
                for dispatch in pending_dispatches:
                    invoice = self.env['account.invoice'].search([('dispatch_ids', '=', dispatch.name)])
                    if not invoice and dispatch.sale_id:
                        sale_ids.append(dispatch.sale_id.id)
                # end avinash

            return {'domain': {'sale_id': [('id', '=', sale_ids)]}}
    # Piyush: code for domain on sale order based on partner on 03-10-2020 ends here

    # Piyush: code for onchange_sale_id on 09-07-2020
    @api.onchange('sale_id')
    def onchange_sale_id(self, grouped=False):
        if self.sale_id:
            invoices = {}
            product_list = []
            required_list = []
            self.invoice_line_ids = ''
            is_dispatch = self.env['stock.picking'].search([('sale_id', '=', self.sale_id.id),
                                                            ('state', '=', 'bill_pending')])
            # Piyush: code for allowing only items whose done qty is more than 0 on 05-09-2020
            for item in is_dispatch.move_lines:
                if item.quantity_done > 0:
                    product_list.append(item.product_id.id)  # code ends here
            if is_dispatch:

                already_dispatched = self.env['account.invoice'].search([('dispatch_ids', '=', is_dispatch.id),
                                                                         ('sale_id', '=', self.sale_id.id)])
                if not already_dispatched:
                    for order in self.sale_id:
                        group_key = order.id if grouped else (order.partner_invoice_id.id, order.currency_id.id)
                        if group_key not in invoices:
                            inv_data = self._prepare_invoice(order)
                            self.invoice_values_assigned(inv_data)

                            for line in order.order_line.sorted(key=lambda l: l.qty_to_invoice < 0):
                                print('salman@@@@@@@@@@@@@@@@@', product_list,line,line.product_id.id in product_list)
                                # piyush: for giving product id check to the sale order lines to sent only read data.
                                if line.product_id.id in product_list:
                                    # code ends here
                                    invoice_lines = self.invoice_line_create(line)
                                    lines_list = (0, False, invoice_lines)
                                    to_obtain_qty = lines_list[2]
                                    qty = to_obtain_qty['quantity']
                                    if qty >= 0:
                                        required_list.append(lines_list)

                            # self.invoice_line_ids = required_list
                                # invoice_lines = self.invoice_line_create(line)
                                # lines_list = (0, False, invoice_lines)
                                # to_obtain_qty = lines_list[2]  # checking for qty if = 0 invoice_lines not created
                                # qty = to_obtain_qty['quantity']
                                # if qty > 0:
                                #     required_list.append(lines_list)


                    self.invoice_line_ids = required_list

                else:
                    raise ValidationError(_("Invoice for this dispatch is already created!"))

            else:
                raise ValidationError(_("There is no dispatch related to this sale order in bill pending state! "))
        else:
            self.invoice_line_ids = ''
            self.dispatch_ids = ''

        # Piyush: code for passing domain for dispatches related to particular
        for rec in self:
            return {'domain': {'dispatch_ids': [('sale_id', '=', rec.sale_id.id)]}}
        # code ends here

    # avinash:20/11/20 Vendor bill date cannot be greater than bill date
    @api.onchange('date_invoice')
    def compare_bill_date(self):
        if self.doc_date and self.date_invoice and self.type == 'in_invoice':
            if self.date_invoice > self.doc_date:
                raise ValidationError('Vendor bill date cannot greater then bill date')
    # end avinash

    # avinash:02/12/20 Created so that on customer invoice and sale return form it pick server date and time
    def default_date(self):
        inv_type = self._context.get('type')
        if inv_type in ['out_invoice', 'out_refund']:
            today_date = fields.Date.context_today(self)
            return today_date

    def default_doc_date(self):
        today_date = fields.Date.context_today(self)
        return today_date
    # end avinash

    name = fields.Char(string='Reference/Description', index=True,
                       readonly=True, states={'draft': [('readonly', False)]}, copy=False,
                       help='The name that will be used on account move lines')

    # avinash 18/08/20 Selection field of tax invoice and cash invoice
    invoice = fields.Selection([
        ('tax_invoice', 'Tax Invoice'),
        ('cash_invoice', 'Cash Invoice')], string="Invoice Type", default='tax_invoice')

    # avinash:27/11/20 Commented becasue in 'stock_account/account_invoice.py'. This function is already exist.
    # avinash 18/08/20 Selection field of tax invoice and cash invoice
    # @api.model
    # def _default_picking_type(self):
    #     res = {}
    #     picking_type_code = ''
    #     picking_type_id_name = ''
    #     type_obj = self.env['stock.picking.type']
    #     company_id = self.env.user.company_id.id
    #     if 'default_picking_type_code' in self._context:
    #         picking_type_code = self._context.get('default_picking_type_code')
    #         # print('picking codeeeeeeeeeeeeeeeeeeee', picking_type_code)
    #     if 'default_picking_type_name' in self._context:
    #         picking_type_id_name = self._context.get('default_picking_type_name')
    #         # print('picking codeeeeeeeeeeeeeeeeeeee', picking_type_id_name)
    #     if picking_type_code == 'internal':
    #         if picking_type_id_name == 'issue':
    #             types = type_obj.search([('code', '=', 'internal'), ('name', '=', 'Issue'),
    #                                      ('warehouse_id.company_id', '=', company_id)])
    #             if not types:
    #                 types = type_obj.search(
    #                     [('code', '=', 'internal'), ('name', '=', 'Issue'), ('warehouse_id', '=', False)])
    #         else:
    #             types = type_obj.search([('code', '=', 'internal'), ('warehouse_id.company_id', '=', company_id)])
    #             if not types:
    #                 types = type_obj.search([('code', '=', 'internal'), ('warehouse_id', '=', False)])
    #     elif picking_type_code == 'outgoing':
    #         types = type_obj.search([('code', '=', 'outgoing'), ('warehouse_id.company_id', '=', company_id)])
    #
    #         if not types:
    #             types = type_obj.search([('code', '=', 'outgoing'), ('warehouse_id', '=', False)])
    #     else:
    #         types = type_obj.search([('code', '=', 'incoming'), ('warehouse_id.company_id', '=', company_id)])
    #         if not types:
    #             types = type_obj.search([('code', '=', 'incoming'), ('warehouse_id', '=', False)])
    #
    #     return types[:1]
    #
    #     res = types[:1]
    #     print("typessssssssssssssssssssssssssssssssssssss1 = ", types[:1])
    #     res['domain'] = {'picking_type_id': [('id', 'in', types[:1])]}
    #     return res

    # avinash:27/11/20 Commented becasue in 'stock_account/account_invoice.py'. This field and default function exist so remove default function from
    # here.
    # picking_type_id = fields.Many2one('stock.picking.type', 'Operation Type', default=_default_picking_type)
    picking_type_id = fields.Many2one('stock.picking.type', 'Operation Type')

    # end avinash

    origin = fields.Char(string='Source Document',
                         help="Reference of the document that produced this invoice.",
                         readonly=True, states={'draft': [('readonly', False)]})
    type = fields.Selection([
        ('out_invoice', 'Customer Invoice'),
        ('in_invoice', 'Vendor Bill'),
        ('out_refund', 'Customer Credit Note'),
        ('in_refund', 'Vendor Credit Note'),
    ], readonly=True, index=True, change_default=True,
        default=lambda self: self._context.get('type', 'out_invoice'),
        track_visibility='always')
    access_token = fields.Char(
        'Security Token', copy=False,
        default=_get_default_access_token)

    refund_invoice_id = fields.Many2one('account.invoice', string="Invoice for which this invoice is the credit note")
    number = fields.Char(related='move_id.name', store=True, readonly=True, copy=False)
    move_name = fields.Char(string='Journal Entry Name', readonly=False,
                            default=False, copy=False,
                            help="Technical field holding the number given to the invoice, automatically set when the invoice is validated then stored to set the same number again if the invoice is cancelled, set to draft and re-validated.")
    reference = fields.Char(string='Vendor Reference', copy=False,
                            help="The partner reference of this invoice.", readonly=True,
                            states={'draft': [('readonly', False)]})
    reference_type = fields.Selection('_get_reference_type', string='Payment Reference',
                                      required=True, readonly=True, states={'draft': [('readonly', False)]},
                                      default='none')
    comment = fields.Text('Additional Information', readonly=True, states={'draft': [('readonly', False)]})

    state = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('paid', 'Paid'),
        ('cancel', 'Cancelled'),
    ], string='Status', index=True, readonly=True, default='draft',
        track_visibility='onchange', copy=False,
        help=" * The 'Draft' status is used when a user is encoding a new and unconfirmed Invoice.\n"
             " * The 'Open' status is used when user creates invoice, an invoice number is generated. It stays in the open status till the user pays the invoice.\n"
             " * The 'Paid' status is set automatically when the invoice is paid. Its related journal entries may or may not be reconciled.\n"
             " * The 'Cancelled' status is used when user cancel invoice.")
    sent = fields.Boolean(readonly=True, default=False, copy=False,
                          help="It indicates that the invoice has been sent.")
    # avinash:02/11/20 Commented and added compute field
    # date_invoice = fields.Date(string='Invoice Date', default=fields.Datetime.now,
    #     readonly=True, states={'draft': [('readonly', False)]}, index=True,
    #     help="Keep empty to use the current date", copy=False)

    date_invoice = fields.Date(string='Invoice Date', default=default_date,
                               readonly=True, states={'draft': [('readonly', False)]}, index=True,
                               help="Keep empty to use the current date", copy=False)
    # end avinash
    date_due = fields.Date(string='Due Date',
                           readonly=True, states={'draft': [('readonly', False)]}, index=True, copy=False,
                           help="If you use payment terms, the due date will be computed automatically at the generation "
                                "of accounting entries. The Payment terms may compute several due dates, for example 50% "
                                "now and 50% in one month, but if you want to force a due date, make sure that the payment "
                                "term is not set on the invoice. If you keep the Payment terms and the due date empty, it "
                                "means direct payment.")
    partner_id = fields.Many2one('res.partner', string='Partner', change_default=True,
                                 required=True, readonly=True, states={'draft': [('readonly', False)]},
                                 track_visibility='always', store=True)
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Terms', oldname='payment_term',
                                      readonly=True, states={'draft': [('readonly', False)]},
                                      help="If you use payment terms, the due date will be computed automatically at the generation "
                                           "of accounting entries. If you keep the payment terms and the due date empty, it means direct payment. "
                                           "The payment terms may compute several due dates, for example 50% now, 50% in one month.")
    date = fields.Date(string='Accounting Date',
                       copy=False,
                       help="Keep empty to use the invoice date.",
                       readonly=True, states={'draft': [('readonly', False)]})

    account_id = fields.Many2one('account.account', string='Account',
                                 required=True, readonly=True, states={'draft': [('readonly', False)]},
                                 domain=[('deprecated', '=', False)], help="The partner account used for this invoice.")
    invoice_line_ids = fields.One2many('account.invoice.line', 'invoice_id', string='Invoice Lines',
                                       oldname='invoice_line',
                                       readonly=True, states={'draft': [('readonly', False)]}, copy=True)
    tax_line_ids = fields.One2many('account.invoice.tax', 'invoice_id', string='Tax Lines', oldname='tax_line',
                                   readonly=True, states={'draft': [('readonly', False)]}, copy=True)
    refund_invoice_ids = fields.One2many('account.invoice', 'refund_invoice_id', string='Refund Invoices',
                                         readonly=True)
    move_id = fields.Many2one('account.move', string='Journal Entry',
                              readonly=True, index=True, ondelete='restrict', copy=False,
                              help="Link to the automatically generated Journal Items.")

    amount_untaxed = fields.Monetary(string='Untaxed Amount',
                                     store=True, readonly=True, compute='_compute_amount', track_visibility='always')
    amount_untaxed_signed = fields.Monetary(string='Untaxed Amount in Company Currency',
                                            currency_field='company_currency_id',
                                            store=True, readonly=True, compute='_compute_amount')
    amount_tax = fields.Monetary(string='Tax',
                                 store=True, readonly=True, compute='_compute_amount')
    amount_total = fields.Monetary(string='Total',
                                   store=True, readonly=True, compute='_compute_amount')
    amount_total_signed = fields.Monetary(string='Total in Invoice Currency', currency_field='currency_id',
                                          store=True, readonly=True, compute='_compute_amount',
                                          help="Total amount in the currency of the invoice, negative for credit notes.")
    amount_total_company_signed = fields.Monetary(string='Total in Company Currency',
                                                  currency_field='company_currency_id',
                                                  store=True, readonly=True, compute='_compute_amount',
                                                  help="Total amount in the currency of the company, negative for credit notes.")
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  required=True, readonly=True, states={'draft': [('readonly', False)]},
                                  default=_default_currency, track_visibility='always')
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string="Company Currency",
                                          readonly=True)
    # avinash 02/11/20 Commented and added condition for sale return and purchase return.
    # avinash 18/08/20 Commented becasue need to show journal type cash also. So modify it.
    # journal_id = fields.Many2one('account.journal', string='Journal',
    #     required=True, readonly=True, states={'draft': [('readonly', False)]},
    #     default=_default_journal,
    #     domain="[('type', 'in', {'out_invoice': ['sale'], 'out_refund': ['sale'], 'in_refund': ['purchase'], 'in_invoice': ['purchase']}.get(type, [])), ('company_id', '=', company_id)]")
    # journal_id = fields.Many2one('account.journal', string='Journal',
    #                              required=True, readonly=True, states={'draft': [('readonly', False)]},
    #                              default=_default_journal,
    #                              domain="[('type', 'in', {'out_invoice': ['sale'], 'out_refund': ['sale']}.get(type, [])),('company_id', '=', company_id)]")

    journal_id = fields.Many2one('account.journal', string='Journal',
        required=True, readonly=True, states={'draft': [('readonly', False)]},
        default=_default_journal,
        domain="[('type', 'in', {'out_invoice': ['sale'], 'out_refund': ['credit_note'], 'in_refund': ['debit_note'], 'in_invoice': ['purchase']}.get(type, [])), ('company_id', '=', company_id)]")
    # end avinash
    check_cash_invoice = fields.Boolean("Check Journal Id", store=True, default=False)
    # end avinash
    company_id = fields.Many2one('res.company', string='Company', change_default=True,
                                 required=True, readonly=True, states={'draft': [('readonly', False)]},
                                 default=lambda self: self.env['res.company']._company_default_get('account.invoice'))

    reconciled = fields.Boolean(string='Paid/Reconciled', store=True, readonly=True, compute='_compute_residual',
                                help="It indicates that the invoice has been paid and the journal entry of the invoice has been reconciled with one or several journal entries of payment.")
    partner_bank_id = fields.Many2one('res.partner.bank', string='Bank Account',
                                      help='Bank Account Number to which the invoice will be paid. A Company bank account if this is a Customer Invoice or Vendor Credit Note, otherwise a Partner bank account number.',
                                      readonly=True, states={
            'draft': [('readonly', False)]})  # Default value computed in default_get for out_invoices

    residual = fields.Monetary(string='Amount Due',
                               compute='_compute_residual', store=True, help="Remaining amount due.")
    residual_signed = fields.Monetary(string='Amount Due in Invoice Currency', currency_field='currency_id',
                                      compute='_compute_residual', store=True,
                                      help="Remaining amount due in the currency of the invoice.")
    residual_company_signed = fields.Monetary(string='Amount Due in Company Currency',
                                              currency_field='company_currency_id',
                                              compute='_compute_residual', store=True,
                                              help="Remaining amount due in the currency of the company.")
    payment_ids = fields.Many2many('account.payment', 'account_invoice_payment_rel', 'invoice_id', 'payment_id',
                                   string="Payments", copy=False, readonly=True)
    payment_move_line_ids = fields.Many2many('account.move.line', string='Payment Move Lines',
                                             compute='_compute_payments', store=True)
    user_id = fields.Many2one('res.users', string='Salesperson', track_visibility='onchange',
                              readonly=True, states={'draft': [('readonly', False)]},
                              default=lambda self: self.env.user, copy=False)
    fiscal_position_id = fields.Many2one('account.fiscal.position', string='Fiscal Position', oldname='fiscal_position',
                                         readonly=True, states={'draft': [('readonly', False)]})
    commercial_partner_id = fields.Many2one('res.partner', string='Commercial Entity', compute_sudo=True,
                                            related='partner_id.commercial_partner_id', store=True, readonly=True,
                                            help="The commercial entity that will be used on Journal Entries for this invoice")

    outstanding_credits_debits_widget = fields.Text(compute='_get_outstanding_info_JSON',
                                                    groups="account.group_account_invoice")
    payments_widget = fields.Text(compute='_get_payment_info_JSON', groups="account.group_account_invoice")
    has_outstanding = fields.Boolean(compute='_get_outstanding_info_JSON', groups="account.group_account_invoice")
    cash_rounding_id = fields.Many2one('account.cash.rounding', string='Cash Rounding Method',
                                       readonly=True, states={'draft': [('readonly', False)]},
                                       help='Defines the smallest coinage of the currency that can be used to pay by cash.')

    # fields use to set the sequence, on the first invoice of the journal
    sequence_number_next = fields.Char(string='Next Number', compute="_get_sequence_number_next",
                                       inverse="_set_sequence_next")
    sequence_number_next_prefix = fields.Char(string='Next Number', compute="_get_sequence_prefix")

    _sql_constraints = [
        ('number_uniq', 'unique(number, company_id, journal_id, type)', 'Invoice Number must be unique per Company!'),
    ]

    # Piyush: code for adding new field sale order in account invoice on 09-07-2020
    freeze_account_item_lines = fields.Boolean(string="freeze account item lines", default=False, store=True)
    sale_id = fields.Many2one('sale.order', string="Sale Order")
    dispatch_ids = fields.Many2many('stock.picking', 'sale_picking_rel', 'invoice_id', 'dispatch_id',
                                    string="Related Dispatches")
    # dispatch_ids = fields.Many2many('stock.picking', 'sale_picking_rel', 'invoice_id', 'id',
    #                                 string="Related Dispatches")
    # code ends here

    # Gaurav 14/3/20 add default check on company gst register
    check_registered = fields.Boolean("Check Registered", store=True, default=False)
    check_invoice_line = fields.Boolean("Check Order Line", store=True, default=False)

    # avinash:20/11/20 Added date field on vendor bill and purchase return form
    # doc_date = fields.Date(default=fields.Datetime.now)
    doc_date = fields.Date(default=default_doc_date)
    # end avinash

    order_calculation_ids = fields.One2many('order.calculation.invoice', 'invoice_id',
                                            'Order Calculation Invoice', compute='_compute_lines', store=True)
    # Himanshu SO 2-12-2020 added the address field and gst field to show the address and gst of the customer
    Address = fields.Text(readonly=True)
    gstin = fields.Char(string="GSTIN")

    # End Himanshu
    # Himanshu SO 2-12-2020 function added to add the address related to the customer
    @api.onchange('partner_id')
    def call_add_delivery_address(self):
        sale_ext_inv_adj.SaleQuotation.add_delivery_address(self)
    #end Himanshu

    # @api.multi
    # @api.onchange('invoice_line_ids')
    # def onchange_order_l(self):
    @api.depends('invoice_line_ids', 'invoice_line_ids.invoice_line_tax_ids')
    def _compute_lines(self):
        tax_dict = {}
        tax = {}
        amt = 0
        bamt = 0
        round_amt = 0
        if self.invoice_line_ids:
            for line in self.invoice_line_ids:
                tax_dict = genric.check_line(line, line.invoice_line_tax_ids, line.invoice_id.currency_id,
                                             line.invoice_id.partner_id,
                                             line.quantity)
                tax = Counter(tax_dict) + Counter(tax)
                # Aman 24/11/2020 Calculated discounted amount to show on table
                if line.product_id:
                    price = line.quantity * line.price_unit
                    if line.discount:
                        amt += price * (line.discount / 100)
                    bamt += price
                else:
                    round_amt += line.price_total
                # Aman end
        charges_data_list = genric.detail_table(self, self.invoice_line_ids, tax, amt, bamt, round_amt)
        self.order_calculation_ids = [(5, 0, 0)]
        self.order_calculation_ids = charges_data_list

    # Gaurav 18/3/20 starts for readonly of customer if there is data in order line
    # @api.onchange('invoice_line_ids')
    # def _onchange_invoice_line(self):
    #     print("something happened on order line")
    #     print("There is no line in order line")
    #     self.check_invoice_line = False
    #     for line in self.invoice_line_ids:
    #         if line:
    #             print("There is line in order line")
    #             self.check_invoice_line = True

    # Gaurav end



    def _get_seq_number_next_stuff(self):
        self.ensure_one()
        journal_sequence = self.journal_id.sequence_id
        if self.journal_id.refund_sequence:
            domain = [('type', '=', self.type)]
            journal_sequence = self.type in ['in_refund',
                                             'out_refund'] and self.journal_id.refund_sequence_id or self.journal_id.sequence_id
        elif self.type in ['in_invoice', 'in_refund']:
            domain = [('type', 'in', ['in_invoice', 'in_refund'])]
        else:
            domain = [('type', 'in', ['out_invoice', 'out_refund'])]
        if self.id:
            domain += [('id', '<>', self.id)]
        domain += [('journal_id', '=', self.journal_id.id), ('state', 'not in', ['draft', 'cancel'])]
        return journal_sequence, domain

    def _compute_portal_url(self):
        super(AccountInvoice, self)._compute_portal_url()
        for order in self:
            order.portal_url = '/my/invoices/%s' % (order.id)

    @api.depends('state', 'journal_id', 'date', 'date_invoice')
    def _get_sequence_prefix(self):
        """ computes the prefix of the number that will be assigned to the first invoice/bill/refund of a journal, in order to
        let the user manually change it.
        """
        if not self.env.user._is_system():
            for invoice in self:
                invoice.sequence_number_next_prefix = False
                invoice.sequence_number_next = ''
            return
        for invoice in self:
            journal_sequence, domain = invoice._get_seq_number_next_stuff()
            sequence_date = invoice.date or invoice.date_invoice
            if (invoice.state == 'draft') and not self.search(domain, limit=1):
                prefix, dummy = journal_sequence.with_context(ir_sequence_date=sequence_date,
                                                              ir_sequence_date_range=sequence_date)._get_prefix_suffix()
                invoice.sequence_number_next_prefix = prefix
            else:
                invoice.sequence_number_next_prefix = False

    @api.depends('state', 'journal_id')
    def _get_sequence_number_next(self):
        """ computes the number that will be assigned to the first invoice/bill/refund of a journal, in order to
        let the user manually change it.
        """
        for invoice in self:
            journal_sequence, domain = invoice._get_seq_number_next_stuff()
            if (invoice.state == 'draft') and not self.search(domain, limit=1):
                sequence_date = invoice.date or invoice.date_invoice
                number_next = journal_sequence._get_current_sequence(sequence_date=sequence_date).number_next_actual
                invoice.sequence_number_next = '%%0%sd' % journal_sequence.padding % number_next
            else:
                invoice.sequence_number_next = ''

    @api.multi
    def _set_sequence_next(self):
        ''' Set the number_next on the sequence related to the invoice/bill/refund'''
        self.ensure_one()
        journal_sequence, domain = self._get_seq_number_next_stuff()
        if not self.env.user._is_admin() or not self.sequence_number_next or self.search_count(domain):
            return
        nxt = re.sub("[^0-9]", '', self.sequence_number_next)
        result = re.match("(0*)([0-9]+)", nxt)
        if result and journal_sequence:
            # use _get_current_sequence to manage the date range sequences
            sequence_date = self.date or self.date_invoice
            sequence = journal_sequence._get_current_sequence(sequence_date=sequence_date)
            sequence.number_next = int(result.group(2))

    @api.multi
    def _get_printed_report_name(self):
        self.ensure_one()
        return  self.type == 'out_invoice' and self.state == 'draft' and _('Draft Invoice') or \
                self.type == 'out_invoice' and self.state in ('open','paid') and _('Invoice - %s') % (self.number) or \
                self.type == 'out_refund' and self.state == 'draft' and _('Credit Note') or \
                self.type == 'out_refund' and _('Credit Note - %s') % (self.number) or \
                self.type == 'in_invoice' and self.state == 'draft' and _('Vendor Bill') or \
                self.type == 'in_invoice' and self.state in ('open','paid') and _('Vendor Bill - %s') % (self.number) or \
                self.type == 'in_refund' and self.state == 'draft' and _('Vendor Credit Note') or \
                self.type == 'in_refund' and _('Vendor Credit Note - %s') % (self.number)

    @api.model
    def create(self, vals):
        if not vals.get('journal_id') and vals.get('type'):
            vals['journal_id'] = self.with_context(type=vals.get('type'))._default_journal().id

        onchanges = {
            '_onchange_partner_id': ['account_id', 'payment_term_id', 'fiscal_position_id', 'partner_bank_id'],
            '_onchange_journal_id': ['currency_id'],
        }
        for onchange_method, changed_fields in onchanges.items():
            if any(f not in vals for f in changed_fields):
                invoice = self.new(vals)
                getattr(invoice, onchange_method)()
                for field in changed_fields:
                    if field not in vals and invoice[field]:
                        vals[field] = invoice._fields[field].convert_to_write(invoice[field], invoice)
        if not vals.get('account_id', False):
            raise UserError(_(
                'Configuration error!\nCould not find any account to create the invoice, are you sure you have a chart of account installed?'))

        # avinash :20/08/20 To check if cash invoice setting is checked or not
        if self.invoice == 'cash_invoice' and self.setting_cash_invoice == False:
            raise ValidationError('Cash invoice setting is not active.')
        # end avinash

        invoice = super(AccountInvoice, self.with_context(mail_create_nolog=True)).create(vals)

        if any(line.invoice_line_tax_ids for line in invoice.invoice_line_ids) and not invoice.tax_line_ids:
            invoice.compute_taxes()

        return invoice

    @api.multi
    def _write(self, vals):
        pre_not_reconciled = self.filtered(lambda invoice: not invoice.reconciled)
        pre_reconciled = self - pre_not_reconciled

        # avinash :20/08/20 To check if cash invoice setting is checked or not
        for inv in self:
            if inv.invoice == 'cash_invoice' and inv.setting_cash_invoice == False:
                raise ValidationError('Cash invoice setting is not active.')
        # end avinash

        res = super(AccountInvoice, self)._write(vals)
        reconciled = self.filtered(lambda invoice: invoice.reconciled)
        not_reconciled = self - reconciled
        (reconciled & pre_reconciled).filtered(lambda invoice: invoice.state == 'open').action_invoice_paid()
        (not_reconciled & pre_not_reconciled).filtered(lambda invoice: invoice.state == 'paid').action_invoice_re_open()
        return res

    @api.model
    # def default_get(self,default_fields):
    def default_get(self, fields):
        """ Compute default partner_bank_id field for 'out_invoice' type,
        using the default values computed for the other fields.
        """
        # check_type_cv= self._context.get('type', 'out_invoice')
        check_type_cv = self._context.get('type')
        res = super(AccountInvoice, self).default_get(fields)
        # Gaurav 14/3/20 add default check on company gst register
        if not self.env.user.company_id.vat:
            # if GST not present, company unregistered
            if 'check_registered' in fields:
                # set tax field invisible
                if check_type_cv == 'out_invoice':
                    # if type is sale hide taxes
                    res['check_registered'] = True
                else:
                    # if type is purchase show taxes
                    res['check_registered'] = False
        # Gaurav end
        if res.get('type', False) not in ('out_invoice', 'in_refund') or not 'company_id' in res:
            return res

        partner_bank_result = self._get_partner_bank_id(res['company_id'])
        if partner_bank_result:
            res['partner_bank_id'] = partner_bank_result.id
        return res

    def _get_partner_bank_id(self, company_id):
        company = self.env['res.company'].browse(company_id)
        if company.partner_id:
            return self.env['res.partner.bank'].search([('partner_id', '=', company.partner_id.id)], limit=1)

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        def get_view_id(xid, name):
            try:
                return self.env.ref('account.' + xid)
            except ValueError:
                view = self.env['ir.ui.view'].search([('name', '=', name)], limit=1)
                if not view:
                    return False
                return view.id

        context = self._context
        if context.get('active_model') == 'res.partner' and context.get('active_ids'):
            partner = self.env['res.partner'].browse(context['active_ids'])[0]
            if not view_type:
                view_id = get_view_id('invoice_tree', 'account.invoice.tree')
                view_type = 'tree'
            elif view_type == 'form':
                if partner.supplier and not partner.customer:
                    view_id = get_view_id('invoice_supplier_form', 'account.invoice.supplier.form').id
                elif partner.customer and not partner.supplier:
                    view_id = get_view_id('invoice_form', 'account.invoice.form').id
        return super(AccountInvoice, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar,
                                                           submenu=submenu)

    @api.model_cr_context
    def _init_column(self, column_name):
        """ Initialize the value of the given column for existing rows.

            Overridden here because we need to generate different access tokens
            and by default _init_column calls the default method once and applies
            it for every record.
        """
        if column_name != 'access_token':
            super(AccountInvoice, self)._init_column(column_name)
        else:
            query = """UPDATE %(table_name)s
                          SET %(column_name)s = md5(md5(random()::varchar || id::varchar) || clock_timestamp()::varchar)::uuid::varchar
                        WHERE %(column_name)s IS NULL
                    """ % {'table_name': self._table, 'column_name': column_name}
            self.env.cr.execute(query)

    def _generate_access_token(self):
        for invoice in self:
            invoice.access_token = self._get_default_access_token()

    @api.multi
    def invoice_print(self):
        """ Print the invoice and mark it as sent, so that we can see more
            easily the next step of the workflow
        """
        self.ensure_one()
        self.sent = True
        if self.user_has_groups('account.group_account_invoice'):
            return self.env.ref('account.account_invoices').report_action(self)
        else:
            return self.env.ref('account.account_invoices_without_payment').report_action(self)

    @api.multi
    def action_invoice_sent(self):
        """ Open a window to compose an email, with the edi invoice template
            message loaded by default
        """
        self.ensure_one()
        template = self.env.ref('account.email_template_edi_invoice', False)
        compose_form = self.env.ref('mail.email_compose_message_wizard_form', False)
        ctx = dict(
            default_model='account.invoice',
            default_res_id=self.id,
            default_use_template=bool(template),
            default_template_id=template and template.id or False,
            default_composition_mode='comment',
            mark_invoice_as_sent=True,
            custom_layout="account.mail_template_data_notification_email_account_invoice",
            force_email=True
        )
        return {
            'name': _('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form.id, 'form')],
            'view_id': compose_form.id,
            'target': 'new',
            'context': ctx,
        }

    @api.multi
    def compute_taxes(self):
        """Function used in other module to compute the taxes on a fresh invoice created (onchanges did not applied)"""
        account_invoice_tax = self.env['account.invoice.tax']
        ctx = dict(self._context)
        for invoice in self:
            # Delete non-manual tax lines
            self._cr.execute("DELETE FROM account_invoice_tax WHERE invoice_id=%s AND manual is False", (invoice.id,))
            if self._cr.rowcount:
                self.invalidate_cache()

            # Generate one tax line per tax, however many invoice lines it's applied to
            tax_grouped = invoice.get_taxes_values()

            # Create new tax lines
            for tax in tax_grouped.values():
                account_invoice_tax.create(tax)

        # dummy write on self to trigger recomputations
        return self.with_context(ctx).write({'invoice_line_ids': []})

    @api.multi
    def unlink(self):
        for invoice in self:
            if invoice.state not in ('draft', 'cancel'):
                raise UserError(_(
                    'You cannot delete an invoice which is not draft or cancelled. You should create a credit note instead.'))
            elif invoice.move_name:
                raise UserError(_(
                    'You cannot delete an invoice after it has been validated (and received a number). You can set it back to "Draft" state and modify its content, then re-confirm it.'))
        return super(AccountInvoice, self).unlink()


    @api.onchange('invoice_line_ids')
    def _onchange_invoice_line_ids(self):
        # Aman 30/12/2020 Added validations to check if Item without HSN code is last item
        # Aman 08/01/2021 commented the below function
        # genric.check_hsn_disable(self, self.invoice_line_ids)
        # Aman end
        # avinash : 19/08/20 Add this condition to make make lot_id field readonly if product type is no tracking
        for line in self.invoice_line_ids:
            if line and line.product_id.tracking not in ['none']:
                line.check_lot_available = True
            else:
                line.check_lot_available = False
        # end avinash

        taxes_grouped = self.get_taxes_values()
        tax_lines = self.tax_line_ids.filtered('manual')
        for tax in taxes_grouped.values():
            tax_lines += tax_lines.new(tax)
        self.tax_line_ids = tax_lines
        # Gaurav 1/4/30 added for freeze customer if invoice line present
        print("working invoice check")
        self.check_invoice_line = False
        for line in self.invoice_line_ids:
            if line:
                print("There is line in order line")
                self.check_invoice_line = True
        return

    @api.onchange('partner_id', 'company_id')
    def _onchange_partner_id(self):
    #Himanshu COA 15-09-2020 add the chart_of_account associated with a vendor/customer to the account_id field.
        val = self.partner_id.name
        chart_of_account_id = self.env['account.account'].search([('name','=',val)]).id
        self.account_id = chart_of_account_id
        # account_id = False_onchange_product_qty
    #end Himanshu
        payment_term_id = False
        fiscal_position = False
        bank_id = False
        warning = {}
        domain = {}
        company_id = self.company_id.id
        p = self.partner_id if not company_id else self.partner_id.with_context(force_company=company_id)
        type = self.type
        # avinash:20/08/20 If cash invoice is selected then account type should be cash

        # Earlier code
        # if p:
        #     rec_account = p.property_account_receivable_id
        #     pay_account = p.property_account_payable_id

        rec_account = False
        pay_account = False
        # My code
        if p:
            if p.name == 'Cash':
                rec_account = self.env['account.account'].search(
                    [('name', '=', 'Cash'), ('company_id', '=', self.env.user.company_id.id)])
                pay_account = p.property_account_payable_id
            else:
                # Aman 20/10/2020 Added conditions since account was not picking properly
                if self.account_id.internal_type == 'receivable':
                    rec_account = self.account_id
                    pay_account = False
                if self.account_id.internal_type == 'payable':
                    rec_account = False
                    pay_account = self.account_id
                # rec_account = p.property_account_receivable_id
                # pay_account = p.property_account_payable_id

            # end avinash
            if not rec_account and not pay_account:
                action = self.env.ref('account.action_account_config')
                msg = _(
                    'Cannot find a chart of accounts for this company, You should configure it. \nPlease go to Account Configuration.')
                raise RedirectWarning(msg, action.id, _('Go to the configuration panel'))

            if type in ('in_invoice', 'in_refund'):
                # account_id = pay_account.id
                payment_term_id = p.property_supplier_payment_term_id.id
            else:
                # account_id = rec_account.id
                payment_term_id = p.property_payment_term_id.id

            delivery_partner_id = self.get_delivery_partner_id()
            fiscal_position = self.env['account.fiscal.position'].get_fiscal_position(self.partner_id.id,
                                                                                      delivery_id=delivery_partner_id)

            # If partner has no warning, check its company
            if p.invoice_warn == 'no-message' and p.parent_id:
                p = p.parent_id
            if p.invoice_warn != 'no-message':
                # Block if partner only has warning but parent company is blocked
                if p.invoice_warn != 'block' and p.parent_id and p.parent_id.invoice_warn == 'block':
                    p = p.parent_id
                warning = {
                    'title': _("Warning for %s") % p.name,
                    'message': p.invoice_warn_msg
                }
                if p.invoice_warn == 'block':
                    self.partner_id = False
        #Himanshu COA 15-09-2020 commented the code such that account_id value should not be replaced.
        # self.account_id = account_id
        # End Himanshu
        self.payment_term_id = payment_term_id
        self.date_due = False
        self.fiscal_position_id = fiscal_position

        if type in ('in_invoice', 'out_refund'):
            bank_ids = p.commercial_partner_id.bank_ids
            bank_id = bank_ids[0].id if bank_ids else False
            self.partner_bank_id = bank_id
            domain = {'partner_bank_id': [('id', 'in', bank_ids.ids)]}

        res = {}
        if warning:
            res['warning'] = warning
        if domain:
            res['domain'] = domain


        return res

    @api.multi
    def get_delivery_partner_id(self):
        self.ensure_one()
        return self.partner_id.address_get(['delivery'])['delivery']

    # avinash 19/08/20  add condition of partner id i.e.
    # When cash invoice is seleted cash partner is also selected and journal is selected retail
    @api.onchange('invoice')
    def _onchange_invoice(self):
        # print(self.setting_cash_invoice)
        if self.invoice_line_ids:
            raise ValidationError('Please deleted added product in invoice line first')

        elif self.invoice and self.invoice == 'cash_invoice':
            # if self.env.user.company_id.cash_invoice == False:
            if not self.setting_cash_invoice:
                raise ValidationError('Cash invoice setting is not active.')
            else:
                # avinash 28/11/20 Commented and changed condition to 'name = cash customer'
                # self.partner_id = self.env['res.partner'].search(['|', ('name', '=', 'Cash'), ('name', '=', 'cash')])
                partner_id = self.env['res.partner'].search(['|', ('name', '=', 'Cash customer'), ('name', '=', 'Cash Customer')])
                if not partner_id:
                    raise ValidationError('Please create a customer name "Cash customer" or "Cash Customer"')
                else:
                    self.partner_id = partner_id
                # end avinash
                journal_retail = self.env['account.journal'].search(
                    [('type', '=', 'sale'), ('name', '=', 'Retail Invoices'),
                     ('company_id', '=', self.env.user.company_id.id)])
                self.journal_id = journal_retail.id
                self.check_cash_invoice = True

        elif self.invoice and self.invoice == 'tax_invoice':
            self.check_cash_invoice = False

        # avinash: 22/08/20 Return only delivery order of login company
        if self.type == 'out_invoice':
            login_company_delivery = self.env['stock.picking.type'].search(
                [('warehouse_id.company_id', '=', self.env.user.company_id.id), ('name', '=', 'Delivery Orders')])
            res = {
                'domain': {
                    'picking_type_id': [('id', 'in', [c.id for c in login_company_delivery])],
                }
            }
            return res

    setting_cash_invoice = fields.Boolean()


    # end avinash

    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        if self.journal_id:
            self.currency_id = self.journal_id.currency_id.id or self.journal_id.company_id.currency_id.id

    @api.onchange('payment_term_id', 'date_invoice')
    def _onchange_payment_term_date_invoice(self):
        date_invoice = self.date_invoice
        if not date_invoice:
            date_invoice = fields.Date.context_today(self)
        if self.payment_term_id:
            pterm = self.payment_term_id
            pterm_list = pterm.with_context(currency_id=self.company_id.currency_id.id).compute(value=1, date_ref=date_invoice)[0]
            self.date_due = max(line[0] for line in pterm_list)
        elif self.date_due and (date_invoice > self.date_due):
            self.date_due = date_invoice

    @api.onchange('cash_rounding_id', 'invoice_line_ids', 'tax_line_ids')
    def _onchange_cash_rounding(self):
        # Drop previous cash rounding lines
        lines_to_remove = self.invoice_line_ids.filtered(lambda l: l.is_rounding_line)
        if lines_to_remove:
            self.invoice_line_ids -= lines_to_remove

        # Clear previous rounded amounts
        for tax_line in self.tax_line_ids:
            if tax_line.amount_rounding != 0.0:
                tax_line.amount_rounding = 0.0

        if self.cash_rounding_id and self.type in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund'):
            rounding_amount = self.cash_rounding_id.compute_difference(self.currency_id, self.amount_total)
            if not self.currency_id.is_zero(rounding_amount):
                if self.cash_rounding_id.strategy == 'biggest_tax':
                    # Search for the biggest tax line and add the rounding amount to it.
                    # If no tax found, an error will be raised by the _check_cash_rounding method.
                    if not self.tax_line_ids:
                        return
                    biggest_tax_line = None
                    for tax_line in self.tax_line_ids:
                        if not biggest_tax_line or tax_line.amount > biggest_tax_line.amount:
                            biggest_tax_line = tax_line
                    biggest_tax_line.amount_rounding += rounding_amount
                elif self.cash_rounding_id.strategy == 'add_invoice_line':
                    # Create a new invoice line to perform the rounding
                    rounding_line = self.env['account.invoice.line'].new({
                        'name': self.cash_rounding_id.name,
                        'invoice_id': self.id,
                        'account_id': self.cash_rounding_id.account_id.id,
                        'price_unit': rounding_amount,
                        'quantity': 1,
                        'is_rounding_line': True,
                        'sequence': 9999  # always last line
                    })

                    # To be able to call this onchange manually from the tests,
                    # ensure the inverse field is updated on account.invoice.
                    if not rounding_line in self.invoice_line_ids:
                        self.invoice_line_ids += rounding_line

    @api.multi
    def action_invoice_draft(self):
        if self.filtered(lambda inv: inv.state != 'cancel'):
            raise UserError(_("Invoice must be cancelled in order to reset it to draft."))
        # go from canceled state to draft state
        self.write({'state': 'draft', 'date': False})
        # Delete former printed invoice
        try:
            report_invoice = self.env['ir.actions.report']._get_report_from_name('account.report_invoice')
        except IndexError:
            report_invoice = False
        if report_invoice and report_invoice.attachment:
            for invoice in self:
                with invoice.env.do_in_draft():
                    invoice.number, invoice.state = invoice.move_name, 'open'
                    attachment = self.env.ref('account.account_invoices').retrieve_attachment(invoice)
                if attachment:
                    attachment.unlink()
        return True

    # avinash:26/09/20 Commented becasue now created small functions for stock move
    # avinash:19/08/20 Preparing dictionary for stock move
    # @api.multi
    # def _prepare_stock_move_out(self, line, picking):
    #     mov_list = []
    #     variant_id = line.product_id
    #
    #     # code for location_id
    #
    #     location_id_required = ''
    #     if self.picking_type_id.default_location_src_id:
    #         location_id_required = self.picking_type_id.default_location_src_id.id
    #     else:
    #         location_ids = self.env['stock.location'].search(
    #             [('name', '=', 'NewStock'), ('company_id', '=', self.env.user.company_id.id)])
    #         if location_ids:
    #             location_id_required = location_ids.id
    #
    #     # code for destination location
    #
    #     dest_location_id = ''
    #     if self.picking_type_id.default_location_dest_id:
    #         dest_location_id = self.picking_type_id.default_location_dest_id.id
    #     else:
    #         if self.partner_id:
    #             dest_location_id = self.partner_id.property_stock_customer.id
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
    #             'quantity_done': line.quantity or 0.0,
    #             'location_id': location_id_required or False,
    #             'location_dest_id': dest_location_id or False,
    #             'picking_id': picking.id,
    #             'picking_type_id': picking.picking_type_id and picking.picking_type_id.id or False,
    #             'origin': line.product_id and line.product_id.name or '',
    #             'warehouse_id': picking.picking_type_id and picking.picking_type_id.warehouse_id and picking.picking_type_id.warehouse_id.id or False,
    #             'state': 'draft',
    #         }
    #
    #         if line:
    #             trk_line_list = []
    #             ret_qty_total = 0.0
    #             for trk_line in line:
    #                 for lot in trk_line.lot_idss:
    #                     each_lot_id = lot.lot_id.id
    #                 if trk_line.quantity > 0.0:
    #                     trk_line_data = (0, False, {
    #                         'product_id': line.product_id and line.product_id.id or False,
    #                         'product_uom_id': variant_id.uom_id and variant_id.uom_id.id or False,
    #                         'location_dest_id': dest_location_id or False,
    #                         'location_id': location_id_required or False,
    #                         # 'lot_id': trk_line.lot_id and trk_line.lot_id.id or False,
    #                         'lot_id': each_lot_id or False,
    #                         'product_uom_qty': 0.0,
    #                         'ordered_qty': 0.0,
    #                         'qty_done': trk_line.quantity or 0.0,
    #                         'picking_id': picking.id or False,
    #                     })
    #                     trk_line_list.append(trk_line_data)
    #                     ret_qty_total += trk_line.quantity
    #
    #             if trk_line_list:
    #                 res['move_line_ids'] = trk_line_list
    #                 res['product_uom_qty'] = ret_qty_total
    #                 res['quantity_done'] = ret_qty_total
    #                 mov_list.append(res)
    #
    #     if line.product_id.tracking == 'none':
    #         res = {
    #             'product_id': variant_id.id or False,
    #             'name': line.product_id and line.product_id.name or '',
    #             'product_uom': variant_id.uom_id and variant_id.uom_id.id or False,
    #             'product_uom_qty': line.quantity or 0.0,
    #             'quantity_done': line.quantity or 0.0,
    #             'location_id': location_id_required or False,
    #             'location_dest_id': dest_location_id or False,
    #             'picking_id': picking.id,
    #             'picking_type_id': picking.picking_type_id and picking.picking_type_id.id or False,
    #             'origin': line.product_id and line.product_id.name or '',
    #             'warehouse_id': self.picking_type_id.warehouse_id.id or False,
    #             'state': 'draft',
    #         }
    #         mov_list.append(res)
    #
    #     return mov_list
    #
    # def create_stock_move(self):
    #     for lot in self:
    #         print(lot.state)
    #         if lot.state not in ['open', 'paid']:
    #             print("state = ", lot.state)
    #             for line in lot.invoice_line_ids:
    #                 picking = self.env['stock.picking']
    #                 if line.quantity > 0.0:
    #                     res_move = self._prepare_stock_move_out(line, picking)
    #                     if res_move:
    #                         for val in res_move:
    #                             self.env['stock.move'].create(val)._action_confirm()._action_done()

        # end avinash

    # avinash: 26/09/20 Prepare dictionary for picking
    @api.model
    def _prepare_picking(self):
        location_id, location_dest_id = self.fetch_location_ids(self.picking_type_id)
        res = {
            'name': self.number,
            'picking_type_id': self.picking_type_id.id,
            'partner_id': self.partner_id.id,
            'date': self.date_invoice,
            'origin': self.name,
            'location_dest_id': location_dest_id,
            'location_id': location_id,
            'company_id': self.company_id.id,
            'delivery_invoice_date': self.date,
            # avinash:21/11/20 Added so that do not show bill on dispatch or receipt
            'from_bill': True
            # end avinash
        }
        if self.picking_type_id.name == "Receipts":
            res['bill_available'] = True

        return res

    # avinash: 02/12/20 Commented and change so it create picking and return picking for each product line
    # avinash: 26/09/20 Create picking for stock move
    # @api.multi
    # def _create_picking(self, product_id):
        # StockPicking = self.env['stock.picking']
        # for rec in self:
        #     if any([ptype in ['product', 'consu'] for ptype in rec.invoice_line_ids.mapped('product_id.type')]):
        #         res = rec._prepare_picking()
        #         picking = StockPicking.create(res)
        # return picking

    @api.multi
    def _create_picking(self, product_id):
        StockPicking = self.env['stock.picking']
        if product_id.type in ['product', 'consu']:
            res = self._prepare_picking()
            picking = StockPicking.create(res)
            return picking
    # end avinash

    # avinash: 26/09/20 Prepare lot detail and create in stock move line
    def create_lot_detail(self, move_line, move_id=False, picking=False):
        lot_detail_list = []
        total_done_qty = 0
        # avinash:30/09/20 This extra for loop is added for customer credit note when created from invoice
        # because in invoice we send 1 product detail but in case of credit note we send all product detail at once (when created from invoice)
        # use to avoid single tone error.
        for product_line in move_line:
        # end
            if product_line.quantity > 0.0:
                for lot_line in product_line.lot_idss:
                    each_lot_id = lot_line.lot_id.id
                    lot_data = {
                        'product_id': product_line.product_id and product_line.product_id.id or False,
                        'product_uom_id': product_line.uom_id and product_line.uom_id.id or False,
                        'location_dest_id': picking and picking.location_dest_id.id or False,
                        'location_id': picking and picking.location_id.id or False,
                        'lot_id': each_lot_id or False,
                        'product_uom_qty': 0.0,
                        'ordered_qty': 0.0,
                        'qty_done': lot_line.qty_done or 0.0,
                    }
                    if move_id:
                        if move_id.move_line_ids[-1] and not move_id.move_line_ids[-1].lot_id:
                            move_id.move_line_ids.write({'qty_done': lot_line.qty_done, 'lot_id': each_lot_id})
                        else:
                            new = move_id.move_line_ids.create(lot_data)
                            new.update({'move_id': move_id.id, 'picking_id': picking.id})

                    total_done_qty += lot_line.qty_done
                    lot_detail_list.append(lot_data)
        return lot_detail_list


    #  avinash: 26/09/20 Preparing product detail for stock move
    def prepare_product_detail(self, line, picking):
        res = {
            'product_id': line.product_id.id or False,
            'name': line.product_id and line.product_id.name or '',
            'product_uom': line.product_id.uom_id and line.product_id.uom_id.id or False,
            'product_uom_qty': line.quantity or 0.0,
            'quantity_done': line.quantity or 0.0,
            'location_id': picking.location_id.id or False,
            'location_dest_id': picking.location_dest_id.id or False,
            'picking_id': picking.id,
            'picking_type_id': picking.picking_type_id and picking.picking_type_id.id or False,
            'origin': line.product_id and line.product_id.name or '',
            'warehouse_id': picking.picking_type_id and picking.picking_type_id.warehouse_id and picking.picking_type_id.warehouse_id.id or False,
            'state': 'draft',
            'product_qty': line.quantity,
            'ordered_qty': line.quantity,
            'price_unit': line.price_unit
        }
        return res

    # avinash: 26/09/20 Calling all the related function for stock move out and return move id
    def create_stock_move(self, line, picking):
        res = self.prepare_product_detail(line, picking)
        move_id = self.env['stock.move'].create(res)
        track_type = self.check_product_tracking(line)

        if track_type == ['lot', 'serial']:
            lot_detail_list = self.create_lot_detail(line, move_id, picking)
        return move_id


    # avinash:19/09/20 Fetching location on the basis of picking type id
    def fetch_location_ids(self, picking_type_id):
        if picking_type_id.name == "Receipts":
            location_id = picking_type_id.default_location_src_id.id or False
            location_dest_id = picking_type_id.default_location_dest_id.id
            if not location_id:
                location_id = self.partner_id.property_stock_supplier.id or False

        elif picking_type_id.name == "Delivery Orders":
            location_id = picking_type_id.default_location_src_id.id or False
            dest_id = self.env['stock.location'].search([('name', '=', 'Customers')])
            location_dest_id = dest_id.id

        # avinash:27/11/20 Fetching location For sale return
        elif picking_type_id.name == "Sales Return":
            location_dest_id = picking_type_id.default_location_dest_id.id or False
            loc_id = self.env['stock.location'].search([('name', '=', 'Customers')])
            location_id = loc_id.id

        # Fetching location For purchase return
        elif picking_type_id.name == "Purchase Return":
            location_id = picking_type_id.default_location_src_id.id or False
            location_dest_id = picking_type_id.default_location_dest_id.id or False
        # end

        else:
            raise ValidationError('No operation type present')

        return location_id, location_dest_id


    # avinash: 19/09/20 Create stock move for customer credit note
    def stock_move(self):
        for rec in self:
            if rec.state not in ['open', 'paid']:
                # avinash:02/12/20 Commented and move below this functionality
                # picking = self._create_picking()
                # end avinash
                for line in rec.invoice_line_ids:
                    # avinash:02/12/20 Also added check for service type product.
                    # avinash:26/11/20 Commented and added condition Only create stock move if product id is available
                    # if line.quantity > 0:
                    if line.quantity > 0 and line.product_id and line.product_id.type != 'service':
                    # end avinash
                        picking = self._create_picking(line.product_id)
                        move_id = self.create_stock_move(line, picking)
                        if move_id:
                            for val in move_id:
                                val._action_confirm()
                                val._action_done()


    @api.multi
    def action_invoice_open(self):
        # avinash: 15/10/20 Added so that same lot cannot be added again. To avoid negative stock
        purchase = self.env['purchase.order']
        purchase.check_lot_detail_repeat(self.invoice_line_ids)
        # end avinash
        # lots of duplicate calls to action_invoice_open, so we remove those already open
        to_open_invoices = self.filtered(lambda inv: inv.state != 'open')
        if to_open_invoices.filtered(lambda inv: inv.state != 'draft'):
            raise UserError(_("Invoice must be in draft state in order to validate it."))
        if to_open_invoices.filtered(
                lambda inv: float_compare(inv.amount_total, 0.0, precision_rounding=inv.currency_id.rounding) == -1):
            raise UserError(_(
                "You cannot validate an invoice with a negative total amount. You should create a credit note instead."))
        to_open_invoices.action_date_assign()
        to_open_invoices.action_move_create()
        # avinash:26/11/20 Bug-id:257 If company is register then hsn code is mandatory
        for line in self.invoice_line_ids:
            if line.product_id and self.env.user.company_id.vat and self.type == 'out_invoice':
                line.check_hsn_code()
        # avinash:02/12/20 Bug-id:257 If vendor is register then hsn code is mandatory
            if line.product_id and self.partner_id.vat and self.type == 'in_invoice':
                line.check_hsn_code()
        # end avinash

        # avinash: 20/08/20 Check if cash invoice is selected then create stock move
        if self.invoice and self.invoice == "cash_invoice":
            # avinash:22/10/20 Added so that we can avoid negative stock
            for line in self.invoice_line_ids:
                line._onchange_product_qty()
            # end avinash
            self.stock_move()

        # avinash: 22/09/20 Stock move for customer credit note
        if self.type == 'out_refund' or self.type == 'in_refund':
            # avinash:22/10/20 Added so that we can avoid negative stock
            if self.type == 'in_refund':
                for line in self.invoice_line_ids:
                    line._onchange_product_qty()
                # end avinash
            self.stock_move()
        # end avinash
        return to_open_invoices.invoice_validate()

    @api.multi
    def action_invoice_paid(self):
        # lots of duplicate calls to action_invoice_paid, so we remove those already paid
        to_pay_invoices = self.filtered(lambda inv: inv.state != 'paid')
        if to_pay_invoices.filtered(lambda inv: inv.state != 'open'):
            raise UserError(_('Invoice must be validated in order to set it to register payment.'))
        if to_pay_invoices.filtered(lambda inv: not inv.reconciled):
            raise UserError(
                _('You cannot pay an invoice which is partially paid. You need to reconcile payment entries first.'))
        return to_pay_invoices.write({'state': 'paid'})

    @api.multi
    def action_invoice_re_open(self):
        if self.filtered(lambda inv: inv.state != 'paid'):
            raise UserError(_('Invoice must be paid in order to set it to register payment.'))
        return self.write({'state': 'open'})

    @api.multi
    def action_invoice_cancel(self):
        if self.filtered(lambda inv: inv.state not in ['draft', 'open']):
            raise UserError(_("Invoice must be in draft or open state in order to be cancelled."))
        return self.action_cancel()

    @api.multi
    def _notification_recipients(self, message, groups):
        groups = super(AccountInvoice, self)._notification_recipients(message, groups)

        for group_name, group_method, group_data in groups:
            if group_name == 'customer':
                continue
            group_data['has_button_access'] = True

        return groups

    @api.multi
    def get_access_action(self, access_uid=None):
        """ Instead of the classic form view, redirect to the online invoice for portal users. """
        self.ensure_one()
        user, record = self.env.user, self
        if access_uid:
            user = self.env['res.users'].sudo().browse(access_uid)
            record = self.sudo(user)

        if user.share or self.env.context.get('force_website'):
            try:
                record.check_access_rule('read')
            except exceptions.AccessError:
                if self.env.context.get('force_website'):
                    return {
                        'type': 'ir.actions.act_url',
                        'url': '/my/invoices/%s' % self.id,
                        'target': 'self',
                        'res_id': self.id,
                    }
                else:
                    pass
            else:
                return {
                    'type': 'ir.actions.act_url',
                    'url': '/my/invoices/%s?access_token=%s' % (self.id, self.access_token),
                    'target': 'self',
                    'res_id': self.id,
                }
        return super(AccountInvoice, self).get_access_action(access_uid)

    def get_mail_url(self):
        return self.get_share_url()

    @api.multi
    def get_formview_id(self, access_uid=None):
        """ Update form view id of action to open the invoice """
        if self.type in ('in_invoice', 'in_refund'):
            return self.env.ref('account.invoice_supplier_form').id
        else:
            return self.env.ref('account.invoice_form').id

    def _prepare_tax_line_vals(self, line, tax):
        """ Prepare values to create an account.invoice.tax line

        The line parameter is an account.invoice.line, and the
        tax parameter is the output of account.tax.compute_all().
        """
        vals = {
            'invoice_id': self.id,
            'name': tax['name'],
            'tax_id': tax['id'],
            'amount': tax['amount'],
            'base': tax['base'],
            'manual': False,
            'sequence': tax['sequence'],
            'account_analytic_id': tax['analytic'] and line.account_analytic_id.id or False,
            'account_id': self.type in ('out_invoice', 'in_invoice') and (tax['account_id'] or line.account_id.id) or (
                        tax['refund_account_id'] or line.account_id.id),
        }

        # If the taxes generate moves on the same financial account as the invoice line,
        # propagate the analytic account from the invoice line to the tax line.
        # This is necessary in situations were (part of) the taxes cannot be reclaimed,
        # to ensure the tax move is allocated to the proper analytic account.
        if not vals.get('account_analytic_id') and line.account_analytic_id and vals[
            'account_id'] == line.account_id.id:
            vals['account_analytic_id'] = line.account_analytic_id.id

        return vals

    @api.multi
    def get_taxes_values(self):
        tax_grouped = {}
        round_curr = self.currency_id.round
        for line in self.invoice_line_ids:
            price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.invoice_line_tax_ids.compute_all(price_unit, self.currency_id, line.quantity, line.product_id,
                                                          self.partner_id)['taxes']
            for tax in taxes:
                val = self._prepare_tax_line_vals(line, tax)
                key = self.env['account.tax'].browse(tax['id']).get_grouping_key(val)

                if key not in tax_grouped:
                    tax_grouped[key] = val
                    tax_grouped[key]['base'] = round_curr(val['base'])
                else:
                    tax_grouped[key]['amount'] += val['amount']
                    tax_grouped[key]['base'] += round_curr(val['base'])
        return tax_grouped

    @api.multi
    def _get_aml_for_register_payment(self):
        """ Get the aml to consider to reconcile in register payment """
        self.ensure_one()
        return self.move_id.line_ids.filtered(
            lambda r: not r.reconciled and r.account_id.internal_type in ('payable', 'receivable'))

    @api.multi
    def register_payment(self, payment_line, writeoff_acc_id=False, writeoff_journal_id=False):
        """ Reconcile payable/receivable lines from the invoice with payment_line """
        line_to_reconcile = self.env['account.move.line']
        for inv in self:
            line_to_reconcile += inv._get_aml_for_register_payment()
        return (line_to_reconcile + payment_line).reconcile(writeoff_acc_id, writeoff_journal_id)

    @api.multi
    def assign_outstanding_credit(self, credit_aml_id):
        self.ensure_one()
        credit_aml = self.env['account.move.line'].browse(credit_aml_id)
        if not credit_aml.currency_id and self.currency_id != self.company_id.currency_id:
            credit_aml.with_context(allow_amount_currency=True, check_move_validity=False).write({
                'amount_currency': self.company_id.currency_id.with_context(date=credit_aml.date).compute(
                    credit_aml.balance, self.currency_id),
                'currency_id': self.currency_id.id})
        if credit_aml.payment_id:
            credit_aml.payment_id.write({'invoice_ids': [(4, self.id, None)]})
        return self.register_payment(credit_aml)

    @api.multi
    def action_date_assign(self):
        for inv in self:
            # Here the onchange will automatically write to the database
            inv._onchange_payment_term_date_invoice()
        return True

    @api.multi
    def finalize_invoice_move_lines(self, move_lines):
        """ finalize_invoice_move_lines(move_lines) -> move_lines

            Hook method to be overridden in additional modules to verify and
            possibly alter the move lines to be created by an invoice, for
            special cases.
            :param move_lines: list of dictionaries with the account.move.lines (as for create())
            :return: the (possibly updated) final move_lines to create for this invoice
        """
        return move_lines

    @api.multi
    def compute_invoice_totals(self, company_currency, invoice_move_lines):
        total = 0
        total_currency = 0
        for line in invoice_move_lines:
            if self.currency_id != company_currency:
                currency = self.currency_id.with_context(
                    date=self._get_currency_rate_date() or fields.Date.context_today(self))
                if not (line.get('currency_id') and line.get('amount_currency')):
                    line['currency_id'] = currency.id
                    line['amount_currency'] = currency.round(line['price'])
                    line['price'] = currency.compute(line['price'], company_currency)
            else:
                line['currency_id'] = False
                line['amount_currency'] = False
                line['price'] = self.currency_id.round(line['price'])
            if self.type in ('out_invoice', 'in_refund'):
                total += line['price']
                total_currency += line['amount_currency'] or line['price']
                line['price'] = - line['price']
            else:
                total -= line['price']
                total_currency -= line['amount_currency'] or line['price']
        return total, total_currency, invoice_move_lines

    @api.model
    def invoice_line_move_line_get(self):
        res = []
        for line in self.invoice_line_ids:
            if line.quantity == 0:
                continue
            tax_ids = []
            for tax in line.invoice_line_tax_ids:
                tax_ids.append((4, tax.id, None))
                for child in tax.children_tax_ids:
                    if child.type_tax_use != 'none':
                        tax_ids.append((4, child.id, None))
            analytic_tag_ids = [(4, analytic_tag.id, None) for analytic_tag in line.analytic_tag_ids]
            # Aman 29/11/2020 changed type from dest to type of invoice to calculate credit and debit values in _convert_prepared_anglosaxon_line()
            move_line_dict = {
                'invl_id': line.id,
                # 'type': 'src',
                'type': self.type,
                'name': line.name.split('\n')[0][:64],
                'price_unit': line.price_unit,
                'quantity': line.quantity,
                'price': line.price_subtotal,
                'account_id': line.account_id.id,
                'product_id': line.product_id.id,
                'uom_id': line.uom_id.id,
                'account_analytic_id': line.account_analytic_id.id,
                'tax_ids': tax_ids,
                'invoice_id': self.id,
                'analytic_tag_ids': analytic_tag_ids
            }
            # Aman end
            res.append(move_line_dict)
        return res

    @api.model
    def tax_line_move_line_get(self):
        res = []
        # keep track of taxes already processed
        done_taxes = []
        # loop the invoice.tax.line in reversal sequence
        for tax_line in sorted(self.tax_line_ids, key=lambda x: -x.sequence):
            if tax_line.amount_total:
                tax = tax_line.tax_id
                if tax.amount_type == "group":
                    for child_tax in tax.children_tax_ids:
                        done_taxes.append(child_tax.id)
                # Aman 29/11/2020 changed type from dest to type of invoice to calculate credit and debit values in _convert_prepared_anglosaxon_line()
                res.append({
                    'invoice_tax_line_id': tax_line.id,
                    'tax_line_id': tax_line.tax_id.id,
                    # 'type': 'tax',
                    'type': self.type,
                    'name': tax_line.name,
                    'price_unit': tax_line.amount_total,
                    'quantity': 1,
                    'price': tax_line.amount_total,
                    'account_id': tax_line.account_id.id,
                    'account_analytic_id': tax_line.account_analytic_id.id,
                    'invoice_id': self.id,
                    'tax_ids': [(6, 0, list(done_taxes))] if done_taxes and tax_line.tax_id.include_base_amount else []
                })
                # Aman end
                done_taxes.append(tax.id)
        return res

    def inv_line_characteristic_hashcode(self, invoice_line):
        """Overridable hashcode generation for invoice lines. Lines having the same hashcode
        will be grouped together if the journal has the 'group line' option. Of course a module
        can add fields to invoice lines that would need to be tested too before merging lines
        or not."""
        return "%s-%s-%s-%s-%s-%s-%s" % (
            invoice_line['account_id'],
            invoice_line.get('tax_ids', 'False'),
            invoice_line.get('tax_line_id', 'False'),
            invoice_line.get('product_id', 'False'),
            invoice_line.get('analytic_account_id', 'False'),
            invoice_line.get('date_maturity', 'False'),
            invoice_line.get('analytic_tag_ids', 'False'),
        )

    def group_lines(self, iml, line):
        """Merge account move lines (and hence analytic lines) if invoice line hashcodes are equals"""
        if self.journal_id.group_invoice_lines:
            line2 = {}
            for x, y, l in line:
                tmp = self.inv_line_characteristic_hashcode(l)
                if tmp in line2:
                    am = line2[tmp]['debit'] - line2[tmp]['credit'] + (l['debit'] - l['credit'])
                    line2[tmp]['debit'] = (am > 0) and am or 0.0
                    line2[tmp]['credit'] = (am < 0) and -am or 0.0
                    line2[tmp]['amount_currency'] += l['amount_currency']
                    line2[tmp]['analytic_line_ids'] += l['analytic_line_ids']
                    qty = l.get('quantity')
                    if qty:
                        line2[tmp]['quantity'] = line2[tmp].get('quantity', 0.0) + qty
                else:
                    line2[tmp] = l
            line = []
            for key, val in line2.items():
                line.append((0, 0, val))
        return line

    @api.multi
    def action_move_create(self):
        """ Creates invoice related analytics and financial move lines """
        account_move = self.env['account.move']

        for inv in self:
            if not inv.journal_id.sequence_id:
                raise UserError(_('Please define sequence on the journal related to this invoice.'))
            if not inv.invoice_line_ids:
                raise UserError(_('Please create some invoice lines.'))
            if inv.move_id:
                continue

            ctx = dict(self._context, lang=inv.partner_id.lang)

            if not inv.date_invoice:
                inv.with_context(ctx).write({'date_invoice': fields.Date.context_today(self)})
            if not inv.date_due:
                inv.with_context(ctx).write({'date_due': inv.date_invoice})
            company_currency = inv.company_id.currency_id

            # create move lines (one per invoice line + eventual taxes and analytic lines)
            iml = inv.invoice_line_move_line_get()
            iml += inv.tax_line_move_line_get()

            diff_currency = inv.currency_id != company_currency
            # create one move line for the total and possibly adjust the other lines amount
            total, total_currency, iml = inv.with_context(ctx).compute_invoice_totals(company_currency, iml)

            name = inv.name or '/'
            if inv.payment_term_id:
                totlines = \
                inv.with_context(ctx).payment_term_id.with_context(currency_id=company_currency.id).compute(total,
                                                                                                            inv.date_invoice)[
                    0]
                res_amount_currency = total_currency
                ctx['date'] = inv._get_currency_rate_date()
                for i, t in enumerate(totlines):
                    if inv.currency_id != company_currency:
                        amount_currency = company_currency.with_context(ctx).compute(t[1], inv.currency_id)
                    else:
                        amount_currency = False

                    # last line: add the diff
                    res_amount_currency -= amount_currency or 0
                    if i + 1 == len(totlines):
                        amount_currency += res_amount_currency

                    iml.append({
                        'type': self.type + '_dest',
                        # 'type': 'dest',
                        'name': name,
                        'price': t[1],
                        'account_id': inv.account_id.id,
                        'date_maturity': t[0],
                        'amount_currency': diff_currency and amount_currency,
                        'currency_id': diff_currency and inv.currency_id.id,
                        'invoice_id': inv.id
                    })
            else:
                # Aman 29/11/2020 changed type from dest to type of invoice to calculate credit and debit values in _convert_prepared_anglosaxon_line()
                iml.append({
                    'type': self.type + '_dest',
                    # 'type': 'dest',
                    'name': name,
                    'price': total,
                    'account_id': inv.account_id.id,
                    'date_maturity': inv.date_due,
                    'amount_currency': diff_currency and total_currency,
                    'currency_id': diff_currency and inv.currency_id.id,
                    'invoice_id': inv.id
                })
                # Aman end
            part = self.env['res.partner']._find_accounting_partner(inv.partner_id)
            line = [(0, 0, self.line_get_convert(l, part.id)) for l in iml]
            line = inv.group_lines(iml, line)

            journal = inv.journal_id.with_context(ctx)
            line = inv.finalize_invoice_move_lines(line)

            # avinash: 28/11/20 Commented and send Bill date on Journal entries form
            # date = inv.date or inv.date_invoice
            if self.type == 'in_invoice' or self.type == 'in_refund':
                date = inv.doc_date
            elif self.type == 'out_invoice' or self.type == 'out_refund':
                date = inv.date_invoice
            # end avinash
            move_vals = {
                'ref': inv.reference,
                'line_ids': line,
                'journal_id': journal.id,
                'date': date,
                'narration': inv.comment,
            }
            ctx['company_id'] = inv.company_id.id
            ctx['invoice'] = inv
            ctx_nolang = ctx.copy()
            ctx_nolang.pop('lang', None)
            move = account_move.with_context(ctx_nolang).create(move_vals)
            # Pass invoice in context in method post: used if you want to get the same
            # account move reference when creating the same invoice after a cancelled one:
            move.post()
            # make the invoice point to that move
            vals = {
                'move_id': move.id,
                'date': date,
                'move_name': move.name,
            }
            inv.with_context(ctx).write(vals)
        return True

    @api.constrains('cash_rounding_id', 'invoice_line_ids', 'tax_line_ids')
    def _check_cash_rounding(self):
        for inv in self:
            if inv.cash_rounding_id:
                rounding_amount = inv.cash_rounding_id.compute_difference(inv.currency_id, inv.amount_total)
                if rounding_amount != 0.0:
                    raise UserError(_('The cash rounding cannot be computed because the difference must '
                                      'be added on the biggest tax found and no tax are specified.\n'
                                      'Please set up a tax or change the cash rounding method.'))

    @api.multi
    def _check_duplicate_supplier_reference(self):
        for invoice in self:
            # refuse to validate a vendor bill/credit note if there already exists one with the same reference for the same partner,
            # because it's probably a double encoding of the same bill/credit note
            if invoice.type in ('in_invoice', 'in_refund') and invoice.reference:
                if self.search([('type', '=', invoice.type), ('reference', '=', invoice.reference),
                                ('company_id', '=', invoice.company_id.id),
                                ('commercial_partner_id', '=', invoice.commercial_partner_id.id),
                                ('id', '!=', invoice.id)]):
                    raise UserError(_(
                        "Duplicated vendor reference detected. You probably encoded twice the same vendor bill/credit note."))

    @api.multi
    def invoice_validate(self):
        for invoice in self.filtered(lambda invoice: invoice.partner_id not in invoice.message_partner_ids):
            invoice.message_subscribe([invoice.partner_id.id])
        self._check_duplicate_supplier_reference()
        return self.write({'state': 'open'})

    @api.model
    def line_get_convert(self, line, part):
        return self.env['product.product']._convert_prepared_anglosaxon_line(line, part)

    @api.multi
    def action_cancel(self):
        moves = self.env['account.move']
        for inv in self:
            if inv.move_id:
                moves += inv.move_id
            if inv.payment_move_line_ids:
                raise UserError(_(
                    'You cannot cancel an invoice which is partially paid. You need to unreconcile related payment entries first.'))

        # First, set the invoices as cancelled and detach the move ids
        self.write({'state': 'cancel', 'move_id': False})
        if moves:
            # second, invalidate the move(s)
            moves.button_cancel()
            # delete the move this invoice was pointing to
            # Note that the corresponding move_lines and move_reconciles
            # will be automatically deleted too
            moves.unlink()
        return True

    ###################

    @api.multi
    def name_get(self):
        TYPES = {
            'out_invoice': _('Invoice'),
            'in_invoice': _('Vendor Bill'),
            'out_refund': _('Credit Note'),
            'in_refund': _('Vendor Credit note'),
        }
        result = []
        for inv in self:
            result.append((inv.id, "%s %s" % (inv.number or TYPES[inv.type], inv.name or '')))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('number', '=', name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()


    @api.model
    def _refund_cleanup_lines(self, lines):
        """ Convert records to dict of values suitable for one2many line creation

            :param recordset lines: records to convert
            :return: list of command tuple for one2many line creation [(0, 0, dict of valueis), ...]
        """
        result = []
        for line in lines:
            values = {}
            for name, field in line._fields.items():
                if name in MAGIC_COLUMNS:
                    continue
                elif field.type == 'many2one':
                    values[name] = line[name].id
                elif field.type not in ['many2many', 'one2many']:
                    values[name] = line[name]
                elif name == 'invoice_line_tax_ids':
                    values[name] = [(6, 0, line[name].ids)]
                elif name == 'analytic_tag_ids':
                    values[name] = [(6, 0, line[name].ids)]
                # avinash: 17/09/20 Add so that we can add lot id in move line
                # and with the help of lot id we add lot detail
                elif name == 'lot_idss':
                    values[name] = [(6, 0, line[name].ids)]

            # Aman 3/09/2020 Added origin_line in dict prepared for credit note from customer invoice
            values['origin_line'] = self.id
            values['date'] = self.date_invoice
            # Aman end

            result.append((0, 0, values))
        return result

    @api.model
    def _refund_tax_lines_account_change(self, lines, taxes_to_change):
        # Let's change the account on tax lines when
        # @param {list} lines: a list of orm commands
        # @param {dict} taxes_to_change
        #   key: tax ID, value: refund account

        if not taxes_to_change:
            return lines

        for line in lines:
            if isinstance(line[2], dict) and line[2]['tax_id'] in taxes_to_change:
                line[2]['account_id'] = taxes_to_change[line[2]['tax_id']]
        return lines

    def _get_refund_common_fields(self):
        return ['partner_id', 'payment_term_id', 'account_id', 'currency_id', 'journal_id']

    @api.model
    def _get_refund_prepare_fields(self):
        return ['name', 'reference', 'comment', 'date_due']

    @api.model
    def _get_refund_modify_read_fields(self):
        read_fields = ['type', 'number', 'invoice_line_ids', 'tax_line_ids',
                       'date', 'partner_insite', 'partner_contact', 'partner_ref']
        return self._get_refund_common_fields() + self._get_refund_prepare_fields() + read_fields

    @api.model
    def _get_refund_copy_fields(self):
        copy_fields = ['company_id', 'user_id', 'fiscal_position_id']
        return self._get_refund_common_fields() + self._get_refund_prepare_fields() + copy_fields

    def _get_currency_rate_date(self):
        return self.date or self.date_invoice

    @api.model
    def _prepare_refund(self, invoice, date_invoice=None, date=None, description=None, journal_id=None):
        """ Prepare the dict of values to create the new credit note from the invoice.
            This method may be overridden to implement custom
            credit note generation (making sure to call super() to establish
            a clean extension chain).

            :param record invoice: invoice as credit note
            :param string date_invoice: credit note creation date from the wizard
            :param integer date: force date from the wizard
            :param string description: description of the credit note from the wizard
            :param integer journal_id: account.journal from the wizard
            :return: dict of value to create() the credit note
        """
        values = {}
        for field in self._get_refund_copy_fields():
            if invoice._fields[field].type == 'many2one':
                values[field] = invoice[field].id
            else:
                values[field] = invoice[field] or False

        values['invoice_line_ids'] = self._refund_cleanup_lines(invoice.invoice_line_ids)

        # avinash:17/09/20 Add lot value in refund
        # print(invoice.invoice_line_ids)
        # values['lot_idss'] = self.prepare_lot_detail_refund(invoice.invoice_line_ids)
        values['lot_idss'] = self.create_lot_detail(invoice.invoice_line_ids)
        # end avinash

        tax_lines = invoice.tax_line_ids
        taxes_to_change = {
            line.tax_id.id: line.tax_id.refund_account_id.id
            for line in tax_lines.filtered(lambda l: l.tax_id.refund_account_id != l.tax_id.account_id)
        }
        cleaned_tax_lines = self._refund_cleanup_lines(tax_lines)
        values['tax_line_ids'] = self._refund_tax_lines_account_change(cleaned_tax_lines, taxes_to_change)

        if journal_id:
            journal = self.env['account.journal'].browse(journal_id)
        elif invoice['type'] == 'in_invoice':
            journal = self.env['account.journal'].search([('type', '=', 'purchase')], limit=1)
        else:
            journal = self.env['account.journal'].search([('type', '=', 'sale')], limit=1)
        values['journal_id'] = journal.id

        values['type'] = TYPE2REFUND[invoice['type']]
        values['date_invoice'] = date_invoice or fields.Date.context_today(invoice)
        values['date_due'] = values['date_invoice']
        values['state'] = 'draft'
        values['number'] = False
        values['origin'] = invoice.number
        values['payment_term_id'] = False
        values['refund_invoice_id'] = invoice.id

        if values['type'] == 'in_refund':
            # avinash: 27/11/20 Commented 'picking_type' and changed operation type so when vendor credit note created from Vendor Bill then operation type is 'Purchase Return'.
            # avinash: 08/10/20 Added so when vendor credit note created from Vendor Bill then operation type is Delivery orders
            # picking_type = self.env['stock.picking.type'].search([('name', '=', 'Delivery Orders')])
            picking_type = self.env['stock.picking.type'].search([('name', '=', 'Purchase Return'),('warehouse_id.company_id', '=',self.env.user.company_id.id)])
            values['picking_type_id'] = picking_type.id
            # avinash: 02/11/20 Added to pass journal id
            journal = self.env['account.journal'].search([('type', '=', 'debit_note')], limit=1)
            values['journal_id'] = journal.id
            # end avinash
            partner_bank_result = self._get_partner_bank_id(values['company_id'])
            if partner_bank_result:
                values['partner_bank_id'] = partner_bank_result.id

        # avinash: 27/11/20 Added so that when sales return is created from customer invoice it passes default 'Operation type': 'Sales Return'.
        if values['type'] == 'out_refund':
            picking_type = self.env['stock.picking.type'].search([('name', '=', 'Sales Return'),('warehouse_id.company_id', '=',self.env.user.company_id.id)])
            values['picking_type_id'] = picking_type.id
            # avinash: 02/11/20 Added to pass journal id
            journal = self.env['account.journal'].search([('type', '=', 'credit_note')], limit=1)
            values['journal_id'] = journal.id
        # end avinash
        if date:
            values['date'] = date
        if description:
            values['name'] = description
        return values

    @api.multi
    @api.returns('self')
    def refund(self, date_invoice=None, date=None, description=None, journal_id=None):
        new_invoices = self.browse()
        for invoice in self:
            # create the new invoice
            values = self._prepare_refund(invoice, date_invoice=date_invoice, date=date,
                                          description=description, journal_id=journal_id)
            refund_invoice = self.create(values)
            invoice_type = {'out_invoice': ('customer invoices credit note'),
                            'in_invoice': ('vendor bill credit note')}
            message = _(
                "This %s has been created from: <a href=# data-oe-model=account.invoice data-oe-id=%d>%s</a>") % (
                      invoice_type[invoice.type], invoice.id, invoice.number)
            refund_invoice.message_post(body=message)
            new_invoices += refund_invoice
        return new_invoices

    def _prepare_payment_vals(self, pay_journal, pay_amount=None, date=None, writeoff_acc=None, communication=None):
        payment_type = self.type in ('out_invoice', 'in_refund') and 'inbound' or 'outbound'
        if payment_type == 'inbound':
            payment_method = self.env.ref('account.account_payment_method_manual_in')
            journal_payment_methods = pay_journal.inbound_payment_method_ids
        else:
            payment_method = self.env.ref('account.account_payment_method_manual_out')
            journal_payment_methods = pay_journal.outbound_payment_method_ids

        if not communication:
            communication = self.type in ('in_invoice', 'in_refund') and self.reference or self.number
            if self.origin:
                communication = '%s (%s)' % (communication, self.origin)

        payment_vals = {
            'invoice_ids': [(6, 0, self.ids)],
            'amount': pay_amount or self.residual,
            'payment_date': date or fields.Date.context_today(self),
            'communication': communication,
            'partner_id': self.partner_id.id,
            'partner_type': self.type in ('out_invoice', 'out_refund') and 'customer' or 'supplier',
            'journal_id': pay_journal.id,
            'payment_type': payment_type,
            'payment_method_id': payment_method.id,
            'payment_difference_handling': writeoff_acc and 'reconcile' or 'open',
            'writeoff_account_id': writeoff_acc and writeoff_acc.id or False,
        }
        return payment_vals

    @api.multi
    def pay_and_reconcile(self, pay_journal, pay_amount=None, date=None, writeoff_acc=None):
        """ Create and post an account.payment for the invoice self, which creates a journal entry that reconciles the invoice.

            :param pay_journal: journal in which the payment entry will be created
            :param pay_amount: amount of the payment to register, defaults to the residual of the invoice
            :param date: payment date, defaults to fields.Date.context_today(self)
            :param writeoff_acc: account in which to create a writeoff if pay_amount < self.residual, so that the invoice is fully paid
        """
        if isinstance(pay_journal, pycompat.integer_types):
            pay_journal = self.env['account.journal'].browse([pay_journal])
        assert len(self) == 1, "Can only pay one invoice at a time."

        payment_vals = self._prepare_payment_vals(pay_journal, pay_amount=pay_amount, date=date,
                                                  writeoff_acc=writeoff_acc)
        payment = self.env['account.payment'].create(payment_vals)
        payment.post()

        return True

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'state' in init_values and self.state == 'paid' and self.type in ('out_invoice', 'out_refund'):
            return 'account.mt_invoice_paid'
        elif 'state' in init_values and self.state == 'open' and self.type in ('out_invoice', 'out_refund'):
            return 'account.mt_invoice_validated'
        elif 'state' in init_values and self.state == 'draft' and self.type in ('out_invoice', 'out_refund'):
            return 'account.mt_invoice_created'
        return super(AccountInvoice, self)._track_subtype(init_values)

    @api.multi
    def _get_tax_amount_by_group(self):
        self.ensure_one()
        currency = self.currency_id or self.company_id.currency_id
        fmt = partial(formatLang, self.with_context(lang=self.partner_id.lang).env, currency_obj=currency)
        res = {}
        for line in self.tax_line_ids:
            res.setdefault(line.tax_id.tax_group_id, {'base': 0.0, 'amount': 0.0})
            res[line.tax_id.tax_group_id]['amount'] += line.amount_total
            res[line.tax_id.tax_group_id]['base'] += line.base
        res = sorted(res.items(), key=lambda l: l[0].sequence)
        res = [(
            r[0].name, r[1]['amount'], r[1]['base'],
            fmt(r[1]['amount']), fmt(r[1]['base']),
        ) for r in res]
        return res


class AccountInvoiceLine(models.Model):
    _name = "account.invoice.line"
    _description = "Invoice Line"
    _order = "invoice_id,sequence,id"

    # avinash:07/11/20 Added so that we can return consumable and service type product on vendor bill and
    # On purchase return form return all products
    @api.onchange('invoice_form_type')
    def product_domain(self):
        if self.invoice_form_type == 'in_invoice':
            res = {
                'domain': {
                    'product_id': [('purchase_ok', '=', True), ('type', '!=', 'product')],
                }
            }
            return res
        elif self.invoice_form_type == 'in_refund':
            res = {
                'domain': {
                    'product_id': [('purchase_ok', '=', True)],
                }
            }
            return res

    # end avinash

    # avinash:22/10/20 Added so that we can avoid negative stock
    @api.onchange('quantity')
    def _onchange_product_qty(self):
        if self.invoice_id.type == 'out_invoice' or self.invoice_id.type == 'in_refund':
            for val in self:
                if val and val.product_id and val.product_id.type =='product' and val.product_id.tracking == 'none' and self.env.user.company_id.default_positive_stock:
                    if val.quantity > val.product_id.qty_available:
                        raise ValidationError(
                            'Cannot issue quantity more than available. For {} available quantity '
                            'is {} '.format(val.product_id.name, val.product_id.qty_available))

    # end avinash

    # Aman 14/10/2020 Added onchange function to get invoice date of invoice selected in against ref no.
    @api.onchange('origin_line')
    def check_date(self):
        date = self.origin_line.date_invoice
        if date:
            self.date = date
    # Aman end

    # Aman 9/10/2020 Added onchange function to check discount
    @api.onchange('discount')
    def check_dis(self):
        genric.check_disct(self)
    # Aman end

    # avinash:27/08/20 Added to update product quantity when product is of type lot

    @api.depends('lot_idss.qty_done')
    def _compute_total_qty(self):
        product_qty = 0.0
        for qty in self:
            if qty.product_id.tracking in ['lot', 'serial'] and qty.lot_idss:
                for item in qty.lot_idss:
                    product_qty += item.qty_done
            qty.quantity = product_qty

    # end avinash

    def _total_qty_set(self):
        quantity = self[0].quantity


    # avinash:27/08/20 For showing lot details

    def action_show_lot_details(self):
        self.ensure_one()
        view = self.env.ref('account.lot_wise_invoice_form')

        return {
            'name': _('Detailed Operations'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.invoice.line',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'res_id': self.id,
        }

    #picking_type_id = fields.Many2one('Operation type', related='invoice_id.picking_type_id')

    # end avinash

    @api.one
    @api.depends('price_unit', 'discount', 'invoice_line_tax_ids', 'quantity',
                 'product_id', 'invoice_id.partner_id', 'invoice_id.currency_id', 'invoice_id.company_id',
                 'invoice_id.date_invoice', 'invoice_id.date')
    def _compute_price(self):
        currency = self.invoice_id and self.invoice_id.currency_id or None
        price = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
        taxes = False
        if self.invoice_line_tax_ids:
            taxes = self.invoice_line_tax_ids.compute_all(price, currency, self.quantity, product=self.product_id,
                                                          partner=self.invoice_id.partner_id)
        self.price_subtotal = price_subtotal_signed = taxes['total_excluded'] if taxes else self.quantity * price
        self.price_total = taxes['total_included'] if taxes else self.price_subtotal
        if self.invoice_id.currency_id and self.invoice_id.currency_id != self.invoice_id.company_id.currency_id:
            price_subtotal_signed = self.invoice_id.currency_id.with_context(
                date=self.invoice_id._get_currency_rate_date()).compute(price_subtotal_signed,
                                                                        self.invoice_id.company_id.currency_id)
        sign = self.invoice_id.type in ['in_refund', 'out_refund'] and -1 or 1
        self.price_subtotal_signed = price_subtotal_signed * sign

    @api.model
    def _default_account(self):
        if self._context.get('journal_id'):
            journal = self.env['account.journal'].browse(self._context.get('journal_id'))
            if self._context.get('type') in ('out_invoice', 'in_refund'):
                return journal.default_credit_account_id.id
            return journal.default_debit_account_id.id

    # avinash:21/08/20 Add dynamic domain for tax_invoice and cash_invoice
    # If tax_invoice is selected then only service and consumable type of product visible
    @api.onchange('tax_invoice')
    def _compute_tax_invoice(self):
        if self.tax_invoice == 'tax_invoice' and self.invoice_id.type == 'out_invoice':
            res = {
                'domain': {
                    'product_id': [('sale_ok', '=', True), ('type', '!=', 'product')],
                }
            }
            return res
        elif self.tax_invoice == 'cash_invoice' and self.invoice_id.type == 'out_invoice':
            res = {
                'domain': {
                    'product_id': [('sale_ok', '=', True)],
                }
            }
            return res

    # end avinash
    # salman add hsn_id field
    hsn_id=fields.Char(string='HSN code')
    # salman end
    name = fields.Text(string='Description', required=True)

    # avinash : 18/08/20 added lot_id to show product lot
    # lot_id = fields.Many2one('stock.production.lot', 'Lot', domain="[('product_id', '=', product_id)]")
    # lot_id = fields.Many2one('account.invoice.lot', 'lot_wise_id')

    # lots_wise_ids = fields.One2many('account.invoice.lot', 'lot_wise_id', string='Lot Wise',store=True)
    lot_idss = fields.One2many('account.invoice.lot', 'lot_wise_id', string='Lot Wise')

    # avinash : 19/08/20 Add field check lot id so on basis of product tracking we can make lot_id field invisible
    check_lot_available = fields.Boolean('Check lot id available', store=True, default=False)

    # end avinash

    # Aman 25/08/2020 Added compute function to get origin and date field to get date of credit note
    origin_line = fields.Many2one('account.invoice', string='Against Ref No.',
                         help="Reference of the document that produced this invoice.", store=True)
    date = fields.Date(string='Date', readonly=False)
    # Aman end

    sequence = fields.Integer(default=10,
                              help="Gives the sequence of this line when displaying the invoice.")
    invoice_id = fields.Many2one('account.invoice', string='Invoice Reference',
                                 ondelete='cascade', index=True)
    invoice_type = fields.Selection(related='invoice_id.type', readonly=True)

    # avinash: 07/11/20 Added so that we can hold invoice type value in this field
    invoice_form_type = fields.Char(readonly=True)
    # end avinash
    uom_id = fields.Many2one('product.uom', string='Unit of Measure',
                             ondelete='set null', index=True, oldname='uos_id')

    # avinash :21/08/20 Add domain for stockable and consumable product when tax invoice is selected else all product

    # product_id = fields.Many2one('product.product', string='Product',
    #     ondelete='restrict', index=True)  domain='_compute_tax_invoice'

    product_id = fields.Many2one('product.product', string='Product', ondelete='restrict', index=True)
    tax_invoice = fields.Char()

    # end avinash
    product_image = fields.Binary('Product Image', related="product_id.image", store=False, readonly=True)
    account_id = fields.Many2one('account.account', string='Account',
                                 required=True, domain=[('deprecated', '=', False)],
                                 default=_default_account,
                                 help="The income or expense account related to the selected product.")
    # Piyush: code for adding new field sale order in account invoice on 09-07-2020
    freeze_qty = fields.Boolean(string="freeze qty", default=False, store=True)
    price_unit = fields.Float(string='Unit Price', required=True, digits=dp.get_precision('Product Price'))
    price_subtotal = fields.Monetary(string='Amount',
                                     store=True, readonly=True, compute='_compute_price',
                                     help="Total amount without taxes")
    price_total = fields.Monetary(string='Amount',
                                  store=True, readonly=True, compute='_compute_price', help="Total amount with taxes")
    price_subtotal_signed = fields.Monetary(string='Amount Signed', currency_field='company_currency_id',
                                            store=True, readonly=True, compute='_compute_price',
                                            help="Total amount in the currency of the company, negative for credit note.")
    quantity = fields.Float(compute='_compute_total_qty', inverse='_total_qty_set', store=True, string='Quantity', digits=dp.get_precision('Product Unit of Measure'),
                            required=True, default=1)
    discount = fields.Float(string='Discount (%)', digits=dp.get_precision('Discount'),
                            default=0.0)
    invoice_line_tax_ids = fields.Many2many('account.tax',
                                            'account_invoice_line_tax', 'invoice_line_id', 'tax_id',
                                            string='Taxes',
                                            domain=[('type_tax_use', '!=', 'none'), '|', ('active', '=', False),
                                                    ('active', '=', True)], oldname='invoice_line_tax_id')
    # invoice_line_tax_ids = fields.Many2many('account.tax',
    #                                         'account_invoice_line_tax', 'invoice_line_id', 'tax_id',
    #                                         string='Taxes',
    #                                          oldname='invoice_line_tax_id')
    # invoice_line_tax_new_ids = fields.Many2many('account.tax',
    #                                         'account_invoice_line_tax_new_test', 'invoice_line_id', 'tax_id',
    #                                         string='Taxes',
    #                                         )

    account_analytic_id = fields.Many2one('account.analytic.account',
                                          string='Analytic Account')
    analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Analytic Tags')
    company_id = fields.Many2one('res.company', string='Company',
                                 related='invoice_id.company_id', store=True, readonly=True, related_sudo=False)
    partner_id = fields.Many2one('res.partner', string='Partner',
                                 related='invoice_id.partner_id', store=True, readonly=True, related_sudo=False)
    currency_id = fields.Many2one('res.currency', related='invoice_id.currency_id', store=True, related_sudo=False)
    company_currency_id = fields.Many2one('res.currency', related='invoice_id.company_currency_id', readonly=True,
                                          related_sudo=False)
    is_rounding_line = fields.Boolean(string='Rounding Line', help='Is a rounding line in case of cash rounding.')

    # Gaurav 13/6/20 added state in lines for status for stock up
    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting', 'Waiting Another Operation'),
        ('confirmed', 'Waiting'),
        ('assigned', 'Ready'),
        ('done', 'Done'),
        # Gaurav 5/6/20 added short close state
        ('short_close', 'Short Close'),
        ('bill_pending', 'Bill Pending'),
        # Gaurav end
        ('cancel', 'Cancelled'),
    ], string='Status')

    # Gaurav end


    # Aman 25/08/2020 Added these functions to get origin and date
    @api.multi
    def _date_count(self):
        for rec in self:
            if rec.invoice_id.date_invoice:
                rec.date = rec.invoice_id.date_invoice
    # Aman end


    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(AccountInvoiceLine, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if self._context.get('type'):
            doc = etree.XML(res['arch'])
            for node in doc.xpath("//field[@name='product_id']"):
                if self._context['type'] in ('in_invoice', 'in_refund'):
                    # Hack to fix the stable version 8.0 -> saas-12
                    # purchase_ok will be moved from purchase to product in master #13271
                    if 'purchase_ok' in self.env['product.template']._fields:
                        node.set('domain', "[('purchase_ok', '=', True)]")
                else:
                    node.set('domain', "[('sale_ok', '=', True)]")
            res['arch'] = etree.tostring(doc, encoding='unicode')
        return res

    # @api.v8
    # def get_invoice_line_account(self, type, product, fpos, company):
    #     accounts = product.product_tmpl_id.get_product_accounts(fpos)
    #     if type in ('out_invoice', 'out_refund'):
    #         return accounts['income']
    #     return accounts['expense']

    # Aman 29/08/2020 This function is called by vendor bill created from PO
    @api.v8
    def get_invoice_line_account1(self, type, product, partner, company, shipping_partner=False, so_line=False, po_line=False):
        if genric.check_vat(self.env.user.company_id.vat):
            tax_percentage = ''
            check_custmr_state = self.env['res.partner'].search(
                [('id', '=', partner.id), ('company_id', '=', self.env.user.company_id.id)])
            if po_line:
                for line in po_line.taxes_id:
                    tax_percentage = line.amount
            if so_line:
                for line in so_line.tax_id:
                    tax_percentage = line.amount
            # Aman 8/12/2020 Created this function to get gst_type to get account_id
            gst_type = self.get_gst_type(check_custmr_state, type, company, shipping_partner)
            res = self.get_account(type, product, gst_type, tax_percentage)
            return res

    @api.v8
    def get_invoice_line_account(self, type, product, fpos, company):
        # Aman 29/8/2020 Added condition to check that company state is same as customer state if true then
        # function related to CGST/SGST will run and if False then function related to IGST will run
        tax_percentage = ''
        if genric.check_vat(self.env.user.company_id.vat) == True:
            check_custmr_state = self.env['res.partner'].search(
                [('id', '=', self.partner_id.id), ('company_id', '=', self.env.user.company_id.id)])
            if self.invoice_line_tax_ids:
                for line in self.invoice_line_tax_ids:
                    tax_percentage = line.amount
            # Aman 8/12/2020 Created this function to get gst_type to get account_id
            gst_type = self.get_gst_type(check_custmr_state, type, company)
            res = self.get_account(type, product, gst_type, tax_percentage)
            return res
        
    # Aman 8/12/2020 Created this function to get gst_type to get account_id
    def get_gst_type(self, check_custmr_state, type, company, shipping_partner=False):
        gst_type = ''
        if type == 'out_invoice' or type == 'out_refund':
            delivery_addr = self.invoice_id.partner_shipping_id.state_id
            if shipping_partner:
                if genric.check_state(company.state_id, shipping_partner.state_id) == True:
                    gst_type = 'CGST'  # Local tax
                else:
                    gst_type = 'IGST'  # Central tax
            elif delivery_addr:
                if genric.check_state(company.state_id, delivery_addr) == True:
                    gst_type = 'CGST'  # Local tax
                else:
                    gst_type = 'IGST'  # Central tax
        else:
            if genric.check_state(company.state_id, check_custmr_state.state_id) == True:
                gst_type = 'CGST'  # Local tax
            else:
                gst_type = 'IGST'  # Central tax
        return gst_type
    # Aman end

    # Aman 1/9/2020 This function is created to get the account for selected product
    def get_account(self, type, product, gst_type, tax_percentage=False):
        account = ''
        if type in ('out_invoice', 'out_refund'):
            account_cust = self.env['customer.tax.line'].search(
                [('tax_group_id', '=', gst_type), ('template_id', '=', product.product_tmpl_id.id), ('tax_percentage', '=', tax_percentage)])
            account = account_cust.income_account
        else:
            account_vend = self.env['vendor.tax.line'].search(
                [('tax_group_id', '=', gst_type), ('template_id', '=', product.product_tmpl_id.id), ('tax_percentage', '=', tax_percentage)])
            account = account_vend.expense_account
        return account or False
    # Aman end

    def _set_currency(self):
        company = self.invoice_id.company_id
        currency = self.invoice_id.currency_id
        if company and currency:
            if company.currency_id != currency:
                self.price_unit = self.price_unit * currency.with_context(
                    dict(self._context or {}, date=self.invoice_id.date_invoice)).rate

    # Gaurav 12/3/20 commented and added code for default tax state wise
    # def _set_taxes(self):
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
    #     self.invoice_line_tax_ids = fp_taxes = self.invoice_id.fiscal_position_id.map_tax(taxes, self.product_id, self.invoice_id.partner_id)
    #
    #
    #     fix_price = self.env['account.tax']._fix_tax_included_price
    #     if self.invoice_id.type in ('in_invoice', 'in_refund'):
    #         prec = self.env['decimal.precision'].precision_get('Product Price')
    #         if not self.price_unit or float_compare(self.price_unit, self.product_id.standard_price, precision_digits=prec) == 0:
    #             self.price_unit = fix_price(self.product_id.standard_price, taxes, fp_taxes)
    #             self._set_currency()
    #     else:
    #         self.price_unit = fix_price(self.product_id.lst_price, taxes, fp_taxes)
    #         self._set_currency()

    # Gaurav 14/3/20 added function for getting shipping id
    # @api.multi
    # def get_delivery_partner_id(self):
    # self.ensure_one()
    # for val in self.partner_id.address_get(['delivery'])['delivery']:
    #     print("delivery val",val)
    # addr = self.pool.get('res.partner').address_get(['delivery'])
    #
    #
    # return addr['delivery']
    # # return val

    def _set_taxes(self):
        """ Used in on_change to set taxes and price."""
        # print ("set account account taxessssssssss")
        # Gaurav 12/3/20 added code for default tax state wise
        check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
        check_custmr_state = self.env['res.partner'].search(
            [('id', '=', self.partner_id.id), ('company_id', '=', self.env.user.company_id.id)])

        if self.invoice_id.type in ('out_invoice', 'out_refund'):
            # Jatin change for taxes to pick from customer_tax_lines on 11-07-2020
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
            taxes = print_tax or self.account_id.tax_ids
            # end Jatin
            # taxes = self.product_id.taxes_id or self.account_id.tax_ids
            account_type = 'sale'
            state_type = self.invoice_id.partner_shipping_id.state_id
            # state_type = check_custmr_state.state_id
        else:
            # Jatin change for taxes to pick from customer_tax_lines on 11-07-2020
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
            taxes = print_tax or self.account_id.tax_ids
            # end Jatin
            # taxes = self.product_id.supplier_taxes_id or self.account_id.tax_ids
            # taxes = self.product_id.supplier_taxes_id or self.account_id.tax_ids or self.product_id.taxes_id
            account_type = 'purchase'
            state_type = check_custmr_state.state_id

        # taxes = self.product_id.taxes_id.filtered(lambda r: not self.company_id or r.company_id == self.company_id)

        # Keep only taxes of the company
        company_id = self.company_id or self.env.user.company_id
        taxes = taxes.filtered(lambda r: r.company_id == company_id)

        taxes_ids_list = taxes.ids
        # print("partner_shipping_id",self.partner_shipping_id, state_type)


        if check_cmpy_state.state_id == state_type:
            print("same all account_type", account_type)
            self.env.cr.execute(
                """ select id from account_tax where active=True and type_tax_use='%s' AND tax_group_id not in (2,3) and company_id='%s'""" % (
                account_type, self.env.user.company_id.id,))
            csgst_taxes = self.env.cr.dictfetchall()
            final = [taxes_ids_list.remove(val.get('id')) for val in csgst_taxes if val.get('id') in taxes_ids_list if
                     csgst_taxes]
            print(" account account finalvvvvvvvvvvvvvvvv", final)

            self.invoice_line_tax_ids = taxes_ids_list

        elif check_cmpy_state.state_id != state_type:
            print("same account_type", account_type)
            self.env.cr.execute(
                """ select id from account_tax where active=True and type_tax_use='%s' AND tax_group_id!=4 and company_id='%s'""" % (
                account_type, self.env.user.company_id.id,))
            igst_taxes = self.env.cr.dictfetchall()
            final = [taxes_ids_list.remove(val.get('id')) for val in igst_taxes if val.get('id') in taxes_ids_list if
                     igst_taxes]
            print(" account account finalvvvvvvvvvvvvvvvv", final)

            self.invoice_line_tax_ids = taxes_ids_list


        # self.invoice_line_tax_ids = fp_taxes = self.invoice_id.fiscal_position_id.map_tax(taxes, self.product_id, self.invoice_id.partner_id)
        fp_taxes = self.invoice_id.fiscal_position_id.map_tax(taxes, self.product_id, self.invoice_id.partner_id)
        # self.invoice_line_tax_ids=[]
        fix_price = self.env['account.tax']._fix_tax_included_price
        if self.invoice_id.type in ('in_invoice', 'in_refund'):
            prec = self.env['decimal.precision'].precision_get('Product Price')
            if not self.price_unit or float_compare(self.price_unit, self.product_id.standard_price,
                                                    precision_digits=prec) == 0:
                self.price_unit = fix_price(self.product_id.standard_price, taxes, fp_taxes)
                # self.price_unit = fix_price(self.product_id.standard_price, taxes)
                self._set_currency()
        else:
            self.price_unit = fix_price(self.product_id.lst_price, taxes, fp_taxes)
            # self.price_unit = fix_price(self.product_id.lst_price, taxes)
            self._set_currency()

        # Gaurav return domain
        return {'domain': {'invoice_line_tax_ids': [taxes_ids_list]}}

    # Gaurav end

    # avinash:26/11/20 Bug-id:257 If company is register then hsn code is mandatory
    def check_hsn_code(self):
        # Aman 23/12/2020 Added condition to check if product's hsn_disable is False
        if not self.product_id.hsn_id and self.product_id.hsn_disable == False:
            raise ValidationError("You need to enter HSN code for {}.".format(self.product_id.name))
    # end avinash

    @api.onchange('product_id')
    def _onchange_product_id(self):
        self.origin_line = False
        self.date = False
        domain = {}
        result = {}
        if not self.invoice_id:
            return

        part = self.invoice_id.partner_id
        fpos = self.invoice_id.fiscal_position_id
        company = self.invoice_id.company_id
        currency = self.invoice_id.currency_id
        type = self.invoice_id.type

        if not part:
            warning = {
                'title': _('Warning!'),
                'message': _('You must first select a partner!'),
            }
            return {'warning': warning}

        if not self.product_id:
            if type not in ('in_invoice', 'in_refund'):
                self.price_unit = 0.0
            domain['uom_id'] = []
        else:
            if part.lang:
                product = self.product_id.with_context(lang=part.lang)
            else:
                product = self.product_id

            self.name = product.partner_ref
            account = self.get_invoice_line_account(type, product, fpos, company)
            if account:
                self.account_id = account.id

            # Gaurav commented _set_taxes function for GST validation and used below with changes in function itself
            # self._set_taxes()

            if self.invoice_id.type in ('in_invoice', 'in_refund'):
                # Aman 28/11/2020 Added description of product on form level
                if product.description:
                    self.name = product.description
                elif product.description_purchase:
                    self.name += '\n' + product.description_purchase
            else:
                # Aman 28/11/2020 Added description of product on form level
                if product.description:
                    self.name = product.description
                elif product.description_sale:
                    self.name += '\n' + product.description_sale

            if not self.uom_id or product.uom_id.category_id.id != self.uom_id.category_id.id:
                self.uom_id = product.uom_id.id
            domain['uom_id'] = [('category_id', '=', product.uom_id.category_id.id)]

            # avinash:03/12/20 Bug-id:257 If vendor is register then hsn code is mandatory
            if self.partner_id.vat and self.invoice_id.type == 'in_invoice':
                self.check_hsn_code()

            # Gaurav 12/3/20 added validation for GST check (if company is unregistered then don't add taxes if registered then add taxes state wise)
            if self.env.user.company_id.vat:
                # avinash:26/11/20 Bug-id:257 If company is register then hsn code is mandatory
                if self.invoice_id.type == 'out_invoice':
                    self.check_hsn_code()
                # end avinash
                # GST present , company registered
                # Gaurav 12/3/20 added code for default tax state wise
                check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
                check_custmr_state = self.env['res.partner'].search(
                    [('id', '=', self.partner_id.id), ('company_id', '=', self.env.user.company_id.id)])
                # checking company state and customer state is same or not
                if check_cmpy_state.state_id == check_custmr_state.state_id:
                    print("func same")
                    # if same states show taxes like CGST SGST GST
                    self.env.cr.execute(
                        """select id from account_tax where active=True and type_tax_use='sale' and tax_group_id!=4 and company_id='%s'""" % (
                        self.env.user.company_id.id,))
                    csgst_taxes = self.env.cr.dictfetchall()
                    print("all account account csgst_taxessssss", csgst_taxes)
                    self._set_taxes()
                    cs_tax_list = []
                    if csgst_taxes:
                        for val in csgst_taxes:
                            tax_detail_idcs = val.get('id')
                            cs_tax_list.append(tax_detail_idcs)
                            print("cs_tax_listttt", cs_tax_list)
                            self.invoice_line_tax_new_ids = cs_tax_list
                            # self.update({'tax_id': [(6, 0, cs_tax_list)]})
                            result = {'domain': {'invoice_line_tax_ids': [('id', 'in', cs_tax_list)]}}

                elif check_cmpy_state.state_id != check_custmr_state.state_id:
                    print("func diff")
                    # if different states show taxes like IGST
                    self.env.cr.execute(
                        """ select id from account_tax where active=True and type_tax_use='sale' and tax_group_id not in (2,3) and company_id='%s'""" % (
                        self.env.user.company_id.id,))
                    igst_taxes = self.env.cr.dictfetchall()
                    self._set_taxes()
                    i_tax_list = []
                    if igst_taxes:
                        for val in igst_taxes:
                            tax_detail_idi = val.get('id')
                            i_tax_list.append(tax_detail_idi)
                            print(" account account i_tax_listtttt", i_tax_list)
                            self.invoice_line_tax_new_ids = i_tax_list

                            result = {'domain': {'invoice_line_tax_ids': [('id', 'in', i_tax_list)]}}

            # Gaurav end

            if company and currency:

                if self.uom_id and self.uom_id.id != product.uom_id.id:
                    self.price_unit = product.uom_id._compute_price(self.price_unit, self.uom_id)
        # return {'domain': domain}
        print("account account return account main", result)
        return result

    # @api.onchange('account_id')
    # def _onchange_account_id(self):
    #     if not self.account_id:
    #         return
    #     if not self.product_id:
    #         fpos = self.invoice_id.fiscal_position_id
    #         self.invoice_line_tax_ids = fpos.map_tax(self.account_id.tax_ids, partner=self.partner_id)
    #     elif not self.price_unit:
    #         self._set_taxes()

    @api.onchange('uom_id')
    def _onchange_uom_id(self):
        warning = {}
        result = {}
        if not self.uom_id:
            self.price_unit = 0.0
        if self.product_id and self.uom_id:
            if self.product_id.uom_id.category_id.id != self.uom_id.category_id.id:
                warning = {
                    'title': _('Warning!'),
                    'message': _(
                        'The selected unit of measure is not compatible with the unit of measure of the product.'),
                }
                self.uom_id = self.product_id.uom_id.id
        if warning:
            result['warning'] = warning
        return result

    def _set_additional_fields(self, invoice):
        """ Some modules, such as Purchase, provide a feature to add automatically pre-filled
            invoice lines. However, these modules might not be aware of extra fields which are
            added by extensions of the accounting module.
            This method is intended to be overridden by these extensions, so that any new field can
            easily be auto-filled as well.
            :param invoice : account.invoice corresponding record
            :rtype line : account.invoice.line record
        """
        pass

    # ---- Gaurav 19/6/20 commented unlink method to overwrite validation only for 0 qty product(stock account)
    @api.multi
    def unlink(self):
        if self.filtered(lambda r: r.invoice_id and r.invoice_id.state != 'draft'):
            raise UserError(_('You can only delete an invoice line if the invoice is in draft state.'))
        return super(AccountInvoiceLine, self).unlink()
    # ------ Gaurav end


class AccountInvoiceTax(models.Model):
    _name = "account.invoice.tax"
    _description = "Invoice Tax"
    _order = 'sequence'

    @api.depends('invoice_id.invoice_line_ids')
    def _compute_base_amount(self):
        tax_grouped = {}
        for invoice in self.mapped('invoice_id'):
            tax_grouped[invoice.id] = invoice.get_taxes_values()
        for tax in self:
            tax.base = 0.0
            if tax.tax_id:
                key = tax.tax_id.get_grouping_key({
                    'tax_id': tax.tax_id.id,
                    'account_id': tax.account_id.id,
                    'account_analytic_id': tax.account_analytic_id.id,
                })
                if tax.invoice_id and key in tax_grouped[tax.invoice_id.id]:
                    tax.base = tax_grouped[tax.invoice_id.id][key]['base']
                else:
                    _logger.warning(
                        'Tax Base Amount not computable probably due to a change in an underlying tax (%s).',
                        tax.tax_id.name)

    invoice_id = fields.Many2one('account.invoice', string='Invoice', ondelete='cascade', index=True)
    name = fields.Char(string='Tax Description', required=True)
    tax_id = fields.Many2one('account.tax', string='Tax', ondelete='restrict')
    account_id = fields.Many2one('account.account', string='Tax Account', required=True,
                                 domain=[('deprecated', '=', False)])
    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic account')
    amount = fields.Monetary()
    amount_rounding = fields.Monetary()
    amount_total = fields.Monetary(string="Amount", compute='_compute_amount_total')
    manual = fields.Boolean(default=True)
    sequence = fields.Integer(help="Gives the sequence order when displaying a list of invoice tax.")
    company_id = fields.Many2one('res.company', string='Company', related='account_id.company_id', store=True,
                                 readonly=True)
    currency_id = fields.Many2one('res.currency', related='invoice_id.currency_id', store=True, readonly=True)
    base = fields.Monetary(string='Base', compute='_compute_base_amount', store=True)

    @api.depends('amount', 'amount_rounding')
    def _compute_amount_total(self):
        for tax_line in self:
            tax_line.amount_total = tax_line.amount + tax_line.amount_rounding


class AccountPaymentTerm(models.Model):
    _name = "account.payment.term"
    _description = "Payment Terms"
    _order = "sequence, id"

    def _default_line_ids(self):
        return [(0, 0, {'value': 'balance', 'value_amount': 0.0, 'sequence': 9, 'days': 0,
                        'option': 'day_after_invoice_date'})]

    name = fields.Char(string='Payment Terms', translate=True, required=True)
    active = fields.Boolean(default=True,
                            help="If the active field is set to False, it will allow you to hide the payment terms without removing it.")
    note = fields.Text(string='Description on the Invoice', translate=True)
    line_ids = fields.One2many('account.payment.term.line', 'payment_id', string='Terms', copy=True,
                               default=_default_line_ids)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    sequence = fields.Integer(required=True, default=10)

    @api.constrains('line_ids')
    @api.one
    def _check_lines(self):
        payment_term_lines = self.line_ids.sorted()
        if payment_term_lines and payment_term_lines[-1].value != 'balance':
            raise ValidationError(_('A Payment Terms should have its last line of type Balance.'))
        lines = self.line_ids.filtered(lambda r: r.value == 'balance')
        if len(lines) > 1:
            raise ValidationError(_('A Payment Terms should have only one line of type Balance.'))

    @api.one
    def compute(self, value, date_ref=False):
        date_ref = date_ref or fields.Date.today()
        amount = value
        sign = value < 0 and -1 or 1
        result = []
        if self.env.context.get('currency_id'):
            currency = self.env['res.currency'].browse(self.env.context['currency_id'])
        else:
            currency = self.env.user.company_id.currency_id
        for line in self.line_ids:
            if line.value == 'fixed':
                amt = sign * currency.round(line.value_amount)
            elif line.value == 'percent':
                amt = currency.round(value * (line.value_amount / 100.0))
            elif line.value == 'balance':
                amt = currency.round(amount)
            if amt:
                next_date = fields.Date.from_string(date_ref)
                if line.option == 'day_after_invoice_date':
                    next_date += relativedelta(days=line.days)
                elif line.option == 'fix_day_following_month':
                    next_first_date = next_date + relativedelta(day=1, months=1)  # Getting 1st of next month
                    next_date = next_first_date + relativedelta(days=line.days - 1)
                elif line.option == 'last_day_following_month':
                    next_date += relativedelta(day=31, months=1)  # Getting last day of next month
                elif line.option == 'last_day_current_month':
                    next_date += relativedelta(day=31, months=0)  # Getting last day of next month
                result.append((fields.Date.to_string(next_date), amt))
                amount -= amt
        amount = sum(amt for _, amt in result)
        dist = currency.round(value - amount)
        if dist:
            last_date = result and result[-1][0] or fields.Date.today()
            result.append((last_date, dist))
        return result

    @api.multi
    def unlink(self):
        property_recs = self.env['ir.property'].search(
            [('value_reference', 'in', ['account.payment.term,%s' % payment_term.id for payment_term in self])])
        property_recs.unlink()
        return super(AccountPaymentTerm, self).unlink()


class AccountPaymentTermLine(models.Model):
    _name = "account.payment.term.line"
    _description = "Payment Terms Line"
    _order = "sequence, id"

    value = fields.Selection([
        ('balance', 'Balance'),
        ('percent', 'Percent'),
        ('fixed', 'Fixed Amount')
    ], string='Type', required=True, default='balance',
        help="Select here the kind of valuation related to this payment terms line.")
    value_amount = fields.Float(string='Value', digits=dp.get_precision('Payment Terms'),
                                help="For percent enter a ratio between 0-100.")
    days = fields.Integer(string='Number of Days', required=True, default=0)
    option = fields.Selection([
        ('day_after_invoice_date', 'Day(s) after the invoice date'),
        ('fix_day_following_month', 'Day(s) after the end of the invoice month (Net EOM)'),
        ('last_day_following_month', 'Last day of following month'),
        ('last_day_current_month', 'Last day of current month'),
    ],
        default='day_after_invoice_date', required=True, string='Options'
    )
    payment_id = fields.Many2one('account.payment.term', string='Payment Terms', required=True, index=True,
                                 ondelete='cascade')
    sequence = fields.Integer(default=10,
                              help="Gives the sequence order when displaying a list of payment terms lines.")

    @api.one
    @api.constrains('value', 'value_amount')
    def _check_percent(self):
        if self.value == 'percent' and (self.value_amount < 0.0 or self.value_amount > 100.0):
            raise ValidationError(_('Percentages for Payment Terms Line must be between 0 and 100.'))

    @api.onchange('option')
    def _onchange_option(self):
        if self.option in ('last_day_current_month', 'last_day_following_month'):
            self.days = 0


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    @api.multi
    def send_mail(self, auto_commit=False):
        context = self._context
        if context.get('default_model') == 'account.invoice' and \
                context.get('default_res_id') and context.get('mark_invoice_as_sent'):
            invoice = self.env['account.invoice'].browse(context['default_res_id'])
            if not invoice.sent:
                invoice.sent = True
            self = self.with_context(mail_post_autofollow=True, lang=invoice.partner_id.lang)
        return super(MailComposeMessage, self).send_mail(auto_commit=auto_commit)


class AccountInvoiceLot(models.Model):
    _name = 'account.invoice.lot'

    lot_wise_id = fields.Many2one('account.invoice.line', 'Lot Wise')

    product_id = fields.Many2one(related="lot_wise_id.product_id", string='Product', store=True)
    # avinash:15/10/20 Added so we can filter lot data on basis of these fields
    invoice_no = fields.Many2one(related="lot_wise_id.invoice_id", store=True)
    company_id = fields.Many2one(related="lot_wise_id.company_id", store=True)
    # end avinash
    lot_id = fields.Many2one('stock.production.lot', 'Lot/Serial No')
    lot_name = fields.Char('Lot/Serial Number')
    available_qty_lot = fields.Float('Available Qty', readonly=True, default=0.0)
    qty_done = fields.Float('Done', default=0.0, digits=dp.get_precision('Product Unit of Measure'), copy=False)
    product_uom = fields.Many2one('product.uom', related='lot_wise_id.product_id.uom_id', string='Unit of Measure')
    product_qty = fields.Float('Qty', digits=dp.get_precision('MRS Quantity'))


    @api.onchange('qty_done')
    def _qty_done_comparision(self):
        for val in self:
            # avinash:14/10/20 Updated to avoid updating available quantity in customer credit note
            if not val.env.context.get('type') == 'out_refund':
            # end avinash
                if val and val.product_id and val.product_id.type =='product' and val.product_id.tracking not in ['none'] and self.env.user.company_id.default_positive_stock:
                    if val.qty_done > val.available_qty_lot:
                        raise ValidationError(
                            'Cannot issue quantity more than available. For {} the available quantity in the lot {} '
                            'is {} '.format(val.product_id.name, val.lot_id.name, val.available_qty_lot))



    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        for val in self:
            # avinash:14/10/20 Updated to avoid updating available quantity in customer credit note
            if val.product_id.type == 'product' and not self.env.context.get('type') == 'out_refund':
            # end avinash
                print(val.product_id)
                dest_location_req = ''
                location_ids = self.env['stock.location'].search(
                    [('name', '=', 'Stock'),
                     ('company_id', '=', self.env.user.company_id.id),
                     ('complete_name', 'like', '%WH/Stock')])

                print(location_ids)
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
                print("match recssssssssssssssssssssssssss2 = ", match_recs, val.product_id.id)

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

    @api.onchange('qty_done')
    def _onchange_qty_done(self):
        """ When the user is encoding a move line for a tracked product, we apply some logic to
        help him. This onchange will warn him if he set `qty_done` to a non-supported value.
        """
        res = {}
        if self.qty_done and self.product_id.tracking == 'serial':
            if float_compare(self.qty_done, 1.0, precision_rounding=self.product_id.uom_id.rounding) != 0:
                message = _(
                    'You can only process 1.0 %s for products with unique serial number.') % self.product_id.uom_id.name
                res['warning'] = {'title': _('Warning'), 'message': message}
        return res

    @api.constrains('qty_done')
    def _check_positive_qty_done(self):
        if any([ml.qty_done < 0 for ml in self]):
            raise ValidationError(_('You can not enter negative quantities!'))

    # avinash: 09/10/20 Added so that when lot detail transfer from other form
    # User cannot delete lot data.
    @api.multi
    def unlink(self):
        if self.lot_wise_id.invoice_id.dispatch_ids:
            raise UserError(_('You cannot delete lot item.'))
        elif self.lot_wise_id.invoice_id.picking_receipt_id:
            raise UserError(_('You cannot delete lot item.'))
        res = super(AccountInvoiceLot, self).unlink()
        return res

    # end avinash

class OrderCalculationInvoice(models.Model):
    _name = "order.calculation.invoice"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Order Calculation Invoice"
    _order = 'serial_no'

    name = fields.Char('Description')
    invoice_id = fields.Many2one('account.invoice', 'Invoice')
    category = fields.Char('Category')
    label = fields.Char('Label')
    amount = fields.Float('Amount')
    serial_no = fields.Integer('Sr No')
    company_id = fields.Many2one('res.company', 'Company', index=True,
                                 default=lambda self: self.env.user.company_id.id)
    cr_date = fields.Date(string='Create Date', required=True, readonly=True, index=True, copy=False,
                          default=fields.Datetime.now)







