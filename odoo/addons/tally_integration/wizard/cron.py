from odoo import api, fields, models, _
import os
from odoo.exceptions import UserError
from . import etree_paser
from . import migrator
# from . import connection
import requests


class TallyCronJob(models.Model):
    
    _name = 'tally.cron.job'
    _description = 'Tally Cron Jobs'
    _inherit = 'tally.connection'
    
    @api.multi
    def getVouchers(self,reportType):
        print("Vouchers Report Type======",reportType)
        url = 'http://localhost:9000'
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
        url = 'http://localhost:9000'
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
        f = open('/home/arke-it03/getData.xml','w+') 
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
        </REQUESTDESC>
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
        if os.path.exists("/home/arke-it03/getData.xml"):
            os.remove("/home/arke-it03/getData.xml")
        return True
    
    @api.model
    def tally_groups(self):
        form_obj = self.env['tally.connection']
        company = self.env['res.company'].search([])[0]
        daybook = self.daybook
                
        def _processData(s):
            f = self.createTempFile(s)
            configdict = etree_paser.ConvertXmlToDict(f.name)
            if not configdict:
                return {}
            tallyData = dict(configdict)
            com = self.env['res.company'].search([])[0]
            obj_migrator = self.env['migrator'].insertData(com,tallyData)
        s = self.getData("Groups")
        _processData(s)    
        return {}   
    
    @api.model
    def tally_ledgers(self):
        form_obj = self.env['tally.connection']
        company = self.env['res.company'].search([])[0]
        daybook = self.daybook
                
        def _processData(s):
            f = self.createTempFile(s)
            configdict = etree_paser.ConvertXmlToDict(f.name)
            if not configdict:
                return {}
            tallyData = dict(configdict)
            com = self.env['res.company'].search([])[0]
            obj_migrator = self.env['migrator'].insertData(com,tallyData)
        s = self.getData("Ledgers")
        _processData(s)    
        return {} 
    
    @api.model
    def tally_vouchers(self):
        print('VOUCHERS++++++')
        form_obj = self.env['tally.connection']
        company = self.env['res.company'].search([])[0]

        s = self.getVouchers("Sales Vouchers")
        f = self.createTempFile(s)
        configdict = etree_paser.ConvertXmlToDict(f.name)
        if not configdict:
            return {}
        tallyData = dict(configdict)
        obj_voucher = self.env['voucher']
        obj_voucher.insertVoucherData(company, tallyData)

        return {} 
    
    @api.model
    def tally_godowns(self):
        form_obj = self.env['tally.connection']
        company = self.env['res.company'].search([])[0]
        daybook = self.daybook
                
        def _processData(s):
            f = self.createTempFile(s)
            configdict = etree_paser.ConvertXmlToDict(f.name)
            if not configdict:
                return {}
            tallyData = dict(configdict)
            com = self.env['res.company'].search([])[0]
            obj_migrator = self.env['migrator'].insertData(com,tallyData)
        s = self.getData("Godowns")
        _processData(s)    
        return {}
    
    @api.model
    def tally_uom(self):
        form_obj = self.env['tally.connection']
        company = self.env['res.company'].search([])[0]
                
        def _processData(s):
            f = self.createTempFile(s)
            configdict = etree_paser.ConvertXmlToDict(f.name)
            if not configdict:
                return {}
            tallyData = dict(configdict)
            com = self.env['res.company'].search([])[0]
            obj_migrator = self.env['migrator'].insertData(com,tallyData)
        s = self.getData("Units")
        _processData(s)    
        return {}
    
    @api.model
    def tally_StockGroups(self):
        form_obj = self.env['tally.connection']
        company = self.env['res.company'].search([])[0]
                
        def _processData(s):
            f = self.createTempFile(s)
            configdict = etree_paser.ConvertXmlToDict(f.name)
            if not configdict:
                return {}
            tallyData = dict(configdict)
            com = self.env['res.company'].search([])[0]
            obj_migrator = self.env['migrator'].insertData(com,tallyData)
        s = self.getData("Stock Groups")
        _processData(s)    
        return {}
    
    @api.model
    def tally_StockItems(self):
        form_obj = self.env['tally.connection']
        company = self.env['res.company'].search([])[0]
                
        def _processData(s):
            f = self.createTempFile(s)
            configdict = etree_paser.ConvertXmlToDict(f.name)
            if not configdict:
                return {}
            tallyData = dict(configdict)
            com = self.env['res.company'].search([])[0]
            obj_migrator = self.env['migrator'].insertData(com,tallyData)
        s = self.getData("Stock Items")
        _processData(s)    
        return {}
    
TallyCronJob()




    
    
    
