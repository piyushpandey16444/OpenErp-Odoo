# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from psycopg2 import IntegrityError
from odoo import api, exceptions, fields, models, _
from odoo.exceptions import UserError

import string
#import pooler
#from . import migrator
from . import voucher
from . import ledger_voucher
from datetime import datetime

code = 0
class ledgers(models.Model):
    
    def insertRecords(self, dic,com, account, acc_type):
        global code
        parent = ""
        name = dic['NAME']
        
        #LOG ENTRY
        syncObj = self.env['sync.logs'].search([('record_name','=',name)])
        if not syncObj:
            vals = {
            'name': 'LEDGERS',
            'log_date': datetime.now(),
            'total_records': 1,
            'record_name' : name,
            'no_imported' : 1,
            'reason' : '',
            'object' : 'Res Partner',
            }
            res = self.env['sync.logs'].create(vals)
        
        print("dic['NAME']Name===",name)
        print ("insert recordsssssssssssss",dic)
        if dic.get('PARENT') and dic['PARENT']:
            parent = dic['PARENT']
            print("dic['PARENT']===",dic['PARENT'])
            domain = [('name','=',parent),('company_id','=',com.id)]     
            
            if dic['PARENT'] == 'Rent Receivable':
                dic['PARENT'] = 'Sundry Creditors'
                parent = dic['PARENT']
                print("dic['PARENT']===",dic['PARENT'])
                domain = [('name','=',parent),('company_id','=',com.id)] 
            elif dic['PARENT'] == 'Transporter':
                dic['PARENT'] = 'Sundry Debtors'
                parent = dic['PARENT']
                print("dic['PARENT']===",dic['PARENT'])
                domain = [('name','=',parent),('company_id','=',com.id)]  
                
        else:
            #searching for the 'account' of the company.
            domain = [('name','=',com.name)]
        
        code += 1        
        parent_id = account.search(domain)
        #If 'parent_id' not found then create the account for that. 
        if not parent_id:
            print('PARENT ID NOT THERE===')
            # creating the 'account' for the company partner.
            data = {'name':com.name, 'code':str.upper(com.name[0:3])+str(code), 'internal_type':'other', 'currency_mode':'current', 'user_type_id':5, 'company_id':com.id}
            print("DATA Value------",data.get('code'))

            try:
                account_Search = self.env['account.account'].search([('code','=',data.get('code'))])
                print("Account_Search----------",account_Search)
                if not account_Search:
                    print("ENTERED IN CREATING ACCOUNT******")
                    parent_id = account.create(data)     
                    print("parent__id",parent_id)    
                else:
                    parent_id = self.env['account.account'].search( [('code','=',data.get('code'))])       
            except:
                raise UserError(_('Company code already exist please use another company name.'))
            
            # creating acc receivable and acc payable for specified company partner.
            accTypObj = self.env['account.account.type']
            
            #searching for Account Types
            payableType = accTypObj.search([('name','=','Payable')])
            receivableType = accTypObj.search([('name','=','Receivable')])

            #creating 'Account Payable' for the company partner.
            CrData = {'name':com.name+' (Creditors)', 'code':str.upper(com.name[0:3])+' (C)'+str(code), 'type':'payable', 'currency_mode':'current', 'user_type_id':payableType[0].id, 'company_id':com.id, 'parent_id':parent_id,'reconcile':True}
            print("CR_DATA******",CrData)
            account_Search1 = self.env['account.account'].search([('code','=',CrData.get('code'))])
            print("Account_Search Cr----------",account_Search1)
            if not account_Search1:
                print("ENTERED IN CREATING ACCOUNT******")
                cr_id = account.create(CrData)
                print("cr_id----",cr_id)
            else:
                    cr_id = self.env['account.account'].search( [('code','=',CrData.get('code'))])  

            #creating 'Account Receivable' for the company partner.
            DrData = {'name':com.name+' (Debtors)', 'code':str.upper(com.name[0:3])+' (D)'+str(code), 'type':'receivable', 'currency_mode':'current', 'user_type_id':receivableType[0].id, 'company_id':com.id, 'parent_id':parent_id,'reconcile':True}
            account_Search2 = self.env['account.account'].search([('code','=',DrData.get('code'))])
            print("Account_Search Dr----------",account_Search2)
            if not account_Search2:
                print("ENTERED IN CREATING ACCOUNT******")
                dr_id = account.create(DrData)
            else:
                    dr_id = self.env['account.account'].search( [('code','=',DrData.get('code'))]) 
            print("CR& DR ID=====",cr_id,dr_id)
            #assigning the 'property_account_receivable_id' and 'property_account_payable_id' for the 'company partner'
            partnerObj = self.env['res.partner']
            partner_id = partnerObj.search([('name','=',com.name),('company_id','=',com.id)])
            print("Company'S Partner Id",partner_id)
            if partner_id:
                partnerData = {'customer':True, 'supplier':True, 'property_account_receivable_id':dr_id, 'property_account_payable_id':cr_id,'from_tally':True}
                partnerObj.write(partnerData)
            else:
                raise UserError("Error !\n Company Partner not found!! \n\nPlease create a partner of the selected company first and then run the wizard again.")
            #creating opening/closing situation journal.
            journalObj = self.env['account.journal']
            journalName = 'Opening/Closing'+" - ("+com.name+")"
            OpenJournalData = {'name':journalName, 'code':'OPN-'+com.name[0], 'type':'situation', 'default_debit_account_id':dr_id, 'default_credit_account_id':cr_id, 'company_id':com.id, 'view_id':3}
            open_id = journalObj.search([('name','=',journalName),('company_id','=',com.id)])

#             if open_id:
#                 journalObj.write(open_id, OpenJournalData)
#             else:
#                 open_id = journalObj.create(OpenJournalData)
                
        else:
            obj = parent_id[0]
            print("obj#########",obj)
            p_code = obj.code
            typ = 0
            usr_typ = 0

            # if parent exist then 'user_type(Account Type)' and 'type(Internal Type)' for the child is same as parent.
            if parent:
                print("Parent=====",parent,obj.user_type_id.id,obj.internal_type)
                usr_typ = obj.user_type_id.id
                typ = obj.internal_type
            #For the Parent Account we have to decide from dictionary key-value pair
            else:
                if dic.get('ISREVENUE') and dic.get('ISDEEMEDPOSITIVE'):
                    if dic['ISREVENUE']=='Yes' and dic['ISDEEMEDPOSITIVE']=='Yes':
                        usr_typ = acc_type.search([('name','=','Expenses')])
                        typ = 'other'
                    elif dic['ISREVENUE']=='Yes':
                        usr_typ = acc_type.search([('name','=','Income')])
                        typ = 'other'
                    elif dic['ISDEEMEDPOSITIVE']=='Yes':
                        usr_typ = acc_type.search([('name','=','Current Assets')])
                        typ = 'receivable'
                    elif dic['ISREVENUE']=='No' and dic['ISDEEMEDPOSITIVE']=='No':
                        usr_typ = acc_type.search([('name','=','Current Liabilities')])
                        typ = 'payable'
                    print("usr_typ[0]======",usr_typ)
                    usr_typ = usr_typ.id
                else: 
                    usr_typ = obj.user_type_id.id
                    typ = obj.internal_type
                    
            if name[:4] == 'Bank':
                typ = 'other'
            
            # creating double accounts(credit a/c and debit a/c) for res.partners and sales/purchase journals 
            contra_p_id    = []   
            if parent == 'Sundry Creditors':
                
                contra_u_typ = acc_type.search([('name','=','Current Assets')])
                domain = [('name','=','Sundry Debtors'),('company_id','=',com.id)]
                contra_parent_id = account.search(domain)
                contra_data = {'name':name+' (Debtors)', 'code':p_code + str(code), 'type':'receivable',
                                'parent_id':contra_parent_id[0], 'currency_mode':'current',
                                'user_type_id':contra_u_typ[0].id, 'company_id':com.id,'reconcile':True}
                code += 1
                
                try:
                    domain = [('name','=',name+' (Debtors)'),('company_id','=',com.id)]
                    contra_p_id = account.search(domain)
                    print("contraPID===",contra_p_id,domain)
                    if not contra_p_id:
                        print("Contra Data",contra_data)
                        contra_p_id = account.create(contra_data)
                        print("Contrapid",contra_p_id)
                        contra_p_id = [contra_p_id]
                    else:
                        code += 1
                
                except IntegrityError as e:
                    code += 50
                    raise UserError('Unique Code Constraint Error. Please Retry the Data Migration.')
                #here we change the name, because related entry is created at below
                name = name + ' (Creditors)'
                    
            elif parent == 'Sundry Debtors':
                print("Under Debtors",acc_type)
                contra_u_typ = acc_type.search([('name','=','Current Liabilities')])
                domain = [('name','=','Sundry Creditors'),('company_id','=',com.id)]
                contra_parent_id = account.search(domain)
                print("contra===",contra_parent_id)
                contra_data = {'name':name+' (Creditors)', 'code':p_code + str(code), 'internal_type':'payable',
                                'parent_id':contra_parent_id[0], 'currency_mode':'current',
                                'user_type_id':contra_u_typ[0].id,'company_id':com.id,'reconcile':True}
                print("CONTRA=====",contra_data)
                code += 1
                
                try:
                    domain = [('name','=',name+' (Creditors)'),('company_id','=',com.id)]
                    contra_p_id = account.search(domain)
                    print("Contra PID & DATA==",contra_p_id)
                    if not contra_p_id:
                        contra_p_id = account.create(contra_data)
                        print("contra_p_id",contra_p_id.reconcile)
                        contra_p_id = [contra_p_id]
                    else:
                        code += 1
                
                except IntegrityError as e:
                    code += 50
                    raise UserError('Unique Code Constraint Error. Please Retry the Data Migration.')
                
                #here we change the name, because related entry is created at below
                name = name + ' (Debtors)'

            
            #creating the account of ledger
            data = {'name':name, 'code':p_code + str(code), 'internal_type':typ, 'parent_id':parent_id[0],
                     'currency_mode':'current', 'user_type_id':usr_typ, 'company_id':com.id,'reconcile':True}
        
            try:
                
                domain = [('name','=',name),('company_id','=',com.id)]
                p_id = account.search(domain)
                syncObj = self.env['sync.logs'].search([('record_name','=',name)])
                syncObj.write({'is_migrated':True,'name':'GROUPS','object':'ACCOUNTS'})
                # If 'p_id' is not found, then create a new account.
                if not p_id:
                    print("DATA+========",data)
                    p_id = account.create(data)
                    p_id = [p_id]
                    syncObj = self.env['sync.logs'].search([('record_name','=',name)])
                    syncObj.write({'is_migrated':True,'name':'GROUPS','object':'ACCOUNTS'})
                #else increase the 'code' by one
                else:
                    code += 1
                    
            except IntegrityError as e:
                code += 50
                raise UserError('Unique Code Constraint Error. Please Retry the Data Migration.')
            
            #Creating Journals For Related Accounts
            
            try:
            #creating sales journal
                print("JRNL NAme-------",name)
                if name == 'Sales Accounts':  
                    journalObj = self.env['account.journal']
                    journalName = 'Sale Journal'+" - ("+com.name+")"
                    SaleJournalData = {'name':journalName, 'code':'SAJ-'+com.name[0], 'type':'sale', 'default_debit_account_id':p_id[0].id, 'default_credit_account_id':p_id[0].id, 'company_id':com.id, 'view_id':4}
                    saj_id = journalObj.search([('name','=',journalName),('company_id','=',com.id)])
        
                    if saj_id:
                        journalObj.write(SaleJournalData)
                    else:
                        saj_id = journalObj.create(SaleJournalData)
    
                #creating purchase journal    
                elif name == 'Purchase Accounts': 
                    journalObj = self.env['account.journal']
                    journalName = 'Vendor Bills'+" - ("+com.name+")"
                    PurchaseJournalData = {'name':journalName, 'code':'EXJ-'+com.name[0], 'type':'purchase', 'default_debit_account_id':p_id[0].id, 'default_credit_account_id':p_id[0].id, 'company_id':com.id, 'view_id':4}
                    exj_id = journalObj.search([('name','=',journalName),('company_id','=',com.id)])
                    print("Journa ID",exj_id,p_id)
                    if exj_id:
                        journalObj.write(PurchaseJournalData)
                    else:
                        exj_id = journalObj.create(PurchaseJournalData)
                    
                # creating res.partner for sundry creditors/debtors    
                elif parent[:6] == 'Sundry': 
                    address = ''
                    address1 = ''
                    pan_no = ''
                    state = ''
                    pinCode = ''
                    country_id = ''
                    pymntDtls = ''
                    
                    print("NAME!!!!!!!!!!!!!!!!!!!!!",dic['NAME'])
                    name = dic['NAME']
                    
                    if dic.get('ADDRESS.LIST') and dic['ADDRESS.LIST']:
                        addr = dic['ADDRESS.LIST']
                        address = addr.get('ADDRESS')[0]
                        address1 = addr.get('ADDRESS')[1]         
                    if dic.get('INCOMETAXNUMBER') and dic['INCOMETAXNUMBER']:
                        pan_no = dic['INCOMETAXNUMBER']
                    if dic.get('LEDSTATENAME') and dic['LEDSTATENAME']:
                        state = dic['LEDSTATENAME']
                    if dic.get('PINCODE') and dic['PINCODE']:
                        pinCode = dic['PINCODE']
                    if dic.get('COUNTRYNAME') and dic['COUNTRYNAME']:
                        country = dic['COUNTRYNAME']
                        country_id = self.env['res.country'].search([('name','=',country)]).id
                                        
                    if dic.get('PAYMENTDETAILS.LIST') and dic['PAYMENTDETAILS.LIST']:
                        pymntDtls = dic['PAYMENTDETAILS.LIST']
                        bankName = pymntDtls.get('BANKNAME')
                        ifscCode = pymntDtls.get('IFSCODE')
                        AccountNumber = pymntDtls.get('ACCOUNTNUMBER')
                        pymntFavouring = pymntDtls.get('PAYMENTFAVOURING')
                        partner_id = self.env['res.partner'].search([('name','=',dic['NAME'])]).id
                        bank = self.env['res.bank'].search([('name','=',bankName)])
                        if bank:
                            bank_id = bank
                        else:
                            bankData = {'name':bankName,'bic':ifscCode}
                            print('bankData==',bankData)
                            bank_id = self.env['res.bank'].create(bankData)
                              
                        bankDetails = {'sanitized_acc_number': AccountNumber , 'acc_number':AccountNumber, 'bank_id':bank_id.id, 'partner_id':partner_id}
                        print(partner_id)
                        PartnerBankObj = self.env['res.partner.bank'].search([('acc_number','=',AccountNumber),('partner_id','=',partner_id)])
                        if not PartnerBankObj:
                            bankObj = self.env['res.partner.bank'].create(bankDetails)
                        
                    partnerObj = self.env['res.partner']
                    PartnerData = {}
                    if parent == 'Sundry Debtors':
                        partnerData = {'property_account_payable_id':contra_p_id[0], 'property_account_receivable_id':p_id[0], 'customer':True, 'supplier':False,'street': address,'street2':address1, 'city':state, 'vat':  pan_no, 'zip' : pinCode, 'country_id':country_id,'company_id':com.id,'from_tally':True}
                        
                        partner_id = partnerObj.search([('name','=',name),('company_id','=',com.id)])
                        print("Partner Id & DATA",partner_id,partnerData)
                        if partner_id:
                            partner_id.write(partnerData)
                            syncObj = self.env['sync.logs'].search([('record_name','=',name)])
                            syncObj.write({'is_migrated':True})
                        else:
                            print("PARTNER_DATA",partnerData,name)
                            partnerData['name'] = name
                            partner_id = partnerObj.create(partnerData)
                            print("Partner Name====",partner_id)
                            syncObj = self.env['sync.logs'].search([('record_name','=',name)])
                            syncObj.write({'is_migrated':True})
                        
                    elif parent == 'Sundry Creditors':
                        print('name-()*******',name)
                        partnerData = {'property_account_payable_id':p_id[0], 'property_account_receivable_id':contra_p_id[0], 'supplier':True, 'customer':False, 'street': address,'street2':address1, 'city':state, 'vat':pan_no ,'zip' : pinCode, 'country_id':country_id,'company_id':com.id,'from_tally':True}
                    
                        partner_id = partnerObj.search([('name','=',name),('company_id','=',com.id)])
                        print("Partner Id & DATA",partner_id,partnerData)
                        if partner_id:
                            partner_id.write(partnerData)
                            syncObj = self.env['sync.logs'].search([('record_name','=',name)])
                            syncObj.write({'is_migrated':True})
                        else:
                            print("PARTNER_DATA",partnerData,name)
                            partnerData['name'] = name
                            partner_id = partnerObj.create(partnerData)
                            print("Partner Name====",partner_id)
                            syncObj = self.env['sync.logs'].search([('record_name','=',name)])
                            syncObj.write({'is_migrated':True})
                            
                # creating account.journal for bank
                elif parent[:4] == 'Bank': 
                
                    journalObj = self.env['account.journal']
                    journalName = str.upper(name)+" - ("+com.name+")"
                    journalData = {'name':journalName, 'code':str.upper(name[0:5]), 'type':'bank', 'default_debit_account_id':p_id[0].id, 'default_credit_account_id':p_id[0].id, 'company_id':com.id, 'view_id':1}
                    bank_id = journalObj.search([('name','=',journalName),('company_id','=',com.id)])
                    
                    if bank_id:
                        journalObj.write(journalData)
                    else:
                        bank_id = journalObj.create(journalData)
    
                # creating account.journal for cash        
                elif parent == 'Cash-in-hand': 
                
                    journalObj = self.env['account.journal']
                    journalName = str.upper(name)+" - ("+com.name+")"
                    journalData = {'name':journalName, 'code':str.upper(name[0:5]), 'type':'cash', 'default_debit_account_id':p_id[0].id, 'default_credit_account_id':p_id[0].id, 'company_id':com.id, 'view_id':1}
                    cash_id = journalObj.search([('name','=',journalName),('company_id','=',com.id)])
                    
                    if cash_id:
                        journalObj.write(journalData)
                    else:
                        cash_id = journalObj.create(journalData)
                        
                elif name == 'Reserves & Surplus':
    
                    domain = [('name','=',com.name)]
                    compObj = self.env['res.company']
                    search_id = compObj.search(domain)
                    print("search_id=======",search_id,p_id[0])
    #                     if search_id:
    #                         compObj.write( search_id, {'property_reserve_and_surplus_account':p_id[0]})
                        
            except Exception as e:
                raise UserError(('Error!!!', str(e)))

            
            if dic.get('OPENINGBALANCE') and dic['OPENINGBALANCE']:
                opening_balance = float(dic['OPENINGBALANCE'])
                print("Opening Balance",opening_balance)
#                 date = str.join(str(datetime.now())[:10].split("-"),"")
                date = datetime.now()
                journalObj = self.env['account.journal']

#                journalName = 'Opening/Closing'+" - ("+com.name+")"
#                domain = [('name','=',journalName),('company_id','=',com.id)]
                domain = [('type','=','general'),('company_id','=',com.id)]
                search_id = journalObj.search(domain)
                print("search_id[0] =++++++++++++",domain,search_id[0])
                
                #If 'OPENINGBALANCE' is positive then 'credit'
                #If 'OPENINGBALANCE' is negative then 'debit'
                voucherLineData = {'AMOUNT':opening_balance, 'LEDGERNAME':name, 'ISPARTYLEDGER':'Yes'}
                print('voucherLineData++++++++',voucherLineData)
                voucherData = {'DATE':date, 'PARTYLEDGERNAME':name, 'VOUCHERTYPENAME':'Receipt', 'NARRATION':'Opening Balance', 'ALLLEDGERENTRIES.LIST':[voucherLineData], 'JOURNALID':search_id[0].id}

                self.env['voucher1'].insertVouchers(voucherData ,com)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
                
                    
                    
                    
