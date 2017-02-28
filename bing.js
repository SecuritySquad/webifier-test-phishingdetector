"use strict";
var page = require('webpage').create(),
    system = require('system');

if (system.args.length === 1) {
    console.log('Usage: bing.js "search text" results');
    phantom.exit(1);
} else {
    page.address = 'https://www.bing.com/search?q=' + encodeURI(system.args[1]);
    page.results = system.args[2];
    page.onError = function(msg, trace) {
        return true;
    };

    page.open(page.address, function (status) {
        if (status !== 'success') {
            console.log('FAIL to load the address');
            phantom.exit(1);
        } else {
            var links = page.evaluate(function () {
                var div = document.getElementById('b_results');
                var as = div.getElementsByTagName('a');
                var links = [];
                for (var i = 0; i < as.length; i++) {
                    var link = as[i].href;
                    if (links.indexOf(link) === -1 && link.indexOf('https://www.bing.com/') === -1)
                        links.push(link);
                }
                return links;
            });
            console.log(JSON.stringify(links.slice(0, page.results)));
            phantom.exit();
        }
    });
}