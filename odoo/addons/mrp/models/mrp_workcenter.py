# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil import relativedelta
import datetime
from odoo.exceptions import UserError, ValidationError
from odoo import api, exceptions, fields, models, _
from odoo.addons import decimal_precision as dp


class MrpWorkcenter(models.Model):
    _name = 'mrp.workcenter'
    _description = 'Work Center'
    _order = "sequence, id"
    # _inherit = ['resource.mixin']

    # resource
    _inherit = ['resource.mixin', 'mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _inherits = {'resource.resource': 'resource_id'}

    #Himanshu MRP made the name field required.
    name = fields.Char(related='resource_id.name', required=True, store=True)
    #End Himanshu
    time_efficiency = fields.Float('Time Efficiency', related='resource_id.time_efficiency', default=100, store=True)
    active = fields.Boolean('Active', related='resource_id.active', default=True, store=True)
    breakdown_ids = fields.One2many("mrp.breakdown.history", 'workcenter_id', string="Breakdown Ids")
    # resource_id = fields.Many2one('resource.resource', string="Resource")

    resource_id = fields.Many2one('resource.resource', 'Resource', ondelete='cascade', required=True)
    code = fields.Char('Code', copy=False)
    note = fields.Text(
        'Description',
        help="Description of the Work Center.")
    capacity = fields.Float(
        'Capacity', default=1.0, oldname='capacity_per_cycle',
        help="Number of pieces that can be produced in parallel.")
    sequence = fields.Integer(
        'Sequence', default=1, required=True,
        help="Gives the sequence order when displaying a list of work centers.")
    color = fields.Integer('Color')
    time_start = fields.Float('Time before prod.', help="Time in minutes for the setup.")
    time_stop = fields.Float('Time after prod.', help="Time in minutes for the cleaning.")
    routing_line_ids = fields.One2many('mrp.routing.workcenter', 'workcenter_id', "Routing Lines")
    order_ids = fields.One2many('mrp.workorder', 'workcenter_id', "Orders")
    workorder_count = fields.Integer('# Work Orders', compute='_compute_workorder_count')
    workorder_ready_count = fields.Integer('# Read Work Orders', compute='_compute_workorder_count')
    workorder_progress_count = fields.Integer('Total Running Orders', compute='_compute_workorder_count')
    workorder_pending_count = fields.Integer('Total Running Orders', compute='_compute_workorder_count')
    workorder_late_count = fields.Integer('Total Late Orders', compute='_compute_workorder_count')
    production_location = fields.Char('Production Location')

    time_ids = fields.One2many('mrp.workcenter.productivity', 'workcenter_id', 'Time Logs')
    working_state = fields.Selection([
        ('normal', 'Normal'),
        ('blocked', 'Blocked'),
        ('done', 'In Progress')], 'Status', compute="_compute_working_state", store=True)
    blocked_time = fields.Float(
        'Blocked Time', compute='_compute_blocked_time',
        help='Blocked hour(s) over the last month', digits=(16, 2))
    productive_time = fields.Float(
        'Productive Time', compute='_compute_productive_time',
        help='Productive hour(s) over the last month', digits=(16, 2))
    oee = fields.Float(compute='_compute_oee', help='Overall Equipment Effectiveness, based on the last month')
    oee_target = fields.Float(string='OEE Target', help="OEE Target in percentage", default=90)
    performance = fields.Integer('Performance', compute='_compute_performance', help='Performance over the last month')
    workcenter_load = fields.Float('Work Center Load', compute='_compute_workorder_count')
    #Himanshu Mrp 06-10-2020 Added the field for tree view
    workcenter_lines = fields.One2many('mrp.workcenter.lines', 'workcenter_id', "Work center lines")
    workcenter_checklist_lines = fields.One2many('mrp.workcenter.checklist', 'workcenter_id', "Work center lines")
    breakdown_ids = fields.One2many("mrp.breakdown.history", 'workcenter_id', string="Breakdown Ids")
    workcenter_id = fields.Many2one("mrp.routing.workcenter")
    workcenter_name = fields.Many2one("mrp.workcenter")


    _sql_constraints = [
        ('value_company_uniq', 'unique (name)', 'This Workcenter already exists !')
    ]

    @api.multi
    def button_unblock(self):
        mrp_hist = self.env['mrp.breakdown.history'].search([('workcenter_id','=',self.id)],order='create_date desc')
        if len(mrp_hist) >0:
            for val in mrp_hist[0]:
                val.write({'to_date':datetime.datetime.now()})

        for order in self:
            order.unblock()
        return True





    @api.onchange('resource_calendar_id', 'name')
    def _onchange_resource_calendar_id(self):
        comp_list = []
        result = {}
        data = self.env['resource.calendar'].search(
            [('company_id', '=', self.env.user.company_id.id)])
        for company in data:
            comp_list.append(company.id)
        if comp_list:
            result['domain'] = {'resource_calendar_id': [('id', 'in', tuple(comp_list))]}
        else:
            result['domain'] = {}
        return result


    @api.depends('order_ids.duration_expected', 'order_ids.workcenter_id', 'order_ids.state', 'order_ids.date_planned_start')
    def _compute_workorder_count(self):
        MrpWorkorder = self.env['mrp.workorder']
        result = {wid: {} for wid in self.ids}
        result_duration_expected = {wid: 0 for wid in self.ids}
        #Count Late Workorder
        data = MrpWorkorder.read_group([('workcenter_id', 'in', self.ids), ('state', 'in', ('pending', 'ready')), ('date_planned_start', '<', datetime.datetime.now().strftime('%Y-%m-%d'))], ['workcenter_id'], ['workcenter_id'])
        count_data = dict((item['workcenter_id'][0], item['workcenter_id_count']) for item in data)
        #Count All, Pending, Ready, Progress Workorder
        res = MrpWorkorder.read_group(
            [('workcenter_id', 'in', self.ids)],
            ['workcenter_id', 'state', 'duration_expected'], ['workcenter_id', 'state'],
            lazy=False)
        for res_group in res:
            result[res_group['workcenter_id'][0]][res_group['state']] = res_group['__count']
            if res_group['state'] in ('pending', 'ready', 'progress'):
                result_duration_expected[res_group['workcenter_id'][0]] += res_group['duration_expected']
        for workcenter in self:
            workcenter.workorder_count = sum(count for state, count in result[workcenter.id].items() if state not in ('done', 'cancel'))
            workcenter.workorder_pending_count = result[workcenter.id].get('pending', 0)
            workcenter.workcenter_load = result_duration_expected[workcenter.id]
            workcenter.workorder_ready_count = result[workcenter.id].get('ready', 0)
            workcenter.workorder_progress_count = result[workcenter.id].get('progress', 0)
            workcenter.workorder_late_count = count_data.get(workcenter.id, 0)

    @api.multi
    @api.depends('time_ids', 'time_ids.date_end', 'time_ids.loss_type')
    def _compute_working_state(self):
        for workcenter in self:
            # We search for a productivity line associated to this workcenter having no `date_end`.
            # If we do not find one, the workcenter is not currently being used. If we find one, according
            # to its `type_loss`, the workcenter is either being used or blocked.
            time_log = self.env['mrp.workcenter.productivity'].search([
                ('workcenter_id', '=', workcenter.id),
                ('date_end', '=', False)
            ], limit=1)
            if not time_log:
                # the workcenter is not being used
                workcenter.working_state = 'normal'

            elif time_log.loss_type in ('productive', 'performance'):
                # the productivity line has a `loss_type` that means the workcenter is being used
                workcenter.working_state = 'done'
            else:
                # the workcenter is blocked
                workcenter.working_state = 'blocked'



    @api.multi
    def write(self, values):
        res = super(MrpWorkcenter, self).write(values)
        maintenance_request = self.env['maintenance.request']

        # if not self.user_line_ids:
        #     raise ValidationError("Please Choose Users...")
        from_date = ''
        to_date = ''

        for val in self:
            for recurrence in val.workcenter_lines:
                if recurrence.maintenance_request_done == False:
                    recurrence_data = []
                    if recurrence.inactive == False:
                        for vals in val.workcenter_checklist_lines:
                            if recurrence.recurrence.id == vals.recurrence.id and vals.in_active==False:
                                val_data1 = (0, False, {
                                    'recurrence': vals.recurrence.id,
                                    'check_list': vals.check_list.id,
                                    'remarks': vals.remarks,
                                    'from_workcenter': True
                                })
                                recurrence_data.append(val_data1)

                        mrp_hist = self.env['mrp.breakdown.history'].search([('workcenter_id', '=', val.id)],
                                                                            order='create_date desc')

                        if len(mrp_hist) > 0:
                            for val in mrp_hist[0]:
                                if val.from_date:
                                    from_date = val.from_date
                                if val.to_date:
                                    to_date = val.to_date

                        # maintenance_request.write({'maintenance_checklist_lines': recurrence_data})
                        maintenance_request_dict = {
                            'maintenance_checklist_lines':recurrence_data,
                            'workcenter_id': self.id,
                            'schedule_date': recurrence.next_schedule_date,
                            'recurrence': recurrence.recurrence.id,
                            'maintenance_type': 'preventive',
                            'from_date': from_date,
                            'to_date': to_date,
                            'duration': recurrence.duration,
                        }
                        maintenance_request.create(maintenance_request_dict)
                        recurrence.maintenance_request_done = True



        return res




    @api.multi
    def _compute_blocked_time(self):
        # TDE FIXME: productivity loss type should be only losses, probably count other time logs differently ??
        data = self.env['mrp.workcenter.productivity'].read_group([
            ('date_start', '>=', fields.Datetime.to_string(datetime.datetime.now() - relativedelta.relativedelta(months=1))),
            ('workcenter_id', 'in', self.ids),
            ('date_end', '!=', False),
            ('loss_type', '!=', 'productive')],
            ['duration', 'workcenter_id'], ['workcenter_id'], lazy=False)
        count_data = dict((item['workcenter_id'][0], item['duration']) for item in data)
        for workcenter in self:
            workcenter.blocked_time = count_data.get(workcenter.id, 0.0) / 60.0

    @api.multi
    def _compute_productive_time(self):
        # TDE FIXME: productivity loss type should be only losses, probably count other time logs differently
        data = self.env['mrp.workcenter.productivity'].read_group([
            ('date_start', '>=', fields.Datetime.to_string(datetime.datetime.now() - relativedelta.relativedelta(months=1))),
            ('workcenter_id', 'in', self.ids),
            ('date_end', '!=', False),
            ('loss_type', '=', 'productive')],
            ['duration', 'workcenter_id'], ['workcenter_id'], lazy=False)
        count_data = dict((item['workcenter_id'][0], item['duration']) for item in data)
        for workcenter in self:
            workcenter.productive_time = count_data.get(workcenter.id, 0.0) / 60.0

    @api.depends('blocked_time', 'productive_time')
    def _compute_oee(self):
        for order in self:
            if order.productive_time:
                order.oee = round(order.productive_time * 100.0 / (order.productive_time + order.blocked_time), 2)
            else:
                order.oee = 0.0

    @api.multi
    def _compute_performance(self):
        wo_data = self.env['mrp.workorder'].read_group([
            ('date_start', '>=', fields.Datetime.to_string(datetime.datetime.now() - relativedelta.relativedelta(months=1))),
            ('workcenter_id', 'in', self.ids),
            ('state', '=', 'done')], ['duration_expected', 'workcenter_id', 'duration'], ['workcenter_id'], lazy=False)
        duration_expected = dict((data['workcenter_id'][0], data['duration_expected']) for data in wo_data)
        duration = dict((data['workcenter_id'][0], data['duration']) for data in wo_data)
        for workcenter in self:
            if duration.get(workcenter.id):
                workcenter.performance = 100 * duration_expected.get(workcenter.id, 0.0) / duration[workcenter.id]
            else:
                workcenter.performance = 0.0

    @api.multi
    @api.constrains('capacity')
    def _check_capacity(self):
        if any(workcenter.capacity <= 0.0 for workcenter in self):
            raise exceptions.UserError(_('The capacity must be strictly positive.'))

    @api.multi
    def unblock(self):
        self.ensure_one()
        if self.working_state != 'blocked':
            raise exceptions.UserError(_("It has been unblocked already. "))
        times = self.env['mrp.workcenter.productivity'].search([('workcenter_id', '=', self.id), ('date_end', '=', False)])
        times.write({'date_end': fields.Datetime.now()})
        return {'type': 'ir.actions.client', 'tag': 'reload'}


    @api.model
    def create(self, vals):
        calender_event = self.env['calendar.event']
        maintenance_request = self.env['maintenance.request']

        maintenance_request_dict = {}
        schedule_date=''



        preventive_recurrence_list, checklist_recurrence_list = [],[]
        if vals.get('workcenter_lines',False):
            preventive_recurrence_list = [i[2]['recurrence'] for i in vals['workcenter_lines'] if i[2].get('recurrence',False)]

        if vals.get('workcenter_checklist_lines', False):
            checklist_recurrence_list = [i[2]['recurrence'] for i in vals['workcenter_checklist_lines'] if i[2].get('recurrence', False)]

        if set(preventive_recurrence_list) != set(checklist_recurrence_list):
            raise ValidationError('Please use all those recurrence that are defined in Preventive')

        res = super(MrpWorkcenter, self).create(vals)
        from_date = ''
        to_date = ''


        for val in res:
            for recurrence in val.workcenter_lines:
                recurrence.maintenance_request_done = True
                recurrence_data = []
                for vals in val.workcenter_checklist_lines:
                    if recurrence.recurrence.id == vals.recurrence.id and vals.in_active==False:
                        val_data1 = (0, False, {
                            'recurrence': vals.recurrence.id,
                            'check_list': vals.check_list.id,
                            'remarks': vals.remarks,
                            'from_workcenter':True
                        })

                        recurrence_data.append(val_data1)
                # maintenance_request.write({'maintenance_checklist_lines': recurrence_data})
                if recurrence.inactive == True:
                    state_data = 'cancel'
                    maintenance_request_dict = {
                        'maintenance_checklist_lines':recurrence_data,
                        'workcenter_id': res.id,
                        'schedule_date': recurrence.next_schedule_date,
                        'recurrence': recurrence.recurrence.id,
                        'maintenance_type': 'preventive',
                        'duration':recurrence.duration,
                        # 'state':state_data,
                    }
                else:
                    maintenance_request_dict = {
                        'maintenance_checklist_lines': recurrence_data,
                        'workcenter_id': res.id,
                        'schedule_date': recurrence.next_schedule_date,
                        'recurrence': recurrence.recurrence.id,
                        'maintenance_type': 'preventive',
                        'duration': recurrence.duration,

                    }


                maintenance_request.create(maintenance_request_dict)



                # cal_dict = {
                #     'name': "test",
                #     'state': "draft",
                #     'start':str(vals.next_schedule_date),
                #     'stop':"2019-08-26 12:20:20",
                #     'start_datetime': '%s 11:00:00' %(vals.next_schedule_date, ),
                #     'user_id':self.env.user.id,
                # }
                #
                # calender_event.create(cal_dict)


        # self.env['calender_event'].search([('workcenter_id', '=', self.id), ('date_end', '=', False)])


        # if not res.user_line_ids:
        #     raise ValidationError("Please Choose Users...")


        return res

    @api.multi
    def unlink(self):

        for val in self:
            data = val.env['mrp.bom'].search([('active', '=', True)])
            for vals in data:
                for value in vals.process_ids:
                    for value1 in value.process_name:
                        for value2 in value1.operation_ids:
                            if value2.workcenter_id.name == val.name:
                                raise UserError(_(
                                    """You cannot delete a Work center with active Bom's."""))


        return super(MrpWorkcenter, self).unlink()





class MrpWorkcenterProductivityLoss(models.Model):
    _name = "mrp.workcenter.productivity.loss"
    _description = "TPM Big Losses"
    _order = "sequence, id"

    name = fields.Char('Reason', required=True)
    sequence = fields.Integer('Sequence', default=1)
    manual = fields.Boolean('Is a Blocking Reason', default=True)
    loss_type = fields.Selection([
        ('availability', 'Availability'),
        ('performance', 'Performance'),
        ('quality', 'Quality'),
        ('productive', 'Productive')], "Effectiveness Category",
        default='availability', required=True)



class MRP_Lot_details(models.Model):
    _name = "mrp.lot.details"

    # name = fields.Char('Reason', required=True)


    @api.model
    def default_get(self, fields_list):
        defaults = super(MRP_Lot_details, self).default_get(fields_list)
        for val in self:
            # print("f")
            pass

        return defaults



    name = fields.Many2one("product.product", string="Product", related='workorder_id.product_id')
    product_id = fields.Many2one("product.product", string="Product", related='workorder_id.product_id')
    lot_serial_detail_id = fields.Many2one('mrp.workcenter.productivity', string="Lot/Serial Detail Id")
    lot_line_ids= fields.One2many("mrp.lot.details.lines", 'lot_line_id',
                                        string="Lot/Serial")
    workorder_id = fields.Many2one('mrp.workorder', 'Work Order')
    production_id = fields.Many2one("mrp.production", string="Production No")
    qty = fields.Float('To Forward', digits=dp.get_precision('Manufacturing Unit of Measure'))
    sum_current_qty = fields.Float('Total Current Qty',compute='_compute_qty',  digits=dp.get_precision('Manufacturing Unit of Measure'))
    sum_pending_qty = fields.Float('Total Qty From Previous Process', compute='_compute_qty', digits=dp.get_precision('Manufacturing Unit of Measure'))
    sum_rejected_qty = fields.Float('Rejected Qty', compute='_compute_qty',
                                    digits=dp.get_precision('Manufacturing Unit of Measure'))
    sum_rework_qty = fields.Float('Rework Qty', compute='_compute_qty',
                                  digits=dp.get_precision('Manufacturing Unit of Measure'))

    have_lot = fields.Boolean("Have Lot")
    serial_saved_this_time = fields.Boolean("Serial Saved Lot")

    state = fields.Selection([
        ('pending', 'Pending'),
        ('ready', 'Ready'),
        ('progress', 'In Progress'),
        ('inspection_pending', 'Pending Inspection'),
        ('done', 'Finished'),
        ('cancel', 'Cancelled')], string='Status', related='workorder_id.state')

    @api.one
    @api.depends('lot_line_ids.qty', 'lot_line_ids.current_qty', 'lot_line_ids.rework_qty', 'lot_line_ids.rejected_qty')
    def _compute_qty(self):
        current_qty = 0
        pending_qty = 0
        rejected_qty = 0
        rework_qty = 0
        for val in self.lot_line_ids:
            current_qty += val.current_qty
            pending_qty += val.qty
            rejected_qty += val.rejected_qty
            rework_qty += val.rework_qty

        self.sum_current_qty = current_qty
        self.sum_pending_qty = pending_qty
        self.sum_rejected_qty = rejected_qty
        self.sum_rework_qty = rework_qty

    def save_data(self):
        all_lots = []


        for val in self:
            if val.sum_rejected_qty > (val.workorder_id.sum_rejected_qty + val.workorder_id.done_qty + val.workorder_id.qty_produced):
                raise ValidationError("Please Check Rejected Qty")

            if val.sum_rework_qty > (val.workorder_id.sum_rework_qty + val.workorder_id.done_qty + val.workorder_id.qty_produced):
                raise ValidationError("Please Check Rework Qty")

            # elif not val.have_lot and val.sum_reject_and_rework > (val.workorder_id.qty_production - val.workorder_id.qty_produced):
            #     raise ValidationError(
            #         "Sum of Rejected,Rework and Current Qty Cannot be Greater than {}...".format(lot_line_id.qty))


        if self.product_id.product_tmpl_id.tracking == 'serial':
            self.workorder_id.serial_saved_this_time = True
            if self.workorder_id.qty_produced != self.workorder_id.qty_production:
                self.workorder_id.state = 'progress'

        if self.sum_current_qty == 0:
            raise  ValidationError("There is not any Qty to Proceed...")

        for val in self.lot_line_ids:
            if val.is_serial:
                val.is_serial_done = True

        self.workorder_id.done_lot_this_time = True
        for val in self.lot_line_ids:
            val.data_saved = True

            if val.lot_serial.id not in all_lots:
                if self.sum_current_qty != self.qty:
                    raise ValidationError("Sum of Current Quantities Must be Equal to To Total Current Qty...")
            else:
                raise ValidationError("Cannot Have Same Lot...")
            all_lots.append(val.lot_serial.id)

    @api.onchange('product_id', 'workorder_id', 'production_id')
    def _onchange_product_id(self):
        input_output_data=[]
        # print("on change  workingggggggggggggggg")

        if self.workorder_id.lot_serial:
            if self.product_id.product_tmpl_id.tracking == 'serial':

                if self.qty > 0:
                    self.serial_saved_this_time = True

                for i in range(0, int(self.qty)):
                    data = (0, False, {
                        # 'input_output_id': self.id,
                        'workorder_id': self.workorder_id.id,
                        'production_id': self.production_id.id,
                        'current_qty': 1,
                        'have_lot':self.have_lot,
                        'is_serial':True

                    })
                    input_output_data.append(data)

                self.lot_line_ids = input_output_data

            elif self.product_id.product_tmpl_id.tracking == 'lot':
                for i in range(0, 1):
                    data = (0, False, {
                        # 'input_output_id': self.id,
                        'workorder_id': self.workorder_id.id,
                        'production_id': self.production_id.id,
                        # 'qty': int(self.qty)
                        'have_lot': self.have_lot,
                        'is_serial': False

                    })
                    input_output_data.append(data)
                self.lot_line_ids = input_output_data
        #
        # all_issued_products = self.env['issue.mrs.line'].search(
        #     [('production_id', '=', self.production_id.id)])


class MRP_Lot_details_Lines(models.Model):
    _name = "mrp.lot.details.lines"

    # name = fields.Char('Reason', required=True)
    lot_serial = fields.Many2one('stock.production.lot', "Lot/Serial")
    qty = fields.Float('Qty From Previous Process', digits=dp.get_precision('Manufacturing Unit of Measure'), default=0.0)
    lot_line_id = fields.Many2one("mrp.lot.details", string='Lot Line')

    lot_detail_lines_ids = fields.One2many("mrp.lot.details.raw.materials", 'lot_detail_lines_id',
                                   string="Lot/Serial")
    workorder_id = fields.Many2one('mrp.workorder', 'Work Order')
    production_id = fields.Many2one("mrp.production", string="Production No")
    product_id = fields.Many2one("product.product", related='workorder_id.product_id')
    name = fields.Many2one("product.product", related='workorder_id.product_id')
    state = fields.Selection([
        ('pending', 'Pending'),
        ('ready', 'Ready'),
        ('progress', 'In Progress'),
        ('inspection_pending', 'Pending Inspection'),
        ('done', 'Finished'),
        ('cancel', 'Cancelled')], string='Status', related='workorder_id.state')
    total_done = fields.Float('Total Done', digits=dp.get_precision('Manufacturing Unit of Measure'))
    current_qty = fields.Float('Current Qty', default=0.0, digits=dp.get_precision('Manufacturing Unit of Measure'))
    data_saved = fields.Boolean("Data Saved")
    have_lot = fields.Boolean("Have Lot")
    is_serial = fields.Boolean("Is Serial")
    is_serial_done = fields.Boolean("Is Serial Done")

    rejected_qty = fields.Float('Rejected Qty', digits=dp.get_precision('Manufacturing Unit of Measure'))
    rework_qty = fields.Float('Rework Qty', digits=dp.get_precision('Manufacturing Unit of Measure'))
    remarks = fields.Text("Remarks")

    @api.onchange('rejected_qty')
    def onchange_rejected_qty(self):
        for val in self:
            if val.lot_line_id.sum_rejected_qty > (
                    val.workorder_id.sum_rejected_qty + val.workorder_id.done_qty + val.workorder_id.qty_produced):
                raise ValidationError("Please Check Rejected Qty")


    @api.onchange('rework_qty')
    def onchange_rework_qty(self):
        for val in self:
            if val.lot_line_id.sum_rework_qty > (
                            val.workorder_id.sum_rework_qty + val.workorder_id.done_qty + val.workorder_id.qty_produced):
                raise ValidationError("Please Check Rework Qty")



    @api.onchange('current_qty')
    def onchange_current_qty(self):
        for val in self:
            if val.qty - val.total_done == 0 and not val.have_lot:
                raise ValidationError("You cannot Insert More Quantities in this Lot...")
            if val.current_qty > (val.qty - val.total_done) and not val.have_lot:
                raise ValidationError("Current Qty Cannot be Greater than {}...".format(val.qty - val.total_done))

    # @api.onchange('rejected_qty', 'rework_qty')
    # def onchange_rework_qty(self):
    #     for val in self:
    #         if (val.rework_qty + val.rejected_qty) > (val.qty + val.current_qty - val.total_done) and not val.have_lot:
    #             raise ValidationError("Rejected or Rework Cannot be Greater than {}...".format(val.qty + val.current_qty - val.total_done))
    #
    #         elif val.have_lot and (val.rework_qty + val.rejected_qty + val.current_qty) > (lot_line_id.qty):
    #             raise ValidationError("Sum of Rejected,Rework and Current Qty Cannot be Greater than {}...".format(lot_line_id.qty))

    # @api.multi
    # def unlink(self):
    #     print("UNBLINGKKKKKKKKKKKKKKKKK")
    #     res = super(MRP_Lot_details_Lines, self).unlink()
    #     for val in self:
    #         if val.id:
    #             print("True")
    #         else:
    #             print("False")
    #
    #
    #     return res





def action_open_form_lot_serial_btn(self):
        view = self.env.ref('mrp.workorder_lot_serial_raw_materials_form')
        # if self.rework_qty <= 0:
        #     raise ValidationError("Rework Qty cannot be 0 for Rework Manufacture")
        # else:
        consumed_id = self.env['mrp.lot.details.raw.materials'].search([('lot_detail_lines_id', '=', self.id)])

        if len(consumed_id) > 0:
            return {
                'name': _('Lot/Serial Raw Materials'),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'mrp.lot.details.raw.materials',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'new',
                'res_id': consumed_id[0].id,
                # 'context': {'default_required_qty': self.product_uom_qty}
            }
        else:
            return {
                'name': _('Lot/Serial Raw Materials'),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'mrp.lot.details.raw.materials',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'new',
                'context': {
                            'default_lot_detail_lines_id': self.id,
                            'default_workorder_id': self.workorder_id.id,
                            'default_production_id': self.production_id.id
                            }
                    }


class MRP_Lot_details_Raw_materials(models.Model):
    _name = "mrp.lot.details.raw.materials"

    workorder_id = fields.Many2one('mrp.workorder', 'Work Order')
    qty = fields.Float("Done Quantity", digits=dp.get_precision('Manufacturing Unit of Measure'))

    # name = fields.Char('Reason', required=True)

    lot_serial_raw_material_line_ids= fields.One2many("mrp.lot.details.raw.materials.lines", 'lot_serial_raw_material_line_id',
                                        string="Lot/Serial")
    lot_detail_lines_id = fields.Many2one('mrp.lot.details.lines', 'Lot Detail Lines')
    production_id = fields.Many2one("mrp.production", string="Production Id")

    state = fields.Selection([
        ('pending', 'Pending'),
        ('ready', 'Ready'),
        ('progress', 'In Progress'),
        ('inspection_pending', 'Pending Inspection'),
        ('done', 'Finished'),
        ('cancel', 'Cancelled')], string='Status', related='workorder_id.state')



    @api.onchange('workorder_id')
    def _onchange_workorder_id(self):
        result = {}
        input_output_data = []

        all_issued_products = self.env['issue.mrs.line'].search(
            [('production_id', '=', self.production_id.id)])

        for val in all_issued_products:
            # all_issued_products22 = self.env['product.product'].search(
            #     [('id', '=', val.product_id.id)])

            for tracking in val.issue_mrs_line_tracking_ids:
                data = (0, False, {
                    # 'input_output_id': self.id,
                    'product_id': tracking.product_id.id,
                    'lot_serial': tracking.lot_id.id,
                    'workorder_id': self.workorder_id.id,
                    'production_id': self.production_id.id,
                    'qty':tracking.product_qty

                })
                input_output_data.append(data)

            self.lot_serial_raw_material_line_ids = input_output_data




            # for lines in self.lot_serial_raw_material_line_ids:
            #     lines.product_id = all_issued_products22.id

            # for vals in all_issued_products22:
            #
            #
            #     data = (0, False, {
            #         # 'input_output_id': self.id,
            #         'product_id': vals.id,
            #         'workorder_id':self.workorder_id.id,
            #         'production_id':self.production_id.id
            #
            #     })
            #     input_output_data.append(data)
            #
            # self.lot_serial_raw_material_line_ids = input_output_data

            #
            # if all_issued_products22:
            #     print("alllllllllllllllllll", all_issued_products22)

        # for emp in emp_data1:
        #     emp_list.append(emp.id)
        # # , ('id', 'not in', self.already_took_helpers)
        # if emp_list:
        #     result['domain'] = {'name': [('id', 'in', tuple(emp_list))]}
        # else:
        #     result['domain'] = {}
        return result







class MRP_Lot_details_Raw_materials_lines(models.Model):
    _name = "mrp.lot.details.raw.materials.lines"

    production_id = fields.Many2one("mrp.production", string="Production Id")
    qty = fields.Float("Issued Quantity", digits=dp.get_precision('Manufacturing Unit of Measure'))
    # name = fields.Char('Reason', required=True)
    workorder_id = fields.Many2one('mrp.workorder', 'Work Order')
    lot_serial = fields.Many2one('stock.production.lot', "Lot/Serial")
    product_id = fields.Many2one("product.product", string="Product")
    qty_done = fields.Float("Quantity Done", digits=dp.get_precision('Manufacturing Unit of Measure'))

    lot_serial_raw_material_line_id = fields.Many2one('mmrp.lot.details.raw.materials', 'Lot Raw Detail Lines')

    state = fields.Selection([
        ('pending', 'Pending'),
        ('ready', 'Ready'),
        ('progress', 'In Progress'),
        ('inspection_pending', 'Pending Inspection'),
        ('done', 'Finished'),
        ('cancel', 'Cancelled')], string='Status', related='workorder_id.state')



    @api.onchange('qty_done')
    def _onchange_qty_done(self):

        if self.qty < self.qty_done:
            raise  ValidationError("Done qty cannot be greator than Issued Qty...")


    @api.onchange('product_id')
    def _onchange_product_id(self):

        emp_list = []
        result = {}

        dep_id = self.env['hr.department'].search(
            [('name', '=', 'Production')])
        emp_data1 = self.env['stock.production.lot'].search(
            [('department_id', '=', dep_id.id)])
        for emp in emp_data1:
            emp_list.append(emp.id)
        # , ('id', 'not in', self.already_took_helpers)
        if emp_list:
            result['domain'] = {'name': [('id', 'in', tuple(emp_list))]}
        else:
            result['domain'] = {}
        return result



class MrpWorkcenterProductivity(models.Model):
    _name = "mrp.workcenter.productivity"
    _description = "Workcenter Productivity Log"
    _order = "id desc"
    _rec_name = "loss_id"

    workcenter_id = fields.Many2one('mrp.workcenter', "Work Center", required=True)
    workorder_id = fields.Many2one('mrp.workorder', 'Work Order')
    user_id = fields.Many2one(
        'res.users', "User",
        default=lambda self: self.env.uid)
    loss_id = fields.Many2one(
        'mrp.workcenter.productivity.loss', "Loss Reason",
        ondelete='restrict', required=True)
    loss_type = fields.Selection(
        "Effectiveness", related='loss_id.loss_type', store=True)
    description = fields.Text('Description')
    date_start = fields.Datetime('Start Date', default=fields.Datetime.now, required=True)
    date_end = fields.Datetime('End Date')
    duration = fields.Float('Duration', compute='_compute_duration', store=True)
    qty = fields.Float("Done Quantity", digits=dp.get_precision('Manufacturing Unit of Measure'))
    # lot_serial = fields.Boolean("Lot/Serial"  , related='workorder_id.lot_serial')

    # name = fields.Many2one('mrp.routing', string="Process", related='workorder_id.process_id')
    # manufacturing_id = fields.Many2one("mrp.production", string="Manufacturing Order", related='workorder_id.production_id')
    # rework_reject_ids = fields.One2many("mrp.workorder.todo.checklist",'rework_reject_id', string="Manufacturing Order")

    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
    ], string='Status')

    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.user.company_id.id)

    status = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
    ], string='Status')
    product_id = fields.Many2one('product.product', string='Product')
    qty_received_from_challan = fields.Float('Qty Received From Challan', digits=dp.get_precision('Manufacturing Unit of Measure'))
    lot_serial_detail_ids = fields.One2many("mrp.lot.details", 'lot_serial_detail_id',
                                        string="Lot/Serial")

    # inspection_pending = fields.Boolean("Inspection Pending", compute="_compute_inspection_pending")

    # @api.multi
    # def _compute_inspection_pending(self):
    #     dep_id = self.env['hr.department'].search(
    #         [('rework_reject_id', '=', self.id)])


    @api.onchange('qty','loss_id','lot_serial')
    def onchange_qty(self):
        for val in self:
            if val.qty and val.qty > round(val.workorder_id.reserved_qty,6):
                raise ValidationError("Cannot Produce More than Reserved Quantity Which is {}...".format(val.workorder_id.reserved_qty))
            # elif val.qty:
            #     val.workorder_id.reserved_qty = val.workorder_id.reserved_qty - val.qty





    @api.model
    def create(self, values):
        res = super(MrpWorkcenterProductivity, self).create(values)
        res.state = 'done'
        # res.workorder_id.reserved_qty = res.workorder_id.reserved_qty - res.qty
        #
        # for val in res.manufacturing_id:
        #     for process in val.process_ids:
        #         if process.process_name.name == self.name.name:
        #             if process.lot_serial == True:
        #                 res.lot_serial = True
        #             else:
        #                 res.lot_serial = False

        return res

    @api.multi
    def write(self, vals):
        res = super(MrpWorkcenterProductivity, self).write(vals)

        # if vals.get('qty'):
        #     self.workorder_id.reserved_qty = self.workorder_id.reserved_qty - self.qty
        return res


    # @api.model
    # def create(self, values):
    #     res = super(MrpWorkcenterProductivity, self).create(values)
    #     res.state = 'done'
    #
    #
    #     return res


    def action_open_form_inspection_btn(self):
        view = self.env.ref('mrp.workorder_todo_checklist_form1')
        # if self.rework_qty <= 0:
        #     raise ValidationError("Rework Qty cannot be 0 for Rework Manufacture")
        # else:
        consumed_id = self.env['mrp.workorder.todo.checklist'].search([('rework_reject_id', '=', self.id)])

        # if self.qty <= 0:
        #     raise ValidationError("Done Qty Must be Greater than 0")
        # else:
        if len(consumed_id) > 0:
            return {
                'name': _('Reject/Rework'),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'mrp.workorder.todo.checklist',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'new',
                'res_id': consumed_id[0].id,
                # 'context': {'default_required_qty': self.product_uom_qty}
            }
        else:
            return {
                'name': _('Reject/Rework'),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'mrp.workorder.todo.checklist',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'new',
                'context': {'default_work_order_id': self.workorder_id.id,
                            'default_todo_checklist_id':self.workorder_id.id,
                            'default_rework_reject_id':self.id,
                            'default_pending_qty': self.qty,
                            'default_date_end': self.date_end,
                            'default_date_start': self.date_start
                        }
                 }

    def action_open_form_lot_serial_btn(self):
        view = self.env.ref('mrp.workorder_lot_serial_form')


        # if self.rework_qty <= 0:
        #     raise ValidationError("Rework Qty cannot be 0 for Rework Manufacture")
        # else:
        consumed_id = self.env['mrp.lot.details'].search([('lot_serial_detail_id', '=', self.id)])

        # if self.qty <= 0:
        #     raise ValidationError("Done Qty Must be Greater than 0")
        # else:

        if len(consumed_id) > 0:
            return {
                'name': _('Lot/Serial'),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'mrp.lot.details',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'current',
                'res_id': consumed_id[0].id,
                # 'context': {'default_required_qty': self.product_uom_qty}
            }
        else:
            return {
                'name': _('Lot/Serial'),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'mrp.lot.details',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'current',
                'context': {
                            'default_lot_serial_detail_id': self.id,
                             'default_workorder_id': self.workorder_id.id,
                             'default_production_id':self.manufacturing_id.id,
                                'default_qty': self.qty,
                            }
                    }

        # self.env['mrp.lot.details'].insert_data()




    @api.depends('date_end', 'date_start')
    def _compute_duration(self):
        for blocktime in self:
            if blocktime.date_end:
                d1 = fields.Datetime.from_string(blocktime.date_start)
                d2 = fields.Datetime.from_string(blocktime.date_end)
                diff = d2 - d1
                if (blocktime.loss_type not in ('productive', 'performance')) and blocktime.workcenter_id.resource_calendar_id:
                    r = blocktime.workcenter_id.resource_calendar_id.get_work_hours_count(d1, d2, blocktime.workcenter_id.resource_id.id)
                    blocktime.duration = round(r * 60, 2)
                else:
                    blocktime.duration = round(diff.total_seconds() / 60.0, 2)
            else:
                blocktime.duration = 0.0

    @api.multi
    def button_block(self):
        breakdown_lines_list = []
        self.ensure_one()
        self.workcenter_id.order_ids.end_all()

        breakdown_lines = (0, False, {
            'from_date': datetime.datetime.now(),
            'reason_for_breakdown': self.loss_id.id
        })
        breakdown_lines_list.append(breakdown_lines)
        self.workcenter_id.write({'breakdown_ids': breakdown_lines_list})



# ===================================new class added to show tree view in preventive tab starts here==============================================
class MrpWorkcenterLines(models.Model):
    _name = 'mrp.workcenter.lines'

    user_id = fields.Many2one('res.users', string='User', index=True,
                              default=lambda self: self.env.user)
    workcenter_id = fields.Many2one('mrp.workcenter', 'Work Center')
    recurrence = fields.Many2one('mrp.workcenter.recurrence',string='Recurrence', required=True)
    duration = fields.Integer('Duration', store=True, required=True)
    start_date = fields.Datetime('Last Maintainance Date', store=True, required=True)
    next_schedule_date = fields.Datetime('Next Schedule Date', store=True)
    stop_date = fields.Datetime("Stop Date")
    # checklist = fields.Text('Check List', store=True)
    inactive = fields.Boolean('Inactive', store=True)
    maintenance_request_done = fields.Boolean('Maintenance Request Done', store=True)
    remarks = fields.Char('Remarks', store=True)
    company_id = fields.Many2one('res.company', 'Company', index=True, default=lambda self: self.env.user.company_id.id)
    # Trilok Added This active_inactive_flag field for solving bug-140 24-10-2020
    active_inactive_flag = fields.Boolean('Active/Inactive', default=False, store=True, help="It will be true if user change start date of inactive line and want to active it.")

    @api.onchange('recurrence', 'start_date', 'from_day' ,'duration')
    def start_date_onchange(self):
            least_date = ""
            if self.start_date:

                for val in self:

                    if datetime.datetime.strptime(val.start_date,"%Y-%m-%d %H:%M:%S") > datetime.datetime.today():
                        raise ValidationError("Last maintainance date must not be a future date.")

                    # if not val.from_day:
                    #     raise ValidationError("Please provide from day.")

                    if val.recurrence.recurrence_name.upper() == "MONTHLY":
                        temp_next_schedule_date,least_date = datetime.datetime.strptime(val.start_date,'%Y-%m-%d %H:%M:%S') +\
                                                             relativedelta.relativedelta(months=1),datetime.datetime.today() - relativedelta.relativedelta(months=1)
                    elif val.recurrence.recurrence_name.upper() == "QUARTERLY":
                        temp_next_schedule_date, least_date = datetime.datetime.strptime(val.start_date,'%Y-%m-%d %H:%M:%S') + relativedelta.relativedelta(months=3), datetime.datetime.today() - relativedelta.relativedelta(months=3)
                    elif val.recurrence.recurrence_name.upper() == "HALF YEARLY":
                        temp_next_schedule_date, least_date = datetime.datetime.strptime(val.start_date,'%Y-%m-%d %H:%M:%S') + relativedelta.relativedelta(months=6), datetime.datetime.today() - relativedelta.relativedelta(months=6)
                    elif val.recurrence.recurrence_name.upper() == "YEARLY":
                        temp_next_schedule_date,least_date = datetime.datetime.strptime(val.start_date,'%Y-%m-%d %H:%M:%S') + relativedelta.relativedelta(years=1),datetime.datetime.today() - relativedelta.relativedelta(years=1)
                    else:
                        temp_next_schedule_date, least_date = datetime.datetime.strptime(val.start_date,'%Y-%m-%d %H:%M:%S') + relativedelta.relativedelta(days=val.recurrence.recurrence_value), datetime.datetime.today() - relativedelta.relativedelta(days=val.recurrence.recurrence_value)

                    self.next_schedule_date = temp_next_schedule_date
                    self.stop_date = temp_next_schedule_date + relativedelta.relativedelta(hours= self.duration) #- relativedelta.relativedelta(hours=6, minute=30)

                    if temp_next_schedule_date < datetime.datetime.today():
                        raise ValidationError("Last Maintainance Date can't be before {x}".format(x=least_date))


    @api.onchange('recurrence')
    def unique_recurrence_check(self):
        if self.recurrence:
            a = 1

    @api.model
    def create(self, values):
        res = super(MrpWorkcenterLines, self).create(values)
        return res

    @api.onchange('start_date')
    def start_date_change_in_inactive_line(self):
        if self.start_date and self.inactive:
            self.active_inactive_flag = True


# ===================================new class added to show tree view in preventive tab ends here==============================================

# End Himanshu

# ===================================new class added to show tree view in Checklist tab starts here=============================================
class MrpWorkCenterChecklist(models.Model):
    _name = 'mrp.workcenter.checklist'

    workcenter_id = fields.Many2one('mrp.workcenter', 'Work Center')
    recurrence = fields.Many2one('mrp.workcenter.recurrence', string='Recurrence',
                                 required=True, domain='[]')
    check_list = fields.Many2one('mrp.workcenter.checklist.master', string='Check List',
                                 required=True)
    in_active = fields.Boolean('Inactive')
    remarks = fields.Text('Remarks')
    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env['res.company']._company_default_get('mrp.production'),
        required=True)

#Himanshu mrp 15-11-2020 if the recurrence is not in the preventive tab and added in checklist tab then the error will be raised
    @api.onchange('recurrence')
    def check_validation(self):
        data = []
        if self.recurrence:
            for rec in self.workcenter_id.workcenter_lines:
                data.append(rec.recurrence.recurrence_name)
                if self.recurrence.recurrence_name not in data:
                    raise ValidationError(_("Not in preventive tab"))
#End Himanshu


class MrpBreakdownHistory(models.Model):
    _name = 'mrp.breakdown.history'
    _description = 'Breakdown History'

    from_date = fields.Datetime('From Date', store=True)
    to_date = fields.Datetime('To Date', store=True)
    reason_for_breakdown = fields.Many2one('mrp.workcenter.productivity.loss',string="Reason For Breakdown")
    remedy = fields.Char("Remedy")
    spare_parts = fields.Char("Spare Parts")
    remarks = fields.Text("Remarks")
    workcenter_id = fields.Many2one('mrp.workcenter', 'Workcenter')



class RecurrenceMasterData(models.Model):
    _name = 'mrp.workcenter.recurrence'
    _rec_name = 'recurrence_name'

    recurrence_name = fields.Char('Name', required=True)
    recurrence_value = fields.Integer('Value', required=True)
    recurrence_type = fields.Selection([('pre_define','Pre-Defined'),('user_define','User-Defined')],
                                       required=True, default='user_define')
    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env['res.company']._company_default_get('mrp.production'),
        required=True)

    @api.multi
    def unlink(self):
        for val in self:
            if val.recurrence_type == "pre_define":
                raise ValidationError("Can't delete pre defined values")

        return super(RecurrenceMasterData,self).unlink()

#End Himanshu


class ChecklistMasterData(models.Model):
    _name = 'mrp.workcenter.checklist.master'

    name = fields.Char('Check List')
    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env['res.company']._company_default_get('mrp.production'),
        required=True)

#Himanshu mrp 6-12-2020 added this code referenced from pflo by trilok sir for the functionality of active/inactive button
class WorkcenterLinesActiveInactive(models.TransientModel):
    _name = "wc.active.inactive"
    _description = "Preventive Line Active Inactive Wizard"

    wc_line_id = fields.Many2one('mrp.workcenter.lines', string='Wc Line No')
    msg = fields.Char()

    @api.model
    def default_get(self, fields):
        active_id = self._context.get('active_id', False)
        res = super(WorkcenterLinesActiveInactive, self).default_get(fields)
        if active_id:
            if 'wc_line_id' in fields and 'wc_line_id' not in res:
                res['wc_line_id'] = active_id
            wc_line_id = self.env['mrp.workcenter.lines'].browse(active_id)
            requests = self.corresponding_maintenance_req(wc_line_id)
            if not wc_line_id.inactive:
                msg = 'Are You Sure You Want To Inactive This?'
                names = ''
                if requests:
                    for req in requests:
                        names += req.name + ' '
                if names == '':
                    res['msg'] = msg
                else:
                    res['msg'] = msg + "\n The Corresponding Maintenance Requests are: " + names + '.'
            else:
                msg = 'Are You Sure You Want To Active This?'
                res['msg'] = msg
        return res

    def corresponding_maintenance_req(self,wc_line_id):
        maintenance_request = self.env['maintenance.request']
        requests =[]
        if wc_line_id:
            requests = maintenance_request.search(
                [('workcenter_id', '=', wc_line_id.workcenter_id.id), ('recurrence', '=', wc_line_id.recurrence.id),
                 ('state', '=', 'normal')])
            return requests
        return requests

    @api.multi
    def yes(self):
        if self.wc_line_id:
            requests = self.corresponding_maintenance_req(self.wc_line_id)
            if not self.wc_line_id.inactive:
                if requests:
                    for req in requests:
                        req.write({'state':'cancel'})
                self.wc_line_id.inactive = True
                self.wc_line_id.active_inactive_flag = False
            else:
                if self.wc_line_id.active_inactive_flag:
                    recurrence_data = []
                    if self.wc_line_id.workcenter_id.workcenter_checklist_lines:
                        for vals in self.wc_line_id.workcenter_id.workcenter_checklist_lines:
                            if self.wc_line_id.recurrence.id == vals.recurrence.id and not vals.in_active:
                                val_data1 = (0, False, {
                                    'recurrence': vals.recurrence.id,
                                    'check_list': vals.check_list.id,
                                    'remarks': vals.remarks,
                                    'from_workcenter': True
                                })
                                recurrence_data.append(val_data1)
                    maintenance_request_dict = {
                        'maintenance_checklist_lines': recurrence_data,
                        'workcenter_id': self.wc_line_id.workcenter_id.id,
                        'schedule_date': self.wc_line_id.next_schedule_date,
                        'recurrence': self.wc_line_id.recurrence.id,
                        'maintenance_type': 'preventive',
                        'duration': self.wc_line_id.duration,
                    }
                    self.env['maintenance.request'].create(maintenance_request_dict)
                self.wc_line_id.inactive = False

    @api.multi
    def no(self):
        pass

    #End Himanshu