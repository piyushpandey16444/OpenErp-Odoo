from odoo import api, fields, models, _
import http.client
from odoo.exceptions import UserError


def make_connection(self, url="localhost:9000"):
    print ('ENTRY__________')
    try:
        conn = http.client.HTTPConnection(url)
        print ('Connection====--',conn)
    except Exception:
        raise UserError(_('Error Occured While Connecting With Tally.'))
    return conn
