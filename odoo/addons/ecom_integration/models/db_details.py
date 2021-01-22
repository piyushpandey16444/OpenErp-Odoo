from odoo import models, fields, api, _
import requests
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
from slugify import slugify
from passlib.context import CryptContext
import json
from math import ceil

default_crypt_context = CryptContext(

    # kdf which can be verified by the context. The default encryption kdf is
    # the first of the list

    ['pbkdf2_sha512', 'md5_crypt'],

    # deprecated algorithms are still verified as usual, but ``needs_update``
    # will indicate that the stored hash should be replaced by a more recent
    # algorithm. Passlib 1.6 supports an `auto` value which deprecates any
    # algorithm but the default, but Ubuntu LTS only provides 1.5 so far.

    deprecated=['md5_crypt'])


host = "http://hoitymoppet.com" 
port = "7000/" 
app_name = "hoitymoppet" 
url = host + ':' + port + app_name


# def function_for_connection(self):
#     url = ''
#     db_connect = self.env['db.details'].search(['company_id', '=', self.env.user.company_id.id])[0]
#     if db_connect:
#         host = "http://" + db_connect.ip_address
#         port = db_connect.port + '/'
#         app_name = db_connect.application
#         url = host + ':' + port + app_name
#     return url


# Piyush: model for holding data coming from hoitymoppet
class EcomCompany(models.Model):
    _name = "ecom.company"

    associated_company_name = fields.Char(string="Company")
    ref_id = fields.Integer('Ref Id')

    @api.multi
    @api.depends('associated_company_name')
    def name_get(self):
        result = []
        for dt in self:
            name = dt.associated_company_name
            result.append((dt.id, name))
        return result


class EcomCategory(models.Model):
    _name = "ecom.category"

    name = fields.Char(string="Category")
    ref_id = fields.Integer('Ref Id')

    @api.multi
    @api.depends('name')
    def name_get(self):
        result = []
        for dt in self:
            name = dt.name
            result.append((dt.id, name))
        return result
# Piyush: model for holding data coming from hoitymoppet


# Piyush: code for inheriting currency, country, currency rate and state for adding migrate and reference id fields
class ResCountry(models.Model):
    _inherit = "res.country"

    # Fields added for migrating data
    migrate_data = fields.Boolean(string="Migrate", default=False)
    reference_id = fields.Integer(string="Reference Id", readonly=True)


class ResCurrencyRate(models.Model):
    _inherit = "res.currency.rate"

    # Fields added for migrating data
    migrate_data = fields.Boolean(string="Migrate", default=False)
    reference_id = fields.Integer(string="Reference Id", readonly=True)


class ResCurrency(models.Model):
    _inherit = "res.currency"

    # Fields added for migrating data
    migrate_data = fields.Boolean(string="Migrate", default=False)
    reference_id = fields.Integer(string="Reference Id", readonly=True)


class ProductUOMCategory(models.Model):
    _inherit = "product.uom.categ"

    # Fields added for migrating data
    migrate_data = fields.Boolean(string="Migrate", default=False)
    reference_id = fields.Integer(string="Reference Id", readonly=True)

    @api.model
    def create(self, vals):

        # if data is being sent to hoitymoppet then these are mandatory fields
        result = super(ProductUOMCategory, self).create(vals)

        # P:code for updating the pflo id in hoitymoppet in creation of company in pflo
        req_dict = {
            "name": result.name,
            "migrate_data": result.migrate_data or False,
            "reference_id": result.id or '',
            "company_id": self.env.user.company_id.reference_id or None,
        }

        try:
            migrate = result['migrate_data']
            if migrate:
                request = requests.post(url + '/create-productuom-category/',
                                        data=req_dict)

                created_instance_id = request.json()
                print("response", request.json())
                result.reference_id = created_instance_id['id']
        except KeyError:
            raise ValidationError("Response from HoityMoppet : {}".format(next(iter(request.json().values()))))

        return result

    @api.multi
    def write(self, vals):
        result = super(ProductUOMCategory, self).write(vals)

        requested_dict = {
            "name": self.name,
            "migrate_data": self.migrate_data,
            "reference_id": self.id,
            "company_id": self.env.user.company_id.reference_id or None,
        }

        # If not already migrated
        if 'migrate_data' in vals:
            migrate_dt = vals.get('migrate_data')

            # create on click of migrate data as data is not already migrated
            if migrate_dt:
                if not self.reference_id:

                    try:
                        migrate = vals['migrate_data']
                        if migrate:
                            request = requests.post(url + '/create-productuom-category/',
                                                    data=requested_dict)

                            created_instance_id = request.json()
                            print("response", request.json())
                            self.reference_id = created_instance_id['id']
                    except KeyError:
                        raise ValidationError("Response from HoityMoppet : {}".format(next(iter(request.json().values()))))

            else:
                requested_dict['active'] = False
                request = requests.put(
                    url + '/update-productuom-category/' + str(self.reference_id) + '/',
                    data=requested_dict)
                print("response", request.json())

        if self.migrate_data:
            # if data edited with migrated data true
            requests.put(url + '/update-productuom-category/' + str(self.reference_id) + '/',
                         data=requested_dict)

        return result


class ProductUOMInherit(models.Model):
    _inherit = "product.uom"

    # Fields added for migrating data
    migrate_data = fields.Boolean(string="Migrate", default=False)
    reference_id = fields.Integer(string="Reference Id", readonly=True)

    @api.model
    def create(self, vals):

        # if data is being sent to hoitymoppet then these are mandatory fields
        result = super(ProductUOMInherit, self).create(vals)

        status = result.active
        if result.active:
            status = 'active'
        else:
            status = 'inactive'

        # P:code for updating the pflo id in hoitymoppet in creation of company in pflo
        req_dict = {
            "name": result.name,
            "migrate_data": result.migrate_data or False,
            "reference_id": result.id or '',
            "status": status,
            "rounding": result.rounding,
            "company_id": self.env.user.company_id.reference_id or None,
        }

        try:
            migrate = result['migrate_data']
            if migrate:
                request = requests.post(url + '/create-product-uom/',
                                        data=req_dict)

                created_instance_id = request.json()
                print("response", request.json())
                result.reference_id = created_instance_id['id']
        except KeyError:
            raise ValidationError("Response from HoityMoppet : {}".format(next(iter(request.json().values()))))

        return result

    @api.multi
    def write(self, vals):
        result = super(ProductUOMInherit, self).write(vals)

        status = self.active
        if self.active:
            status = 'active'
        else:
            status = 'inactive'

        requested_dict = {
            "name": self.name,
            "migrate_data": self.migrate_data or False,
            "reference_id": self.id or '',
            "status": status or 'active',
            "rounding": self.rounding,
            "company_id": self.env.user.company_id.reference_id or None,
        }

        # If not already migrated
        if 'migrate_data' in vals:
            migrate_dt = vals.get('migrate_data')

            # create on click of migrate data as data is not already migrated
            if migrate_dt:
                if not self.reference_id:

                    try:
                        migrate = vals['migrate_data']
                        if migrate:
                            request = requests.post(url + '/create-product-uom/',
                                                    data=requested_dict)

                            created_instance_id = request.json()
                            print("response", request.json())
                            self.reference_id = created_instance_id['id']
                    except KeyError:
                        raise ValidationError("Response from HoityMoppet : {}".format(next(iter(request.json().values()))))

            else:
                requested_dict['active'] = False
                request = requests.put(
                    url + '/update-productuom/' + str(self.reference_id) + '/',
                    data=requested_dict)
                print("response", request.json())

        if self.migrate_data:
            # if data edited with migrated data true
            requests.put(url + '/update-productuom/' + str(self.reference_id) + '/',
                         data=requested_dict)

        return result


# code ends here


class ResCountryState(models.Model):
    _inherit = "res.country.state"

    # Fields added for migrating data
    migrate_data = fields.Boolean(string="Migrate", default=False)
    reference_id = fields.Integer(string="Reference Id", readonly=True)
# Piyush: code for inheriting currency,country,currency rate,state for adding migrate and reference id fields ends here


# Piyush: code for inheriting database details model
class DatabaseDetails(models.Model):
    _name = "db.details"
    _description = "Database Details based on company"

    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.user.company_id)
    db_name = fields.Char(string='Database Name')
    port = fields.Integer(string='Port')
    ip_address = fields.Char(string='IP Address')
    username = fields.Char(string='Username')
    password = fields.Char(string='Password')
    password_hashed = fields.Char(string='Password Hashed')
    application = fields.Selection([('hoitymoppet', 'Hoitymoppet'), ('pflo_lite', 'Pflo Lite')], 'Application',
                                   default='hoitymoppet')
    migration_required = fields.Boolean(string="Migrate", default=False)
    migrate_data = fields.Boolean(string="Migrate Data", default=False)

    @api.model
    def create(self, vals):
        """
        create function which will run only once for a particular company. It will return validation error while
        creating infomation for next row of same company.
        :param vals: **datadict
        """
        check_existing_data = self.env['db.details'].search([('company_id', '=', self.env.user.company_id.id)])
        if check_existing_data:
            raise UserError("Data already exist, cannot create new. Please edit that.")
        result = super(DatabaseDetails, self).create(vals)
        return result

    def fetch_all_data(self):

        ids_list_category = []
        ids_list_company = []
        ecom_obj_cat = self.env['ecom.category'].search([])

        for ids in ecom_obj_cat:
            ids_list_category.append(ids.ref_id)

        # for getting category data
        request_cat = requests.get(url + '/category-list/', timeout=2.50)
        req_data = request_cat.content
        changed_data = json.loads(req_data.decode('utf-8'))

        for dt in changed_data:
            req_id = dt.get('id')
            req_name = dt.get('category')

            if req_id not in ids_list_category:
                data = {"name": req_name, "ref_id": req_id}
                ecom_obj_cat.create(data)

        # for getting company data
        ecom_obj_comp = self.env['ecom.company'].search([])

        for comp in ecom_obj_comp:
            ids_list_company.append(comp.ref_id)

        request = requests.get(url + '/company-list/', timeout=2.50)
        req_data = request.content
        changed_data = json.loads(req_data.decode('utf-8'))

        for x in changed_data:
            req_id = x.get('id')
            req_name = x.get('associated_company_name')
            if req_id not in ids_list_company:
                data = {"associated_company_name": req_name, "ref_id": req_id}
                ecom_obj_comp.create(data)

    def migrate_all_data(self):
        """
        Migrate all data for country, currency and currency rate, product uom models to HM.
        on click of the button this function loops into all the models and call create api for that models in HM
        adding reference_id of the generated instance and making migrate tp True for all the records.
        """
        check_migrated_currency = self.env['res.currency'].search([('migrate_data', '=', False)])
        if check_migrated_currency:
            # migration of currency
            currency_list = self.env['res.currency'].search([])

            if currency_list:
                for currency in currency_list:
                    currency_dict = {
                        "name": currency.name or '',
                        "symbol": currency.symbol or '',
                        "rounding": currency.rounding or '',
                        "status": 'active',
                        "position": currency.position or 'after',
                        "currency_unit_label": currency.currency_unit_label or '',
                        "currency_subunit_label": currency.currency_subunit_label or '',
                        "create_uid": self.env.user.reference_id or 1,
                        "migrate_data": True,
                        "reference_id": currency.id or False,
                        "company_id": self.env.user.company_id.reference_id or None,
                    }
                    # create api for migrating data from here to hoitymoppet
                    request = requests.post(url + '/create-currency/',
                                            data=currency_dict)
                    created_currency_id = request.json()
                    print("response_currency", request.json())
                    currency.reference_id = created_currency_id['id']
                    currency.migrate_data = True
                    # code ends here
        check_migrated_rate = self.env['res.currency.rate'].search([('migrate_data', '=', True)])
        if not check_migrated_rate:
            # migration of currency_rate
            currency_rate_dict = {}
            currency_rate_list = self.env['res.currency.rate'].search([])
            if currency_rate_list:
                for currency_rate in currency_rate_list:
                    # taking reference of currency and company
                    currency_ref = self.env['res.currency'].search(
                        [('id', '=', currency_rate.currency_id.id)]).reference_id or ''
                    company_ref = self.env['res.company'].search(
                        [('id', '=', currency_rate.company_id.id)]).reference_id or ''

                    currency_rate_dict = {
                        "name": currency_rate.name or '',
                        "rate": currency_rate.rate or '',
                        "currency_id": currency_ref or '',
                        "company_id": company_ref or '',
                        "create_uid": self.env.user.reference_id or 1,
                        "migrate_data": True,
                        "reference_id": currency_rate.id or False,
                    }
                    # create api for migrating data from here to hoitymoppet
                    request = requests.post(url + '/create-currency-rate/',
                                            data=currency_rate_dict)
                    created_currency_rate_id = request.json()
                    print("response_rate", request.json())
                    currency_rate.reference_id = created_currency_rate_id['id']
                    currency_rate.migrate_data = True
        check_migrated_country = self.env['res.country'].search([('migrate_data', '=', True)])
        if not check_migrated_country:
            # migration of countries
            countries = self.env['res.country'].search([])
            if countries:
                for country_data in countries:
                    # taking reference of currency and company
                    currency_ref = self.env['res.currency'].search(
                        [('id', '=', country_data.currency_id.id)]).reference_id or ''
                    country_dict = {
                        "name": country_data.name or '',
                        "code": country_data.code or '',
                        "address_format": country_data.address_format or '',
                        "address_view_id": country_data.address_view_id or 1,
                        "currency_id": currency_ref or None,
                        "phone_code": country_data.phone_code or '',
                        "create_uid": self.env.user.reference_id or 1,
                        "name_position": country_data.name_position or '',
                        "reference_id": country_data.id,
                        "migrate_data": True,
                        "company_id": self.env.user.company_id.reference_id or None,
                    }

                    # create api for migrating data from here to hoitymoppet
                    request = requests.post(url + '/create-country/',
                                            data=country_dict)

                    created_country_id = request.json()
                    print("response_country", request.json())
                    country_data.reference_id = created_country_id['id']
                    country_data.migrate_data = True
        # check_migrated_state = self.env['res.country.state'].search([])
        # if not check_migrated_state:
        if True:
            # migration of states
            state_list = self.env['res.country.state'].search([('country_id', '=', 104)])
            if state_list:
                for state in state_list:
                    # taking reference of country id
                    country_ref = self.env['res.country'].search([('id', '=', state.country_id.id)]).reference_id or ''

                    state_dict = {
                        "name": state.name,
                        "code": state.code or '',
                        "country_id": country_ref or '',
                        "create_uid": self.env.user.reference_id or 1,
                        "reference_id": state.id,
                        "migrate_data": True,
                        "company_id": self.env.user.company_id.reference_id or None,
                    }
                    # create api for migrating data from here to hoitymoppet
                    request = requests.post(url + '/create-state/',
                                            data=state_dict)

                    created_state_id = request.json()
                    print("response_state", request.json())
                    state.reference_id = created_state_id['id']
                    state.migrate_data = True
        check_migrated_product_uom = self.env['product.uom'].search([('migrate_data', '=', True)])
        if not check_migrated_product_uom:
            # migration of product uom
            product_uom_list = self.env['product.uom'].search([])
            if product_uom_list:
                for product_uom in product_uom_list:
                    company_ref = self.env['res.country'].search([('id', '=', product_uom.company_id.id)])
                    # comp_req = company_ref.reference_id if company_ref.reference_id else None
                    comp_req = 1
                    status = 'active' if product_uom.active else 'inactive'
                    product_uom_dict = {
                        "name": product_uom.name or '',
                        "rounding": product_uom.rounding or 0.0,
                        "company_id": comp_req,
                        "reference_id": product_uom.id,
                        "migrate_data": True,
                        "status": status or 'active',
                    }
                    # create api for migrating data from here to hoitymoppet
                    request = requests.post(url + '/create-product-uom/',
                                            data=product_uom_dict)

                    created_instance_id = request.json()
                    print("response_product_uom", request.json())
                    product_uom.reference_id = created_instance_id['id']
                    product_uom.migrate_data = True
        else:
            raise ValidationError("Country, State, Currency, Currency Rate and product uom are migrated already!")
        # code ends here

    @api.onchange('application')
    def onchange_application_details(self):
        for rec in self:
            migration_req = False
            if rec.application and rec.application == 'hoitymoppet':
                migration_req = True
            rec.migration_required = migration_req

# Piyush: code for inheriting database details model ends here


# Piyush: code for inheriting company model
class ResCompany(models.Model):
    _inherit = "res.company"

    # Fields added for migrating data
    migrate_data = fields.Boolean(string="Migrate", default=False)
    reference_id = fields.Integer(string="Reference Id", readonly=True)
    ecom_company = fields.Many2one('ecom.company', string="Ecom Company")

    @api.onchange('ecom_company')
    def onchange_ecom_company(self):
        make_ids = []
        ref = self.env['res.company'].search([])
        if ref:
            for refc_id in ref:
                make_ids.append(refc_id.reference_id)
        dom_rec = []
        check = self.env['ecom.company'].search([])
        for ag in check:
            if ag.ref_id not in make_ids:
                dom_rec.append(ag.id)
        return {'domain': {'ecom_company': [('id', '=', dom_rec)]}}

    @api.model
    def create(self, vals):

        # if data is being sent to hoitymoppet then these are mandatory fields
        if 'migrate_data' in vals:
            migrate = vals.get('migrate_data')
            logo = vals.get('logo')
            website = vals.get('website')
            if migrate and (not logo or not website):
                raise ValidationError(_("Please provide both website and logo !"))  # website fields

        result = super(ResCompany, self).create(vals)

        country_data = result.state_id
        state_data = result.state_id
        currency_data = result.currency_id

        required_dict = {
            "associated_company_name": result.name,
            "associated_company_url": result.website,
            "street": result.street or '',
            "street2": result.street2 or '',
            "zip": result.zip or '',
            "city": result.city or '',
            "company_logo": result.logo,
            "email": result.email or '',
            "phone": result.phone or '',
            "migrate_data": True,
            "reference_id": result.id or '',
            "company_id": self.env.user.company_id.reference_id or None,
            "currency_id": result.currency_id.reference_id or None,
        }

        try:
            ecom_comp = False
            if 'ecom_company' in vals:
                ecom_comp = vals.get('ecom_company')
            if result.migrate_data and not ecom_comp:
                # P:code for updating the pflo id in hoitymoppet in creation of company in pflo
                request = requests.post(url + '/create-company/',
                                        data=required_dict)

                created_company_id = request.json()
                print("response", request.json())
                result.reference_id = created_company_id['id']

        except KeyError:
            raise ValidationError("Response from HoityMoppet : {}".format(next(iter(request.json().values()))))

        company_to_map = False
        if 'ecom_company' in vals:
            company_to_map = vals.get('ecom_company')
        if result.migrate_data and company_to_map:
            id_obtained = self.env['ecom.company'].search([('id', '=', company_to_map)]).ref_id

            if id_obtained:
                request = requests.put(url + '/update-company/' + str(id_obtained) + '/',
                                       data=required_dict)
                created_instance = request.json()
                print("response", request.json())
                result.reference_id = created_instance['id']
        return result

    @api.multi
    def write(self, vals):

        # if data is being sent to hoitymoppet then these are mandatory fields
        if 'migrate_data' in vals:
            migrate = vals.get('migrate_data')
            logo = vals.get('logo') or self.logo
            website = vals.get('website') or self.website
            if migrate:
                if not logo or not website:
                    raise ValidationError("Please provide both website and logo !")  # verify fields
            else:
                raise UserError("Company can not be deleted ! ")
                # delete the item if already created!

        result = super(ResCompany, self).write(vals)

        requested_dict = {
            "associated_company_name": self.name,
            "associated_company_url": self.website or '',
            "street": self.street or '',
            "street2": self.street2 or '',
            "zip": self.zip or '',
            "city": self.city or '',
            "company_logo": self.logo or '',
            "email": self.email or '',
            "phone": self.phone or '',
            "migrate_data": True,
            "reference_id": self.id or '',
            "company_id": self.env.user.company_id.reference_id or None,
            "currency_id": self.currency_id.reference_id or None,
        }

        # If not already migrated
        if 'migrate_data' in vals:
            migrate_dt = vals.get('migrate_data')

            # create on click of migrate data as data is not already migrated
            ecom_comp = False
            if 'ecom_company' in vals:
                ecom_comp = vals.get('ecom_company')
            if migrate_dt and not ecom_comp:
                if not self.reference_id:

                    try:
                        migrate = vals['migrate_data']
                        if migrate:
                            request = requests.post(url + '/create-company/',
                                                    data=requested_dict)

                            created_instruction_id = request.json()
                            print("response", request.json())
                            self.reference_id = created_instruction_id['id']
                    except KeyError:
                        raise ValidationError("Response from HoityMoppet : {}".format(next(iter(request.json().values()))))

            elif migrate_dt and ecom_comp:
                id_obtained = self.env['ecom.company'].search([('id', '=', ecom_comp)]).ref_id

                if id_obtained:
                    request = requests.put(
                        url + '/update-company/' + str(id_obtained) + '/',
                        data=requested_dict)
                    created_instance = request.json()
                    print("response", request.json())
                    self.reference_id = created_instance['id']

        if self.migrate_data:

            # if removing website or logo
            if not self.logo or not self.website:
                raise ValidationError("Please provide both website and logo !")  # verify fields

            # if data edited with migrated data true
            else:
                requests.put(url + '/update-company/' + str(self.reference_id) + '/',
                             data=requested_dict)

        return result
# Piyush: code for inheriting company model ends here


# Piyush: code for inheriting product category model
class ProductCategory(models.Model):
    _inherit = "product.category"

    image = fields.Binary(string="Image", attachment=True)
    migrate_data = fields.Boolean(string="Migrate", default=False)
    reference_id = fields.Integer(string="Reference Id", readonly=False)
    ecom_category = fields.Many2one('ecom.category', string="Ecom Category")
    invisible_flag = fields.Boolean(string="Hide Category", default=False)

    @api.model
    def create(self, vals):

        migrate = vals.get('migrate_data')
        if migrate:  # check for parent category, company, image if data is to be migrated

            # Company and category check if provided while migrations
            if 'company_id' in vals:
                company = vals.get('company_id') or False
                if company:
                    migrated_company = self.env['res.company'].search([('id', '=', company)])
                    if not migrated_company.reference_id:
                        raise ValidationError("This company is not created in Hoitymoppet !")

            if 'parent_id' in vals or 'image' in vals:
                parent = vals.get('parent_id') or False
                cat_image = vals.get('image') or False

                if parent:
                    migrated_category = self.env['product.category'].search([('id', '=', parent)])
                    if not migrated_category.reference_id:
                        raise ValidationError("This category is not created in Hoitymoppet !")

                if not cat_image:
                    raise ValidationError("Please provide image to the category!")

        result = super(ProductCategory, self).create(vals)

        # P:code for updating the pflo id in hoitymoppet in creation of company in pflo
        req_dict = {
            "category": result.name,
            "category_image": result.image or None,
            "status": "active",  # default for now
            "parent_category": result.parent_id.reference_id or None,
            "associated_company": result.company_id.reference_id or 1,  # default 1 for now
            "migrate_data": result.migrate_data or True,
            "reference_id": result.id,
            "invisible": result.invisible_flag or False,
        }

        try:
            ecom_category = False
            if 'ecom_category' in vals:
                ecom_category = vals.get('ecom_category')
            if result.migrate_data and not ecom_category:
                request = requests.post(url + '/create-category/',
                                        data=req_dict)

                created_category_id = request.json()
                print("response", request.json())
                result.reference_id = created_category_id['id']

        except KeyError:
            raise ValidationError("Response from HoityMoppet : {}".format(next(iter(request.json().values()))))

        ecom_category_to_map = False
        if 'ecom_category' in vals:
            ecom_category_to_map = vals.get('ecom_category')
        if result.migrate_data and ecom_category_to_map:
            id_obtained = self.env['ecom.category'].search([('id', '=', ecom_category_to_map)]).ref_id

            if id_obtained:
                request = requests.put(url + '/update-category/' + str(id_obtained) + '/',
                                       data=req_dict)
                created_instance = request.json()
                print("response", request.json())
                result.reference_id = created_instance['id']

        return result

    @api.multi
    def write(self, vals):

        # if data is being sent to hoitymoppet then these are mandatory fields
        if 'migrate_data' in vals:
            migrate = vals.get('migrate_data')
            image = vals.get('image') or self.image or False
            parent = vals.get('parent_id') or self.parent_id or False

            if migrate:

                if not image:
                    raise ValidationError("Please provide image for the category !")  # verify fields

                # Company and category check if provided while migrations
                if 'parent_id' in vals or 'company_id' in vals:
                    category = vals.get('parent_id') or False
                    company = vals.get('company_id') or False

                    if company:
                        migrated_company = self.env['res.company'].search([('id', '=', company)])
                        if not migrated_company.reference_id:
                            raise ValidationError("This company is not created in Hoitymoppet !")

                    if category:
                        migrated_category = self.env['product.category'].search([('id', '=', category)])
                        if not migrated_category.reference_id:
                            raise ValidationError("This category is not created in Hoitymoppet !")

        result = super(ProductCategory, self).write(vals)

        req_dict = {
            "category": self.name,
            "category_image": self.image or None,
            "status": "active",  # default for now
            "parent_category": self.parent_id.reference_id or None,  # default 1 for now
            "associated_company": self.company_id.reference_id or 1,
            "migrate_data": self.migrate_data or True,
            "reference_id": self.id,
            "company_id": self.env.user.company_id.reference_id or None,
            "invisible": self.invisible_flag or False,
        }

        # If not already migrated
        if 'migrate_data' in vals:
            migrate_dt = vals.get('migrate_data')

            # create on click of migrate data as data is not already migrated
            ecom_cat = False
            if 'ecom_category' in vals:
                ecom_comp = vals.get('ecom_category')
            if migrate_dt and not ecom_cat:
                if not self.reference_id:

                    try:
                        # verify fields before creation

                        # check for category image
                        if not self.image:
                            raise ValidationError("Please provide category image !")

                        if not self.company_id.reference_id:
                            raise ValidationError("This company is not created in Hoitymoppet !")  # verify fields

                        if self.parent_id and not self.parent_id.reference_id:
                            raise ValidationError("This category is not created in Hoitymoppet !")  # verify fields

                        request = requests.post(url + '/create-category/',
                                                data=req_dict)

                        created_category_id = request.json()
                        print("response", request.json())
                        self.reference_id = created_category_id['id']
                    except KeyError:
                        raise ValidationError("Response from HoityMoppet : {}".format(next(iter(request.json().values()))))

            elif migrate_dt and ecom_cat:
                id_obtained = self.env['ecom.category'].search([('id', '=', ecom_cat)]).ref_id
                if id_obtained:
                    request = requests.put(
                        url + '/update-company/' + str(id_obtained) + '/',
                        data=req_dict)
                    created_instance = request.json()
                    print("response", request.json())
                    self.reference_id = created_instance['id']

            elif not migrate_dt:
                req_dict['status'] = 'inactive'
                request = requests.put(
                    url + '/update-category/' + str(self.reference_id) + '/',
                    data=req_dict)
                created_instance = request.json()
                print("response", request.json())
                self.reference_id = created_instance['id']

        if self.migrate_data:
            # if removing image
            if not self.image:
                raise ValidationError("Please provide category image !")  # verify fields

            if not self.company_id.reference_id:
                raise ValidationError("This company is not created in Hoitymoppet !")  # verify fields

            if self.parent_id and not self.parent_id.reference_id:
                raise ValidationError("This category is not created in Hoitymoppet !")  # verify fields

            # if data edited with migrated data true
            else:
                requests.put(url + '/update-category/' + str(self.reference_id) + '/',
                             data=req_dict)

        return result
# Piyush: code for category creation ends here


# Piyush: code for user creation
class ResUsers(models.Model):
    _inherit = "res.users"

    migrate_data = fields.Boolean(string="Migrate", default=False)
    reference_id = fields.Integer(string="Reference Id", readonly=True,
                                  help="Unique token id of the user created in django")

    def migration_company_check(self, main_comp_check):
        if main_comp_check:
            migrated_company = self.env['res.company'].search([('id', '=', main_comp_check)])
            if not migrated_company.reference_id:
                raise ValidationError(
                    "{} is not created in Hoitymoppet !".format(migrated_company.name))

    @api.model
    def create(self, vals):

        migrate = vals.get('migrate_data')
        if migrate:  # check for company_id, company_ids if data is to be migrated

            # Company and category check if provided while migrations
            if 'company_id' in vals:
                company = vals.get('company_id') or False
                if company:
                    self.migration_company_check(main_comp_check=company)

            # allowed companies check
            if 'company_ids' in vals:
                company_all = vals.get('company_ids') or False
                for company_req in company_all:
                    for main_comp_check in company_req[2]:
                        if main_comp_check:
                            self.migration_company_check(main_comp_check=main_comp_check)

        result = super(ResUsers, self).create(vals)

        try:
            if result.migrate_data:
                # P:code for updating the pflo id in hoitymoppet in creation of company in pflo
                req_dict = {
                    "username": result.login or '',
                    "password": "New@Password" or False,
                    "email": result.login,
                    "default_company": result.company_id.reference_id or 1,
                    "associated_company": [cmp_id.reference_id for cmp_id in result.company_ids] or [1, 2],
                    "is_active": result.active or 'active',
                    "first_name": result.name or '',
                    "last_name": result.name or '',
                    "is_superuser": True,
                    "is_staff": True,
                    "migrate_data": result.migrate_data,
                    "reference_id": result.id or '',
                }

                request = requests.post(url + '/create-user/',
                                        data=req_dict)

                created_user_id = request.json()
                print("response", request.json())
                result.reference_id = created_user_id['id']

        except KeyError:
            raise ValidationError("Response from HoityMoppet : {}".format(next(iter(request.json().values()))))

        return result

    @api.multi
    def write(self, vals):

        # if data is being sent to hoitymoppet then these are mandatory fields
        if 'migrate_data' in vals:
            migrate = vals.get('migrate_data')
            if migrate:  # check for company_id, company_ids if data is to be migrated

                # Company and category check if provided while migrations
                if 'company_id' in vals or self.company_id.id:
                    company = vals.get('company_id') or self.company_id.id
                    if company:
                        self.migration_company_check(main_comp_check=company)

                # allowed companies check
                if 'company_ids' in vals:
                    company_all = vals.get('company_ids') or False
                    for company_req in company_all:
                        for main_comp_check in company_req[2]:
                            if main_comp_check:
                                self.migration_company_check(main_comp_check=main_comp_check)

            else:
                raise UserError("User Cannot be deleted ! ")
                # delete the item if already created!

        result = super(ResUsers, self).write(vals)

        req_dict = {
            "username": self.login or '',
            "password": "New@Password",
            "email": self.login,
            "default_company": self.company_id.reference_id,
            "associated_company": [cmp_id.reference_id for cmp_id in self.company_ids],
            "is_active": self.active or 'active',
            "first_name": self.name or '',
            "last_name": self.name or '',
            "is_superuser": True,
            "is_staff": True,
            "migrate_data": self.migrate_data,
            "reference_id": self.id or '',
        }

        # If not already migrated
        if 'migrate_data' in vals:
            migrate_dt = vals.get('migrate_data')

            # create on click of migrate data as data is not already migrated
            if migrate_dt:
                if not self.reference_id:

                    try:
                        # verify fields before creation

                        # check for company
                        self.migration_company_check(main_comp_check=self.company_id.id)
                        for ids in self.company_ids:
                            self.migration_company_check(main_comp_check=ids.id)

                        request = requests.post(url + '/create-user/',
                                                data=req_dict)

                        created_user_id = request.json()
                        print("response", request.json())
                        self.reference_id = created_user_id['id']
                    except KeyError:
                        raise ValidationError("Response from HoityMoppet : {}".format(next(iter(request.json().values()))))

            else:
                raise ValidationError("delete data from hoitymoppet!")

        if self.migrate_data:

            # check for company
            self.migration_company_check(main_comp_check=self.company_id.id)
            for ids in self.company_ids:
                self.migration_company_check(main_comp_check=ids.id)

            # if data edited with migrated data true
            else:
                requests.put(url + '/update-user/' + str(self.reference_id) + '/',
                             data=req_dict)

        return result
        # Piyush: code for User creation ends here
# Piyush: code for inheriting user model ends here


# Piyush: code for inheriting product model
class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.multi
    @api.constrains('sale_ok', 'migrate_data', 'age_ids')
    def _check_age_ids(self):
        if self.migrate_data and self.sale_ok:
            if not self.age_ids:
                raise ValidationError("Please provide age for the product !")

    @api.multi
    @api.constrains('sale_delay', 'migrate_data')
    def mfg_lead_time(self):
        if self.migrate_data and self.sale_delay and self.sale_delay <= 0:
            raise ValidationError("Please provide more than 0 days !")
        elif self.migrate_data and not self.sale_delay:
            raise ValidationError("Please provide Manufacturing Lead Time")

    # Piyush: code for adding fields realated to ecom integration in product tabs
    product_fabric_id = fields.Many2one("product.fabric", string="Fabric")
    care_instruction_id = fields.Many2one("care.instruction", string="Care Instruction")
    age_ids = fields.Many2many("age", string="Age")
    color_ids = fields.Many2many("color", string="Color")
    migrate_data = fields.Boolean(string="Migrate", default=False)
    reference_id = fields.Integer(string="Reference Id", readonly=True)
    discount_price = fields.Float(string="Discount")
    category_ids = fields.Many2many('product.category', string="Multi Categories")
    image_ids = fields.One2many('multiple.images', 'product_id', string="Image")
    relative_product = fields.Many2one('product.product', string='Relative Product', )
    related_product = fields.Many2many('product.product', string='Related Product')
    related_products = fields.Many2many('product.product', string='Related Products')
    mrp_data = fields.Float("Mrp", compute="get_mrp_data")
    mrp_discounted_data = fields.Float("Mrp Discounted", compute="get_mrp_discounted_data")
    shipping_charge = fields.Float(string="Shipping Charge")
    ecommerce_check = fields.Boolean(string="Ecommerce Check", default=False)

    def calculate_taxed_mrp(self, price=None):
        for rec in self:
            required_mrp = 0.0
            rate_for_computing = 0.0
            if rec.customer_tax_lines:
                for tax in rec.customer_tax_lines:
                    obtain_tax = self.env['account.tax'].search([('id', '=', tax.tax_id.id)])
                    if obtain_tax.type_tax_use == 'sale' and obtain_tax.tax_group_id.id == 4:
                        rate_for_computing = obtain_tax.amount or 0.0
            if price and price > 0 and rate_for_computing > 0:
                required_mrp = price + (price * rate_for_computing / 100)
            return round(required_mrp)

    @api.multi
    def get_mrp_data(self):
        for rec in self:
            if rec.list_price:
                rec.mrp_data = self.calculate_taxed_mrp(price=rec.list_price)

    @api.multi
    def get_mrp_discounted_data(self):
        for rec in self:
            if rec.discount_price:
                rec.mrp_discounted_data = self.calculate_taxed_mrp(price=rec.discount_price)

    # Piyush:code for defining onchange function of discount_price < sales price
    @api.onchange('discount_price', 'list_price')
    def onchange_discount_price(self):
        for rec in self:
            if rec.list_price and rec.discount_price and rec.discount_price >= rec.list_price:
                raise ValidationError("Price after discount should not be greater than or equal to Sales Price!")
            elif rec.discount_price and not rec.list_price:
                raise ValidationError("Please provide the sales price. ")
            rec.mrp_discounted_data = self.calculate_taxed_mrp(price=rec.discount_price)
            rec.mrp_data = self.calculate_taxed_mrp(price=rec.list_price)

    # Piyush:code for defining onchange function of migrate_data
    @api.onchange('migrate_data')
    def onchange_migrate_data(self):
        if self.migrate_data:
            self.type = 'product'

    # checks for below function
    def check_migrated(self, company_id=None, care_instruction=None, category=None, fabric=None):
        if company_id:
            migrated_company = self.env['res.company'].search([('id', '=', company_id)])
            if migrated_company:
                if not migrated_company.reference_id:
                    raise ValidationError(_("{} is not created in Hoitymoppet !".format(migrated_company.name)))

        if care_instruction:
            migrated_care = self.env['care.instruction'].search([('id', '=', care_instruction)])
            if migrated_care:
                if not migrated_care.reference_id:
                    raise ValidationError(_("{} is not created in Hoitymoppet !".format(migrated_care.name)))

        if category:
            migrated_categ = self.env['product.category'].search([('id', '=', category)])
            if migrated_categ:
                if not migrated_categ.reference_id:
                    raise ValidationError(_("{} category is not created in Hoitymoppet !".format(migrated_categ.name)))

        if fabric:
            migrated_fabric = self.env['product.fabric'].search([('id', '=', fabric)])
            if migrated_fabric:
                if not migrated_fabric.reference_id:
                    raise ValidationError(_("{} is not created in Hoitymoppet !".format(migrated_fabric.name)))

    # check of items created in hoitymoppet or not
    def check_data_to_migrate(self, vals):

        # hsn_id  check
        if 'hsn_id' in vals and not vals.get('hsn_id'):
            raise ValidationError("Please provide HSN Code!")

        # company_check
        if 'company_id' in vals or self.company_id:
            company_id = vals.get('company_id') or self.company_id.id or False
            if company_id:
                self.check_migrated(company_id=company_id)

        # care instruction check
        if 'care_instruction_id' in vals or self.care_instruction_id:
            care_instruction = vals.get('care_instruction_id') or self.care_instruction_id.id or False
            if care_instruction:
                self.check_migrated(care_instruction=care_instruction, company_id=None, category=None, fabric=None)

        # categories check
        if 'categ_id' in vals or self.categ_id:
            category = vals.get('categ_id') or self.categ_id.id or False
            if category:
                self.check_migrated(care_instruction=None, company_id=None, category=category, fabric=None)

        # fabric
        if 'product_fabric_id' in vals or self.product_fabric_id:
            fabric = vals.get('product_fabric_id') or self.product_fabric_id.id or False
            if fabric:
                self.check_migrated(care_instruction=None, company_id=None, category=None, fabric=fabric)

        # color
        if 'color_ids' in vals:
            color_all = vals.get('color_ids') or self.color_ids
            for color_req in color_all:
                for clr in color_req[2]:
                    if clr:
                        migrated_color = self.env['color'].search([('id', '=', clr)])
                        if migrated_color:
                            if not migrated_color.reference_id:
                                raise ValidationError(
                                    _("{} color is not created in Hoitymoppet !".format(migrated_color.name)))

        # age
        if 'age_ids' in vals:
            age_all = vals.get('age_ids') or self.age_ids
            for age_req in age_all:
                for age in age_req[2]:
                    if age:
                        migrated_age = self.env['age'].search([('id', '=', age)])
                        if migrated_age:
                            if not migrated_age.reference_id:
                                raise ValidationError(
                                    _("{} age is not created in Hoitymoppet !".format(migrated_age.name)))

        # multiple categories while creations
        if 'category_ids' in vals:
            category_all = vals.get('category_ids') or self.category_ids
            for category_req in category_all:
                for category in category_req[2]:
                    if category:
                        migrated_categ = self.env['product.category'].search([('id', '=', category)])
                        if migrated_categ:
                            if not migrated_categ.reference_id:
                                raise ValidationError(
                                    _("{} category is not created in Hoitymoppet !".format(migrated_categ.name)))

        # related products
        if 'related_products' in vals:
            product_all = vals.get('related_products') or self.related_products
            for product_req in product_all:
                for pro in product_req[2]:
                    if pro:
                        product_data = self.env['product.product'].search([('id', '=', pro)])
                        migrated_product = self.env['product.template'].search(
                            [('id', '=', product_data.product_tmpl_id.id)])
                        if migrated_product:
                            if not migrated_product.reference_id:
                                raise ValidationError(
                                    _("{} product is not created in Hoitymoppet !".format(migrated_product.name)))

        # Route check
        # if 'route_ids' in vals or self.route_ids:
        #     route_req = vals.get('route_ids') or False
        #     required_route = self.route_ids.id or False
        #     if route_req:
        #         for ext_route in route_req:
        #             for ent_route in ext_route[2]:
        #                 route_name = self.env['stock.location.route'].search([('id', '=', ent_route)]).name
        #                 if route_name not in ['Make To Order', 'Manufacture']:
        #                     raise ValidationError("Please provide Manufacture or MTO route to this Product!")
        #     elif required_route:
        #         route_name_new = self.env['stock.location.route'].search([('id', '=', required_route)]).name
        #         if route_name_new not in ['Make To Order', 'Manufacture']:
        #             raise ValidationError("Please provide Manufacture or MTO route to this Product!")
        #     else:
        #         pass

    @api.model
    def create(self, vals):

        # if data is being sent to hoitymoppet then these are mandatory fields
        if 'migrate_data' in vals:
            migrate_value = vals.get('migrate_data')
            if migrate_value:

                if 'hsn_id' not in vals:
                    raise ValidationError('Please provide HSN Code!')

                # sales and discount price validations
                if 'list_price' in vals or 'discount_price' in vals:
                    sales_price = vals.get('list_price') or 0.0
                    discounted_price = vals.get('discount_price') or 0.0
                    if discounted_price >= sales_price:
                        raise ValidationError(
                            "Price after discount should not be greater than or equal to Sales Price!")

                # if not vals.get('description') or not vals.get('full_quality_image'):
                if not vals.get('full_quality_image') or not vals.get('list_price'):
                    raise ValidationError(_("Please provide image and sales price to the product!"))  # product

                # if data is being sent to hoitymoppet then this is check if already created or not
                self.check_data_to_migrate(vals=vals)

        result = super(ProductTemplate, self).create(vals)
        result.ecommerce_check = True

        try:
            if result.migrate_data:

                categories_list = []
                if result.category_ids:
                    for req_cat in result.category_ids:
                        categories_list.append(req_cat.reference_id)
                age_list = [ag.reference_id for ag in result.age_ids]
                color_list = [clr.reference_id for clr in result.color_ids]

                # add category to rep category
                if result.categ_id and result.categ_id not in categories_list:
                    categories_list.append(result.categ_id.reference_id)

                related_products = []
                if result.related_products:
                    for related_pro in result.related_products:
                        required_id = self.env['product.template'].search([('id', '=', related_pro.product_tmpl_id.id)])
                        related_products.append(required_id.reference_id) or False
                # defined_route = self.route_define()

                product_id = self.env['product.product'].search([('product_tmpl_id', '=', result.id)])
                slug_data = slugify(result.name)
                print("slug_data", slug_data)
                # self.assertEquals(slug_data, "this-is-a-test")

                unit = None
                if result.uom_id:
                    unit = self.env['product.uom'].search([('id', '=', result.uom_id.id)]).reference_id or False

                # P:code for updating the pflo id in hoitymoppet in creation of company in pflo
                required_dict = {
                    "product_name": result.name,
                    "slug": slug_data,
                    # "product_type": 1 or False,  # default for now as there is no matching pro type in pflo
                    "associated_company": result.company_id.reference_id or False,
                    "categories": categories_list or result.categ_id.reference_id,  # many2many categories
                    "categories_erp": result.categ_id.reference_id or None,  # single category
                    "age": age_list or None,  # many2many age fields
                    # "country": 1 or False,  # default for now
                    "color": color_list or None,  # color many2many tags field
                    "careinstructions": result.care_instruction_id.reference_id or None,
                    "item_detail": result.description or "default details for " + ' ' + result.name,
                    # "style_code": result.default_code or "default code for "+' '+result.name,
                    # "price": result.list_price or 0.0,
                    # "discount_price": result.discount_price or 0.0,
                    "price": result.mrp_data or 0.0,
                    "discount_price": result.mrp_discounted_data or 0.0,
                    "productimage": result.full_quality_image,
                    "migrate_data": result.migrate_data or True,
                    # "stock": defined_route or 1,
                    "reference_id": product_id.id,
                    "product_fabric": result.product_fabric_id.reference_id or None,
                    "status": 'active',
                    "relative_product": related_products or None,
                    "expected_delivery_date": result.sale_delay or 0,
                    "product_uom": unit or False,
                    "shipping_charges": result.shipping_charge or 0.0,
                }
                request = requests.post(url + '/create-product/',
                                        data=required_dict)

                created_product_id = request.json()
                print("response", request.json())
                result.reference_id = created_product_id['id']

        except KeyError:
            raise ValidationError("Response from HoityMoppet : {}".format(next(iter(request.json().values()))))

        return result

    @api.multi
    def write(self, vals):

        # if data is being sent to hoitymoppet then these are mandatory fields
        if 'migrate_data' in vals:
            migrate = vals.get('migrate_data')
            sale = vals.get('sale_ok') or self.sale_ok
            if migrate and not sale:
                raise ValidationError("Only Can be sold type of objects can be Migrated.")
            if migrate:

                price = vals.get('list_price') or self.list_price
                image = vals.get('full_quality_image') or self.full_quality_image
                if not price or not image:
                    raise ValidationError(
                        "Please provide both Sales Price and Image for the product !")  # verify fields

                # if data is being sent to hoitymoppet then this is check if already created or not
                self.check_data_to_migrate(vals=vals)

                # sales and discount price validations
                if 'list_price' in vals or 'discount_price' in vals:
                    sales_price = vals.get('list_price') or self.list_price
                    discounted_price = vals.get('discount_price') or self.discount_price
                    if discounted_price >= sales_price:
                        raise ValidationError(
                            "Price after discount should not be greater than or equal to Sales Price!")

            # else:
            #     raise UserError("Are you sure you want to delete this company in Hoitymoppet! ")
            # delete the item if already created!

        if self.migrate_data:

            if 'sale_delay' in vals:
                delay = vals.get('sale_delay')
                if delay <= 0:
                    raise ValidationError("Please provide more than 0 days !")

            if 'hsn_id' in vals and not vals.get('hsn_id'):
                raise ValidationError("Please provide HSN Code!")

            # sales and discount price validations
            if 'list_price' in vals or 'discount_price' in vals:
                sales_price = vals.get('list_price') or self.list_price
                discounted_price = vals.get('discount_price') or self.discount_price
                if discounted_price >= sales_price:
                    raise ValidationError(
                        "Price after discount should not be greater than or equal to Sales Price!")

            self.check_data_to_migrate(vals=vals)

            if 'category_ids' in vals:

                # multiple categories while editing
                category_all = vals.get('category_ids')
                for category_req in category_all:
                    for category in category_req[2]:
                        if category:
                            migrated_categ = self.env['product.category'].search([('id', '=', category)])
                            if migrated_categ:
                                if not migrated_categ.reference_id:
                                    raise ValidationError(
                                        _("{} category is not created in Hoitymoppet !".format(
                                            migrated_categ.name)))

            if 'age_ids' in vals:
                # multiple ages while editing
                age_all = vals.get('age_ids')
                for age_req in age_all:
                    for age in age_req[2]:
                        if age:
                            migrated_age = self.env['age'].search([('id', '=', age)])
                            if migrated_age:
                                if not migrated_age.reference_id:
                                    raise ValidationError(
                                        _("{} age is not created in Hoitymoppet !".format(
                                            migrated_age.name)))

            if 'color_ids' in vals:
                # multiple color_ids while editing
                color_all = vals.get('color_ids')
                for color_req in color_all:
                    for clr in color_req[2]:
                        if clr:
                            migrated_clr = self.env['color'].search([('id', '=', clr)])
                            if migrated_clr:
                                if not migrated_clr.reference_id:
                                    raise ValidationError(
                                        _("{} color is not created in Hoitymoppet !".format(
                                            migrated_clr.name)))

            if 'related_products' in vals:
                # multiple related_products while editing
                related_all = vals.get('related_products')
                for pro_req in related_all:
                    for pro in pro_req[2]:
                        if pro:
                            product_data = self.env['product.product'].search([('id', '=', pro)])
                            migrated_pro = self.env['product.template'].search(
                                [('id', '=', product_data.product_tmpl_id.id)])
                            if migrated_pro:
                                if not migrated_pro.reference_id:
                                    raise ValidationError(
                                        _("{} product is not created in Hoitymoppet !".format(
                                            migrated_pro.name)))

        result = super(ProductTemplate, self).write(vals)

        categories_list = []
        if self.category_ids:
            for req_cat in self.category_ids:
                categories_list.append(req_cat.reference_id)

        # categories_list = [categ.reference_id for categ in self.category_ids] or False
        age_list = [ag.reference_id for ag in self.age_ids] or False
        color_list = [clr.reference_id for clr in self.color_ids] or False

        # add category to rep category
        if self.categ_id and self.categ_id not in categories_list:
            categories_list.append(self.categ_id.reference_id)

        related_products = []
        if self.related_products:
            for related_pro in self.related_products:
                required_id = self.env['product.template'].search([('id', '=', related_pro.product_tmpl_id.id)])
                related_products.append(required_id.reference_id) or False

        # req_route = self.route_define()

        product_id = self.env['product.product'].search([('product_tmpl_id', '=', self.id)])
        unit = None
        if self.uom_id:
            unit = self.env['product.uom'].search([('id', '=', self.uom_id.id)]).reference_id or False

        requested_dict = {
            "product_name": self.name,
            # "product_type": 1 or False,  # default for now as there is no matching pro type in pflo
            "associated_company": self.company_id.reference_id or 1,
            "categories": categories_list or self.categ_id.reference_id,  # many2many categories
            "categories_erp": self.categ_id.reference_id or None,  # single category
            "age": age_list or None,  # many2many age fields
            # "country": 1 or False,  # default for now
            "color": color_list or None,  # color many2many tags field
            "careinstructions": self.care_instruction_id.reference_id or None,
            "item_detail": self.description or '',
            # "style_code": self.default_code or "default code for "+' '+result.name,
            # "price": self.list_price or 0.0,
            # "discount_price": self.discount_price or 0.0,
            "price": float(self.mrp_data) or 0.0,
            "discount_price": self.mrp_discounted_data or 0.0,
            "productimage": self.full_quality_image or False,
            "migrate_data": self.migrate_data,
            # "stock": req_route or 1,
            "reference_id": product_id.id,
            "product_fabric": self.product_fabric_id.reference_id or None,
            "status": 'active',
            "relative_product": related_products or None,
            "expected_delivery_date": self.sale_delay or 0,
            "product_uom": unit or False,
            "shipping_charges": self.shipping_charge or 0.0,
        }

        # If not already migrated
        if 'migrate_data' in vals:
            migrate_dt = vals.get('migrate_data')

            # create on click of migrate data as data is not already migrated
            if migrate_dt:
                slug_data = slugify(self.name)
                requested_dict['slug'] = slug_data

                if not self.reference_id:
                    try:
                        request = requests.post(url + '/create-product/',
                                                data=requested_dict)

                        created_product_id = request.json()
                        print("response", request.json())
                        self.reference_id = created_product_id['id']
                    except KeyError:
                        raise ValidationError("Response from HoityMoppet : {}".format(next(iter(request.json().values()))))

            else:
                slug_data = slugify(self.name)
                requested_dict['slug'] = slug_data
                requested_dict['status'] = 'inactive'
                request = requests.put(
                    url + '/update-product/' + str(self.reference_id) + '/',
                    data=requested_dict)
                print("response", request.json())
                # if self.saledetail_id:
                #     for so in self.saledetail_id:
                #         sale = self.env['sale.order'].search([('name', '=', so.sequence)])
                #         for line in sale.order_line:
                #             if line.product_uom_qty != line.qty_delivered:
                #                 raise ValidationError(
                #                     _("Can not delete this product it is having SO with remaining dispatches.. "))
                        # else:
                        #     requested_dict['status'] = 'inactive'
                        #     request = requests.put(
                        #         url + '/update-product/' + str(self.reference_id) + '/',
                        #         data=requested_dict)
                        #     print("response", request.json())

        if self.migrate_data:

            # if removing image
            if not self.full_quality_image:
                raise ValidationError("Please provide image to the product !")  # verify fields

            # if data edited update code for updating it to hoitymoppet
            else:
                slug_data = slugify(self.name)
                requested_dict['slug'] = slug_data
                requests.put(url + '/update-product/' + str(self.reference_id) + '/',
                             data=requested_dict)

        return result
# P: code ends for product creation


# P:code for creating care instructions model
class CareInstructions(models.Model):
    _name = "care.instruction"
    _description = "Care Instructions for the product"
    _order = "name"

    name = fields.Char(string="Care Name", required=True)
    care_details = fields.Text(string='Care Instructions', required=True)
    company_id = fields.Many2one('res.company', string="Company", required=True,
                                 default=lambda self: self.env.user.company_id)
    status = fields.Selection([('active', 'Active'), ('inactive', 'Inactive')], 'Status', default='active')

    migrate_data = fields.Boolean(string="Migrate", default=False)
    reference_id = fields.Integer(string="Reference Id", readonly=True)

    def migration_company_check(self, main_comp_check):
        if main_comp_check:
            migrated_company = self.env['res.company'].search([('id', '=', main_comp_check)])
            if not migrated_company.reference_id:
                raise ValidationError(
                    "{} is not created in Hoitymoppet !".format(migrated_company.name))

    @api.model
    def create(self, vals):

        if 'migrate_data' in vals and 'company_id' in vals:

            # if data is being sent to hoitymoppet then these are mandatory fields
            migrate = vals.get('migrate_data')
            if migrate:

                # company_check
                company_id = vals.get('company_id') or False
                if company_id:
                    self.migration_company_check(main_comp_check=company_id)

        # if data is being sent to hoitymoppet then these are mandatory fields
        result = super(CareInstructions, self).create(vals)

        # P:code for updating the pflo id in hoitymoppet in creation of company in pflo
        req_dict = {
            "cares_name": result.name or '',
            "cares_details": result.care_details or '',
            "status": result.status or '',
            "associated_company": result.company_id.reference_id or '',
            "migrate_data": result.migrate_data or False,
            "reference_id": result.id or '',
        }

        try:
            migrate = result['migrate_data']
            if migrate:
                request = requests.post(url + '/create-care-instruction/',
                                        data=req_dict)

                created_instruction_id = request.json()
                print("response", request.json())
                result.reference_id = created_instruction_id['id']
        except KeyError:
            raise ValidationError("Response from HoityMoppet : {}".format(next(iter(request.json().values()))))

        return result

    @api.multi
    def write(self, vals):

        if 'migrate_data' in vals and not self.reference_id:
            migrate = vals.get('migrate_data')
            if migrate:
                # company_check
                if 'company_id' in vals or self.company_id:
                    company_id = vals.get('company_id') or self.company_id
                    if company_id and not company_id.reference_id:
                        raise ValidationError(_("This company is not created in hoitymoppet! "))

        result = super(CareInstructions, self).write(vals)

        req_dict = {
            "cares_name": self.name or '',
            "cares_details": self.care_details or '',
            "status": self.status or '',
            "associated_company": self.company_id.reference_id or '',
            "migrate_data": self.migrate_data or True,
        }

        # If not already migrated
        if 'migrate_data' in vals:

            migrate = vals.get('migrate_data')
            if migrate:
                if not self.reference_id:
                    try:
                        migrate = vals['migrate_data']
                        if migrate:
                            request = requests.post(url + '/create-care-instruction/',
                                                    data=req_dict)

                            created_instruction_id = request.json()
                            print("response", request.json())
                            self.reference_id = created_instruction_id['id']
                    except KeyError:
                        raise ValidationError("Response from HoityMoppet : {}".format(next(iter(request.json().values()))))

            else:
                req_dict['status'] = 'inactive'
                request = requests.put(url + '/update-care-instruction/' + str(self.reference_id) + '/',
                             data=req_dict)
                print("response", request.json())

        if self.migrate_data:
            # if data edited with migrated data true
            requests.put(url + '/update-care-instruction/' + str(self.reference_id) + '/',
                         data=req_dict)
        return result
# P: code for care instructions ends here


# P:code for creating product fabric model
class ProductFabric(models.Model):
    _name = "product.fabric"
    _description = "Fabric for the product"
    _order = "name"

    name = fields.Char(string="Fabric Name", required=True)
    fabric_details = fields.Text(string='Fabric Details', required=True)
    company_id = fields.Many2one('res.company', string="Company", required=True,
                                 default=lambda self: self.env.user.company_id)
    status = fields.Selection([('active', 'Active'), ('inactive', 'Inactive')], 'Status', default='active')

    migrate_data = fields.Boolean(string="Migrate", default=False)
    reference_id = fields.Integer(string="Reference Id", readonly=True)

    @api.multi
    @api.constrains('name')
    def _check_name_duplicate(self):
        """
        Method for checking that name should not duplicate for the fiber.
        """
        for line in self:
            if line.name:
                check = self.env['product.fabric'].search([('name', '=', line.name)])
                if check and len(check) > 1:
                    raise ValidationError(_('Duplicate Fabric are not allowed !'))

    def check_migrated(self, company_id=None):
        if company_id:
            required_company = self.env['res.company'].search([('id', '=', company_id)])
            migrated = required_company.reference_id
            if not migrated:
                raise ValidationError(_("This company is not created in Hoitymoppet !"))

    @api.model
    def create(self, vals):

        if 'migrate_data' in vals and 'company_id' in vals:

            # if data is being sent to hoitymoppet then these are mandatory fields
            migrate = vals.get('migrate_data')
            if migrate:

                # company_check
                if 'company_id' in vals or self.company_id:
                    company_id = vals.get('company_id') or self.company_id
                    if company_id:
                        self.check_migrated(company_id=company_id)

        # if data is being sent to hoitymoppet then these are mandatory fields
        result = super(ProductFabric, self).create(vals)

        # P:code for updating the pflo id in hoitymoppet in creation of company in pflo
        req_dict = {
            "fabric": result.name or '',
            "fabric_detail": result.fabric_details or '',
            "status": result.status or '',
            "associated_company": result.company_id.reference_id or '',
            "migrate_data": result.migrate_data or False,
            "reference_id": result.id or '',
        }

        try:
            migrate = result['migrate_data']
            if migrate:
                request = requests.post(url + '/create-fabric/',
                                        data=req_dict)

                created_fabric_id = request.json()
                print("response", request.json())
                result.reference_id = created_fabric_id['id']
        except KeyError:
            raise ValidationError("Response from HoityMoppet : {}".format(next(iter(request.json().values()))))

        return result

    @api.multi
    def write(self, vals):

        # if 'migrate_data' in vals and not self.reference_id:
        if 'migrate_data' in vals:
            migrate = vals.get('migrate_data')

            if migrate:
                # company_check
                if 'company_id' in vals or self.company_id:
                    company_id = vals.get('company_id') or self.company_id
                    if company_id:
                        self.check_migrated(company_id=company_id.id)

        # if 'active' in vals and vals['active'] is False:
        #     self.env['mail.activity'].sudo().search(
        #         [('res_model', '=', self._name), ('res_id', 'in', self.ids)])

        res = super(ProductFabric, self).write(vals)

        requested_dict = {
            "fabric": self.name or '',
            "fabric_detail": self.fabric_details or '',
            "status": self.status or 'active',
            "associated_company": self.company_id.reference_id or False,
            "migrate_data": self.migrate_data or True,
        }

        # If not already migrated
        if 'migrate_data' in vals:
            migrate_dt = vals.get('migrate_data')

            # create on click of migrate data as data is not already migrated
            if migrate_dt:
                if not self.reference_id:

                    try:
                        migrate = vals['migrate_data']
                        if migrate:
                            request = requests.post(url + '/create-fabric/',
                                                    data=requested_dict)

                            created_fabric_id = request.json()
                            print("response", request.json())
                            self.reference_id = created_fabric_id['id']
                    except KeyError:
                        raise ValidationError("Response from HoityMoppet : {}".format(next(iter(request.json().values()))))

            else:
                requested_dict['status'] = 'inactive'
                request = requests.put(
                    url + '/update-fabric/' + str(self.reference_id) + '/',
                    data=requested_dict)
                print("response", request.json())

        if self.migrate_data:
            # if data edited with migrated data true
            requests.put(url + '/update-fabric/' + str(self.reference_id) + '/',
                         data=requested_dict)

        return res

# P: code for product fabric ends here


# P:code for creating Age model
class Age(models.Model):
    _name = "age"
    _description = "Age for reference"
    _order = "name"

    name = fields.Char(string="Age", required=True)
    # pwd = fields.Char(string="pwd", required=True)
    # pwd_hashed = fields.Char(string="pwd hashed")
    company_id = fields.Many2one('res.company', string="Company", required=True,
                                 default=lambda self: self.env.user.company_id)
    status = fields.Selection([('active', 'Active'), ('inactive', 'Inactive')], 'Status', default='active')

    migrate_data = fields.Boolean(string="Migrate", default=False)
    reference_id = fields.Integer(string="Reference Id", readonly=True)

    @api.multi
    @api.constrains('name')
    def _check_age_name_duplicate(self):
        """
        Method for checking that name should not duplicate for the age.
        """
        for line in self:
            if line.name:
                check = self.env['age'].search([('name', '=', line.name)])
                if check and len(check) > 1:
                    raise ValidationError(_('Duplicate Age are not allowed !'))

    def _crypt_context(self):
        """ Passlib CryptContext instance used to encrypt and verify
        passwords. Can be overridden if technical, legal or political matters
        require different kdfs than the provided default.

        Requires a CryptContext as deprecation and upgrade notices are used
        internally
        """
        return default_crypt_context

    def _set_password(self, password):
        encrypted = self._crypt_context().encrypt(password)
        print(encrypted)

    def check_migrated(self, company_id=None):
        if company_id:
            required_company = self.env['res.company'].search([('id', '=', company_id)])
            migrated = required_company.reference_id
            if not migrated:
                raise ValidationError(_("This company is not created in Hoitymoppet !"))

    @api.model
    def create(self, vals):

        # pwd = vals.get('pwd')
        # self._set_password(pwd)

        if 'migrate_data' in vals and 'company_id' in vals:

            # if data is being sent to hoitymoppet then these are mandatory fields
            migrate = vals.get('migrate_data')
            if migrate:

                # company_check
                if 'company_id' in vals or self.company_id:
                    company_id = vals.get('company_id') or self.company_id
                    if company_id:
                        self.check_migrated(company_id=company_id)

        # if data is being sent to hoitymoppet then these are mandatory fields
        result = super(Age, self).create(vals)

        # P:code for updating the pflo id in hoitymoppet in creation of company in pflo
        req_dict = {
            "age": result.name or '',
            "status": result.status or '',
            "associated_company": result.company_id.reference_id or '',
            "migrate_data": result.migrate_data or False,
            "reference_id": result.id or '',
        }

        try:
            migrate = result['migrate_data']
            if migrate:
                request = requests.post(url + '/create-age/',
                                        data=req_dict)

                created_age_id = request.json()
                print("response", request.json())
                result.reference_id = created_age_id['id']
        except KeyError:
            raise ValidationError("Response from HoityMoppet : {}".format(next(iter(request.json().values()))))

        return result

    @api.multi
    def write(self, vals):

        # if data is being sent to hoitymoppet then these are mandatory fields
        if 'migrate_data' in vals:
            migrate = vals.get('migrate_data')
            company_id = vals.get('company_id') or self.company_id
            if migrate:
                if not company_id:
                    raise ValidationError("Please provide company id!")  # verify fields
            # else:
            #     raise UserError("Are you sure you want to delete this company in Hoitymoppet! ")
            # delete the item if already created!

        result = super(Age, self).write(vals)

        requested_dict = {
            "age": self.name,
            "status": self.status,
            "associated_company": self.company_id.reference_id,
            "migrate_data": self.migrate_data,
            "reference_id": self.id,
        }

        # If not already migrated
        if 'migrate_data' in vals:
            migrate_dt = vals.get('migrate_data')

            # create on click of migrate data as data is not already migrated
            if migrate_dt:
                if not self.reference_id:

                    try:
                        migrate = vals['migrate_data']
                        if migrate:
                            request = requests.post(url + '/create-age/',
                                                    data=requested_dict)

                            created_age_id = request.json()
                            print("response", request.json())
                            self.reference_id = created_age_id['id']
                    except KeyError:
                        raise ValidationError("Response from HoityMoppet : {}".format(next(iter(request.json().values()))))

            else:
                requested_dict['status'] = 'inactive'
                request = requests.put(url + '/update-age/' + str(self.reference_id) + '/',
                             data=requested_dict)
                print("response", request.json())

        if self.migrate_data:
            # if data edited with migrated data true
            requests.put(url + '/update-age/' + str(self.reference_id) + '/',
                         data=requested_dict)

        return result
# P: code for Age ends here


# P:code for creating Color model
class Color(models.Model):
    _name = "color"
    _description = "Color for reference"
    _order = "name"

    name = fields.Char(string="Name", required=True)
    color_name = fields.Char(string="Color", required=True, default="#fff")
    company_id = fields.Many2one('res.company', string="Company", required=True,
                                 default=lambda self: self.env.user.company_id)
    status = fields.Selection([('active', 'Active'), ('inactive', 'Inactive')], 'Status', default='active')

    migrate_data = fields.Boolean(string="Migrate", default=False)
    reference_id = fields.Integer(string="Reference Id", readonly=True)

    @api.multi
    @api.constrains('name')
    def _check_color_name_duplicate(self):
        """
        Method for checking that name should not duplicate for the color.
        """
        for line in self:
            if line.name:
                check = self.env['color'].search([('name', '=', line.name)])
                if check and len(check) > 1:
                    raise ValidationError(_('Duplicate Color are not allowed !'))

    def check_migrated(self, company_id=None):
        if company_id:
            required_company = self.env['res.company'].search([('id', '=', company_id)])
            migrated = required_company.reference_id
            if not migrated:
                raise ValidationError(_("This company is not created in Hoitymoppet !"))

    @api.model
    def create(self, vals):

        if 'migrate_data' in vals and 'company_id' in vals:

            # if data is being sent to hoitymoppet then these are mandatory fields
            migrate = vals.get('migrate_data')
            if migrate:

                # company_check
                if 'company_id' in vals or self.company_id:
                    company_id = vals.get('company_id') or self.company_id
                    if company_id:
                        self.check_migrated(company_id=company_id)

        # if data is being sent to hoitymoppet then these are mandatory fields
        result = super(Color, self).create(vals)

        req_dict = {
            "color_name": result.name or '',
            "color": result.color_name or '',
            "associated_company": result.company_id.reference_id or '',
            "status": result.status or 'active',
            "migrate_data": result.migrate_data or False,
            "reference_id": result.id or '',
            # "create_uid": create_uid or False,
            # "write_uid": write_uid or False,
        }

        try:
            migrate = result['migrate_data']
            if migrate:
                request = requests.post(url + '/create-color/',
                                        data=req_dict)

                created_color_id = request.json()
                print("response", request.json())
                result.reference_id = created_color_id['id']
        except KeyError:
            raise ValidationError("Response from HoityMoppet : {}".format(next(iter(request.json().values()))))

        return result

    @api.multi
    def write(self, vals):

        # if 'migrate_data' in vals and not self.reference_id:
        if 'migrate_data' in vals:
            migrate = vals.get('migrate_data')

            if migrate:
                # company_check
                if 'company_id' in vals or self.company_id:
                    company_id = vals.get('company_id') or self.company_id
                    if company_id:
                        self.check_migrated(company_id=company_id.id)

        # if 'active' in vals and vals['active'] is False:
        #     self.env['mail.activity'].sudo().search(
        #         [('res_model', '=', self._name), ('res_id', 'in', self.ids)])

        res = super(Color, self).write(vals)

        requested_dict = {
            "color_name": self.name or '',
            "color": self.color_name or '',
            "associated_company": self.company_id.reference_id or False,
            "status": self.status or 'active',
            "migrate_data": self.migrate_data or False,
            "reference_id": self.id,
        }

        # If not already migrated
        if 'migrate_data' in vals:
            migrate_dt = vals.get('migrate_data')

            # create on click of migrate data as data is not already migrated
            if migrate_dt:
                if not self.reference_id:

                    try:
                        migrate = vals['migrate_data']
                        if migrate:
                            request = requests.post(url + '/create-color/',
                                                    data=requested_dict)

                            created_color_id = request.json()
                            print("response", request.json())
                            self.reference_id = created_color_id['id']
                    except KeyError:
                        raise ValidationError("Response from HoityMoppet : {}".format(next(iter(request.json().values()))))

            else:
                requested_dict['status'] = 'inactive'
                request = requests.put(url + '/update-color/' + str(self.reference_id) + '/',
                                       data=requested_dict)
                print("response", request.json())
                # del_request = requests.delete(
                #     'http://127.0.0.1:7000/hoitymoppet/delete-fabric/' + str(self.reference_id) + '/',
                #     verify=True)
                # del_request.json()
                # delete data from hoitymoppet!

        if self.migrate_data:
            # if data edited with migrated data true
            requests.put(url + '/update-color/' + str(self.reference_id) + '/',
                         data=requested_dict)

        return res
# P: code for creating color ends here


# Piyush: code for adding class for holding multiple images
class MultipleImages(models.Model):
    _name = "multiple.images"
    _description = "Model for holding multiple images to a perticular product !"
    _order = "image"

    image = fields.Binary(string="Add Image", max_width=100, max_height=100, attachment=True)
    product_id = fields.Many2one('product.template', 'Product')
    migrate_data = fields.Boolean(string="Migrate", default=False)
    reference_id = fields.Integer(string="Reference Id", readonly=True)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.user.company_id)

    @api.model
    def create(self, vals):

        # if data is being sent to hoitymoppet then these are mandatory fields
        result = super(MultipleImages, self).create(vals)

        # P:code for updating the pflo id in hoitymoppet in creation of company in pflo
        req_dict = {
            "product": result.product_id.reference_id or '',
            "image": result.image,
            "migrate_data": True,
            "reference_id": result.id,
            "status": True,
            "associated_company": result.company_id.reference_id or 1,
        }

        try:
            request = requests.post(url + '/create-images/',
                                    data=req_dict)
            created_instance_id = request.json()
            print("response", request.json())
            result.reference_id = created_instance_id['id']
        except KeyError:
            raise ValidationError("Response from HoityMoppet : {}".format(next(iter(request.json().values()))))
        return result

    @api.multi
    def unlink(self):
        for rec in self:
            request = requests.delete(
                        url + '/delete-image/' + str(rec.id) + '/',
                        verify=True)
        return super(MultipleImages, rec).unlink()
# Piyush: code for adding class for holding multiple images ends here


# Piyush: code for inheriting customer class
def state_and_country_check(vals):
    if "state_id" in vals:
        state = vals.get("state_id", False)
        if not state:
            raise ValidationError("Please provide state !")
    if "country_id" in vals:
        country = vals.get("country_id", False)
        if not country:
            raise ValidationError("Please provide Country !")
    # Piyush: code for making state and country required in manual partner creation on 1jan ends here


class Customer(models.Model):
    _inherit = 'res.partner'

    @api.multi
    @api.constrains('email')
    def email_dup_constrains(self):
        """
        Method for checking that email should not duplicate for the customer where parent is Null.
        """
        for line in self:
            if line.email:
                check = self.env['res.partner'].search([('email', '=', line.email), ('parent_id', '=', False)])
                if check and len(check) > 1:
                    raise ValidationError(_('Duplicate Email are not allowed for Customer!'))

    # Fields added for migrating data
    children_ids = fields.One2many("customer.children", 'customer_id', string="Children")
    cart_ids = fields.One2many("customer.cart", 'customer_id', string="Customer Cart")
    wishlist_ids = fields.One2many("customer.wishlist", 'customer_id', string="Customer Wishlist")
    migrate_data = fields.Boolean(string="Migrate", default=False)
    reference_id = fields.Integer(string="Reference Id", readonly=True)

    def check_state(self, vals):
        # if data is being sent to hoitymoppet then these are mandatory fields
        if 'state_id' in vals and "from_hm" in vals and vals.get("from_hm"):
            state_req = vals.get('state_id')
            try:
                state_found = self.env['res.country.state'].search([('id', '=', state_req)]).id
                vals['state_id'] = state_found
            except:
                vals['state_id'] = 587

        if 'country_id' in vals and "from_hm" in vals and vals.get("from_hm"):
            country_req = vals.get('country_id')
            try:
                country_found = self.env['res.country'].search([('id', '=', country_req)]).id
                vals['country_id'] = country_found
            except:
                vals['country_id'] = 1
        return vals

    # Piyush: code for making state and country required in manual partner creation on 1jan

    @api.model
    def create(self, vals):
        if "created_from_hm" in vals and vals.get("created_from_hm"):
            vals['customer'] = True
        if 'parent_id' not in vals:
            vals['parent_id'] = False
        # Piyush: code for making state and country required in manual partner creation on 1jan
        if "created_from_hm" not in vals and ("state_id" in vals or "country_id" in vals):
            state_and_country_check(vals)
        # Piyush: code for making state and country required in manual partner creation on 1jan ends here
        result = super(Customer, self).create(vals)
        return result

    @api.multi
    def write(self, vals):
        if "created_from_hm" in vals and vals.get("created_from_hm"):
            vals['customer'] = True

        # Piyush: code for making state and country required in manual partner creation on 1jan
        if "created_from_hm" not in vals and ("state_id" in vals or "country_id" in vals):
            state_and_country_check(vals)
        # Piyush: code for making state and country required in manual partner creation on 1jan ends here

        result = super(Customer, self).write(vals)
        return result
# Piyush: code for inheriting customer class ends here


# Piyush: code for adding class for holding multiple child by customer
class CustomerChild(models.Model):
    _name = "customer.children"
    _description = "Model for holding multiple Children to a particular Customer !"
    _order = "name"

    customer_id = fields.Many2one('res.partner', string="Parent")
    name = fields.Char(string="Child Name")
    child_birth_date = fields.Date('Date of Birth')
    # profile = models.ForeignKey(Profile, on_delete=models.CASCADE, null=True, blank=True)
    # Fields added for migrating data
    migrate_data = fields.Boolean(string="Migrate", default=False)
    reference_id = fields.Integer(string="Reference Id", readonly=True)

    @api.model
    def create(self, vals):
        if 'child_birth_date' in vals:
            date_of_birth = vals.get('child_birth_date')
            date_time_obj = datetime.strptime(date_of_birth, '%Y-%d-%m').date()
            vals['child_birth_date'] = date_time_obj

        res = super(CustomerChild, self).create(vals)
        return res

    @api.multi
    def write(self, vals):
        res = super(CustomerChild, self).write(vals)
        return res
# Piyush: code for adding class for holding multiple child by customer ends here


# Piyush: code for inheriting sale order class
class SaleOrder(models.Model):
    _inherit = "sale.order"

    # Fields added for migrating data
    migrate_data = fields.Boolean(string="Migrate", default=False, readonly=True)
    reference_id = fields.Integer(string="Reference Id", readonly=True)
    data_from_hoitymoppet = fields.Boolean("From Hoitymoppet", default=False)
    coupon_id = fields.Many2one('available.coupons', string="Coupon")
    shipping_charges = fields.Float(string='Shipping Charges')

    def get_unit_price(self):
        for rec in self:
            if rec.coupon_id and rec.coupon_id.coupon_type == "Percentage":
                value = rec.coupon_id.coupon_value
                if value and value > 0:
                    for line in rec.order_line:
                        # line.update({'discount': value})
                        price = rec.product_id.mrp_discounted_data or rec.product_id.mrp_data
                        calculated_value = price - (price * value / 100)
                        line.unit_price = calculated_value
            elif rec.coupon_id and rec.coupon_id.coupon_type == 'Fixed':
                pass  # convert into percentage the value of coupon and then apply

    def expexcted_delivery_date(self, vals):
        expected_days = vals.get('maximum_days')
        if expected_days and expected_days > 0:
            vals['no_of_days_manu'] = expected_days
            vals['manufacturnig_end_date'] = datetime.strptime(str(datetime.now().date()), '%Y-%m-%d').date() + \
                                                timedelta(days=expected_days)

    @api.model
    def create(self, vals):
        if 'maximum_days' in vals and 'reference_id' in vals and vals.get('reference_id'):
            self.expexcted_delivery_date(vals=vals)

        if 'address_id' in vals and 'partner_id' in vals and vals.get('partner_id') \
                and 'reference_id' in vals and vals and vals.get('reference_id'):
            addr = vals.get('address_id')
            parent = vals.get('partner_id')
            req_add = self.env['res.partner'].search([('reference_id', '=', addr), ('parent_id', '=', parent)]).id

            vals['partner_shipping_id'] = req_add
        result = super(SaleOrder, self).create(vals)

        if result.partner_id.id != result.partner_shipping_id.id:
            data = self.env['res.partner'].search([('id', '=', result.partner_shipping_id.id),
                                                   ('parent_id', '=', result.partner_id.id)])
            street = data.street or False
            street2 = data.street2 or False
            city = data.city
            state = self.env['res.country.state'].search([('id', '=', data.state_id.id)]).name
            country = self.env['res.country'].search([('id', '=', data.country_id.id)]).name
            zip = data.zip
            data_list = [street, street2, city, state, zip, country]
            val = ""
            if data_list:
                for dt in data_list:
                    if dt:
                        val = val + str(dt) + "\n"
            result.address = val
            result.gstin = self.env['res.partner'].search([('display_name', '=', result.partner_shipping_id.display_name)]).vat

        return result

    @api.multi
    def write(self, vals):

        if 'maximum_days' in vals and 'reference_id' in vals and vals.get('reference_id'):
            self.expexcted_delivery_date(vals=vals)

        if 'address_id' in vals and 'partner_id' in vals and vals.get('partner_id') and self.reference_id :
            addr = vals.get('address_id')
            parent = vals.get('partner_id')
            req_add = self.env['res.partner'].search([('reference_id', '=', addr), ('parent_id', '=', parent)]).id
            vals['partner_shipping_id'] = req_add

        if "coupon_id" in vals and "coupon_applied" in vals and vals.get("coupon_applied") and self.reference_id:
            result = super(SaleOrder, self).write(vals)
            self.get_unit_price()
            return result

        if ('state' in vals and 'confirmation_date' in vals) or ('dispatch_ids' in vals) and self.reference_id:
            if 'dispatch_ids' in vals:
                vals['state_new'] = 'Shipped'
                requests.put(url + '/update-order/' + str(self.reference_id) + '/',
                             data=vals)

            elif 'state' in vals and 'confirmation_date' in vals:
                requests.put(url + '/update-order/' + str(self.reference_id) + '/',
                             data=vals)

        if 'state' in vals and self.reference_id:
            requests.put(url + '/update-order/' + str(self.reference_id) + '/',
                         data=vals)
            vals['state'] = 'sale'

        if 'shipping_charges' in vals and self.reference_id:

            # Code for getting taxes before adding the product on 22dec ends here
            max_tax = []
            value = 0.0
            if self.order_line:
                for order_line in self.order_line:
                    if order_line.product_id and order_line.tax_id[0] and order_line.tax_id[0].type_tax_use == 'sale':
                        get_tax_ids = order_line.tax_id[0].tax_group_id
                        if get_tax_ids:
                            if get_tax_ids and get_tax_ids.name == 'IGST':
                                max_tax.append(order_line.tax_id[0].amount)
                            else:
                                max_tax.append(order_line.tax_id[0].amount * 2)
            if max_tax:
                value = max(max_tax)

            # Add new product to the sale order for adjusting shipping charges, this is a service type product.
            sale_order_line_obj = self.env['sale.order.line']  # created sale order line object
            shipping = self.env['shipping.product'].search([])
            get_product = self.env['product.product'].search([('id', '=', shipping[0].product_id.id)])
            ship_charge = 0.0
            tax_ids = []
            if not value:
                if self.partner_id and self.partner_id.state_id and self.company_id and self.company_id.partner_id.state_id:
                    if self.partner_shipping_id.state_id == self.company_id.partner_id.state_id:
                        for tx in get_product.customer_tax_lines:
                            if tx.tax_group_id.name in ['CGST', 'SGST'] and tx.tax_percentage == shipping.percentage/2:
                                tax_ids.append(tx.tax_id.id)
                    else:
                        for tx in get_product.customer_tax_lines:
                            if tx.tax_group_id.name == "IGST" and tx.tax_percentage == shipping.percentage:
                                tax_ids.append(tx.tax_id.id)
                ship_charge = (vals.get("shipping_charges"))/(1+(shipping.percentage/100))  # should be 18 by default

            else:
                if self.order_line:
                    for order_line in self.order_line:
                        if order_line.product_id and order_line.tax_id[0] and order_line.tax_id[0].type_tax_use == 'sale':
                            get_tax_ids = order_line.tax_id[0].tax_group_id
                            if get_tax_ids:
                                if get_tax_ids and get_tax_ids.name == 'IGST':
                                    for txs in get_product.customer_tax_lines:
                                        if txs.tax_group_id.name == "IGST" and txs.tax_percentage == value:
                                            tax_ids.append(txs.tax_id.id)
                                elif get_tax_ids and get_tax_ids.name in ['CGST', 'SGST']:
                                    for txs in get_product.customer_tax_lines:
                                        if txs.tax_group_id.name in ['CGST', 'SGST'] and txs.tax_percentage == value/2:
                                            tax_ids.append(txs.tax_id.id)

                    ship_charge = (vals.get("shipping_charges")) / (
                                1 + (value / 100))  # should be 18 by default
            line_dict = {
                "order_id": self.id or False,
                "name": get_product.name or '',
                "product_id": get_product.id or 1,
                "product_uom_qty": 1.0,
                "price_unit": round(ship_charge, 2),
                "product_uom": get_product.uom_id.id or 1,
                "tax_id": [(6, 0, tax_ids)],
            }

            sale_order_line_obj.create(line_dict)  # create sale order line with the existing product

            # tax_list=[]
            # order_lines=self.order_line
            # for rec in order_lines:
            #     taxes=rec.tax_id
            #     amount = 0.0
            #     for tax in taxes:
            #         if tax.tax_group_id.name == 'IGST':
            #             amount= tax.amount
            #         elif tax.tax_group_id.name == 'CGST' or tax.tax_group_id.name =='SGST':
            #             amount= amount+tax.amount
            #     tax_list.append(amount)
            # max_tax=max(tax_list)
            # print("max_tax",max_tax)
            # print('vals.get("shipping_charges")',vals.get("shipping_charges"))
            # ship_charge=(vals.get("shipping_charges"))/(1+(max_tax/100))
            # tax_amount=ship_charge*(max_tax/100)
            # self.amount_tax=self.amount_tax+tax_amount
            vals['shipping_charges'] = ship_charge
            # self.amount_total=self.amount_total + ship_charge + tax_amount
            # print("vals",vals)
            #vals.get("shipping_charges")
        # print("hiii")
        # tax_list=[]
        # order_lines=self.order_line
        # for rec in order_lines:
        #     taxes=rec.tax_id
        #     for tax in taxes:
        #         amount=tax.amount
        #         tax_list.append(amount)
        # if tax_list:
        #     max_tax=max(tax_list)
        # max_tax=25.00
        # print("max_tax",max_tax)
        # ship_charge=(500)/(1+(max_tax/100.00))
        # tax_amount=ship_charge*(max_tax/100.00)
        # print
        # vals['amount_tax']=self.amount_tax+tax_amount
        # vals['shipping_charges']=ship_charge
        # vals['amount_total']=self.amount_total + ship_charge

        # Code for getting taxes before adding the product on 22dec
        result = super(SaleOrder, self).write(vals)
        return result
# Piyush: code for inheriting sale order class ends here


# Piyush: code for inheriting sale order line class
class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    # Fields added for migrating data
    migrate_data = fields.Boolean(string="Migrate", default=False, readonly=True)
    reference_id = fields.Integer(string="Reference Id", readonly=True)
    age_id = fields.Many2one('age', string="Age")
    custom_measure_master_id = fields.Many2one('user.custom.measures.master', string="Custom Measure")
    color_id = fields.Many2one('color', string="color")

    # Piyush: code for checking user custom measures on 21-10-2020
    @api.multi
    def get_user_custom_measures(self):
        """
        This function opens a view of user custom measures master that contains custom measures created by the
        customer.
        :return: Returns an action that will open a form view (in a popup) allowing to work on all the
        user custom lines of a particular custom measures master.
        """
        all_custom_measures = []
        custom_measures_master = self.env['user.custom.measures.master'].search(
            [('id', '=', self.custom_measure_master_id.id)])
        if custom_measures_master:
            all_custom_measures = self.env['custom.measures'].search(
                [('custom_measures_master', '=', custom_measures_master.id),
                 ('customer', '=', self.order_id.partner_id.id)]).ids
        result = self.env.ref('ecom_integration.action_custom_measures_form').read()[0]
        res = self.env.ref('ecom_integration.view_custom_measures_tree', False)
        res_form = self.env.ref('ecom_integration.view_custom_measures_form', False)
        result['views'] = [(res and res.id or False, 'list'), (res_form and res_form.id or False, 'form')]
        result['domain'] = [('id', 'in', tuple(all_custom_measures))]
        result['target'] = 'current'
        result['view_type'] = 'form'
        result['view_mode'] = 'tree,form'
        return result
    # code ends here

    # Piyush: code for computing unit price based on tax, cupons ans discount on 18-10-2020
    def get_price_unit(self, vals):
        """
        This function takes in vals and return unit price after computing coupons, discount and taxes on the
        sale order and product respectively.
        :param vals: it contains **kwargs of data to be created in sale order lines.
        :return: **kwargs with the updated price unit.
        """
        price_unit = vals.get('price_unit')
        pro_product = self.env['product.product'].search([('id', '=', vals.get('product_id'))])
        req_product = self.env['product.template'].search([('id', '=', pro_product.product_tmpl_id.id)])
        find_delay = self.env['sale.order'].search([('id', '=', vals.get('order_id'))])
        if find_delay:
            for line in find_delay.order_line:
                delay_time = []
                if line.product_id.sale_delay and req_product.sale_delay > 0:
                    delay_time.append(req_product.sale_delay)
                if len(delay_time) > 0:
                    find_delay.no_of_days_manu = max(delay_time)
                    find_delay.manufacturnig_end_date = datetime.strptime(str(datetime.now().date()), '%Y-%m-%d').date() + \
                                                        timedelta(days=max(delay_time))
        for rec in req_product:
            if rec.customer_tax_lines:
                for tax in rec.customer_tax_lines:
                    obtain_tax = self.env['account.tax'].search([('id', '=', tax.tax_id.id)])
                    if obtain_tax.type_tax_use == 'sale' and obtain_tax.tax_group_id.id == 4:
                        # vals['price_unit'] = ceil(price_unit / (1 + obtain_tax.amount / 100))
                        vals['price_unit'] = round((price_unit / (1 + obtain_tax.amount / 100)), 2)
        return vals
    # code ends here

    @api.model
    def create(self, vals):
        values = {}
        if 'order_detail' in vals and 'order_id' in vals and 'reference_id' in vals and vals and vals.get('reference_id'):
            if 'product_id' in vals and 'product_uom' in vals:
                vals['product_uom'] = self.env['product.product'].search([('id', '=', vals.get('product_id'))]).product_tmpl_id.uom_id.id
            values = self.get_price_unit(vals=vals)
        if values:
            result = super(SaleOrderLine, self).create(values)
        else:
            result = super(SaleOrderLine, self).create(vals)
        return result

    @api.multi
    def write(self, vals):
        values = {}
        if 'order_detail' in vals and 'order_id' in vals and 'reference_id' in vals and vals.get('reference_id'):
            if 'product_id' in vals and 'product_uom' in vals:
                vals['product_uom'] = self.env['product.product'].search(
                    [('id', '=', vals.get('product_id'))]).product_tmpl_id.uom_id.id
            values = self.get_price_unit(vals=vals)
        if values:
            result = super(SaleOrderLine, self).write(values)
        else:
            result = super(SaleOrderLine, self).write(vals)
        return result

# Piyush: code for inheriting sale order line class ends here


# Piyush: code for adding class for customer cart
class CustomerCart(models.Model):
    _name = "customer.cart"
    _description = "Model for holding data in customer cart!"

    customer_id = fields.Many2one('res.partner', string="Customer Name", required=True)
    product_id = fields.Many2one('product.product', 'Product', required=True)
    product_size = fields.Char(string='Product Size')
    user_custom_size = fields.Char(string='User Custom Size')
    prod_color = fields.Many2one("Color", string="Old Color")
    color_id = fields.Many2one("color", string="Product Color")
    quantity = fields.Integer(string='Quantity', default=0)
    total_price = fields.Integer(string='Total Price')
    ordered = fields.Boolean(string="Ordered", default=False)
    migrate_data = fields.Boolean(string="Migrate", default=False)
    reference_id = fields.Integer(string="Reference Id", readonly=True)
    product_age = fields.Many2one('age', string="Age")
    user_custom_size_master = fields.Many2one('user.custom.measures.master', string="User Custom Measures Master")

    @api.model
    def create(self, values):
        result = super(CustomerCart, self).create(values)
        return result
# Piyush: code for adding class for customer cart ends here


# Piyush: code for adding class for customer cart
class CustomerWishlist(models.Model):
    _name = "customer.wishlist"
    _description = "Model for holding data in customer cart!"

    customer_id = fields.Many2one('res.partner', string="Customer Name", required=True)
    product_id = fields.Many2one('product.product', 'Product', required=True)
    migrate_data = fields.Boolean(string="Migrate", default=False)
    reference_id = fields.Integer(string="Reference Id", readonly=True)

    @api.model
    def create(self, values):
        result = super(CustomerWishlist, self).create(values)
        return result
# Piyush: code for adding class for customer cart ends here


# Piyush: code for adding class for measurement master
class MeasurementMaster(models.Model):
    _name = "measurement.master"
    _description = "Model for Measurement Master!"

    name = fields.Char(string='Measure Name', required=True)
    status = fields.Selection([('active', 'Active'), ('inactive', 'Inactive')], 'Status', default='active')
    size_unit = fields.Selection([('centimeter', 'centimeter'), ('inches', 'inches')], 'Size Unit', default='inches')
    migrate_data = fields.Boolean(string="Migrate", default=False)
    reference_id = fields.Integer(string="Reference Id", readonly=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.user.company_id.id,
                                 readonly=True)

    @api.multi
    @api.constrains('name')
    def _check_measurement_master_name_duplicate(self):
        """
        Method for checking that name should not duplicate for the measurement master.
        """
        for line in self:
            if line.name:
                check = self.env['measurement.master'].search([('name', '=', line.name)])
                if check and len(check) > 1:
                    raise ValidationError(_('Duplicate Measurement Master are not allowed !'))

    @api.model
    def create(self, vals):

        result = super(MeasurementMaster, self).create(vals)

        # P:code for updating the pflo id in hoitymoppet in creation of company in pflo
        req_dict = {
            "name": result.name or '',
            "status": result.status or '',
            "size_unit": result.size_unit or '',
            "migrate_data": result.migrate_data or False,
            "reference_id": result.id or '',
            "associated_company": self.env.user.company_id.reference_id or None,
        }

        try:
            migrate = result['migrate_data']
            if migrate:
                request = requests.post(url + '/create-measurement-master/',
                                        data=req_dict)

                created_measurement_master_id = request.json()
                print("response", request.json())
                result.reference_id = created_measurement_master_id['id']
        except KeyError:
            raise ValidationError("Response from HoityMoppet : {}".format(next(iter(request.json().values()))))

        return result

    @api.multi
    def write(self, vals):

        result = super(MeasurementMaster, self).write(vals)

        requested_dict = {
            "name": self.name,
            "status": self.status,
            "size_unit": self.size_unit,
            "migrate_data": self.migrate_data,
            "reference_id": self.id,
            "associated_company": self.env.user.company_id.reference_id or None,
        }

        # If not already migrated
        if 'migrate_data' in vals:
            migrate_dt = vals.get('migrate_data')

            # create on click of migrate data as data is not already migrated
            if migrate_dt:
                if not self.reference_id:

                    try:
                        migrate = vals['migrate_data']
                        if migrate:
                            request = requests.post(url + '/create-measurement-master/',
                                                    data=requested_dict)

                            created_measurement_master_id = request.json()
                            print("response", request.json())
                            self.reference_id = created_measurement_master_id['id']
                    except KeyError:
                        raise ValidationError("Response from HoityMoppet : {}".format(next(iter(request.json().values()))))

            else:
                del_request = requests.put(
                    url + '/delete-measurement-master/' + str(self.reference_id) + '/',
                    verify=True)
                del_request.json()
                # delete data from hoitymoppet!

        if self.migrate_data:
            # if data edited with migrated data true
            requests.put(url + '/update-measurement-master/' + str(self.reference_id) + '/',
                         data=requested_dict)

        return result
# Piyush: code for adding class for measurement master ends here


# Piyush: code for age and measure lines model 19-09-2020
class AgeMeasure(models.Model):
    _name = "age.measures"
    _description = "Model for Age and Measures details!"

    age = fields.Many2one('age', string="Age", required=True)
    measure_ids = fields.One2many('measures', 'measures_id', string="Measure Lines")
    migrate_data = fields.Boolean("Migrate data", default=False)

    @api.onchange('migrate_data')
    def onchange_migrate_data(self):
        for rec in self:
            if rec.age and rec.migrate_data and rec.measure_ids:
                for migrate in rec.measure_ids:
                    migrate.migrate_data = True
            elif not rec.migrate_data and rec.age and rec.measure_ids:
                for migrate in rec.measure_ids:
                    migrate.migrate_data = False

    @api.onchange('age')
    def onchange_age(self):

        check = self.env['age.measures'].search([])
        domain = {}
        age_rec = []
        for ag in check:
            age_rec.append(ag.age.id)

            domain = {'domain': {'age': [('id', '!=', age_rec)]}}

        if self.age:
            self.measure_ids = ''
            measures_list = []
            age_record = self.env['measurement.master'].search([])
            for item in age_record:
                line = (0, 0, {
                    'measure_name': item.id,
                    'size_unit': item.size_unit,
                    'age': self.age.id,
                    'status': 'active',
                })
                measures_list.append(line)
            self.measure_ids = measures_list

        else:
            self.measure_ids = ''
        return domain

    @api.multi
    def write(self, values):
        if 'migrate_data' in values:
            migrate_check = values.get('migrate_data')
            if not migrate_check:
                raise ValidationError("Age measures can not be unmigrated, this can be done manually at lines !")
        result = super(AgeMeasure, self).write(values)
        return result

# Piyush: code for age and measure lines model ends here 19-09-2020


# Piyush: code for adding class for Measures
class Measures(models.Model):
    _name = "measures"
    _description = "Model for Measures!"

    @api.multi
    @api.constrains('value', 'status')
    def _check_zero_check(self):
        """
        method for checking that Measures value should be greater than zero
        """
        for line in self:
            if line.status == 'active' and line.value <= 0:
                raise ValidationError("Measure Values should be greater than 0 for active measures !")

    @api.multi
    @api.constrains('measure_name', 'age')
    def _check_measure_ids(self):
        """
        Quantity Multiple can not be less than 1
        """
        for line in self:
            if line.measure_name and line.age:
                check = self.env['measures'].search([('age', '=', line.age.id),
                                                     ('measure_name', '=', line.measure_name.id)])
                if check and len(check) > 1:
                    raise ValidationError(_('Duplicate Measure name are not allowed !'))

    @api.multi
    @api.depends('measure_name.name')
    def name_get(self):
        result = []
        for dt in self:
            name = dt.measure_name.name
            result.append((dt.id, name))
        return result

    # @api.multi
    # def onchange_measure_ids(self):
    #     list_ids = []
    #     data = []
    #
    #     already_prepared = self.env['measurement.master'].search([])
    #     for c in already_prepared:
    #         data.append(c.id)
    #
    #     size_ids = self.env['measures'].search([])
    #     for m in size_ids:
    #         if not self.age:
    #             if m.measure_name not in data:
    #                 list_ids.append(m.measure_name.id)
    #         else:
    #             size = self.env['measures'].search(['age', '=', self.age.id])
    #             for n in size:
    #                 if n.measure_name not in data:
    #                     list_ids.append(m.measure_name.id)
    #
    #     x = [('id', '!=', list_ids)]
    #     print("data", data)
    #     print("list_ids", list_ids)
    #     print("x", x)
    #     return x

    measure_name = fields.Many2one('measurement.master', string='Measure Name')
    age = fields.Many2one('age', string="Age")
    measures_id = fields.Many2one('age.measures', string="Measure")
    value = fields.Float(string="Value", required=True)
    status = fields.Selection([('active', 'Active'), ('inactive', 'Inactive')], 'Status', default='active')
    size_unit = fields.Selection([('centimeter', 'centimeter'), ('inches', 'inches')], 'Size Unit',
                                 default='inches')

    migrate_data = fields.Boolean(string="Migrate", default=False)
    reference_id = fields.Integer(string="Reference Id", readonly=True)

    # @api.multi
    # def _get_required_domain(self):
    #     print("dd")
    #     print(er)
    #     if self.measure_name:
    #         record_list = []
    #         req_measure = self.env['measures'].search([('measure_name', '=', self.measure_name.id)])
    #         for record in req_measure:
    #             if self.measure_name.id == record.measure_name.id:
    #                 record_list.append(record.age.id)
    #         return {'domain': {'age': [('id', '!=', record_list)]}}

    @api.model
    def create(self, vals):

        result = super(Measures, self).create(vals)

        # P:code for updating the pflo id in hoitymoppet in creation of company in pflo
        req_dict = {
            "mesure_name": result.measure_name.reference_id or '',
            "age": result.age.reference_id or '',
            "value": result.value or '',
            "status": result.status or '',
            "size_unit": result.size_unit or '',
            "migrate_data": result.migrate_data or False,
            "reference_id": result.id or '',
            "company_id": self.env.user.company_id.reference_id or None,
        }

        try:
            migrate = result['migrate_data']
            if migrate and not result.reference_id:
                request = requests.post(url + '/create-measures/',
                                        data=req_dict)

                created_measures_id = request.json()
                print("response", request.json())
                result.reference_id = created_measures_id['id']
        except KeyError:
            raise ValidationError("Response from HoityMoppet : {}".format(next(iter(request.json().values()))))

        return result

    @api.multi
    def write(self, vals):

        result = super(Measures, self).write(vals)

        requested_dict = {
            "mesure_name": self.measure_name.reference_id,
            "age": self.age.reference_id,
            "value": self.value,
            "status": self.status,
            "size_unit": self.size_unit,
            "migrate_data": self.migrate_data,
            "reference_id": self.id,
            "company_id": self.env.user.company_id.reference_id or None,
        }

        # If not already migrateds
        if 'migrate_data' in vals:
            migrate_dt = vals.get('migrate_data')

            # create on click of migrate data as data is not already migrated
            if migrate_dt:
                if not self.reference_id:

                    try:
                        migrate = vals['migrate_data']
                        if migrate:
                            request = requests.post(url + '/create-measures/',
                                                    data=requested_dict)

                            created_measures_id = request.json()
                            print("response", request.json())
                            self.reference_id = created_measures_id['id']
                    except KeyError:
                        raise ValidationError("Response from HoityMoppet : {}".format(next(iter(request.json().values()))))

            else:
                del_request = requests.put(
                    url + '/delete-measures/' + str(self.reference_id) + '/',
                    verify=True)
                del_request.json()
                # delete data from hoitymoppet!

        if self.migrate_data:
            # if data edited with migrated data true
            requests.put(url + '/update-measures/' + str(self.reference_id) + '/',
                         data=requested_dict)

        return result
# Piyush: code for adding class for Measures ends here


# Piyush: code for adding class for UserCustomMeasures
class UserCustomMeasures(models.Model):
    _name = "custom.measures"
    _description = "Model for UserCustomMeasures"

    user_custom_size_name = fields.Char(string="Custom Size")
    customer = fields.Many2one('res.partner', string="Customer")
    measures = fields.Many2one('measurement.master', string='Measure Name')
    measures_id = fields.Many2one('measures', string='Measure Name')
    age = fields.Many2one('age', string="Age", required=True)
    custom_measures_master = fields.Many2one('user.custom.measures.master', string="Custom Measures Master")
    standard_value = fields.Float(string="Standard Value", default=0)
    associated_company = fields.Many2one('res.company', string="Company", default=lambda self: self.env.user.company_id)
    custom_value = fields.Float(string="Custom Value", default=0)
    status = fields.Selection([('active', 'Active'), ('inactive', 'Inactive')], 'Status', default='active')
    size_unit = fields.Selection([('centimeter', 'centimeter'), ('inches', 'inches')], 'Size Unit',
                                 default='inches')

    migrate_data = fields.Boolean(string="Migrate", default=False)
    reference_id = fields.Integer(string="Reference Id", readonly=True)

    @api.multi
    @api.depends('user_custom_size_name')
    def name_get(self):
        result = []
        for dt in self:
            name = dt.user_custom_size_name
            result.append((dt.id, name))
        return result

    @api.model
    def create(self, values):
        result = super(UserCustomMeasures, self).create(values)
        return result
# Piyush: code for adding class for UserCustomMeasures ends here


# Piyush: code for coupon details model
def date_validation(initial_date, final_date):
    if initial_date and final_date:
        # check for their relation among themselves
        required_from_date = datetime.strptime(initial_date, '%Y-%m-%d').date()
        required_to_date = datetime.strptime(final_date, '%Y-%m-%d').date()
        if required_to_date < required_from_date:
            raise ValidationError("Valid from date should not be greater than Valid to date !")

        # check for future date
        now = fields.date.today()
        required_from_date = datetime.strptime(initial_date, '%Y-%m-%d').date()
        required_to_date = datetime.strptime(final_date, '%Y-%m-%d').date()
        if required_from_date < now or required_to_date < now:
            raise ValidationError("Both the valid from and valid to date should be future date !")


class AvailableCoupons(models.Model):
    _name = "available.coupons"
    _description = "Model for handling couppons information"

    @api.multi
    @api.constrains('partner_ids', 'allowed_users')
    def check_partners(self):
        for rec in self:
            if rec.allowed_users != 'all' and not rec.partner_ids:
                raise ValidationError("Please provide specific Customers!")

    name = fields.Char(string="Coupon Name", required=True)
    coupon_description = fields.Char(string="Coupon Description", required=True, default="Details of the given coupon.")
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.user.company_id.id,
                                 readonly=True)
    valid_from = fields.Date(string='Valid From', default=fields.datetime.now(),
                             help="Manually set the starting date of your coupon (offer), should be future date.")
    valid_to = fields.Date(string='Valid Upto', default=fields.datetime.now(),
                           help="Manually set the expiration date of your coupon (offer), should be future date.")
    minimum_amount = fields.Float(string="Minimum Order Amount", default=0.0)
    limit_number = fields.Integer(string="Number of Times Coupons Can be Used", default=0)
    coupon_type = fields.Selection([
        ('Percentage', 'Percentage'), ('Fixed', 'Fixed')], default='Percentage', string="Coupon Type")
    coupon_value = fields.Float(string="Coupon Value", required=True)
    allowed_users = fields.Selection([
        ('all', 'All'), ('specific', 'Specific')], default="all", string="Allowed Users")
    user_ids = fields.Many2many('res.users', string="User List")
    partner_ids = fields.Many2many('res.partner', string="Partners List")
    status = fields.Selection([('active', 'Active'), ('inactive', 'Inactive')], 'Status', default='active')
    migrate_data = fields.Boolean(string="Migrate", default=False)
    reference_id = fields.Integer(string="Reference Id", readonly=True)

    @api.multi
    @api.constrains('name')
    def _check_coupon_name_duplicate(self):
        """
        Method for checking that name should not duplicate for the Coupon.
        """
        for line in self:
            if line.name:
                check = self.env['available.coupons'].search([('name', '=', line.name)])
                if check and len(check) > 1:
                    raise ValidationError(_('Duplicate Coupon Codes are not allowed !'))

    @api.onchange('allowed_users')
    def onchange_allowed_users(self):
        check = self.env['res.partner'].search([('parent_id', '=', False), ('customer', '=', True)])
        domain = {}
        partner_req = []
        for cx in check:
            partner_req.append(cx.id)
        domain = {'domain': {'partner_ids': [('id', '=', partner_req)]}}
        return domain

    @api.onchange('coupon_value')
    def coupon_value_onchange(self):
        for rec in self:
            if rec.coupon_value and rec.coupon_type == 'Percentage' and rec.coupon_value > 99:
                raise ValidationError("Coupon Value for Percentage type can not be greater than 99")

    def validation_checks(self, vals):
        # if data is being sent to hoitymoppet then these are mandatory fields
        if 'migrate_data' in vals:
            migrate_value = vals.get('migrate_data')
            if migrate_value:

                # company check
                if 'company_id' in vals:
                    company = vals.get('company_id')
                    if not company.reference_id:
                        company_name = self.env['res.company'].search([('id', '=', company.id)])
                        raise ValidationError("{} company is not migrated in Hoitymoppet! ".format(company_name.name))

                # users check
                if 'partner_ids' in vals and 'allowed_users' in vals:
                    all_usr = vals.get('allowed_users')
                    if all_usr == 'specific':
                        # multiple users while creating
                        user_all = vals.get('partner_ids')
                        for user_req in user_all:
                            for usr in user_req[2]:
                                if usr:
                                    migrated_usr = self.env['res.users'].search([('id', '=', usr)])
                                    if migrated_usr:
                                        if not migrated_usr.reference_id:
                                            raise ValidationError(
                                                _("{} User is not created in Hoitymoppet !".format(migrated_usr.name)))

    @api.model
    def create(self, vals):
        self.validation_checks(vals=vals)
        if 'valid_from' in vals and 'valid_to' in vals:
            from_dt = vals.get('valid_from')
            to_dt = vals.get('valid_to')
            date_validation(initial_date=from_dt, final_date=to_dt)

        result = super(AvailableCoupons, self).create(vals)
        if result.migrate_data:

            users_list = [cx.reference_id for cx in result.partner_ids] or False
            all_cx = False
            if not users_list:
                all_cx = True
            required_from_date = datetime.strptime(result.valid_from, '%Y-%m-%d').date()
            required_to_date = datetime.strptime(result.valid_to, '%Y-%m-%d').date()

            # P:code for updating the pflo id in hoitymoppet in creation of coupon in pflo
            required_dict = {
                "code": result.name or 'default',
                "valid_from": required_from_date or fields.datetime.now,
                "valid_to": required_to_date or fields.datetime.now,
                "limit_number": result.limit_number or 0,
                "minimum_amount": result.minimum_amount or 0.0,
                "company_id": result.company_id.reference_id or False,
                "discount_type": result.coupon_type or 'Percentage',
                "discount": result.coupon_value or 0.0,
                "coupon_description": result.coupon_description or '',
                "all_customer": all_cx or False,
                "customer": users_list or None,
                "migrate_data": result.migrate_data or True,
                "reference_id": result.id,
                "active": True,
            }
            request = requests.post(url + '/create-coupon/',
                                    data=required_dict)

            created_coupon_id = request.json()
            print("response", request.status_code, request.json())
            result.reference_id = created_coupon_id['id']

        return result

    @api.multi
    def write(self, vals):
        self.validation_checks(vals=vals)
        if 'valid_from' in vals or 'valid_to' in vals:
            initial_date = vals.get('valid_from') or self.valid_from
            final_date = vals.get('valid_to') or self.valid_to
            if initial_date and final_date:
                # check for their relation among themselves
                required_from_date = datetime.strptime(initial_date, '%Y-%m-%d').date()
                required_to_date = datetime.strptime(final_date, '%Y-%m-%d').date()
                if required_to_date < required_from_date:
                    raise ValidationError("Valid from date should not be greater than Valid to date !")

                # check for future date
                now = fields.date.today()
                required_from_date = datetime.strptime(initial_date, '%Y-%m-%d').date()
                required_to_date = datetime.strptime(final_date, '%Y-%m-%d').date()
                if required_to_date < now:
                    raise ValidationError("Valid to date should be future date !")

        result = super(AvailableCoupons, self).write(vals)

        users_list = [cx.reference_id for cx in self.partner_ids] or False
        all_cx = False
        if not users_list:
            all_cx = True
        required_from_date = datetime.strptime(self.valid_from, '%Y-%m-%d').date()
        required_to_date = datetime.strptime(self.valid_to, '%Y-%m-%d').date()

        requested_dict = {
            "code": self.name or 'default',
            "valid_from": required_from_date or fields.datetime.now,
            "valid_to": required_to_date or fields.datetime.now,
            "limit_number": self.limit_number or 0,
            "minimum_amount": self.minimum_amount or 0.0,
            "company_id": self.company_id.reference_id or False,
            "discount_type": self.coupon_type or 'Percentage',
            "all_customer": all_cx or False,
            "coupon_description": self.coupon_description or False,
            "discount": self.coupon_value or 0.0,
            "customer": users_list or None,
            "migrate_data": self.migrate_data or True,
            "reference_id": self.id,
            "active": True,
        }

        # If not already migrated
        if 'migrate_data' in vals:
            migrate_dt = vals.get('migrate_data')

            # create on click of migrate data as data is not already migrated
            if migrate_dt:
                if not self.reference_id:
                    self.validation_checks(vals=vals)
                    try:
                        request = requests.post(url + '/create-coupon/',
                                                data=requested_dict)

                        created_coupon_id = request.json()
                        print("response", request.json())
                        self.reference_id = created_coupon_id['id']
                    except KeyError:
                        # x = next(iter(request.json().values()))[0]
                        # print(x)
                        raise ValidationError("HM - {}".format((next(iter(request.json().values())))))

            else:
                requested_dict['active'] = False
                request = requests.put(url + '/update-coupon/' + str(self.reference_id) + '/',
                                       data=requested_dict)
                print("response", request.json())

        if self.migrate_data:
            request = requests.put(url + '/update-coupon/' + str(self.reference_id) + '/',
                                   data=requested_dict)
            print("response", request.json())
        return result
# P: code ends for product creation


# Piyush: code for adding user custom measure master 20-10-2020
class UserCustomMeasuresMaster(models.Model):
    _name = "user.custom.measures.master"
    _description = "Master for User Custom Measure!"

    @api.multi
    @api.depends('user_custom_size_name')
    def name_get(self):
        result = []
        for dt in self:
            name = dt.user_custom_size_name
            result.append((dt.id, name))
        return result

    user_custom_size_name = fields.Char(string='User Custom Size', required=True)
    customer_id = fields.Many2one('res.partner', string="Customer Name", required=True)
    age_id = fields.Many2one('age', string="Age")
    associated_company = fields.Many2one('res.company', string="Company", default=lambda self: self.env.user.company_id)
    status = fields.Selection([('active', 'Active'), ('inactive', 'Inactive')], 'Status', default='active')
    migrate_data = fields.Boolean(string="Migrate", default=False)
    reference_id = fields.Integer(string="Reference Id", readonly=True)
# Piyush: code for adding user custom measure master ends here


# Jatin: code for adding shipping charges
class ShippingCharges(models.Model):
    _name = "shipping.charges"
    _description = "Master for shipping charges"

    # Piyush: code for constrains on 17dec
    @api.multi
    @api.constrains('charge_type', 'max_charge', 'migrate_data')
    def _check_for_constrains(self):
        if self.migrate_data and self.charge_type == 'prod_based_charge':
            if not self.max_charge:
                raise ValidationError("Please select max charge type !")

    # Piyush: code for constrains on 17dec ends here

    associated_company = fields.Many2one('res.company', string="Company", default=lambda self: self.env.user.company_id,
                                         readonly=True)
    status = fields.Selection([('active', 'Active'), ('inactive', 'Inactive')], 'Status', default='active')
    migrate_data = fields.Boolean(string="Migrate", default=False)
    reference_id = fields.Integer(string="Reference Id", readonly=True)
    free_order_value = fields.Float(string="Free Order Value")
    charge_type = fields.Selection(
        [('specific_amount', 'Charge Specific Amount'), ('prod_based_charge', 'Product Based Charge')], 'Charge Type',
        default='specific_amount')
    max_charge = fields.Selection([('max_value', 'Max Value'), ('sum_value', 'Sum Of Value')], 'Max Charge')

    specific_charge = fields.Float(string="Specific Charge")

    @api.model
    def create(self, vals):
        """
        create function which will run only once for a particular company. It will return validation error while
        creating infomation for next row of same company.
        :param vals: **datadict
        """
        check_existing_data = self.env['shipping.charges'].search([])
        if check_existing_data:
            raise UserError("Data already exist, cannot create new. Please edit that.")
        result = super(ShippingCharges, self).create(vals)
        if result.migrate_data:
            # P:code for updating the pflo id in hoitymoppet in creation of coupon in pflo
            required_dict = {
                "associated_company": self.env.user.company_id.reference_id or None,
                "free_order_value": result.free_order_value or 0.0,
                "specific_charge": result.specific_charge or 0.0,
                "charge_type": result.charge_type or 'specific_amount',
                "max_charge": result.max_charge or None,
                "migrate_data": result.migrate_data or True,
                "reference_id": result.id,
                "status": result.status or 'active',
            }
            request = requests.post(url + '/create-shipping-charge/',
                                    data=required_dict)

            created_instance_id = request.json()
            print("response", request.status_code, request.json())
            result.reference_id = created_instance_id['id']
        return result

    @api.multi
    def write(self, vals):

        # if data is being sent to hoitymoppet then these are mandatory fields
        if 'migrate_data' in vals:
            migrate = vals.get('migrate_data')

        result = super(ShippingCharges, self).write(vals)

        requested_dict = {
            "associated_company": self.env.user.company_id.reference_id or None,
            "free_order_value": self.free_order_value or 0.0,
            "specific_charge": self.specific_charge or 0.0,
            "charge_type": self.charge_type or 'specific_amount',
            "max_charge": self.max_charge or None,
            "migrate_data": self.migrate_data or True,
            "reference_id": self.id,
            "status": self.status or 'active',
        }

        # If not already migrated
        if 'migrate_data' in vals:
            migrate_dt = vals.get('migrate_data')

            # create on click of migrate data as data is not already migrated
            if migrate_dt:
                if not self.reference_id:
                    try:
                        request = requests.post(url + '/create-shipping-charge/',
                                                data=requested_dict)

                        created_instance_id = request.json()
                        print("response", request.json())
                        self.reference_id = created_instance_id['id']
                    except KeyError:
                        raise ValidationError("Response from HoityMoppet : {}".format(next(iter(request.json().values()))))

            else:
                request = requests.put(
                    url + '/update-shipping-charge/' + str(self.reference_id) + '/',
                    data=requested_dict)
                print("response", request.json())

        if self.migrate_data:
            requests.put(url + '/update-shipping-charge/' + str(self.reference_id) + '/',
                         data=requested_dict)
        return result


# Piyush: code for adding dynamic email template description on 28-10-2020
class EmailDescription(models.Model):
    _name = "email.description"
    _description = "Model for making email descriptions dynamic based on the subject."

    name = fields.Char('Template Name')
    subject = fields.Selection(
        [('registration', 'Registration Template'), ('order_confirmation', 'Order Confirmation'),
         ('status_change', 'Status Change')], 'Email Template For',
        default='registration')
    email_description = fields.Text('Email Description')
    migrate_data = fields.Boolean(string="Migrate", default=False)
    reference_id = fields.Integer(string="Reference Id", readonly=True)

    @api.model
    def create(self, vals):
        result = super(EmailDescription, self).create(vals)
        if result.migrate_data:
            # P:code for updating the pflo id in hoitymoppet in creation of coupon in pflo
            required_dict = {
                "name": result.name or 'default',
                "subject": result.subject or 'registration',
                "email_description": result.email_description or '',
                "migrate_data": result.migrate_data or True,
                "reference_id": result.id,
            }
            request = requests.post('http://192.168.2.18:8000/accounts/create-email-description/',
                                    data=required_dict)

            created_instance_id = request.json()
            print("response", request.status_code, request.json())
            result.reference_id = created_instance_id['id']
        return result

    @api.multi
    def write(self, vals):
        result = super(EmailDescription, self).write(vals)

        requested_dict = {
            "name": self.name or 'default',
            "subject": self.subject or 'registration',
            "email_description": self.email_description or '',
            "migrate_data": self.migrate_data or True,
            "reference_id": self.id,
        }

        # If not already migrated
        if 'migrate_data' in vals:
            migrate_dt = vals.get('migrate_data')

            # create on click of migrate data as data is not already migrated
            if migrate_dt:
                if not self.reference_id:
                    try:
                        request = requests.post('http://192.169.2.18:8000/accounts/create-email-description/',
                                                data=requested_dict)

                        created_instance_id = request.json()
                        print("response", request.json())
                        self.reference_id = created_instance_id['id']
                    except KeyError:
                        raise ValidationError("Response from HoityMoppet : {}".format(next(iter(request.json().values()))))

        if self.migrate_data:
            request = requests.put('http://192.169.2.18:8000/accounts/update-email-description/' + str(self.reference_id) + '/',
                                   data=requested_dict)
            print("response", request.json())
        return result
# Piyush: code for adding dynamic email template description on 28-10-2020 ends here


class AdvancePayment(models.Model):
    _inherit = "account.payment"

    @api.model
    def create(self, vals):
        print('coming from hoituyyyyyyyy')
        # if data is being sent to hoitymoppet then these are mandatory fields
        result = super(AdvancePayment, self).create(vals)
        return result


# Piyush: code for adding Shipping Product on 16-12-2020
class ShippingProduct(models.Model):
    _name = "shipping.product"
    _description = "Model for adding product on the sale order line."

    @api.multi
    @api.constrains('percentage', 'migrate_data')
    def _check_for_constrains(self):
        if self.migrate_data and self.percentage:
            if 0 > self.percentage > 100:
                raise ValidationError("Tax Percentage should be between 0 and 100, both values excluded !")

    name = fields.Char('Name', required=True)
    shipping_charge = fields.Selection([('courier_charges', 'Courier Charges')], 'Shipping Type', required=True,
                                       default='courier_charges')
    percentage = fields.Integer('Percentage of Tax', required=True)
    product_id = fields.Many2one('product.product', 'Product', required=True)
    migrate_data = fields.Boolean(string="Migrate", default=False)
    reference_id = fields.Integer(string="Reference Id", readonly=True)

    @api.model
    def create(self, vals):
        """
        create function which will run only once for a particular record. It will return validation error while
        creating information for next row of same.
        :param vals: **datadict
        """
        check_existing_data = self.env['shipping.product'].search([])
        if check_existing_data:
            raise UserError("Data already exist, cannot create new. Please edit that.")
        result = super(ShippingProduct, self).create(vals)
        if result.migrate_data:
            # P:code for updating the pflo id in hoitymoppet in creation of coupon in pflo
            required_dict = {
                "name": result.name or 'default',
                "product_id": result.product_id.id,
                "shipping_charge": result.shipping_charge,
                "percentage": result.percentage,
                "migrate_data": result.migrate_data or True,
                "reference_id": result.id,
            }
            request = requests.post(url + '/create-shipping-product/',
                                    data=required_dict)

            created_instance_id = request.json()
            print("response", request.status_code, request.json())
            result.reference_id = created_instance_id['id']
        return result

    @api.multi
    def write(self, vals):

        # if data is being sent to hoitymoppet then these are mandatory fields
        if 'migrate_data' in vals:
            migrate = vals.get('migrate_data')

        result = super(ShippingProduct, self).write(vals)

        product = self.env['product.template'].search([('id', '=', self.product_id.product_tmpl_id.id)]).reference_id
        requested_dict = {
            "name": self.name or 'default',
            "product_id": self.product_id.id,
            "shipping_charge": self.shipping_charge,
            "percentage": self.percentage,
            "migrate_data": self.migrate_data or True,
            "reference_id": self.id,
        }

        # If not already migrated
        if 'migrate_data' in vals:
            migrate_dt = vals.get('migrate_data')

            # create on click of migrate data as data is not already migrated
            if migrate_dt:
                if not self.reference_id:
                    try:
                        request = requests.post(url + '/create-shipping-product/',
                                                data=requested_dict)

                        created_instance_id = request.json()
                        print("response", request.json())
                        self.reference_id = created_instance_id['id']
                    except KeyError:
                        raise ValidationError(
                            "Response from HoityMoppet : {}".format(next(iter(request.json().values()))))

            else:
                request = requests.put(
                    url + '/update-shipping-product/' + str(self.reference_id) + '/',
                    data=requested_dict)
                print("response", request.json())

        if self.migrate_data:
            requests.put(url + '/update-shipping-product/' + str(self.reference_id) + '/',
                         data=requested_dict)
        return result

# Piyush: code for adding and migrating shipping charges on 16-12-2020 ends here
