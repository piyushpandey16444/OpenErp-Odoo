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

import time
# import datetime
from datetime import datetime
from dateutil.relativedelta import relativedelta
from psycopg2 import IntegrityError
import string
from odoo import api, exceptions, fields, models, _
from odoo.exceptions import UserError,AccessError,ValidationError
import json

class voucher(models.Model): 

    

#     def __init__(self):
#         self.poolObj = pooler.get_pool(cr.dbname)
#         self.voucherObj = self.poolObj.get('account.voucher')
#         self.acctObj = self.poolObj.get('account.account')
#         self.partnerObj = self.poolObj.get('res.partner')
#         self.jrObj = self.poolObj.get('account.journal')
        
    # Creates 'fiscal year' and its 12 'periods'
    # def createFY(self,  dt, company):
    #     fiscalYrObj = self.env['account.fiscalyear']
    #
    #     yr = str(datetime.datetime.today().year)
    #     #data = {'code':'FY'+dt[:4], 'name':'Fiscal Year '+dt[:4]+' '+company.name, 'company_id':company.id, 'date_start':datetime(yr,01,01), 'date_stop':datetime(yr,12,31)}
    #
    #     fy_id = fiscalYrObj.create(data)
    #
    #     fy = fiscalYrObj.browse(fy_id)
    #
    #     ds = datetime.strptime(fy.date_start, '%Y-%m-%d')
    #     while ds.strftime('%Y-%m-%d')<fy.date_stop:
    #         de = ds + relativedelta(months=1, days=-1)
    #
    #         if de.strftime('%Y-%m-%d')>fy.date_stop:
    #             de = datetime.strptime(fy.date_stop, '%Y-%m-%d')
    #
    #         self.env['account.period'].create({
    #             'name': ds.strftime('%m/%Y'),
    #             'code': ds.strftime('%m/%Y'),
    #             'date_start': ds.strftime('%Y-%m-%d'),
    #             'date_stop': de.strftime('%Y-%m-%d'),
    #             'fiscalyear_id': fy.id,
    #         })
    #         ds = ds + relativedelta(months=1)
    #     return fy_id

    def createFY(self, dt, company):
        fiscalYrObj = self.env['account.fiscalyear']
        print("ledger vocucher", dt, company)
        yr = str(datetime.today().year)
        # data = {'code':'FY'+dt[:4], 'name':'Fiscal Year '+dt[:4]+' '+company.name, 'company_id':company.id, 'date_start':datetime(yr,01,01), 'date_stop':datetime(yr,12,31)}
        yr = str(datetime.today().year)
        print("yrrrrrrrrrrrr", yr)
        format_str = '%Y-%m-%d'
        date_start = datetime.strptime(yr + '-' + '01' + '-' + '01', format_str)
        date_end = datetime.strptime(yr + '-' + '12' + '-' + '31', format_str)
        print("date startttttttttttt0", date_start, type(date_start))
        data = {
            'code': 'FY' + yr,
            'name': 'Fiscal Year ' + yr + '-' + company.name,
            'company_id': company.id,
            'date_start': date_start,
            'date_stop': date_end
        }

        fy_id = fiscalYrObj.create(data)

        fy = fiscalYrObj.browse(fy_id)

        ds = datetime.strptime(fy_id.date_start, '%Y-%m-%d')
        while ds.strftime('%Y-%m-%d') < fy_id.date_stop:
            de = ds + relativedelta(months=1, days=-1)

            if de.strftime('%Y-%m-%d') > fy_id.date_stop:
                de = datetime.strptime(fy_id.date_stop, '%Y-%m-%d')

            self.env['account.period'].create({
                'name': ds.strftime('%m/%Y'),
                'code': ds.strftime('%m/%Y'),
                'date_start': ds.strftime('%Y-%m-%d'),
                'date_stop': de.strftime('%Y-%m-%d'),
                'fiscalyear_id': fy_id.id,
            })
            ds = ds + relativedelta(months=1)
        return fy_id.id
    
    def createAccountMoveLine(self,  dic, move_id, period_id, journal_id, VTYPE, com):
        print("ENtry In AML------------------------============",VTYPE)
        vtype = VTYPE
        if vtype == 'Sales' or vtype == 'Purchase':
            print("vtype-----",vtype)
            if dic.get('ALLLEDGERENTRIES.LIST') and dic['ALLLEDGERENTRIES.LIST']:
                list1 = []
                entries = dic['ALLLEDGERENTRIES.LIST']
                print(json.dumps(entries, indent=4, sort_keys=True))
                for i in entries:
                     
                    credit = 0
                    debit = 0
                    
                    amount = float(i['AMOUNT'])
                    print("amount===",amount)
                    if amount > 0:
                        credit = amount
                    else:
                        debit = amount * (-1)
                
                    name = i['LEDGERNAME']

                    domain = [('name','=',name),('company_id','=',com.id)]
                    print ("domain for account account",domain)
                    sid = self.env['account.account'].search(domain)
                    print ("siddddddddddddddd",sid)
                    if sid:
                        Object = self.env['account.account'].search([('id','=',sid[0].id)])
                        print("sid--------",sid[0].id,Object)
                        if Object.user_type_id.name == 'view' or Object.user_type_id.name == 'closed':
                            return True
                    
                        data = (0,False,{'name':name, 'debit':debit, 'credit':credit, 'account_id':sid[0].id, 'move_id':move_id.id, 'period_id':period_id.id, 'journal_id':journal_id.id})
                        list1.append(data)
                        print ("------====## LIST ##===----------",list1)

                        print("AML------data===",data)
                    print ("move iddddddddd",move_id)
                    move_id.write({'line_ids':list1})

#                         try:
#                             accMoveLineObj = self.env['account.move.line']
#                             accMoveLineObj.create( val)
#                         except Exception as e:
#                             raise UserError(('Move Line Creation Error!!!', str(e)))
                
        else: #if vtype == 'Payment' or vtype == 'Receipt':
            
            if dic.get('ALLLEDGERENTRIES.LIST') and dic['ALLLEDGERENTRIES.LIST']:
                list1 = []
                entries = dic['ALLLEDGERENTRIES.LIST']
                for i in entries:
                    
                    credit = 0
                    debit = 0
            
                    name = i['LEDGERNAME']
                    
                    Partner = self.env['res.partner'].search([('name','=',name)])
                    if Partner:
                        name = name + ' (Creditors)'
                    else:
                        name = name
                    print("NAME---",name)
                    domain = [('name','=',name),('company_id','=',com.id)]
                    sid = self.env['account.account'].search(domain)
                    print("sid-----@@@@@@@@@@@@---",sid)
                    print("DOMAIN & SID",domain,sid)
                    Object = self.env['account.account'].search([('id','=',sid[0].id)])
                    print("Object-----",Object)
                    if Object.user_type_id.name == 'view' or Object.user_type_id.name == 'closed':
                        print("RETURN----")
                        return True
                
                    accMoveLineObj = self.env['account.move.line']
                    amount = float(i['AMOUNT'])
                    print("Amount======",amount)
                    if amount > 0:
                        credit = amount
                    else:
                        debit = amount * (-1)
                    
                    data = (0,False, {'name':name, 'debit':debit, 'credit':credit, 'account_id':sid[0].id, 'move_id':move_id.id, 'period_id':period_id.id, 'journal_id':journal_id.id})
                    list1.append(data)
                print("Check Data List1====",list1)
                move_id.write({'line_ids':list1})
                
#                     try:
#                         accMoveLineObj.create(data)
#                     except Exception as e:
#                         raise UserError(('Move Line Creation Error!!!', str(e)))
                    
        return True
    
    def createAccountMove(self, dic, period_id, VTYPE, com):
        
        if dic.get('DATE') and dic['DATE']:
            date = dic['DATE']
            
        narration = ''
        guid = ''
        if dic.get('NARRATION') and dic['NARRATION']:
            narration = dic['NARRATION']
        if dic.get('GUID') and dic['GUID']:
            guid = dic['GUID']
        
        #searching for the 'Company Account'
        acc_id = self.env['account.account'].search( [('name','=',com.name),('company_id','=',com.id)])
        
        #Creating 'General' Journal for Indirect Incomes/Expenses.
        journalObj = self.env['account.journal']
        journalName = 'General Journal'+" - ("+com.name+")"

        #assigning 'Company Account' to 'default_debit_account_id' and 'default_credit_account_id' for the 'General'
        GeneralJournalData = {'name':journalName, 'code':'GEN-'+com.name[0], 'type':'general', 'default_debit_account_id':acc_id[0].id, 'default_credit_account_id':acc_id[0].id, 'company_id':com.id, 'view_id':3}
        print("GeneralJournalData===",GeneralJournalData)
        journal_id = journalObj.search([('name','=',journalName),('company_id','=',com.id)])
        if journal_id:
            journalObj.write(GeneralJournalData)
            journal_id = journal_id[0]
        else:
            journal_id = journalObj.create( GeneralJournalData)

        data = {'period_id':period_id.id, 'journal_id':journal_id.id, 'date':date, 'narration':narration,'from_tally':True,'tally_guid':guid}
        print("data=",data)
        #check IF Already Exist
        check_move_id = self.env['account.move'].search([('tally_guid','=',guid)])
        print('check_move_id====',check_move_id)
            
        if check_move_id:
            check_move_id.write(data)
        else:
            #creating entries in 'account.move'        
            move_id = accMoveObj = self.env['account.move'].create(data)
            
            #creating entries for 'account.move.line'
            self.createAccountMoveLine(dic, move_id, period_id, journal_id, VTYPE, com)
        
        return True
    
    @api.multi
    def createAccountVoucherLine(self, dic, com, voucher_id, vtype):
        a = []
        if vtype == 'Sale' or vtype == 'Purchase':
            
            if dic.get('LEDGERENTRIES.LIST') and dic['LEDGERENTRIES.LIST']:
                
                i = dic['LEDGERENTRIES.LIST']
                if type(i) == list:
                    for x in i:
                       if x['AMOUNT']:
                           print("========",x['AMOUNT'])
                           a.append(x['AMOUNT'])
                else:
                    print("========",i['AMOUNT'])
                    a.append(i['AMOUNT'])
#                 print("i",i[0]['AMOUNT'])
                print("a=====",a)
                if float(a[0])<0:
                    typ = 'cr'
                    a[0] = float(a[0]) * (-1)
                else:
                    typ = 'dr'
                
                if vtype == 'Sale':    
                    name = 'Sales Accounts'
                elif vtype == 'Purchase':
                    name = 'Purchase Accounts'
                
                domain = [('name','=',name),('company_id','=',com.id)]
                sid = self.env['account.account'].search(domain)
                
                data = {'voucher_id':voucher_id.id, 'name':'', 'account_id':sid[0].id, 'price_unit':a[0]}
                print("Sale AVL DATA",data)
                accVhrLineObj = self.env['account.voucher.line']
                                
                try:
                    accVhrLineObj.create(data)
                except Exception as e:
                    raise UserError(('Voucher Line Creation Error!!!', str(e)))
            
            if dic.get('ALLLEDGERENTRIES.LIST') and dic['ALLLEDGERENTRIES.LIST']:
                entries = dic['ALLLEDGERENTRIES.LIST']
                
                for i in entries:
                
                    if float(i['AMOUNT'])>0:
                        typ = 'cr'
                        name = i['LEDGERNAME']
                        domain = [('name','=',name),('company_id','=',com.id)]
                        sid = self.env['account.account'].search(domain)
                        if not sid:
                            name = i['LEDGERNAME']+' (Creditors)'
                            domain = [('name','=',name),('company_id','=',com.id)]
                            sid = self.env['account.account'].search(domain)
                    else:
                        typ = 'dr'
                        i['AMOUNT'] = float(i['AMOUNT']) * (-1)
                        name = i['LEDGERNAME']
                        domain = [('name','=',name),('company_id','=',com.id)]
                        sid = self.env['account.account'].search(domain)
                        if not sid:
                            name = i['LEDGERNAME']+' (Debtors)'
                            domain = [('name','=',name),('company_id','=',com.id)]
                            sid = self.env['account.account'].search(domain)

                    data = {'voucher_id':voucher_id.id, 'name':'', 'account_id':sid[0].id, 'price_unit':i['AMOUNT']}
                    accVhrLineObj = self.env['account.voucher.line']
                    try:
                        accVhrLineObj.create( data)
                    except Exception as e:
                        raise UserError(('Voucher Line Creation Error!!!', str(e)))
                    
        elif vtype == 'Payment' or vtype == 'Receipt':
            
            if dic.get('ALLLEDGERENTRIES.LIST') and dic['ALLLEDGERENTRIES.LIST']:
                entries = dic['ALLLEDGERENTRIES.LIST']
                length = len(entries)
                #for i in entries:
                i = entries[length - 1]
                if float(i['AMOUNT'])>0:
                    typ = 'cr'
                    name = i['LEDGERNAME']
                    domain = [('name','=',name),('company_id','=',com.id)]
                    sid = self.env['account.account'].search(domain)
                    if not sid:
                        name = i['LEDGERNAME']+' (Creditors)'
                        domain = [('name','=',name),('company_id','=',com.id)]
                        sid = self.env['account.account'].search(domain)
                else:
                    typ = 'dr'
                    i['AMOUNT'] = float(i['AMOUNT']) * (-1)
                    name = i['LEDGERNAME']
                    domain = [('name','=',name),('company_id','=',com.id)]
                    sid = self.env['account.account'].search(domain)
                    if not sid:
                        name = i['LEDGERNAME']+' (Debtors)'
                        domain = [('name','=',name),('company_id','=',com.id)]
                        sid = self.env['account.account'].search(domain)
                
                print ("iiiiiiiiiiiiiii",i)
                print("Check Dat==1111111",voucher_id)
                print("Check Dat==222",  sid)
                print("Check Dat==33333333", i['AMOUNT'])
                print("Check Dat==44444444",  typ)
                data = {'voucher_id':voucher_id.id, 'name':'', 'account_id':sid[0].id, 'price_unit':i['AMOUNT']}
                print("AVL DATA",data)
                accVhrLineObj = self.env['account.voucher.line']
                try:
                    accVhrLineObj.create( data)
                except Exception as e:
                    raise UserError(('Voucher Line Creation Error!!!', str(e)))
                
        else:
            vtype = 'Receipt'
            if dic.get('ALLLEDGERENTRIES.LIST') and dic['ALLLEDGERENTRIES.LIST']:
                entries = dic['ALLLEDGERENTRIES.LIST']
                
                for i in entries:
                
                    if float(i['AMOUNT'])>0:
                        typ = 'cr'
                        name = i['LEDGERNAME']
                        domain = [('name','=',name),('company_id','=',com.id)]
                        sid = self.env['account.account'].search(domain)
                        if not sid:
                            name = i['LEDGERNAME']+' (Creditors)'
                            domain = [('name','=',name),('company_id','=',com.id)]
                            sid = self.env['account.account'].search(domain)
                    else:
                        typ = 'dr'
                        i['AMOUNT'] = float(i['AMOUNT']) * (-1)
                        name = i['LEDGERNAME']
                        domain = [('name','=',name),('company_id','=',com.id)]
                        sid = self.env['account.account'].search(domain)
                        if not sid:
                            name = i['LEDGERNAME']+' (Debtors)'
                            domain = [('name','=',name),('company_id','=',com.id)]
                            sid = self.env['account.account'].search(domain)

                    data = {'voucher_id':voucher_id.id, 'name':'', 'account_id':sid[0].id, 'price_unit':i['AMOUNT']}
                    accVhrLineObj = self.env['account.voucher.line']
                    try:
                        accVhrLineObj.create(data)
                    except Exception as e:
                        raise UserError(('Voucher Line Creation Error!!!', str(e)))
    
        return True

    def get_current_fiscal_year(self,date,company):
        fiscalYrObj = self.env['account.fiscalyear']
        year = date[:4]
        # self.env.cr.execute("""select id from account_fiscalyear where date_part('year', date_start) = %s""")
        self.env.cr.execute( """ select id from account_fiscalyear where state='draft' and company_id = %s and date_part('year', date_start) = %s""" ,(company.id,year))
        data = self.env.cr.dictfetchall()
        # self.env.cr.execute(
        #     """select sum(dline.product_remain_qty) from delivery_order_line as dline left join delivery_order as dol on (dline.delivery_id=dol.id) where dline.product_id= %s and dline.delivery_id in %s  """,
        #     (sale_line.product_id.id, tuple(dlist)))
        # outgoing = self.env.cr.dictfetchall()
        print ("dataaaaaaaaaaa",data)
        if len(data) > 0:
            fiscal_id = data[0].get('id')
            fiscal_id = fiscalYrObj.browse(fiscal_id)
            print ("fiscal idddddddddd",fiscal_id)
            return fiscal_id
        else:
            fiscal_code = 'FY' + year
            print("fiscal codeeeeeeeeeeee", fiscal_code, type(fiscal_code))

            # domain = [('code', '=', '19-20'), ('company_id', '=', com.id)]
            domain = [('code', '=', fiscal_code), ('company_id', '=', company.id), ('state', '=', 'draft')]
            print("DT Domain==", domain)
            fy_id = fiscalYrObj.search(domain)
            if not fy_id:
                fiscal_code = year[2:4] + '-' + str(int(year[2:4])+1)
                domain = [('code', '=', fiscal_code), ('company_id', '=', company.id), ('state', '=', 'draft')]
                print("DT Domain==", domain)
                fy_id = fiscalYrObj.search(domain)
                if not fiscal_code:
                    raise ValidationError("Dispatch Deadline Date cannot be less then today !")
                else:
                    return  fy_id
            else:
                return fy_id
    
    @api.multi
    def insertVouchers(self,  dic, com):
        print("Inserted In Vouchers")
        print (" tally data in insert voucherssssssss",dic)
        vtype = ''
        DATE = ''
        NARRATION = ''
        ACC_ID = ''
        JR_ID = ''

        #'Date' is used to create 'fiscal year' and its related 'periods'
        if dic.get('DATE') and dic['DATE']: #for date and fiscal year & periods
            dt = ''
            DATE = dic['DATE']
            dt = str(datetime.today().year)
            print("DATE====",DATE)
            fiscalYrObj = self.env['account.fiscalyear']
            # year = DATE[:4]
            # print("yearrrrrrrrrrr22222", year)
            # fiscal_code = 'FY' + year
            # print("fiscal codeeeeeeeeeeee222222222", fiscal_code, type(fiscal_code))
            #
            # domain = [('code','=',fiscal_code),('company_id','=',com.id),('state','=','draft')]
            # print("DT Domain==",domain)
            # fy_id = fiscalYrObj.search(domain)
            fy_id = self.get_current_fiscal_year(DATE,com)
            print("Current FY",fy_id)
            #If fiscal year is not found then create Fiscal Year and its related periods.
            if not fy_id:
                fy_id = self.createFY( DATE, com)
                #searching the period from the specified date.
                period_id = self.env['account.period'].search( [('code','=',DATE[4:6]+'/'+DATE[:4]),('fiscalyear_id','=',fy_id)])
            #searching the period from the specified date.
            else:
                period_id = self.env['account.period'].search( [('code','=',DATE[4:6]+'/'+DATE[:4]),('fiscalyear_id','=',fy_id[0].id)])
        
        print ("period iddddddddddddddd",period_id)
        # deciding partner name for the 'Accounting Voucher'.
        #if 'PARTYLEDGERNAME' is there then search for the partner.
        print("Partner Ledger",dic['PARTYLEDGERNAME'])
        if dic.get('PARTYLEDGERNAME') and dic['PARTYLEDGERNAME']: 
            partnerObj = self.env['res.partner']
            partner_id = self.env['res.partner'].search([('name','=',dic['PARTYLEDGERNAME']),('company_id','=',com.id)])
            if not partner_id:
                partner_id = self.env['res.partner'].search([('name','=',com.name),('company_id','=',com.id)])
            part_obj = self.env['res.partner'].browse(partner_id[0])
            print("Partner Object",part_obj)
        #else search for the 'Company Partner'
        else:
            partner_id = self.env['res.partner'].search( [('name','=',com.name),('company_id','=',com.id)])
            part_obj = self.env['res.partner'].browse( partner_id[0])
            print("Partner Obj",part_obj)
        # deciding 'voucher type' for the 'Accounting Voucher'
        #for journal and account selection    
        print("dic['VOUCHERTYPENAME']==",dic['VOUCHERTYPENAME'])
        if dic.get('VOUCHERTYPENAME') and dic['VOUCHERTYPENAME']: 
            VTYPE = dic['VOUCHERTYPENAME']
            print("DIC VTYPE====",dic['VOUCHERTYPENAME'])
            if dic.get('ALLLEDGERENTRIES.LIST') and dic['ALLLEDGERENTRIES.LIST']: 
                i = len(dic['ALLLEDGERENTRIES.LIST'])-1
            
            if VTYPE == 'Sales' or VTYPE == 'Debit Note' or VTYPE == 'TAX INVOICE':
                print("==VTYPE ENTRY IN SALES==")
                vtype = 'sale'
                VTYPE = 'Sale'
                ACC_ID = part_obj.property_account_receivable_id.id
                JR_ID = self.env['account.journal'].search( [('name','=','Tax Invoices')]) 
                print("Journl ID==",JR_ID)
                
            elif VTYPE == 'Purchase' or VTYPE =='Credit Note':
                print("==VTYPE ENTRY IN Purchase==")
                vtype = 'purchase'
                VTYPE = 'Purchase'
                ACC_ID = part_obj.property_account_payable_id.id
                JR_ID = self.env['account.journal'].search( [('name','=','Vendor Bills')])
                print("Purchase JR_ID==",JR_ID)
            
            elif VTYPE == 'Payment':
                print("==VTYPE ENTRY IN Payment==")
                vtype = 'purchase'
                VTYPE = 'Payment'
                ACC_ID = part_obj.property_account_payable_id.id
                ledgerName = dic['ALLLEDGERENTRIES.LIST'][i]['LEDGERNAME']
                print("ladger Name==",ledgerName)
                journalName = str.upper(ledgerName)+" - ("+com.name+")"
                JR_ID = self.env['account.journal'].search( [('name','=',journalName)])
                print("JR_ID==",JR_ID)
            
            elif VTYPE == 'Receipt' or VTYPE == 'Contra' or VTYPE == 'Journal':
                print("==VTYPE ENTRY IN Receipt==")
                vtype = 'purchase'
                ACC_ID = part_obj.property_account_receivable_id.id
                ledgerName = dic['ALLLEDGERENTRIES.LIST'][i]['LEDGERNAME']
                print("ledgerName==",ledgerName,ACC_ID)
                journalName = str.upper(ledgerName)+" - ("+com.name+")"
                print("journalName==",journalName)
                JR_ID = self.env['account.journal'].search( [('name','=','Vendor Bills')])
                print("JR_ID===",JR_ID)
            
            elif VTYPE == 'Material Out-Job Work':
                print("==VTYPE ENTRY IN Material Out-Job Work==")
                vtype = 'sale'
                VTYPE = 'Sale'
                ACC_ID = part_obj.property_account_payable_id.id
                JR_ID = self.env['account.journal'].search( [('name','=','Tax Invoices')])
                print("SALE JR_ID==",JR_ID)
                
            elif VTYPE == 'Stock Journal':
                print("==VTYPE ENTRY IN Stock Journal==")
                vtype = 'sale'
                VTYPE = 'Sale'
                ACC_ID = part_obj.property_account_payable_id.id
                JR_ID = self.env['account.journal'].search( [('name','=','Stock Journal')])
                print("SALE JR_ID==",JR_ID)
            elif VTYPE == 'RENT INVOICE':
                print("==VTYPE ENTRY IN RENT JOURNAL==")
                vtype = 'sale'
                VTYPE = 'Sale'
                ACC_ID = part_obj.property_account_payable_id.id
                JR_ID = self.env['account.journal'].search( [('name','=','Miscellaneous Operations')])
            else:
                print("==VTYPE ENTRY IN MISCELLANEOUS JOURNAL==")
                vtype = 'sale'
                VTYPE = 'Sale'
                ACC_ID = part_obj.property_account_payable_id.id
                JR_ID = self.env['account.journal'].search( [('name','=','Miscellaneous Operations')])
                            
                
        #deciding the entry :: is it misc. income/expence or indirect income/expence or not?? 
        if dic.get('ALLLEDGERENTRIES.LIST') and dic['ALLLEDGERENTRIES.LIST']:
            for i in dic['ALLLEDGERENTRIES.LIST']:
                #if 'ISPARTYLEDGER' == 'No', then entries goes to 'account.move'
                if i.get('ISPARTYLEDGER') and i['ISPARTYLEDGER']=='No':
                    print ("periodddddddddddddddddddd",period_id)
                    self.createAccountMove( dic, period_id[0], VTYPE, com)
                    return True
        
        narration =''
        guid = ''
        if dic.get('NARRATION') and dic['NARRATION']:
            print("Entered In NARRATION",dic['NARRATION'])
            NARRATION = dic['NARRATION']
        if dic.get('GUID') and dic['GUID']:
            print("Entered In GUID",dic['GUID'])
            guid = dic['GUID']
        if dic.get('JOURNALID') and dic['JOURNALID']:
            print("Entered In JOURNALID",dic['JOURNALID'])
            JR_ID = [dic['JOURNALID']]
            print("///////==JR_ID ENTRY IN JOURNALID==\n\\\\\\",JR_ID)
        
        print("+++Check Ids++++",JR_ID,vtype)
        print("ACC_ID===",ACC_ID)
        data = {'voucher_type': vtype, 'date':DATE, 'journal_id':JR_ID[0].id, 'narration':NARRATION,
                 'state':'draft', 'account_id':ACC_ID, 'partner_id': part_obj.id.id, 
                 'pay_now':'pay_later','from_tally':True,'tally_guid':guid}
        print("VTYPE==%%%%",VTYPE)
        print("date for account move line createeeeee", data)
        # print("aaaaaaaaaaaaaa", a)
        
        VchNo = ''
        if dic.get('VOUCHERNUMBER') and dic['VOUCHERNUMBER']:
            VchNo = dic['VOUCHERNUMBER']
            
        
        voucherObj = self.env['account.voucher']
        
        Voucher = self.env['account.voucher'].search([('tally_guid','=',guid)])
        if Voucher:
            voucherObj.write(data)
            syncObj = self.env['sync.logs'].search([('record_name','=',part_obj.id.name)])
            syncObj.write({'is_migrated':True,'log_date': datetime.now()})
        else:
            vid = voucherObj.create(data)
            
            #LOG ENTRY
            syncObj = self.env['sync.logs'].search([('record_name','=',part_obj.id.name)])
            if not syncObj:
                vals = {
                'name': 'VOUCHERS',
                'log_date': datetime.now(),
                'total_records': 1,
                'record_name' : part_obj.id.name,
                'no_imported' : 1,
                'reason' : '',
                'object' : 'ACCOUNT VOUCHER',
                'voucher_no': VchNo,
                'voucher_type': VTYPE,
                'is_migrated':True,
                }
                res = self.env['sync.logs'].create(vals)
                
            self.createAccountVoucherLine( dic, com, vid, VTYPE)
        
        return True

    def insertVoucherData(self,  com, tallyData):

        a = tallyData['BODY']['IMPORTDATA']['REQUESTDATA']

        if a.get('TALLYMESSAGE'):
            l = len(a['TALLYMESSAGE'])
            dic = {}
            #If there is no records in tally.        
            if l<=0:
                pass

            #If there is only one record in tally.        
            elif l<2:  #for single record [TALLYMESSAGE] is dictionary.
                k = list(tallyData.get("BODY").get("IMPORTDATA").get("REQUESTDATA").get("TALLYMESSAGE").keys())
                k1 = tallyData.get("BODY").get("IMPORTDATA").get("REQUESTDATA").get("TALLYMESSAGE")['VOUCHER']
                dic = k1
                
#                 k = a['TALLYMESSAGE'].keys()
# DIC                print("k====",k[0],dic)
#                 dic = a['TALLYMESSAGE'][k]
                if (k[0] == 'VOUCHER'):
                    self.insertVouchers(dic ,com)

            #If there are multiple records in tally.    
            else:    #for multiple records [TALLYMESSAGE] is list of dictionaries.
                for i in a['TALLYMESSAGE']:
                    for k , k1 in i.items():
                        dic = k1
                        if (k=='VOUCHER'):
                            self.insertVouchers( dic ,com)

        return True

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
