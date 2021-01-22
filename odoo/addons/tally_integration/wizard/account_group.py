from odoo import api, fields, models, _
from odoo.exceptions import UserError
import requests
from datetime import datetime
from xml.etree import ElementTree as ET


class AccountGroup(models.Model):
    _name = 'account.group.import'
    
    @api.multi
    def create_AccountGroups(self,url,company,tally_company,create_xml):
        print('==Create Account Groups==',url)
        #f = open("masters.xml", "w+")
        # group = self.env['account.account'].search([])
        #group = self.env['account.account'].search([('company_id','=',company.id)],order='id')
        tally_company = tally_company
        tally_company = self.env['test.connection']._check_and_opt(tally_company)
        prim_group = self.env['account.account.type'].search([], order='id')
        for line in prim_group:
            grpName = line.name
            grpName = self.env['test.connection']._check_and_opt(grpName)
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
                                    <GROUP NAME="" RESERVEDNAME="">
                                    <GUID></GUID>
                                    <PARENT/>
                                    <BASICGROUPISCALCULABLE>No</BASICGROUPISCALCULABLE>
                                    <ADDLALLOCTYPE/>
                                    <GRPDEBITPARENT/>
                                    <GRPCREDITPARENT/>
                                    <ISBILLWISEON>No</ISBILLWISEON>
                                    <ISCOSTCENTRESON>No</ISCOSTCENTRESON>
                                    <ISADDABLE>No</ISADDABLE>
                                    <ISUPDATINGTARGETID>No</ISUPDATINGTARGETID>
                                    <ASORIGINAL>Yes</ASORIGINAL>
                                    <ISSUBLEDGER>No</ISSUBLEDGER>
                                    <ISREVENUE>No</ISREVENUE>
                                    <AFFECTSGROSSPROFIT>No</AFFECTSGROSSPROFIT>
                                    <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
                                    <TRACKNEGATIVEBALANCES>Yes</TRACKNEGATIVEBALANCES>
                                    <ISCONDENSED>No</ISCONDENSED>
                                    <AFFECTSSTOCK>No</AFFECTSSTOCK>
                                    <ISGROUPFORLOANRCPT>No</ISGROUPFORLOANRCPT>
                                    <ISGROUPFORLOANPYMNT>No</ISGROUPFORLOANPYMNT>
                                    <ISRATEINCLUSIVEVAT>No</ISRATEINCLUSIVEVAT>
                                    <ISINVDETAILSENABLE>No</ISINVDETAILSENABLE>
                                    <SORTPOSITION> 500</SORTPOSITION>
                                    <ALTERID/>
                                    <SERVICETAXDETAILS.LIST>      </SERVICETAXDETAILS.LIST>
                                    <VATDETAILS.LIST>      </VATDETAILS.LIST>
                                    <SALESTAXCESSDETAILS.LIST>      </SALESTAXCESSDETAILS.LIST>
                                    <GSTDETAILS.LIST>      </GSTDETAILS.LIST>
                                    <LANGUAGENAME.LIST>
                                    <NAME.LIST TYPE="String">
                                    <NAME>""" + grpName + """</NAME>
                                    </NAME.LIST>
                                    <LANGUAGEID> 1033</LANGUAGEID>
                                    </LANGUAGENAME.LIST>
                                    <XBRLDETAIL.LIST>      </XBRLDETAIL.LIST>
                                    <AUDITDETAILS.LIST>      </AUDITDETAILS.LIST>
                                    <SCHVIDETAILS.LIST>      </SCHVIDETAILS.LIST>
                                    <EXCISETARIFFDETAILS.LIST>      </EXCISETARIFFDETAILS.LIST>
                                    <TCSCATEGORYDETAILS.LIST>      </TCSCATEGORYDETAILS.LIST>
                                    <TDSCATEGORYDETAILS.LIST>      </TDSCATEGORYDETAILS.LIST>
                                    <GSTCLASSFNIGSTRATES.LIST>      </GSTCLASSFNIGSTRATES.LIST>
                                    <EXTARIFFDUTYHEADDETAILS.LIST>      </EXTARIFFDUTYHEADDETAILS.LIST>
                                    </GROUP>
                                    </TALLYMESSAGE>
                                    </REQUESTDATA>
                                    </IMPORTDATA>
                                    </BODY>
                                    </ENVELOPE>
                                 """
            print("paramsparamsparamsparamsparamsparamsparams", params)
            if create_xml:
                f = open("masters.xml", "a+")
                f.write(params)
                f.close()
                created_in_tally = True
                line.write({'created_in_tally': created_in_tally})
            else:
                res = requests.post(url, data=params, headers={'Content-Type': 'application/xml'})
                root = ET.fromstring(res.content)
                print("root", root)

                print("rres.content", res.content)
                created_in_tally = False
                altered_in_tally = False
                if len(root) > 9:
                    if root[0].tag == 'LINEERROR':
                        altered_in_tally = False
                        sync_dict = {}
                        sync_dict = {
                            'object': 'account.account.type',
                            'name': 'Account Groups',
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

                else:
                    print("elseeeeeeeeeee", root[0].tag)
                    if root[0].tag == 'CREATED':
                        print("root[0].text", root[0].text)
                        if root[0].text == '1':
                            created_in_tally = True
                    # print("line and altred ,createddd", line, altered_in_tally, created_in_tally)


        sec_group=self.env['account.group'].search([], order='id')
        for line in sec_group:
            grpName = line.name
            grpName = self.env['test.connection']._check_and_opt(grpName)
            parent=''
            if line.account_type_id:
                parent=line.account_type_id.name
                parent = self.env['test.connection']._check_and_opt(parent)
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
                                    <GROUP NAME="" RESERVEDNAME="">
                                    <GUID></GUID>
                                    <PARENT>"""+parent+"""</PARENT>
                                    <BASICGROUPISCALCULABLE>No</BASICGROUPISCALCULABLE>
                                    <ADDLALLOCTYPE/>
                                    <GRPDEBITPARENT/>
                                    <GRPCREDITPARENT/>
                                    <ISBILLWISEON>No</ISBILLWISEON>
                                    <ISCOSTCENTRESON>No</ISCOSTCENTRESON>
                                    <ISADDABLE>No</ISADDABLE>
                                    <ISUPDATINGTARGETID>No</ISUPDATINGTARGETID>
                                    <ASORIGINAL>Yes</ASORIGINAL>
                                    <ISSUBLEDGER>No</ISSUBLEDGER>
                                    <ISREVENUE>No</ISREVENUE>
                                    <AFFECTSGROSSPROFIT>No</AFFECTSGROSSPROFIT>
                                    <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
                                    <TRACKNEGATIVEBALANCES>Yes</TRACKNEGATIVEBALANCES>
                                    <ISCONDENSED>No</ISCONDENSED>
                                    <AFFECTSSTOCK>No</AFFECTSSTOCK>
                                    <ISGROUPFORLOANRCPT>No</ISGROUPFORLOANRCPT>
                                    <ISGROUPFORLOANPYMNT>No</ISGROUPFORLOANPYMNT>
                                    <ISRATEINCLUSIVEVAT>No</ISRATEINCLUSIVEVAT>
                                    <ISINVDETAILSENABLE>No</ISINVDETAILSENABLE>
                                    <SORTPOSITION> 500</SORTPOSITION>
                                    <ALTERID/>
                                    <SERVICETAXDETAILS.LIST>      </SERVICETAXDETAILS.LIST>
                                    <VATDETAILS.LIST>      </VATDETAILS.LIST>
                                    <SALESTAXCESSDETAILS.LIST>      </SALESTAXCESSDETAILS.LIST>
                                    <GSTDETAILS.LIST>      </GSTDETAILS.LIST>
                                    <LANGUAGENAME.LIST>
                                    <NAME.LIST TYPE="String">
                                    <NAME>""" + grpName + """</NAME>
                                    </NAME.LIST>
                                    <LANGUAGEID> 1033</LANGUAGEID>
                                    </LANGUAGENAME.LIST>
                                    <XBRLDETAIL.LIST>      </XBRLDETAIL.LIST>
                                    <AUDITDETAILS.LIST>      </AUDITDETAILS.LIST>
                                    <SCHVIDETAILS.LIST>      </SCHVIDETAILS.LIST>
                                    <EXCISETARIFFDETAILS.LIST>      </EXCISETARIFFDETAILS.LIST>
                                    <TCSCATEGORYDETAILS.LIST>      </TCSCATEGORYDETAILS.LIST>
                                    <TDSCATEGORYDETAILS.LIST>      </TDSCATEGORYDETAILS.LIST>
                                    <GSTCLASSFNIGSTRATES.LIST>      </GSTCLASSFNIGSTRATES.LIST>
                                    <EXTARIFFDUTYHEADDETAILS.LIST>      </EXTARIFFDUTYHEADDETAILS.LIST>
                                    </GROUP>
                                    </TALLYMESSAGE>
                                    </REQUESTDATA>
                                    </IMPORTDATA>
                                    </BODY>
                                    </ENVELOPE>
                                 """
            print("paramsparamsparamsparamsparamsparamsparams", params)
            if create_xml:
                f = open("masters.xml", "a+")
                f.write(params)
                f.close()
                created_in_tally = True
                line.write({'created_in_tally': created_in_tally})
            else:
                res = requests.post(url, data=params, headers={'Content-Type': 'application/xml'})
                root = ET.fromstring(res.content)
                print("root", root)
                print("rres.content", res.content)
                created_in_tally = False
                #altered_in_tally = False
                if len(root) > 9:
                    if root[0].tag == 'LINEERROR':
                        altered_in_tally = False
                        sync_dict = {}
                        sync_dict = {
                            'object': 'account.group',
                            'name': 'Account Groups',
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

        return True


