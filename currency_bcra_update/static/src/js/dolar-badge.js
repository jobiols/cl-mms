odoo.define('dolar_badge', function(require) {
    var Widget = require('web.Widget');
    var SystrayMenu = require('web.SystrayMenu');
    var UserMenu = require('web.UserMenu');
    var session = require('web.session');
    var Dialog = require('web.Dialog');
    var core = require('web.core');
    var ajax = require('web.ajax');
    var qweb = core.qweb;
    var _t = core._t;

    var BcraBadge = Widget.extend({
        template: 'BcraBadge',
        events: {
        },
        start: function() {
            var res = this._super.apply(this, arguments);
            this.loadDolar().then(this.actualizar.bind(this));
            return res;
        },
        loadDolar: function() {
            return this._rpc({
                model: 'bcra.scrap',
                method: 'get_last_rate',
            });
        },
        actualizar: function(rate) {
            this.$('#dolar-badge').text("Dólar: $ " + `${rate.rate} \n (${rate.date})`);
        },
    });

    SystrayMenu.Items.push(BcraBadge);

    return {
        Menu: BcraBadge,
    };
});
