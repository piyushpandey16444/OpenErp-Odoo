from psycopg2 import IntegrityError
from odoo import api, exceptions, fields, models, _
from odoo.exceptions import UserError
import string
from . import migrator
from . import voucher
from datetime import datetime

class PartnerLedgers(models.Model):
        
    @api.multi
    def insertLedgers(self,  dic):
        print('Insert Partner Ledger Entry=======',list(dic.keys()))
        print("DIC VAl-------------",dic)
        if 'ISSIMPLEUNIT' in list(dic.keys()) and dic['ISSIMPLEUNIT'] == 'No':
            return {}
        
        rounding = 1.0
        if 'DECIMALPLACES' in list(dic.keys()) and dic['DECIMALPLACES'] != '0':
            rounding =  1 / ( pow(10,float(dic['DECIMALPLACES'])) )
            print('rounding=====',rounding)

        data = {'name':dic['VOUCHERTYPENAME'], 'customer':True , 'supplier':1.0}
        partnerObj = self.env["res.partner"]
        sid = partnerObj.search([('name','=',dic['VOUCHERTYPENAME'])])
        if sid:
            print("SID VALUE@@@@@",sid)
            partnerObj.write( data)
        else:
            return partnerObj.create(data)
        
        
        