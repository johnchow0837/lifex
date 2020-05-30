odoo.define('base_rpc_cache.cache', function (require) {
    'use strict';
    var ajax = require('web.ajax');

    var core = require('web.core');
    var Model = require('web.DataModel');
    var _t = core._t;
    var utils = require('web.utils');
    var time = require('web.time');
    var _cache = {};

    function _genericJsonRpc(fct_name, params, fct) {
        var data = {
            jsonrpc: "2.0",
            method: fct_name,
            params: params,
            id: Math.floor(Math.random() * 1000 * 1000 * 1000)
        };
        var xhr = fct(data);
        var result = xhr.pipe(function (result) {
            core.bus.trigger('rpc:result', data, result);
            if (result.error !== undefined) {
                if (result.error.data.arguments[0] !== "bus.Bus not available in test mode") {
                    console.error("Server application error", JSON.stringify(result.error));
                }
                return $.Deferred().reject("server", result.error);
            } else {
                return result.result;
            }
        }, function () {
            //console.error("JsonRPC communication error", _.toArray(arguments));
            var def = $.Deferred();
            return def.reject.apply(def, ["communication"].concat(_.toArray(arguments)));
        });
        // FIXME: jsonp?
        result.abort = function () {
            if (xhr.abort) xhr.abort();
        };
        return result;
    }

    function jsonRpc(url, fct_name, params, settings) {
        var arg_json = JSON.stringify([url, fct_name, params, settings]);
        if (!_cache[arg_json]) {
            _cache[arg_json] = _genericJsonRpc(fct_name, params, function (data) {
                return $.ajax(url, _.extend({}, settings, {
                    url: url,
                    dataType: 'json',
                    type: 'POST',
                    data: JSON.stringify(data, time.date_to_utc),
                    contentType: 'application/json'
                }));
            }).always(function (res) {
                setTimeout(function () {
                    delete _cache[arg_json];
                }, 300);
                return res;
            })
        }
        return _cache[arg_json];
    }

    ajax.jsonRpc = jsonRpc;

    var ListView = require('web.ListView');

    ListView.List.include({
        render_cell: function (record, column) {
            if (column.type !== 'many2many') {
                return this._super.apply(this, arguments);
            }
            var value = record.get(column.id);
            // non-resolved (string) m2m values are arrays
            if (value instanceof Array && !_.isEmpty(value)
                && (!record.get(column.id + '__display') && record.get(column.id + '__display') !== '')) {
                var ids;
                // they come in two shapes:
                if (value[0] instanceof Array) {
                    _.each(value, function (command) {
                        switch (command[0]) {
                            case 4:
                                ids.push(command[1]);
                                break;
                            case 5:
                                ids = [];
                                break;
                            case 6:
                                ids = command[2];
                                break;
                            default:
                                throw new Error(_.str.sprintf(_t("Unknown m2m command %s"), command[0]));
                        }
                    });
                } else {
                    // 2. an array of ids
                    ids = value;
                }
                new Model(column.relation)
                    .call('name_get', [ids, this.dataset.get_context()]).done(function (names) {
                    // FIXME: nth horrible hack in this poor listview
                    // 由于_cache缓存的问题，可能这段代码执行在下面临时设置__display代码之前，所以通过setTimeout把这个值设置 放在下一个
                    setTimeout(function () {
                        record.set(column.id + '__display', _(names).pluck(1).join(', '));
                        record.set(column.id, ids);
                    }, 0);

                });
                // temporary empty display name
                record.set(column.id + '__display', false);
            }
            return column.format(record.toForm().data, {
                model: this.dataset.model,
                id: record.get('id')
            });
        }
    });

    return {
        ajax: ajax,
        ListView: ListView
    }
});