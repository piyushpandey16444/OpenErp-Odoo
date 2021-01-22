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

#from openerp# import pooler
import sys
from odoo import api, exceptions, fields, models, _
from . import stock
from . import ledgers
import json

class migrator(models.Model):
    
#     def getPoolObj(self, cr):
#         return pooler.get_pool(cr.dbname)

    def getAccountObj(self):
        account = self.env['account.account']
        acc_type = self.env['account.account.type']
        return account, acc_type

    def getStockObj(self, pool):
        uom = pool.get('product.uom')
        prod = pool.get('product.product')
        prodCat = pool.get('product.category')
        currency = pool.get('res.currency')
        return uom, prod, prodCat, currency

    def getStockLocationObj(self, pool):
        return pool.get('stock.location')
    
    def getEmployeeObj(self,pool):
        return pool.get('hr.employee')

    def insertData(self,com, tallyData):
        print("Inserted in INSERT DATA====================")
        a = tallyData
        print('Tally Data@@@@@@@@@@',tallyData)
        account = self.env['account.account']
        acc_type = self.env['account.account.type']
        prodCatObj = self.env['product.category']
        uomObj = self.env['product.uom']
        prodObj = self.env['product.product']
        godownObj = self.env['stock.location']


        print("tallyu dayataaaaaaaaaaaaaa", tallyData)
        
#         print(json.dumps(tallyData, indent=4, sort_keys=True))
#         print(tallyData.get("BODY").get("IMPORTDATA").get("REQUESTDATA").get("TALLYMESSAGE"))
        
        
        if tallyData.get("BODY").get("IMPORTDATA").get("REQUESTDATA").get("TALLYMESSAGE"):
            l = len(tallyData.get("BODY").get("IMPORTDATA").get("REQUESTDATA").get("TALLYMESSAGE"))
            print('L value=========',l)
            
            dic = {}
        
            if l<=0:
                pass
            
            elif l<2:  #for single record [TALLYMESSAGE] is dictionary.
                k = list(tallyData.get("BODY").get("IMPORTDATA").get("REQUESTDATA").get("TALLYMESSAGE").keys())

#~~                 k1 = tallyData.get("BODY").get("IMPORTDATA").get("REQUESTDATA").get("TALLYMESSAGE")['UNIT']
                print('K Value============',k)
#~                 dic = k1
                if (k=='GROUP' or k=='LEDGER'):
                    if dic.get('NAME') and dic['NAME']:
                        obj_ledgers = self.env['ledgers'].insertRecords(dic,com, account, acc_type)
                elif (k[0]=='UNIT'):
                    print('Pre Entered')
                    k1 = tallyData.get("BODY").get("IMPORTDATA").get("REQUESTDATA").get("TALLYMESSAGE")['UNIT']
                    dic = k1
                    #jatin Changed for extra arguments
                    obj_stock = self.env['stock'].insertUnits(dic)
                    #end jatin

                    #obj_stock.insertUnits(dic)
                elif (k[0]=='STOCKGROUP'):
                    k1 = tallyData.get("BODY").get("IMPORTDATA").get("REQUESTDATA").get("TALLYMESSAGE")['STOCKGROUP']    
                    dic = k1
                    obj_stock = self.env['stock']
                    obj_stock.insertStockGroups(prodCatObj, dic)
                elif (k[0]=='STOCKITEM'):
                    k1 = tallyData.get("BODY").get("IMPORTDATA").get("REQUESTDATA").get("TALLYMESSAGE")['STOCKITEM']
                    dic = k1
                    obj_stock = self.env['stock']
                    obj_stock.insertStockItems( prodObj, uomObj, prodCatObj, dic, com)
                elif (k=='CURRENCY'):
                    obj_stock = self.env['stock']
                    obj_stock.insertCurrencies(currencyObj, dic, com)
                elif (k[0]=='GODOWN'):
                    obj_stock = self.env['stock']
                    k1 = tallyData.get("BODY").get("IMPORTDATA").get("REQUESTDATA").get("TALLYMESSAGE")['GODOWN']
                    dic = k1
                    
                    obj_stock.insertGodowns( godownObj, dic, com)
                elif (k=='COSTCENTRE'):
                    obj_employee = employee.employee()
                    obj_employee.insertEmployees(empObj, dic, com)
                # print('ledger_count==============================================',ledger_count)

            else:    #for multiple records [TALLYMESSAGE] is list of dictionaries.
                for i  in tallyData.get("BODY").get("IMPORTDATA").get("REQUESTDATA").get("TALLYMESSAGE"):
#                     print(i,"++++++++++++++++++++")
                    for k , k2 in i.items():
#                         print('K Multi Valu+++e========',k)
#                         print('K Value============',k)
#                         print('K2 Value========',k2)
                        dic = k2

                        if (k=='GROUP' or k=='LEDGER'):        
                            if dic.get('NAME') and dic['NAME']:
                                obj_ledgers = self.env['ledgers'].insertRecords(dic,com, account, acc_type)
                        elif (k=='UNIT'):
                            print('Multi Entered===========')
                            obj_stock = self.env['stock'].insertUnits(dic)
                            print("k2================================",k2)
    #                         obj_stock.insertUnits(dic)
                        elif (k=='STOCKGROUP'):
                            obj_stock = self.env['stock']
                            obj_stock.insertStockGroups(prodCatObj, dic)
                        elif (k=='STOCKITEM'):
                            obj_stock = self.env['stock']
                            obj_stock.insertStockItems( prodObj, uomObj, prodCatObj, dic,com)
#                         elif (k=='CURRENCY'):
#                             obj_stock = stock.stock()
#                             obj_stock.insertCurrencies(cr, uid, currencyObj, dic, com)
                        elif (k=='GODOWN'):
                            obj_stock = self.env['stock']
                            obj_stock.insertGodowns(godownObj, dic,com)
                        elif (k=='COSTCENTRE'):
                            obj_employee = employee.employee()
                            obj_employee.insertEmployees(cr, uid, empObj, dic, com)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:    

