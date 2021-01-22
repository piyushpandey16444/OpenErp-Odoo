from odoo import api, fields, models, _

class SyncLogs(models.Model):
    _name = 'sync.logs'
    
    name = fields.Char('Name')
    object = fields.Char('Model Name')
    log_date = fields.Datetime('Log Date')
    total_records = fields.Integer('Total Records')
    no_imported = fields.Integer('Records Migrated Successfully')
    record_name = fields.Char('Record Name')
    is_migrated = fields.Boolean('Is Migrated')
    reason = fields.Char('Reason')
    voucher_no = fields.Char('Voucher Number')
    voucher_type = fields.Char('Voucher Type')
    
    
    