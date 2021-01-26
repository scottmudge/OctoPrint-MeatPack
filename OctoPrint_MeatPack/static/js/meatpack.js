/*
 * View model for OctoPrint-MeatPack
 *
 * Author: Scott Mudge <mail@scottmudge.com>
 * License: AGPLv3
 */

$(function() {

    function MeatPackViewModel(parameters) {
        var self = this;

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


        self.printerState = parameters[0];
        self.settings = parameters[1];
        self.printerConn = parameters[2];

        self.transmissionStats = ko.observableArray([]);
        self.dataReceived = false;
        self.totalBytes = 0.0
        self.totalBytesSec = 0.0
        self.packedBytes = 0.0

        self.packingEnabled = ko.pureComputed(function() {
            return self.settings.settings.plugins.meatpack.enableMeatPack() ? true : false;
        });

        self.allVisible = ko.pureComputed(function() {
            return self.settings.settings.plugins.meatpack.logTransmissionStats() ? true : false;
        });

        self.showTXStats = ko.pureComputed(function() {
            // #TESTING
            return true;

            if (self.printerConn.isOperational()) return true;
            return false;
        });

        self.requestData = function () {
            OctoPrint.plugins.meatpack.get().done(self.fromResponse)
        };

        self.fromResponse = function(response){
            self.totalBytes = response.transmissionStats.totalBytes;
            self.totalBytesSec = response.transmissionStats.totalBytesSec;
            self.packedBytes = response.transmissionStats.packedBytes;

            // self.transmissionStats(response);
            self.dataReceived = true;
        };

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
                return "No Data";
            }
        };

        self.txPackedString = function() {
            if (self.dataReceived){
                return self.toFileSizeString(self.packedBytes, 3);
            }
            else{
                return "No Data";
            }
        };

        self.txRatioString = function() {

            if (self.dataReceived && self.totalBytes > 0.0){
                var ratio = self.packedBytes / self.totalBytes;
                return ratio.toFixed(3);
            }
            else{
                return "No Data";
            }
        };

        self.txRateString = function() {
            if (self.dataReceived){
                return self.toFileSizeString(Math.round(self.totalBytesSec), 3) + "/sec";
            }
            else{
                return "No Data";
            }
        };

         self.enabledString = ko.pureComputed(function() {
            if (self.packingEnabled()){
                return "Enabled";
            }
            else{
                return "Disabled";
            }
        });

        self.onStartup = self.onUserLoggedIn = function () {
            self.requestData();
            self.updateAllText();
        };

        self.onDataUpdaterPluginMessage = function (plugin, data) {
            if (plugin != "meatpack"){
                return;
            }

            self.requestData();
            self.updateAllText();
        };

        self.updateAllText = function () {
            if (self.showTXStats()){
                document.getElementById("meatpack_packed_tx_string").innerHTML =
                "<span title='" +
                text_packed + "'>" + name_packed + "</span>: <strong>" + self.txPackedString() + "</strong></div>";

                document.getElementById("meatpack_total_tx_string").innerHTML =
                "<span title='" +
                text_total + "'>" + name_total + "</span>: <strong>" + self.txTotalString() + "</strong></div>";

                document.getElementById("meatpack_ratio_string").innerHTML =
                "<span title='" +
                text_ratio + "'>" + name_ratio + "</span>: <strong>" + self.txRatioString() + "</strong></div>";

                document.getElementById("meatpack_rate_string").innerHTML =
                "<span title='" +
                text_txrate + "'>" + name_txrate + "</span>: <strong>" + self.txRateString() + "</strong></div>";
            }
        };


        self.onBeforeBinding = function() {
            var element = $("#state").find("hr:nth-of-type(2)");
            if (element.length) {
                element.after(
                "<section id='meatpack_total_content' data-bind='visible: allVisible()'>" +
                "<strong>TX Statistics</strong>"+
                "<div id='meatpack_packed_tx_string' data-bind='visible: showTXStats()'><span title='" +
                text_packed + "'>" + name_packed + "</span>: No Data</div>" +

                "<div id='meatpack_total_tx_string' data-bind='visible: showTXStats()'><span title='" +
                text_total + "'>" + name_total + "</span>: No Data</strong></div>" +

                "<div id='meatpack_ratio_string' data-bind='visible: showTXStats()'><span title='" +
                text_ratio + "'>" + name_ratio + "</span>: No Data</div>" +

                "<div id='meatpack_rate_string' data-bind='visible: showTXStats()'><span title='" +
                text_txrate + "'>" + name_txrate + "</span>: No Data</div>" +

                "<div id='meatpack_enabled_string' data-bind='visible: showTXStats()'><span title='" +
                text_enabled + "'>" + name_enabled +
                "</span>: <strong data-bind='text: enabledString'></strong></div>" +
                 "<hr >" +
                "</section>"
                );
            }
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: MeatPackViewModel,
        dependencies: ["printerStateViewModel", "settingsViewModel", "connectionViewModel"],
        elements: [
        "#meatpack_total_content",
        "#meatpack_total_tx_string",
        "#meatpack_packed_tx_string",
        "#meatpack_ratio_string",
        "#meatpack_rate_string",
        "#meatpack_enabled_string"]
    });
});
