from odoo import api, fields, models, _
from odoo.exceptions import UserError

import urllib.request
from urllib.request import urlopen
import http.client
import requests,base64,io
from urllib import request, parse
from datetime import datetime
from xml.etree import ElementTree as ET

class TestConnection(models.Model):
    _name = 'test.connection'

    def _get_default_url(self):
        tally_url = self.env['ir.config_parameter'].sudo().get_param('tally.url')
        if tally_url:
            return tally_url
        else:
            return 'http://192.168.2.77:9000'

    def _check_and_opt(self,name):
        #print("heeeeeeeeeeeeeeeeeeeeeeeeeeeelo",name)
        if name:
            if(name.find('&') != -1):
                name=name.replace("&","&amp;")
                ##print("in 1111111111111111111111",name)
                return name
            else:
                #print("in 222222222222222", name)
                return name
        else:
            #print("in 222222222222222",name)
            return name

 
    # url = fields.Char('Tally URL With Port', size=256, required=True,default = lambda * a:'http://localhost:9000')
    url = fields.Char('Tally URL With Port', size=256, required=True, default=_get_default_url)
    company = fields.Many2one("res.company", string="Migrate Data from Company",
                              default=lambda self: self.env['res.company']._company_default_get('account.invoice'))
    daybook = fields.Char(string='Path To DayBook', size=256,
                    help='Export the DayBook in XML Format, and give the path of DayBook.xml file.',
                    default = '/home/mdi/.wine/dosdevices/c:/Tally/DayBook.xml')
    ledgers = fields.Boolean(string='Ledgers')
    groups = fields.Boolean(string='Groups')
    vouchers = fields.Boolean(string='Vouchers')
    invoices = fields.Boolean(string='Invoices')
    product_master=fields.Boolean(string='Masters')
    accounts_master=fields.Boolean(string='Masters')
    accounts_vouchers=fields.Boolean(string='Vouchers/Invoices')
#     inventory_master = fields.Boolean(string='All Inventory Masters')
    stock_items = fields.Boolean(string='Stock Items')
    stock_groups = fields.Boolean(string='Stock Groups', help="Godowns (Warehouses)")
    units = fields.Boolean(string='Unit of Measure')
    tally_company = fields.Char(string="Migrate Data into Tally Company")
    tally_transfer_type = fields.Boolean()
    stock_journal = fields.Boolean(string='Stock Up/Consumption')

#     employees = fields.Boolean(string='Employees')
#     godowns = fields.Boolean(string='Godowns')


    # @api.onchange('to_download_master')
    # def master_xml_check(self):
    #     if self.to_download_master:
    #         fl = open("masters.xml", "rb")
    #         fk = open("vouchers.xml", "rb")
    #         fstring = fl.read()
    #         fkstring = fk.read()
    #         self.master_xml=base64.b64encode(fstring)
    #         self.voucher_xml=base64.b64encode(fkstring)
    #         self.master_name="master.xml"
    #         self.voucher_name="voucher.xml"
    #         fl.close()
    #         fk.close()

    @api.onchange('company')
    def transfer_type(self):
        get_param = self.env['ir.config_parameter'].sudo().get_param('tally_validations.tally_transfer_type')
        #print('get_paramget_paramget_paramget_param',get_param)
        if get_param =='account_wise':
            self.tally_transfer_type=True
            #print("hellohellohellohellohellohellohellohellohellohellohellohellohellohellohello",self.tally_transfer_type)
        elif get_param=='product_wise':
            self.tally_transfer_type=False
        else:
            self.tally_transfer_type = True

    @api.multi
    def xml_read(self):
        create_xml = False
        if self.accounts_vouchers:
            if self.tally_transfer_type==True:
                self.vouchers=True
            else:
                self.vouchers = True
                self.invoices= True
                self.stock_journal=True
        if self.accounts_master:
            self.ledgers=True
            self.groups=True
        if self.product_master:
            self.stock_items=True
            self.stock_groups=True
            self.units=True

        url = self.url
        tally_transfer_type=self.tally_transfer_type
        if self.company:
            company = self.company
        else:
            company = self.env.user.company_id.id
        tally_company = self.tally_company
        if self.units:
            print("Units Entry")
            # uom = self.env['product.uom'].search([])
            #uom = self.env['product.uom'].search([('company_id', '=', company.id), ('created_in_tally', '=', False)],
             #                                    order='id')
            uom = self.env['product.uom'].search([('company_id','=',company.id)],order='id')
            print("uommmmmmmmmmmmm", uom)

            # print ("len of uommmmmmmmmm",len(uom))
            tally_company = tally_company
            tally_company = self._check_and_opt(tally_company)
            print("tally_companyyyyyyyyyyyyyyyyy", tally_company)

            for line in uom:
                # print ("line of uommmmmmmmmmmm",line)
                uomName = line.name
                uomName = self._check_and_opt(uomName)
                print("uooooooooooooooooo", uomName)
                # GUID = str(00) + str(line.id)
                # print("GUID====", GUID)
                #GUID ='uom'+ uomName
                # if line.tally_guid:
                #     GUID =line.tally_guid
                # else:
                #     GUID = 'uom'+uomName
                params = """
                    <?xml version='1.0' encoding='utf-8'?>
                    <ENVELOPE>
                    <HEADER>
                    <TALLYREQUEST>Import Data</TALLYREQUEST>
                    </HEADER>
                    <BODY>
                    <IMPORTDATA>
                    <REQUESTDESC>
                    <REPORTNAME>All Masters</REPORTNAME>
                    <STATICVARIABLES>
                    <SVCURRENTCOMPANY>""" + tally_company + """</SVCURRENTCOMPANY>
                    </STATICVARIABLES>
                    </REQUESTDESC>
                    <REQUESTDATA>
                    <TALLYMESSAGE xmlns:UDF="TallyUDF">
                    <UNIT NAME="" REMOTEID="" RESERVEDNAME="">
                    <NAME>""" + uomName + """</NAME>

                    <GUID></GUID>
                    <GSTREPUOM></GSTREPUOM>
                    <ISUPDATINGTARGETID>No</ISUPDATINGTARGETID>
                    <ASORIGINAL>Yes</ASORIGINAL>
                    <ISGSTEXCLUDED>No</ISGSTEXCLUDED>
                    <ISSIMPLEUNIT>Yes</ISSIMPLEUNIT>
                    <ALTERID></ALTERID>
                    </UNIT>
                    </TALLYMESSAGE>
                    </REQUESTDATA>
                    </IMPORTDATA>
                    </BODY>
                    </ENVELOPE>
                     """

                print('hello try', params)
                print('url', url)
                res = requests.post(url, data=params, headers={'Content-Type': 'application/xml'})
                print("hello", res)
                root = ET.fromstring(res.content)
                # print("root",root)
                # print("root[0]",root[0])
                print("res.content", res.content)
                print("lengroot",len(root))
                created_in_tally = False
                altered_in_tally = False
                if len(root) > 9:
                    if root[0].tag == 'LINEERROR':
                        altered_in_tally = False
                        sync_dict = {}
                        sync_dict = {
                            'object': 'product.uom',
                            'name': 'Product UOM',
                            'total_records': 1,
                            'record_name': line.name,
                            'log_date': datetime.now(),
                            'reason': root[0].text,
                            # 'no_imported': 1,
                        }
                        self.env['sync.logs'].create(sync_dict)
                    if root[1].tag == 'CREATED':
                        if root[1].text == '1':
                            created_in_tally = True
                    line.write({'created_in_tally': created_in_tally})
                else:
                    print("elseeeeeeeeeee", root[0].tag)
                    if root[0].tag == 'CREATED':
                        print("root[0].text", root[0].text)
                        if root[0].text == '1':
                            created_in_tally = True
                    # print("line and altred ,createddd", line, altered_in_tally, created_in_tally)
                    line.write({'created_in_tally': created_in_tally})

        if self.stock_groups:
            print("Stock Groups Entry")
            self.env['stock.groups'].create_stockGroups(url,company,tally_company,create_xml)
        if self.stock_items:
            print("Stock Item Entry")
            self.env['stock.item'].create_stockItem(url,company,tally_company,create_xml)
        if self.groups:
            print("Account Group Entry")
            self.env['account.group.import'].create_AccountGroups(url,company,tally_company,create_xml)
        if self.ledgers:
            print("Ledger Entry")
            self.env['account.ledger'].create_ledger(url,company,tally_company,create_xml)
        if self.vouchers:
            print("Voucher Entry")
            self.env['account.voucher.import'].create_voucher(url,company,tally_company,tally_transfer_type,create_xml)
        if self.invoices:
            print("Account invoices Entry")
            self.env['account.invoices.import'].create_AccountInvoices(url, company, tally_company,create_xml)
        if self.stock_journal:
            print("Heelo")
            self.env['stock.journal.import'].create_StockJournal(url, company, tally_company, create_xml)

        print ('+++HELLO Tally +++')

        return True

    @api.multi
    def xml_create(self):
        url = self.url
        create_xml= True
        if self.accounts_vouchers:
            if self.tally_transfer_type==True:
                self.vouchers=True
            else:
                self.vouchers = True
                self.invoices= True
                self.stock_journal=True
        if self.accounts_master:
            self.ledgers=True
            self.groups=True
        if self.product_master:
            self.stock_items=True
            self.stock_groups=True
            self.units=True
        print("Time at start",datetime.now())
        f = open("masters.xml", "w+")
        f.close()
        f = open("vouchers.xml", "w+")
        f.close()
        print("Time at xml read",datetime.now())
        tally_transfer_type = self.tally_transfer_type
        if self.company:
            company = self.company
        else:
            company = self.env.user.company_id.id
        tally_company = self.tally_company
        print("Time at units start",datetime.now())
        if self.units:
            #print("Units Entry")
            #f = open("uomdata.xml", "r")
            # uom = self.env['product.uom'].search([])
            # uom = self.env['product.uom'].search([('company_id', '=', company.id), ('created_in_tally', '=', False)],
            #                                      order='id')
            #uom = self.env['product.uom'].search([('company_id', '=', company.id), ('created_in_tally', '=', False)], order='id')
            uom = self.env['product.uom'].search([('company_id', '=', company.id)], order='id')
            #print("uommmmmmmmmmmmm", uom)

            # print ("len of uommmmmmmmmm",len(uom))
            tally_company = tally_company
            tally_company = self._check_and_opt(tally_company)
            #print("tally_companyyyyyyyyyyyyyyyyy", tally_company)

            for line in uom:
                # print ("line of uommmmmmmmmmmm",line)
                uomName = line.name
                uomName = self._check_and_opt(uomName)
                #print("uooooooooooooooooo", uomName)
                # GUID = str(00) + str(line.id)
                # print("GUID====", GUID)
                # if line.tally_guid:
                #     GUID =line.tally_guid
                # else:
                #     GUID = 'uom'+uomName

                params = """
                        <?xml version='1.0' encoding='utf-8'?>
                        <ENVELOPE>
                        <HEADER>
                        <TALLYREQUEST>Import Data</TALLYREQUEST>
                        </HEADER>
                        <BODY>
                        <IMPORTDATA>
                        <REQUESTDESC>
                        <REPORTNAME>All Masters</REPORTNAME>
                        <STATICVARIABLES>
                        <SVCURRENTCOMPANY>""" + tally_company + """</SVCURRENTCOMPANY>
                        </STATICVARIABLES>
                        </REQUESTDESC>
                        <REQUESTDATA>
                        <TALLYMESSAGE xmlns:UDF="TallyUDF">
                        <UNIT NAME="" REMOTEID="" RESERVEDNAME="">
                        <NAME>""" + uomName + """</NAME>

                        <GUID></GUID>
                        <GSTREPUOM></GSTREPUOM>
                        <ISUPDATINGTARGETID>No</ISUPDATINGTARGETID>
                        <ASORIGINAL>Yes</ASORIGINAL>
                        <ISGSTEXCLUDED>No</ISGSTEXCLUDED>
                        <ISSIMPLEUNIT>Yes</ISSIMPLEUNIT>
                        <ALTERID></ALTERID>
                        </UNIT>
                        </TALLYMESSAGE>
                        </REQUESTDATA>
                        </IMPORTDATA>
                        </BODY>
                        </ENVELOPE>
                         """

               # print('hello try', params)
                if create_xml:
                    f = open("masters.xml", "a+")
                    f.write(params)
                    f.close()
                    created_in_tally=True
                    line.write({'created_in_tally': created_in_tally})

        print("Time at groups start",datetime.now())
        if self.stock_groups:
            #print("Stock Groups Entry")
            self.env['stock.groups'].create_stockGroups(url, company, tally_company,create_xml)
        print("Time at items start",datetime.now())
        if self.stock_items:
            #print("Stock Item Entry")
            self.env['stock.item'].create_stockItem(url, company, tally_company,create_xml)
        print("Time at acc_groups start",datetime.now())
        if self.groups:
            print("Account Group Entry")
            self.env['account.group.import'].create_AccountGroups(url, company, tally_company,create_xml)
        print("Time at acc_ledgers start",datetime.now())
        if self.ledgers:
            print("Ledger Entry")
            self.env['account.ledger'].create_ledger(url, company, tally_company,create_xml)
        print("Time at acc_vouchers start",datetime.now())
        if self.vouchers:
            print("Voucher Entry")
            self.env['account.voucher.import'].create_voucher(url, company, tally_company, tally_transfer_type,create_xml)
        if self.invoices:
            print("Account invoices Entry")
            self.env['account.invoices.import'].create_AccountInvoices(url, company, tally_company,create_xml)
        if self.stock_journal:
            print("Heelo")
            self.env['stock.journal.import'].create_StockJournal(url, company, tally_company, create_xml)

        #print('+++HELLO Tally +++')
        print("Time at import end",datetime.now())
        template = self.env.ref('tally_integration.save_file_wizard_migrate_data_to_xml')
        fl = open("masters.xml", "rb")
        fk = open("vouchers.xml", "rb")
        fstring = fl.read()
        fkstring =fk.read()
        valu={'master_xml': base64.b64encode(fstring),
                       'master_name':'master.xml',
                       'voucher_xml':base64.b64encode(fkstring),
                       'voucher_name':'vouchers.xml'
                        }
        my_file=self.env['save.file.wizard'].create(valu)

        #binary= base64.encodestring(fstring)
        print("Time at wizard start",datetime.now())
        wizard={
            'name': _('Download Xml'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'res_id': my_file.id,
            'view_mode': 'form',
            'res_model': 'save.file.wizard',
            'view_id': template.id,
            'target': 'new',
            # 'context':{
                # 'default_to_download_master': True,
                # 'default_master_xml': base64.b64encode(fstring),
                #        'default_master_name':'master.xml',
                #        'default_voucher_xml':base64.b64encode(fkstring),
                #        'default_voucher_name':'vouchers.xml'
                #         },
        }
        fl.close()
        fk.close()
        print("Time at wizard end",datetime.now())
        return wizard


    def import_tally_uom(self,company,tally_company,url):
        print("Units Entry")
        # uom = self.env['product.uom'].search([])
        # uom = self.env['product.uom'].search([('company_id', '=', company.id), ('created_in_tally', '=', False)],
        #                                      order='id')
        uom = self.env['product.uom'].search([('company_id', '=', company.id)], order='id')
        print("uommmmmmmmmmmmm", uom)

        # print ("len of uommmmmmmmmm",len(uom))
        tally_company = tally_company
        tally_company = self._check_and_opt(tally_company)
        print("tally_companyyyyyyyyyyyyyyyyy", tally_company)

        for line in uom:
            # print ("line of uommmmmmmmmmmm",line)
            uomName = line.name
            uomName = self._check_and_opt(uomName)
            print("uooooooooooooooooo", uomName)
            # GUID = str(00) + str(line.id)
            # print("GUID====", GUID)
            # GUID ='uom'+ uomName
            # if line.tally_guid:
            #     GUID = line.tally_guid
            # else:
            #     GUID = 'uom' + uomName
            params = """
                            <?xml version='1.0' encoding='utf-8'?>
                            <ENVELOPE>
                            <HEADER>
                            <TALLYREQUEST>Import Data</TALLYREQUEST>
                            </HEADER>
                            <BODY>
                            <IMPORTDATA>
                            <REQUESTDESC>
                            <REPORTNAME>All Masters</REPORTNAME>
                            <STATICVARIABLES>
                            <SVCURRENTCOMPANY>""" + tally_company + """</SVCURRENTCOMPANY>
                            </STATICVARIABLES>
                            </REQUESTDESC>
                            <REQUESTDATA>
                            <TALLYMESSAGE xmlns:UDF="TallyUDF">
                            <UNIT NAME="" REMOTEID="" RESERVEDNAME="">
                            <NAME>""" + uomName + """</NAME>
                            <GUID></GUID>
                            <GSTREPUOM></GSTREPUOM>
                            <ISUPDATINGTARGETID>No</ISUPDATINGTARGETID>
                            <ASORIGINAL>Yes</ASORIGINAL>
                            <ISGSTEXCLUDED>No</ISGSTEXCLUDED>
                            <ISSIMPLEUNIT>Yes</ISSIMPLEUNIT>
                            <ALTERID></ALTERID>
                            </UNIT>
                            </TALLYMESSAGE>
                            </REQUESTDATA>
                            </IMPORTDATA>
                            </BODY>
                            </ENVELOPE>
                             """

            print('hello try', params)
            print('url', url)
            res = requests.post(url, data=params, headers={'Content-Type': 'application/xml'})
            print("hello", res)
            root = ET.fromstring(res.content)
            # print("root",root)
            # print("root[0]",root[0])
            print("res.content", res.content)
            print("lengroot", len(root))
            created_in_tally = False
            altered_in_tally = False
            if len(root) > 9:
                if root[0].tag == 'LINEERROR':
                    altered_in_tally = False
                    sync_dict = {}
                    sync_dict = {
                        'object': 'product.uom',
                        'name': 'Product UOM',
                        'total_records': 1,
                        'record_name': line.name,
                        'log_date': datetime.now(),
                        'reason': root[0].text,
                        # 'no_imported': 1,
                    }
                    self.env['sync.logs'].create(sync_dict)
                if root[1].tag == 'CREATED':
                    if root[1].text == '1':
                        created_in_tally = True
                line.write({'created_in_tally': created_in_tally})
            else:
                if root[0].tag == 'CREATED':
                    print("root[0].text", root[0].text)
                    if root[0].text == '1':
                        created_in_tally = True
                # print("line and altred ,createddd", line, altered_in_tally, created_in_tally)
                line.write({'created_in_tally': created_in_tally})


    #Auto scheduler function to import odoo to tally by pushkal on : 29 Feb 20: starts here

    @api.multi
    def auto_import_odoo_to_tally(self):
        company_ids = self.env['res.company'].search([('tally_migration','=',True)])
        create_xml =False
        tally_transfer_type = self.tally_transfer_type
        if len(company_ids):
            for val in company_ids:
                print("vallllllllllll",val)
                if val.tally_company_id and val.auto_import_tally and val.auto_import_tally_url:
                    url = val.auto_import_tally_url
                    self.import_tally_uom(val,val.tally_company_id.name,url)
                    self.env['stock.groups'].create_stockGroups(url,val,val.tally_company_id.name,create_xml)
                    self.env['stock.item'].create_stockItem(url,val,val.tally_company_id.name,create_xml)
                    self.env['account.group.import'].create_AccountGroups(url,val,val.tally_company_id.name,create_xml)
                    self.env['account.ledger'].create_ledger(url,val,val.tally_company_id.name,create_xml)
                    self.env['account.voucher.import'].create_voucher(url,val,val.tally_company_id.name,tally_transfer_type,create_xml)
                    self.env['account.invoices.import'].create_AccountInvoices(url,val,val.tally_company_id.name, create_xml)
                    self.env['stock.journal.import'].create_StockJournal(url, val, val.tally_company_id.name, create_xml)

    # Auto scheduler function to import odoo to tally by pushkal on : 29 Feb 20: ends here

class SaveFileWizard(models.TransientModel):
    _name='save.file.wizard'

    master_xml = fields.Binary(string="Master Xml", readonly=True)
    to_download_master = fields.Boolean(string="Get Masters")
    master_name = fields.Char(string="Name")
    voucher_name = fields.Char(string="Name")
    voucher_xml = fields.Binary(string="Voucher Xml")






    
    
    
    
    