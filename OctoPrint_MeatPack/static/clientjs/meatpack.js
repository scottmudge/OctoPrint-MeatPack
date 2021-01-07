(function (global, factory) {
    if (typeof define === "function" && define.amd) {
        define(["OctoPrintClient"], factory);
    } else {
        factory(global.OctoPrintClient);
    }
})(this, function (OctoPrintClient) {
    var OctoPrintMeatPackClient = function (base) {
        this.base = base;
    };

    OctoPrintMeatPackClient.prototype.get = function (refresh, opts) {
        return this.base.get(
            this.base.getSimpleApiUrl("meatpack"),
            opts
        );
    };

    OctoPrintClient.registerPluginComponent(
        "meatpack",
        OctoPrintMeatPackClient
    );
    return OctoPrintMeatPackClient;
});
