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
from odoo import api, fields, models, _
from datetime import datetime

total = 0


class stock(models.Model):

    # previous code
    # def insertGodowns(self,  godownObj, dic,com):
    #     print("Inserted In Godowns====")
    #     USAGE = 'view'
    #     godown_id = 0
    #     if dic.get('NAME') and dic['NAME']:
    #         NAME = dic['NAME']
    #     if dic.get('PARENT') and dic['PARENT']:
    #         USAGE = 'internal'
    #         PARENT = dic['PARENT']
    #         domain = [('name','=',PARENT),('company_id','=',com.id)]
    #         parent_id = godownObj.search(domain)
    #         print("parentId& domain==+++",parent_id,domain,dic['PARENT'])
    #         data = {'name':NAME, 'usage':USAGE, 'location_id':parent_id[0].id, 'company_id':com.id}
    #         print("data====",data)
    #         godown_id = godownObj.search([('name','=',NAME),('company_id','=',com.id)])
    #         print("godown_id",godown_id)
    #     else:
    #         godown_id = godownObj.search([('name','=',NAME)])
    #         data = {'name':NAME, 'usage':USAGE, 'company_id':com.id}
    #     print("godown_id===",godown_id)
    #     if godown_id:
    #         syncObj = self.env['sync.logs'].search([('record_name','=',NAME)])
    #         syncObj.write({'is_migrated':True,'log_date': datetime.now()})
    #         godownObj.write(data)
    #     else:
    #         #LOG ENTRY
    #         syncObj = self.env['sync.logs'].search([('record_name','=',NAME)])
    #         if not syncObj:
    #             vals = {
    #             'name': 'STOCK LOCATIONS',
    #             'log_date': datetime.now(),
    #             'total_records': 1,
    #             'record_name' : NAME,
    #             'no_imported' : 1,
    #             'reason' : '',
    #             'is_migrated' : True,
    #             'object' : 'Stock Location',
    #             }
    #             res = self.env['sync.logs'].create(vals)
    #         godown_id = godownObj.create(data)
    #
    #     return True

    def insertGodowns(self, godownObj, dic, com):
        godownObj = self.env['tally.stock.location']
        print("Inserted In Godowns====")
        USAGE = 'view'
        godown_id = 0
        if dic.get('NAME') and dic['NAME']:
            NAME = dic['NAME']

        if dic.get('GUID') and dic['GUID']:
            print("Entered In GUID", dic['GUID'])
            guid = dic['GUID']

        if dic.get('PARENT') and dic['PARENT']:
            USAGE = 'internal'
            PARENT = dic['PARENT']
            domain = [('name', '=', PARENT), ('company_id', '=', com.id)]
            parent_id = godownObj.search(domain)
            print("parentId& domain==+++", parent_id, domain, dic['PARENT'])
            if not parent_id:
                print ("no parent godown")
                data = {'name': NAME, 'usage': USAGE, 'company_id': com.id,
                        'guid': guid}
                print("data====", data)
                godown_id = godownObj.search([('name', '=', NAME), ('company_id', '=', com.id)])
                print("godown_id", godown_id)
            else:
                data = {'name': NAME, 'usage': USAGE, 'location_id': parent_id[0].id, 'company_id': com.id, 'guid': guid}
                print("data====", data)
                godown_id = godownObj.search([('name', '=', NAME), ('company_id', '=', com.id)])
                print("godown_id", godown_id)
        else:
            godown_id = godownObj.search([('name', '=', NAME)])
            data = {'name': NAME, 'usage': USAGE, 'company_id': com.id, 'guid': guid}
        print("godown_id===", godown_id)
        if godown_id:
            syncObj = self.env['sync.logs'].search([('record_name', '=', NAME)])
            syncObj.write({'is_migrated': True, 'log_date': datetime.now()})
            godown_id.write(data)
        else:
            # LOG ENTRY
            syncObj = self.env['sync.logs'].search([('record_name', '=', NAME)])
            if not syncObj:
                vals = {
                    'name': 'STOCK LOCATIONS',
                    'log_date': datetime.now(),
                    'total_records': 1,
                    'record_name': NAME,
                    'no_imported': 1,
                    'reason': '',
                    'is_migrated': True,
                    'object': 'Stock Location',
                }
                res = self.env['sync.logs'].create(vals)
            godown_id = godownObj.create(data)

        return True

    def insertCurrencies(self, cr, uid, currencyObj, dic, com):
        rounding = 1.0
        if dic.has_key('NAME') and dic['NAME']:
            SYMBOL = dic['NAME']
        if dic.has_key('EXPANDEDSYMBOL') and dic['EXPANDEDSYMBOL']:
            NAME = dic['EXPANDEDSYMBOL']
        if dic.has_key('DECIMALPLACES') and dic['DECIMALPLACES'] != '0':
            ROUNDING = 1 / (pow(10, float(dic['DECIMALPLACES'])))

        data = {'name': NAME, 'symbol': SYMBOL, 'rounding': ROUNDING, 'company_id': com.id}
        currency_id = currencyObj.search([('name', '=', NAME), ('company_id', '=', com.id)])
        if currency_id:
            currencyObj.write(data)
        else:
            currencyObj.create(data)
        return True

    # preious code
    # @api.multi
    # def insertUnits(self,  uomObj = False,dic=False):
    #     print('Insert Units Entry=======',list(dic.keys()))
    #     print("DIC VAl-------------",dic)
    #     guid=''
    #     if 'ISSIMPLEUNIT' in list(dic.keys()) and dic['ISSIMPLEUNIT'] == 'No':
    #         return {}
    #
    #     rounding = 1.0
    #     if 'DECIMALPLACES' in list(dic.keys()) and dic['DECIMALPLACES'] != '0':
    #         rounding =  1 / ( pow(10,float(dic['DECIMALPLACES'])) )
    #         print('rounding=====',rounding)
    #
    #     if dic.get('GUID') and dic['GUID']:
    #         print("Entered In GUID", dic['GUID'])
    #         guid = dic['GUID']
    #     print ("GUID for PRODUCT TEMPLATEE",guid)
    #
    #     data = {'name':dic['VOUCHERTYPENAME'], 'category_id':1 , 'factor':1.0 , 'rounding':rounding, 'uom_type':'reference'}
    #     uomObj = self.env["product.uom"]
    #     sid = uomObj.search([('name','=',dic['VOUCHERTYPENAME'])])
    #     if sid:
    #         print("SID VALUE@@@@@",sid)
    #         uomObj.write( data)
    #         syncObj = self.env['sync.logs'].search([('record_name','=',dic['VOUCHERTYPENAME'])])
    #         syncObj.write({'is_migrated':True,'log_date': datetime.now()})
    #     else:
    #         #LOG ENTRY
    #         syncObj = self.env['sync.logs'].search([('record_name','=',dic['VOUCHERTYPENAME'])])
    #         if not syncObj:
    #             vals = {
    #             'name': 'UNITS OF MEASURE',
    #             'log_date': datetime.now(),
    #             'total_records': 1,
    #             'record_name' : dic['VOUCHERTYPENAME'],
    #             'no_imported' : 1,
    #             'reason' : '',
    #             'is_migrated' : True,
    #             'object' : 'Product UOM',
    #             }
    #             res = self.env['sync.logs'].create(vals)
    #         return uomObj.create(data)

    # new Code by shubham
    #Jatin Changed for extra argument
    @api.multi
    def insertUnits(self,dic=False):
        #end jatin
        # print('Insert Units Entry=======', list(dic.keys()))
        print("DIC VAl-------------", dic)
        #print("uom obj==============",uomObj)
        guid = ''
        if dic :
            if 'ISSIMPLEUNIT' in list(dic.keys()) and dic['ISSIMPLEUNIT'] == 'No':
                return {}

            rounding = 1.0
            if 'DECIMALPLACES' in list(dic.keys()) and dic['DECIMALPLACES'] != '0':
                rounding = 1 / (pow(10, float(dic['DECIMALPLACES'])))
                print('rounding=====', rounding)

            if dic.get('GUID') and dic['GUID']:
                print("Entered In GUID", dic['GUID'])
                guid = dic['GUID']
            print("GUID for PRODUCT TEMPLATEE", guid)

            data = {'name': dic['VOUCHERTYPENAME'], 'category_id': 1, 'factor': 1.0, 'rounding': rounding,
                    'uom_type': 'bigger', 'guid': guid}
            uomObj = self.env["tally.product.uom"]
            #uomObj = self.env["product.uom"]
            sid = uomObj.search([('name', '=', dic['VOUCHERTYPENAME'])])
            if sid:
                print("SID VALUE@@@@@", sid)
                sid.write(data)
                syncObj = self.env['sync.logs'].search([('record_name', '=', dic['VOUCHERTYPENAME'])])
                syncObj.write({'is_migrated': True, 'log_date': datetime.now()})
            else:
                # LOG ENTRY
                syncObj = self.env['sync.logs'].search([('record_name', '=', dic['VOUCHERTYPENAME'])])
                if not syncObj:
                    vals = {
                        'name': 'UNITS OF MEASURE',
                        'log_date': datetime.now(),
                        'total_records': 1,
                        'record_name': dic['VOUCHERTYPENAME'],
                        'no_imported': 1,
                        'reason': '',
                        'is_migrated': True,
                        'object': 'Product UOM',
                    }
                    res = self.env['sync.logs'].create(vals)
                return uomObj.create(data)

    # data was inserted in product.category
    # def insertStockGroups(self, prodCatObj, dic):
    #     guid=''
    #     print("insert stocmk h=group...")
    #     if dic.get('GUID') and dic['GUID']:
    #         print("Entered In GUID", dic['GUID'])
    #         guid = dic['GUID']
    #     print ("GUID for PRODUCT TEMPLATEE",guid)
    #     if dic.get('PARENT') and dic['PARENT']:
    #         pid = prodCatObj.search( [('name','=',dic['PARENT'])])
    #         print("pid=====",pid)
    #     else:
    #         pid = prodCatObj.search([('name','=','All')])
    #         print("pid==-->",pid)
    #     data = {'name': dic['VOUCHERTYPENAME'], 'parent_id':pid[0].id, 'type':'normal','tally_guid':guid}
    #
    #     sid = prodCatObj.search([('name','=',dic['VOUCHERTYPENAME'])])
    #     print("sid=====",sid)
    #     if sid:
    #         prodCatObj.write(data)
    #         syncObj = self.env['sync.logs'].search([('record_name','=',dic['VOUCHERTYPENAME'])])
    #         syncObj.write({'is_migrated':True,'log_date': datetime.now()})
    #     else:
    #         #LOG ENTRY
    #         syncObj = self.env['sync.logs'].search([('record_name','=',dic['VOUCHERTYPENAME'])])
    #         if not syncObj:
    #             vals = {
    #             'name': 'PRODUCT CATEGORIES',
    #             'log_date': datetime.now(),
    #             'total_records': 1,
    #             'record_name' : dic['VOUCHERTYPENAME'],
    #             'no_imported' : 1,
    #             'reason' : '',
    #             'is_migrated' : True,
    #             'object' : 'Product Category',
    #             }
    #             res = self.env['sync.logs'].create(vals)
    #             data['from_tally'] =True
    #
    #         return prodCatObj.create( data)

    # data is inserted in tally_product_category
    def insertStockGroups(self, prodCatObj, dic):
        prodCatObj = self.env['tally.product.category']
        guid = ''
        print("insert stocmk h=group...")
        if dic.get('GUID') and dic['GUID']:
            print("Entered In GUID", dic['GUID'])
            guid = dic['GUID']
        print("GUID for PRODUCT TEMPLATEE", guid)
        if dic.get('PARENT') and dic['PARENT']:
            pid = prodCatObj.search([('name', '=', dic['PARENT'])])
            print("pid=====", pid)
        else:
            pid = prodCatObj.search([('name', '=', 'All')])
            print("pid==-->", pid)
        data = {'name': dic['VOUCHERTYPENAME'], 'type': 'normal', 'tally_guid': guid}

        # sid = prodCatObj.search([('name', '=', dic['VOUCHERTYPENAME'])])
        sid = prodCatObj.search([('tally_guid', '=', guid)])
        print("sid=====", sid)
        if sid:
            sid.write(data)
            syncObj = self.env['sync.logs'].search([('record_name', '=', dic['VOUCHERTYPENAME'])])
            syncObj.write({'is_migrated': True, 'log_date': datetime.now()})
            return sid.write(data)
        else:
            # LOG ENTRY
            syncObj = self.env['sync.logs'].search([('record_name', '=', dic['VOUCHERTYPENAME'])])
            if not syncObj:
                vals = {
                    'name': 'PRODUCT CATEGORIES',
                    'log_date': datetime.now(),
                    'total_records': 1,
                    'record_name': dic['VOUCHERTYPENAME'],
                    'no_imported': 1,
                    'reason': '',
                    'is_migrated': True,
                    'object': 'Product Category',
                }
                res = self.env['sync.logs'].create(vals)
                data['from_tally'] = True

            return prodCatObj.create(data)

    #         insert data in product.product
    # @api.multi
    # def insertStockItems(self,  prodObj, uomObj, prodCatObj, dic, com):
    #     global total
    #     costing_met = 'standard'
    #     std_price = 0.0
    #     guid=False
    #
    #     if dic.get('OPENINGVALUE') and dic['OPENINGVALUE']:
    #         opening_value = dic['OPENINGVALUE']
    #         if float(opening_value) < 0:
    #             opening_value = (float(opening_value) * (-1))
    #         total = total + float(opening_value)
    #
    #
    #     if dic.get('OPENINGRATE') and dic['OPENINGRATE']:
    #         std_price = float(dic['OPENINGRATE'].split('/')[0])
    #
    #     uomID = uomObj.search( [('name','=',dic['BASEUNITS'])])
    #     if not uomID:
    #         uomID = self.insertUnits( uomObj, {'VOUCHERTYPENAME':dic['BASEUNITS']})
    #     else:
    #         uomID = uomID[0]
    #
    #     categID = prodCatObj.search( [('name','=',dic['PARENT'])])
    #     if not categID:
    #         categID = self.insertStockGroups(prodCatObj, {'VOUCHERTYPENAME':dic['PARENT']})
    #     else:
    #         categID = categID[0]
    #
    #     if dic.get('COSTINGMETHOD') and dic['COSTINGMETHOD'] == "Avg. Cost":
    #         costing_met = 'average'
    #
    #     # update guid in product template table by pushkal : 30 jan 19: starts here
    #     if dic.get('GUID') and dic['GUID']:
    #         print("Entered In GUID", dic['GUID'])
    #         guid = dic['GUID']
    #     print ("GUID for PRODUCT TEMPLATEE",guid)
    #     # update guid in product template table by pushkal : 30 jan 19: ends here
    #
    #     #if company is selected then the product will belong to that company.
    #     if com:
    #         print("dic['VOUCHERTYPENAME'-------",dic['VOUCHERTYPENAME'])
    #         data = {'name':dic['VOUCHERTYPENAME'], 'cost_method':costing_met, 'uom_id':uomID.id, 'uom_po_id':uomID.id, 'standard_price':std_price, 'categ_id':categID.id, 'company_id':com.id,'tally_guid': guid}
    #         print("data@@@@@@@",data)
    #     else:
    #         data = {'name':dic['VOUCHERTYPENAME'], 'cost_method':costing_met, 'uom_id':uomID.id, 'uom_po_id':uomID, 'standard_price':std_price, 'categ_id':categID.id,'tally_guid': guid}
    #         print("data====",data)
    #     #if record is already exist then it will updated else new record is created.
    #     sid = prodObj.search([('name','=',dic['VOUCHERTYPENAME']),('company_id','=',com.id)])
    #     print("sid====",sid)
    #
    #     if sid:
    #         prodObj.write(data)
    #         syncObj = self.env['sync.logs'].search([('record_name','=',dic['VOUCHERTYPENAME'])])
    #         syncObj.write({'is_migrated':True,'log_date': datetime.now()})
    #     else:
    #         #LOG ENTRY
    #         syncObj = self.env['sync.logs'].search([('record_name','=',dic['VOUCHERTYPENAME'])])
    #         if not syncObj:
    #             vals = {
    #             'name': 'PRODUCTS',
    #             'log_date': datetime.now(),
    #             'total_records': 1,
    #             'record_name' : dic['VOUCHERTYPENAME'],
    #             'no_imported' : 1,
    #             'reason' : '',
    #             'is_migrated' : True,
    #             'object' : 'Product Template',
    #             }
    #             res = self.env['sync.logs'].create(vals)
    #
    #         return prodObj.create(data)
    # vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

    @api.multi
    def insertStockItems(self, prodObj, uomObj, prodCatObj, dic, com):
        account = self.env['account.account']
        acc_type = self.env['account.account.type']
        prodCatObj = self.env['tally.product.category']
        uomObj = self.env['tally.product.uom']
        prodObj = self.env['tally.product.template']
        godownObj = self.env['tally.stock.location']

        global total
        costing_met = 'standard'
        std_price = 0.0
        guid = False

        if dic.get('OPENINGVALUE') and dic['OPENINGVALUE']:
            opening_value = dic['OPENINGVALUE']
            if float(opening_value) < 0:
                opening_value = (float(opening_value) * (-1))
            total = total + float(opening_value)

        if dic.get('OPENINGRATE') and dic['OPENINGRATE']:
            std_price = float(dic['OPENINGRATE'].split('/')[0])

        uomID = uomObj.search([('name', '=', dic['BASEUNITS'])])
        print ("uom iddddddddddd",uomID,dic['BASEUNITS'])
        if not uomID:
            if dic['BASEUNITS']:
                #Jatin Changed for extra argument passed
                #uomID = self.insertUnits(uomObj, {'VOUCHERTYPENAME': dic['BASEUNITS']})
                uomID = self.insertUnits({'VOUCHERTYPENAME': dic['BASEUNITS']})
                #end jatin
            else :
                uomID=self.env['tally.product.uom'].browse(6)
        else:
            uomID = uomID[0]

        categID = prodCatObj.search([('name', '=', dic['PARENT'])])
        if not categID:
            categID = self.insertStockGroups(prodCatObj, {'VOUCHERTYPENAME': dic['PARENT']})
        else:
            categID = categID[0]

        if dic.get('COSTINGMETHOD') and dic['COSTINGMETHOD'] == "Avg. Cost":
            costing_met = 'average'

        # update guid in product template table by pushkal : 30 jan 19: starts here
        if dic.get('GUID') and dic['GUID']:
            print("Entered In GUID", dic['GUID'])
            guid = dic['GUID']
        print("GUID for PRODUCT TEMPLATEE", guid)
        # update guid in product template table by pushkal : 30 jan 19: ends here

        # if company is selected then the product will belong to that company.
        if com:
            print("dic['VOUCHERTYPENAME'-------", dic['VOUCHERTYPENAME'])
            data = {'name': dic['VOUCHERTYPENAME'], 'cost_method': costing_met, 'uom_id': uomID.id,
                    'uom_po_id': uomID.id,
                    'standard_price': std_price, 'categ_id': categID.id, 'company_id': com.id, 'guid': guid}
            print("data@@@@@@@", data)
        else:
            data = {'name': dic['VOUCHERTYPENAME'], 'cost_method': costing_met, 'uom_id': uomID.id, 'uom_po_id': uomID,
                    'standard_price': std_price, 'categ_id': categID.id, 'guid': guid}
            print("data====", data)
        # if record is already exist then it will updated else new record is created.
        sid = prodObj.search([('name', '=', dic['VOUCHERTYPENAME']), ('company_id', '=', com.id)])
        print("sid====", sid)

        if sid:
            sid.write(data)
            syncObj = self.env['sync.logs'].search([('record_name', '=', dic['VOUCHERTYPENAME'])])
            syncObj.write({'is_migrated': True, 'log_date': datetime.now()})
        else:
            # LOG ENTRY
            syncObj = self.env['sync.logs'].search([('record_name', '=', dic['VOUCHERTYPENAME'])])
            if not syncObj:
                vals = {
                    'name': 'PRODUCTS',
                    'log_date': datetime.now(),
                    'total_records': 1,
                    'record_name': dic['VOUCHERTYPENAME'],
                    'no_imported': 1,
                    'reason': '',
                    'is_migrated': True,
                    'object': 'Product Template',
                }
                res = self.env['sync.logs'].create(vals)

            return prodObj.create(data)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
        
        
        
        
        
