from odoo import api, fields, models, _
from odoo.exceptions import UserError
import requests
import random
from datetime import datetime
from xml.etree import ElementTree as ET


class StockItem(models.Model):
    _name = 'stock.item'
    
    @api.multi
    def create_stockItem(self,url,company,tally_company,create_xml):
        print('** Create Stock Item **',url)
        #f = open("masters.xml", "w+")
        Product = self.env['product.product'].search([('company_id', '=', company.id)],order='id')
        #Product = self.env['product.product'].search([('company_id', '=', company.id),('created_in_tally','=',False)],order='id')
        #Product = self.env['product.product'].search([('id', '=', 12)])
        print ("productttttttt",Product)
        print ("len of the product temp listttttt",len(Product))
        tally_company = tally_company
        tally_company = self.env['test.connection']._check_and_opt(tally_company)

        for line in Product:
            alias = ''
            print ("lineeeeeeeeeee",line,line.attribute_value_ids)
            if line.attribute_value_ids :
                attr_name = ''
                for val in line.attribute_value_ids:
                    if val.attribute_id:
                        attr_name = attr_name  + val.attribute_id.name + ':' + val.name + ','
                    else:
                        attr_name = attr_name + 'Attribute' + ':' + val.name + ','
                    print ("valllllllllll",val)
                if attr_name:
                    ProductName =  line.name + '(' + attr_name + ')'
                else:
                    ProductName = line.name
                print ("product nameeeeeeeee",ProductName)
            else:
                ProductName = line.name
            if line.default_code:
                alias = line.default_code
            ProductName=self.env['test.connection']._check_and_opt(ProductName)
            print("ProductNameProductNameProductNameProductName",ProductName)

            UOM = line.product_tmpl_id.uom_id.name
            UOM = self.env['test.connection']._check_and_opt(UOM)
            Rate = line.product_tmpl_id.list_price
            categ_name = line.product_tmpl_id.categ_id.name
            categ_name = self.env['test.connection']._check_and_opt(categ_name)
            print("ProductName====",ProductName,UOM,Rate)
            #GUID = 'itm'+ ProductName
            warehouse=self.env['stock.warehouse'].search([('company_id', '=', company.id)])
            godown=warehouse.name
            godown = self.env['test.connection']._check_and_opt(godown)
            hsn_code,cgst_lines,sgst_lines='aa','',''
            print(hsn_code,cgst_lines,sgst_lines)
            if line.hsn_id:
                hsn_code=line.hsn_id.hsn_code
                cgst_lines=self.env['tax.master.details'].search([('tax_master_details_id', '=',line.hsn_id.id),('tax_group_id.name','=','CGST')],limit=1).tax_percentage
                sgst_lines=self.env['tax.master.details'].search([('tax_master_details_id', '=',line.hsn_id.id),('tax_group_id.name','=','SGST')],limit=1).tax_percentage
                igst_lines=self.env['tax.master.details'].search([('tax_master_details_id', '=',line.hsn_id.id),('tax_group_id.name','=','IGST')],limit=1).tax_percentage
                igst_date=self.env['tax.master.details'].search([('tax_master_details_id', '=',line.hsn_id.id),('tax_group_id.name','=','IGST')],limit=1).from_date
                vch_year = igst_date[0:4]
                vch_date = igst_date[-2:]
                vch_month = igst_date[-5:-3]
                Date = str(vch_year) + str(vch_month) + str(vch_date)
                print(hsn_code,cgst_lines,sgst_lines,igst_lines)
            else:
                hsn_code=''
                Date=''
                cgst_lines=''
                sgst_lines=''
                igst_lines=''

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
                <STOCKITEM NAME="" REMOTEID="" RESERVEDNAME="">
                <OLDAUDITENTRYIDS.LIST TYPE="Number">
                <OLDAUDITENTRYIDS>-1</OLDAUDITENTRYIDS>
                </OLDAUDITENTRYIDS.LIST>
                <GUID></GUID>
                <PARENT>""" + categ_name + """</PARENT>
                <CATEGORY/>
                <GSTAPPLICABLE>&#4; Applicable</GSTAPPLICABLE> 
                <GSTDETAILS.LIST>
                   <APPLICABLEFROM>"""+Date+"""</APPLICABLEFROM>
                   <CALCULATIONTYPE>On Value</CALCULATIONTYPE>
                   <HSNCODE>"""+hsn_code+"""</HSNCODE>
                   <HSNMASTERNAME/>
                   <HSN>Taxable</HSN>
                   <TAXABILITY>Taxable</TAXABILITY>
                   <ISREVERSECHARGEAPPLICABLE>No</ISREVERSECHARGEAPPLICABLE>
                   <ISNONGSTGOODS>No</ISNONGSTGOODS>
                   <GSTINELIGIBLEITC>No</GSTINELIGIBLEITC>
                   <INCLUDEEXPFORSLABCALC>No</INCLUDEEXPFORSLABCALC>
                   <STATEWISEDETAILS.LIST>
                    <STATENAME>&#4; Any</STATENAME>
                    <RATEDETAILS.LIST>
                     <GSTRATEDUTYHEAD>Central Tax</GSTRATEDUTYHEAD>
                     <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>
                     <GSTRATE>"""+str(cgst_lines)+"""</GSTRATE>
                    </RATEDETAILS.LIST>
                    <RATEDETAILS.LIST>
                     <GSTRATEDUTYHEAD>State Tax</GSTRATEDUTYHEAD>
                     <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>
                     <GSTRATE>"""+str(sgst_lines)+"""</GSTRATE>
                    </RATEDETAILS.LIST>
                    <RATEDETAILS.LIST>
                     <GSTRATEDUTYHEAD>Integrated Tax</GSTRATEDUTYHEAD>
                     <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>
                     <GSTRATE>"""+str(igst_lines)+"""</GSTRATE>
                    </RATEDETAILS.LIST>
                    <RATEDETAILS.LIST>
                     <GSTRATEDUTYHEAD>Cess</GSTRATEDUTYHEAD>
                     <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>
                    </RATEDETAILS.LIST>
                    <RATEDETAILS.LIST>
                     <GSTRATEDUTYHEAD>Cess on Qty</GSTRATEDUTYHEAD>
                     <GSTRATEVALUATIONTYPE>Based on Quantity</GSTRATEVALUATIONTYPE>
                    </RATEDETAILS.LIST>
                    <RATEDETAILS.LIST>
                     <GSTRATEDUTYHEAD>State Cess</GSTRATEDUTYHEAD>
                     <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>
                    </RATEDETAILS.LIST>
                    <GSTSLABRATES.LIST>        </GSTSLABRATES.LIST>
                   </STATEWISEDETAILS.LIST>
                   <TEMPGSTDETAILSLABRATES.LIST>       </TEMPGSTDETAILSLABRATES.LIST>
                  </GSTDETAILS.LIST>
                <GSTTYPEOFSUPPLY>Goods</GSTTYPEOFSUPPLY>
                <EXCISEAPPLICABILITY>&#4; Applicable</EXCISEAPPLICABILITY>
                <SALESTAXCESSAPPLICABLE/>
                <VATAPPLICABLE>&#4; Applicable</VATAPPLICABLE>
                <COSTINGMETHOD>Avg. Cost</COSTINGMETHOD>
                <VALUATIONMETHOD>Avg. Price</VALUATIONMETHOD>
                <BASEUNITS>""" + UOM + """</BASEUNITS>
                <ADDITIONALUNITS/>
                <EXCISEITEMCLASSIFICATION/>
                <VATBASEUNIT>""" + UOM + """</VATBASEUNIT>
                <Alias>""" + alias + """</Alias>
                <ISCOSTCENTRESON>No</ISCOSTCENTRESON>
                <ISBATCHWISEON>No</ISBATCHWISEON>
                <ISPERISHABLEON>No</ISPERISHABLEON>
                <ISENTRYTAXAPPLICABLE>No</ISENTRYTAXAPPLICABLE>
                <ISCOSTTRACKINGON>No</ISCOSTTRACKINGON>
                <ISUPDATINGTARGETID>No</ISUPDATINGTARGETID>
                <ASORIGINAL>Yes</ASORIGINAL>
                <ISRATEINCLUSIVEVAT>No</ISRATEINCLUSIVEVAT>
                <IGNOREPHYSICALDIFFERENCE>No</IGNOREPHYSICALDIFFERENCE>
                <IGNORENEGATIVESTOCK>No</IGNORENEGATIVESTOCK>
                <TREATSALESASMANUFACTURED>No</TREATSALESASMANUFACTURED>
                <TREATPURCHASESASCONSUMED>No</TREATPURCHASESASCONSUMED>
                <TREATREJECTSASSCRAP>No</TREATREJECTSASSCRAP>
                <HASMFGDATE>No</HASMFGDATE>
                <ALLOWUSEOFEXPIREDITEMS>No</ALLOWUSEOFEXPIREDITEMS>
                <IGNOREBATCHES>No</IGNOREBATCHES>
                <IGNOREGODOWNS>No</IGNOREGODOWNS>
                <CALCONMRP>No</CALCONMRP>
                <EXCLUDEJRNLFORVALUATION>No</EXCLUDEJRNLFORVALUATION>
                <ISMRPINCLOFTAX>No</ISMRPINCLOFTAX>
                <ISADDLTAXEXEMPT>No</ISADDLTAXEXEMPT>
                <ISSUPPLEMENTRYDUTYON>No</ISSUPPLEMENTRYDUTYON>
                <GVATISEXCISEAPPL>No</GVATISEXCISEAPPL>
                <REORDERASHIGHER>No</REORDERASHIGHER>
                <MINORDERASHIGHER>No</MINORDERASHIGHER>
                <ISEXCISECALCULATEONMRP>No</ISEXCISECALCULATEONMRP>
                <INCLUSIVETAX>No</INCLUSIVETAX>
                <GSTCALCSLABONMRP>No</GSTCALCSLABONMRP>
                <MODIFYMRPRATE>No</MODIFYMRPRATE>
                <ALTERID> </ALTERID>
                <DENOMINATOR> 1</DENOMINATOR>
                <BASICRATEOFEXCISE/>
                <RATEOFVAT>0</RATEOFVAT>
                <VATBASENO> 1</VATBASENO>
                <VATTRAILNO> 1</VATTRAILNO>
                <VATACTUALRATIO> 1</VATACTUALRATIO>
                <OPENINGBALANCE> </OPENINGBALANCE>
                <OPENINGVALUE></OPENINGVALUE>
                <OPENINGRATE></OPENINGRATE>
                <SERVICETAXDETAILS.LIST>      </SERVICETAXDETAILS.LIST>
                <VATDETAILS.LIST>      </VATDETAILS.LIST>
                <SALESTAXCESSDETAILS.LIST>      </SALESTAXCESSDETAILS.LIST>
                <LANGUAGENAME.LIST>
                <NAME.LIST TYPE="String">
                <NAME>"""+ ProductName +"""</NAME>
                </NAME.LIST>
                <LANGUAGEID> 1033</LANGUAGEID>
                </LANGUAGENAME.LIST>
                <SCHVIDETAILS.LIST>      </SCHVIDETAILS.LIST>
                <EXCISETARIFFDETAILS.LIST>      </EXCISETARIFFDETAILS.LIST>
                <TCSCATEGORYDETAILS.LIST>      </TCSCATEGORYDETAILS.LIST>
                <TDSCATEGORYDETAILS.LIST>      </TDSCATEGORYDETAILS.LIST>
                <EXCLUDEDTAXATIONS.LIST>      </EXCLUDEDTAXATIONS.LIST>
                <OLDAUDITENTRIES.LIST>      </OLDAUDITENTRIES.LIST>
                <ACCOUNTAUDITENTRIES.LIST>      </ACCOUNTAUDITENTRIES.LIST>
                <AUDITENTRIES.LIST>      </AUDITENTRIES.LIST>
                <MRPDETAILS.LIST>      </MRPDETAILS.LIST>
                <VATCLASSIFICATIONDETAILS.LIST>      </VATCLASSIFICATIONDETAILS.LIST>
                <COMPONENTLIST.LIST>      </COMPONENTLIST.LIST>
                <ADDITIONALLEDGERS.LIST>      </ADDITIONALLEDGERS.LIST>
                <SALESLIST.LIST>      </SALESLIST.LIST>
                <PURCHASELIST.LIST>      </PURCHASELIST.LIST>
                <FULLPRICELIST.LIST>      </FULLPRICELIST.LIST>
                <BATCHALLOCATIONS.LIST>
                <GODOWNNAME>"""+godown+"""</GODOWNNAME>
                <BATCHNAME>Primary Batch</BATCHNAME>
                <OPENINGBALANCE> </OPENINGBALANCE>
                <OPENINGVALUE></OPENINGVALUE>
                <OPENINGRATE></OPENINGRATE>
                </BATCHALLOCATIONS.LIST>
                <TRADEREXCISEDUTIES.LIST>      </TRADEREXCISEDUTIES.LIST>
                <STANDARDCOSTLIST.LIST>      </STANDARDCOSTLIST.LIST>
                <STANDARDPRICELIST.LIST>      </STANDARDPRICELIST.LIST>
                <EXCISEITEMGODOWN.LIST>      </EXCISEITEMGODOWN.LIST>
                <MULTICOMPONENTLIST.LIST>      </MULTICOMPONENTLIST.LIST>
                <LBTDETAILS.LIST>      </LBTDETAILS.LIST>
                <PRICELEVELLIST.LIST>      </PRICELEVELLIST.LIST>
                <GSTCLASSFNIGSTRATES.LIST>      </GSTCLASSFNIGSTRATES.LIST>
                <EXTARIFFDUTYHEADDETAILS.LIST>      </EXTARIFFDUTYHEADDETAILS.LIST>
                <TEMPGSTITEMSLABRATES.LIST>      </TEMPGSTITEMSLABRATES.LIST>
                </STOCKITEM>
                </TALLYMESSAGE>
                </REQUESTDATA>
                </IMPORTDATA>
                </BODY>
                </ENVELOPE>
             """
            #print ("paramsssssssssss",params)
            if create_xml:
                f = open("masters.xml", "a+")
                f.write(params)
                f.close()
                created_in_tally = True
                line.write({'created_in_tally': created_in_tally})
            else:
                res = requests.post(url, data=params, headers={'Content-Type': 'application/xml'})
                print(res)
                root = ET.fromstring(res.content)
                created_in_tally = False
                altered_in_tally = False
                if len(root) > 9:
                    if root[0].tag == 'LINEERROR':
                        altered_in_tally = False
                        sync_dict={}
                        sync_dict={
                            'object':'product.product',
                            'name': 'Product Variants',
                            'total_records':1,
                            'record_name':line.name,
                            'log_date':datetime.now(),
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