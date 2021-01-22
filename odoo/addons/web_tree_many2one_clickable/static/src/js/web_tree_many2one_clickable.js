/* Copyright 2013 Therp BV (<http://therp.nl>).
 * Copyright 2015 Pedro M. Baeza <pedro.baeza@serviciosbaeza.com>
 * Copyright 2016 Antonio Espinosa <antonio.espinosa@tecnativa.com>
 * Copyright 2017 Sodexis <dev@sodexis.com>
 * Copyright 2018 Camptocamp SA
 * License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl). */

odoo.define('web_tree_many2one_clickable.many2one_clickable', function (require) {
    var ListRenderer = require('web.ListRenderer');

    ListRenderer.include({
        _renderBodyCell: function (record, node, colIndex, options) {
//            console.log("web treee",this)
//            console.log("web treee222222",this.state,this.state.fields)
//            console.log("web fieldddddddd",this.state.fields)
//            console.log("web treee333333",this.state.model)
//            if (!node.attrs.widget && node.attrs.name &&
//                this.state.fields[node.attrs.name] &&
//                this.state.fields[node.attrs.name].type === 'many2one') {
//                // no explicit widget provided on a many2one field,
//                // force `many2one` widget
//                console.log("web clickableeeee",this.state.fields[node.attrs.name].clickable)
//                node.attrs.widget = 'many2one';
//            }
//            console.log("web clickableeeee222222")
//            return this._super(record, node, colIndex, options);
//          Add clickable condition By Pushkal on 03 jan 19 : starts here
            if (!node.attrs.widget && node.attrs.name &&
                this.state.fields[node.attrs.name] &&
                this.state.fields[node.attrs.name].type === 'many2one') {
                // no explicit widget provided on a many2one field,
                // force `many2one` widget
                if (this.state.fields[node.attrs.name].clickable) {
                    node.attrs.widget = 'many2one';
                }
            }
//            console.log("log .............", options);
            return this._super(record, node, colIndex, options);
        }
    });
});
