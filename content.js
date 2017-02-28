"use strict";
var page = require('webpage').create(),
    system = require('system');

if (system.args.length === 1) {
    console.log('Usage: content.js <URL> screenshot.png');
    phantom.exit(1);
} else {
    page.address = system.args[1];
    page.screenshot = system.args[2];
    page.onError = function(msg, trace) {
        return true;
    };

    page.settings.userAgent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36';
    page.open(page.address, function (status) {
        if (status !== 'success') {
            console.log('FAIL to load the address');
            phantom.exit(1);
        } else {
            page.render(page.screenshot);
            var content = page.content.replace(/<style.*?>[\S\s]+<\/style>|<script.*?>[\S\s]+?<\/script>|<\/?[^>]+(>|$)|['".:,;()\[\]{}|=]/g, "");
            var words = content.split(/\s+/g).filter(function (word) {
                return word != undefined && word.length > 0;
            });
            var result = {
                "screenshot": page.screenshot,
                "content": words.join(' '),
                "html": page.content
            };
            console.log(JSON.stringify(result));
            phantom.exit();
        }
    });
}