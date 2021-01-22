from odoo import api, fields, models, _
from odoo.exceptions import UserError
import requests
import random
from datetime import datetime
from xml.etree import ElementTree as ET


class StockGroups(models.Model):
    _name = 'stock.groups'

    # commented
    # @api.multi
    # def create_stockGroups(self,url):
    #     print('** Create Stock Item **',url)
    #     Warehouse = self.env['stock.warehouse'].search([])
    #     for line in Warehouse:
    #         WarehouseName = line.name
    #         WarehouseCode = line.code
    #         print("Warehouse====",WarehouseName)
    #
    #         params = """
    #             <?xml version='1.0' encoding='utf-8'?>
    #             <ENVELOPE>
    #             <HEADER>
    #             <TALLYREQUEST>Import Data</TALLYREQUEST>
    #             </HEADER>
    #             <BODY>
    #             <IMPORTDATA>
    #             <REQUESTDESC>
    #             <REPORTNAME>All Masters</REPORTNAME>
    #             <STATICVARIABLES>
    #             <SVCURRENTCOMPANY>Arkefilters</SVCURRENTCOMPANY>
    #             </STATICVARIABLES>
    #             </REQUESTDESC>
    #             <REQUESTDATA>
    #             <TALLYMESSAGE xmlns:UDF="TallyUDF">
    #             <STOCKGROUP NAME="" RESERVEDNAME="">
    #             <GUID>6199d8ea-2b04-47c5-b5e9-b9274827b566-000000a1</GUID>
    #             <PARENT/>
    #             <COSTINGMETHOD>Avg. Cost</COSTINGMETHOD>
    #             <VALUATIONMETHOD>Avg. Price</VALUATIONMETHOD>
    #             <BASEUNITS>Piece</BASEUNITS>
    #             <ADDITIONALUNITS/>
    #             <ISBATCHWISEON>No</ISBATCHWISEON>
    #             <ISPERISHABLEON>No</ISPERISHABLEON>
    #             <ISADDABLE>No</ISADDABLE>
    #             <ISUPDATINGTARGETID>No</ISUPDATINGTARGETID>
    #             <ASORIGINAL>Yes</ASORIGINAL>
    #             <IGNOREPHYSICALDIFFERENCE>No</IGNOREPHYSICALDIFFERENCE>
    #             <IGNORENEGATIVESTOCK>No</IGNORENEGATIVESTOCK>
    #             <TREATSALESASMANUFACTURED>No</TREATSALESASMANUFACTURED>
    #             <TREATPURCHASESASCONSUMED>No</TREATPURCHASESASCONSUMED>
    #             <TREATREJECTSASSCRAP>No</TREATREJECTSASSCRAP>
    #             <HASMFGDATE>No</HASMFGDATE>
    #             <ALLOWUSEOFEXPIREDITEMS>No</ALLOWUSEOFEXPIREDITEMS>
    #             <IGNOREBATCHES>No</IGNOREBATCHES>
    #             <IGNOREGODOWNS>No</IGNOREGODOWNS>
    #             <ALTERID> 162</ALTERID>
    #             <SERVICETAXDETAILS.LIST>      </SERVICETAXDETAILS.LIST>
    #             <VATDETAILS.LIST>      </VATDETAILS.LIST>
    #             <SALESTAXCESSDETAILS.LIST>      </SALESTAXCESSDETAILS.LIST>
    #             <GSTDETAILS.LIST>      </GSTDETAILS.LIST>
    #             <LANGUAGENAME.LIST>
    #             <NAME.LIST TYPE="String">
    #             <NAME>""" + WarehouseName + """</NAME>
    #             <NAME>""" + WarehouseCode + """</NAME>
    #             </NAME.LIST>
    #             <LANGUAGEID> 1033</LANGUAGEID>
    #             </LANGUAGENAME.LIST>
    #             <SCHVIDETAILS.LIST>      </SCHVIDETAILS.LIST>
    #             <EXCISETARIFFDETAILS.LIST>      </EXCISETARIFFDETAILS.LIST>
    #             <TCSCATEGORYDETAILS.LIST>      </TCSCATEGORYDETAILS.LIST>
    #             <TDSCATEGORYDETAILS.LIST>      </TDSCATEGORYDETAILS.LIST>
    #             <GSTCLASSFNIGSTRATES.LIST>      </GSTCLASSFNIGSTRATES.LIST>
    #             <EXTARIFFDUTYHEADDETAILS.LIST>      </EXTARIFFDUTYHEADDETAILS.LIST>
    #             <TEMPGSTITEMSLABRATES.LIST>      </TEMPGSTITEMSLABRATES.LIST>
    #             </STOCKGROUP>
    #             </TALLYMESSAGE>
    #             </REQUESTDATA>
    #             </IMPORTDATA>
    #             </BODY>
    #             </ENVELOPE>
    #          """
    #
    #         res = requests.post(url, data=params, headers={'Content-Type': 'application/xml'})
    #         print("Successfully Exported Data")
    #         print(res)
    #
    #     return True

    # params = """
    #                                 <?xml version='1.0' encoding='utf-8'?>
    #                                 <ENVELOPE>
    #                                 <HEADER>
    #                                 <TALLYREQUEST>Import Data</TALLYREQUEST>
    #                                 </HEADER>
    #                                 <BODY>
    #                                 <IMPORTDATA>
    #                                 <REQUESTDESC>
    #                                 <REPORTNAME>All Masters</REPORTNAME>
    #                                 <STATICVARIABLES>
    #                                 <SVCURRENTCOMPANY>""" + tally_company + """</SVCURRENTCOMPANY>
    #                                 </STATICVARIABLES>
    #                                 </REQUESTDESC>
    #                                 <REQUESTDATA>
    #                                 <TALLYMESSAGE xmlns:UDF="TallyUDF">
    #                                 <STOCKGROUP NAME="" RESERVEDNAME="">
    #                                 <GUID></GUID>
    #                                 <PARENT>""" + parent_name + """<PARENT/>
    #                                 <COSTINGMETHOD>Avg. Cost</COSTINGMETHOD>
    #                                 <VALUATIONMETHOD>Avg. Price</VALUATIONMETHOD>
    #                                 <BASEUNITS>Piece</BASEUNITS>
    #                                 <ADDITIONALUNITS/>
    #                                 <ISBATCHWISEON>No</ISBATCHWISEON>
    #                                 <ISPERISHABLEON>No</ISPERISHABLEON>
    #                                 <ISADDABLE>No</ISADDABLE>
    #                                 <ISUPDATINGTARGETID>No</ISUPDATINGTARGETID>
    #                                 <ASORIGINAL>Yes</ASORIGINAL>
    #                                 <IGNOREPHYSICALDIFFERENCE>No</IGNOREPHYSICALDIFFERENCE>
    #                                 <IGNORENEGATIVESTOCK>No</IGNORENEGATIVESTOCK>
    #                                 <TREATSALESASMANUFACTURED>No</TREATSALESASMANUFACTURED>
    #                                 <TREATPURCHASESASCONSUMED>No</TREATPURCHASESASCONSUMED>
    #                                 <TREATREJECTSASSCRAP>No</TREATREJECTSASSCRAP>
    #                                 <HASMFGDATE>No</HASMFGDATE>
    #                                 <ALLOWUSEOFEXPIREDITEMS>No</ALLOWUSEOFEXPIREDITEMS>
    #                                 <IGNOREBATCHES>No</IGNOREBATCHES>
    #                                 <IGNOREGODOWNS>No</IGNOREGODOWNS>
    #                                 <ALTERID> 162</ALTERID>
    #                                 <SERVICETAXDETAILS.LIST>      </SERVICETAXDETAILS.LIST>
    #                                 <VATDETAILS.LIST>      </VATDETAILS.LIST>
    #                                 <SALESTAXCESSDETAILS.LIST>      </SALESTAXCESSDETAILS.LIST>
    #                                 <GSTDETAILS.LIST>      </GSTDETAILS.LIST>
    #                                 <LANGUAGENAME.LIST>
    #                                 <NAME.LIST TYPE="String">
    #                                 <NAME>""" + CategoryName + """</NAME>
    #
    #                                 </NAME.LIST>
    #                                 <LANGUAGEID> 1033</LANGUAGEID>
    #                                 </LANGUAGENAME.LIST>
    #                                 <SCHVIDETAILS.LIST>      </SCHVIDETAILS.LIST>
    #                                 <EXCISETARIFFDETAILS.LIST>      </EXCISETARIFFDETAILS.LIST>
    #                                 <TCSCATEGORYDETAILS.LIST>      </TCSCATEGORYDETAILS.LIST>
    #                                 <TDSCATEGORYDETAILS.LIST>      </TDSCATEGORYDETAILS.LIST>
    #                                 <GSTCLASSFNIGSTRATES.LIST>      </GSTCLASSFNIGSTRATES.LIST>
    #                                 <EXTARIFFDUTYHEADDETAILS.LIST>      </EXTARIFFDUTYHEADDETAILS.LIST>
    #                                 <TEMPGSTITEMSLABRATES.LIST>      </TEMPGSTITEMSLABRATES.LIST>
    #                                 </STOCKGROUP>
    #                                 </TALLYMESSAGE>
    #                                 </REQUESTDATA>
    #                                 </IMPORTDATA>
    #                                 </BODY>
    #                                 </ENVELOPE>
    #                              """

    #
    # @api.multi
    # def create_stockGroups(self, url):
    #     print('** Create Stock Item **', url)
    #     Categories = self.env['product.category'].search([])
    #     for line in Categories:
    #         if line.sequence_code:
    #             CategoryName = line.name
    #             CategoryCode = line.sequence_code
    #             print("Warehouse====", CategoryName)
    #
    #             params = """
    #                     <?xml version='1.0' encoding='utf-8'?>
    #                     <ENVELOPE>
    #                     <HEADER>
    #                     <TALLYREQUEST>Import Data</TALLYREQUEST>
    #                     </HEADER>
    #                     <BODY>
    #                     <IMPORTDATA>
    #                     <REQUESTDESC>
    #                     <REPORTNAME>All Masters</REPORTNAME>
    #                     <STATICVARIABLES>
    #                     <SVCURRENTCOMPANY>Arkefilters</SVCURRENTCOMPANY>
    #                     </STATICVARIABLES>
    #                     </REQUESTDESC>
    #                     <REQUESTDATA>
    #                     <TALLYMESSAGE xmlns:UDF="TallyUDF">
    #                     <STOCKGROUP NAME="" RESERVEDNAME="">
    #                     <GUID>6199d8ea-2b04-47c5-b5e9-b9274827b566-000000a1</GUID>
    #                     <PARENT/>
    #                     <COSTINGMETHOD>Avg. Cost</COSTINGMETHOD>
    #                     <VALUATIONMETHOD>Avg. Price</VALUATIONMETHOD>
    #                     <BASEUNITS>Piece</BASEUNITS>
    #                     <ADDITIONALUNITS/>
    #                     <ISBATCHWISEON>No</ISBATCHWISEON>
    #                     <ISPERISHABLEON>No</ISPERISHABLEON>
    #                     <ISADDABLE>No</ISADDABLE>
    #                     <ISUPDATINGTARGETID>No</ISUPDATINGTARGETID>
    #                     <ASORIGINAL>Yes</ASORIGINAL>
    #                     <IGNOREPHYSICALDIFFERENCE>No</IGNOREPHYSICALDIFFERENCE>
    #                     <IGNORENEGATIVESTOCK>No</IGNORENEGATIVESTOCK>
    #                     <TREATSALESASMANUFACTURED>No</TREATSALESASMANUFACTURED>
    #                     <TREATPURCHASESASCONSUMED>No</TREATPURCHASESASCONSUMED>
    #                     <TREATREJECTSASSCRAP>No</TREATREJECTSASSCRAP>
    #                     <HASMFGDATE>No</HASMFGDATE>
    #                     <ALLOWUSEOFEXPIREDITEMS>No</ALLOWUSEOFEXPIREDITEMS>
    #                     <IGNOREBATCHES>No</IGNOREBATCHES>
    #                     <IGNOREGODOWNS>No</IGNOREGODOWNS>
    #                     <ALTERID> Yes</ALTERID>
    #                     <SERVICETAXDETAILS.LIST>      </SERVICETAXDETAILS.LIST>
    #                     <VATDETAILS.LIST>      </VATDETAILS.LIST>
    #                     <SALESTAXCESSDETAILS.LIST>      </SALESTAXCESSDETAILS.LIST>
    #                     <GSTDETAILS.LIST>      </GSTDETAILS.LIST>
    #                     <LANGUAGENAME.LIST>
    #                     <NAME.LIST TYPE="String">
    #                     <NAME>""" + CategoryName + """</NAME>
    #                     <NAME>""" + CategoryCode + """</NAME>
    #                     </NAME.LIST>
    #                     <LANGUAGEID> 1033</LANGUAGEID>
    #                     </LANGUAGENAME.LIST>
    #                     <SCHVIDETAILS.LIST>      </SCHVIDETAILS.LIST>
    #                     <EXCISETARIFFDETAILS.LIST>      </EXCISETARIFFDETAILS.LIST>
    #                     <TCSCATEGORYDETAILS.LIST>      </TCSCATEGORYDETAILS.LIST>
    #                     <TDSCATEGORYDETAILS.LIST>      </TDSCATEGORYDETAILS.LIST>
    #                     <GSTCLASSFNIGSTRATES.LIST>      </GSTCLASSFNIGSTRATES.LIST>
    #                     <EXTARIFFDUTYHEADDETAILS.LIST>      </EXTARIFFDUTYHEADDETAILS.LIST>
    #                     <TEMPGSTITEMSLABRATES.LIST>      </TEMPGSTITEMSLABRATES.LIST>
    #                     </STOCKGROUP>
    #                     </TALLYMESSAGE>
    #                     </REQUESTDATA>
    #                     </IMPORTDATA>
    #                     </BODY>
    #                     </ENVELOPE>
    #                  """
    #
    #             res = requests.post(url, data=params, headers={'Content-Type': 'application/xml'})
    #             print("Successfully Exported Data")
    #             print(res)

    # params = """
    #                                <?xml version='1.0' encoding='utf-8'?>
    #                                <ENVELOPE>
    #                                <HEADER>
    #                                <TALLYREQUEST>Import Data</TALLYREQUEST>
    #                                </HEADER>
    #                                <BODY>
    #                                <IMPORTDATA>
    #                                <REQUESTDESC>
    #                                <REPORTNAME>All Masters</REPORTNAME>
    #                                <STATICVARIABLES>
    #                                <SVCURRENTCOMPANY>""" + tally_company + """</SVCURRENTCOMPANY>
    #                                </STATICVARIABLES>
    #                                </REQUESTDESC>
    #                                <REQUESTDATA>
    #                                <TALLYMESSAGE xmlns:UDF="TallyUDF">
    #                                <STOCKGROUP REMOTEID=" """ + str(guid) + """ " ACTION="Create">
    #
    #                                <GUID>""" + guid + """</GUID>
    #                                <PARENT/>
    #                                <COSTINGMETHOD>Avg. Cost</COSTINGMETHOD>
    #                                <VALUATIONMETHOD>Avg. Price</VALUATIONMETHOD>
    #                                <BASEUNITS>Piece</BASEUNITS>
    #                                <ADDITIONALUNITS/>
    #                                <ISBATCHWISEON>No</ISBATCHWISEON>
    #                                <ISPERISHABLEON>No</ISPERISHABLEON>
    #                                <ISADDABLE>No</ISADDABLE>
    #                                <ISUPDATINGTARGETID>No</ISUPDATINGTARGETID>
    #                                <ASORIGINAL>Yes</ASORIGINAL>
    #                                <IGNOREPHYSICALDIFFERENCE>No</IGNOREPHYSICALDIFFERENCE>
    #                                <IGNORENEGATIVESTOCK>No</IGNORENEGATIVESTOCK>
    #                                <TREATSALESASMANUFACTURED>No</TREATSALESASMANUFACTURED>
    #                                <TREATPURCHASESASCONSUMED>No</TREATPURCHASESASCONSUMED>
    #                                <TREATREJECTSASSCRAP>No</TREATREJECTSASSCRAP>
    #                                <HASMFGDATE>No</HASMFGDATE>
    #                                <ALLOWUSEOFEXPIREDITEMS>No</ALLOWUSEOFEXPIREDITEMS>
    #                                <IGNOREBATCHES>No</IGNOREBATCHES>
    #                                <IGNOREGODOWNS>No</IGNOREGODOWNS>
    #                                <ALTERID> 162</ALTERID>
    #                                <SERVICETAXDETAILS.LIST>      </SERVICETAXDETAILS.LIST>
    #                                <VATDETAILS.LIST>      </VATDETAILS.LIST>
    #                                <SALESTAXCESSDETAILS.LIST>      </SALESTAXCESSDETAILS.LIST>
    #                                <GSTDETAILS.LIST>      </GSTDETAILS.LIST>
    #                                <LANGUAGENAME.LIST>
    #                                <NAME.LIST TYPE="String">
    #                                <NAME>""" + CategoryName + """</NAME>
    #
    #                                </NAME.LIST>
    #                                <LANGUAGEID> 1033</LANGUAGEID>
    #                                </LANGUAGENAME.LIST>
    #                                <SCHVIDETAILS.LIST>      </SCHVIDETAILS.LIST>
    #                                <EXCISETARIFFDETAILS.LIST>      </EXCISETARIFFDETAILS.LIST>
    #                                <TCSCATEGORYDETAILS.LIST>      </TCSCATEGORYDETAILS.LIST>
    #                                <TDSCATEGORYDETAILS.LIST>      </TDSCATEGORYDETAILS.LIST>
    #                                <GSTCLASSFNIGSTRATES.LIST>      </GSTCLASSFNIGSTRATES.LIST>
    #                                <EXTARIFFDUTYHEADDETAILS.LIST>      </EXTARIFFDUTYHEADDETAILS.LIST>
    #                                <TEMPGSTITEMSLABRATES.LIST>      </TEMPGSTITEMSLABRATES.LIST>
    #                                </STOCKGROUP>
    #                                </TALLYMESSAGE>
    #                                </REQUESTDATA>
    #                                </IMPORTDATA>
    #                                </BODY>
    #                                </ENVELOPE>
    #                             """
    #
    #     return True

    @api.multi
    def create_stockGroups(self, url, company, tally_company,create_xml):
        print('** Create Stock Item **', url)
        #f = open("masters.xml", "w+")
        guid = ''
        # Categories = self.env['product.category'].search([])
        #Categories = self.env['product.category'].search([('company_id', '=', company.id),('created_in_tally','=',False)])
        Categories = self.env['product.category'].search([('company_id', '=', company.id)], order='id')
        print("categorissssssssssssss", Categories)
        print("len of categoryyyyyyyy", len(Categories))
        tally_company = tally_company
        tally_company = self.env['test.connection']._check_and_opt(tally_company)
        #JAtin Commented for few fields not present.
        for line in Categories:
            if line:
                CategoryName = line.name
                #CategoryCode = line.categ_seq_code
                parent_name = False
                print("Warehouse====", CategoryName)
                CategoryName = self.env['test.connection']._check_and_opt(CategoryName)
                print("CategoryNameCategoryNameCategoryNameCategoryName",CategoryName)
                #print("CategoryCodeCategoryCode", CategoryCode)
                #guid = line.tally_guid

                #print("guid from tally going to update", guid)
                if line.parent_id:
                    parent_name = line.parent_id.name
                print("parent_nameparent_name", parent_name)
                parent_name = self.env['test.connection']._check_and_opt(parent_name)
                if line.stock_in_tally:
                    stock_addable= 'Yes'
                else:
                    stock_addable='No'
                if CategoryName and parent_name:
                    print("iiiiiiiffffffffffffff")
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
                                <STOCKGROUP NAME="" RESERVEDNAME="">
                                <GUID></GUID>
                                <PARENT>""" + parent_name + """</PARENT>
                                <COSTINGMETHOD>Avg. Cost</COSTINGMETHOD>
                                <VALUATIONMETHOD>Avg. Price</VALUATIONMETHOD>
                                <ADDITIONALUNITS/>
                                <ISBATCHWISEON>No</ISBATCHWISEON>
                                <ISPERISHABLEON>No</ISPERISHABLEON>
                                <ISADDABLE>"""+stock_addable+"""</ISADDABLE>
                                <ISUPDATINGTARGETID>No</ISUPDATINGTARGETID>
                                <ASORIGINAL>Yes</ASORIGINAL>
                                <IGNOREPHYSICALDIFFERENCE>No</IGNOREPHYSICALDIFFERENCE>
                                <IGNORENEGATIVESTOCK>No</IGNORENEGATIVESTOCK>
                                <TREATSALESASMANUFACTURED>No</TREATSALESASMANUFACTURED>
                                <TREATPURCHASESASCONSUMED>No</TREATPURCHASESASCONSUMED>
                                <TREATREJECTSASSCRAP>No</TREATREJECTSASSCRAP>
                                <HASMFGDATE>No</HASMFGDATE>
                                <ALLOWUSEOFEXPIREDITEMS>No</ALLOWUSEOFEXPIREDITEMS>
                                <IGNOREBATCHES>No</IGNOREBATCHES>
                                <IGNOREGODOWNS>No</IGNOREGODOWNS>
                                <ALTERID> Yes</ALTERID>
                                <SERVICETAXDETAILS.LIST>      </SERVICETAXDETAILS.LIST>
                                <VATDETAILS.LIST>      </VATDETAILS.LIST>
                                <SALESTAXCESSDETAILS.LIST>      </SALESTAXCESSDETAILS.LIST>
                                <GSTDETAILS.LIST>      </GSTDETAILS.LIST>
                                <LANGUAGENAME.LIST>
                                <NAME.LIST TYPE="String">
                                <NAME>""" + CategoryName + """</NAME>

                                </NAME.LIST>
                                <LANGUAGEID> 1033</LANGUAGEID>
                                </LANGUAGENAME.LIST>
                                <SCHVIDETAILS.LIST>      </SCHVIDETAILS.LIST>
                                <EXCISETARIFFDETAILS.LIST>      </EXCISETARIFFDETAILS.LIST>
                                <TCSCATEGORYDETAILS.LIST>      </TCSCATEGORYDETAILS.LIST>
                                <TDSCATEGORYDETAILS.LIST>      </TDSCATEGORYDETAILS.LIST>
                                <GSTCLASSFNIGSTRATES.LIST>      </GSTCLASSFNIGSTRATES.LIST>
                                <EXTARIFFDUTYHEADDETAILS.LIST>      </EXTARIFFDUTYHEADDETAILS.LIST>
                                <TEMPGSTITEMSLABRATES.LIST>      </TEMPGSTITEMSLABRATES.LIST>
                                </STOCKGROUP>
                                </TALLYMESSAGE>
                                </REQUESTDATA>
                                </IMPORTDATA>
                                </BODY>
                                </ENVELOPE>
                             """
                elif CategoryName:
                    print("eliffffffffffffff")
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
                                <STOCKGROUP NAME="" RESERVEDNAME="">
                                <GUID></GUID>
                                <PARENT/>
                                <COSTINGMETHOD>Avg. Cost</COSTINGMETHOD>
                                <VALUATIONMETHOD>Avg. Price</VALUATIONMETHOD>
                                <ADDITIONALUNITS/>
                                <ISBATCHWISEON>No</ISBATCHWISEON>
                                <ISPERISHABLEON>No</ISPERISHABLEON>
                                <ISADDABLE>"""+stock_addable+"""</ISADDABLE>
                                <ISUPDATINGTARGETID>No</ISUPDATINGTARGETID>
                                <ASORIGINAL>Yes</ASORIGINAL>
                                <IGNOREPHYSICALDIFFERENCE>No</IGNOREPHYSICALDIFFERENCE>
                                <IGNORENEGATIVESTOCK>No</IGNORENEGATIVESTOCK>
                                <TREATSALESASMANUFACTURED>No</TREATSALESASMANUFACTURED>
                                <TREATPURCHASESASCONSUMED>No</TREATPURCHASESASCONSUMED>
                                <TREATREJECTSASSCRAP>No</TREATREJECTSASSCRAP>
                                <HASMFGDATE>No</HASMFGDATE>
                                <ALLOWUSEOFEXPIREDITEMS>No</ALLOWUSEOFEXPIREDITEMS>
                                <IGNOREBATCHES>No</IGNOREBATCHES>
                                <IGNOREGODOWNS>No</IGNOREGODOWNS>
                                <ALTERID> Yes</ALTERID>
                                <SERVICETAXDETAILS.LIST>      </SERVICETAXDETAILS.LIST>
                                <VATDETAILS.LIST>      </VATDETAILS.LIST>
                                <SALESTAXCESSDETAILS.LIST>      </SALESTAXCESSDETAILS.LIST>
                                <GSTDETAILS.LIST>      </GSTDETAILS.LIST>
                                <LANGUAGENAME.LIST>
                                <NAME.LIST TYPE="String">
                                <NAME>""" + CategoryName + """</NAME>

                                </NAME.LIST>
                                <LANGUAGEID> 1033</LANGUAGEID>
                                </LANGUAGENAME.LIST>
                                <SCHVIDETAILS.LIST>      </SCHVIDETAILS.LIST>
                                <EXCISETARIFFDETAILS.LIST>      </EXCISETARIFFDETAILS.LIST>
                                <TCSCATEGORYDETAILS.LIST>      </TCSCATEGORYDETAILS.LIST>
                                <TDSCATEGORYDETAILS.LIST>      </TDSCATEGORYDETAILS.LIST>
                                <GSTCLASSFNIGSTRATES.LIST>      </GSTCLASSFNIGSTRATES.LIST>
                                <EXTARIFFDUTYHEADDETAILS.LIST>      </EXTARIFFDUTYHEADDETAILS.LIST>
                                <TEMPGSTITEMSLABRATES.LIST>      </TEMPGSTITEMSLABRATES.LIST>
                                </STOCKGROUP>
                                </TALLYMESSAGE>
                                </REQUESTDATA>
                                </IMPORTDATA>
                                </BODY>
                                </ENVELOPE>
                             """
                print("parammmmmmmmmmmmm", params)
                if create_xml:
                    f = open("masters.xml", "a+")
                    f.write(params)
                    f.close()
                    created_in_tally = True
                    line.write({'created_in_tally': created_in_tally})
                else:
                    print("here in else of stock group ")
                    res = requests.post(url, data=params, headers={'Content-Type': 'application/xml'})
                    print("Successfully Exported Data")
                    root = ET.fromstring(res.content)
                    print("res.comtent",res.content)
                    created_in_tally = False
                    altered_in_tally = False
                    if len(root) > 9:
                        if root[0].tag == 'LINEERROR':
                            altered_in_tally = False
                            sync_dict = {}
                            sync_dict = {
                                'object': 'product.category',
                                'name': 'Product Category',
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


