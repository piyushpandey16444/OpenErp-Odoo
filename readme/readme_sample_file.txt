SVN Revision No 
                    1775
Release Date

	08-Sept-2020
Developer 
            Jatin and Aman

List of Changes to be done

  Jatin:-
  Ticket #  : (PROD) - stock - to rectify the stock onhand issue for job work challan
  Ticket #  : (PROD) - stock_ext - to rectify the stock onhand issue for job work challan
  Aman:-
  Ticket # : (PROD) - sale - to rectify the account of the product in invoicing

Affected components/entities

	Python Files  		
  		stock - stock_picking.py(Jatin):-added this to rectify the stock onhand issue in case of job work challan
		sale - sale.py(Aman):-added type which will get the current type of invoice, then call get_invoice_line_account1 function to get account from product form

   	 xml files 
		stock_ext - stock_ext_view.xml(Jatin):-added extra condition in invisble in case of job work challan

Code Review Status 

       Done by Gaurav Gupta sir

Pre-requisites

	N/A

Co-requisites

	N/A

Known issues or Limitations

	N/A

Abbreviations

	N/A	Not applicable
	DBS	DataBase

============================================================================

SVN Revision No
                    1776
Release Date

	09-Sept-2020
Developer
            Aman and Piyush

List of Changes to be done

  Aman:-
  Ticket #  : (PROD) - account - bug in account id (id is not found)
  Ticket #  : (PROD) - sale - singleton error in getting type from invoice
  Piyush:-
  Ticket # : (PROD) - account - allowing only items whose done qty is more than 0

Affected components/entities

	Python Files
  		account - account_invoice.py(Aman):-removed id when pass account in dictionary
  		account - account_invoice.py(Piyush):-code for allowing only items whose done qty is more than 0 in onchange_sale_id() function
		sale - sale.py(Aman):-added a for loop to get type which will get the current type of invoice, then call get_invoice_line_account1 function to get account from product form

   	 xml files


Code Review Status

       Done by Gaurav Gupta sir

Pre-requisites

	N/A

Co-requisites

	N/A

Known issues or Limitations

	N/A

Abbreviations

	N/A	Not applicable
	DBS	DataBase

============================================================================

SVN Revision No
                    1778
Release Date

	11-Sept-2020
Developer
            Jatin

List of Changes to be done

  
  Ticket #  : (PROD) - Tally Integration with odoo
Affected components/entities

        Module Added
                      tally_integration
                      tally_odoo_extension
                      tally_validations

	Python Files
  		
   	 xml files


Code Review Status

       Done by Gaurav Gupta sir

Pre-requisites

	N/A

Co-requisites

	N/A

Known issues or Limitations

	N/A

Abbreviations

	N/A	Not applicable
	DBS	DataBase

============================================================================
SVN Revision No
                    1783
Release Date

	18-Sept-2020
Developer
            Himanshu

List of Changes to be done


  Ticket #  : (PROD) - Inventory Adjustment
Affected components/entities

        Module Added


	Python Files
	stock_inventory.py
	 Removed the pack selection option from inventory adjustment form
         Code added to raise error if the line id is empty in the tree view of inventory adjustment
         Added this code to make lot/serial number field required/readonly when tracking is true/false

   	 xml files

   	 stock_inventory_views.xml

   	 This field is used to apply attrs to product_id when its true/false
         Made this field readyonly
         Required this field when product is of serial, lot type and readonly when it of none type
         Removed the package_id (PACK) from the line_ids in the inventory adjustment


Code Review Status

       Done by Gaurav sir

Pre-requisites

	N/A

Co-requisites

	N/A

Known issues or Limitations

	N/A

Abbreviations

	N/A	Not applicable
	DBS	DataBase

============================================================================
SVN Revision No
                    1785
Release Date

	19-Sept-2020
Developer
            Aman, Jatin, Piyush

List of Changes to be done

Aman
  Ticket 38  : (PROD) - Sale Order - Add a new column (stock update) in main tree view in without mrp database
  Ticket 38  : (PROD) - Sale Order - Available quantity was not displaying on sale order form when so is created from sale quotation
  Ticket 38  : (PROD) - Sale Order - Add a validation on stock update button. If there is not pending quantity in mto products then it should throw validation error when we press stock update button
  Ticket 38  : (PROD) - Inventory Adjustment - Pending quantity was not displaying in Inventory adjustment form
Jatin
  Ticket 14  : (PROD) - Tally Integration
Piyush
  Ticket #  : (PROD) - Account Invoice

 Affected components/entities

        Module Added


	Python Files
	Aman
	sale.py - 1) Added field to show stock status at main tree view
	          2) added onchange function to set check_pending_qty value to update or not update on basis of pending qty
	          3) added code to set check_pending_qty value to update or not update on basis of pending qty when so is created from sale quotation
	          4) Created check_mrp_mod function to check mto products
	          5) Created check_stock_status function to check stock status
	          6) Added get_tree_view function because it is called when we open main tree view

	sale_ext_inv_adj.py -
	          1) to update stock status and show produced_quantity when so is created from sale quotation
	          2) added condition of pending quantity. If there is no pending quantity then product will not go to stock.inventory.line
	          3) Added validation, if pending quantity is zero for mto product then validation should be displayed on click of stock update button

	stock_inventory.py -
	          1) Added this code to add pending quantity in stock.inventory.line

	Jatin
	tally_integration/account_group.py - replace name account.group with account.group.import
	tally_integration/test.py - replace name account.group with account.group.import

	Piyush
	sale/account_invoice.py -
	          1) code for adding sale line ids on invoice from sale order

   	 xml files
   	 Aman
   	 sale_views.xml -
   	          1) Added new tree view for no mrp database
   	          2) Added server action to call dynamic tree view


Code Review Status

       Done by Gaurav sir

Pre-requisites

	N/A

Co-requisites

	N/A

Known issues or Limitations

	N/A

Abbreviations

	N/A	Not applicable
	DBS	DataBase

============================================================================
SVN Revision No
                    1790
Release Date

	07-Oct-2020
Developer
            Himanshu , Aman 

List of Changes to be done

Himanshu 
   Ticket# -Inventory Adjustment - Freezing/required the lot/serial when sale_order products are added in inventory_adjustment on the click of start inventory
   Ticket# -Stock move - Comment the code 

 Affected components/entities

        Module Added


	Python Files
	Himanshu
	stock_inventory.py - 1) Added code for freezing tracking when the tracebility is no-tracking and required when tracebility is unique and lots type.

	Aman
        stock_move.py - 2) Commented the code

	

   	xml files
   	 

Code Review Status

       Done by gaurav sir

Pre-requisites

	N/A

Co-requisites

	N/A

Known issues or Limitations

	N/A

Abbreviations

	N/A	Not applicable
	DBS	DataBase

============================================================================

SVN Revision No
                    1796
Release Date

	8-Oct-2020
Developer
    Aman

List of Changes to be done

    Ticket #  : (PROD) - Sale Order - New Stages will be Quotation, Quotation Sent, Confirmed, Partial Ordered, Done, Lost Order, and Cancel
    Ticket #  : (PROD) - Sale Order - After email sent to vendor it should move in quotation sent stage
    Ticket #  : (PROD) - Sale Order - After confirmation and if sale order is created then it should move in confirm stage.
    Ticket #  : (PROD) - Sale Order - If sales order is confirmed for the quotation then it should move to Done Stage.
    Ticket #  : (PROD) - Sale Order - Unit rate is picking wrong when order is generated from quotation
    Ticket #  : (PROD) - Sale Order - Once order is created for all quantities available in Quotation for all the products then no further order creation is allowed "Validation MSG required" that "Order already placed for all quantities of this quotation".
    Ticket #  : (PROD) - Sale Order - Two Print buttons and two sent for email buttons are showing at the time of creating quotation
    Ticket #  : (PROD) - Sale Order - Customer name should get freezed after adding of item line and it should be editable again if all item lines get removed
    Ticket #  : (PROD) - Sale Order - If SO is creation from quotation then its order type should not allow to change
    Ticket #  : (PROD) - Sale Order - Tax value is not showing in footer level of SO
    Ticket #  : (PROD) - Sale Order - In case of second time creating partial then gross value also not picking
    Ticket #  : (PROD) - Sale Order - Existing item should not allow to change on SO level
    Ticket #  : (PROD) - Sale Order - Quotation stage is not moving in Done in case of partial order confirmation
    Ticket #  : (PROD) - Sale Order - If SO is created from Quotation then addition of item should not allow

 Affected components/entities

        Module Added


	Python Files
	sale.py - 1) Added check_so_from_sq field to make fields readonly when so is created from sale quotation.
	          2) Changed the state of SQ depending on the quantity left(done or partial ordered).
	          3) added self.price_unit since price was getting changed when we change product qty.
	          4) Added a validation to check unit price and product quantity
	          5) Added onchange function to check discount

	sale_ext_inv_adj.py -
	          1) When we create so from sale.quotation unit price was not displaying correct so did some changes for that.
	          2) Added price tax since it was not displaying on so created from sale quotation
	          3) Corrected code for partial order by subtracting total_qty_ordered_hidden by product_uom_qty so that we can get amount of qty which is left
	          4) added a field to make partner_id readonly
	          5) added a function to make boolean field true or false when we click on order_line
	          6) Added 2 fields to compute total_qty_ordered and hidden so that we can calculate product uom qty
	          7) Added function to compute total_qty_ordered so that we can calculate product uom qty
	          8) Added function to compute total_qty_ordered_hidden so that we can calculate product uom qty
	          9) Added a function to change the state of sale quotation to confirmed
	          10) Added condition to check if customer is selected before selecting product
	          11) Added onchange function to check discount

	mail/wizard/mail_compose_message.py -
	          1) Set sale quotation state to quotation sent when email is sent

	purchase.py
	          1) Added a validation to check unit price and product quantity

	genric.py
	          1) Added check_disct() function to check discount


   	xml files
   	sale_views.xml -
   	          1) Added attrs to make so_type field readonly
   	          2) Added check_so_from_sq field to make some fields readonly when so is created from sale quotation
   	          3) Added attrs to make fields readonly when check_so_from_sq field is true

   	sale_ext_inv_adj_view.xml -
   	          1) added rest_cust for making partner_id as readonly field
   	          2) Added new states to attributes and added a new button use to change state to confirmed
   	          3) Commented 2 buttons because they were extra


Code Review Status

    Done by Gaurav sir

Pre-requisites

	N/A

Co-requisites

	N/A

Known issues or Limitations

	N/A

Abbreviations

	N/A	Not applicable
	DBS	DataBase
============================================================================


SVN Revision No 1797
                    
Release Date

	13-Oct-2020
Developer
            Avinash Kumar


List of Changes to be done


Job Work challan form

Ticket 23  : (PROD) - Error of destination location in product moves of job work challan.
Ticket #  : (PROD) - For lot wise item. If we do not enter any lot and try to confirm form then it gives erorr.
Ticket #  : (PROD) - For lot type product if we add more than 1 lot in lot detail then total done quantity decrease on only one lot (not on both the lots).
Ticket #  : (PROD) - Add functionality for unique product. Do not check lot id in case of unique product on Job work challan form.



Customer credit note

Ticket # : (PROD) - When customer credit note creates from wizard (of customer invoice) it gives error.
Ticket #  : (PROD) - Need to transfer lot details from customer invoice to customer credit notes.
Ticket #  : (PROD) - Working on stock moves customer credit note. (Stock Up)
Ticket #  : (PROD) - Working on updating lot detail because if we add two lots in a product and validate on customer credit note form then only 1 lot detail updated in stock.move.line table. (and total done quantity update on 1 lot).

Ticket #  : (PROD) - On move line freeze quantity field if product type is lot.
Ticket #  : (PROD) - Need to add validation in case of product type lot on customer credit note if lot detail is not provided.
Ticket #  : (PROD) - Reference no and date field on customer credit note make mandatory.
Ticket #  : (PROD) - Add unlink function for product type lot if invoice created from receipt.



Vendor Bill

Ticket 18  : (PROD) - Working on transfer lot detail from receipt to vendor bills.
Ticket #  : (PROD) - When more than 1 receipt on vendor bill then club detail of all the lots.
Ticket #  : (PROD) - When select PO manually then lot detail button is not visible for lot type product.
Ticket #  : (PROD) - Show only those PO on vendor bill whose vendor bill is not created else do not show po and If vendor is selected on vendor bill then show PO of the selected vendor only (Both the flow works on on-change of Vendor or partner_id).

Ticket #  : (PROD) - Add unlink function for product type lot if vendor bill created from receipt.


Vendor Credit note

Ticket 20  : (PROD) - Stock move on vendor credit note.



Affected components/entities

a)Python fiels
- purchase.py
- account/account_invoice.py
- stock/account_invoice.py
- purchase/account_invoice.py


b)xml files
   	 
- account_invoice_view.xml


Code Review Status

       Done by gaurav sir

Pre-requisites

	N/A

Co-requisites

	N/A

Known issues or Limitations

	N/A

Abbreviations

	N/A	Not applicable
	DBS	DataBase
============================================================================
SVN Revision No
                    1800
Release Date

	13-Oct-2020
Developer
    Aman

List of Changes to be done

    Ticket 116  : (PROD) - Need to create some default groups and its tagging with their account type at the time of database creation
    Ticket 117  : (PROD) - Need to change the name of default account type creation at the time of database create and some new account types also required.

 Affected components/entities

        Module Added


	Python Files

   	xml files
   	account/data/data_account_group.xml -
   	          1) Added a new xml file to  create default account group

   	account/data/data_account_type.xml -
   	          1) Added default account types

   	account_view.xml -
   	          1) Added menuitem so that account type can be displayed in ui
   	          2) Added menuitem so that account group can be displayed in ui
   	          3) Added group_id to list view

   	l10n_in/data/l10n_in_chart_data.xml -
   	          1) Added new default chart of accounts

   	l10n_in/data/account_tax_template_data.xml -
   	          1) Added new default taxes

   	l10n_in/data/account_fiscal_position_data.xml -
   	          1) Commented fiscal position tax template as it is not being used and were giving error when all the old taxes were commented

Code Review Status

    Done by Gaurav sir

Pre-requisites

	N/A

Co-requisites

	N/A

Known issues or Limitations

	N/A

Abbreviations

	N/A	Not applicable
	DBS	DataBase
============================================================================

============================================================================
SVN Revision No
                    1801
Release Date

	15-Oct-2020
Developer
    Himanshu

List of Changes to be done

    Ticket #  : A Default chart of account creation required with customer/vendor name on create of Customer and Vendor
    Ticket #  : For the COA its account type should decide at the basis of it is customer or it is a vendor
    Ticket #  : If it is a customer then its account type should be Debtor and If the type is vendor then its account type should be creditor
    Ticket #  : At the time of Customer Invoice and vendor bill their account should select that COA which is linked with their customer or vendor
    Ticket #  : A new field required named as Type in which some hard code fields are available like , Customer, vendor, Employee, Other. On behalf of this we can segregate the type of accounts
    Ticket #  : If Accounts are Customer, Vendor and Employee then their Information related fields also required on COA form which can be came from customer and vendor form at the time of creation

 Affected components/entities

    Module Added

	Python Files
	Account/Account_invoice.py
	    Added the chart_of_account associated with a vendor/customer to the account_id field.
	    Commented the code such that account_id value should not be replaced
	Account/Account.py
	    partner_id is added in the chart of account form such that with the help of it all the fields of vendor and customers can be used.
	    changed the field name from 'Type' to 'Account Type'
	    Added the selection field
	purchase/res_partner.py
	    Added a new create function to make a chart of account on the creation of vendors and customers.
	    Query to get the last code added corresponding to a vendor/customer.
	    First check if there is no code present in the database then add a new one with prefix and if a code is present then increment 1  to it add to the database.

   	xml files
   	Account/Account_views.xml
   	    Added the selection field


Code Review Status

    Done by Gaurav sir

Pre-requisites

	N/A

Co-requisites

	N/A

Known issues or Limitations

	N/A

Abbreviations

	N/A	Not applicable
	DBS	DataBase
============================================================================

SVN Revision No. 1811
                    
Release Date

	21-Oct-2020
Developer
    Avinash Kumar

List of Changes to be done

    Ticket #  : (PROD) - Total scheduling quantity cannot be greater then sale order quantity.(on sale order scheduling form). When created 2
                         scheduling and edit quantity of scheduing 1. 

    Ticket #  : (PROD) - When vendor bill is created from receipt and verify then sequence no of receipt updated which do not required. 
    Ticket #  : (PROD) - Customer credit note form check available quantity (functionality do not need here) for product type lot. Because it 
                         is stock in (so no need to check)  
    Ticket #  : (PROD) - On lot detail form . If same lot is added more then 1 time then stock is going to negative.Add validation so that 
                         user cannot add same lot twice. On Customer invoice form, Dispatch form and Job work challan form.
    Ticket #  : (PROD) - On Issues form extra product line is added when create stock move. In case When same product added two times 
                         (either tracking or no tracking product). 
    Ticket #  : (PROD) - Make lot field mandatory on issues form
    Ticket #  : (PROD) - If product type is tracking then same lot cannot be added twice on issues form.
    Ticket #  : (PROD) - If product type is not tracking then same product cannot be added twice on issues form.



 Affected components/entities

        Module Added


	Python Files
        1.stock_move_line.py
        2.stock_picking.py
        3.purchase.py
        4.stock_move.py
        5.account_invoice.py
        6.sale.py
          

   	xml files
        1.stock_picking_view.xml
   	

Code Review Status

    Done by Gaurav sir

Pre-requisites

	N/A

Co-requisites

	N/A

Known issues or Limitations

	N/A

Abbreviations

	N/A	Not applicable
	DBS	DataBase
============================================================================
SVN Revision No
                    1812
Release Date

	21-Oct-2020
Developer
            Aman, Himanshu

List of Changes to be donebce

Aman
  Ticket 168  : (PROD) - HoityMoppet- sales - sales order- lost sales order functionality is not working fine, getting error. HoityMoppet- sales - sales Quotation- lost sales Quotation- functionality is not working fine, getting error.
  Ticket 169  : (PROD) - Sale Order - HoityMoppet- sales - sales Quotation- while user is generating the duplicate sale Quotation, it is  showing the AMD history details. Step- sales Quotation- duplicate- new document in draft mode( showing AMD)
  Ticket #  : (PROD) - Sale Order - Add table to display taxes, subtotal, total amount.
  Ticket #  : (PROD) - Sale Quotation - Add table to display taxes, subtotal, total amount.
  Ticket #  : (PROD) - Purchase Order - Add table to display taxes, subtotal, total amount.
  Ticket #  : (PROD) - RFQ - Add table to display taxes, subtotal, total amount.
  Ticket #  : (PROD) - Customer Invoice - Add table to display taxes, subtotal, total amount.
  Ticket #  : (PROD) - Vendor Bill - Add table to display taxes, subtotal, total amount.
  Ticket #  : (PROD) - Sale Return - Date must be filled from the invoice selected.
  Ticket #  : (PROD) - Account Invoice - Change the name of customer credit note to sale return and vendor credit note to purchase return.
  Ticket 192  : (PROD) - MRP - Showing error while marking the work order as done, kindly look into it.


 Affected components/entities

        Module Added


	Python Files
        Aman
	sale.py - 1) Added condition for receptions in state bill pending
	          2) Added function for lost order functionality
	          3) Added function to calculate values to display on table below products table
	          4) Added order.calculation.sale model to display taxes, subtotal, total amount
	          5) Created order_calculation_ids onetomany field to access order.calculation.sale model

	sale_ext_inv_adj.py -
	          1) Added function for lost order functionality
	          2) Added function to calculate values to display on table below products table
	          3) Added order.calculation.sale.quotation model to display taxes, subtotal, total amount
	          4) Created order_calculation_ids onetomany field to access order.calculation.sale.quotation model
                  5) Added field to check if SQ is duplicate or not
                  6) Made check_duplicate true because it is a duplicate SQ and its amd should be new
                  7) Added a condition to check if sale quotation is duplicate or not

        purchase.py -
	          1) Added function to calculate values to display on table below products table
	          2) Added order.calculation model to display taxes, subtotal, total amount
	          3) Created order_calculation_ids onetomany field to access order.calculation model

        purchase_ext.py -
	          1) Added function to calculate values to display on table below products table
	          2) Added order.rfq.calculation model to display taxes, subtotal, total amount
	          3) Created order_calculation_ids onetomany field to access order.rfq.calculation model
                  4) Added conditions since account was not picking properly

        account_invoice.py -
	          1) Added function to calculate values to display on table below products table
	          2) Added order.calculation.invoice model to display taxes, subtotal, total amount
	          3) Created order_calculation_ids onetomany field to access order.calculation.invoice model
                  4) Added onchange function to get invoice date of invoice selected in against ref no.

	genric.py -
	          1) Added function for lost order functionality
                  2) Added a function to change the state to lost order
                  3) Added function to calculate taxes to display on table below products table
                  4) Added function to calculate values to display on table below products table

        mail_compose_message.py -
	          1) Set sale quotation state to quotation sent when email is sent

        stock/res_config_settings.py -
                  1) Added field to install stock_ext module
                  2) Added onchange function to make module_stock_ext true when group_stock_production_lot is true and same for false

        res_config.py -
                  1) Validation to check Lot Sequence Generator field

        mrp_workorder.py -
                  1) Added readonly condition for final_lot_id field
                  2) Added for loop since it was giving singleton error in get_final_lot_id() function.

        account_invoice_refund.py -
	          1) Added code to get order_calculation_ids and display it in the table

        Himanshu
        purchase/res_partner.py -
                  1) Added a new functionality to make code run properly for chart of account through vendor and customer.

        account.py -
                  1) Added the new create function for the code that will be added from backend whenever a new chart of accounts will be made



   	 xml files
         Aman
   	 sale_views.xml -
   	          1) Added Calculation table on SO form

         rfq_views.xml -
   	          1) Added Calculation table on RFQ form

         account_invoice_view.xml -
   	          1) Added Calculation table on PO form
   	          2) Changed the name Customer credit note to sales return
                  3) Changed the name Vendor credit note to purchase return

         purchase_views.xml -
   	          1) Added Calculation table on PO form

         sale_ext_inv_adj_view.xml -
   	          1) Added Calculation table on SQ form
              2) Added field to check if SQ is duplicate or not

         stock/res_config_settings_views.xml -
              1) Added field to install stock_ext module

Code Review Status

       Done by Gaurav sir

Pre-requisites

	N/A

Co-requisites

	N/A

Known issues or Limitations

	N/A

Abbreviations

	N/A	Not applicable
	DBS	DataBase

============================================================================

