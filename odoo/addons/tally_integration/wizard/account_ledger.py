from odoo import api, fields, models, _
from odoo.exceptions import UserError
import requests
import random
import datetime
from datetime import datetime
from xml.etree import ElementTree as ET

class AccountLedger(models.Model):
    _name = 'account.ledger'
    
    @api.multi
    def create_ledger(self,url,company,tally_company,create_xml):
        print('==Create Account Ledger==',url)
        #f = open("masters.xml", "w+")
        Currency = self.env['res.currency'].search([('name','=','INR')])
        logo = Currency.symbol
        CurrnLogo = logo.encode('utf-8')
        print("currency logo=====",logo,CurrnLogo)
        # Name = self.env['res.partner'].search([('company_id', '=', company.id),('parent_id','=',False),('created_in_tally','=',False)], order='id')
        # #Name = self.env['res.partner'].search([('company_id', '=', company.id),('parent_id','=',False)], order='id')
        # print("Name",Name)
        # print ("lem of partner for ledgers lengthhhhhhhhh",len(Name))
        # tally_company = tally_company
        # tally_company = self.env['test.connection']._check_and_opt(tally_company)
        # for line in Name:
        #     print("PartyName====",line.name)
        #     PartyName = line.name
        #     PartyName = self.env['test.connection']._check_and_opt(PartyName)
        #     Address = str(line.street) + str(line.street2)
        #     print("Address====",Address)
        #     Address = self.env['test.connection']._check_and_opt(Address)
        #     state = line.state_id.name
        #     if state:
        #         state = line.state_id.name
        #     else:
        #         state = 'Delhi'
        #
        #     if line.customer:
        #         print("Customer Type==",line.customer)
        #         LedgerType = 'Sundry Debtors'
        #     else:
        #         LedgerType = 'Sundry Creditors'
        #         print("Customer Type+++++==",line.customer)
        #     LedgerType = self.env['test.connection']._check_and_opt(LedgerType)
        #
        #     params = """
        #         <?xml version='1.0' encoding='utf-8'?>
        #         <ENVELOPE>
        #         <HEADER>
        #         <TALLYREQUEST>Import Data</TALLYREQUEST>
        #         </HEADER>
        #         <BODY>
        #         <IMPORTDATA>
        #         <REQUESTDESC>
        #         <REPORTNAME>All Masters</REPORTNAME>
        #         <STATICVARIABLES>
        #         <SVCURRENTCOMPANY>""" + tally_company + """</SVCURRENTCOMPANY>
        #         </STATICVARIABLES>
        #         </REQUESTDESC>
        #         <REQUESTDATA>
        #         <TALLYMESSAGE xmlns:UDF="TallyUDF">
        #         <LEDGER NAME="" RESERVEDNAME="">
        #         <ADDRESS.LIST TYPE="String">
        #         <ADDRESS>""" + str(Address) + """</ADDRESS>
        #         </ADDRESS.LIST>
        #         <MAILINGNAME.LIST TYPE="String">
        #         <MAILINGNAME>""" + PartyName + """</MAILINGNAME>
        #         </MAILINGNAME.LIST>
        #         <OLDAUDITENTRYIDS.LIST TYPE="Number">
        #         <OLDAUDITENTRYIDS>-1</OLDAUDITENTRYIDS>
        #         </OLDAUDITENTRYIDS.LIST>
        #         <STARTINGFROM/>
        #         <STREGDATE/>
        #         <LBTREGNDATE/>
        #         <SAMPLINGDATEONEFACTOR/>
        #         <SAMPLINGDATETWOFACTOR/>
        #         <ACTIVEFROM/>
        #         <ACTIVETO/>
        #         <CREATEDDATE/>
        #         <ALTEREDON/>
        #         <VATAPPLICABLEDATE/>
        #         <EXCISEREGISTRATIONDATE/>
        #         <PANAPPLICABLEFROM/>
        #         <PAYINSRUNNINGFILEDATE/>
        #         <VATTAXEXEMPTIONDATE/>
        #         <GUID></GUID>
        #         <CURRENCYNAME>&#8377;</CURRENCYNAME>
        #         <EMAIL/>
        #         <STATENAME>"""+ state +"""</STATENAME>
        #         <PINCODE/>
        #         <WEBSITE/>
        #         <INCOMETAXNUMBER/>
        #         <SALESTAXNUMBER/>
        #         <INTERSTATESTNUMBER/>
        #         <VATTINNUMBER/>
        #         <COUNTRYNAME>India</COUNTRYNAME>
        #         <EXCISERANGE/>
        #         <EXCISEDIVISION/>
        #         <EXCISECOMMISSIONERATE/>
        #         <LBTREGNNO/>
        #         <LBTZONE/>
        #         <EXPORTIMPORTCODE/>
        #         <GSTREGISTRATIONTYPE>Regular</GSTREGISTRATIONTYPE>
        #         <VATDEALERTYPE>Regular</VATDEALERTYPE>
        #         <PRICELEVEL/>
        #         <UPLOADLASTREFRESH/>
        #         <PARENT>""" + LedgerType + """</PARENT>
        #         <SAMPLINGMETHOD/>
        #         <SAMPLINGSTRONEFACTOR/>
        #         <IFSCODE/>
        #         <NARRATION/>
        #         <REQUESTORRULE/>
        #         <GRPDEBITPARENT/>
        #         <GRPCREDITPARENT/>
        #         <SYSDEBITPARENT/>
        #         <SYSCREDITPARENT/>
        #         <TDSAPPLICABLE/>
        #         <TCSAPPLICABLE/>
        #         <GSTAPPLICABLE/>
        #         <CREATEDBY/>
        #         <ALTEREDBY/>
        #         <TAXCLASSIFICATIONNAME/>
        #         <TAXTYPE>Others</TAXTYPE>
        #         <BILLCREDITPERIOD/>
        #         <BANKDETAILS/>
        #         <BANKBRANCHNAME/>
        #         <BANKBSRCODE/>
        #         <DEDUCTEETYPE/>
        #         <BUSINESSTYPE/>
        #         <TYPEOFNOTIFICATION/>
        #         <MSMEREGNUMBER/>
        #         <COUNTRYOFRESIDENCE>India</COUNTRYOFRESIDENCE>
        #         <RELATEDPARTYID/>
        #         <RELPARTYISSUINGAUTHORITY/>
        #         <IMPORTEREXPORTERCODE/>
        #         <EMAILCC/>
        #         <DESCRIPTION/>
        #         <LEDADDLALLOCTYPE/>
        #         <TRANSPORTERID/>
        #         <LEDGERPHONE/>
        #         <LEDGERFAX/>
        #         <LEDGERCONTACT/>
        #         <LEDGERMOBILE/>
        #         <RELATIONTYPE/>
        #         <MAILINGNAMENATIVE/>
        #         <STATENAMENATIVE/>
        #         <COUNTRYNAMENATIVE/>
        #         <BASICTYPEOFDUTY/>
        #         <GSTTYPE/>
        #         <EXEMPTIONTYPE/>
        #         <APPROPRIATEFOR/>
        #         <SUBTAXTYPE/>
        #         <STXNATUREOFPARTY/>
        #         <NAMEONPAN/>
        #         <USEDFORTAXTYPE/>
        #         <ECOMMMERCHANTID/>
        #         <PARTYGSTIN/>
        #         <GSTDUTYHEAD/>
        #         <GSTAPPROPRIATETO/>
        #         <GSTTYPEOFSUPPLY/>
        #         <GSTNATUREOFSUPPLY/>
        #         <CESSVALUATIONMETHOD/>
        #         <PAYTYPE/>
        #         <PAYSLIPNAME/>
        #         <ATTENDANCETYPE/>
        #         <LEAVETYPE/>
        #         <CALCULATIONPERIOD/>
        #         <ROUNDINGMETHOD/>
        #         <COMPUTATIONTYPE/>
        #         <CALCULATIONTYPE/>
        #         <PAYSTATTYPE/>
        #         <PROFESSIONALTAXNUMBER/>
        #         <USERDEFINEDCALENDERTYPE/>
        #         <ITNATURE/>
        #         <ITCOMPONENT/>
        #         <NOTIFICATIONNUMBER/>
        #         <REGISTRATIONNUMBER/>
        #         <SERVICECATEGORY></SERVICECATEGORY>
        #         <ABATEMENTNOTIFICATIONNO/>
        #         <STXDUTYHEAD/>
        #         <STXCLASSIFICATION/>
        #         <NOTIFICATIONSLNO/>
        #         <SERVICETAXAPPLICABLE/>
        #         <EXCISELEDGERCLASSIFICATION/>
        #         <EXCISEREGISTRATIONNUMBER/>
        #         <EXCISEACCOUNTHEAD/>
        #         <EXCISEDUTYTYPE/>
        #         <EXCISEDUTYHEADCODE/>
        #         <EXCISEALLOCTYPE/>
        #         <EXCISEDUTYHEAD/>
        #         <NATUREOFSALES/>
        #         <EXCISENOTIFICATIONNO/>
        #         <EXCISEIMPORTSREGISTARTIONNO/>
        #         <EXCISEAPPLICABILITY/>
        #         <EXCISETYPEOFBRANCH/>
        #         <EXCISEDEFAULTREMOVAL/>
        #         <EXCISENOTIFICATIONSLNO/>
        #         <TYPEOFTARIFF/>
        #         <EXCISEREGNO/>
        #         <EXCISENATUREOFPURCHASE/>
        #         <TDSDEDUCTEETYPEMST/>
        #         <TDSRATENAME/>
        #         <TDSDEDUCTEESECTIONNUMBER/>
        #         <PANSTATUS/>
        #         <DEDUCTEEREFERENCE/>
        #         <TDSDEDUCTEETYPE/>
        #         <ITEXEMPTAPPLICABLE/>
        #         <TAXIDENTIFICATIONNO/>
        #         <LEDGERFBTCATEGORY/>
        #         <BRANCHCODE/>
        #         <CLIENTCODE/>
        #         <BANKINGCONFIGBANK/>
        #         <BANKINGCONFIGBANKID/>
        #         <BANKACCHOLDERNAME>Arkefilters</BANKACCHOLDERNAME>
        #         <USEFORPOSTYPE/>
        #         <PAYMENTGATEWAY/>
        #         <TYPEOFINTERESTON/>
        #         <BANKCONFIGIFSC/>
        #         <BANKCONFIGMICR/>
        #         <BANKCONFIGSHORTCODE/>
        #         <PYMTINSTOUTPUTNAME/>
        #         <PRODUCTCODETYPE/>
        #         <SALARYPYMTPRODUCTCODE/>
        #         <OTHERPYMTPRODUCTCODE/>
        #         <PAYMENTINSTLOCATION/>
        #         <ENCRPTIONLOCATION/>
        #         <NEWIMFLOCATION/>
        #         <IMPORTEDIMFLOCATION/>
        #         <BANKNEWSTATEMENTS/>
        #         <BANKIMPORTEDSTATEMENTS/>
        #         <BANKMICR/>
        #         <CORPORATEUSERNOECS/>
        #         <CORPORATEUSERNOACH/>
        #         <CORPORATEUSERNAME/>
        #         <IMFNAME/>
        #         <PAYINSBATCHNAME/>
        #         <LASTUSEDBATCHNAME/>
        #         <PAYINSFILENUMPERIOD/>
        #         <ENCRYPTEDBY/>
        #         <ENCRYPTEDID/>
        #         <ISOCURRENCYCODE/>
        #         <BANKCAPSULEID/>
        #         <SALESTAXCESSAPPLICABLE/>
        #         <BANKIBAN/>
        #         <VATTAXEXEMPTIONNATURE/>
        #         <VATTAXEXEMPTIONNUMBER/>
        #         <LEDSTATENAME/>
        #         <VATAPPLICABLE/>
        #         <PARTYBUSINESSTYPE/>
        #         <PARTYBUSINESSSTYLE/>
        #         <ISBILLWISEON>Yes</ISBILLWISEON>
        #         <ISCOSTCENTRESON>No</ISCOSTCENTRESON>
        #         <ISINTERESTON>No</ISINTERESTON>
        #         <ALLOWINMOBILE>No</ALLOWINMOBILE>
        #         <ISCOSTTRACKINGON>No</ISCOSTTRACKINGON>
        #         <ISBENEFICIARYCODEON>No</ISBENEFICIARYCODEON>
        #         <ISUPDATINGTARGETID>No</ISUPDATINGTARGETID>
        #         <ASORIGINAL>Yes</ASORIGINAL>
        #         <ISCONDENSED>No</ISCONDENSED>
        #         <AFFECTSSTOCK>No</AFFECTSSTOCK>
        #         <ISRATEINCLUSIVEVAT>No</ISRATEINCLUSIVEVAT>
        #         <FORPAYROLL>No</FORPAYROLL>
        #         <ISABCENABLED>No</ISABCENABLED>
        #         <ISCREDITDAYSCHKON>No</ISCREDITDAYSCHKON>
        #         <INTERESTONBILLWISE>No</INTERESTONBILLWISE>
        #         <OVERRIDEINTEREST>No</OVERRIDEINTEREST>
        #         <OVERRIDEADVINTEREST>No</OVERRIDEADVINTEREST>
        #         <USEFORVAT>No</USEFORVAT>
        #         <IGNORETDSEXEMPT>No</IGNORETDSEXEMPT>
        #         <ISTCSAPPLICABLE>No</ISTCSAPPLICABLE>
        #         <ISTDSAPPLICABLE>No</ISTDSAPPLICABLE>
        #         <ISFBTAPPLICABLE>No</ISFBTAPPLICABLE>
        #         <ISGSTAPPLICABLE>No</ISGSTAPPLICABLE>
        #         <ISEXCISEAPPLICABLE>No</ISEXCISEAPPLICABLE>
        #         <ISTDSEXPENSE>No</ISTDSEXPENSE>
        #         <ISEDLIAPPLICABLE>No</ISEDLIAPPLICABLE>
        #         <ISRELATEDPARTY>No</ISRELATEDPARTY>
        #         <USEFORESIELIGIBILITY>No</USEFORESIELIGIBILITY>
        #         <ISINTERESTINCLLASTDAY>No</ISINTERESTINCLLASTDAY>
        #         <APPROPRIATETAXVALUE>No</APPROPRIATETAXVALUE>
        #         <ISBEHAVEASDUTY>No</ISBEHAVEASDUTY>
        #         <INTERESTINCLDAYOFADDITION>No</INTERESTINCLDAYOFADDITION>
        #         <INTERESTINCLDAYOFDEDUCTION>No</INTERESTINCLDAYOFDEDUCTION>
        #         <ISOTHTERRITORYASSESSEE>No</ISOTHTERRITORYASSESSEE>
        #         <OVERRIDECREDITLIMIT>No</OVERRIDECREDITLIMIT>
        #         <ISAGAINSTFORMC>No</ISAGAINSTFORMC>
        #         <ISCHEQUEPRINTINGENABLED>Yes</ISCHEQUEPRINTINGENABLED>
        #         <ISPAYUPLOAD>No</ISPAYUPLOAD>
        #         <ISPAYBATCHONLYSAL>No</ISPAYBATCHONLYSAL>
        #         <ISBNFCODESUPPORTED>No</ISBNFCODESUPPORTED>
        #         <ALLOWEXPORTWITHERRORS>No</ALLOWEXPORTWITHERRORS>
        #         <CONSIDERPURCHASEFOREXPORT>No</CONSIDERPURCHASEFOREXPORT>
        #         <ISTRANSPORTER>No</ISTRANSPORTER>
        #         <USEFORNOTIONALITC>No</USEFORNOTIONALITC>
        #         <ISECOMMOPERATOR>No</ISECOMMOPERATOR>
        #         <SHOWINPAYSLIP>No</SHOWINPAYSLIP>
        #         <USEFORGRATUITY>No</USEFORGRATUITY>
        #         <ISTDSPROJECTED>No</ISTDSPROJECTED>
        #         <FORSERVICETAX>No</FORSERVICETAX>
        #         <ISINPUTCREDIT>No</ISINPUTCREDIT>
        #         <ISEXEMPTED>No</ISEXEMPTED>
        #         <ISABATEMENTAPPLICABLE>No</ISABATEMENTAPPLICABLE>
        #         <ISSTXPARTY>No</ISSTXPARTY>
        #         <ISSTXNONREALIZEDTYPE>No</ISSTXNONREALIZEDTYPE>
        #         <ISUSEDFORCVD>No</ISUSEDFORCVD>
        #         <LEDBELONGSTONONTAXABLE>No</LEDBELONGSTONONTAXABLE>
        #         <ISEXCISEMERCHANTEXPORTER>No</ISEXCISEMERCHANTEXPORTER>
        #         <ISPARTYEXEMPTED>No</ISPARTYEXEMPTED>
        #         <ISSEZPARTY>No</ISSEZPARTY>
        #         <TDSDEDUCTEEISSPECIALRATE>No</TDSDEDUCTEEISSPECIALRATE>
        #         <ISECHEQUESUPPORTED>No</ISECHEQUESUPPORTED>
        #         <ISEDDSUPPORTED>No</ISEDDSUPPORTED>
        #         <HASECHEQUEDELIVERYMODE>No</HASECHEQUEDELIVERYMODE>
        #         <HASECHEQUEDELIVERYTO>No</HASECHEQUEDELIVERYTO>
        #         <HASECHEQUEPRINTLOCATION>No</HASECHEQUEPRINTLOCATION>
        #         <HASECHEQUEPAYABLELOCATION>No</HASECHEQUEPAYABLELOCATION>
        #         <HASECHEQUEBANKLOCATION>No</HASECHEQUEBANKLOCATION>
        #         <HASEDDDELIVERYMODE>No</HASEDDDELIVERYMODE>
        #         <HASEDDDELIVERYTO>No</HASEDDDELIVERYTO>
        #         <HASEDDPRINTLOCATION>No</HASEDDPRINTLOCATION>
        #         <HASEDDPAYABLELOCATION>No</HASEDDPAYABLELOCATION>
        #         <HASEDDBANKLOCATION>No</HASEDDBANKLOCATION>
        #         <ISEBANKINGENABLED>No</ISEBANKINGENABLED>
        #         <ISEXPORTFILEENCRYPTED>No</ISEXPORTFILEENCRYPTED>
        #         <ISBATCHENABLED>No</ISBATCHENABLED>
        #         <ISPRODUCTCODEBASED>No</ISPRODUCTCODEBASED>
        #         <HASEDDCITY>No</HASEDDCITY>
        #         <HASECHEQUECITY>No</HASECHEQUECITY>
        #         <ISFILENAMEFORMATSUPPORTED>No</ISFILENAMEFORMATSUPPORTED>
        #         <HASCLIENTCODE>No</HASCLIENTCODE>
        #         <PAYINSISBATCHAPPLICABLE>No</PAYINSISBATCHAPPLICABLE>
        #         <PAYINSISFILENUMAPP>No</PAYINSISFILENUMAPP>
        #         <ISSALARYTRANSGROUPEDFORBRS>No</ISSALARYTRANSGROUPEDFORBRS>
        #         <ISEBANKINGSUPPORTED>No</ISEBANKINGSUPPORTED>
        #         <ISSCBUAE>No</ISSCBUAE>
        #         <ISBANKSTATUSAPP>No</ISBANKSTATUSAPP>
        #         <ISSALARYGROUPED>No</ISSALARYGROUPED>
        #         <USEFORPURCHASETAX>No</USEFORPURCHASETAX>
        #         <AUDITED>No</AUDITED>
        #         <SAMPLINGNUMONEFACTOR>0</SAMPLINGNUMONEFACTOR>
        #         <SAMPLINGNUMTWOFACTOR>0</SAMPLINGNUMTWOFACTOR>
        #         <SORTPOSITION> 1000</SORTPOSITION>
        #         <ALTERID> 178</ALTERID>
        #         <DEFAULTLANGUAGE>0</DEFAULTLANGUAGE>
        #         <RATEOFTAXCALCULATION>0</RATEOFTAXCALCULATION>
        #         <GRATUITYMONTHDAYS>0</GRATUITYMONTHDAYS>
        #         <GRATUITYLIMITMONTHS>0</GRATUITYLIMITMONTHS>
        #         <CALCULATIONBASIS>0</CALCULATIONBASIS>
        #         <ROUNDINGLIMIT>0</ROUNDINGLIMIT>
        #         <ABATEMENTPERCENTAGE>0</ABATEMENTPERCENTAGE>
        #         <TDSDEDUCTEESPECIALRATE>0</TDSDEDUCTEESPECIALRATE>
        #         <BENEFICIARYCODEMAXLENGTH>0</BENEFICIARYCODEMAXLENGTH>
        #         <ECHEQUEPRINTLOCATIONVERSION>0</ECHEQUEPRINTLOCATIONVERSION>
        #         <ECHEQUEPAYABLELOCATIONVERSION>0</ECHEQUEPAYABLELOCATIONVERSION>
        #         <EDDPRINTLOCATIONVERSION>0</EDDPRINTLOCATIONVERSION>
        #         <EDDPAYABLELOCATIONVERSION>0</EDDPAYABLELOCATIONVERSION>
        #         <PAYINSRUNNINGFILENUM>0</PAYINSRUNNINGFILENUM>
        #         <TRANSACTIONTYPEVERSION>0</TRANSACTIONTYPEVERSION>
        #         <PAYINSFILENUMLENGTH>0</PAYINSFILENUMLENGTH>
        #         <SAMPLINGAMTONEFACTOR/>
        #         <SAMPLINGAMTTWOFACTOR/>
        #         <OPENINGBALANCE/>
        #         <CREDITLIMIT/>
        #         <GRATUITYLIMITAMOUNT/>
        #         <ODLIMIT/>
        #         <TEMPGSTCGSTRATE>0</TEMPGSTCGSTRATE>
        #         <TEMPGSTSGSTRATE>0</TEMPGSTSGSTRATE>
        #         <TEMPGSTIGSTRATE>0</TEMPGSTIGSTRATE>
        #         <TEMPISVATFIELDSEDITED/>
        #         <TEMPAPPLDATE/>
        #         <TEMPCLASSIFICATION/>
        #         <TEMPNATURE/>
        #         <TEMPPARTYENTITY/>
        #         <TEMPBUSINESSNATURE/>
        #         <TEMPVATRATE>0</TEMPVATRATE>
        #         <TEMPADDLTAX>0</TEMPADDLTAX>
        #         <TEMPCESSONVAT>0</TEMPCESSONVAT>
        #         <TEMPTAXTYPE/>
        #         <TEMPMAJORCOMMODITYNAME/>
        #         <TEMPCOMMODITYNAME/>
        #         <TEMPCOMMODITYCODE/>
        #         <TEMPSUBCOMMODITYCODE/>
        #         <TEMPUOM/>
        #         <TEMPTYPEOFGOODS/>
        #         <TEMPTRADENAME/>
        #         <TEMPGOODSNATURE/>
        #         <TEMPSCHEDULE/>
        #         <TEMPSCHEDULESLNO/>
        #         <TEMPISINVDETAILSENABLE/>
        #         <TEMPLOCALVATRATE>0</TEMPLOCALVATRATE>
        #         <TEMPVALUATIONTYPE/>
        #         <TEMPISCALCONQTY/>
        #         <TEMPISSALETOLOCALCITIZEN/>
        #         <LEDISTDSAPPLICABLECURRLIAB/>
        #         <ISPRODUCTCODEEDITED/>
        #         <SERVICETAXDETAILS.LIST>      </SERVICETAXDETAILS.LIST>
        #         <LBTREGNDETAILS.LIST>      </LBTREGNDETAILS.LIST>
        #         <VATDETAILS.LIST>      </VATDETAILS.LIST>
        #         <SALESTAXCESSDETAILS.LIST>      </SALESTAXCESSDETAILS.LIST>
        #         <GSTDETAILS.LIST>      </GSTDETAILS.LIST>
        #         <LANGUAGENAME.LIST>
        #         <NAME.LIST TYPE="String">
        #         <NAME>""" + PartyName + """</NAME>
        #         </NAME.LIST>
        #         <LANGUAGEID> 1033</LANGUAGEID>
        #         </LANGUAGENAME.LIST>
        #         <XBRLDETAIL.LIST>      </XBRLDETAIL.LIST>
        #         <AUDITDETAILS.LIST>      </AUDITDETAILS.LIST>
        #         <SCHVIDETAILS.LIST>      </SCHVIDETAILS.LIST>
        #         <EXCISETARIFFDETAILS.LIST>      </EXCISETARIFFDETAILS.LIST>
        #         <TCSCATEGORYDETAILS.LIST>      </TCSCATEGORYDETAILS.LIST>
        #         <TDSCATEGORYDETAILS.LIST>      </TDSCATEGORYDETAILS.LIST>
        #         <SLABPERIOD.LIST>      </SLABPERIOD.LIST>
        #         <GRATUITYPERIOD.LIST>      </GRATUITYPERIOD.LIST>
        #         <ADDITIONALCOMPUTATIONS.LIST>      </ADDITIONALCOMPUTATIONS.LIST>
        #         <EXCISEJURISDICTIONDETAILS.LIST>      </EXCISEJURISDICTIONDETAILS.LIST>
        #         <EXCLUDEDTAXATIONS.LIST>      </EXCLUDEDTAXATIONS.LIST>
        #         <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
        #         <PAYMENTDETAILS.LIST>      </PAYMENTDETAILS.LIST>
        #         <BANKEXPORTFORMATS.LIST>      </BANKEXPORTFORMATS.LIST>
        #         <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
        #         <INTERESTCOLLECTION.LIST>      </INTERESTCOLLECTION.LIST>
        #         <LEDGERCLOSINGVALUES.LIST>      </LEDGERCLOSINGVALUES.LIST>
        #         <LEDGERAUDITCLASS.LIST>      </LEDGERAUDITCLASS.LIST>
        #         <OLDAUDITENTRIES.LIST>      </OLDAUDITENTRIES.LIST>
        #         <TDSEXEMPTIONRULES.LIST>      </TDSEXEMPTIONRULES.LIST>
        #         <DEDUCTINSAMEVCHRULES.LIST>      </DEDUCTINSAMEVCHRULES.LIST>
        #         <LOWERDEDUCTION.LIST>      </LOWERDEDUCTION.LIST>
        #         <STXABATEMENTDETAILS.LIST>      </STXABATEMENTDETAILS.LIST>
        #         <LEDMULTIADDRESSLIST.LIST>      </LEDMULTIADDRESSLIST.LIST>
        #         <STXTAXDETAILS.LIST>      </STXTAXDETAILS.LIST>
        #         <CHEQUERANGE.LIST>      </CHEQUERANGE.LIST>
        #         <DEFAULTVCHCHEQUEDETAILS.LIST>      </DEFAULTVCHCHEQUEDETAILS.LIST>
        #         <ACCOUNTAUDITENTRIES.LIST>      </ACCOUNTAUDITENTRIES.LIST>
        #         <AUDITENTRIES.LIST>      </AUDITENTRIES.LIST>
        #         <BRSIMPORTEDINFO.LIST>      </BRSIMPORTEDINFO.LIST>
        #         <AUTOBRSCONFIGS.LIST>      </AUTOBRSCONFIGS.LIST>
        #         <BANKURENTRIES.LIST>      </BANKURENTRIES.LIST>
        #         <DEFAULTCHEQUEDETAILS.LIST>      </DEFAULTCHEQUEDETAILS.LIST>
        #         <DEFAULTOPENINGCHEQUEDETAILS.LIST>      </DEFAULTOPENINGCHEQUEDETAILS.LIST>
        #         <CANCELLEDPAYALLOCATIONS.LIST>      </CANCELLEDPAYALLOCATIONS.LIST>
        #         <ECHEQUEPRINTLOCATION.LIST>      </ECHEQUEPRINTLOCATION.LIST>
        #         <ECHEQUEPAYABLELOCATION.LIST>      </ECHEQUEPAYABLELOCATION.LIST>
        #         <EDDPRINTLOCATION.LIST>      </EDDPRINTLOCATION.LIST>
        #         <EDDPAYABLELOCATION.LIST>      </EDDPAYABLELOCATION.LIST>
        #         <AVAILABLETRANSACTIONTYPES.LIST>      </AVAILABLETRANSACTIONTYPES.LIST>
        #         <LEDPAYINSCONFIGS.LIST>      </LEDPAYINSCONFIGS.LIST>
        #         <TYPECODEDETAILS.LIST>      </TYPECODEDETAILS.LIST>
        #         <FIELDVALIDATIONDETAILS.LIST>      </FIELDVALIDATIONDETAILS.LIST>
        #         <INPUTCRALLOCS.LIST>      </INPUTCRALLOCS.LIST>
        #         <GSTCLASSFNIGSTRATES.LIST>      </GSTCLASSFNIGSTRATES.LIST>
        #         <EXTARIFFDUTYHEADDETAILS.LIST>      </EXTARIFFDUTYHEADDETAILS.LIST>
        #         <VOUCHERTYPEPRODUCTCODES.LIST>      </VOUCHERTYPEPRODUCTCODES.LIST>
        #         </LEDGER>
        #         </TALLYMESSAGE>
        #         </REQUESTDATA>
        #         </IMPORTDATA>
        #         </BODY>
        #         </ENVELOPE>
        #      """
        #
        #     # res = requests.post(url, data=params, headers={'Content-Type': 'application/xml'})
        #     headers = {'Content-Type': 'application/xml'}
        #     print ("paramsparamsparamsparamsparams",params)
        #     res = requests.post(url, data=params.encode('utf-8'), headers=headers)
        #     root = ET.fromstring(res.content)
        #     # res = requests.post(url, data=params, headers={'Content-Type': 'application/xml'})
        #     print("response for ledgerssssssssss",res)
        #     created_in_tally = False
        #     altered_in_tally = False
        #     if len(root) > 9:
        #         if root[0].tag == 'LINEERROR':
        #             altered_in_tally = False
        #             sync_dict = {}
        #             sync_dict = {
        #                 'object': 'res.partner',
        #                 'name': 'Ledgers',
        #                 'total_records': 1,
        #                 'record_name': line.name,
        #                 'log_date': datetime.now(),
        #                 'reason': root[0].text,
        #                 # 'no_imported': 1,
        #             }
        #             self.env['sync.logs'].create(sync_dict)
        #         if root[1].tag == 'CREATED':
        #             if root[1].text == '1':
        #                 created_in_tally = True
        #         line.write({'created_in_tally': created_in_tally})
        #     else:
        #         print("elseeeeeeeeeee", root[0].tag)
        #         if root[0].tag == 'CREATED':
        #             print("root[0].text", root[0].text)
        #             if root[0].text == '1':
        #                 created_in_tally = True
        #         # print("line and altred ,createddd", line, altered_in_tally, created_in_tally)
        #         line.write({'created_in_tally': created_in_tally})

        #group = self.env['account.account'].search([('company_id', '=', company.id), ('created_in_tally', '=', False)],order='id')
        group = self.env['account.account'].search([('company_id', '=', company.id)], order='id')
        #group = self.env['account.account'].search([('group_id', '=',7)], order='id')
        for line in group:
            print("PartyName====", line.name)
            PartyName = line.name
            PartyName = self.env['test.connection']._check_and_opt(PartyName)
            #Address = str(line.street) + str(line.street2)
            #print("Address====", Address)
            #Address = self.env['test.connection']._check_and_opt(Address)
            # state = line.state_id.name
            # if state:
            #     state = line.state_id.name
            # else:
            #     state = 'Delhi'
            tax_type='Others'
            gst_duty=''
            tax_perc=''
            gst = ''
            gst_app='<GSTAPPLICABLE>&#4; Not Applicable</GSTAPPLICABLE>'
            if line.tally_account_type_id:
                # Parent = self.env['account.account.type'].search([('id', '=', line.user_type_id.id)])
                LedgerType = line.tally_account_type_id.name
            else:
                if line.group_id:
                    tax_master=''
                    LedgerType = line.group_id.name
                else:
                    Parent = self.env['account.account.type'].search([('id', '=', line.user_type_id.id)])
                    LedgerType = Parent.name
            if line.gst_applicable:
                if LedgerType == 'Duties & Taxes':
                    tax_type = 'GST'
                    tax_master = self.env['account.tax'].search([('id', '=', line.taxes.id)], limit=1)
                    tax_perc = tax_master.amount
                    if tax_master.tax_group_id.name == 'CGST':
                        gst_duty = 'Central Tax'
                    elif tax_master.tax_group_id.name == 'SGST':
                        gst_duty = 'State Tax'
                    elif tax_master.tax_group_id.name == 'IGST':
                        gst_duty = 'Integrated Tax'
                else:
                # elif LedgerType in ('Purchase Accounts','Sales Accounts'):

                # if LedgerType == 'Purchase Accounts':
                #     tax_master = self.env['account.tax'].search([('expense_account_id', '=', line.id)], limit=1)
                #     if tax_master.tax_group_id.name in ('CGST','SGST'):
                #         nat_trans="Purchase Taxable"
                #         ig_tax_pert=2*(tax_master.amount)
                #         cs_tax_pert=tax_master.amount
                #
                #     elif tax_master.tax_group_id.name == 'IGST':
                #         nat_trans= "Interstate Purchase Taxable"
                #         ig_tax_pert=tax_master.amount
                #         cs_tax_pert=(tax_master.amount)/2
                #
                #     print('tax_mastertax_mastertax_mastertax_mastertax_master',tax_master)
                #
                # elif LedgerType == 'Sales Accounts':
                #     tax_master = self.env['account.tax'].search([('income_account_id', '=', line.id)], limit=1)
                #     if tax_master.tax_group_id.name in ('CGST', 'SGST'):
                #         nat_trans = "Sales Taxable"
                #         ig_tax_pert = 2 * (tax_master.amount)
                #         cs_tax_pert = tax_master.amount
                #     elif tax_master.tax_group_id.name == 'IGST':
                #         nat_trans = "Interstate Sales Taxable"
                #         ig_tax_pert = tax_master.amount
                #         cs_tax_pert = (tax_master.amount)/2
                    gst_app = '<GSTAPPLICABLE>&#4; Applicable</GSTAPPLICABLE>'
                    tax_master = self.env['account.tax'].search([('id', '=', line.taxes.id)], limit=1)
                    if tax_master.tax_group_id.name in ('CGST', 'SGST'):
                        ig_tax_pert = 2 * (tax_master.amount)
                        cs_tax_pert = tax_master.amount
                    elif tax_master.tax_group_id.name == 'IGST':
                        ig_tax_pert = tax_master.amount
                        cs_tax_pert = (tax_master.amount) / 2
                    nat_trans = line.nat_trans.name
                    nat_trans = self.env['test.connection']._check_and_opt(nat_trans)
                    if nat_trans in ('Not Applicable',False) :
                        nat=''
                    else:
                        nat='< GSTNATUREOFTRANSACTION >'+ nat_trans + '< / GSTNATUREOFTRANSACTION >'

                    gst = """<GSTDETAILS.LIST>
                       <APPLICABLEFROM>20200401</APPLICABLEFROM>
                       <HSNMASTERNAME/>
                       <TAXABILITY>Taxable</TAXABILITY>
                       """+nat+"""
                       <ISREVERSECHARGEAPPLICABLE>No</ISREVERSECHARGEAPPLICABLE>
                       <ISNONGSTGOODS>No</ISNONGSTGOODS>
                       <GSTINELIGIBLEITC>No</GSTINELIGIBLEITC>
                       <INCLUDEEXPFORSLABCALC>No</INCLUDEEXPFORSLABCALC>
                       <STATEWISEDETAILS.LIST>
                        <STATENAME>&#4; Any</STATENAME>
                        <RATEDETAILS.LIST>
                         <GSTRATEDUTYHEAD>Central Tax</GSTRATEDUTYHEAD>
                         <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>
                         <GSTRATE> """ + str(cs_tax_pert) + """</GSTRATE>
                        </RATEDETAILS.LIST>
                        <RATEDETAILS.LIST>
                         <GSTRATEDUTYHEAD>State Tax</GSTRATEDUTYHEAD>
                         <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>
                         <GSTRATE> """ + str(cs_tax_pert) + """</GSTRATE>
                        </RATEDETAILS.LIST>
                        <RATEDETAILS.LIST>
                         <GSTRATEDUTYHEAD>Integrated Tax</GSTRATEDUTYHEAD>
                         <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>
                         <GSTRATE>""" + str(ig_tax_pert) + """</GSTRATE>
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
                      </GSTDETAILS.LIST>"""

            LedgerType = self.env['test.connection']._check_and_opt(LedgerType)
            address=''
            state = ''
            pincode = ''
            reg_type= 'Unregistered'
            gstin=''
            billwise ='No'
            affect_stock='Yes'
            if line.partner_id:
                billwise ='Yes'
                affect_stock ='No'
                if line.partner_id.street:
                    address = address+str(line.partner_id.street)
                if line.partner_id.street2:
                    address = address + str(line.partner_id.street2)
                if line.partner_id.city:
                    address = address + str(line.partner_id.city)
                if line.partner_id.state_id:
                    state = str(line.partner_id.state_id.name)
                if line.partner_id.zip:
                    pincode = str(line.partner_id.zip)
                if line.partner_id.vat:
                    reg_type='Regular'
                    gstin = line.partner_id.vat
            address = self.env['test.connection']._check_and_opt(address)
            state = self.env['test.connection']._check_and_opt(state)

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
                <LEDGER NAME="" RESERVEDNAME="">
                <ADDRESS.LIST TYPE="String">
                <ADDRESS>"""+address+"""</ADDRESS>
                </ADDRESS.LIST>
                <MAILINGNAME.LIST TYPE="String">
                <MAILINGNAME>""" + PartyName + """</MAILINGNAME>
                </MAILINGNAME.LIST>
                <OLDAUDITENTRYIDS.LIST TYPE="Number">
                <OLDAUDITENTRYIDS>-1</OLDAUDITENTRYIDS>
                </OLDAUDITENTRYIDS.LIST>
                <STARTINGFROM/>
                <STREGDATE/>
                <LBTREGNDATE/>
                <SAMPLINGDATEONEFACTOR/>
                <SAMPLINGDATETWOFACTOR/>
                <ACTIVEFROM/>
                <ACTIVETO/>
                <CREATEDDATE/>
                <ALTEREDON/>
                <VATAPPLICABLEDATE/>
                <EXCISEREGISTRATIONDATE/>
                <PANAPPLICABLEFROM/>
                <PAYINSRUNNINGFILEDATE/>
                <VATTAXEXEMPTIONDATE/>
                <GUID></GUID>
                <CURRENCYNAME>&#8377;</CURRENCYNAME>
                <EMAIL/>
                <STATENAME>"""+ state +"""</STATENAME>
                <PINCODE>"""+pincode+"""</PINCODE>
                <WEBSITE/>
                <INCOMETAXNUMBER/>
                <SALESTAXNUMBER/>
                <INTERSTATESTNUMBER/>
                <VATTINNUMBER/>
                <COUNTRYNAME>India</COUNTRYNAME>
                <EXCISERANGE/>
                <EXCISEDIVISION/>
                <EXCISECOMMISSIONERATE/>
                <LBTREGNNO/>
                <LBTZONE/>
                <EXPORTIMPORTCODE/>
                <GSTREGISTRATIONTYPE>"""+reg_type+"""</GSTREGISTRATIONTYPE>
                <VATDEALERTYPE>Regular</VATDEALERTYPE>
                <PRICELEVEL/>
                <UPLOADLASTREFRESH/>
                <PARENT>""" + LedgerType + """</PARENT>
                <SAMPLINGMETHOD/>
                <SAMPLINGSTRONEFACTOR/>
                <IFSCODE/>
                <NARRATION/>
                <REQUESTORRULE/>
                <GRPDEBITPARENT/>
                <GRPCREDITPARENT/>
                <SYSDEBITPARENT/>
                <SYSCREDITPARENT/>
                <TDSAPPLICABLE/>
                <TCSAPPLICABLE/>
                """+gst_app+"""
                <CREATEDBY/>
                <ALTEREDBY/>
                <TAXCLASSIFICATIONNAME/>
                <TAXTYPE>"""+tax_type+"""</TAXTYPE>
                <BILLCREDITPERIOD/>
                <BANKDETAILS/>
                <BANKBRANCHNAME/>
                <BANKBSRCODE/>
                <DEDUCTEETYPE/>
                <BUSINESSTYPE/>
                <TYPEOFNOTIFICATION/>
                <MSMEREGNUMBER/>
                <COUNTRYOFRESIDENCE>India</COUNTRYOFRESIDENCE>
                <RELATEDPARTYID/>
                <RELPARTYISSUINGAUTHORITY/>
                <IMPORTEREXPORTERCODE/>
                <EMAILCC/>
                <DESCRIPTION/>
                <LEDADDLALLOCTYPE/>
                <TRANSPORTERID/>
                <LEDGERPHONE/>
                <LEDGERFAX/>
                <LEDGERCONTACT/>
                <LEDGERMOBILE/>
                <RELATIONTYPE/>
                <MAILINGNAMENATIVE/>
                <STATENAMENATIVE/>
                <COUNTRYNAMENATIVE/>
                <BASICTYPEOFDUTY/>
                <GSTTYPE/>
                <EXEMPTIONTYPE/>
                <APPROPRIATEFOR/>
                <SUBTAXTYPE/>
                <STXNATUREOFPARTY/>
                <NAMEONPAN/>
                <USEDFORTAXTYPE/>
                <ECOMMMERCHANTID/>
                <PARTYGSTIN>"""+gstin+"""</PARTYGSTIN>
                <GSTDUTYHEAD>"""+gst_duty+"""</GSTDUTYHEAD>
                <GSTAPPROPRIATETO/>
                <GSTTYPEOFSUPPLY>Goods</GSTTYPEOFSUPPLY>
                <GSTNATUREOFSUPPLY/>
                <CESSVALUATIONMETHOD/>
                <PAYTYPE/>
                <PAYSLIPNAME/>
                <ATTENDANCETYPE/>
                <LEAVETYPE/>
                <CALCULATIONPERIOD/>
                <ROUNDINGMETHOD/>
                <COMPUTATIONTYPE/>
                <CALCULATIONTYPE/>
                <PAYSTATTYPE/>
                <PROFESSIONALTAXNUMBER/>
                <USERDEFINEDCALENDERTYPE/>
                <ITNATURE/>
                <ITCOMPONENT/>
                <NOTIFICATIONNUMBER/>
                <REGISTRATIONNUMBER/>
                <SERVICECATEGORY></SERVICECATEGORY>
                <ABATEMENTNOTIFICATIONNO/>
                <STXDUTYHEAD/>
                <STXCLASSIFICATION/>
                <NOTIFICATIONSLNO/>
                <SERVICETAXAPPLICABLE/>
                <EXCISELEDGERCLASSIFICATION/>
                <EXCISEREGISTRATIONNUMBER/>
                <EXCISEACCOUNTHEAD/>
                <EXCISEDUTYTYPE/>
                <EXCISEDUTYHEADCODE/>
                <EXCISEALLOCTYPE/>
                <EXCISEDUTYHEAD/>
                <NATUREOFSALES/>
                <EXCISENOTIFICATIONNO/>
                <EXCISEIMPORTSREGISTARTIONNO/>
                <EXCISEAPPLICABILITY/>
                <EXCISETYPEOFBRANCH/>
                <EXCISEDEFAULTREMOVAL/>
                <EXCISENOTIFICATIONSLNO/>
                <TYPEOFTARIFF/>
                <EXCISEREGNO/>
                <EXCISENATUREOFPURCHASE/>
                <TDSDEDUCTEETYPEMST/>
                <TDSRATENAME/>
                <TDSDEDUCTEESECTIONNUMBER/>
                <PANSTATUS/>
                <DEDUCTEEREFERENCE/>
                <TDSDEDUCTEETYPE/>
                <ITEXEMPTAPPLICABLE/>
                <TAXIDENTIFICATIONNO/>
                <LEDGERFBTCATEGORY/>
                <BRANCHCODE/>
                <CLIENTCODE/>
                <BANKINGCONFIGBANK/>
                <BANKINGCONFIGBANKID/>
                <BANKACCHOLDERNAME></BANKACCHOLDERNAME>
                <USEFORPOSTYPE/>
                <PAYMENTGATEWAY/>
                <TYPEOFINTERESTON/>
                <BANKCONFIGIFSC/>
                <BANKCONFIGMICR/>
                <BANKCONFIGSHORTCODE/>
                <PYMTINSTOUTPUTNAME/>
                <PRODUCTCODETYPE/>
                <SALARYPYMTPRODUCTCODE/>
                <OTHERPYMTPRODUCTCODE/>
                <PAYMENTINSTLOCATION/>
                <ENCRPTIONLOCATION/>
                <NEWIMFLOCATION/>
                <IMPORTEDIMFLOCATION/>
                <BANKNEWSTATEMENTS/>
                <BANKIMPORTEDSTATEMENTS/>
                <BANKMICR/>
                <CORPORATEUSERNOECS/>
                <CORPORATEUSERNOACH/>
                <CORPORATEUSERNAME/>
                <IMFNAME/>
                <PAYINSBATCHNAME/>
                <LASTUSEDBATCHNAME/>
                <PAYINSFILENUMPERIOD/>
                <ENCRYPTEDBY/>
                <ENCRYPTEDID/>
                <ISOCURRENCYCODE/>
                <BANKCAPSULEID/>
                <SALESTAXCESSAPPLICABLE/>
                <BANKIBAN/>
                <VATTAXEXEMPTIONNATURE/>
                <VATTAXEXEMPTIONNUMBER/>
                <LEDSTATENAME/>
                <VATAPPLICABLE/>
                <PARTYBUSINESSTYPE/>
                <PARTYBUSINESSSTYLE/>
                <ISBILLWISEON>"""+billwise+"""</ISBILLWISEON>
                <ISCOSTCENTRESON>No</ISCOSTCENTRESON>
                <ISINTERESTON>No</ISINTERESTON>
                <ALLOWINMOBILE>No</ALLOWINMOBILE>
                <ISCOSTTRACKINGON>No</ISCOSTTRACKINGON>
                <ISBENEFICIARYCODEON>No</ISBENEFICIARYCODEON>
                <ISUPDATINGTARGETID>No</ISUPDATINGTARGETID>
                <ASORIGINAL>Yes</ASORIGINAL>
                <ISCONDENSED>No</ISCONDENSED>
                <AFFECTSSTOCK>"""+affect_stock+"""</AFFECTSSTOCK>
                <ISRATEINCLUSIVEVAT>No</ISRATEINCLUSIVEVAT>
                <FORPAYROLL>No</FORPAYROLL>
                <ISABCENABLED>No</ISABCENABLED>
                <ISCREDITDAYSCHKON>No</ISCREDITDAYSCHKON>
                <INTERESTONBILLWISE>No</INTERESTONBILLWISE>
                <OVERRIDEINTEREST>No</OVERRIDEINTEREST>
                <OVERRIDEADVINTEREST>No</OVERRIDEADVINTEREST>
                <USEFORVAT>No</USEFORVAT>
                <IGNORETDSEXEMPT>No</IGNORETDSEXEMPT>
                <ISTCSAPPLICABLE>No</ISTCSAPPLICABLE>
                <ISTDSAPPLICABLE>No</ISTDSAPPLICABLE>
                <ISFBTAPPLICABLE>No</ISFBTAPPLICABLE>
                <ISGSTAPPLICABLE>No</ISGSTAPPLICABLE>
                <ISEXCISEAPPLICABLE>No</ISEXCISEAPPLICABLE>
                <ISTDSEXPENSE>No</ISTDSEXPENSE>
                <ISEDLIAPPLICABLE>No</ISEDLIAPPLICABLE>
                <ISRELATEDPARTY>No</ISRELATEDPARTY>
                <USEFORESIELIGIBILITY>No</USEFORESIELIGIBILITY>
                <ISINTERESTINCLLASTDAY>No</ISINTERESTINCLLASTDAY>
                <APPROPRIATETAXVALUE>No</APPROPRIATETAXVALUE>
                <ISBEHAVEASDUTY>No</ISBEHAVEASDUTY>
                <INTERESTINCLDAYOFADDITION>No</INTERESTINCLDAYOFADDITION>
                <INTERESTINCLDAYOFDEDUCTION>No</INTERESTINCLDAYOFDEDUCTION>
                <ISOTHTERRITORYASSESSEE>No</ISOTHTERRITORYASSESSEE>
                <OVERRIDECREDITLIMIT>No</OVERRIDECREDITLIMIT>
                <ISAGAINSTFORMC>No</ISAGAINSTFORMC>
                <ISCHEQUEPRINTINGENABLED>Yes</ISCHEQUEPRINTINGENABLED>
                <ISPAYUPLOAD>No</ISPAYUPLOAD>
                <ISPAYBATCHONLYSAL>No</ISPAYBATCHONLYSAL>
                <ISBNFCODESUPPORTED>No</ISBNFCODESUPPORTED>
                <ALLOWEXPORTWITHERRORS>No</ALLOWEXPORTWITHERRORS>
                <CONSIDERPURCHASEFOREXPORT>No</CONSIDERPURCHASEFOREXPORT>
                <ISTRANSPORTER>No</ISTRANSPORTER>
                <USEFORNOTIONALITC>No</USEFORNOTIONALITC>
                <ISECOMMOPERATOR>No</ISECOMMOPERATOR>
                <SHOWINPAYSLIP>No</SHOWINPAYSLIP>
                <USEFORGRATUITY>No</USEFORGRATUITY>
                <ISTDSPROJECTED>No</ISTDSPROJECTED>
                <FORSERVICETAX>No</FORSERVICETAX>
                <ISINPUTCREDIT>No</ISINPUTCREDIT>
                <ISEXEMPTED>No</ISEXEMPTED>
                <ISABATEMENTAPPLICABLE>No</ISABATEMENTAPPLICABLE>
                <ISSTXPARTY>No</ISSTXPARTY>
                <ISSTXNONREALIZEDTYPE>No</ISSTXNONREALIZEDTYPE>
                <ISUSEDFORCVD>No</ISUSEDFORCVD>
                <LEDBELONGSTONONTAXABLE>No</LEDBELONGSTONONTAXABLE>
                <ISEXCISEMERCHANTEXPORTER>No</ISEXCISEMERCHANTEXPORTER>
                <ISPARTYEXEMPTED>No</ISPARTYEXEMPTED>
                <ISSEZPARTY>No</ISSEZPARTY>
                <TDSDEDUCTEEISSPECIALRATE>No</TDSDEDUCTEEISSPECIALRATE>
                <ISECHEQUESUPPORTED>No</ISECHEQUESUPPORTED>
                <ISEDDSUPPORTED>No</ISEDDSUPPORTED>
                <HASECHEQUEDELIVERYMODE>No</HASECHEQUEDELIVERYMODE>
                <HASECHEQUEDELIVERYTO>No</HASECHEQUEDELIVERYTO>
                <HASECHEQUEPRINTLOCATION>No</HASECHEQUEPRINTLOCATION>
                <HASECHEQUEPAYABLELOCATION>No</HASECHEQUEPAYABLELOCATION>
                <HASECHEQUEBANKLOCATION>No</HASECHEQUEBANKLOCATION>
                <HASEDDDELIVERYMODE>No</HASEDDDELIVERYMODE>
                <HASEDDDELIVERYTO>No</HASEDDDELIVERYTO>
                <HASEDDPRINTLOCATION>No</HASEDDPRINTLOCATION>
                <HASEDDPAYABLELOCATION>No</HASEDDPAYABLELOCATION>
                <HASEDDBANKLOCATION>No</HASEDDBANKLOCATION>
                <ISEBANKINGENABLED>No</ISEBANKINGENABLED>
                <ISEXPORTFILEENCRYPTED>No</ISEXPORTFILEENCRYPTED>
                <ISBATCHENABLED>No</ISBATCHENABLED>
                <ISPRODUCTCODEBASED>No</ISPRODUCTCODEBASED>
                <HASEDDCITY>No</HASEDDCITY>
                <HASECHEQUECITY>No</HASECHEQUECITY>
                <ISFILENAMEFORMATSUPPORTED>No</ISFILENAMEFORMATSUPPORTED>
                <HASCLIENTCODE>No</HASCLIENTCODE>
                <PAYINSISBATCHAPPLICABLE>No</PAYINSISBATCHAPPLICABLE>
                <PAYINSISFILENUMAPP>No</PAYINSISFILENUMAPP>
                <ISSALARYTRANSGROUPEDFORBRS>No</ISSALARYTRANSGROUPEDFORBRS>
                <ISEBANKINGSUPPORTED>No</ISEBANKINGSUPPORTED>
                <ISSCBUAE>No</ISSCBUAE>
                <ISBANKSTATUSAPP>No</ISBANKSTATUSAPP>
                <ISSALARYGROUPED>No</ISSALARYGROUPED>
                <USEFORPURCHASETAX>No</USEFORPURCHASETAX>
                <AUDITED>No</AUDITED>
                <SAMPLINGNUMONEFACTOR>0</SAMPLINGNUMONEFACTOR>
                <SAMPLINGNUMTWOFACTOR>0</SAMPLINGNUMTWOFACTOR>
                <SORTPOSITION> 1000</SORTPOSITION>
                <ALTERID></ALTERID>
                <DEFAULTLANGUAGE>0</DEFAULTLANGUAGE>
                <RATEOFTAXCALCULATION>"""+str(tax_perc)+"""</RATEOFTAXCALCULATION>
                <GRATUITYMONTHDAYS>0</GRATUITYMONTHDAYS>
                <GRATUITYLIMITMONTHS>0</GRATUITYLIMITMONTHS>
                <CALCULATIONBASIS>0</CALCULATIONBASIS>
                <ROUNDINGLIMIT>0</ROUNDINGLIMIT>
                <ABATEMENTPERCENTAGE>0</ABATEMENTPERCENTAGE>
                <TDSDEDUCTEESPECIALRATE>0</TDSDEDUCTEESPECIALRATE>
                <BENEFICIARYCODEMAXLENGTH>0</BENEFICIARYCODEMAXLENGTH>
                <ECHEQUEPRINTLOCATIONVERSION>0</ECHEQUEPRINTLOCATIONVERSION>
                <ECHEQUEPAYABLELOCATIONVERSION>0</ECHEQUEPAYABLELOCATIONVERSION>
                <EDDPRINTLOCATIONVERSION>0</EDDPRINTLOCATIONVERSION>
                <EDDPAYABLELOCATIONVERSION>0</EDDPAYABLELOCATIONVERSION>
                <PAYINSRUNNINGFILENUM>0</PAYINSRUNNINGFILENUM>
                <TRANSACTIONTYPEVERSION>0</TRANSACTIONTYPEVERSION>
                <PAYINSFILENUMLENGTH>0</PAYINSFILENUMLENGTH>
                <SAMPLINGAMTONEFACTOR/>
                <SAMPLINGAMTTWOFACTOR/>
                <OPENINGBALANCE/>
                <CREDITLIMIT/>
                <GRATUITYLIMITAMOUNT/>
                <ODLIMIT/>
                <TEMPGSTCGSTRATE>0</TEMPGSTCGSTRATE>
                <TEMPGSTSGSTRATE>0</TEMPGSTSGSTRATE>
                <TEMPGSTIGSTRATE>0</TEMPGSTIGSTRATE>
                <TEMPISVATFIELDSEDITED/>
                <TEMPAPPLDATE/>
                <TEMPCLASSIFICATION/>
                <TEMPNATURE/>
                <TEMPPARTYENTITY/>
                <TEMPBUSINESSNATURE/>
                <TEMPVATRATE>0</TEMPVATRATE>
                <TEMPADDLTAX>0</TEMPADDLTAX>
                <TEMPCESSONVAT>0</TEMPCESSONVAT>
                <TEMPTAXTYPE/>
                <TEMPMAJORCOMMODITYNAME/>
                <TEMPCOMMODITYNAME/>
                <TEMPCOMMODITYCODE/>
                <TEMPSUBCOMMODITYCODE/>
                <TEMPUOM/>
                <TEMPTYPEOFGOODS/>
                <TEMPTRADENAME/>
                <TEMPGOODSNATURE/>
                <TEMPSCHEDULE/>
                <TEMPSCHEDULESLNO/>
                <TEMPISINVDETAILSENABLE/>
                <TEMPLOCALVATRATE>0</TEMPLOCALVATRATE>
                <TEMPVALUATIONTYPE/>
                <TEMPISCALCONQTY/>
                <TEMPISSALETOLOCALCITIZEN/>
                <LEDISTDSAPPLICABLECURRLIAB/>
                <ISPRODUCTCODEEDITED/>
                <SERVICETAXDETAILS.LIST>      </SERVICETAXDETAILS.LIST>
                <LBTREGNDETAILS.LIST>      </LBTREGNDETAILS.LIST>
                <VATDETAILS.LIST>      </VATDETAILS.LIST>
                <SALESTAXCESSDETAILS.LIST>      </SALESTAXCESSDETAILS.LIST>
                """+gst+"""
                <LANGUAGENAME.LIST>
                <NAME.LIST TYPE="String">
                <NAME>""" + PartyName + """</NAME>
                </NAME.LIST>
                <LANGUAGEID> 1033</LANGUAGEID>
                </LANGUAGENAME.LIST>
                <XBRLDETAIL.LIST>      </XBRLDETAIL.LIST>
                <AUDITDETAILS.LIST>      </AUDITDETAILS.LIST>
                <SCHVIDETAILS.LIST>      </SCHVIDETAILS.LIST>
                <EXCISETARIFFDETAILS.LIST>      </EXCISETARIFFDETAILS.LIST>
                <TCSCATEGORYDETAILS.LIST>      </TCSCATEGORYDETAILS.LIST>
                <TDSCATEGORYDETAILS.LIST>      </TDSCATEGORYDETAILS.LIST>
                <SLABPERIOD.LIST>      </SLABPERIOD.LIST>
                <GRATUITYPERIOD.LIST>      </GRATUITYPERIOD.LIST>
                <ADDITIONALCOMPUTATIONS.LIST>      </ADDITIONALCOMPUTATIONS.LIST>
                <EXCISEJURISDICTIONDETAILS.LIST>      </EXCISEJURISDICTIONDETAILS.LIST>
                <EXCLUDEDTAXATIONS.LIST>      </EXCLUDEDTAXATIONS.LIST>
                <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
                <PAYMENTDETAILS.LIST>      </PAYMENTDETAILS.LIST>
                <BANKEXPORTFORMATS.LIST>      </BANKEXPORTFORMATS.LIST>
                <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
                <INTERESTCOLLECTION.LIST>      </INTERESTCOLLECTION.LIST>
                <LEDGERCLOSINGVALUES.LIST>      </LEDGERCLOSINGVALUES.LIST>
                <LEDGERAUDITCLASS.LIST>      </LEDGERAUDITCLASS.LIST>
                <OLDAUDITENTRIES.LIST>      </OLDAUDITENTRIES.LIST>
                <TDSEXEMPTIONRULES.LIST>      </TDSEXEMPTIONRULES.LIST>
                <DEDUCTINSAMEVCHRULES.LIST>      </DEDUCTINSAMEVCHRULES.LIST>
                <LOWERDEDUCTION.LIST>      </LOWERDEDUCTION.LIST>
                <STXABATEMENTDETAILS.LIST>      </STXABATEMENTDETAILS.LIST>
                <LEDMULTIADDRESSLIST.LIST>      </LEDMULTIADDRESSLIST.LIST>
                <STXTAXDETAILS.LIST>      </STXTAXDETAILS.LIST>
                <CHEQUERANGE.LIST>      </CHEQUERANGE.LIST>
                <DEFAULTVCHCHEQUEDETAILS.LIST>      </DEFAULTVCHCHEQUEDETAILS.LIST>
                <ACCOUNTAUDITENTRIES.LIST>      </ACCOUNTAUDITENTRIES.LIST>
                <AUDITENTRIES.LIST>      </AUDITENTRIES.LIST>
                <BRSIMPORTEDINFO.LIST>      </BRSIMPORTEDINFO.LIST>
                <AUTOBRSCONFIGS.LIST>      </AUTOBRSCONFIGS.LIST>
                <BANKURENTRIES.LIST>      </BANKURENTRIES.LIST>
                <DEFAULTCHEQUEDETAILS.LIST>      </DEFAULTCHEQUEDETAILS.LIST>
                <DEFAULTOPENINGCHEQUEDETAILS.LIST>      </DEFAULTOPENINGCHEQUEDETAILS.LIST>
                <CANCELLEDPAYALLOCATIONS.LIST>      </CANCELLEDPAYALLOCATIONS.LIST>
                <ECHEQUEPRINTLOCATION.LIST>      </ECHEQUEPRINTLOCATION.LIST>
                <ECHEQUEPAYABLELOCATION.LIST>      </ECHEQUEPAYABLELOCATION.LIST>
                <EDDPRINTLOCATION.LIST>      </EDDPRINTLOCATION.LIST>
                <EDDPAYABLELOCATION.LIST>      </EDDPAYABLELOCATION.LIST>
                <AVAILABLETRANSACTIONTYPES.LIST>      </AVAILABLETRANSACTIONTYPES.LIST>
                <LEDPAYINSCONFIGS.LIST>      </LEDPAYINSCONFIGS.LIST>
                <TYPECODEDETAILS.LIST>      </TYPECODEDETAILS.LIST>
                <FIELDVALIDATIONDETAILS.LIST>      </FIELDVALIDATIONDETAILS.LIST>
                <INPUTCRALLOCS.LIST>      </INPUTCRALLOCS.LIST>
                <GSTCLASSFNIGSTRATES.LIST>      </GSTCLASSFNIGSTRATES.LIST>
                <EXTARIFFDUTYHEADDETAILS.LIST>      </EXTARIFFDUTYHEADDETAILS.LIST>
                <VOUCHERTYPEPRODUCTCODES.LIST>      </VOUCHERTYPEPRODUCTCODES.LIST>
                </LEDGER>
                </TALLYMESSAGE>
                </REQUESTDATA>
                </IMPORTDATA>
                </BODY>
                </ENVELOPE>
             """

            # res = requests.post(url, data=params, headers={'Content-Type': 'application/xml'})
            if create_xml:
                f = open("masters.xml", "a+")
                f.write(params)
                f.close()
                created_in_tally = True
                line.write({'created_in_tally': created_in_tally})
            else:
                headers = {'Content-Type': 'application/xml'}
                #print("paramsparamsparamsparamsparams", params)
                res = requests.post(url, data=params.encode('utf-8'), headers=headers)
                root = ET.fromstring(res.content)
                # res = requests.post(url, data=params, headers={'Content-Type': 'application/xml'})
                print("response for ledgerssssssssss", res)
                created_in_tally = False
                altered_in_tally = False
                if len(root) > 9:
                    if root[0].tag == 'LINEERROR':
                        altered_in_tally = False
                        sync_dict = {}
                        sync_dict = {
                            'object': 'account.account',
                            'name': 'Account ledgers',
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

        #Jatin commented because we are not using hr for now
        # import Employee too in Tally Ledgers
        # employee_ids = self.env['hr.employee'].search([('company_id', '=', company.id),('active','=',True),('created_in_tally','=',False)], order='id')
        # print("lem of employee_ids for ledgers lengthhhhhhhhh", len(employee_ids))
        # for line1 in employee_ids:
        #     print("PartyName====", line1.name)
        #     if line1.emp_code:
        #         PartyName = line1.name + '(' + line1.emp_code + ')'
        #     else:
        #         PartyName = line1.name
        #     Address = str(line1.street) + str(line1.street2)
        #     print("Address====", Address)
        #     tally_company = tally_company
        #     LedgerType = 'Sundry Creditors'
        #
        #     params = """
        #                 <?xml version='1.0' encoding='utf-8'?>
        #                 <ENVELOPE>
        #                 <HEADER>
        #                 <TALLYREQUEST>Import Data</TALLYREQUEST>
        #                 </HEADER>
        #                 <BODY>
        #                 <IMPORTDATA>
        #                 <REQUESTDESC>
        #                 <REPORTNAME>All Masters</REPORTNAME>
        #                 <STATICVARIABLES>
        #                 <SVCURRENTCOMPANY>""" + tally_company + """</SVCURRENTCOMPANY>
        #                 </STATICVARIABLES>
        #                 </REQUESTDESC>
        #                 <REQUESTDATA>
        #                 <TALLYMESSAGE xmlns:UDF="TallyUDF">
        #                 <LEDGER NAME="" RESERVEDNAME="">
        #                 <ADDRESS.LIST TYPE="String">
        #                 <ADDRESS>""" + str(Address) + """</ADDRESS>
        #                 </ADDRESS.LIST>
        #                 <MAILINGNAME.LIST TYPE="String">
        #                 <MAILINGNAME>""" + PartyName + """</MAILINGNAME>
        #                 </MAILINGNAME.LIST>
        #                 <OLDAUDITENTRYIDS.LIST TYPE="Number">
        #                 <OLDAUDITENTRYIDS>-1</OLDAUDITENTRYIDS>
        #                 </OLDAUDITENTRYIDS.LIST>
        #                 <STARTINGFROM/>
        #                 <STREGDATE/>
        #                 <LBTREGNDATE/>
        #                 <SAMPLINGDATEONEFACTOR/>
        #                 <SAMPLINGDATETWOFACTOR/>
        #                 <ACTIVEFROM/>
        #                 <ACTIVETO/>
        #                 <CREATEDDATE/>
        #                 <ALTEREDON/>
        #                 <VATAPPLICABLEDATE/>
        #                 <EXCISEREGISTRATIONDATE/>
        #                 <PANAPPLICABLEFROM/>
        #                 <PAYINSRUNNINGFILEDATE/>
        #                 <VATTAXEXEMPTIONDATE/>
        #                 <GUID></GUID>
        #                 <CURRENCYNAME>&#8377;</CURRENCYNAME>
        #                 <EMAIL/>
        #                 <STATENAME/>
        #                 <PINCODE/>
        #                 <WEBSITE/>
        #                 <INCOMETAXNUMBER/>
        #                 <SALESTAXNUMBER/>
        #                 <INTERSTATESTNUMBER/>
        #                 <VATTINNUMBER/>
        #                 <COUNTRYNAME>India</COUNTRYNAME>
        #                 <EXCISERANGE/>
        #                 <EXCISEDIVISION/>
        #                 <EXCISECOMMISSIONERATE/>
        #                 <LBTREGNNO/>
        #                 <LBTZONE/>
        #                 <EXPORTIMPORTCODE/>
        #                 <GSTREGISTRATIONTYPE>Regular</GSTREGISTRATIONTYPE>
        #                 <VATDEALERTYPE>Regular</VATDEALERTYPE>
        #                 <PRICELEVEL/>
        #                 <UPLOADLASTREFRESH/>
        #                 <PARENT>""" + LedgerType + """</PARENT>
        #                 <SAMPLINGMETHOD/>
        #                 <SAMPLINGSTRONEFACTOR/>
        #                 <IFSCODE/>
        #                 <NARRATION/>
        #                 <REQUESTORRULE/>
        #                 <GRPDEBITPARENT/>
        #                 <GRPCREDITPARENT/>
        #                 <SYSDEBITPARENT/>
        #                 <SYSCREDITPARENT/>
        #                 <TDSAPPLICABLE/>
        #                 <TCSAPPLICABLE/>
        #                 <GSTAPPLICABLE/>
        #                 <CREATEDBY/>
        #                 <ALTEREDBY/>
        #                 <TAXCLASSIFICATIONNAME/>
        #                 <TAXTYPE>Others</TAXTYPE>
        #                 <BILLCREDITPERIOD/>
        #                 <BANKDETAILS/>
        #                 <BANKBRANCHNAME/>
        #                 <BANKBSRCODE/>
        #                 <DEDUCTEETYPE/>
        #                 <BUSINESSTYPE/>
        #                 <TYPEOFNOTIFICATION/>
        #                 <MSMEREGNUMBER/>
        #                 <COUNTRYOFRESIDENCE>India</COUNTRYOFRESIDENCE>
        #                 <RELATEDPARTYID/>
        #                 <RELPARTYISSUINGAUTHORITY/>
        #                 <IMPORTEREXPORTERCODE/>
        #                 <EMAILCC/>
        #                 <DESCRIPTION/>
        #                 <LEDADDLALLOCTYPE/>
        #                 <TRANSPORTERID/>
        #                 <LEDGERPHONE/>
        #                 <LEDGERFAX/>
        #                 <LEDGERCONTACT/>
        #                 <LEDGERMOBILE/>
        #                 <RELATIONTYPE/>
        #                 <MAILINGNAMENATIVE/>
        #                 <STATENAMENATIVE/>
        #                 <COUNTRYNAMENATIVE/>
        #                 <BASICTYPEOFDUTY/>
        #                 <GSTTYPE/>
        #                 <EXEMPTIONTYPE/>
        #                 <APPROPRIATEFOR/>
        #                 <SUBTAXTYPE/>
        #                 <STXNATUREOFPARTY/>
        #                 <NAMEONPAN/>
        #                 <USEDFORTAXTYPE/>
        #                 <ECOMMMERCHANTID/>
        #                 <PARTYGSTIN/>
        #                 <GSTDUTYHEAD/>
        #                 <GSTAPPROPRIATETO/>
        #                 <GSTTYPEOFSUPPLY/>
        #                 <GSTNATUREOFSUPPLY/>
        #                 <CESSVALUATIONMETHOD/>
        #                 <PAYTYPE/>
        #                 <PAYSLIPNAME/>
        #                 <ATTENDANCETYPE/>
        #                 <LEAVETYPE/>
        #                 <CALCULATIONPERIOD/>
        #                 <ROUNDINGMETHOD/>
        #                 <COMPUTATIONTYPE/>
        #                 <CALCULATIONTYPE/>
        #                 <PAYSTATTYPE/>
        #                 <PROFESSIONALTAXNUMBER/>
        #                 <USERDEFINEDCALENDERTYPE/>
        #                 <ITNATURE/>
        #                 <ITCOMPONENT/>
        #                 <NOTIFICATIONNUMBER/>
        #                 <REGISTRATIONNUMBER/>
        #                 <SERVICECATEGORY></SERVICECATEGORY>
        #                 <ABATEMENTNOTIFICATIONNO/>
        #                 <STXDUTYHEAD/>
        #                 <STXCLASSIFICATION/>
        #                 <NOTIFICATIONSLNO/>
        #                 <SERVICETAXAPPLICABLE/>
        #                 <EXCISELEDGERCLASSIFICATION/>
        #                 <EXCISEREGISTRATIONNUMBER/>
        #                 <EXCISEACCOUNTHEAD/>
        #                 <EXCISEDUTYTYPE/>
        #                 <EXCISEDUTYHEADCODE/>
        #                 <EXCISEALLOCTYPE/>
        #                 <EXCISEDUTYHEAD/>
        #                 <NATUREOFSALES/>
        #                 <EXCISENOTIFICATIONNO/>
        #                 <EXCISEIMPORTSREGISTARTIONNO/>
        #                 <EXCISEAPPLICABILITY/>
        #                 <EXCISETYPEOFBRANCH/>
        #                 <EXCISEDEFAULTREMOVAL/>
        #                 <EXCISENOTIFICATIONSLNO/>
        #                 <TYPEOFTARIFF/>
        #                 <EXCISEREGNO/>
        #                 <EXCISENATUREOFPURCHASE/>
        #                 <TDSDEDUCTEETYPEMST/>
        #                 <TDSRATENAME/>
        #                 <TDSDEDUCTEESECTIONNUMBER/>
        #                 <PANSTATUS/>
        #                 <DEDUCTEEREFERENCE/>
        #                 <TDSDEDUCTEETYPE/>
        #                 <ITEXEMPTAPPLICABLE/>
        #                 <TAXIDENTIFICATIONNO/>
        #                 <LEDGERFBTCATEGORY/>
        #                 <BRANCHCODE/>
        #                 <CLIENTCODE/>
        #                 <BANKINGCONFIGBANK/>
        #                 <BANKINGCONFIGBANKID/>
        #                 <BANKACCHOLDERNAME>Arkefilters</BANKACCHOLDERNAME>
        #                 <USEFORPOSTYPE/>
        #                 <PAYMENTGATEWAY/>
        #                 <TYPEOFINTERESTON/>
        #                 <BANKCONFIGIFSC/>
        #                 <BANKCONFIGMICR/>
        #                 <BANKCONFIGSHORTCODE/>
        #                 <PYMTINSTOUTPUTNAME/>
        #                 <PRODUCTCODETYPE/>
        #                 <SALARYPYMTPRODUCTCODE/>
        #                 <OTHERPYMTPRODUCTCODE/>
        #                 <PAYMENTINSTLOCATION/>
        #                 <ENCRPTIONLOCATION/>
        #                 <NEWIMFLOCATION/>
        #                 <IMPORTEDIMFLOCATION/>
        #                 <BANKNEWSTATEMENTS/>
        #                 <BANKIMPORTEDSTATEMENTS/>
        #                 <BANKMICR/>
        #                 <CORPORATEUSERNOECS/>
        #                 <CORPORATEUSERNOACH/>
        #                 <CORPORATEUSERNAME/>
        #                 <IMFNAME/>
        #                 <PAYINSBATCHNAME/>
        #                 <LASTUSEDBATCHNAME/>
        #                 <PAYINSFILENUMPERIOD/>
        #                 <ENCRYPTEDBY/>
        #                 <ENCRYPTEDID/>
        #                 <ISOCURRENCYCODE/>
        #                 <BANKCAPSULEID/>
        #                 <SALESTAXCESSAPPLICABLE/>
        #                 <BANKIBAN/>
        #                 <VATTAXEXEMPTIONNATURE/>
        #                 <VATTAXEXEMPTIONNUMBER/>
        #                 <LEDSTATENAME/>
        #                 <VATAPPLICABLE/>
        #                 <PARTYBUSINESSTYPE/>
        #                 <PARTYBUSINESSSTYLE/>
        #                 <ISBILLWISEON>Yes</ISBILLWISEON>
        #                 <ISCOSTCENTRESON>No</ISCOSTCENTRESON>
        #                 <ISINTERESTON>No</ISINTERESTON>
        #                 <ALLOWINMOBILE>No</ALLOWINMOBILE>
        #                 <ISCOSTTRACKINGON>No</ISCOSTTRACKINGON>
        #                 <ISBENEFICIARYCODEON>No</ISBENEFICIARYCODEON>
        #                 <ISUPDATINGTARGETID>No</ISUPDATINGTARGETID>
        #                 <ASORIGINAL>Yes</ASORIGINAL>
        #                 <ISCONDENSED>No</ISCONDENSED>
        #                 <AFFECTSSTOCK>No</AFFECTSSTOCK>
        #                 <ISRATEINCLUSIVEVAT>No</ISRATEINCLUSIVEVAT>
        #                 <FORPAYROLL>No</FORPAYROLL>
        #                 <ISABCENABLED>No</ISABCENABLED>
        #                 <ISCREDITDAYSCHKON>No</ISCREDITDAYSCHKON>
        #                 <INTERESTONBILLWISE>No</INTERESTONBILLWISE>
        #                 <OVERRIDEINTEREST>No</OVERRIDEINTEREST>
        #                 <OVERRIDEADVINTEREST>No</OVERRIDEADVINTEREST>
        #                 <USEFORVAT>No</USEFORVAT>
        #                 <IGNORETDSEXEMPT>No</IGNORETDSEXEMPT>
        #                 <ISTCSAPPLICABLE>No</ISTCSAPPLICABLE>
        #                 <ISTDSAPPLICABLE>No</ISTDSAPPLICABLE>
        #                 <ISFBTAPPLICABLE>No</ISFBTAPPLICABLE>
        #                 <ISGSTAPPLICABLE>No</ISGSTAPPLICABLE>
        #                 <ISEXCISEAPPLICABLE>No</ISEXCISEAPPLICABLE>
        #                 <ISTDSEXPENSE>No</ISTDSEXPENSE>
        #                 <ISEDLIAPPLICABLE>No</ISEDLIAPPLICABLE>
        #                 <ISRELATEDPARTY>No</ISRELATEDPARTY>
        #                 <USEFORESIELIGIBILITY>No</USEFORESIELIGIBILITY>
        #                 <ISINTERESTINCLLASTDAY>No</ISINTERESTINCLLASTDAY>
        #                 <APPROPRIATETAXVALUE>No</APPROPRIATETAXVALUE>
        #                 <ISBEHAVEASDUTY>No</ISBEHAVEASDUTY>
        #                 <INTERESTINCLDAYOFADDITION>No</INTERESTINCLDAYOFADDITION>
        #                 <INTERESTINCLDAYOFDEDUCTION>No</INTERESTINCLDAYOFDEDUCTION>
        #                 <ISOTHTERRITORYASSESSEE>No</ISOTHTERRITORYASSESSEE>
        #                 <OVERRIDECREDITLIMIT>No</OVERRIDECREDITLIMIT>
        #                 <ISAGAINSTFORMC>No</ISAGAINSTFORMC>
        #                 <ISCHEQUEPRINTINGENABLED>Yes</ISCHEQUEPRINTINGENABLED>
        #                 <ISPAYUPLOAD>No</ISPAYUPLOAD>
        #                 <ISPAYBATCHONLYSAL>No</ISPAYBATCHONLYSAL>
        #                 <ISBNFCODESUPPORTED>No</ISBNFCODESUPPORTED>
        #                 <ALLOWEXPORTWITHERRORS>No</ALLOWEXPORTWITHERRORS>
        #                 <CONSIDERPURCHASEFOREXPORT>No</CONSIDERPURCHASEFOREXPORT>
        #                 <ISTRANSPORTER>No</ISTRANSPORTER>
        #                 <USEFORNOTIONALITC>No</USEFORNOTIONALITC>
        #                 <ISECOMMOPERATOR>No</ISECOMMOPERATOR>
        #                 <SHOWINPAYSLIP>No</SHOWINPAYSLIP>
        #                 <USEFORGRATUITY>No</USEFORGRATUITY>
        #                 <ISTDSPROJECTED>No</ISTDSPROJECTED>
        #                 <FORSERVICETAX>No</FORSERVICETAX>
        #                 <ISINPUTCREDIT>No</ISINPUTCREDIT>
        #                 <ISEXEMPTED>No</ISEXEMPTED>
        #                 <ISABATEMENTAPPLICABLE>No</ISABATEMENTAPPLICABLE>
        #                 <ISSTXPARTY>No</ISSTXPARTY>
        #                 <ISSTXNONREALIZEDTYPE>No</ISSTXNONREALIZEDTYPE>
        #                 <ISUSEDFORCVD>No</ISUSEDFORCVD>
        #                 <LEDBELONGSTONONTAXABLE>No</LEDBELONGSTONONTAXABLE>
        #                 <ISEXCISEMERCHANTEXPORTER>No</ISEXCISEMERCHANTEXPORTER>
        #                 <ISPARTYEXEMPTED>No</ISPARTYEXEMPTED>
        #                 <ISSEZPARTY>No</ISSEZPARTY>
        #                 <TDSDEDUCTEEISSPECIALRATE>No</TDSDEDUCTEEISSPECIALRATE>
        #                 <ISECHEQUESUPPORTED>No</ISECHEQUESUPPORTED>
        #                 <ISEDDSUPPORTED>No</ISEDDSUPPORTED>
        #                 <HASECHEQUEDELIVERYMODE>No</HASECHEQUEDELIVERYMODE>
        #                 <HASECHEQUEDELIVERYTO>No</HASECHEQUEDELIVERYTO>
        #                 <HASECHEQUEPRINTLOCATION>No</HASECHEQUEPRINTLOCATION>
        #                 <HASECHEQUEPAYABLELOCATION>No</HASECHEQUEPAYABLELOCATION>
        #                 <HASECHEQUEBANKLOCATION>No</HASECHEQUEBANKLOCATION>
        #                 <HASEDDDELIVERYMODE>No</HASEDDDELIVERYMODE>
        #                 <HASEDDDELIVERYTO>No</HASEDDDELIVERYTO>
        #                 <HASEDDPRINTLOCATION>No</HASEDDPRINTLOCATION>
        #                 <HASEDDPAYABLELOCATION>No</HASEDDPAYABLELOCATION>
        #                 <HASEDDBANKLOCATION>No</HASEDDBANKLOCATION>
        #                 <ISEBANKINGENABLED>No</ISEBANKINGENABLED>
        #                 <ISEXPORTFILEENCRYPTED>No</ISEXPORTFILEENCRYPTED>
        #                 <ISBATCHENABLED>No</ISBATCHENABLED>
        #                 <ISPRODUCTCODEBASED>No</ISPRODUCTCODEBASED>
        #                 <HASEDDCITY>No</HASEDDCITY>
        #                 <HASECHEQUECITY>No</HASECHEQUECITY>
        #                 <ISFILENAMEFORMATSUPPORTED>No</ISFILENAMEFORMATSUPPORTED>
        #                 <HASCLIENTCODE>No</HASCLIENTCODE>
        #                 <PAYINSISBATCHAPPLICABLE>No</PAYINSISBATCHAPPLICABLE>
        #                 <PAYINSISFILENUMAPP>No</PAYINSISFILENUMAPP>
        #                 <ISSALARYTRANSGROUPEDFORBRS>No</ISSALARYTRANSGROUPEDFORBRS>
        #                 <ISEBANKINGSUPPORTED>No</ISEBANKINGSUPPORTED>
        #                 <ISSCBUAE>No</ISSCBUAE>
        #                 <ISBANKSTATUSAPP>No</ISBANKSTATUSAPP>
        #                 <ISSALARYGROUPED>No</ISSALARYGROUPED>
        #                 <USEFORPURCHASETAX>No</USEFORPURCHASETAX>
        #                 <AUDITED>No</AUDITED>
        #                 <SAMPLINGNUMONEFACTOR>0</SAMPLINGNUMONEFACTOR>
        #                 <SAMPLINGNUMTWOFACTOR>0</SAMPLINGNUMTWOFACTOR>
        #                 <SORTPOSITION> 1000</SORTPOSITION>
        #                 <ALTERID> 178</ALTERID>
        #                 <DEFAULTLANGUAGE>0</DEFAULTLANGUAGE>
        #                 <RATEOFTAXCALCULATION>0</RATEOFTAXCALCULATION>
        #                 <GRATUITYMONTHDAYS>0</GRATUITYMONTHDAYS>
        #                 <GRATUITYLIMITMONTHS>0</GRATUITYLIMITMONTHS>
        #                 <CALCULATIONBASIS>0</CALCULATIONBASIS>
        #                 <ROUNDINGLIMIT>0</ROUNDINGLIMIT>
        #                 <ABATEMENTPERCENTAGE>0</ABATEMENTPERCENTAGE>
        #                 <TDSDEDUCTEESPECIALRATE>0</TDSDEDUCTEESPECIALRATE>
        #                 <BENEFICIARYCODEMAXLENGTH>0</BENEFICIARYCODEMAXLENGTH>
        #                 <ECHEQUEPRINTLOCATIONVERSION>0</ECHEQUEPRINTLOCATIONVERSION>
        #                 <ECHEQUEPAYABLELOCATIONVERSION>0</ECHEQUEPAYABLELOCATIONVERSION>
        #                 <EDDPRINTLOCATIONVERSION>0</EDDPRINTLOCATIONVERSION>
        #                 <EDDPAYABLELOCATIONVERSION>0</EDDPAYABLELOCATIONVERSION>
        #                 <PAYINSRUNNINGFILENUM>0</PAYINSRUNNINGFILENUM>
        #                 <TRANSACTIONTYPEVERSION>0</TRANSACTIONTYPEVERSION>
        #                 <PAYINSFILENUMLENGTH>0</PAYINSFILENUMLENGTH>
        #                 <SAMPLINGAMTONEFACTOR/>
        #                 <SAMPLINGAMTTWOFACTOR/>
        #                 <OPENINGBALANCE/>
        #                 <CREDITLIMIT/>
        #                 <GRATUITYLIMITAMOUNT/>
        #                 <ODLIMIT/>
        #                 <TEMPGSTCGSTRATE>0</TEMPGSTCGSTRATE>
        #                 <TEMPGSTSGSTRATE>0</TEMPGSTSGSTRATE>
        #                 <TEMPGSTIGSTRATE>0</TEMPGSTIGSTRATE>
        #                 <TEMPISVATFIELDSEDITED/>
        #                 <TEMPAPPLDATE/>
        #                 <TEMPCLASSIFICATION/>
        #                 <TEMPNATURE/>
        #                 <TEMPPARTYENTITY/>
        #                 <TEMPBUSINESSNATURE/>
        #                 <TEMPVATRATE>0</TEMPVATRATE>
        #                 <TEMPADDLTAX>0</TEMPADDLTAX>
        #                 <TEMPCESSONVAT>0</TEMPCESSONVAT>
        #                 <TEMPTAXTYPE/>
        #                 <TEMPMAJORCOMMODITYNAME/>
        #                 <TEMPCOMMODITYNAME/>
        #                 <TEMPCOMMODITYCODE/>
        #                 <TEMPSUBCOMMODITYCODE/>
        #                 <TEMPUOM/>
        #                 <TEMPTYPEOFGOODS/>
        #                 <TEMPTRADENAME/>
        #                 <TEMPGOODSNATURE/>
        #                 <TEMPSCHEDULE/>
        #                 <TEMPSCHEDULESLNO/>
        #                 <TEMPISINVDETAILSENABLE/>
        #                 <TEMPLOCALVATRATE>0</TEMPLOCALVATRATE>
        #                 <TEMPVALUATIONTYPE/>
        #                 <TEMPISCALCONQTY/>
        #                 <TEMPISSALETOLOCALCITIZEN/>
        #                 <LEDISTDSAPPLICABLECURRLIAB/>
        #                 <ISPRODUCTCODEEDITED/>
        #                 <SERVICETAXDETAILS.LIST>      </SERVICETAXDETAILS.LIST>
        #                 <LBTREGNDETAILS.LIST>      </LBTREGNDETAILS.LIST>
        #                 <VATDETAILS.LIST>      </VATDETAILS.LIST>
        #                 <SALESTAXCESSDETAILS.LIST>      </SALESTAXCESSDETAILS.LIST>
        #                 <GSTDETAILS.LIST>      </GSTDETAILS.LIST>
        #                 <LANGUAGENAME.LIST>
        #                 <NAME.LIST TYPE="String">
        #                 <NAME>""" + PartyName + """</NAME>
        #                 </NAME.LIST>
        #                 <LANGUAGEID> 1033</LANGUAGEID>
        #                 </LANGUAGENAME.LIST>
        #                 <XBRLDETAIL.LIST>      </XBRLDETAIL.LIST>
        #                 <AUDITDETAILS.LIST>      </AUDITDETAILS.LIST>
        #                 <SCHVIDETAILS.LIST>      </SCHVIDETAILS.LIST>
        #                 <EXCISETARIFFDETAILS.LIST>      </EXCISETARIFFDETAILS.LIST>
        #                 <TCSCATEGORYDETAILS.LIST>      </TCSCATEGORYDETAILS.LIST>
        #                 <TDSCATEGORYDETAILS.LIST>      </TDSCATEGORYDETAILS.LIST>
        #                 <SLABPERIOD.LIST>      </SLABPERIOD.LIST>
        #                 <GRATUITYPERIOD.LIST>      </GRATUITYPERIOD.LIST>
        #                 <ADDITIONALCOMPUTATIONS.LIST>      </ADDITIONALCOMPUTATIONS.LIST>
        #                 <EXCISEJURISDICTIONDETAILS.LIST>      </EXCISEJURISDICTIONDETAILS.LIST>
        #                 <EXCLUDEDTAXATIONS.LIST>      </EXCLUDEDTAXATIONS.LIST>
        #                 <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
        #                 <PAYMENTDETAILS.LIST>      </PAYMENTDETAILS.LIST>
        #                 <BANKEXPORTFORMATS.LIST>      </BANKEXPORTFORMATS.LIST>
        #                 <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
        #                 <INTERESTCOLLECTION.LIST>      </INTERESTCOLLECTION.LIST>
        #                 <LEDGERCLOSINGVALUES.LIST>      </LEDGERCLOSINGVALUES.LIST>
        #                 <LEDGERAUDITCLASS.LIST>      </LEDGERAUDITCLASS.LIST>
        #                 <OLDAUDITENTRIES.LIST>      </OLDAUDITENTRIES.LIST>
        #                 <TDSEXEMPTIONRULES.LIST>      </TDSEXEMPTIONRULES.LIST>
        #                 <DEDUCTINSAMEVCHRULES.LIST>      </DEDUCTINSAMEVCHRULES.LIST>
        #                 <LOWERDEDUCTION.LIST>      </LOWERDEDUCTION.LIST>
        #                 <STXABATEMENTDETAILS.LIST>      </STXABATEMENTDETAILS.LIST>
        #                 <LEDMULTIADDRESSLIST.LIST>      </LEDMULTIADDRESSLIST.LIST>
        #                 <STXTAXDETAILS.LIST>      </STXTAXDETAILS.LIST>
        #                 <CHEQUERANGE.LIST>      </CHEQUERANGE.LIST>
        #                 <DEFAULTVCHCHEQUEDETAILS.LIST>      </DEFAULTVCHCHEQUEDETAILS.LIST>
        #                 <ACCOUNTAUDITENTRIES.LIST>      </ACCOUNTAUDITENTRIES.LIST>
        #                 <AUDITENTRIES.LIST>      </AUDITENTRIES.LIST>
        #                 <BRSIMPORTEDINFO.LIST>      </BRSIMPORTEDINFO.LIST>
        #                 <AUTOBRSCONFIGS.LIST>      </AUTOBRSCONFIGS.LIST>
        #                 <BANKURENTRIES.LIST>      </BANKURENTRIES.LIST>
        #                 <DEFAULTCHEQUEDETAILS.LIST>      </DEFAULTCHEQUEDETAILS.LIST>
        #                 <DEFAULTOPENINGCHEQUEDETAILS.LIST>      </DEFAULTOPENINGCHEQUEDETAILS.LIST>
        #                 <CANCELLEDPAYALLOCATIONS.LIST>      </CANCELLEDPAYALLOCATIONS.LIST>
        #                 <ECHEQUEPRINTLOCATION.LIST>      </ECHEQUEPRINTLOCATION.LIST>
        #                 <ECHEQUEPAYABLELOCATION.LIST>      </ECHEQUEPAYABLELOCATION.LIST>
        #                 <EDDPRINTLOCATION.LIST>      </EDDPRINTLOCATION.LIST>
        #                 <EDDPAYABLELOCATION.LIST>      </EDDPAYABLELOCATION.LIST>
        #                 <AVAILABLETRANSACTIONTYPES.LIST>      </AVAILABLETRANSACTIONTYPES.LIST>
        #                 <LEDPAYINSCONFIGS.LIST>      </LEDPAYINSCONFIGS.LIST>
        #                 <TYPECODEDETAILS.LIST>      </TYPECODEDETAILS.LIST>
        #                 <FIELDVALIDATIONDETAILS.LIST>      </FIELDVALIDATIONDETAILS.LIST>
        #                 <INPUTCRALLOCS.LIST>      </INPUTCRALLOCS.LIST>
        #                 <GSTCLASSFNIGSTRATES.LIST>      </GSTCLASSFNIGSTRATES.LIST>
        #                 <EXTARIFFDUTYHEADDETAILS.LIST>      </EXTARIFFDUTYHEADDETAILS.LIST>
        #                 <VOUCHERTYPEPRODUCTCODES.LIST>      </VOUCHERTYPEPRODUCTCODES.LIST>
        #                 </LEDGER>
        #                 </TALLYMESSAGE>
        #                 </REQUESTDATA>
        #                 </IMPORTDATA>
        #                 </BODY>
        #                 </ENVELOPE>
        #              """
        #
        #     # res = requests.post(url, data=params, headers={'Content-Type': 'application/xml'})
        #     headers = {'Content-Type': 'application/xml'}
        #     print("paramsparamsparamsparamsparams", params)
        #     res = requests.post(url, data=params.encode('utf-8'), headers=headers)
        #     root = ET.fromstring(res.content)
        #     # res = requests.post(url, data=params, headers={'Content-Type': 'application/xml'})
        #     print("response for ledgerssssssssss", res)
        #     created_in_tally = False
        #     altered_in_tally = False
        #     if len(root) > 9:
        #         if root[0].tag == 'LINEERROR':
        #             altered_in_tally = False
        #             sync_dict = {}
        #             sync_dict = {
        #                 'object': 'hr.employee',
        #                 'name': 'Ledgers',
        #                 'total_records': 1,
        #                 'record_name': line1.name,
        #                 'log_date': datetime.now(),
        #                 'reason': root[0].text,
        #                 # 'no_imported': 1,
        #             }
        #             self.env['sync.logs'].create(sync_dict)
        #         if root[1].tag == 'CREATED':
        #             if root[1].text == '1':
        #                 created_in_tally = True
        #         line1.write({'created_in_tally': created_in_tally})
        #     else:
        #         print("elseeeeeeeeeee", root[0].tag)
        #         if root[0].tag == 'CREATED':
        #             print("root[0].text", root[0].text)
        #             if root[0].text == '1':
        #                 created_in_tally = True
        #         # print("line and altred ,createddd", line, altered_in_tally, created_in_tally)
        #         line1.write({'created_in_tally': created_in_tally})
        #
        return True