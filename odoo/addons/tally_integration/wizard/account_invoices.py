from odoo import api, fields, models, _
from odoo.exceptions import UserError
import requests
from datetime import datetime
from xml.etree import ElementTree as ET

class AccountInvoices(models.Model):
    _name = 'account.invoices.import'

    @api.multi
    def create_AccountInvoices(self, url, company, tally_company,create_xml):
        #f = open("vouchers.xml", "w+")
        tally_company = tally_company
        tally_company = self.env['test.connection']._check_and_opt(tally_company)
        #invoices = self.env['account.invoice'].search([('state', 'in', ('open', 'paid')),('type','in',('out_invoice','in_invoice','out_refund','in_refund')),('company_id','=',company.id),('created_in_tally','=',False)], order='id')
        invoices = self.env['account.invoice'].search([('state', 'in', ('open', 'paid')),('type','in',('out_invoice','in_invoice','out_refund','in_refund')),('company_id','=',company.id)], order='id')
        #invoices = self.env['account.invoice'].search([('id','in', (27,))])
        print("invoices",invoices)
        for line in invoices:
            PartyName = line.partner_id.name
            PartyName = self.env['test.connection']._check_and_opt(PartyName)
            movelineObj = self.env['account.invoice.line'].search([('invoice_id', '=', line.id)])
            if movelineObj:
                Narration = line.number
                Narration = self.env['test.connection']._check_and_opt(Narration)
                GUID = Narration
                if line.type == 'out_invoice':
                    VchType = 'Sales'
                    print("VchType===", VchType)
                    Amount = str(str('-')+str(line.amount_total))
                    deemedpos = 'Yes'
                    basicbuyername=PartyName
                    excise_manf='No'
                    GUID='s'+GUID
                    reference = line.number
                    VchDate = line.date_invoice
                    # params5 = self.supply_party_ledger(PartyName, deemedpos, Amount)
                if line.type == 'in_invoice':
                    VchType = 'Purchase'
                    print("VchType===", VchType)
                    Amount = str(line.amount_total)
                    deemedpos = 'No'
                    basicbuyername = tally_company
                    excise_manf='Yes'
                    GUID = 'p' + GUID
                    reference = line.reference
                    VchDate = line.doc_date
                if line.type == 'out_refund':
                    VchType = 'Credit Note'
                    deemedpos = 'No'
                    Amount = str(line.amount_total)
                    basicbuyername = PartyName
                    excise_manf = 'No'
                    GUID = 'sr' + GUID
                    #reference=line.origin
                    inv_line = self.env['account.invoice.line'].search([('invoice_id', '=', line.id)], limit=1)
                    reference = inv_line.origin_line.number
                    VchDate = line.date_invoice
                if line.type == 'in_refund':
                    VchType = 'Debit Note'
                    deemedpos = 'Yes'
                    Amount = str(str('-')+str(line.amount_total))
                    basicbuyername = tally_company
                    excise_manf = 'No'
                    GUID = 'pr' + GUID
                    #reference = line.reference
                    inv_line = self.env['account.invoice.line'].search([('invoice_id', '=', line.id)], limit=1)
                    reference = inv_line.origin_line.number
                    VchDate = line.doc_date
                    # print(VchType,Amount,basicbuyername,reference)

                print("++++++++GUID++++++++",GUID)

                vch_year = VchDate[0:4]
                vch_date = VchDate[-2:]
                vch_month = VchDate[-5:-3]
                Date = str(vch_year) + str(vch_month) + str(vch_date)

                params2 = ''
                params5 = ''
                for prod_line in  movelineObj:
                    if prod_line.product_id:
                    # product_name=prod_line.product_id.name
                        if prod_line.product_id.attribute_value_ids:
                            attr_name = ''
                            for val in prod_line.product_id.attribute_value_ids:
                                if val.attribute_id:
                                    attr_name = attr_name + val.attribute_id.name + ':' + val.name + ','
                                else:
                                    attr_name = attr_name + 'Attribute' + ':' + val.name + ','
                                print("valllllllllll", val)
                            if attr_name:
                                product_name = prod_line.product_id.name + '(' + attr_name + ')'
                            else:
                                product_name = prod_line.product_id.name
                        else:
                            product_name = prod_line.product_id.name
                        product_name=self.env['test.connection']._check_and_opt(product_name)
                        if VchType in ('Purchase','Credit Note'):
                            deemed_pos = 'Yes'
                            price_subtotal = str(str('-')+str(prod_line.price_subtotal))
                        elif VchType in ('Sales','Debit Note'):
                            deemed_pos = 'No'
                            price_subtotal = str(prod_line.price_subtotal)
                        account_name=prod_line.account_id.name
                        account_name = self.env['test.connection']._check_and_opt(account_name)
                        quantity = str(prod_line.quantity)
                        uom=prod_line.uom_id.name
                        if not uom:
                            uom= prod_line.product_id.uom_id.name
                        #uom='Units'
                        if prod_line.discount:
                            price_unit =str(prod_line.price_unit - (prod_line.price_unit * (prod_line.discount)/100))
                        else:
                            price_unit = str(prod_line.price_unit)

                        print("uom", uom)
                        warehouse = self.env['stock.warehouse'].search([('company_id', '=', company.id)])
                        godown = warehouse.name
                        godown = self.env['test.connection']._check_and_opt(godown)


                        params1="""<INVENTORYENTRIES.LIST>
                               <STOCKITEMNAME>"""+product_name+"""</STOCKITEMNAME>
                               <ISDEEMEDPOSITIVE>"""+deemed_pos+"""</ISDEEMEDPOSITIVE>
                               <ISLASTDEEMEDPOSITIVE>"""+deemed_pos+"""</ISLASTDEEMEDPOSITIVE>
                               <ISAUTONEGATE>No</ISAUTONEGATE>
                               <ISCUSTOMSCLEARANCE>No</ISCUSTOMSCLEARANCE>
                               <ISTRACKCOMPONENT>No</ISTRACKCOMPONENT>
                               <ISTRACKPRODUCTION>No</ISTRACKPRODUCTION>
                               <ISPRIMARYITEM>No</ISPRIMARYITEM>
                               <ISSCRAP>No</ISSCRAP>
                               <RATE>"""+price_unit+"""/"""+uom+"""</RATE>
                               <AMOUNT>"""+price_subtotal+"""</AMOUNT>
                               <ACTUALQTY> """+quantity+" "+uom+"""</ACTUALQTY>
                               <BILLEDQTY> """+quantity+" "+uom+"""</BILLEDQTY>
                               <BATCHALLOCATIONS.LIST>
                                <GODOWNNAME>"""+godown+"""</GODOWNNAME>
                                <BATCHNAME>Primary Batch</BATCHNAME>
                                <DESTINATIONGODOWNNAME>"""+godown+"""</DESTINATIONGODOWNNAME>
                                <INDENTNO/>
                                <ORDERNO/>
                                <TRACKINGNUMBER/>
                                <DYNAMICCSTISCLEARED>No</DYNAMICCSTISCLEARED>
                                <AMOUNT>"""+price_subtotal+"""</AMOUNT>
                                <ACTUALQTY> """+quantity+" "+uom+"""</ACTUALQTY>
                                <BILLEDQTY> """+quantity+" "+uom+"""</BILLEDQTY>
                                <ADDITIONALDETAILS.LIST>        </ADDITIONALDETAILS.LIST>
                                <VOUCHERCOMPONENTLIST.LIST>        </VOUCHERCOMPONENTLIST.LIST>
                               </BATCHALLOCATIONS.LIST>
                               <ACCOUNTINGALLOCATIONS.LIST>
                                <OLDAUDITENTRYIDS.LIST TYPE="Number">
                                 <OLDAUDITENTRYIDS>-1</OLDAUDITENTRYIDS>
                                </OLDAUDITENTRYIDS.LIST>
                                <LEDGERNAME>"""+account_name+"""</LEDGERNAME>
                                <GSTCLASS/>
                                <ISDEEMEDPOSITIVE>"""+deemed_pos+"""</ISDEEMEDPOSITIVE>
                                <LEDGERFROMITEM>No</LEDGERFROMITEM>
                                <REMOVEZEROENTRIES>No</REMOVEZEROENTRIES>
                                <ISPARTYLEDGER>No</ISPARTYLEDGER>
                                <ISLASTDEEMEDPOSITIVE>"""+deemed_pos+"""</ISLASTDEEMEDPOSITIVE>
                                <ISCAPVATTAXALTERED>No</ISCAPVATTAXALTERED>
                                <ISCAPVATNOTCLAIMED>No</ISCAPVATNOTCLAIMED>
                                <AMOUNT>"""+price_subtotal+"""</AMOUNT>
                                <SERVICETAXDETAILS.LIST>        </SERVICETAXDETAILS.LIST>
                                <BANKALLOCATIONS.LIST>        </BANKALLOCATIONS.LIST>
                                <BILLALLOCATIONS.LIST>        </BILLALLOCATIONS.LIST>
                                <INTERESTCOLLECTION.LIST>        </INTERESTCOLLECTION.LIST>
                                <OLDAUDITENTRIES.LIST>        </OLDAUDITENTRIES.LIST>
                                <ACCOUNTAUDITENTRIES.LIST>        </ACCOUNTAUDITENTRIES.LIST>
                                <AUDITENTRIES.LIST>        </AUDITENTRIES.LIST>
                                <INPUTCRALLOCS.LIST>        </INPUTCRALLOCS.LIST>
                                <DUTYHEADDETAILS.LIST>        </DUTYHEADDETAILS.LIST>
                                <EXCISEDUTYHEADDETAILS.LIST>        </EXCISEDUTYHEADDETAILS.LIST>
                                <RATEDETAILS.LIST>        </RATEDETAILS.LIST>
                                <SUMMARYALLOCS.LIST>        </SUMMARYALLOCS.LIST>
                                <STPYMTDETAILS.LIST>        </STPYMTDETAILS.LIST>
                                <EXCISEPAYMENTALLOCATIONS.LIST>        </EXCISEPAYMENTALLOCATIONS.LIST>
                                <TAXBILLALLOCATIONS.LIST>        </TAXBILLALLOCATIONS.LIST>
                                <TAXOBJECTALLOCATIONS.LIST>        </TAXOBJECTALLOCATIONS.LIST>
                                <TDSEXPENSEALLOCATIONS.LIST>        </TDSEXPENSEALLOCATIONS.LIST>
                                <VATSTATUTORYDETAILS.LIST>        </VATSTATUTORYDETAILS.LIST>
                                <COSTTRACKALLOCATIONS.LIST>        </COSTTRACKALLOCATIONS.LIST>
                                <REFVOUCHERDETAILS.LIST>        </REFVOUCHERDETAILS.LIST>
                                <INVOICEWISEDETAILS.LIST>        </INVOICEWISEDETAILS.LIST>
                                <VATITCDETAILS.LIST>        </VATITCDETAILS.LIST>
                                <ADVANCETAXDETAILS.LIST>        </ADVANCETAXDETAILS.LIST>
                               </ACCOUNTINGALLOCATIONS.LIST>
                               <DUTYHEADDETAILS.LIST>       </DUTYHEADDETAILS.LIST>
                               <SUPPLEMENTARYDUTYHEADDETAILS.LIST>       </SUPPLEMENTARYDUTYHEADDETAILS.LIST>
                               <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
                               <REFVOUCHERDETAILS.LIST>       </REFVOUCHERDETAILS.LIST>
                               <EXCISEALLOCATIONS.LIST>       </EXCISEALLOCATIONS.LIST>
                               <EXPENSEALLOCATIONS.LIST>       </EXPENSEALLOCATIONS.LIST>
                              </INVENTORYENTRIES.LIST>"""
                    else:
                        params1=''
                        ledgername = prod_line.account_id.name
                        ledgername = self.env['test.connection']._check_and_opt(ledgername)

                        if VchType in ('Purchase','Credit Note'):
                            deemed_pos2 = 'Yes'
                            if prod_line.price_subtotal>0:
                                amout = str(str('-') + str(prod_line.price_subtotal))
                            else:
                                amout = str(abs(prod_line.price_subtotal))

                        elif VchType in ('Sales','Debit Note'):
                            deemed_pos2 = 'No'
                            amout = str(prod_line.price_subtotal)

                        params6="""<LEDGERENTRIES.LIST>
                                   <OLDAUDITENTRYIDS.LIST TYPE="Number">
                                    <OLDAUDITENTRYIDS>-1</OLDAUDITENTRYIDS>
                                   </OLDAUDITENTRYIDS.LIST>
                                   <LEDGERNAME>"""+ledgername+"""</LEDGERNAME>
                                   <GSTCLASS/>
                                   <ISDEEMEDPOSITIVE>"""+deemed_pos2+"""</ISDEEMEDPOSITIVE>
                                   <LEDGERFROMITEM>No</LEDGERFROMITEM>
                                   <REMOVEZEROENTRIES>No</REMOVEZEROENTRIES>
                                   <ISPARTYLEDGER>No</ISPARTYLEDGER>
                                   <ISLASTDEEMEDPOSITIVE>"""+deemed_pos2+"""</ISLASTDEEMEDPOSITIVE>
                                   <ISCAPVATTAXALTERED>No</ISCAPVATTAXALTERED>
                                   <ISCAPVATNOTCLAIMED>No</ISCAPVATNOTCLAIMED>
                                   <AMOUNT>"""+amout+"""</AMOUNT>
                                   <VATEXPAMOUNT>"""+amout+"""</VATEXPAMOUNT>
                                   <SERVICETAXDETAILS.LIST>       </SERVICETAXDETAILS.LIST>
                                   <BANKALLOCATIONS.LIST>       </BANKALLOCATIONS.LIST>
                                   <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
                                   <INTERESTCOLLECTION.LIST>       </INTERESTCOLLECTION.LIST>
                                   <OLDAUDITENTRIES.LIST>       </OLDAUDITENTRIES.LIST>
                                   <ACCOUNTAUDITENTRIES.LIST>       </ACCOUNTAUDITENTRIES.LIST>
                                   <AUDITENTRIES.LIST>       </AUDITENTRIES.LIST>
                                   <INPUTCRALLOCS.LIST>       </INPUTCRALLOCS.LIST>
                                   <DUTYHEADDETAILS.LIST>       </DUTYHEADDETAILS.LIST>
                                   <EXCISEDUTYHEADDETAILS.LIST>       </EXCISEDUTYHEADDETAILS.LIST>
                                   <RATEDETAILS.LIST>       </RATEDETAILS.LIST>
                                   <SUMMARYALLOCS.LIST>       </SUMMARYALLOCS.LIST>
                                   <STPYMTDETAILS.LIST>       </STPYMTDETAILS.LIST>
                                   <EXCISEPAYMENTALLOCATIONS.LIST>       </EXCISEPAYMENTALLOCATIONS.LIST>
                                   <TAXBILLALLOCATIONS.LIST>       </TAXBILLALLOCATIONS.LIST>
                                   <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
                                   <TDSEXPENSEALLOCATIONS.LIST>       </TDSEXPENSEALLOCATIONS.LIST>
                                   <VATSTATUTORYDETAILS.LIST>       </VATSTATUTORYDETAILS.LIST>
                                   <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
                                   <REFVOUCHERDETAILS.LIST>       </REFVOUCHERDETAILS.LIST>
                                   <INVOICEWISEDETAILS.LIST>       </INVOICEWISEDETAILS.LIST>
                                   <VATITCDETAILS.LIST>       </VATITCDETAILS.LIST>
                                   <ADVANCETAXDETAILS.LIST>       </ADVANCETAXDETAILS.LIST>
                                  </LEDGERENTRIES.LIST>
                        """
                        params5=params5+params6

                    params2=params2+params1

                params3=''
                tax_lines = line.tax_line_ids
                for tax_line in tax_lines:
                    tax_detail = self.env['account.tax'].search([('id', '=',tax_line.tax_id.id)])
                    tax_account=tax_detail.account_id.name
                    tax_account = self.env['test.connection']._check_and_opt(tax_account)
                    tax_per=str(tax_detail.amount)
                    tax_amount= round(tax_line.amount,2)
                    if VchType in ('Purchase','Credit Note'):
                        deemed_pos1 = 'Yes'
                        tax_amount = str(str('-') + str(tax_amount))
                    elif VchType in ('Sales','Debit Note'):
                        deemed_pos1 = 'No'
                        tax_amount = str(tax_amount)
                    params4="""
                               <LEDGERENTRIES.LIST>
                               <OLDAUDITENTRYIDS.LIST TYPE="Number">
                                <OLDAUDITENTRYIDS>-1</OLDAUDITENTRYIDS>
                               </OLDAUDITENTRYIDS.LIST>
                               <BASICRATEOFINVOICETAX.LIST TYPE="Number">
                                <BASICRATEOFINVOICETAX> """+tax_per+"""</BASICRATEOFINVOICETAX>
                               </BASICRATEOFINVOICETAX.LIST>
                               <LEDGERNAME>"""+tax_account+"""</LEDGERNAME>
                               <GSTCLASS/>
                               <ISDEEMEDPOSITIVE>"""+deemed_pos1+"""</ISDEEMEDPOSITIVE>
                               <LEDGERFROMITEM>No</LEDGERFROMITEM>
                               <REMOVEZEROENTRIES>No</REMOVEZEROENTRIES>
                               <ISPARTYLEDGER>No</ISPARTYLEDGER>
                               <ISLASTDEEMEDPOSITIVE>"""+deemed_pos1+"""</ISLASTDEEMEDPOSITIVE>
                               <ISCAPVATTAXALTERED>No</ISCAPVATTAXALTERED>
                               <ISCAPVATNOTCLAIMED>No</ISCAPVATNOTCLAIMED>
                               <AMOUNT>"""+tax_amount+"""</AMOUNT>
                               <VATEXPAMOUNT>"""+tax_amount+"""</VATEXPAMOUNT>
                               <SERVICETAXDETAILS.LIST>       </SERVICETAXDETAILS.LIST>
                               <BANKALLOCATIONS.LIST>       </BANKALLOCATIONS.LIST>
                               <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
                               <INTERESTCOLLECTION.LIST>       </INTERESTCOLLECTION.LIST>
                               <OLDAUDITENTRIES.LIST>       </OLDAUDITENTRIES.LIST>
                               <ACCOUNTAUDITENTRIES.LIST>       </ACCOUNTAUDITENTRIES.LIST>
                               <AUDITENTRIES.LIST>       </AUDITENTRIES.LIST>
                               <INPUTCRALLOCS.LIST>       </INPUTCRALLOCS.LIST>
                               <DUTYHEADDETAILS.LIST>       </DUTYHEADDETAILS.LIST>
                               <EXCISEDUTYHEADDETAILS.LIST>       </EXCISEDUTYHEADDETAILS.LIST>
                               <RATEDETAILS.LIST>       </RATEDETAILS.LIST>
                               <SUMMARYALLOCS.LIST>       </SUMMARYALLOCS.LIST>
                               <STPYMTDETAILS.LIST>       </STPYMTDETAILS.LIST>
                               <EXCISEPAYMENTALLOCATIONS.LIST>       </EXCISEPAYMENTALLOCATIONS.LIST>
                               <TAXBILLALLOCATIONS.LIST>       </TAXBILLALLOCATIONS.LIST>
                               <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
                               <TDSEXPENSEALLOCATIONS.LIST>       </TDSEXPENSEALLOCATIONS.LIST>
                               <VATSTATUTORYDETAILS.LIST>       </VATSTATUTORYDETAILS.LIST>
                               <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
                               <REFVOUCHERDETAILS.LIST>       </REFVOUCHERDETAILS.LIST>
                               <INVOICEWISEDETAILS.LIST>       </INVOICEWISEDETAILS.LIST>
                               <VATITCDETAILS.LIST>       </VATITCDETAILS.LIST>
                               <ADVANCETAXDETAILS.LIST>       </ADVANCETAXDETAILS.LIST>
                              </LEDGERENTRIES.LIST>
                    """
                    params3=params3+params4

                params="""<ENVELOPE>
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
                           <REQUESTDATA>0
                            <TALLYMESSAGE xmlns:UDF="TallyUDF">
                             <VOUCHER REMOTEID=" """+GUID+""" " VCHKEY="" VCHTYPE=" """+VchType+""" " ACTION="Create" OBJVIEW="Invoice Voucher View">
                              <OLDAUDITENTRYIDS.LIST TYPE="Number">
                               <OLDAUDITENTRYIDS>-1</OLDAUDITENTRYIDS>
                              </OLDAUDITENTRYIDS.LIST>
                              <DATE>"""+Date+""" </DATE>
                              <GUID>"""+GUID+""" </GUID>
                              <NARRATION></NARRATION>
                              <COUNTRYOFRESIDENCE>India</COUNTRYOFRESIDENCE>
                              <PARTYNAME>"""+PartyName+"""</PARTYNAME>
                              <PARTYLEDGERNAME>"""+PartyName+"""</PARTYLEDGERNAME>
                              <VOUCHERTYPENAME>"""+VchType+"""</VOUCHERTYPENAME>
                              <REFERENCE>"""+reference+"""</REFERENCE>
                              <VOUCHERNUMBER/>
                              <BASICBASEPARTYNAME>"""+PartyName+"""</BASICBASEPARTYNAME>
                              <CSTFORMISSUETYPE/>
                              <CSTFORMRECVTYPE/>
                              <FBTPAYMENTTYPE>Default</FBTPAYMENTTYPE>
                              <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
                              <BASICBUYERNAME>"""+basicbuyername+"""</BASICBUYERNAME>
                              <BASICDATETIMEOFINVOICE/>
                              <BASICDATETIMEOFREMOVAL/>
                              <VCHGSTCLASS/>
                              <CONSIGNEESTATENAME/>
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
                              <ISINVOICE>Yes</ISINVOICE>
                              <MFGJOURNAL>No</MFGJOURNAL>
                              <HASDISCOUNTS>No</HASDISCOUNTS>
                              <ASPAYSLIP>No</ASPAYSLIP>
                              <ISCOSTCENTRE>No</ISCOSTCENTRE>
                              <ISSTXNONREALIZEDVCH>No</ISSTXNONREALIZEDVCH>
                              <ISEXCISEMANUFACTURERON>"""+excise_manf+"""</ISEXCISEMANUFACTURERON>
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
                              """+params2+"""
                              <SUPPLEMENTARYDUTYHEADDETAILS.LIST>      </SUPPLEMENTARYDUTYHEADDETAILS.LIST>
                              <INVOICEDELNOTES.LIST>      </INVOICEDELNOTES.LIST>
                              <INVOICEORDERLIST.LIST>      </INVOICEORDERLIST.LIST>
                              <INVOICEINDENTLIST.LIST>      </INVOICEINDENTLIST.LIST>
                              <ATTENDANCEENTRIES.LIST>      </ATTENDANCEENTRIES.LIST>
                              <ORIGINVOICEDETAILS.LIST>      </ORIGINVOICEDETAILS.LIST>
                              <INVOICEEXPORTLIST.LIST>      </INVOICEEXPORTLIST.LIST>
                              <LEDGERENTRIES.LIST>
                               <OLDAUDITENTRYIDS.LIST TYPE="Number">
                                <OLDAUDITENTRYIDS>-1</OLDAUDITENTRYIDS>
                               </OLDAUDITENTRYIDS.LIST>
                               <LEDGERNAME>"""+PartyName+"""</LEDGERNAME>
                               <GSTCLASS/>
                               <ISDEEMEDPOSITIVE>"""+deemedpos+"""</ISDEEMEDPOSITIVE>
                               <LEDGERFROMITEM>No</LEDGERFROMITEM>
                               <REMOVEZEROENTRIES>No</REMOVEZEROENTRIES>
                               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
                               <ISLASTDEEMEDPOSITIVE>"""+deemedpos+"""</ISLASTDEEMEDPOSITIVE>
                               <ISCAPVATTAXALTERED>No</ISCAPVATTAXALTERED>
                               <ISCAPVATNOTCLAIMED>No</ISCAPVATNOTCLAIMED>
                               <AMOUNT>"""+Amount+"""</AMOUNT>
                               <SERVICETAXDETAILS.LIST>       </SERVICETAXDETAILS.LIST>
                               <BANKALLOCATIONS.LIST>       </BANKALLOCATIONS.LIST>
                               <BILLALLOCATIONS.LIST>
                                <NAME>1</NAME>
                                <BILLTYPE>New Ref</BILLTYPE>
                                <TDSDEDUCTEEISSPECIALRATE>No</TDSDEDUCTEEISSPECIALRATE>
                                <AMOUNT>"""+Amount+"""</AMOUNT>
                                <INTERESTCOLLECTION.LIST>        </INTERESTCOLLECTION.LIST>
                                <STBILLCATEGORIES.LIST>        </STBILLCATEGORIES.LIST>
                               </BILLALLOCATIONS.LIST>
                               <INTERESTCOLLECTION.LIST>       </INTERESTCOLLECTION.LIST>
                               <OLDAUDITENTRIES.LIST>       </OLDAUDITENTRIES.LIST>
                               <ACCOUNTAUDITENTRIES.LIST>       </ACCOUNTAUDITENTRIES.LIST>
                               <AUDITENTRIES.LIST>       </AUDITENTRIES.LIST>
                               <INPUTCRALLOCS.LIST>       </INPUTCRALLOCS.LIST>
                               <DUTYHEADDETAILS.LIST>       </DUTYHEADDETAILS.LIST>
                               <EXCISEDUTYHEADDETAILS.LIST>       </EXCISEDUTYHEADDETAILS.LIST>
                               <RATEDETAILS.LIST>       </RATEDETAILS.LIST>
                               <SUMMARYALLOCS.LIST>       </SUMMARYALLOCS.LIST>
                               <STPYMTDETAILS.LIST>       </STPYMTDETAILS.LIST>
                               <EXCISEPAYMENTALLOCATIONS.LIST>       </EXCISEPAYMENTALLOCATIONS.LIST>
                               <TAXBILLALLOCATIONS.LIST>       </TAXBILLALLOCATIONS.LIST>
                               <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
                               <TDSEXPENSEALLOCATIONS.LIST>       </TDSEXPENSEALLOCATIONS.LIST>
                               <VATSTATUTORYDETAILS.LIST>       </VATSTATUTORYDETAILS.LIST>
                               <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
                               <REFVOUCHERDETAILS.LIST>       </REFVOUCHERDETAILS.LIST>
                               <INVOICEWISEDETAILS.LIST>       </INVOICEWISEDETAILS.LIST>
                               <VATITCDETAILS.LIST>       </VATITCDETAILS.LIST>
                               <ADVANCETAXDETAILS.LIST>       </ADVANCETAXDETAILS.LIST>
                              </LEDGERENTRIES.LIST>
                              """+params3+params5+"""
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

                print("params", params)
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
                    print("root", res.content)
                    created_in_tally = False
                    if len(root) > 9:
                        if root[0].tag == 'LINEERROR':
                            #print(" im here in lineeror",root[0].tag)
                            altered_in_tally=False
                            sync_dict = {}
                            sync_dict = {
                                'object': 'account.invoice',
                                'name': 'Invoices',
                                'total_records': 1,
                                'record_name': line.number,
                                'log_date': datetime.now(),
                                'reason': root[0].text,
                                # 'no_imported': 1,
                            }
                            self.env['sync.logs'].create(sync_dict)
                        if root[1].tag == 'CREATED':
                            if root[1].text == '1':
                                created_in_tally = True
                            print(" im here in created")
                        line.write({'created_in_tally':created_in_tally})
                    else:
                        print ("elseeeeeeeeeee",root[0].tag)
                        if root[0].tag == 'CREATED':
                            print ("root[0].text",root[0].text)
                            if root[0].text == '1':
                                created_in_tally = True
                        print ("line and altred ,createddd",line,created_in_tally)
                        line.write({'created_in_tally':created_in_tally})

        return True
