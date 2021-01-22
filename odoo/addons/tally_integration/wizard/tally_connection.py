from odoo import api, fields, models, _
import os
from odoo.exceptions import UserError
from . import etree_paser
from . import migrator
# from . import connection
import requests


class TallyConnection(models.Model):
    
    @api.onchange('ledgers')
    def onchange_ledgers_option(self):
        if self.ledgers == True:
            return {'value':{'groups': True}}
        else:
            return {'value':{'groups': False}}

    def _get_default_url(self):
        tally_url = self.env['ir.config_parameter'].sudo().get_param('tally.url')
        if tally_url:
            return tally_url
        else:
            return 'http://localhost:9000'

    _name = 'tally.connection'
    _description = 'Tally Connection'
    
    # url = fields.Char('Tally URL With Port', size=256, required=True,default = lambda * a:'http://localhost:9000')
    url = fields.Char('Tally URL With Port', size=256, required=True, default=_get_default_url)
    company = fields.Many2one("res.company", string="Migrate Data Into Company",
                            default=lambda self: self.env['res.company']._company_default_get('account.invoice'))
    daybook = fields.Char(string='Path To DayBook', size=256,
                    help='Export the DayBook in XML Format, and give the path of DayBook.xml file.',
                    default = '/home/arke-it03/DayBook.xml')
    ledgers = fields.Boolean(string='Ledgers')
    groups = fields.Boolean(string='Groups')
    vouchers = fields.Boolean(string='Vouchers')
#     inventory_master = fields.Boolean(string='All Inventory Masters')
    stock_items = fields.Boolean(string='Stock Items')
    stock_groups = fields.Boolean(string='Stock Groups')
    units = fields.Boolean(string='Unit of Measure')
#     employees = fields.Boolean(string='Employees')
    godowns = fields.Boolean(string='Godowns')
    
    @api.multi
    def getVouchers(self,reportType):
        print("Vouchers Report Type======",reportType)
        url = self.url
        print('URL',url)
        print('Entered In GetData')
        headers = {"Content-type": "text/xml", "Accept": "text/xml"}
        params = """
        <?xml version='1.0' encoding='utf-8'?>
        <ENVELOPE>
        <HEADER>
        <TALLYREQUEST>Export Data</TALLYREQUEST>
        </HEADER>
        <BODY>
        <EXPORTDATA>
        <REQUESTDESC>
        <REPORTNAME>Voucher Register</REPORTNAME>
        <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT> 
        <ACCOUNTTYPE>""" + reportType + """</ACCOUNTTYPE> 
        <EXPLODEFLAG>No</EXPLODEFLAG>          
        </STATICVARIABLES>
        </REQUESTDESC>
        </EXPORTDATA>
        </BODY>
        </ENVELOPE>
         """
        
        res = requests.post(url, data=params, headers={'Content-Type': 'application/xml'})
        r1 = res.text
#         print('** r1.read() Value **',r1)
        return r1
    
    @api.multi
    def getData(self,reportType):
        print("Report Type======",reportType)
        url = self.url
        print('URL',url)
        print('Entered In GetData')
        headers = {"Content-type": "text/xml", "Accept": "text/xml"}
        params = """
        <?xml version='1.0' encoding='utf-8'?>
        <ENVELOPE>
        <HEADER>
        <TALLYREQUEST>Export Data</TALLYREQUEST>
        </HEADER>
        <BODY>
        <EXPORTDATA>
        <REQUESTDESC>
        <REPORTNAME>List of Accounts</REPORTNAME>
        <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT> 
        <ACCOUNTTYPE>""" + reportType + """</ACCOUNTTYPE> 
        <EXPLODEFLAG>No</EXPLODEFLAG>          
        </STATICVARIABLES>
        </REQUESTDESC>
        </EXPORTDATA>
        </BODY>
        </ENVELOPE>
         """
        
        res = requests.post(url, data=params, headers={'Content-Type': 'application/xml'})
#         print(res.getresponse())
        r1 = res.text
#         print('** r1.read() Value **',r1)
        return r1
    
    def createTempFile(self,s):
        f = open('/home/sourav/odoo/getDatas.xml','w')
        s1 = """ 
        <ENVELOPE>
        <HEADER>
        <TALLYREQUEST>Import Data</TALLYREQUEST>
        </HEADER>
        <BODY>
        <IMPORTDATA>
        <REQUESTDESC>
        <REPORTNAME>All Masters</REPORTNAME>
        <STATICVARIABLES>
        <SVCURRENTCOMPANY>Arkefilters</SVCURRENTCOMPANY>
        </STATICVARIABLES>
        <REQUESTDATA>
        <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <UNIT NAME="Packets" RESERVEDNAME="">
        <NAME>kilograms</NAME>
        <GUID>f5baa156-7f6e-4a48-8ff1-ab4bd8fc0370-00003439</GUID>
        <GSTREPUOM>BDL-BUNDLES</GSTREPUOM>
        <ISUPDATINGTARGETID>No</ISUPDATINGTARGETID>
        <ASORIGINAL>Yes</ASORIGINAL>
        <ISGSTEXCLUDED>No</ISGSTEXCLUDED>
        <ISSIMPLEUNIT>Yes</ISSIMPLEUNIT>
        <ALTERID> 12068</ALTERID>
        </UNIT>
        </TALLYMESSAGE>
        </REQUESTDATA>
        </IMPORTDATA>
        </BODY>
        </ENVELOPE>        
        """
#         f.write(s)
#         f = open('/home/arke-it03/getData.xml','r') 
#         a =f.read()
        a = s.replace('&#4;', '')
        f.write(a)
        f.close()
        return f

    def deleteTempFile(self):
        if os.path.exists("/home/gourav/odoo/qa1/odoo/getData.xml"):
            os.remove("/home/gourav/odoo/qa1/odoo/getData.xml")
        return True
    
    @api.one
    def tally_main(self):

        form_obj = self.env['tally.connection']
        company = self.company
        daybook = self.daybook
        print("Company-----",company)

        def _processData(s):
            f = self.createTempFile(s)
            configdict = etree_paser.ConvertXmlToDict(f.name)
            if not configdict:
                return {}
            tallyData = dict(configdict)
            
            print('TallyData',tallyData)
            com = self.company
            obj_migrator = self.env['migrator'].insertData(com,tallyData)
#             self.deleteTempFile()
        
        if self.ledgers:
            print('Entered in Ledgers')
            s = self.getData("Ledgers")
            _processData(s)
        elif self.groups:
            s = self.getData("Groups")
            _processData(s)
            
        if self.vouchers:
            s = self.getVouchers("Sales Vouchers")
#             s = self.getData("Ledgers")
#             _processData(s)

            f = self.createTempFile(s)
            configdict = etree_paser.ConvertXmlToDict(f.name)
            if not configdict:
                return {}
            tallyData = dict(configdict)
            obj_voucher = self.env['voucher']
            obj_voucher.insertVoucherData(company, tallyData)

#         if self.inventory_master:
#             s = self.getData("All Inventory Masters")
#             _processData(s)    
        elif self.stock_items:
            s = self.getData("Stock Items")
            _processData(s)    
        elif self.stock_groups:
            s = self.getData("Stock Groups")
            _processData(s)

        if self.units and not self.stock_items :
            print('Entered in Units')
            s = self.getData("Units")
            _processData(s)
        
        # if self.godowns:
        #     s = self.getData("Godowns")
        #     _processData(s)
            
#         if self.employees:
#             s = self.getData("Employees")
#             _processData(s)
                    
        return {}   

TallyConnection()

class Partner(models.Model):
    _inherit = 'res.partner'

    @api.multi
    def _compute_bank_count(self):
        bank_data = self.env['res.partner.bank'].read_group([('partner_id', 'in', self.ids)], ['partner_id'],
                                                            ['partner_id'])
        mapped_data = dict([(bank['partner_id'][0], bank['partner_id_count']) for bank in bank_data])
        for partner in self:
            partner.bank_account_count = mapped_data.get(partner.id, 0)
    
    from_tally = fields.Boolean('Migrated From Tally')
    # avinash:02/12/20 Commented and remove store true becasue of this on vendor form count bank account functionality is not working
    # bank_account_count = fields.Integer(compute='_compute_bank_count', string="Bank",store=True,default=False)
    bank_account_count = fields.Integer(compute='_compute_bank_count', string="Bank")
    # end avinash
    created_in_tally = fields.Boolean('Created in Tally', default=False)
    
class AccountMove(models.Model):
    _inherit = "account.move"
    
    from_tally = fields.Boolean('Migrated From Tally')
    tally_guid = fields.Char('Tally GUID')
    altered_in_tally = fields.Boolean('Altered in Tally', default=False)
    created_in_tally = fields.Boolean('Created in Tally', default=False)
    
class AccountVoucher(models.Model):
    _inherit = 'account.voucher'

    from_tally = fields.Boolean('Migrated From Tally')
    tally_guid = fields.Char('Tally GUID')
    created_in_tally = fields.Boolean('Created in Tally', default=False)

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    from_tally = fields.Boolean('Migrated From Tally')
    tally_guid = fields.Char('Tally GUID')
    created_in_tally = fields.Boolean('Created in Tally', default=False)

class ProductProduct(models.Model):
    _inherit = 'product.product'

    from_tally = fields.Boolean('Migrated From Tally')
    tally_guid = fields.Char('Tally GUID')
    created_in_tally = fields.Boolean('Created in Tally', default=False)

class ProductUOM(models.Model):
    _inherit = 'product.uom'

    from_tally = fields.Boolean('Migrated From Tally')
    tally_guid = fields.Char('Tally GUID')
    created_in_tally = fields.Boolean('Created in Tally', default=False)

class ProductCategory(models.Model):
    _inherit = 'product.category'

    from_tally = fields.Boolean('Migrated From Tally')
    tally_guid = fields.Char('Tally GUID')
    created_in_tally = fields.Boolean('Created in Tally', default=False)

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    created_in_tally = fields.Boolean('Created in Tally', default=False)

class AccountAccount(models.Model):
    _inherit = 'account.account'

    from_tally = fields.Boolean('Migrated From Tally')
    tally_guid = fields.Char('Tally GUID')
    created_in_tally = fields.Boolean('Created in Tally', default=False)

class AccountInvoice(models.Model):
    _inherit = "account.invoice"

    from_tally = fields.Boolean('Migrated From Tally')
    tally_guid = fields.Char('Tally GUID')
    created_in_tally = fields.Boolean('Created in Tally', default=False)

class AccountGroup(models.Model):
    _inherit = "account.group"

    from_tally = fields.Boolean('Migrated From Tally')
    tally_guid = fields.Char('Tally GUID')
    created_in_tally = fields.Boolean('Created in Tally', default=False)

class Inventory(models.Model):
    _inherit = "stock.inventory"

    from_tally = fields.Boolean('Migrated From Tally')
    tally_guid = fields.Char('Tally GUID')
    created_in_tally = fields.Boolean('Created in Tally', default=False)

class Issues(models.Model):
    _inherit = "stock.issues"

    from_tally = fields.Boolean('Migrated From Tally')
    tally_guid = fields.Char('Tally GUID')
    created_in_tally = fields.Boolean('Created in Tally', default=False)

class AccountAccountType(models.Model):
    _inherit = "account.account.type"

    from_tally = fields.Boolean('Migrated From Tally')
    tally_guid = fields.Char('Tally GUID')
    created_in_tally = fields.Boolean('Created in Tally', default=False)












    
    
    
