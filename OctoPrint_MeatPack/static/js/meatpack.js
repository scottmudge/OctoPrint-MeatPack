/*
 * View model for OctoPrint-MeatPack
 *
 * Author: Scott Mudge <mail@scottmudge.com>
 * License: AGPLv3
 */

$(function() {

    function MeatPackViewModel(parameters) {
        var self = this;

        self.settings = parameters[0];
        self.printerConn = parameters[1];

        // Locales strings
        var containerTitle = "Meatpack statistics";

        var name_total = gettext("Effective TX");
        var text_total = gettext("Total transmitted data for lifetime of connection.");

        var name_packed = gettext("Comp. TX");
        var text_packed = gettext("Total packed transmitted data for lifetime of connection.");

        var name_ratio = gettext("Comp. Ratio");
        var text_ratio = gettext("Current compression ratio.");

        var name_txrate = gettext("Effective TX Rate");
        var text_txrate = gettext("Total avg data transmitted per second (5 second period).");

        var name_enabled = gettext("Packing State");
        var text_enabled = gettext("State of whether or not g-code packing is enabled.");

        var txt_no_data = gettext("No data");

        var txt_lbl_disabled = gettext("Disabled");
        var txt_lbl_enabled = gettext("Enabled");

        self.transmissionStats = ko.observableArray([]);
        self.dataReceived = false;
        self.totalBytes = 0.0
        self.totalBytesSec = 0.0
        self.packedBytes = 0.0

        // Settings lookup shortcuts
        self.packingEnabled = ko.pureComputed(function() {
            return self.settings.settings.plugins.meatpack.enableMeatPack() ? true : false;
        });

        self.showStatsInUI = ko.pureComputed(function() {
            return self.settings.settings.plugins.meatpack.logTransmissionStats() ? true : false;
        });

        self.windowType = function() {
            return self.settings.settings.plugins.meatpack.logTransmissionStatsType();
        };


        // Should we show the data based on printer operational status
        self.showTXStats = function() {
            if (self.printerConn.isOperational()) return true;
            return false;
        };

        // Get all statsa data
        self.getAllData = function () {
            // Don't poll api if we don't need it
            if (self.showStatsInUI()){
                OctoPrint.plugins.meatpack.get().done(function(response){
                    self.totalBytes = response.transmissionStats.totalBytes;
                    self.totalBytesSec = response.transmissionStats.totalBytesSec;
                    self.packedBytes = response.transmissionStats.packedBytes;
                    // self.transmissionStats(response);
                    self.dataReceived = true;
                    // Update UI
                    self.updateAllText();
                });
            }
        };

        // String formatting for variables - START
        // Thanks @FormerLurker - github
        var byte = 1024;
        self.toFileSizeString = function (bytes, precision) {
            precision = precision || 0;

            if (bytes < 1.0) bytes = 0.0;

            if (Math.abs(bytes) < byte) {
                return bytes + ' Bytes';
            }
            var units = ['kB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
            var u = -1;
            do {
                bytes /= byte;
                ++u;
            } while (Math.abs(bytes) >= byte && u < units.length - 3);
            return bytes.toFixed(precision) + ' ' + units[u];
        };

        self.txTotalString = function() {
            if (self.dataReceived){
                return self.toFileSizeString(self.totalBytes, 3);
            }
            else{
                return txt_no_data;
            }
        };

        self.txPackedString = function() {
            if (self.dataReceived){
                return self.toFileSizeString(self.packedBytes, 3);
            }
            else{
                return txt_no_data;
            }
        };

        self.txRatioString = function() {
            if (self.dataReceived && self.totalBytes > 0.0){
                var ratio = self.packedBytes / self.totalBytes;
                return ratio.toFixed(3);
            }else{
                return txt_no_data;
            }
        };

        self.txRateString = function() {
            if (self.dataReceived){
                return self.toFileSizeString(Math.round(self.totalBytesSec), 3) + "/sec";
            }
            else{
                return txt_no_data;
            }
        };

        self.enabledString = function() {
            if (self.packingEnabled()){
                return txt_lbl_enabled;
            }
            else{
                return txt_lbl_disabled;
            }
        };

        // String formatting for variables - END

        // On user login redraw data
        self.onUserLoggedIn = function () {
            self.getAllData();
        };

        self.onDataUpdaterPluginMessage = function (plugin, data) {
            if (plugin != "meatpack"){
                return;
            }
            self.getAllData();
        };

        // Update the UI
        self.updateAllText = function () {
            if (!self.showStatsInUI()){
                return false;
            }
            if (self.showTXStats()){
                $("#meatpack_packed_tx_string strong").html(self.txPackedString());
                $("#meatpack_total_tx_string strong").html(self.txTotalString());
                $("#meatpack_ratio_string strong").html(self.txRatioString());
                $("#meatpack_rate_string strong").html(self.txRateString());
                $("#meatpack_enabled_string strong").html(self.enabledString());
            }else{
                // Mimick the standard state look/feel
                $("#meatpack_total_content div strong, #meatpack_widget_container div strong").html('-')
                $("#meatpack_enabled_string strong").html(self.enabledString());
            }
        };

        self.drawContainer = function(){
            // Delete everyhing
            if (!self.showStatsInUI()){
                $('#meatpack_total_content').remove();
                $('#meatpack_widget').remove();
                return;
            }
            if (self.windowType() == "standalone"){
                $('#meatpack_total_content').remove();
                if ($('#meatpack_widget').length == 1){
                    return;
                }
                $('<div id="meatpack_widget" class="accordion-group">\
                    <div class="accordion-heading"><a class="accordion-toggle" data-toggle="collapse" data-target="#meatpack_widget_container"><i class="fas fa-compress icon-black"></i> '+ containerTitle +'</a></div>\
                    <div id="meatpack_widget_container" class="accordion-body in collapse">\
                        <div class="accordion-inner">\
                            <div id="meatpack_packed_tx_string"><span title="'+text_packed + '">' + name_packed + '</span>: <strong></strong></div>\
                            <div id="meatpack_total_tx_string"><span title="'+text_total + '">' + name_total + '</span>: <strong></strong></div>\
                            <div id="meatpack_ratio_string"><span title="'+text_ratio + '">' + name_ratio + '</span>: <strong></strong></div>\
                            <div id="meatpack_rate_string"><span title="'+text_txrate + '">' + name_txrate + '</span>: <strong></strong></div>\
                            <div id="meatpack_enabled_string"><span title="'+text_enabled + '">' + name_enabled + '</span>: <strong></strong></div>\
                        </div>\
                    </div>\
                </div>').insertAfter( "#state_wrapper" );
                return;
            }
            $('#meatpack_widget').remove();
            // Normal inside state panel
            if ($('#meatpack_total_content').length == 1){
                return;
            }
            var element = $("#state hr:eq(1)")
            if (element.length) {
                element.after('<section id="meatpack_total_content">\
                    <strong>'+containerTitle+'</strong>\
                    <div id="meatpack_packed_tx_string"><span title="'+text_packed + '">' + name_packed + '</span>: <strong></strong></div>\
                    <div id="meatpack_total_tx_string"><span title="'+text_total + '">' + name_total + '</span>: <strong></strong></div>\
                    <div id="meatpack_ratio_string"><span title="'+text_ratio + '">' + name_ratio + '</span>: <strong></strong></div>\
                    <div id="meatpack_rate_string"><span title="'+text_txrate + '">' + name_txrate + '</span>: <strong></strong></div>\
                    <div id="meatpack_enabled_string"><span title="'+text_enabled + '">' + name_enabled + '</span>: <strong></strong></div>\
                    <hr/>\
                </section>');
            }
        }

        // Refresh on save
        self.onSettingsHidden = function () {
            self.drawContainer();
        };

        self.onBeforeBinding = function() {
            self.drawContainer();
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: MeatPackViewModel,
        dependencies: ["settingsViewModel", "connectionViewModel"],
    });
});
