from odoo import api, fields, models, _
from odoo.exceptions import UserError
import requests
from datetime import datetime,date
from xml.etree import ElementTree as ET

class StockJournalImport(models.Model):
    _name = 'stock.journal.import'

    @api.multi
    def create_StockJournal(self, url, company, tally_company, create_xml):
        print("heelo")
        tally_company = tally_company
        tally_company = self.env['test.connection']._check_and_opt(tally_company)
        invtObj = self.env['stock.inventory'].search([('state', 'in', ('done',)), ('company_id', '=', company.id),('sale_id','!=',False)],order='id')
        #invtObj = self.env['stock.inventory'].search([('state', 'in', ('done',)), ('company_id', '=', company.id),('sale_id','!=',False),('created_in_tally','=',False)],order='id')
        #invtObj = self.env['stock.inventory'].search([('id', '=', 12)])
        print("",invtObj)
        for line in invtObj:
            moveobj=self.env['stock.move'].search([('inventory_id', '=', line.id)])
            VchDate=str(datetime.strptime(line.date,"%Y-%m-%d %H:%M:%S").date())
            vch_year = VchDate[0:4]
            vch_date = VchDate[-2:]
            vch_month = VchDate[-5:-3]
            Date = str(vch_year) + str(vch_month) + str(vch_date)
            lname=line.name
            print(lname)
            GUID=str('SJ'+ str(lname[-5:])+str(line.id))
            print(GUID)

            print('date1date1date1date1',Date)
            print("move_linemove_linemove_line",moveobj)
            params2=''
            for move in moveobj:
                #product=move.product_id.name
                if move.product_id.attribute_value_ids:
                    attr_name = ''
                    for val in move.product_id.attribute_value_ids:
                        if val.attribute_id:
                            attr_name = attr_name + val.attribute_id.name + ':' + val.name + ','
                        else:
                            attr_name = attr_name + 'Attribute' + ':' + val.name + ','
                        print("valllllllllll", val)
                    if attr_name:
                        product_name = move.product_id.name + '(' + attr_name + ')'
                    else:
                        product_name = move.product_id.name
                else:
                    product_name = move.product_id.name
                product_name = self.env['test.connection']._check_and_opt(product_name)
                quantity= str(int(move.product_uom_qty))
                uom= move.product_uom.name
                loca=move.location_dest_id
                godown=self.env['stock.warehouse'].search([('lot_stock_id', '=', loca.id)])
                godown_name=godown.name
                godown_name = self.env['test.connection']._check_and_opt(godown_name)

                print(product_name,quantity,uom,godown_name)
                params1="""
                           <INVENTORYENTRIESIN.LIST>
                           <STOCKITEMNAME>"""+product_name+"""</STOCKITEMNAME>
                           <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
                           <ISLASTDEEMEDPOSITIVE>Yes</ISLASTDEEMEDPOSITIVE>
                           <ISAUTONEGATE>No</ISAUTONEGATE>
                           <ISCUSTOMSCLEARANCE>No</ISCUSTOMSCLEARANCE>
                           <ISTRACKCOMPONENT>No</ISTRACKCOMPONENT>
                           <ISTRACKPRODUCTION>No</ISTRACKPRODUCTION>
                           <ISPRIMARYITEM>No</ISPRIMARYITEM>
                           <ISSCRAP>No</ISSCRAP>
                           <ACTUALQTY>"""+quantity+" "+uom+"""</ACTUALQTY>
                           <BILLEDQTY>"""+quantity+" "+uom+"""</BILLEDQTY>
                           <BATCHALLOCATIONS.LIST>
                            <GODOWNNAME>"""+godown_name+"""</GODOWNNAME>
                            <BATCHNAME>Primary Batch</BATCHNAME>
                            <DESTINATIONGODOWNNAME>"""+godown_name+"""</DESTINATIONGODOWNNAME>
                            <INDENTNO/>
                            <ORDERNO/>
                            <TRACKINGNUMBER/>
                            <DYNAMICCSTISCLEARED>No</DYNAMICCSTISCLEARED>
                            <ACTUALQTY>"""+quantity+" "+uom+"""</ACTUALQTY>
                            <BILLEDQTY>"""+quantity+" "+uom+"""</BILLEDQTY>
                            <ADDITIONALDETAILS.LIST>        </ADDITIONALDETAILS.LIST>
                            <VOUCHERCOMPONENTLIST.LIST>        </VOUCHERCOMPONENTLIST.LIST>
                           </BATCHALLOCATIONS.LIST>
                           <DUTYHEADDETAILS.LIST>       </DUTYHEADDETAILS.LIST>
                           <SUPPLEMENTARYDUTYHEADDETAILS.LIST>       </SUPPLEMENTARYDUTYHEADDETAILS.LIST>
                           <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
                           <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
                           <REFVOUCHERDETAILS.LIST>       </REFVOUCHERDETAILS.LIST>
                           <EXCISEALLOCATIONS.LIST>       </EXCISEALLOCATIONS.LIST>
                           <EXPENSEALLOCATIONS.LIST>       </EXPENSEALLOCATIONS.LIST>
                          </INVENTORYENTRIESIN.LIST> 
                """
                print("params1",params1)
                params2=params2+params1

            params="""
                     <ENVELOPE>
                     <HEADER>
                      <TALLYREQUEST>Import Data</TALLYREQUEST>
                     </HEADER>
                     <BODY>
                      <IMPORTDATA>
                       <REQUESTDESC>
                        <REPORTNAME>Vouchers</REPORTNAME>
                        <STATICVARIABLES>
                         <SVCURRENTCOMPANY>"""+tally_company+"""</SVCURRENTCOMPANY>
                        </STATICVARIABLES>
                       </REQUESTDESC>
                       <REQUESTDATA>
                        <TALLYMESSAGE xmlns:UDF="TallyUDF">
                         <VOUCHER REMOTEID=" """+GUID+""" " VCHKEY="" VCHTYPE="Stock Journal" ACTION="Create" OBJVIEW="Consumption Voucher View">
                          <OLDAUDITENTRYIDS.LIST TYPE="Number">
                           <OLDAUDITENTRYIDS>-1</OLDAUDITENTRYIDS>
                          </OLDAUDITENTRYIDS.LIST>
                          <DATE>"""+Date+"""</DATE>
                          <GUID>"""+GUID+"""</GUID>
                          <VOUCHERTYPENAME>Stock Journal</VOUCHERTYPENAME>
                          <VOUCHERNUMBER/>
                          <CSTFORMISSUETYPE/>
                          <CSTFORMRECVTYPE/>
                          <FBTPAYMENTTYPE>Default</FBTPAYMENTTYPE>
                          <PERSISTEDVIEW>Consumption Voucher View</PERSISTEDVIEW>
                          <VCHGSTCLASS/>
                          <DESTINATIONGODOWN>"""+godown_name+"""</DESTINATIONGODOWN>
                          <DIFFACTUALQTY>No</DIFFACTUALQTY>
                          <ISMSTFROMSYNC>No</ISMSTFROMSYNC>
                          <ASORIGINAL>No</ASORIGINAL>
                          <AUDITED>No</AUDITED>
                          <FORJOBCOSTING>No</FORJOBCOSTING>
                          <ISOPTIONAL>No</ISOPTIONAL>
                          <EFFECTIVEDATE>"""+Date+"""</EFFECTIVEDATE>
                          <USEFOREXCISE>No</USEFOREXCISE>
                          <ISFORJOBWORKIN>No</ISFORJOBWORKIN>
                          <ALLOWCONSUMPTION>No</ALLOWCONSUMPTION>
                          <USEFORINTEREST>No</USEFORINTEREST>
                          <USEFORGAINLOSS>No</USEFORGAINLOSS>
                          <USEFORGODOWNTRANSFER>No</USEFORGODOWNTRANSFER>
                          <USEFORCOMPOUND>No</USEFORCOMPOUND>
                          <USEFORSERVICETAX>No</USEFORSERVICETAX>
                          <ISDELETED>No</ISDELETED>
                          <ISONHOLD>No</ISONHOLD>
                          <ISBOENOTAPPLICABLE>No</ISBOENOTAPPLICABLE>
                          <ISEXCISEVOUCHER>No</ISEXCISEVOUCHER>
                          <EXCISETAXOVERRIDE>No</EXCISETAXOVERRIDE>
                          <USEFORTAXUNITTRANSFER>No</USEFORTAXUNITTRANSFER>
                          <IGNOREPOSVALIDATION>No</IGNOREPOSVALIDATION>
                          <EXCISEOPENING>No</EXCISEOPENING>
                          <USEFORFINALPRODUCTION>No</USEFORFINALPRODUCTION>
                          <ISTDSOVERRIDDEN>No</ISTDSOVERRIDDEN>
                          <ISTCSOVERRIDDEN>No</ISTCSOVERRIDDEN>
                          <ISTDSTCSCASHVCH>No</ISTDSTCSCASHVCH>
                          <INCLUDEADVPYMTVCH>No</INCLUDEADVPYMTVCH>
                          <ISSUBWORKSCONTRACT>No</ISSUBWORKSCONTRACT>
                          <ISVATOVERRIDDEN>No</ISVATOVERRIDDEN>
                          <IGNOREORIGVCHDATE>No</IGNOREORIGVCHDATE>
                          <ISVATPAIDATCUSTOMS>No</ISVATPAIDATCUSTOMS>
                          <ISDECLAREDTOCUSTOMS>No</ISDECLAREDTOCUSTOMS>
                          <ISSERVICETAXOVERRIDDEN>No</ISSERVICETAXOVERRIDDEN>
                          <ISISDVOUCHER>No</ISISDVOUCHER>
                          <ISEXCISEOVERRIDDEN>No</ISEXCISEOVERRIDDEN>
                          <ISEXCISESUPPLYVCH>No</ISEXCISESUPPLYVCH>
                          <ISGSTOVERRIDDEN>No</ISGSTOVERRIDDEN>
                          <GSTNOTEXPORTED>No</GSTNOTEXPORTED>
                          <IGNOREGSTINVALIDATION>No</IGNOREGSTINVALIDATION>
                          <ISGSTREFUND>No</ISGSTREFUND>
                          <ISGSTSECSEVENAPPLICABLE>No</ISGSTSECSEVENAPPLICABLE>
                          <ISVATPRINCIPALACCOUNT>No</ISVATPRINCIPALACCOUNT>
                          <ISSHIPPINGWITHINSTATE>No</ISSHIPPINGWITHINSTATE>
                          <ISOVERSEASTOURISTTRANS>No</ISOVERSEASTOURISTTRANS>
                          <ISDESIGNATEDZONEPARTY>No</ISDESIGNATEDZONEPARTY>
                          <ISCANCELLED>No</ISCANCELLED>
                          <HASCASHFLOW>No</HASCASHFLOW>
                          <ISPOSTDATED>No</ISPOSTDATED>
                          <USETRACKINGNUMBER>No</USETRACKINGNUMBER>
                          <ISINVOICE>No</ISINVOICE>
                          <MFGJOURNAL>No</MFGJOURNAL>
                          <HASDISCOUNTS>No</HASDISCOUNTS>
                          <ASPAYSLIP>No</ASPAYSLIP>
                          <ISCOSTCENTRE>No</ISCOSTCENTRE>
                          <ISSTXNONREALIZEDVCH>No</ISSTXNONREALIZEDVCH>
                          <ISEXCISEMANUFACTURERON>No</ISEXCISEMANUFACTURERON>
                          <ISBLANKCHEQUE>No</ISBLANKCHEQUE>
                          <ISVOID>No</ISVOID>
                          <ORDERLINESTATUS>No</ORDERLINESTATUS>
                          <VATISAGNSTCANCSALES>No</VATISAGNSTCANCSALES>
                          <VATISPURCEXEMPTED>No</VATISPURCEXEMPTED>
                          <ISVATRESTAXINVOICE>No</ISVATRESTAXINVOICE>
                          <VATISASSESABLECALCVCH>No</VATISASSESABLECALCVCH>
                          <ISVATDUTYPAID>Yes</ISVATDUTYPAID>
                          <ISDELIVERYSAMEASCONSIGNEE>No</ISDELIVERYSAMEASCONSIGNEE>
                          <ISDISPATCHSAMEASCONSIGNOR>No</ISDISPATCHSAMEASCONSIGNOR>
                          <CHANGEVCHMODE>No</CHANGEVCHMODE>
                          <ALTERID/> 
                          <MASTERID/>
                          <VOUCHERKEY/>
                          <EWAYBILLDETAILS.LIST>      </EWAYBILLDETAILS.LIST>
                          <EXCLUDEDTAXATIONS.LIST>      </EXCLUDEDTAXATIONS.LIST>
                          <OLDAUDITENTRIES.LIST>      </OLDAUDITENTRIES.LIST>
                          <ACCOUNTAUDITENTRIES.LIST>      </ACCOUNTAUDITENTRIES.LIST>
                          <AUDITENTRIES.LIST>      </AUDITENTRIES.LIST>
                          <DUTYHEADDETAILS.LIST>      </DUTYHEADDETAILS.LIST>
                          <SUPPLEMENTARYDUTYHEADDETAILS.LIST>      </SUPPLEMENTARYDUTYHEADDETAILS.LIST>
                          <INVOICEDELNOTES.LIST>      </INVOICEDELNOTES.LIST>
                          <INVOICEORDERLIST.LIST>      </INVOICEORDERLIST.LIST>
                          <INVOICEINDENTLIST.LIST>      </INVOICEINDENTLIST.LIST>
                          <ATTENDANCEENTRIES.LIST>      </ATTENDANCEENTRIES.LIST>
                          <ORIGINVOICEDETAILS.LIST>      </ORIGINVOICEDETAILS.LIST>
                          <INVOICEEXPORTLIST.LIST>      </INVOICEEXPORTLIST.LIST>
                          """+params2+"""
                          <INVENTORYENTRIESOUT.LIST>      </INVENTORYENTRIESOUT.LIST>
                          <PAYROLLMODEOFPAYMENT.LIST>      </PAYROLLMODEOFPAYMENT.LIST>
                          <ATTDRECORDS.LIST>      </ATTDRECORDS.LIST>
                          <GSTEWAYCONSIGNORADDRESS.LIST>      </GSTEWAYCONSIGNORADDRESS.LIST>
                          <GSTEWAYCONSIGNEEADDRESS.LIST>      </GSTEWAYCONSIGNEEADDRESS.LIST>
                          <TEMPGSTRATEDETAILS.LIST>      </TEMPGSTRATEDETAILS.LIST>
                         </VOUCHER>
                        </TALLYMESSAGE>
                        <TALLYMESSAGE xmlns:UDF="TallyUDF">
                         <COMPANY>
                          <REMOTECMPINFO.LIST MERGE="Yes">
                           <NAME/>
                           <REMOTECMPNAME>"""+tally_company+"""</REMOTECMPNAME>
                           <REMOTECMPSTATE/>
                          </REMOTECMPINFO.LIST>
                         </COMPANY>
                        </TALLYMESSAGE>
                        <TALLYMESSAGE xmlns:UDF="TallyUDF">
                         <COMPANY>
                          <REMOTECMPINFO.LIST MERGE="Yes">
                           <NAME/>
                           <REMOTECMPNAME>"""+tally_company+"""</REMOTECMPNAME>
                           <REMOTECMPSTATE/>
                          </REMOTECMPINFO.LIST>
                         </COMPANY>
                        </TALLYMESSAGE>
                       </REQUESTDATA>
                      </IMPORTDATA>
                     </BODY>
                    </ENVELOPE>
"""
            print("paramsparamsparamsparamsparams",params)
            if create_xml:
                f = open("vouchers.xml", "a+")
                f.write(params)
                f.close()
                created_in_tally = True
                line.write({'created_in_tally': created_in_tally})
            else:
                res = requests.post(url, data=params, headers={'Content-Type': 'application/xml'})
                print("RESPONSE+++++++++++", res)
                # print ("responseeeeeeeeee text",res.text)
                # print("responseeeeeeeeee text", type(res.text))
                # print("responseeeeeeeeee contentttttttttt", res.content)
                root = ET.fromstring(res.content)
                created_in_tally = False
                print("root", res.content)
                if len(root) > 9:
                    if root[0].tag == 'LINEERROR':
                        sync_dict = {}
                        sync_dict = {
                            'object': 'stock.inventory',
                            'name': 'Inventory Adustments',
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
                        print(" im here in created")
                    line.write({'created_in_tally': created_in_tally})
                else:
                    print("elseeeeeeeeeee", root[0].tag)
                    if root[0].tag == 'CREATED':
                        print("root[0].text", root[0].text)
                        if root[0].text == '1':
                            created_in_tally = True
                    print("line and altred ,createddd", line, created_in_tally)
                    line.write({'created_in_tally': created_in_tally})

        #issueObj=self.env['stock.issues'].search([('id', '=', 2)])
        issueObj = self.env['stock.issues'].search([('state', 'in', ('done',)), ('company_id', '=', company.id)],order='id')
        # issueObj = self.env['stock.issues'].search([('state', 'in', ('done',)), ('company_id', '=', company.id),('created_in_tally','=',False)],order='id')
        for lines in issueObj:
            movelineobj=lines.move_line_ids
            loca = lines.location_id
            godown = self.env['stock.warehouse'].search([('lot_stock_id', '=', loca.id)])
            godown_name = godown.name
            godown_name = self.env['test.connection']._check_and_opt(godown_name)
            name=lines.name
            GUIDS='Iss'+str(name[-4:])+str(lines.id)
            VchDate = str(datetime.strptime(lines.date, "%Y-%m-%d %H:%M:%S").date())
            vch_year = VchDate[0:4]
            vch_date = VchDate[-2:]
            vch_month = VchDate[-5:-3]
            date1 = str(vch_year) + str(vch_month) + str(vch_date)

            params3=''
            for moveline in movelineobj:
                if moveline.product_id.attribute_value_ids:
                    attr_name = ''
                    for val in moveline.product_id.attribute_value_ids:
                        if val.attribute_id:
                            attr_name = attr_name + val.attribute_id.name + ':' + val.name + ','
                        else:
                            attr_name = attr_name + 'Attribute' + ':' + val.name + ','
                        print("valllllllllll", val)
                    if attr_name:
                        product_name = moveline.product_id.name + '(' + attr_name + ')'
                    else:
                        product_name = moveline.product_id.name
                else:
                    product_name = moveline.product_id.name
                product_name = self.env['test.connection']._check_and_opt(product_name)
                uom=moveline.product_uom_id.name
                quantity= str(int(moveline.qty_done))
                params4="""
                   <INVENTORYENTRIESOUT.LIST>
                   <STOCKITEMNAME>"""+product_name+"""</STOCKITEMNAME>
                   <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
                   <ISLASTDEEMEDPOSITIVE>No</ISLASTDEEMEDPOSITIVE>
                   <ISAUTONEGATE>No</ISAUTONEGATE>
                   <ISCUSTOMSCLEARANCE>No</ISCUSTOMSCLEARANCE>
                   <ISTRACKCOMPONENT>No</ISTRACKCOMPONENT>
                   <ISTRACKPRODUCTION>No</ISTRACKPRODUCTION>
                   <ISPRIMARYITEM>No</ISPRIMARYITEM>
                   <ISSCRAP>No</ISSCRAP>
                   <ACTUALQTY>"""+quantity+" "+uom+"""</ACTUALQTY>
                   <BILLEDQTY>"""+quantity+" "+uom+"""</BILLEDQTY>
                   <BATCHALLOCATIONS.LIST>
                    <GODOWNNAME>"""+godown_name+"""</GODOWNNAME>
                    <BATCHNAME>Primary Batch</BATCHNAME>
                    <INDENTNO/>
                    <ORDERNO/>
                    <TRACKINGNUMBER/>
                    <DYNAMICCSTISCLEARED>No</DYNAMICCSTISCLEARED>
                    <ACTUALQTY>"""+quantity+" "+uom+"""</ACTUALQTY>
                    <BILLEDQTY>"""+quantity+" "+uom+"""</BILLEDQTY>
                    <ADDITIONALDETAILS.LIST>        </ADDITIONALDETAILS.LIST>
                    <VOUCHERCOMPONENTLIST.LIST>        </VOUCHERCOMPONENTLIST.LIST>
                   </BATCHALLOCATIONS.LIST>
                   <DUTYHEADDETAILS.LIST>       </DUTYHEADDETAILS.LIST>
                   <SUPPLEMENTARYDUTYHEADDETAILS.LIST>       </SUPPLEMENTARYDUTYHEADDETAILS.LIST>
                   <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
                   <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
                   <REFVOUCHERDETAILS.LIST>       </REFVOUCHERDETAILS.LIST>
                   <EXCISEALLOCATIONS.LIST>       </EXCISEALLOCATIONS.LIST>
                   <EXPENSEALLOCATIONS.LIST>       </EXPENSEALLOCATIONS.LIST>
                  </INVENTORYENTRIESOUT.LIST>
                  """
                params3=params3+params4

            params="""
                     <ENVELOPE>
                     <HEADER>
                      <TALLYREQUEST>Import Data</TALLYREQUEST>
                     </HEADER>
                     <BODY>
                      <IMPORTDATA>
                       <REQUESTDESC>
                        <REPORTNAME>Vouchers</REPORTNAME>
                        <STATICVARIABLES>
                         <SVCURRENTCOMPANY>"""+tally_company+"""</SVCURRENTCOMPANY>
                        </STATICVARIABLES>
                       </REQUESTDESC>
                       <REQUESTDATA>
                        <TALLYMESSAGE xmlns:UDF="TallyUDF">
                         <VOUCHER REMOTEID=" """+GUIDS+""" " VCHKEY="" VCHTYPE="Stock Journal" ACTION="Create" OBJVIEW="Consumption Voucher View">
                          <OLDAUDITENTRYIDS.LIST TYPE="Number">
                           <OLDAUDITENTRYIDS>-1</OLDAUDITENTRYIDS>
                          </OLDAUDITENTRYIDS.LIST>
                          <DATE>"""+date1+"""</DATE>
                          <GUID>"""+GUIDS+"""</GUID>
                          <VOUCHERTYPENAME>Stock Journal</VOUCHERTYPENAME>
                          <VOUCHERNUMBER/>
                          <CSTFORMISSUETYPE/>
                          <CSTFORMRECVTYPE/>
                          <FBTPAYMENTTYPE>Default</FBTPAYMENTTYPE>
                          <PERSISTEDVIEW>Consumption Voucher View</PERSISTEDVIEW>
                          <VCHGSTCLASS/>
                          <DIFFACTUALQTY>No</DIFFACTUALQTY>
                          <ISMSTFROMSYNC>No</ISMSTFROMSYNC>
                          <ASORIGINAL>No</ASORIGINAL>
                          <AUDITED>No</AUDITED>
                          <FORJOBCOSTING>No</FORJOBCOSTING>
                          <ISOPTIONAL>No</ISOPTIONAL>
                          <EFFECTIVEDATE>"""+date1+"""</EFFECTIVEDATE>
                          <USEFOREXCISE>No</USEFOREXCISE>
                          <ISFORJOBWORKIN>No</ISFORJOBWORKIN>
                          <ALLOWCONSUMPTION>No</ALLOWCONSUMPTION>
                          <USEFORINTEREST>No</USEFORINTEREST>
                          <USEFORGAINLOSS>No</USEFORGAINLOSS>
                          <USEFORGODOWNTRANSFER>No</USEFORGODOWNTRANSFER>
                          <USEFORCOMPOUND>No</USEFORCOMPOUND>
                          <USEFORSERVICETAX>No</USEFORSERVICETAX>
                          <ISDELETED>No</ISDELETED>
                          <ISONHOLD>No</ISONHOLD>
                          <ISBOENOTAPPLICABLE>No</ISBOENOTAPPLICABLE>
                          <ISEXCISEVOUCHER>No</ISEXCISEVOUCHER>
                          <EXCISETAXOVERRIDE>No</EXCISETAXOVERRIDE>
                          <USEFORTAXUNITTRANSFER>No</USEFORTAXUNITTRANSFER>
                          <IGNOREPOSVALIDATION>No</IGNOREPOSVALIDATION>
                          <EXCISEOPENING>No</EXCISEOPENING>
                          <USEFORFINALPRODUCTION>No</USEFORFINALPRODUCTION>
                          <ISTDSOVERRIDDEN>No</ISTDSOVERRIDDEN>
                          <ISTCSOVERRIDDEN>No</ISTCSOVERRIDDEN>
                          <ISTDSTCSCASHVCH>No</ISTDSTCSCASHVCH>
                          <INCLUDEADVPYMTVCH>No</INCLUDEADVPYMTVCH>
                          <ISSUBWORKSCONTRACT>No</ISSUBWORKSCONTRACT>
                          <ISVATOVERRIDDEN>No</ISVATOVERRIDDEN>
                          <IGNOREORIGVCHDATE>No</IGNOREORIGVCHDATE>
                          <ISVATPAIDATCUSTOMS>No</ISVATPAIDATCUSTOMS>
                          <ISDECLAREDTOCUSTOMS>No</ISDECLAREDTOCUSTOMS>
                          <ISSERVICETAXOVERRIDDEN>No</ISSERVICETAXOVERRIDDEN>
                          <ISISDVOUCHER>No</ISISDVOUCHER>
                          <ISEXCISEOVERRIDDEN>No</ISEXCISEOVERRIDDEN>
                          <ISEXCISESUPPLYVCH>No</ISEXCISESUPPLYVCH>
                          <ISGSTOVERRIDDEN>No</ISGSTOVERRIDDEN>
                          <GSTNOTEXPORTED>No</GSTNOTEXPORTED>
                          <IGNOREGSTINVALIDATION>No</IGNOREGSTINVALIDATION>
                          <ISGSTREFUND>No</ISGSTREFUND>
                          <ISGSTSECSEVENAPPLICABLE>No</ISGSTSECSEVENAPPLICABLE>
                          <ISVATPRINCIPALACCOUNT>No</ISVATPRINCIPALACCOUNT>
                          <ISSHIPPINGWITHINSTATE>No</ISSHIPPINGWITHINSTATE>
                          <ISOVERSEASTOURISTTRANS>No</ISOVERSEASTOURISTTRANS>
                          <ISDESIGNATEDZONEPARTY>No</ISDESIGNATEDZONEPARTY>
                          <ISCANCELLED>No</ISCANCELLED>
                          <HASCASHFLOW>No</HASCASHFLOW>
                          <ISPOSTDATED>No</ISPOSTDATED>
                          <USETRACKINGNUMBER>No</USETRACKINGNUMBER>
                          <ISINVOICE>No</ISINVOICE>
                          <MFGJOURNAL>No</MFGJOURNAL>
                          <HASDISCOUNTS>No</HASDISCOUNTS>
                          <ASPAYSLIP>No</ASPAYSLIP>
                          <ISCOSTCENTRE>No</ISCOSTCENTRE>
                          <ISSTXNONREALIZEDVCH>No</ISSTXNONREALIZEDVCH>
                          <ISEXCISEMANUFACTURERON>No</ISEXCISEMANUFACTURERON>
                          <ISBLANKCHEQUE>No</ISBLANKCHEQUE>
                          <ISVOID>No</ISVOID>
                          <ORDERLINESTATUS>No</ORDERLINESTATUS>
                          <VATISAGNSTCANCSALES>No</VATISAGNSTCANCSALES>
                          <VATISPURCEXEMPTED>No</VATISPURCEXEMPTED>
                          <ISVATRESTAXINVOICE>No</ISVATRESTAXINVOICE>
                          <VATISASSESABLECALCVCH>No</VATISASSESABLECALCVCH>
                          <ISVATDUTYPAID>Yes</ISVATDUTYPAID>
                          <ISDELIVERYSAMEASCONSIGNEE>No</ISDELIVERYSAMEASCONSIGNEE>
                          <ISDISPATCHSAMEASCONSIGNOR>No</ISDISPATCHSAMEASCONSIGNOR>
                          <CHANGEVCHMODE>No</CHANGEVCHMODE>
                          <ALTERID/>
                          <MASTERID/>
                          <VOUCHERKEY/>
                          <EWAYBILLDETAILS.LIST>      </EWAYBILLDETAILS.LIST>
                          <EXCLUDEDTAXATIONS.LIST>      </EXCLUDEDTAXATIONS.LIST>
                          <OLDAUDITENTRIES.LIST>      </OLDAUDITENTRIES.LIST>
                          <ACCOUNTAUDITENTRIES.LIST>      </ACCOUNTAUDITENTRIES.LIST>
                          <AUDITENTRIES.LIST>      </AUDITENTRIES.LIST>
                          <DUTYHEADDETAILS.LIST>      </DUTYHEADDETAILS.LIST>
                          <SUPPLEMENTARYDUTYHEADDETAILS.LIST>      </SUPPLEMENTARYDUTYHEADDETAILS.LIST>
                          <INVOICEDELNOTES.LIST>      </INVOICEDELNOTES.LIST>
                          <INVOICEORDERLIST.LIST>      </INVOICEORDERLIST.LIST>
                          <INVOICEINDENTLIST.LIST>      </INVOICEINDENTLIST.LIST>
                          <ATTENDANCEENTRIES.LIST>      </ATTENDANCEENTRIES.LIST>
                          <ORIGINVOICEDETAILS.LIST>      </ORIGINVOICEDETAILS.LIST>
                          <INVOICEEXPORTLIST.LIST>      </INVOICEEXPORTLIST.LIST>
                          <INVENTORYENTRIESIN.LIST>      </INVENTORYENTRIESIN.LIST>
                           """+params3+"""
                          <PAYROLLMODEOFPAYMENT.LIST>      </PAYROLLMODEOFPAYMENT.LIST>
                          <ATTDRECORDS.LIST>      </ATTDRECORDS.LIST>
                          <GSTEWAYCONSIGNORADDRESS.LIST>      </GSTEWAYCONSIGNORADDRESS.LIST>
                          <GSTEWAYCONSIGNEEADDRESS.LIST>      </GSTEWAYCONSIGNEEADDRESS.LIST>
                          <TEMPGSTRATEDETAILS.LIST>      </TEMPGSTRATEDETAILS.LIST>
                         </VOUCHER>
                        </TALLYMESSAGE>
                        <TALLYMESSAGE xmlns:UDF="TallyUDF">
                         <COMPANY>
                          <REMOTECMPINFO.LIST MERGE="Yes">
                           <NAME/>
                           <REMOTECMPNAME>"""+tally_company+"""</REMOTECMPNAME>
                           <REMOTECMPSTATE/>
                          </REMOTECMPINFO.LIST>
                         </COMPANY>
                        </TALLYMESSAGE>
                        <TALLYMESSAGE xmlns:UDF="TallyUDF">
                         <COMPANY>
                          <REMOTECMPINFO.LIST MERGE="Yes">
                           <NAME/>
                           <REMOTECMPNAME>"""+tally_company+"""</REMOTECMPNAME>
                           <REMOTECMPSTATE/>
                          </REMOTECMPINFO.LIST>
                         </COMPANY>
                        </TALLYMESSAGE>
                       </REQUESTDATA>
                      </IMPORTDATA>
                     </BODY>
                    </ENVELOPE>
                    """
            if create_xml:
                f = open("vouchers.xml", "a+")
                f.write(params)
                f.close()
                created_in_tally = True
                lines.write({'created_in_tally': created_in_tally})
            else:
                res = requests.post(url, data=params, headers={'Content-Type': 'application/xml'})
                print("RESPONSE+++++++++++", res)
                # print ("responseeeeeeeeee text",res.text)

                root = ET.fromstring(res.content)
                created_in_tally = False
                print("root", res.content)
                if len(root) > 9:
                    if root[0].tag == 'LINEERROR':
                        sync_dict = {}
                        sync_dict = {
                            'object': 'stock.issues',
                            'name': 'Inventory Issues',
                            'total_records': 1,
                            'record_name': lines.name,
                            'log_date': datetime.now(),
                            'reason': root[0].text,
                            # 'no_imported': 1,
                        }
                        self.env['sync.logs'].create(sync_dict)
                    if root[1].tag == 'CREATED':
                        if root[1].text == '1':
                            created_in_tally = True
                        print(" im here in created")
                    lines.write({'created_in_tally': created_in_tally})
                else:
                    print("elseeeeeeeeeee", root[0].tag)
                    if root[0].tag == 'CREATED':
                        print("root[0].text", root[0].text)
                        if root[0].text == '1':
                            created_in_tally = True
                    print("line and altred ,createddd", lines, created_in_tally)
                    lines.write({'created_in_tally': created_in_tally})






        return True