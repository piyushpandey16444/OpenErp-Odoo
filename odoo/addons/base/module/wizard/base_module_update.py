# -*- coding: utf-8 -*-

from odoo import api, fields, models


class BaseModuleUpdate(models.TransientModel):
    _name = "base.module.update"
    _description = "Update Module"

    updated = fields.Integer('Number of modules updated', readonly=True)
    added = fields.Integer('Number of modules added', readonly=True)
    state = fields.Selection([('init', 'init'), ('done', 'done')], 'Status', readonly=True, default='init')

    # Aman 14/10/2020 Added function to install all modules by press of a button
    @api.multi
    def install_module(self):
        a = self.env['ir.module.module']
        a.update_list()
        list = ['tally_integration', 'stock', 'sale_management', 'purchase', 'mail','sale_ext', 'account_invoicing',
                'purchase_extension','account_invoice_extension','base_ext','purchase_requisition', 'ecom_integration',
                'web_widget_many2many_tags_open','web_tree_many2one_clickable', 'calendar', 'simple_backend_theme','stock_ext']
        for i in list:
            moduleIds = a.search([('state', '!=', 'installed'), ('name', '=', i)])
            if moduleIds:
                moduleIds[0].button_immediate_install()
    # Aman end

    @api.multi
    def update_module(self):
        for this in self:
            updated, added = self.env['ir.module.module'].update_list()
            this.write({'updated': updated, 'added': added, 'state': 'done'})
        return False

    @api.multi
    def action_module_open(self):
        res = {
            'domain': str([]),
            'name': 'Modules',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'ir.module.module',
            'view_id': False,
            'type': 'ir.actions.act_window',
        }
        return res
