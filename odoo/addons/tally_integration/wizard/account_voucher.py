from odoo import api, fields, models, _
from odoo.exceptions import UserError
import requests
import random
from datetime import datetime
from xml.etree import ElementTree as ET
import xml.etree.ElementTree as ETT


class AccountVoucherImport(models.Model):
    _name = 'account.voucher.import'
    
    @api.multi
    def create_voucher(self,url,company,tally_company,tally_transfer_type,create_xml):
        print('==Create Account Voucher==',url)
        #f = open("vouchers.xml", "w+")
        # moveObj = self.env['account.move'].search([])
        #moveObj = self.env['account.move'].search([('state', 'in', ('posted',)),('company_id','=',company.id),('created_in_tally','=',False)])
        moveObj = self.env['account.move'].search([('state', 'in', ('posted',)),('company_id','=',company.id)], order='id')
        print ("move print objjjjjjjjjjjjjjj",moveObj)
        tally_company = str(tally_company)
        tally_company = self.env['test.connection']._check_and_opt(tally_company)
        for line in moveObj:
            print("moveObj==",moveObj)
            lineobj=self.env['account.move.line'].search([('move_id', '=', line.id)], order='id asc')
            print("lineobj",lineobj)
            movelineObj = self.env['account.move.line'].search([('move_id', '=', line.id)], limit=1)
            if lineobj and movelineObj:
                PartyName = movelineObj.partner_id.name
                if not PartyName:
                    PartyName=''
                if movelineObj.partner_id:
                    PartyName = movelineObj.partner_id.name
                #PartyName = self.env['test.connection']._check_and_opt(PartyName)
                params5=''
                Narration = line.name
                Narration = self.env['test.connection']._check_and_opt(Narration)
                GUID = Narration
                GUID = self.env['test.connection']._check_and_opt(GUID)
                if line.journal_id.type == 'sale' and tally_transfer_type == True:
                    VchType = 'Sales'
                    print("VchType===",VchType)
                    VchView='Invoice Voucher View'
                    Amount = str(str('-')+str(line.amount))
                    deemedpos = 'Yes'
                    params5=self.supply_party_ledger(PartyName,deemedpos,Amount)
                    GUID = 'sale' + GUID
                elif line.journal_id.type == 'purchase' and tally_transfer_type== True:
                    VchType = 'Purchase'
                    VchView = 'Invoice Voucher View'
                    Amount = str(line.amount)
                    deemedpos = 'No'
                    params5 = self.supply_party_ledger(PartyName, deemedpos, Amount)
                    GUID = 'pur' + GUID
                elif line.journal_id.type == 'general':
                    VchType = 'Journal'
                    VchView='Accounting Voucher View'
                    GUID = 'jrnl' + GUID
                elif line.journal_id.type in ['cash','bank']:
                    VchType = 'Receipt'
                    VchView = 'Accounting Voucher View'
                    GUID = 'rcpt' + GUID
                elif line.journal_id.type in ['cash_payment','bank_payment']:
                    VchType = 'Payment'
                    VchView = 'Accounting Voucher View'
                    GUID = 'pyt' + GUID
                else:
                    continue
                print("VchType______=",VchType)
                #print(abc)
                VchType = self.env['test.connection']._check_and_opt(VchType)
                VchType=str(VchType)
                params10=""
                for move in lineobj:
                    print('acc name',move.account_id.name)
                    if VchType== 'Purchase':
                        if move.balance>0.0:
                            ledger_name=move.account_id.name
                            ledger_name = self.env['test.connection']._check_and_opt(ledger_name)
                            amount=str(str('-')+str(move.balance))
                            deemedpositive="Yes"
                            ISPARTYLEDGER='No'
                            params4=self.supply_ledger_entry(ledger_name,amount,deemedpositive,ISPARTYLEDGER)
                            params10=params10+params4
                    elif VchType == 'Sales':
                        if move.balance<0.0:
                            ledger_name=move.account_id.name
                            ledger_name = self.env['test.connection']._check_and_opt(ledger_name)
                            amount=str(move.credit)
                            deemedpositive = "No"
                            ISPARTYLEDGER='No'
                            params4=self.supply_ledger_entry(ledger_name,amount,deemedpositive,ISPARTYLEDGER)
                            print('params4',params4)
                            params10=params10+params4
                    elif VchType =='Journal':
                        ledger_name = move.account_id.name
                        ledger_name = self.env['test.connection']._check_and_opt(ledger_name)
                        if not movelineObj.partner_id:
                            if move.account_id.Type in ['Customer','Vendor']:
                                PartyName= move.account_id.partner_id.name
                        if move.debit>0.0:
                            amount = str(str('-') + str(move.debit))
                            deemedpositive = "Yes"
                        elif move.credit>0.0:
                            amount = str(move.credit)
                            deemedpositive = "No"
                        ISPARTYLEDGER='No'
                        params4 = self.supply_ledger_entry(ledger_name, amount, deemedpositive,ISPARTYLEDGER)
                        params10 = params10 + params4
                    elif VchType=='Payment' or VchType=='Receipt':
                        ledger_name = move.account_id.name
                        ledger_name = self.env['test.connection']._check_and_opt(ledger_name)
                        if move.debit > 0.0:
                            amount = str(str('-') + str(move.debit))
                            deemedpositive = "Yes"
                        elif move.credit > 0.0:
                            amount = str(move.credit)
                            deemedpositive = "No"
                        ISPARTYLEDGER = 'Yes'
                        params4 = self.supply_ledger_entry(ledger_name, amount, deemedpositive, ISPARTYLEDGER)
                        params10 = params10 + params4

                VchDate = line.date
                print('VchDateVchDateVchDate',VchDate)
                #print("PartyName==",movelineObj.partner_id,PartyName,VchDate)
                PartyName = self.env['test.connection']._check_and_opt(PartyName)
                vch_year= VchDate[0:4]
                vch_date = VchDate[-2:]
                vch_month = VchDate[-5:-3]
                Date = str(vch_year)+str(vch_month)+str(vch_date)

                print("GUID=====",GUID)
                params1 ="""
                <?xml version='1.0' encoding='utf-8'?>
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
                <VOUCHER REMOTEID=" """+GUID+""" " VCHKEY="" VCHTYPE=" """+VchType+""" " ACTION="Create" OBJVIEW=" """+VchView+""" ">
                <OLDAUDITENTRYIDS.LIST TYPE="Number">
                <OLDAUDITENTRYIDS>-1</OLDAUDITENTRYIDS>
                </OLDAUDITENTRYIDS.LIST>
                <DATE>"""+Date+"""</DATE>
                <GUID>"""+GUID+"""</GUID>
                <STATENAME/>
                <PARTYNAME>"""+PartyName+"""</PARTYNAME>
                <PARTYLEDGERNAME>"""+PartyName+"""</PARTYLEDGERNAME>
                <VOUCHERTYPENAME>"""+VchType+"""</VOUCHERTYPENAME>
                <VOUCHERNUMBER/>
                <BASICBASEPARTYNAME>"""+PartyName+"""</BASICBASEPARTYNAME>
                <CSTFORMISSUETYPE/>
                <CSTFORMRECVTYPE/>
                <FBTPAYMENTTYPE>Default</FBTPAYMENTTYPE>
                <PERSISTEDVIEW>"""+VchView+"""</PERSISTEDVIEW>
                <BASICBUYERNAME>"""+tally_company+"""</BASICBUYERNAME>
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
                <ISEXCISEMANUFACTURERON>Yes</ISEXCISEMANUFACTURERON>
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
                <INVENTORYENTRIES.LIST>      </INVENTORYENTRIES.LIST>
                <SUPPLEMENTARYDUTYHEADDETAILS.LIST>      </SUPPLEMENTARYDUTYHEADDETAILS.LIST>
                <INVOICEDELNOTES.LIST>      </INVOICEDELNOTES.LIST>
                <INVOICEORDERLIST.LIST>      </INVOICEORDERLIST.LIST>
                <INVOICEINDENTLIST.LIST>      </INVOICEINDENTLIST.LIST>
                <ATTENDANCEENTRIES.LIST>      </ATTENDANCEENTRIES.LIST>
                <ORIGINVOICEDETAILS.LIST>      </ORIGINVOICEDETAILS.LIST>
                <INVOICEEXPORTLIST.LIST>      </INVOICEEXPORTLIST.LIST>
                """+ params5 + params10+"""
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
                   <NAME></NAME>
                   <REMOTECMPNAME>"""+tally_company+"""</REMOTECMPNAME>
                   <REMOTECMPSTATE></REMOTECMPSTATE>
                  </REMOTECMPINFO.LIST>
                 </COMPANY>
                </TALLYMESSAGE>
                <TALLYMESSAGE xmlns:UDF="TallyUDF">
                 <COMPANY>
                  <REMOTECMPINFO.LIST MERGE="Yes">
                   <NAME></NAME>
                   <REMOTECMPNAME>"""+tally_company+"""</REMOTECMPNAME>
                   <REMOTECMPSTATE></REMOTECMPSTATE>
                  </REMOTECMPINFO.LIST>
                 </COMPANY>
                </TALLYMESSAGE>
               </REQUESTDATA>
              </IMPORTDATA>
             </BODY>
            </ENVELOPE>
"""

                params=params1
                print("params", params)
                if create_xml:
                    f = open("vouchers.xml", "a+")
                    f.write(params)
                    f.close()
                    created_in_tally = True
                    line.write({'created_in_tally': created_in_tally})
                else:
                    res = requests.post(url, data=params, headers={'Content-Type': 'application/xml'})
                    print("RESPONSE+++++++++++",res)
                    root = ET.fromstring(res.content)
                    print("root",root)
                    print("rres.content",res.content)
                    print("root[0] lengthhhhhhhh", len(root))
                    created_in_tally=False
                    altered_in_tally=False
                    if len(root) > 9:
                        if root[0].tag == 'LINEERROR':
                            #print(" im here in lineeror",root[0].tag)
                            altered_in_tally=False
                            sync_dict = {}
                            sync_dict = {
                                'object': 'account.move',
                                'name': 'Vouchers',
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
                        line.write({'altered_in_tally':altered_in_tally,'created_in_tally':created_in_tally})
                    else:
                        print ("elseeeeeeeeeee",root[0].tag)
                        if root[0].tag == 'CREATED':
                            print ("root[0].text",root[0].text)
                            if root[0].text == '1':
                                created_in_tally = True
                        if root[1].tag == 'ALTERED':
                            print("root[1].text alteredddddddd", root[0].text,root[1].text == '1')
                            if root[1].text == '1':
                                altered_in_tally = True
                        print ("line and altred ,createddd",line,altered_in_tally,created_in_tally)
                        line.write({'altered_in_tally':altered_in_tally,'created_in_tally':created_in_tally})
                    # for child in root:
                    #     print(child.tag)
                    #     print(child.attrib)

                    # for r in res.text:
                    #     print ("rrrrrrrrrrrrrrr",r)
                    # print("responseeeeeeeeee response_dict", response_dict)
        return True

    def supply_ledger_entry(self,ledger_name,amount,deemedpositive,ISPARTYLEDGER):
        params4 = """      <LEDGERENTRIES.LIST>
                           <OLDAUDITENTRYIDS.LIST TYPE="Number">
                            <OLDAUDITENTRYIDS>-1</OLDAUDITENTRYIDS>
                           </OLDAUDITENTRYIDS.LIST>
                           <LEDGERNAME>""" + ledger_name + """</LEDGERNAME>
                           <GSTCLASS/>
                           <ISDEEMEDPOSITIVE>"""+deemedpositive+"""</ISDEEMEDPOSITIVE>
                           <LEDGERFROMITEM>No</LEDGERFROMITEM>
                           <REMOVEZEROENTRIES>No</REMOVEZEROENTRIES>
                           <ISPARTYLEDGER>"""+ISPARTYLEDGER+"""</ISPARTYLEDGER>
                           <ISLASTDEEMEDPOSITIVE>"""+deemedpositive+"""</ISLASTDEEMEDPOSITIVE>
                           <ISCAPVATTAXALTERED>No</ISCAPVATTAXALTERED>
                           <ISCAPVATNOTCLAIMED>No</ISCAPVATNOTCLAIMED>
                           <AMOUNT>""" + amount + """</AMOUNT>
                           <VATEXPAMOUNT>""" + amount + """</VATEXPAMOUNT>
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
        return params4

    def supply_party_ledger(self,PartyName,deemedpos,Amount):
        params5 = """<LEDGERENTRIES.LIST>
                           <OLDAUDITENTRYIDS.LIST TYPE="Number">
                            <OLDAUDITENTRYIDS>-1</OLDAUDITENTRYIDS>
                           </OLDAUDITENTRYIDS.LIST>
                           <LEDGERNAME>""" + PartyName + """</LEDGERNAME>
                           <GSTCLASS/>
                           <ISDEEMEDPOSITIVE>""" + deemedpos + """</ISDEEMEDPOSITIVE>
                           <LEDGERFROMITEM>No</LEDGERFROMITEM>
                           <REMOVEZEROENTRIES>No</REMOVEZEROENTRIES>
                           <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
                           <ISLASTDEEMEDPOSITIVE>""" + deemedpos + """</ISLASTDEEMEDPOSITIVE>
                           <ISCAPVATTAXALTERED>No</ISCAPVATTAXALTERED>
                           <ISCAPVATNOTCLAIMED>No</ISCAPVATNOTCLAIMED>
                           <AMOUNT>""" + Amount + """</AMOUNT>
                           <SERVICETAXDETAILS.LIST>       </SERVICETAXDETAILS.LIST>
                           <BANKALLOCATIONS.LIST>       </BANKALLOCATIONS.LIST>
                           <BILLALLOCATIONS.LIST>
                            <NAME>1</NAME>
                            <BILLTYPE>New Ref</BILLTYPE>
                            <TDSDEDUCTEEISSPECIALRATE>No</TDSDEDUCTEEISSPECIALRATE>
                            <AMOUNT>""" + Amount + """</AMOUNT>
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
                          </LEDGERENTRIES.LIST>"""
        return params5
    
    
    
    
    
    