odoo.define('web_widget_many2many_tags_open', function (require) {
    "use strict";

    var relational_fields = require('web.relational_fields');
    var FormFieldMany2ManyTags = relational_fields.FormFieldMany2ManyTags;
    var ListFieldMany2ManyTags = relational_fields.ListFieldMany2ManyTags;

    FormFieldMany2ManyTags.include({
        _onOpenColorPicker: function (event) {
            var open_view = this.nodeOptions.open_view;
            if (open_view && this.mode === 'readonly') {
                event.preventDefault();
                event.stopPropagation();
                var self = this;
                var tag_id = $(event.currentTarget).data('id');
                this._rpc({
                    model: this.field.relation,
                    method: 'get_formview_action',
                    args: [[tag_id]],
                    context: this.record.getContext(this.recordParams),
                }).then(function (action) {
                    self.trigger_up('do_action', {action: action});
                });
            } else {
                this._super.apply(this, arguments);
            }
        }
    });

    // 05 Nov devashish | for creating wizard on many2many in treeview / listview
    ListFieldMany2ManyTags.include({
        _onOpenColorPicker: function (event) {
            var open_view = this.nodeOptions.open_view;
            if (open_view && this.mode === 'readonly') {
                event.preventDefault();
                event.stopPropagation();
                var self = this;
                var tag_id = $(event.currentTarget).data('id');
                this._rpc({
                    model: this.field.relation,
                    method: 'get_formview_action',
                    args: [[tag_id]],
                    context: this.record.getContext(this.recordParams),
                }).then(function (action) {
                    self.trigger_up('do_action', {action: action});
                });
            } else {
                this._super.apply(this, arguments);
            }
        }
    });
    // End

});


// document.readyState(function(){
//     setTimeout(function(){
//         // var all_input = $(".o_input");
//         // $(all_input).attr("disabled", "disabled");
//         $(".o_input").attr("disabled", "disabled");
//     },1000);
// });